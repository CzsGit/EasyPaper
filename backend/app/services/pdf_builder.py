from __future__ import annotations

import io

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


class PDFBuilder:
    """
    基于原位替换 (In-Place Replacement) 的 PDF 生成器。
    1. 严格按照原始 bbox 绘制图片和文本。
    2. 使用统一的小号字体 (Uniform Small Font) 以适应文本框。
    """

    def __init__(
        self,
        font_name: str = "PingFang",
        base_font_size: int = 9,
    ) -> None:
        self.font_name = font_name
        self.base_font_size = base_font_size
        self.has_chinese_font = False
        self.chinese_font = "Helvetica"
        self.chinese_font_bold = "Helvetica-Bold"
        self.chinese_font_italic = "Helvetica-Oblique"

        # 注册中文字体 (按优先级尝试: macOS苹方 → macOS华文黑体 → Linux Noto CJK)
        _font_candidates = [
            (
                "PingFang",
                "/System/Library/Fonts/PingFang.ttc",
                0,
                "PingFang-Bold",
                "/System/Library/Fonts/PingFang.ttc",
                1,
            ),
            ("STHeiti", "/System/Library/Fonts/STHeiti Light.ttc", 0, None, None, None),
            (
                "NotoSansCJK",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                0,
                "NotoSansCJK-Bold",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                0,
            ),
        ]
        for name, path, idx, bold_name, bold_path, bold_idx in _font_candidates:
            try:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=idx))
                self.has_chinese_font = True
                self.chinese_font = name
                if bold_name and bold_path:
                    try:
                        pdfmetrics.registerFont(TTFont(bold_name, bold_path, subfontIndex=bold_idx))
                        self.chinese_font_bold = bold_name
                    except Exception:
                        self.chinese_font_bold = name
                else:
                    self.chinese_font_bold = name
                self.chinese_font_italic = name
                break
            except Exception:
                continue

    def build(self, doc_layout: dict) -> bytes:
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer)

        pages = doc_layout.get("pages", [])
        print(f"DEBUG: Builder received {len(pages)} pages")

        for page in pages:
            self._render_page(pdf, page)
            pdf.showPage()

        pdf.save()
        return buffer.getvalue()

    def _render_page(self, pdf: canvas.Canvas, page: dict) -> None:
        width = page.get("width")
        height = page.get("height")
        pdf.setPageSize((width, height))

        # 1. 绘制全页背景 (Background Preservation)
        bg_image = next((img for img in page.get("images", []) if img.get("type") == "background"), None)
        if bg_image:
            try:
                img_data = bg_image["data"]
                img_reader = ImageReader(io.BytesIO(img_data))
                pdf.drawImage(img_reader, 0, 0, width=width, height=height)
            except Exception as e:
                print(f"Error drawing background: {e}")

        # 1.1 添加页面书签
        page_index = page.get("page_index", 0)
        pdf.bookmarkPage(f"page_{page_index}")

        # 获取保护区域
        protected_zones = page.get("protected_zones", [])

        # 2. 绘制文本块 (Text Overwrite)
        for block in page.get("text_blocks", []):
            self._render_text_block(pdf, block, height, protected_zones)

        # 3. 恢复链接 (Link Preservation)
        self._render_links(pdf, page)

    def _render_links(self, pdf: canvas.Canvas, page: dict) -> None:
        """恢复页面中的超链接"""
        height = page.get("height")
        for link in page.get("links", []):
            if link.get("text"):
                continue

            rect = link.get("from")
            kind = link.get("kind")

            # Flip Y coordinate
            # rect is [x0, y0, x1, y1] (Top-Left origin)
            # ReportLab needs [x0, y0, x1, y1] (Bottom-Left origin)
            # rl_y0 = height - rect[3]
            # rl_y1 = height - rect[1]
            # But pdf.linkURL expects rect as [x0, y0, x1, y1] in its coord system.

            rl_rect = [rect[0], height - rect[3], rect[2], height - rect[1]]

            if kind == 2:  # URI
                uri = link.get("uri")
                if uri:
                    pdf.linkURL(uri, rl_rect, relative=0)
            elif kind == 1 or kind == 4:  # GoTo / Named (Internal)
                target_page = link.get("page")
                if target_page is not None:
                    pdf.linkRect("", f"page_{target_page}", rl_rect, relative=0)

    def _render_text_block(
        self, pdf: canvas.Canvas, block: dict, page_height: float, protected_zones: list = None
    ) -> None:
        # Skip rotated blocks (PRESERVE strategy)
        if block.get("rotation", 0) != 0:
            return

        text = block.get("rewritten_text") or block.get("text", "")
        if not text:
            return

        bbox = block.get("bbox")
        x0, top_y, x1, bottom_y = bbox

        # Convert PDFMiner bbox (top-left origin) to ReportLab bbox (bottom-left origin)
        rl_x = x0
        rl_y_bottom = page_height - bottom_y
        rl_width = x1 - x0
        rl_height = bottom_y - top_y

        # 计算白色遮罩区域，避开保护区域（图片、表格）
        mask_bbox = [x0 - 1, top_y - 1, x1 + 1, bottom_y + 1]
        if protected_zones:
            mask_bbox = self._clip_mask_around_protected(mask_bbox, protected_zones)

        # 如果遮罩区域被完全裁剪掉，跳过绘制
        if mask_bbox is None:
            return

        # Draw White Mask to cover original text
        pdf.saveState()
        pdf.setFillColorRGB(1, 1, 1)  # White
        pdf.setStrokeColorRGB(1, 1, 1)
        mask_x0, mask_y0, mask_x1, mask_y1 = mask_bbox
        mask_rl_y = page_height - mask_y1
        mask_rl_w = mask_x1 - mask_x0
        mask_rl_h = mask_y1 - mask_y0
        pdf.rect(mask_x0, mask_rl_y, mask_rl_w, mask_rl_h, fill=1, stroke=1)
        pdf.restoreState()

        # 文本绘制使用原始的文本框大小（不是裁剪后的遮罩大小）
        # 这样字体只在真正放不下时才缩小
        text_x = rl_x
        text_y_bottom = rl_y_bottom
        text_width = rl_width
        text_height = rl_height

        # Determine style based on LLM semantic tags
        block_style = block.get("style", "body")

        if text.startswith("<h1>") and text.endswith("</h1>"):
            block_style = "h1"
            text = text[4:-5]
        elif text.startswith("<h2>") and text.endswith("</h2>"):
            block_style = "h2"
            text = text[4:-5]
        elif text.startswith("<h3>") and text.endswith("</h3>"):
            block_style = "h3"
            text = text[4:-5]
        elif text.startswith("<caption>") and text.endswith("</caption>"):
            block_style = "caption"
            text = text[9:-10]

        # 字体样式配置 (使用中文字体)
        STYLE_CONFIG = {
            "h1": (self.chinese_font_bold, 14, 1.3),
            "h2": (self.chinese_font_bold, 12, 1.3),
            "h3": (self.chinese_font_bold, 10, 1.3),
            "caption": (self.chinese_font_italic, 8, 1.3),
            "body": (self.chinese_font, 9, 1.3),
        }

        font_name, font_size, leading_mult = STYLE_CONFIG.get(block_style, STYLE_CONFIG["body"])

        self._fit_text_to_box(
            pdf, text, text_x, text_y_bottom, text_width, text_height, font_name, font_size, leading_mult
        )

    def _clip_mask_around_protected(self, mask_bbox: list, protected_zones: list) -> list | None:
        """
        裁剪白色遮罩区域，避免覆盖保护区域（图片、表格）。
        如果遮罩与保护区域严重重叠，返回 None 表示跳过。
        """
        x0, y0, x1, y1 = mask_bbox
        mask_area = (x1 - x0) * (y1 - y0)
        if mask_area <= 0:
            return None

        for zone in protected_zones:
            zx0, zy0, zx1, zy1 = zone
            # 计算重叠区域
            ix0 = max(x0, zx0)
            iy0 = max(y0, zy0)
            ix1 = min(x1, zx1)
            iy1 = min(y1, zy1)

            if ix0 < ix1 and iy0 < iy1:
                # 有重叠
                overlap_area = (ix1 - ix0) * (iy1 - iy0)
                overlap_ratio = overlap_area / mask_area

                # 如果重叠超过 30%，跳过这个文本块的遮罩
                if overlap_ratio > 0.3:
                    return None

                # 尝试裁剪遮罩：如果保护区域在遮罩下方，缩短遮罩高度
                if zy0 > y0 and zy0 < y1:
                    y1 = zy0  # 裁剪底部
                # 如果保护区域在遮罩上方
                if zy1 < y1 and zy1 > y0:
                    y0 = zy1  # 裁剪顶部

        if y1 - y0 < 5:  # 裁剪后太小，跳过
            return None

        return [x0, y0, x1, y1]

    def _sanitize_text(self, text: str) -> str:
        """
        清理文本中的 HTML 标签，避免 ReportLab 解析错误。
        """
        import re

        # 移除所有 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        # 转义剩余的特殊字符
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        # 将换行转为 <br/>
        text = text.replace("\n", "<br/>")
        return text

    def _fit_text_to_box(
        self,
        pdf: canvas.Canvas,
        text: str,
        x: float,
        y_bottom: float,
        width: float,
        height: float,
        font_name: str,
        font_size: float,
        leading_mult: float,
        min_font_size: float = 4.0,  # 最小字体4pt
        font_step: float = 0.5,
    ) -> None:
        """
        渲染文本到指定边界框，如果放不下则自动缩小字体。
        如果即使最小字体也放不下，使用裁剪防止溢出。
        """
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph

        text = self._sanitize_text(text)
        current_font_size = font_size
        p = None
        actual_h = height  # 默认值

        # 循环尝试，直到文本能放下或达到最小字体
        while current_font_size >= min_font_size:
            style = ParagraphStyle(
                name="Normal",
                fontName=font_name,
                fontSize=current_font_size,
                leading=current_font_size * leading_mult,
                alignment=TA_LEFT,
                textColor="black",
            )

            p = Paragraph(text, style)
            w, actual_h = p.wrap(width, height)

            if actual_h <= height:
                break  # 能放下，使用当前字体大小

            current_font_size -= font_step  # 缩小字体继续尝试

        if p is None:
            return

        # 检查是否溢出
        needs_clip = actual_h > height
        if needs_clip:
            print(f"WARNING: Text overflow - need {actual_h:.1f}px but only have {height:.1f}px, applying clip")
            # 使用裁剪路径防止溢出
            pdf.saveState()
            clip_path = pdf.beginPath()
            clip_path.rect(x - 1, y_bottom - 1, width + 2, height + 2)
            clip_path.close()
            pdf.clipPath(clip_path, stroke=0, fill=0)

        # 绘制文本（顶部对齐，但不超出边界）
        draw_y = (y_bottom + height) - actual_h
        # 确保不会画到边界下方
        if draw_y < y_bottom:
            draw_y = y_bottom

        p.drawOn(pdf, x, draw_y)

        if needs_clip:
            pdf.restoreState()
