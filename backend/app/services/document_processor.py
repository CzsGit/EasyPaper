"""
文档处理器 - 使用 PDFMathTranslate (pdf2zh) 进行学术论文翻译/简化
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path
from string import Template

from ..core.config import AppConfig
from ..models.task import TaskResult, TaskStatus
from .task_manager import TaskManager

logger = logging.getLogger(__name__)

SIMPLIFY_PROMPT = Template(
    "You are an expert at simplifying academic English. "
    "Rewrite the following text using simple, everyday vocabulary "
    "(CEFR A2/B1 level, approximately 2000 common English words). "
    "Keep the same meaning. Keep all formula notations {v*} unchanged. "
    "Output only the rewritten text, nothing else.\n\n"
    "Source Text: $text\n\n"
    "Simplified Text:"
)


class DocumentProcessor:
    def __init__(self, config: AppConfig, task_manager: TaskManager) -> None:
        self.config = config
        self.task_manager = task_manager

    async def process(self, task_id: str, file_bytes: bytes, filename: str, mode: str = "translate") -> None:
        """使用 pdf2zh 处理 PDF 文档"""

        if mode == "simplify":
            self.task_manager.update_progress(task_id, TaskStatus.PARSING, 10, "正在准备简化...")
        else:
            self.task_manager.update_progress(task_id, TaskStatus.PARSING, 10, "正在准备翻译...")

        # 设置 pdf2zh 环境变量
        os.environ["OPENAILIKED_BASE_URL"] = self.config.llm.base_url
        os.environ["OPENAILIKED_API_KEY"] = self.config.llm.api_key
        os.environ["OPENAILIKED_MODEL"] = self.config.llm.model

        try:
            # 在线程中运行 pdf2zh（同步库）
            result = await asyncio.to_thread(
                self._translate_with_pdf2zh,
                file_bytes,
                filename,
                task_id,
                mode,
            )

            if result is None:
                self.task_manager.set_error(task_id, "处理失败，请重试")
                return

            pdf_bytes, output_filename = result

            # 生成简单的预览 HTML
            preview_html = self._build_simple_preview(mode)

            task_result = TaskResult(
                pdf_bytes=pdf_bytes,
                preview_html=preview_html,
                filename=output_filename,
            )

            self.task_manager.set_result(task_id, task_result)
            logger.info(f"Task {task_id} 处理完成 (mode={mode})")

        except Exception as exc:
            logger.exception("处理失败: %s", exc)
            self.task_manager.set_error(task_id, f"处理失败: {exc}")

    def _translate_with_pdf2zh(
        self,
        file_bytes: bytes,
        filename: str,
        task_id: str,
        mode: str = "translate",
    ) -> tuple[bytes, str] | None:
        """调用 pdf2zh 进行翻译或简化"""

        try:
            from pdf2zh import translate
            from pdf2zh.doclayout import DocLayoutModel
        except ImportError:
            logger.error("pdf2zh 未安装，请运行: pip install pdf2zh")
            return None

        # 加载 DocLayout-YOLO 模型
        model = DocLayoutModel.load_available()

        # 根据模式设置目标语言
        lang_out = "zh" if mode == "translate" else "en"

        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 保存输入文件
            input_path = Path(temp_dir) / filename
            input_path.write_bytes(file_bytes)

            logger.info(f"开始处理: {input_path} (mode={mode}, lang_out={lang_out})")

            # 更新进度
            if mode == "simplify":
                self.task_manager.update_progress(task_id, TaskStatus.REWRITING, 30, "正在使用 AI 简化...")
            else:
                self.task_manager.update_progress(task_id, TaskStatus.REWRITING, 30, "正在使用 AI 翻译...")

            try:
                # 调用 pdf2zh
                results = translate(
                    files=[str(input_path)],
                    lang_in="en",
                    lang_out=lang_out,
                    service="openailiked",
                    thread=4,
                    output=temp_dir,
                    model=model,
                    prompt=SIMPLIFY_PROMPT if mode == "simplify" else None,
                    ignore_cache=mode == "simplify",
                )

                if not results or len(results) == 0:
                    logger.error("pdf2zh 返回空结果")
                    return None

                file_mono, file_dual = results[0]

                # 更新进度
                self.task_manager.update_progress(task_id, TaskStatus.RENDERING, 80, "正在生成 PDF...")

                # 优先使用双语版本，如果没有则使用单语版本
                output_file = file_dual if file_dual else file_mono

                if output_file and Path(output_file).exists():
                    pdf_bytes = Path(output_file).read_bytes()
                    prefix = "translated" if mode == "translate" else "simplified"
                    output_filename = f"{prefix}_{Path(filename).stem}.pdf"
                    logger.info(f"处理完成: {output_file}")
                    return pdf_bytes, output_filename

                logger.error("输出文件不存在")
                return None

            except Exception as e:
                logger.exception(f"pdf2zh 处理失败: {e}")
                return None

    def _build_simple_preview(self, mode: str = "translate") -> str:
        """生成简单的预览 HTML"""
        if mode == "simplify":
            return """
        <div style="padding: 20px; text-align: center; color: #666;">
            <p>PDF 简化完成，请下载查看。</p>
            <p style="font-size: 12px;">使用 PDFMathTranslate 技术，保留公式和布局。</p>
        </div>
        """
        return """
        <div style="padding: 20px; text-align: center; color: #666;">
            <p>PDF 翻译完成，请下载查看。</p>
            <p style="font-size: 12px;">使用 PDFMathTranslate 技术，保留公式和布局。</p>
        </div>
        """
