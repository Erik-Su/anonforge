from __future__ import annotations

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.project import ProjectMemberRole, ProjectVideoMode
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services import project as svc
from app.utils.time_tools import utc_now

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 工厂函数
# ---------------------------------------------------------------------------

def _make_user(username: str, is_superuser: bool = False) -> User:
    return User(
        username=username,
        password_hash="hashed",
        is_superuser=is_superuser,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def _make_project_payload(name: str = "测试项目") -> ProjectCreate:
    return ProjectCreate(
        name=name,
        intro="简介",
        project_type="novel_to_video",
        content_type="novel",
        art_style="3D_chinese_traditional",
        director_manual="",
        video_ratio="9:16",
        image_model="",
        video_model="",
        image_quality="standard",
        mode=ProjectVideoMode.TEXT,
    )


@pytest_asyncio.fixture
async def owner(db_session: AsyncSession) -> User:
    user = _make_user("owner")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def other_user(db_session: AsyncSession) -> User:
    user = _make_user("other")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def superuser(db_session: AsyncSession) -> User:
    user = _make_user("admin", is_superuser=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def project(db_session: AsyncSession, owner: User):
    return await svc.create_project(db_session, owner.public_id, _make_project_payload())


# ---------------------------------------------------------------------------
# 创建项目
# ---------------------------------------------------------------------------

class TestCreateProject:
    async def test_creates_project_with_correct_fields(self, db_session: AsyncSession, owner: User):
        proj = await svc.create_project(db_session, owner.public_id, _make_project_payload("我的项目"))

        assert proj.id is not None
        assert proj.public_id != ""
        assert proj.name == "我的项目"
        assert proj.owner_id == owner.public_id

    async def test_owner_automatically_added_as_member(self, db_session: AsyncSession, owner: User, project):
        members = await svc.list_project_members(db_session, project.public_id, owner.public_id)

        assert len(members) == 1
        assert members[0].user_public_id == owner.public_id
        assert members[0].role == ProjectMemberRole.OWNER


# ---------------------------------------------------------------------------
# 查询项目
# ---------------------------------------------------------------------------

class TestGetProject:
    async def test_get_by_public_id(self, db_session: AsyncSession, owner: User, project):
        found = await svc.get_project_by_public_id(db_session, project.public_id, owner.public_id)
        assert found is not None
        assert found.id == project.id

    async def test_get_nonexistent_returns_none(self, db_session: AsyncSession, owner: User):
        result = await svc.get_project_by_public_id(db_session, "nonexistent-id", owner.public_id)
        assert result is None

    async def test_get_raises_when_no_access(self, db_session: AsyncSession, other_user: User, project):
        with pytest.raises(svc.ProjectAccessDeniedError):
            await svc.get_project_or_raise(db_session, project.public_id, other_user.public_id)

    async def test_superuser_can_access_any_project(self, db_session: AsyncSession, superuser: User, project):
        found = await svc.get_project_by_public_id(db_session, project.public_id, superuser.public_id)
        assert found is not None


# ---------------------------------------------------------------------------
# 列表与搜索
# ---------------------------------------------------------------------------

class TestListAndSearchProjects:
    async def test_owner_sees_own_project(self, db_session: AsyncSession, owner: User, project):
        projects = await svc.list_projects(db_session, owner.public_id)
        assert any(p.id == project.id for p in projects)

    async def test_unrelated_user_sees_nothing(self, db_session: AsyncSession, other_user: User, project):
        projects = await svc.list_projects(db_session, other_user.public_id)
        assert all(p.id != project.id for p in projects)

    async def test_superuser_sees_all_projects(self, db_session: AsyncSession, superuser: User, project):
        projects = await svc.list_projects(db_session, superuser.public_id)
        assert any(p.id == project.id for p in projects)

    async def test_member_sees_joined_project(self, db_session: AsyncSession, owner: User, other_user: User, project):
        await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.EDITOR, owner.public_id
        )
        projects = await svc.list_projects(db_session, other_user.public_id)
        assert any(p.id == project.id for p in projects)

    async def test_search_by_name_matches(self, db_session: AsyncSession, owner: User, project):
        results = await svc.search_projects_by_name(db_session, owner.public_id, "测试")
        assert any(p.id == project.id for p in results)

    async def test_search_by_name_no_match(self, db_session: AsyncSession, owner: User, project):
        results = await svc.search_projects_by_name(db_session, owner.public_id, "不存在xyz")
        assert not any(p.id == project.id for p in results)

    async def test_search_by_member(self, db_session: AsyncSession, owner: User, project):
        results = await svc.search_projects_by_member(db_session, owner.public_id, owner.public_id)
        assert any(p.id == project.id for p in results)


# ---------------------------------------------------------------------------
# 更新项目
# ---------------------------------------------------------------------------

class TestUpdateProject:
    async def test_update_name(self, db_session: AsyncSession, owner: User, project):
        updated = await svc.update_project(
            db_session, project.public_id, ProjectUpdate(name="新名字"), owner.public_id
        )
        assert updated.name == "新名字"

    async def test_update_by_non_member_raises(self, db_session: AsyncSession, other_user: User, project):
        with pytest.raises(svc.ProjectAccessDeniedError):
            await svc.update_project(
                db_session, project.public_id, ProjectUpdate(name="x"), other_user.public_id
            )


# ---------------------------------------------------------------------------
# 禁用 / 启用项目
# ---------------------------------------------------------------------------

class TestDisableEnableProject:
    async def test_disable_sets_disabled_at(self, db_session: AsyncSession, owner: User, project):
        disabled = await svc.disable_project(db_session, project.public_id, owner.public_id)
        assert disabled.disabled_at is not None
        assert disabled.is_disabled

    async def test_enable_clears_disabled_at(self, db_session: AsyncSession, owner: User, project):
        await svc.disable_project(db_session, project.public_id, owner.public_id)
        enabled = await svc.enable_project(db_session, project.public_id, owner.public_id)
        assert enabled.disabled_at is None
        assert enabled.is_active


# ---------------------------------------------------------------------------
# 删除项目
# ---------------------------------------------------------------------------

class TestDeleteProject:
    async def test_delete_removes_project(self, db_session: AsyncSession, owner: User, project):
        await svc.delete_project(db_session, project.public_id, owner.public_id)
        result = await svc._get_project_by_public_id(db_session, project.public_id)
        assert result is None

    async def test_delete_by_non_member_raises(self, db_session: AsyncSession, other_user: User, project):
        with pytest.raises(svc.ProjectAccessDeniedError):
            await svc.delete_project(db_session, project.public_id, other_user.public_id)


# ---------------------------------------------------------------------------
# 成员管理
# ---------------------------------------------------------------------------

class TestProjectMembers:
    async def test_list_members_includes_owner(self, db_session: AsyncSession, owner: User, project):
        members = await svc.list_project_members(db_session, project.public_id, owner.public_id)
        assert any(m.user_public_id == owner.public_id for m in members)

    async def test_invite_member(self, db_session: AsyncSession, owner: User, other_user: User, project):
        member = await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.EDITOR, owner.public_id
        )
        assert member.user_public_id == other_user.public_id
        assert member.role == ProjectMemberRole.EDITOR

    async def test_invite_duplicate_raises(self, db_session: AsyncSession, owner: User, other_user: User, project):
        await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.EDITOR, owner.public_id
        )
        with pytest.raises(svc.ProjectMemberConflictError):
            await svc.invite_project_member(
                db_session, project.public_id, other_user.public_id, ProjectMemberRole.VIEWER, owner.public_id
            )

    async def test_update_member_role(self, db_session: AsyncSession, owner: User, other_user: User, project):
        await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.VIEWER, owner.public_id
        )
        updated = await svc.update_project_member_role(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.ADMIN, owner.public_id
        )
        assert updated.role == ProjectMemberRole.ADMIN

    async def test_remove_member(self, db_session: AsyncSession, owner: User, other_user: User, project):
        await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.EDITOR, owner.public_id
        )
        await svc.remove_project_member(
            db_session, project.public_id, other_user.public_id, owner.public_id
        )
        members = await svc.list_project_members(db_session, project.public_id, owner.public_id)
        assert not any(m.user_public_id == other_user.public_id for m in members)

    async def test_remove_nonexistent_member_raises(self, db_session: AsyncSession, owner: User, other_user: User, project):
        with pytest.raises(svc.ProjectMemberNotFoundError):
            await svc.remove_project_member(
                db_session, project.public_id, other_user.public_id, owner.public_id
            )


# ---------------------------------------------------------------------------
# 搜索可邀请成员
# ---------------------------------------------------------------------------

class TestSearchMemberCandidates:
    async def test_returns_matching_user(self, db_session: AsyncSession, owner: User, other_user: User, project):
        candidates = await svc.search_project_member_candidates(
            db_session, project.public_id, "other", owner.public_id
        )
        assert any(u.public_id == other_user.public_id for u in candidates)

    async def test_excludes_owner(self, db_session: AsyncSession, owner: User, other_user: User, project):
        candidates = await svc.search_project_member_candidates(
            db_session, project.public_id, "owner", owner.public_id
        )
        assert not any(u.public_id == owner.public_id for u in candidates)

    async def test_excludes_existing_member(self, db_session: AsyncSession, owner: User, other_user: User, project):
        await svc.invite_project_member(
            db_session, project.public_id, other_user.public_id, ProjectMemberRole.VIEWER, owner.public_id
        )
        candidates = await svc.search_project_member_candidates(
            db_session, project.public_id, "other", owner.public_id
        )
        assert not any(u.public_id == other_user.public_id for u in candidates)

    async def test_empty_keyword_returns_empty(self, db_session: AsyncSession, owner: User, project):
        candidates = await svc.search_project_member_candidates(
            db_session, project.public_id, "   ", owner.public_id
        )
        assert candidates == []
