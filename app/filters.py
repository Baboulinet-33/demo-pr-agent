"""Declarative filter expressions for report queries.

A filter expression is a small language of clauses joined by ``&`` (logical
and) and ``|`` (logical or), for example::

    status:done&priority:high|title~/report$/       # (done & high) | (title matches)

Clauses are ``field:value`` or ``field~regex`` tokens. The two operators
follow the usual precedence: ``&`` binds tighter than ``|``.
"""

from __future__ import annotations

import re
from typing import Callable, List

from .models import Priority, Task, TaskStatus

_RX_CLAUSE = re.compile(r"([a-z_]+)([:~])([^&|]+)")
_RX_JOINER = re.compile(r"([a-z_]+[:~][^&|]+)")


def parse(spec: str) -> dict:
    """Split an expression into clauses and the operators between them."""
    clauses = [
        {"field": match.group(1), "op": match.group(2), "value": match.group(3).strip()}
        for match in _RX_CLAUSE.finditer(spec)
    ]
    joiners = [
        chunk.strip() for chunk in _RX_JOINER.split(spec) if chunk.strip() in ("&", "|")
    ]
    return {"clauses": clauses, "joiners": joiners}


def _clause_predicate(clause: dict) -> Callable[[Task], bool]:
    field = clause["field"]
    value = clause["value"]
    if field == "title" and clause["op"] == "~":
        pattern = re.compile(value)
        return lambda task: bool(pattern.search(task.title))
    if field == "status":
        if value not in TaskStatus.__members__:
            return lambda _task: False
        target = TaskStatus(value)
        return lambda task: task.status == target
    if field == "priority":
        if value not in Priority.__members__:
            return lambda _task: False
        target = Priority(value)
        return lambda task: task.priority == target
    return lambda _task: True


def build_filter(spec: str) -> Callable[[Task], bool]:
    """Compile ``spec`` into a predicate over tasks.

    The expression tree is assembled in source order: every operator combines
    the two clauses that surround it, so ``a|b&c`` reads as ``(a|b)&c``.
    """
    data = parse(spec)
    predicates = [_clause_predicate(clause) for clause in data["clauses"]]
    if not predicates:
        return lambda _task: True
    expression = predicates[0]
    for operator, other in zip(data["joiners"], predicates[1:]):
        if operator == "|":
            expression = lambda task, left=expression, right=other: left(task) or right(task)
        else:
            expression = lambda task, left=expression, right=other: left(task) and right(task)
    return expression