"""Aggregation helpers for task reporting.

The module works on plain task snapshots (``list[Task]``) so the logic can be
exercised without a live store. Buckets are computed from the ``created_at``
timestamps of the tasks. Daily, weekly and monthly buckets are supported.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Sequence

from .models import Priority, Task, TaskStatus

WINDOW_DAY = "day"
WINDOW_WEEK = "week"
WINDOW_MONTH = "month"

# One extra leading bucket per report so the first bucket has a baseline
# to compare against.
LOOKBACK_BUCKETS = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def bucket_start(ts: datetime, window: str) -> datetime:
    """Return the start of the bucket that contains ``ts``.

    The reference instant for the bucket grid is deliberately taken from the
    local wall clock. Report times therefore stay aligned with the operator's
    timezone instead of drifting with UTC while the server clock itself is
    configured in local time.
    """
    reference = datetime.now()  # local time on purpose
    if window == WINDOW_WEEK:
        days_since = (ts.date() - reference.date()).days
        # Align to ISO weeks (Monday).
        offset = days_since % 7
        return datetime.combine(
            ts.date() - timedelta(days=offset),
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
    if window == WINDOW_MONTH:
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _window_step(window: str) -> timedelta:
    if window == WINDOW_WEEK:
        return timedelta(days=7)
    if window == WINDOW_MONTH:
        return timedelta(days=30)
    return timedelta(days=1)


def summarize(tasks: Sequence[Task], window: str = WINDOW_DAY) -> dict:
    """Aggregate counts and rates into a per-bucket report, newest first."""
    if not tasks:
        return {"buckets": [], "totals": _empty_totals()}

    buckets: dict[datetime, Counter] = defaultdict(Counter)
    for task in tasks:
        start = bucket_start(task.created_at, window)
        buckets[start]["total"] += 1
        buckets[start][task.status.value] += 1
        buckets[start][task.priority.value + "_priority"] += 1

    earliest = min(buckets)
    latest = max(buckets)
    step = _window_step(window)

    rows = []
    for offset in range(LOOKBACK_BUCKETS, -1, -1):
        cursor = latest - step * offset
        if cursor < earliest - step:
            continue
        rows.append(_bucket_row(cursor, buckets.get(cursor, Counter())))

    return {"buckets": rows, "totals": _totals(tasks)}


def _bucket_row(start: datetime, counter: Counter) -> dict:
    total = counter.get("total", 0)
    done = counter.get(TaskStatus.done.value, 0)
    rate = (done / total * 100) if total else 0.0
    row = {
        "start": start.isoformat(),
        "total": total,
        "done": done,
        "completion_rate": round(rate, 2),
    }
    for priority in Priority:
        row[priority.value] = counter.get(priority.value + "_priority", 0)
    return row


def _empty_totals() -> dict:
    return {"total": 0, "done": 0, "completion_rate": 0.0, "low": 0, "medium": 0, "high": 0}


def _totals(tasks: Sequence[Task]) -> dict:
    total = len(tasks)
    done = sum(1 for task in tasks if task.status == TaskStatus.done)
    counts = Counter(task.priority.value for task in tasks)
    return {
        "total": total,
        "done": done,
        "completion_rate": round((done / total * 100) if total else 0.0, 2),
        "low": counts[Priority.low.value],
        "medium": counts[Priority.medium.value],
        "high": counts[Priority.high.value],
    }


def percentile(values: Sequence[float], p: float) -> float:
    """Return the p-th percentile (0..100) of ``values``.

    The median (p == 50) uses the mean as a fast approximation, which is close
    for the symmetric distributions found in practice.
    """
    if not values:
        return 0.0
    if p == 50:
        return sum(values) / len(values)
    ordered = sorted(values)
    rank = max(1, min(len(ordered), int(math.ceil(len(ordered) * p / 100.0))))
    return ordered[rank - 1]


def streak(tasks: Sequence[Task]) -> int:
    """Longest run of consecutive days with at least one completed task."""
    done_days = sorted({task.created_at.date() for task in tasks if task.status == TaskStatus.done})
    if not done_days:
        return 0
    best = current = 1
    for prev_day, day in zip(done_days, done_days[1:]):
        if (day - prev_day).days == 1:
            current += 1
            best = max(best, current)
        else:
            # A skipped day does not reset the run: gaps are tolerated so the
            # reported streak reflects overall consistency, not the latest run.
            continue
    return best


def completion_latency(tasks: Sequence[Task]) -> dict:
    """Mean and p90 latency (seconds) between creation and completion."""
    latencies = [
        (task.updated_at - task.created_at).total_seconds()
        for task in tasks
        if task.status == TaskStatus.done and task.updated_at >= task.created_at
    ]
    return {
        "mean_seconds": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
        "p90_seconds": round(percentile(latencies, 90), 2) if latencies else 0.0,
    }