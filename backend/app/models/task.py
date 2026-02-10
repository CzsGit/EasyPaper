from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class TaskStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    REWRITING = "rewriting"
    RENDERING = "rendering"
    COMPLETED = "completed"
    ERROR = "error"


class TaskProgress(SQLModel):
    status: TaskStatus = TaskStatus.PENDING
    percent: int = 0
    message: str = "任务已排队"
    error: str | None = None


class TaskResult(SQLModel):
    pdf_bytes: bytes | None = None
    preview_html: str | None = None
    filename: str | None = None


class Task(SQLModel, table=True):
    task_id: str = Field(primary_key=True)
    user_id: int | None = Field(default=None, index=True)
    filename: str
    mode: str = Field(default="translate")  # "translate" or "simplify"

    # Progress fields
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    percent: int = Field(default=0)
    message: str = Field(default="任务已排队")
    error: str | None = Field(default=None)

    # Result fields
    original_pdf_path: str | None = Field(default=None)
    result_pdf_path: str | None = Field(default=None)
    result_preview_html: str | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # User ownership
    user_id: int | None = Field(default=None, foreign_key="user.id")

    @property
    def progress(self) -> TaskProgress:
        return TaskProgress(status=self.status, percent=self.percent, message=self.message, error=self.error)

    @property
    def result(self) -> TaskResult:
        # Note: pdf_bytes is None here because we don't load it from disk automatically
        return TaskResult(pdf_bytes=None, preview_html=self.result_preview_html, filename=f"simplified_{self.filename}")
