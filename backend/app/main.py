# FastAPI 应用入口，创建 app 实例、注册路由、中间件等

from __future__ import annotations


from fastapi import FastAPI

from app.core.config import settings
from app.routes.api import api_router

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name, 
        description=settings.app_description
    )
    app.include_router(api_router)
    return app

app = create_app()
