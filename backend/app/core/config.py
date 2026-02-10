from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    api_key: str = Field(..., alias="api_key")
    base_url: str = Field("https://api.zhizengzeng.com/v1", alias="base_url")
    model: str = Field("gemini-2.5-flash", alias="model")
    judge_model: str = Field("gemini-2.5-flash", alias="judge_model")


class ProcessingConfig(BaseModel):
    max_pages: int = Field(100, alias="max_pages")
    max_upload_mb: int = Field(50, alias="max_upload_mb")
    max_concurrent: int = Field(3, alias="max_concurrent")
    preview_html: bool = Field(True, alias="preview_html")


class StorageConfig(BaseModel):
    cleanup_minutes: int = Field(30, alias="cleanup_minutes")
    temp_dir: str = Field("./backend/tmp", alias="temp_dir")


class LoggingConfig(BaseModel):
    level: str = Field("INFO", alias="level")
    file: str = Field("./backend/logs/app.log", alias="file")


class DatabaseConfig(BaseModel):
    url: str = Field("sqlite:///./backend/data/app.db", alias="url")


class SecurityConfig(BaseModel):
    secret_key: str = Field("CHANGE_THIS_TO_A_SECURE_SECRET_KEY", alias="secret_key")
    cors_origins: list[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="cors_origins",
    )


class AppConfig(BaseModel):
    llm: LLMConfig
    processing: ProcessingConfig = ProcessingConfig()
    storage: StorageConfig = StorageConfig()
    logging: LoggingConfig = LoggingConfig()
    database: DatabaseConfig = DatabaseConfig()
    security: SecurityConfig = SecurityConfig()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    return data


@lru_cache
def get_config() -> AppConfig:
    # Try multiple paths
    candidates = [
        Path(os.getenv("APP_CONFIG_PATH", "")),
        Path("config/config.yaml"),
        Path("backend/config/config.yaml"),
    ]

    config_path = None
    for path in candidates:
        if path and path.exists() and path.is_file():
            config_path = path
            break

    if not config_path:
        # Fallback to example if exists, or raise error
        if Path("config/config.example.yaml").exists():
            config_path = Path("config/config.example.yaml")
        elif Path("backend/config/config.example.yaml").exists():
            config_path = Path("backend/config/config.example.yaml")
        else:
            raise FileNotFoundError("Config file not found in config/config.yaml or backend/config/config.yaml")

    raw = _load_yaml(config_path)
    return AppConfig(**raw)
