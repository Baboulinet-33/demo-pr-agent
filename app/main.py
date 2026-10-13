from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import task_service
from .models import (
    LoginRequest,
    RegisterRequest,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    TokenResponse,
)
from .security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from .store import TaskStore, UserStore

app = FastAPI(title="TaskFlow API", version="0.1.0")

users = UserStore()
tasks = TaskStore()

bearer_scheme = HTTPBearer(auto_error=False)


def current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return subject


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest) -> dict:
    if not users.register(payload.email, hash_password(payload.password)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return {"email": payload.email}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    stored = users.password_hash(payload.email)
    if stored is None or not verify_password(payload.password, stored):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_access_token(payload.email))


@app.get("/tasks", response_model=List[Task])
def list_tasks(
    user: str = Depends(current_user),
    task_status: Optional[TaskStatus] = Query(default=None, alias="status"),
) -> List[Task]:
    return tasks.list(user, status=task_status)


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, user: str = Depends(current_user)) -> Task:
    return task_service.run(tasks, "create", user, body=payload)


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int, user: str = Depends(current_user)) -> Task:
    return task_service.run(tasks, "get", user, task_id=task_id)


@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate, user: str = Depends(current_user)) -> Task:
    return task_service.run(tasks, "update", user, task_id=task_id, body=payload)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: str = Depends(current_user)) -> None:
    task_service.run(tasks, "delete", user, task_id=task_id)