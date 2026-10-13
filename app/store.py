import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import Priority, Task, TaskStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class UserStore:
    """In-memory user account storage keyed by email."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._passwords: Dict[str, str] = {}

    def register(self, email: str, password_hash: str) -> bool:
        if email in self._passwords:
            return False
        self._passwords[email] = password_hash
        return True

    def password_hash(self, email: str) -> Optional[str]:
        return self._passwords.get(email)


class TaskStore:
    """In-memory task storage, scoped by owner."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[int, Task] = {}
        self._sequence = 1

    def create(
        self,
        owner: str,
        title: str,
        description: str = "",
        status: TaskStatus = TaskStatus.todo,
        priority: Priority = Priority.medium,
    ) -> Task:
        task = Task(
            id=self._sequence,
            owner=owner,
            title=title,
            description=description,
            status=status,
            priority=priority,
            created_at=_now(),
            updated_at=_now(),
        )
        self._tasks[task.id] = task
        self._sequence += 1
        return task

    def get(self, task_id: int, owner: str) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None or task.owner != owner:
            return None
        return task

    def list(self, owner: str, status: Optional[TaskStatus] = None) -> List[Task]:
        with self._lock:
            tasks = [task for task in self._tasks.values() if task.owner == owner]
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        return sorted(tasks, key=lambda task: task.id)

    def update(self, task_id: int, owner: str, changes: Dict[str, object]) -> Optional[Task]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.owner != owner:
                return None
            updated = task.model_copy(update={**changes, "updated_at": _now()})
            self._tasks[task_id] = updated
            return updated

    def delete(self, task_id: int, owner: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.owner != owner:
                return False
            del self._tasks[task_id]
            return True
