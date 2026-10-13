from datetime import datetime, timezone

from app.analytics import (
    bucket_start,
    completion_latency,
    percentile,
    streak,
    summarize,
)
from app.models import Priority, Task, TaskStatus

DAY = datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)


def _day(day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, minute, 0, tzinfo=timezone.utc)


def _task(**kwargs) -> Task:
    base = {
        "id": 1,
        "owner": "alice@example.com",
        "title": "A task",
        "description": "",
        "status": TaskStatus.todo,
        "priority": Priority.medium,
        "created_at": _day(1),
        "updated_at": _day(1),
    }
    base.update(kwargs)
    return Task(**base)


def test_bucket_start_day_midday() -> None:
    ts = _day(3, hour=14, minute=30)
    assert bucket_start(ts, "day") == datetime(2026, 5, 3, 0, 0, 0, tzinfo=timezone.utc)


def test_bucket_start_week_is_midnight_of_a_day() -> None:
    start = bucket_start(_day(12, hour=9), "week")
    assert start <= _day(12, hour=9)
    assert start.hour == 0 and start.minute == 0 and start.second == 0


def test_bucket_start_month_first_of_month() -> None:
    assert bucket_start(_day(15, hour=8), "month") == datetime(2026, 5, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_summarize_empty() -> None:
    out = summarize([])
    assert out["buckets"] == []
    assert out["totals"]["total"] == 0


def test_summarize_day_buckets() -> None:
    tasks = [
        _task(id=1, status=TaskStatus.done, created_at=_day(1, 9)),
        _task(id=2, status=TaskStatus.todo, created_at=_day(1, 15), priority=Priority.high),
    ]
    out = summarize(tasks, "day")
    assert out["totals"]["total"] == 2
    assert out["totals"]["done"] == 1
    assert out["totals"]["high"] == 1
    full = [row for row in out["buckets"] if row["total"] > 0]
    assert len(full) == 1
    assert full[0]["done"] == 1
    assert full[0]["completion_rate"] == 50.0


def test_percentile_high_tail() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 100.0]
    assert percentile(values, 90) == 100.0
    assert percentile(values, 100) == 100.0


def test_percentile_empty() -> None:
    assert percentile([], 95) == 0.0


def test_streak_empty() -> None:
    assert streak([]) == 0


def test_streak_single_day() -> None:
    assert streak([_task(id=1, status=TaskStatus.done, created_at=_day(5))]) == 1


def test_streak_contiguous_days() -> None:
    tasks = [
        _task(id=i, status=TaskStatus.done, created_at=_day(i))
        for i in (4, 5, 6, 7)
    ]
    assert streak(tasks) == 4


def test_completion_latency_mean_and_p90() -> None:
    tasks = [
        _task(
            id=1,
            status=TaskStatus.done,
            created_at=datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
    ]
    out = completion_latency(tasks)
    assert out["mean_seconds"] == 7200.0
    assert out["p90_seconds"] == 7200.0