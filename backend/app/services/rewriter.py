from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

import httpx

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "你是一位专业的学术翻译专家。你的任务是将英文学术论文翻译成流畅、准确的中文。\n\n"
    "【最重要的规则】\n"
    "数学符号和变量必须原样保留，绝对不能翻译或修改：\n"
    "- 变量名：a_t, x_i, y_{t,k}, Â_{i,s,g,t,k} 等\n"
    "- 希腊字母：α, β, γ, μ, σ 等\n"
    "- 数学符号：≤, ≥, ∈, ∑, ∫ 等\n"
    "- 公式：保持完全不变\n"
    "- 下标上标：保持原样\n\n"
    "例如：\n"
    "原文: 'For an LLM-based policy, each action a_t consists of tokens {y_{t,k}}'\n"
    "翻译: '对于基于LLM的策略，每个动作 a_t 由令牌 {y_{t,k}} 组成'\n\n"
    "其他规则：\n"
    "1. 翻译成自然流畅的中文，保持学术严谨性。\n"
    "2. 技术术语可以保留英文或在中文后用括号标注。\n"
    "3. 移除引用标记（如 [1], [2-4], (Smith et al., 2020)）。\n"
    "4. 章节标题直接翻译。\n"
    "5. 参考文献列表保持原样不翻译。\n"
    "6. 只输出纯文本，不要添加 HTML 标签或 Markdown 格式。"
)


class LLMRewriter:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.zhizengzeng.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self._client = httpx.AsyncClient(base_url=base_url, timeout=httpx.Timeout(120.0, connect=10.0))

    async def rewrite_blocks(self, blocks: Sequence[str]) -> list[str]:
        results: list[str] = []
        for text in blocks:
            simplified = await self.rewrite(text)
            results.append(simplified)
        return results

    async def rewrite(self, text: str) -> str:
        if not text.strip():
            return text

        # 简单的重试逻辑
        max_retries = 3
        base_delay = 2

        for attempt in range(max_retries):
            try:
                return await self._do_rewrite(text)
            except Exception as exc:
                if attempt == max_retries - 1:
                    logger.error("LLM重写失败 (最终尝试): %s", exc)
                    return text

                delay = base_delay * (2**attempt)
                logger.warning("LLM重写出错: %s, %d秒后重试...", exc, delay)
                await asyncio.sleep(delay)
        return text

    async def _do_rewrite(self, text: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "请将以下英文翻译成中文：\n\n" + text,
                },
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
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
        return message.get("content", text).strip() or text

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> LLMRewriter:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        await self.close()
