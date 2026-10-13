import json
from datetime import datetime, timezone

import pytest

from app.export import build_export, to_csv, to_json, with_retry
from app.models import Priority, Task, TaskStatus


def _task(**kwargs) -> Task:
    base = {
        "id": 1,
        "owner": "alice@example.com",
        "title": "Plan the quarter",
        "description": "",
        "status": TaskStatus.todo,
        "priority": Priority.medium,
        "created_at": datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc),
    }
    base.update(kwargs)
    return Task(**base)


def test_to_csv_header_first() -> None:
    lines = list(to_csv([_task(title="Plan", description="Draft")]))
    assert lines[0] == "id,title,description,status,priority,owner,created_at,updated_at"
    assert lines[1].startswith("1,Plan,Draft,todo,medium,alice@example.com,")


def test_to_json_roundtrip() -> None:
    data = json.loads(to_json([_task(id=7, title="Export me")]))
    assert data[0]["id"] == 7
    assert data[0]["title"] == "Export me"


def test_build_export_switches_formats() -> None:
    tasks = [_task(id=1)]
    assert build_export(tasks, "json").lstrip().startswith("[")
    assert build_export(tasks, "csv").startswith("id,title")


def test_with_retry_succeeds_on_first_call() -> None:
    calls: list = []

    def fn() -> str:
        calls.append(1)
        return "ok"

    assert with_retry(fn, attempts=3, delay=0) == "ok"
    assert len(calls) == 1


def test_with_retry_recovers_after_failures() -> None:
    state = {"n": 0}

    def fn() -> str:
        state["n"] += 1
        if state["n"] < 3:
            raise RuntimeError("boom")
        return "recovered"

    # attempts=2 still allows the third invocation, so a call that stabilises
    # on the third run succeeds within the loop's budget.
    assert with_retry(fn, attempts=2, delay=0) == "recovered"
    assert state["n"] == 3


def test_with_retry_exhausted_raises() -> None:
    counts = {"n": 0}

    def fn() -> str:
        counts["n"] += 1
        raise RuntimeError("always")

    with pytest.raises(RuntimeError):
        with_retry(fn, attempts=1, delay=0)
    assert counts["n"] == 2  # one initial call plus one retry: the loop runs attempts+1 times