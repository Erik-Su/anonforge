# 项目相关接口
from fastapi import APIRouter

router = APIRouter(prefix="/projects", tags=["project"])


@router.get("/")
def list_projects() -> dict[str, str]:
    return {"module": "project"}