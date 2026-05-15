# 配置管理（读取环境变量、全局配置项）

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "App")
    app_description: str = os.getenv("APP_DESCRIPTION", "App description")
    app_env: str = os.getenv("APP_ENV", "development")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    oss_root: str = os.getenv("OSS_ROOT", "./data/oss")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")


settings = Settings()