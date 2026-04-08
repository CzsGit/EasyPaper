from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class DraftStatus(StrEnum):
    COLLECTING_INPUT = "collecting_input"
    READY = "ready"
    SUBMITTED = "submitted"
    EXPIRED = "expired"


class TranslationDraft(SQLModel, table=True):
    draft_id: str = Field(primary_key=True)
    source_type: str
    source_path: str | None = Field(default=None)
    source_url: str | None = Field(default=None)
    filename: str
    target_lang: str = Field(default="zh")
    highlight: bool | None = Field(default=None)
    status: DraftStatus = Field(default=DraftStatus.COLLECTING_INPUT)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentOption(SQLModel, table=False):
    label: str
    value: bool


class AgentTranslateRequest(SQLModel, table=False):
    draft_id: str | None = None
    pdf_url: str | None = None
    pdf_base64: str | None = None
    highlight: bool | None = None


class AgentTranslateNeedsInput(SQLModel, table=False):
    status: str = "needs_input"
    draft_id: str
    missing_fields: list[str]
    question: str
    options: list[AgentOption]


class AgentTranslateReady(SQLModel, table=False):
    status: str = "ready"
    draft_id: str


class AgentTranslateAccepted(SQLModel, table=False):
    status: str = "accepted"
    draft_id: str
    task_id: str
    status_url: str


class AgentTranslateToolResult(SQLModel, table=False):
    status: str
    draft_id: str
    missing_fields: list[str] = []
    question: str | None = None
    options: list[AgentOption] = []
    task_id: str | None = None
    status_url: str | None = None


class AgentArtifactMetadata(SQLModel, table=False):
    task_id: str
    filename: str
    content_type: str = "application/pdf"


class AgentArtifactPayload(AgentArtifactMetadata, table=False):
    download_path: str | None = None
    pdf_base64: str | None = None


class AgentTaskStatus(SQLModel, table=False):
    task_id: str
    status: str
    percent: int
    message: str
    error: str | None = None
    artifact_ready: bool = False
