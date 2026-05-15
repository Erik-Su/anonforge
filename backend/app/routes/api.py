# 总路由（设置/api前缀，并统一接入routes下的所有的路由对象）

from fastapi import APIRouter

from app.core.config import settings
from app.routes.project import router as project_router

api_router = APIRouter(prefix=settings.api_prefix)
api_router.include_router(project_router)#include_router 是原地修改，直接把路由注册进 api_router 内部的路由表里。

@api_router.get("/health")
def health_check():
    return {"status": "ok"}


