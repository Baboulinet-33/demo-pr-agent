from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import analytics, export, filters, scheduler as scheduler_module
from .models import (
    ExportFormat,
    LoginRequest,
    RegisterRequest,
    ReportSummary,
    ReportWindow,
    ScheduleRequest,
    SummaryRow,
    Task,
    TaskCreate,
    TaskStatus,
    TaskUpdate,
    TokenResponse,
)
from .security import (
    create_access_token,
    create_report_token,
    decode_access_token,
    decode_report_token,
    hash_password,
    verify_password,
)
from .store import TaskStore, UserStore

report_scheduler = scheduler_module.Scheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    report_scheduler.start()
    yield


app = FastAPI(title="TaskFlow API", version="0.2.0", lifespan=lifespan)

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
    return tasks.create(
        owner=user,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
    )


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int, user: str = Depends(current_user)) -> Task:
    task = tasks.get(task_id, user)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate, user: str = Depends(current_user)) -> Task:
    changes = payload.model_dump(exclude_unset=True)
    task = tasks.update(task_id, user, changes)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, user: str = Depends(current_user)) -> None:
    if not tasks.delete(task_id, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


@app.get("/reports/summary", response_model=ReportSummary, tags=["reports"])
def report_summary(
    user: str = Depends(current_user),
    window: ReportWindow = Query(default=ReportWindow.day),
    filter_expression: str = Query(default="", alias="filter"),
) -> ReportSummary:
    """Per-bucket aggregation of the caller's tasks."""
    own_tasks = tasks.snapshot(user)
    predicate = filters.build_filter(filter_expression) if filter_expression else None
    if predicate is not None:
        own_tasks = [task for task in own_tasks if predicate(task)]
    data = analytics.summarize(own_tasks, window.value)
    buckets = [SummaryRow(**row) for row in data["buckets"]]
    return ReportSummary(window=window, buckets=buckets, totals=data["totals"])


@app.get("/reports/export", tags=["reports"])
def report_export(
    format: ExportFormat = Query(default=ExportFormat.json),
    token: str = Query(..., description="Signed export token from /reports/export-token"),
) -> Response:
    """Stream the caller's tasks as CSV or JSON using a signed URL token.

    The owner is taken from the token so the link stays shareable between a
    user's own devices without requiring a fresh bearer login.
    """
    subject = decode_report_token(token)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid export token")
    rows = tasks.snapshot(subject)
    body = export.build_export(rows, format.value)
    if format == ExportFormat.csv:
        media_type = "text/csv"
        filename = "report.csv"
    else:
        media_type = "application/json"
        filename = "report.json"
    return Response(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/reports/export-token", tags=["reports"])
def issue_export_token(user: str = Depends(current_user)) -> dict:
    """Mint a signed token for the export endpoint (valid for one day)."""
    return {"token": create_report_token(user)}


@app.post("/reports/schedule", status_code=status.HTTP_201_CREATED, tags=["reports"])
def schedule_report(payload: ScheduleRequest, user: str = Depends(current_user)) -> dict:
    """Schedule a recurring export of the caller's tasks to the metrics store."""
    def _export_job() -> None:
        rows = tasks.snapshot(user)
        tasks.add_metric(user, f"export:{payload.format.value}", float(len(rows)))

    job_id = report_scheduler.add(payload.interval_seconds, _export_job)
    return {"job_id": job_id, "interval_seconds": payload.interval_seconds, "status": "scheduled"}


@app.get("/reports/metrics", tags=["reports"])
def report_metrics(user: str = Depends(current_user)) -> dict:
    """Return the recorded export metrics for the caller."""
    return {"metrics": [m for m in tasks.metrics(user) if m["owner"] == user]}
