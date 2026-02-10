from __future__ import annotations

import asyncio
import json
import logging

import httpx

logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = (
    "You are an expert document analyzer. Your task is to classify text blocks from academic PDFs.\n\n"
    "For each text block, determine if it should be:\n"
    "1. REWRITE - Normal body text, paragraphs, section headers, figure captions, and any complete sentences. "
    "This includes text that describes or explains formulas, figures, or algorithms.\n"
    "2. PRESERVE - ONLY isolated visual elements: axis labels (x, y), single symbols (α, β), "
    "short labels within charts (SE, p<0.05), reference markers like (a)(b)(c), "
    "or pure mathematical notation without explanatory text.\n\n"
    "CRITICAL RULES:\n"
    "- If text contains a complete sentence (subject + verb), it is REWRITE.\n"
    "- If text is longer than 20 characters with words, it is likely REWRITE.\n"
    "- Text describing formulas (e.g., 'where μ = mean(...)') is REWRITE.\n"
    "- Figure captions ('Figure 1: ...') are REWRITE.\n"
    "- Only very short isolated labels (≤3 words, no verbs) should be PRESERVE.\n\n"
    "Examples:\n"
    "- 'For an LLM-based policy, we compute...' → REWRITE\n"
    "- 'where μ_i = mean(A_i^tok)' → REWRITE\n"
    "- 'This ensures that for each task i...' → REWRITE\n"
    "- 'Figure 1: System architecture' → REWRITE\n"
    "- 'x-axis' → PRESERVE\n"
    "- 'α' → PRESERVE\n"
    "- '(1)' → PRESERVE\n"
    "- 'SE' → PRESERVE\n\n"
    "Respond with a JSON object containing a list of classifications. Format:\n"
    "{\n"
    '  "classifications": [\n'
    '    {"id": 0, "type": "REWRITE"},\n'
    '    {"id": 1, "type": "PRESERVE"}\n'
    "  ]\n"
    "}\n"
    "Ensure the order matches the input blocks exactly."
)


class BlockClassifier:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.zhizengzeng.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(60.0, connect=10.0))

    async def classify_blocks(self, blocks: list[dict]) -> list[str]:
        """
        Classify a list of text blocks.
        Returns a list of classifications: 'REWRITE' or 'PRESERVE'
        """
        if not blocks:
            return []

        # Build input for LLM
        block_descriptions = []
        for i, block in enumerate(blocks):
            text = block.get("text", "")[:500]  # Limit to 500 chars context
            bbox = block.get("bbox", [0, 0, 0, 0])
            page_index = block.get("page_index", 0)

            # Add context about position (e.g., "Left side", "Top")
            # This helps if the user knows figures are often on one side

            desc = f'Block {i} (Page {page_index + 1}, Position: {bbox}): "{text}"'
            block_descriptions.append(desc)

        input_text = "\n\n".join(block_descriptions)

        # Call LLM
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await self._do_classify(input_text, len(blocks))
                # 应用启发式验证规则纠正明显错误
                return self._validate_classifications(blocks, result)
            except Exception as exc:
                if attempt == max_retries - 1:
                    logger.error("Block classification failed: %s", exc)
                    # Default to REWRITE for all blocks on failure to ensure content is processed
                    return ["REWRITE"] * len(blocks)

                delay = 2 * (2**attempt)
                logger.warning("Classification error: %s, retrying in %ds...", exc, delay)
                await asyncio.sleep(delay)

        return ["REWRITE"] * len(blocks)

    async def _do_classify(self, input_text: str, expected_count: int) -> list[str]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CLASSIFICATION_PROMPT},
                {"role": "user", "content": f"Classify these {expected_count} blocks:\n\n{input_text}"},
            ],
            "temperature": 0.1,
            "max_tokens": 4096,
            # "response_format": {"type": "json_object"} # Removed as it causes 400 with some models
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = await self._client.post("/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "").strip()

        try:
            # Clean markdown code blocks if present
            if content.startswith("```"):
                # Remove first line (```json) and last line (```)
                lines = content.split("\n")
                if len(lines) >= 2:
                    # Find start of JSON
                    start_idx = 0
                    if lines[0].startswith("```"):
                        start_idx = 1

                    # Find end of JSON
                    end_idx = len(lines)
                    if lines[-1].strip() == "```":
                        end_idx = -1

                    content = "\n".join(lines[start_idx:end_idx])

            parsed = json.loads(content)
            classifications_list = parsed.get("classifications", [])

            # Map back to list
            result_map = {item["id"]: item["type"] for item in classifications_list}

            final_results = []
            for i in range(expected_count):
                res = result_map.get(i, "REWRITE")  # Default to REWRITE if missing
                if res not in ["REWRITE", "PRESERVE"]:
                    res = "REWRITE"
                final_results.append(res)

            return final_results

        except json.JSONDecodeError:
            logger.error("Failed to parse classification JSON: %s", content)
            # Fallback: try to find JSON object in text
            try:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    json_str = content[start : end + 1]
                    parsed = json.loads(json_str)
                    classifications_list = parsed.get("classifications", [])
                    result_map = {item["id"]: item["type"] for item in classifications_list}
                    final_results = []
                    for i in range(expected_count):
                        res = result_map.get(i, "REWRITE")
                        final_results.append(res)
                    return final_results
            except Exception:
                pass

            raise ValueError("Invalid JSON response")  # noqa: B904

    def _is_pure_formula(self, text: str) -> bool:
        """
        检测文本是否是【纯公式】（几乎没有描述性文字）。

        区分：
        - 纯公式："A_{i,s,g,t,k} = ..." → PRESERVE
        - 混合文本："For an LLM-based policy, action a_t consists of..." → REWRITE（翻译时保留符号）
        - 短标签："x-axis", "α", "(1)" → PRESERVE
        """
        text = text.strip()

        # 规则1: 非常短的文本（<15字符），可能是标签或符号
        if len(text) < 15:
            return True

        # 规则2: 检测是否包含完整句子（有主谓结构的描述性文字）
        # 如果有完整句子，即使包含数学符号也应该翻译
        sentence_indicators = [
            " is ",
            " are ",
            " was ",
            " were ",
            " have ",
            " has ",
            " can ",
            " will ",
            " should ",
            " may ",
            " might ",
            " the ",
            " a ",
            " an ",
            " this ",
            " that ",
            " these ",
            " we ",
            " our ",
            " they ",
            " it ",
            " its ",
            " where ",
            " which ",
            " when ",
            " how ",
            " what ",
            " denote ",
            " denotes ",
            " represent ",
            " represents ",
            " compute ",
            " define ",
            " ensure ",
            " consider ",
        ]
        text_lower = text.lower()
        has_sentence = any(ind in text_lower for ind in sentence_indicators)

        # 如果包含句子结构，这是描述性文字，应该翻译
        if has_sentence:
            return False

        # 规则3: 检测是否以大写字母开头的完整句子
        if text[0].isupper() and ". " in text:
            return False

        # 规则4: 长度>100 的文本几乎肯定是描述性段落
        if len(text) > 100:
            return False

        # 规则5: 只有短文本（<50字符）且没有句子结构，才可能是纯公式
        if len(text) < 50:
            # 检查是否主要由数学符号组成
            math_chars = "₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹≤≥≠≈∈∑∫∂αβγδεζηθικλμνξπρστυφχψω{}[]()=+-*/_^"
            math_ratio = sum(1 for c in text if c in math_chars or not c.isalpha()) / max(len(text), 1)
            if math_ratio > 0.5:
                return True

        return False

    def _validate_classifications(self, blocks: list[dict], classifications: list[str]) -> list[str]:
        """应用启发式规则纠正分类错误"""
        validated = []
        for block, classification in zip(blocks, classifications, strict=False):
            text = block.get("text", "").strip()

            # 规则0: 纯公式/短标签必须 PRESERVE
            if self._is_pure_formula(text):
                validated.append("PRESERVE")
                continue

            # 规则1: 包含完整句子（有句号）且长度>30，强制 REWRITE
            # 即使包含数学符号，描述性文字也应该翻译（翻译时会保留符号）
            if "." in text and len(text) > 30:
                classification = "REWRITE"

            # 规则2: 长度>50 的文本是描述性段落，强制 REWRITE
            if len(text) > 50:
                classification = "REWRITE"

            # 规则3: 包含常见动词的文本是正文
            verbs = [
                "is",
                "are",
                "was",
                "were",
                "have",
                "has",
                "can",
                "will",
                "should",
                "compute",
                "define",
                "ensure",
                "denote",
                "consider",
            ]
            if any(f" {v} " in f" {text.lower()} " for v in verbs):
                classification = "REWRITE"

            validated.append(classification)

        return validated

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> BlockClassifier:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.close()
