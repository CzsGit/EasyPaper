from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

from ..core.config import get_config
from ..core.db import engine
from ..models.task import Task, TaskResult, TaskStatus


class TaskManager:
    def __init__(self, ttl_minutes: int = 30) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self.config = get_config()
        # Ensure temp dir exists
        Path(self.config.storage.temp_dir).mkdir(parents=True, exist_ok=True)

    def create_task(self, filename: str, user_id: Optional[int] = None, mode: str = "translate") -> Task:
        task_id = uuid.uuid4().hex
        task = Task(task_id=task_id, filename=filename, user_id=user_id, mode=mode)
        with Session(engine) as session:
            session.add(task)
            session.commit()
            session.refresh(task)
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        with Session(engine) as session:
            return session.get(Task, task_id)

    def list_tasks(self, user_id: Optional[int] = None, limit: int = 50) -> list[Task]:
        with Session(engine) as session:
            statement = select(Task)
            if user_id:
                statement = statement.where(Task.user_id == user_id)
            statement = statement.order_by(Task.created_at.desc()).limit(limit)
            return session.exec(statement).all()

    def update_progress(self, task_id: str, status: TaskStatus, percent: int, message: str, error: Optional[str] = None) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            task.status = status
            task.percent = percent
            task.message = message
            task.error = error
            session.add(task)
            session.commit()

    def update_original_path(self, task_id: str, path: str) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            task.original_pdf_path = path
            session.add(task)
            session.commit()

    def set_result(self, task_id: str, result: TaskResult) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            
            # Save PDF to disk
            if result.pdf_bytes:
                file_path = Path(self.config.storage.temp_dir) / f"{task_id}.pdf"
                file_path.write_bytes(result.pdf_bytes)
                task.result_pdf_path = str(file_path)
            
            task.result_preview_html = result.preview_html
            task.status = TaskStatus.COMPLETED
            task.percent = 100
            task.message = "生成完成"
            
            session.add(task)
            session.commit()

    def set_error(self, task_id: str, message: str) -> None:
        with Session(engine) as session:
            task = session.get(Task, task_id)
            if not task:
                return
            task.status = TaskStatus.ERROR
            task.error = message
            task.message = message
            session.add(task)
            session.commit()

    def cleanup(self) -> None:
        cutoff = datetime.utcnow() - self._ttl
        with Session(engine) as session:
            statement = select(Task).where(Task.created_at < cutoff)
            expired_tasks = session.exec(statement).all()
            
            for task in expired_tasks:
                # Delete file if exists
                if task.result_pdf_path:
                    try:
                        Path(task.result_pdf_path).unlink(missing_ok=True)
                    except Exception:
                        pass
                session.delete(task)
            
            session.commit()
