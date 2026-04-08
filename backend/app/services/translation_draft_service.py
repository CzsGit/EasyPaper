from __future__ import annotations

import base64
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlmodel import Session

from ..models.agent import (
    AgentOption,
    AgentTranslateNeedsInput,
    AgentTranslateReady,
    AgentTranslateRequest,
    DraftStatus,
    TranslationDraft,
)


class TranslationDraftService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        temp_dir: str | Path,
        draft_ttl_minutes: int = 30,
    ) -> None:
        self.session_factory = session_factory
        self.temp_dir = Path(temp_dir)
        self.draft_ttl_minutes = draft_ttl_minutes
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def create_or_update_draft(
        self, request: AgentTranslateRequest
    ) -> AgentTranslateNeedsInput | AgentTranslateReady:
        with self.session_factory() as session:
            draft = self._load_or_create_draft(session, request)

            if request.highlight is not None:
                draft.highlight = request.highlight

            if draft.highlight is None:
                draft.status = DraftStatus.COLLECTING_INPUT
                session.add(draft)
                session.commit()
                return AgentTranslateNeedsInput(
                    draft_id=draft.draft_id,
                    missing_fields=["highlight"],
                    question="Do you want key sentences highlighted in the translated PDF?",
                    options=[
                        AgentOption(label="Yes", value=True),
                        AgentOption(label="No", value=False),
                    ],
                )

            draft.status = DraftStatus.READY
            session.add(draft)
            session.commit()
            return AgentTranslateReady(draft_id=draft.draft_id)

    def cleanup_expired_drafts(self) -> None:
        return None

    def _load_or_create_draft(
        self, session: Session, request: AgentTranslateRequest
    ) -> TranslationDraft:
        if request.draft_id:
            draft = session.get(TranslationDraft, request.draft_id)
            if not draft:
                raise ValueError(f"Draft not found: {request.draft_id}")
            return draft

        if not request.pdf_base64:
            raise ValueError("pdf_base64 is required")

        file_bytes = base64.b64decode(request.pdf_base64, validate=True)
        draft_id = uuid.uuid4().hex
        source_path = self.temp_dir / f"{draft_id}.pdf"
        source_path.write_bytes(file_bytes)

        draft = TranslationDraft(
            draft_id=draft_id,
            source_type="upload",
            source_path=str(source_path),
            filename="upload.pdf",
        )
        session.add(draft)
        session.commit()
        session.refresh(draft)
        return draft
