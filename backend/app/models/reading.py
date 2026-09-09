"""Persistent source anchors and per-reader state, separate from PDF export jobs."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class ReadingDocument(SQLModel, table=True):
    task_id: str = Field(primary_key=True)
    document_json: str
    schema_version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingAid(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    block_id: str = Field(index=True)
    content_json: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReadingState(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str = Field(index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    block_id: str = ""
    offset: float = 0
    mode: str = "chinese"
    font_size: int = 18
    understood_json: str = "[]"
    bookmarked_terms_json: str = "[]"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
