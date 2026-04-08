from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

from ..models.agent import AgentArtifactMetadata, AgentTaskStatus


class TranslationArtifactService:
    def __init__(self, task_manager) -> None:
        self.task_manager = task_manager

    def get_metadata(self, task_id: str) -> AgentArtifactMetadata:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        filename = Path(task.result_pdf_path).name if task.result_pdf_path else f"translated_{task.filename}"
        return AgentArtifactMetadata(task_id=task_id, filename=filename)

    def get_task_status(self, task_id: str) -> AgentTaskStatus:
        task = self.task_manager.get_task(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        artifact_ready = bool(task.result_pdf_path and Path(task.result_pdf_path).exists())
        return AgentTaskStatus(
            task_id=task_id,
            status=str(task.status),
            percent=task.percent,
            message=task.message,
            error=task.error,
            artifact_ready=artifact_ready,
        )

    def build_file_response(self, task_id: str) -> FileResponse:
        task = self.task_manager.get_task(task_id)
        if not task or not task.result_pdf_path:
            raise ValueError(f"Artifact not found for task: {task_id}")

        result_path = Path(task.result_pdf_path)
        if not result_path.exists():
            raise FileNotFoundError(result_path)

        return FileResponse(
            result_path,
            media_type="application/pdf",
            filename=result_path.name,
        )
