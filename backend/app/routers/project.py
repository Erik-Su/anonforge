from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import Depends, HTTPException, Query, Request, Response, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.middlewares import common
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.routers.base import BaseView, route
from app.schemas.project import (
    ProjectCreate,
    ProjectMemberInvite,
    ProjectMemberRead,
    ProjectMemberRoleUpdate,
    ProjectRead,
    ProjectUpdate,
)
from app.schemas.user import UserRead
from app.services import project as project_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AUTH = [Depends(common.jwt_auth_middleware), Depends(common.request_duration_middleware)]


class ProjectView(BaseView):
    """项目类视图。"""

    router_prefix = "/projects"
    router_tags = ["project"]

    @staticmethod
    def _raise_as_http(exc: Exception) -> NoReturn:
        if isinstance(exc, project_service.ProjectNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, project_service.ProjectAccessDeniedError):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        if isinstance(exc, project_service.ProjectMemberNotFoundError):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if isinstance(exc, project_service.ProjectMemberConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise exc

    @route(
        "/",
        methods=["GET"],
        response_model=list[ProjectRead],
        summary="获取项目列表",
        description="返回当前用户可访问的全部项目，超级管理员可见所有项目。",
        middlewares=AUTH,
    )
    async def list_projects(self, request: Request, session: SessionDep) -> list[Project]:
        uid = request.state.current_user_public_id
        return await project_service.list_projects(session, uid)

    @route(
        "/search",
        methods=["GET"],
        response_model=list[ProjectRead],
        summary="搜索项目",
        description="按项目名（name）或成员公开 ID（member）搜索当前用户可访问的项目。",
        middlewares=AUTH,
    )
    async def search_projects(
        self,
        request: Request,
        session: SessionDep,
        name: str | None = Query(default=None, description="按项目名模糊搜索"),
        member: str | None = Query(default=None, description="按成员公开 ID 筛选"),
    ) -> list[Project]:
        uid = request.state.current_user_public_id
        if member:
            return await project_service.search_projects_by_member(session, uid, member)
        if name:
            return await project_service.search_projects_by_name(session, uid, name)
        return await project_service.list_projects(session, uid)

    @route(
        "/",
        methods=["POST"],
        response_model=ProjectRead,
        status_code=status.HTTP_201_CREATED,
        summary="创建项目",
        description="创建新项目，创建者自动成为 owner 成员。",
        middlewares=AUTH,
    )
    async def create_project(self, request: Request, payload: ProjectCreate, session: SessionDep) -> Project:
        uid = request.state.current_user_public_id
        try:
            return await project_service.create_project(session, uid, payload)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}",
        methods=["GET"],
        response_model=ProjectRead,
        summary="获取项目详情",
        description="按公开 ID 查询项目详情，无权限时返回 403。",
        middlewares=AUTH,
    )
    async def get_project(self, public_id: str, request: Request, session: SessionDep) -> Project:
        uid = request.state.current_user_public_id
        try:
            project = await project_service.get_project_by_public_id(session, public_id, uid)
            if project is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
            return project
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}",
        methods=["PATCH"],
        response_model=ProjectRead,
        summary="更新项目",
        description="更新项目基础信息，仅项目成员可操作。",
        middlewares=AUTH,
    )
    async def update_project(self, public_id: str, request: Request, payload: ProjectUpdate, session: SessionDep) -> Project:
        uid = request.state.current_user_public_id
        try:
            return await project_service.update_project(session, public_id, payload, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/disable",
        methods=["PATCH"],
        response_model=ProjectRead,
        summary="禁用项目",
        middlewares=AUTH,
    )
    async def disable_project(self, public_id: str, request: Request, session: SessionDep) -> Project:
        uid = request.state.current_user_public_id
        try:
            return await project_service.disable_project(session, public_id, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/enable",
        methods=["PATCH"],
        response_model=ProjectRead,
        summary="启用项目",
        middlewares=AUTH,
    )
    async def enable_project(self, public_id: str, request: Request, session: SessionDep) -> Project:
        uid = request.state.current_user_public_id
        try:
            return await project_service.enable_project(session, public_id, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}",
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="删除项目",
        description="删除项目及其全部成员关系。",
        middlewares=AUTH,
    )
    async def delete_project(self, public_id: str, request: Request, session: SessionDep) -> Response:
        uid = request.state.current_user_public_id
        try:
            await project_service.delete_project(session, public_id, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @route(
        "/{public_id}/members",
        methods=["GET"],
        response_model=list[ProjectMemberRead],
        summary="获取项目成员列表",
        middlewares=AUTH,
    )
    async def list_project_members(self, public_id: str, request: Request, session: SessionDep) -> list[ProjectMember]:
        uid = request.state.current_user_public_id
        try:
            return await project_service.list_project_members(session, public_id, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/members/candidates",
        methods=["GET"],
        response_model=list[UserRead],
        summary="搜索可邀请用户",
        description="按用户名或邮箱搜索尚未加入项目的用户。",
        middlewares=AUTH,
    )
    async def search_member_candidates(
        self,
        public_id: str,
        request: Request,
        session: SessionDep,
        keyword: str = Query(default="", description="用户名或邮箱关键词"),
    ) -> list[User]:
        uid = request.state.current_user_public_id
        try:
            return await project_service.search_project_member_candidates(session, public_id, keyword, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/members",
        methods=["POST"],
        response_model=ProjectMemberRead,
        status_code=status.HTTP_201_CREATED,
        summary="邀请项目成员",
        middlewares=AUTH,
    )
    async def invite_project_member(
        self, public_id: str, request: Request, payload: ProjectMemberInvite, session: SessionDep
    ) -> ProjectMember:
        uid = request.state.current_user_public_id
        try:
            return await project_service.invite_project_member(session, public_id, payload.user_public_id, payload.role, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/members/{user_public_id}",
        methods=["PATCH"],
        response_model=ProjectMemberRead,
        summary="更新成员角色",
        middlewares=AUTH,
    )
    async def update_member_role(
        self, public_id: str, user_public_id: str, request: Request, payload: ProjectMemberRoleUpdate, session: SessionDep
    ) -> ProjectMember:
        uid = request.state.current_user_public_id
        try:
            return await project_service.update_project_member_role(session, public_id, user_public_id, payload.role, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)

    @route(
        "/{public_id}/members/{user_public_id}",
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        summary="移除项目成员",
        middlewares=AUTH,
    )
    async def remove_project_member(
        self, public_id: str, user_public_id: str, request: Request, session: SessionDep
    ) -> Response:
        uid = request.state.current_user_public_id
        try:
            await project_service.remove_project_member(session, public_id, user_public_id, uid)
        except project_service.ProjectServiceError as exc:
            self._raise_as_http(exc)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


router = ProjectView()()
