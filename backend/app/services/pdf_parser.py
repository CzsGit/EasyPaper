from __future__ import annotations

from dataclasses import dataclass, field

import fitz  # type: ignore


@dataclass
class PageLayout:
    width: float
    height: float
    images: list[dict]
    text_blocks: list[dict]
    links: list[dict]
    page_index: int
    protected_zones: list[list[float]] = field(default_factory=list)  # 保护区域（图片、表格）


@dataclass
class DocumentLayout:
    pages: list[PageLayout]
    filename: str


class PDFParser:
    def __init__(self, max_pages: int = 100) -> None:
        self.max_pages = max_pages
        from .layout_analyzer import LayoutAnalyzer

        self.layout_analyzer = LayoutAnalyzer()

    def parse(self, file_bytes: bytes, filename: str, progress_callback=None) -> DocumentLayout:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if doc.page_count > self.max_pages:
            raise ValueError(f"PDF页数超过限制：{self.max_pages}")

        # 第一遍扫描：统计字体大小分布，确定正文字号
        font_sizes = []
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if b["type"] == 0:  # text
                    for line in b["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip():
                                font_sizes.append(span["size"])

        base_size = 11.0
        if font_sizes:
            base_size = max(set(font_sizes), key=font_sizes.count)

        pages: list[PageLayout] = []
        block_counter = 0

        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            width, height = page.rect.width, page.rect.height

            # 1. 获取全页背景图
            background_img = self._get_page_background(page)
            images = [{"type": "background", "data": background_img, "bbox": [0, 0, width, height]}]
            page_links = []

            # 2. 使用 YOLOv10 进行版面分析 (Layout Analysis)
            # 将页面转为图片供模型分析
            pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))  # 1x scale is usually enough for 640x640 input
            page_img_bytes = pix.tobytes("png")

            layout_results = self.layout_analyzer.analyze(page_img_bytes)

            if progress_callback:
                # Progress from 10% to 20%
                current_progress = 10 + int(10 * ((page_index + 1) / doc.page_count))
                progress_callback(current_progress, f"正在分析页面布局 ({page_index + 1}/{doc.page_count})")

            # 提取保护区域 (Non-Text Zones)
            protected_zones = []
            for res in layout_results:
                label = res["label"]
                bbox = res["bbox"]
                # YOLO classes: Text, Title, List, Table, Figure
                # We want to protect Table and Figure.
                # Title and List should be rewritten.
                if label in ["Table", "Figure"]:
                    protected_zones.append(fitz.Rect(bbox))

            # 3. 提取并筛选文本块
            text_blocks = []
            raw_blocks = page.get_text("dict").get("blocks", [])

            for block in raw_blocks:
                if block.get("type") != 0:  # 只处理文本
                    continue

                bbox = [float(v) for v in block.get("bbox", [])]
                block_rect = fitz.Rect(bbox)

                # 过滤页眉页脚
                if bbox[1] < height * 0.05 or bbox[3] > height * 0.95:
                    continue

                # 过滤保护区域内的文本 (Intersection Check)
                is_protected = False
                for zone in protected_zones:
                    # Use & operator for intersection
                    intersection = block_rect & zone
                    # 如果重叠面积超过文本块面积的 50%，或者完全包含，则视为保护
                    # 或者简单的相交判定
                    if (intersection.width * intersection.height) > (block_rect.width * block_rect.height) * 0.5:
                        is_protected = True
                        break

                if is_protected:
                    continue

                # 过滤数学公式 (Still useful as a secondary check)
                if self._is_math_block(block, width):
                    continue

                processed_block = self._process_text_block(block, base_size, block_counter, page_index)
                if processed_block:
                    processed_block["links"] = []
                    text_blocks.append(processed_block)
                    block_counter += 1

            # 4. 合并相邻文本块 (Merge adjacent blocks)
            merged_blocks = self._merge_text_blocks(text_blocks)

            # 保存保护区域的 bbox 列表
            protected_zone_bboxes = [[z.x0, z.y0, z.x1, z.y1] for z in protected_zones]

            pages.append(
                PageLayout(
                    width=width,
                    height=height,
                    images=images,
                    text_blocks=merged_blocks,
                    links=page_links,
                    page_index=page_index,
                    protected_zones=protected_zone_bboxes,
                )
            )

        return DocumentLayout(pages=pages, filename=filename)

    def _merge_text_blocks(self, blocks: list[dict]) -> list[dict]:
        """
        合并垂直相邻的文本块，减少碎片化。
        """
        if not blocks:
            return []

        # 按 Y 坐标排序 (Reverted for Coordinate-based Layout)
        sorted_blocks = sorted(blocks, key=lambda b: b["bbox"][1])
        merged = []
        current = sorted_blocks[0]

        for next_block in sorted_blocks[1:]:
            # 判断是否可以合并
            # 1. 垂直距离很近
            # Note: In reading order, next_block might be in a new column (top of page), so v_gap could be negative.
            # We only merge if next_block is BELOW current block.
            v_gap = next_block["bbox"][1] - current["bbox"][3]

            # 2. 水平对齐 (左对齐或居中)
            h_align_diff = abs(next_block["bbox"][0] - current["bbox"][0])

            # 限制合并的文本长度，避免创建过大的文本块导致翻译后溢出
            current_text_len = len(current.get("text", ""))
            next_text_len = len(next_block.get("text", ""))
            combined_len = current_text_len + next_text_len

            should_merge = (
                v_gap >= -5.0
                and v_gap < 15.0  # 垂直间距更严格 (was 20)
                and h_align_diff < 15.0  # 水平对齐更严格 (was 20)
                and current["rotation"] == next_block["rotation"]
                and combined_len < 500  # 合并后文本不超过500字符
            )

            if should_merge:
                # 合并
                # 更新 bbox: [min_x, min_y, max_x, max_y]
                new_bbox = [
                    min(current["bbox"][0], next_block["bbox"][0]),
                    min(current["bbox"][1], next_block["bbox"][1]),
                    max(current["bbox"][2], next_block["bbox"][2]),
                    max(current["bbox"][3], next_block["bbox"][3]),
                ]

                # 合并文本 (加换行符)
                new_text = current["text"] + "\n" + next_block["text"]

                # 更新 current
                current["bbox"] = new_bbox
                current["text"] = new_text
                # ID 保持第一个 block 的 ID
                # Style 保持第一个 block 的 style (或者重新计算，但这里先简单处理)
            else:
                merged.append(current)
                current = next_block

        merged.append(current)
        return merged

    def _get_page_background(self, page) -> bytes:
        """
        获取全页背景图。
        使用 2x 缩放以保证清晰度。
        """
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        return pix.tobytes("png")

    def _process_text_block(self, block: dict, base_size: float, counter: int, page_index: int) -> dict | None:
        text_content = []
        block_size = 0.0
        block_flags = 0
        span_count = 0

        # Detect rotation from the first line
        lines = block.get("lines", [])
        rotation = 0
        if lines:
            dir_vec = lines[0].get("dir", (1, 0))
            if abs(dir_vec[0]) < 0.1:  # Vertical
                if dir_vec[1] < 0:
                    rotation = 90
                else:
                    rotation = 270
            elif dir_vec[0] < 0:  # Horizontal reversed
                rotation = 180

        for line in lines:
            for span in line.get("spans", []):
                text = span.get("text", "")
                text_content.append(text)
                if text.strip():
                    block_size += span["size"]
                    block_flags |= span["flags"]
                    span_count += 1
            text_content.append("\n")

        full_text = "".join(text_content).strip()
        if not full_text:
            return None

        avg_size = block_size / span_count if span_count > 0 else base_size
        bbox = [float(v) for v in block.get("bbox", [])]

        style = "body"
        if avg_size > base_size * 1.6:
            style = "h1"
        elif avg_size > base_size * 1.3:
            style = "h2"
        elif avg_size < base_size * 0.9:
            style = "caption"

        bold_span_count = 0
        for line in lines:
            for span in line.get("spans", []):
                if span["text"].strip() and (span["flags"] & 16):
                    bold_span_count += 1

        is_bold = (bold_span_count / span_count > 0.5) if span_count > 0 else False

        return {
            "type": "text",
            "text": full_text,
            "bbox": bbox,
            "page_index": page_index,
            "id": f"block_{counter}",
            "style": style,
            "font_size": avg_size,
            "is_bold": is_bold,
            "rotation": rotation,
        }

    def _is_math_block(self, block: dict, page_width: float = 600.0) -> bool:
        """
        判断文本块是否为数学公式。
        策略：大幅收紧判定标准，防止误伤正文。
        """
        text = "".join([span["text"] for line in block.get("lines", []) for span in line.get("spans", [])]).strip()
        if not text:
            return False

        # 0. 段落检测 (Paragraph Detection)
        if len(text) > 150 and text.count(" ") > 5:
            return False

        # 1. 基于字体的检测 (Font-based Detection)
        fonts = set()
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                fonts.add(span.get("font", "").lower())

        math_fonts = ["cmmi", "cmsy", "cmex", "msbm", "wasy", "dsrom", "euclid", "stix"]
        body_fonts = ["nimbus", "arial", "helvetica", "times", "calibri"]

        has_math_font = any(any(mf in f for mf in math_fonts) for f in fonts)
        has_body_font = any(any(bf in f for bf in body_fonts) for f in fonts)

        if has_math_font and not has_body_font:
            return True

        if has_math_font:
            text_no_space = text.replace(" ", "")
            alpha_count = sum(c.isalpha() for c in text_no_space)

            is_likely_text = False
            if len(text) > 0 and alpha_count / len(text) > 0.6:
                if " " in text.strip():
                    is_likely_text = True
                elif len(text) < 5:
                    is_likely_text = False
                else:
                    is_likely_text = True

            if not is_likely_text:
                return True

        # 2. 基于布局的检测 (Layout-based Detection)
        if "LRL" in text and ("(" in text or "=" in text) and len(text) < 100:
            return True

        piecewise_keywords = ["If on", "Otherwise", "adaptation using SE"]
        if any(kw in text for kw in piecewise_keywords):
            if any(c in text for c in "()=012"):
                return True

        math_indicators = [":=", "≈", "≠", "≤", "≥", "∑", "∫", "∂", "∇", "√", "∏"]
        if any(x in text for x in math_indicators):
            return True

        # 3. 短文本/孤立字符检测
        if len(text) < 5:
            if any(c.isdigit() or c in "+-*/=<>(){}[],." for c in text):
                return True
            if len(text) == 1 and text.isalpha():
                return True

        return False
