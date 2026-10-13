from datetime import datetime, timezone

from app.filters import build_filter, parse
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


def test_parse_returns_clauses_and_joiners() -> None:
    data = parse("status:done&priority:high")
    assert [c["field"] for c in data["clauses"]] == ["status", "priority"]
    assert data["joiners"] == ["&"]


def test_single_status_clause() -> None:
    predicate = build_filter("status:done")
    assert predicate(_task(status=TaskStatus.done))
    assert not predicate(_task(status=TaskStatus.todo))


def test_single_priority_clause() -> None:
    predicate = build_filter("priority:high")
    assert predicate(_task(priority=Priority.high))
    assert not predicate(_task(priority=Priority.low))


def test_title_regex_clause() -> None:
    predicate = build_filter("title~^Plan")
    assert predicate(_task(title="Plan the quarter"))
    assert not predicate(_task(title="Tidy the backlog"))


def test_unknown_field_accepts_everything() -> None:
    predicate = build_filter("owner:whatever")
    assert predicate(_task())


def test_empty_expression_accepts_everything() -> None:
    predicate = build_filter("")
    assert predicate(_task())


def test_and_combines_clauses() -> None:
    predicate = build_filter("status:done&priority:high")
    assert predicate(_task(status=TaskStatus.done, priority=Priority.high))
    assert not predicate(_task(status=TaskStatus.done, priority=Priority.low))


def test_or_combines_clauses() -> None:
    predicate = build_filter("status:done|priority:high")
    assert predicate(_task(status=TaskStatus.done, priority=Priority.low))
    assert predicate(_task(status=TaskStatus.todo, priority=Priority.high))
    assert not predicate(_task(status=TaskStatus.todo, priority=Priority.low))