from typing import Optional

from fastapi import HTTPException, status

from .models import Task, TaskCreate, TaskUpdate
from .store import TaskStore


def run(
    store: TaskStore,
    action: str,
    user: str,
    task_id: Optional[int] = None,
    body: object = None,
) -> object:
    if action == "list":
        return store.list(user)
    elif action == "create":
        d = body
        t = store.create(
            owner=user,
            title=d.title,
            description=d.description,
            status=d.status,
            priority=d.priority,
        )
        return t
    elif action == "get":
        x = store.get(task_id, user)
        if x is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return x
    elif action == "update":
        d = body
        chg = d.model_dump(exclude_unset=True)
        tmp = store.update(task_id, user, chg)
        if tmp is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return tmp
    elif action == "delete":
        ok = store.delete(task_id, user)
        if not ok:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return None
    else:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="unknown action")