from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..core.config import get_config
from ..models.task import TaskStatus
from ..models.user import User
from ..services.document_processor import DocumentProcessor
from ..services.task_manager import TaskManager
from .deps import get_current_user


def create_router(task_manager: TaskManager, processor: DocumentProcessor) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["documents"])
    cfg = get_config()
    _max_bytes = cfg.processing.max_upload_mb * 1024 * 1024
    _semaphore = asyncio.Semaphore(cfg.processing.max_concurrent)
    limiter = Limiter(key_func=get_remote_address)

    @router.post("/upload")
    @limiter.limit("10/minute")
    async def upload_pdf(
        request: Request,
        file: UploadFile = File(...),
        mode: str = Form("translate"),
        user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        if mode not in ("translate", "simplify"):
            raise HTTPException(status_code=400, detail="mode must be 'translate' or 'simplify'")
        if file.content_type not in {"application/pdf", "application/octet-stream"}:
            raise HTTPException(status_code=400, detail="仅支持PDF文件")
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="文件内容为空")
        if len(file_bytes) > _max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"文件大小超过限制（最大 {cfg.processing.max_upload_mb}MB）",
            )

        task = task_manager.create_task(file.filename or "document.pdf", user_id=user.id, mode=mode)

        # Save original file
        original_path = Path(task_manager.config.storage.temp_dir) / f"{task.task_id}_original.pdf"
        with open(original_path, "wb") as f:
            f.write(file_bytes)

        # Update task with original path
        task_manager.update_original_path(task.task_id, str(original_path))

        async def _process_with_limit() -> None:
            async with _semaphore:
                await processor.process(task.task_id, file_bytes, task.filename, mode=mode)

        asyncio.create_task(_process_with_limit())

        return {"task_id": task.task_id}

    @router.get("/tasks")
    async def list_tasks(user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
        tasks = task_manager.list_tasks(user_id=user.id)
        return [
            {
                "task_id": t.task_id,
                "filename": t.filename,
                "status": t.status,
                "created_at": t.created_at,
                "percent": t.percent,
                "message": t.message,
                "mode": t.mode,
            }
            for t in tasks
        ]

    @router.get("/status/{task_id}")
    async def get_status(task_id: str) -> dict[str, Any]:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        progress = task.progress
        return {
            "status": progress.status,
            "percent": progress.percent,
            "message": progress.message,
            "error": progress.error,
        }

    @router.get("/result/{task_id}/preview", response_class=HTMLResponse)
    async def get_preview(task_id: str, user: User = Depends(get_current_user)) -> str:
        task = task_manager.get_task(task_id)
        if not task or task.status != TaskStatus.COMPLETED:
            raise HTTPException(status_code=404, detail="结果尚未生成")
        if task.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        if not task.result_preview_html:
            raise HTTPException(status_code=404, detail="暂无预览")
        return task.result_preview_html

    @router.get("/result/{task_id}/pdf")
    async def download_pdf(task_id: str, user: User = Depends(get_current_user)):
        task = task_manager.get_task(task_id)
        if not task or task.status != TaskStatus.COMPLETED:
            raise HTTPException(status_code=404, detail="结果尚未生成")
        if task.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")

        if not task.result_pdf_path or not Path(task.result_pdf_path).exists():
            raise HTTPException(status_code=404, detail="暂无PDF内容或文件已过期")

        return FileResponse(task.result_pdf_path, media_type="application/pdf", filename=f"simplified_{task.filename}")

    @router.delete("/tasks/{task_id}")
    async def delete_task(task_id: str, user: User = Depends(get_current_user)) -> dict[str, str]:
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")
        task_manager.delete_task(task_id)
        return {"status": "deleted"}

    @router.get("/original/{task_id}/pdf")
    async def get_original_pdf(task_id: str, user: User = Depends(get_current_user)):
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        if task.user_id != user.id:
            raise HTTPException(status_code=403, detail="无权访问此任务")

        if not task.original_pdf_path or not Path(task.original_pdf_path).exists():
            raise HTTPException(status_code=404, detail="原始文件不存在或已过期")

        return FileResponse(task.original_pdf_path, media_type="application/pdf", filename=f"original_{task.filename}")

    return router
