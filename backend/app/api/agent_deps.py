from __future__ import annotations

from fastapi import Header, HTTPException, status

from ..core.config import get_config


def require_agent_api_key(x_agent_api_key: str | None = Header(default=None)) -> None:
    config = get_config()
    if not x_agent_api_key or x_agent_api_key not in config.agent.api_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid agent API key",
        )
