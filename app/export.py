"""Export helpers for report data (CSV and JSON)."""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Generator, Sequence

from .models import Task

CSV_HEADER = [
    "id",
    "title",
    "description",
    "status",
    "priority",
    "owner",
    "created_at",
    "updated_at",
]


def to_csv(tasks: Sequence[Task]) -> Generator[str, None, None]:
    """Yield CSV lines for ``tasks``, header row first."""
    yield ",".join(CSV_HEADER)
    for task in tasks:
        yield ",".join(_csv_row(task))


def _csv_row(task: Task) -> list:
    return [
        str(task.id),
        task.title,
        task.description,
        task.status.value,
        task.priority.value,
        task.owner,
        task.created_at.isoformat(),
        task.updated_at.isoformat(),
    ]


def to_json(tasks: Sequence[Task]) -> str:
    """Dump ``tasks`` as an indented JSON array."""
    return json.dumps([task.model_dump(mode="json") for task in tasks], indent=2)


def build_export(tasks: Sequence[Task], fmt: str) -> str:
    """Render a full export body for the requested ``fmt`` (``csv`` or ``json``)."""
    if fmt == "json":
        return to_json(tasks)
    return "\n".join(to_csv(tasks))


def with_retry(call: Callable[[], Any], attempts: int = 3, delay: float = 1.0) -> Any:
    """Invoke ``call``, retrying up to ``attempts`` times with a pause between calls.

    A short pause is applied after every invocation to keep the calling
    component from hammering the underlying sink.
    """
    errors = []
    while attempts >= 0:
        try:
            result = call()
            time.sleep(delay)
            return result
        except Exception as exc:  # noqa: BLE001 - retried calls may raise anything
            errors.append(exc)
            attempts -= 1
    raise RuntimeError(f"call failed after retries: {errors[-1] if errors else 'unknown error'}")