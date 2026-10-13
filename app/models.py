from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class TaskStatus(str, Enum):
    todo = "todo"
    doing = "doing"
    done = "done"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: TaskStatus = TaskStatus.todo
    priority: Priority = Priority.medium


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None


class Task(BaseModel):
    id: int
    owner: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.todo
    priority: Priority = Priority.medium
    created_at: datetime
    updated_at: datetime


class ReportWindow(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class ExportFormat(str, Enum):
    csv = "csv"
    json = "json"


class ScheduleRequest(BaseModel):
    interval_seconds: int = Field(ge=10, le=86400)
    format: ExportFormat = ExportFormat.json
    filename: str = Field(default="export", min_length=1, max_length=64)


class SummaryRow(BaseModel):
    start: str
    total: int
    done: int
    completion_rate: float
    low: int = 0
    medium: int = 0
    high: int = 0


class ReportSummary(BaseModel):
    window: ReportWindow
    buckets: List[SummaryRow] = Field(default_factory=list)
    totals: dict = Field(default_factory=dict)
