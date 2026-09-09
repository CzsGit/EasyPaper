from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import LLMConfig
from app.services.ai_client import AIClient, AIError


def _fake_codex(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fake-codex.py"
    script.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\n"
        "args=sys.argv\n"
        "out=args[args.index('--output-last-message')+1]\n"
        "sys.stdin.read()\n" + body + "\n",
        encoding="utf-8",
    )
    script.chmod(0o700)
    return str(script)


def _config(executable: str) -> LLMConfig:
    return LLMConfig(provider="codex", codex={"executable": executable, "timeout_seconds": 10})


@pytest.mark.asyncio
async def test_codex_client_returns_structured_text_without_api_credentials(tmp_path, monkeypatch):
    executable = _fake_codex(
        tmp_path,
        """
print(json.dumps({'type':'thread.started','thread_id':'fixture'}))
print(json.dumps({'type':'turn.started'}))
leaked = bool(os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY'))
open(out, 'w').write(json.dumps({'text': json.dumps({'answer':'ok', 'credential_leaked': leaked})}))
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'fixture'}}))
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'cached_input_tokens':0,'output_tokens':1,'reasoning_output_tokens':0}}))
""",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-inherited")
    result = await AIClient(_config(executable)).complete_json("Return JSON.", "hello")
    assert result == {"answer": "ok", "credential_leaked": False}


@pytest.mark.asyncio
async def test_codex_client_rejects_tool_events(tmp_path):
    executable = _fake_codex(
        tmp_path,
        """
print(json.dumps({'type':'item.started','item':{'type':'command_execution','command':'echo'}}))
""",
    )
    with pytest.raises(AIError, match="终止"):
        await AIClient(_config(executable)).complete("Return text.", "hello")
