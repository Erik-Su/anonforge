from __future__ import annotations

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services import user as user_service
from app.utils.string_tools import hash_password
from app.utils.time_tools import utc_now


def make_user(**kwargs: object) -> User:
    defaults: dict[str, object] = dict(
        username="testuser",
        password_hash=hash_password("password123"),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    defaults.update(kwargs)
    return User(**defaults)  # type: ignore[arg-type]


class TestGetUserByUsername:
    async def test_returns_user_when_found(self, db_session: AsyncSession, saved_user: User) -> None:
        result = await user_service.get_user_by_username(db_session, saved_user.username)
        assert result is not None
        assert result.username == saved_user.username

    async def test_returns_none_when_not_found(self, db_session: AsyncSession) -> None:
        result = await user_service.get_user_by_username(db_session, "nonexistent")
        assert result is None


class TestGetUserByEmail:
    async def test_returns_user_when_found(self, db_session: AsyncSession) -> None:
        user = make_user(username="emailuser", email="find@example.com")
        db_session.add(user)
        await db_session.commit()

        result = await user_service.get_user_by_email(db_session, "find@example.com")
        assert result is not None
        assert result.email == "find@example.com"

    async def test_returns_none_when_not_found(self, db_session: AsyncSession) -> None:
        result = await user_service.get_user_by_email(db_session, "ghost@example.com")
        assert result is None


class TestGetUserByPublicId:
    async def test_returns_user_when_found(self, db_session: AsyncSession, saved_user: User) -> None:
        result = await user_service.get_user_by_public_id(db_session, saved_user.public_id)
        assert result is not None
        assert result.public_id == saved_user.public_id

    async def test_returns_none_when_not_found(self, db_session: AsyncSession) -> None:
        result = await user_service.get_user_by_public_id(db_session, "no-such-id")
        assert result is None


class TestGetUserOrRaise:
    async def test_returns_user_when_found(self, db_session: AsyncSession, saved_user: User) -> None:
        result = await user_service.get_user_or_raise(db_session, saved_user.public_id)
        assert result.public_id == saved_user.public_id

    async def test_raises_user_not_found_error(self, db_session: AsyncSession) -> None:
        with pytest.raises(user_service.UserNotFoundError):
            await user_service.get_user_or_raise(db_session, "no-such-id")


class TestEnsureUniqueUsername:
    async def test_passes_when_username_is_unique(self, db_session: AsyncSession) -> None:
        await user_service.ensure_unique_username(db_session, "brandnewuser")

    async def test_raises_when_username_taken(self, db_session: AsyncSession, saved_user: User) -> None:
        with pytest.raises(user_service.UserNameConflictError):
            await user_service.ensure_unique_username(db_session, saved_user.username)

    async def test_passes_when_same_user_keeps_own_username(self, db_session: AsyncSession, saved_user: User) -> None:
        await user_service.ensure_unique_username(
            db_session, saved_user.username, current_user_id=saved_user.id
        )


class TestEnsureUniqueEmail:
    async def test_passes_when_email_is_none(self, db_session: AsyncSession) -> None:
        await user_service.ensure_unique_email(db_session, None)

    async def test_passes_when_email_is_unique(self, db_session: AsyncSession) -> None:
        await user_service.ensure_unique_email(db_session, "unique@example.com")

    async def test_raises_when_email_taken(self, db_session: AsyncSession) -> None:
        user = make_user(username="emailowner", email="dup@example.com")
        db_session.add(user)
        await db_session.commit()

        with pytest.raises(user_service.UserEmailConflictError):
            await user_service.ensure_unique_email(db_session, "dup@example.com")

    async def test_passes_when_same_user_keeps_own_email(self, db_session: AsyncSession) -> None:
        user = make_user(username="sameowner", email="same@example.com")
        db_session.add(user)
        await db_session.commit()

        await user_service.ensure_unique_email(
            db_session, "same@example.com", current_user_id=user.id
        )


class TestListUsers:
    async def test_returns_empty_list(self, db_session: AsyncSession) -> None:
        result = await user_service.list_users(db_session)
        assert result == []

    async def test_returns_all_users(self, db_session: AsyncSession, saved_user: User) -> None:
        result = await user_service.list_users(db_session)
        assert len(result) == 1
        assert result[0].username == saved_user.username

    async def test_ordered_by_sort_order_then_id(self, db_session: AsyncSession) -> None:
        u1 = make_user(username="z_user", sort_order=2)
        u2 = make_user(username="a_user", sort_order=1)
        db_session.add(u1)
        db_session.add(u2)
        await db_session.commit()

        result = await user_service.list_users(db_session)
        assert result[0].username == "a_user"
        assert result[1].username == "z_user"


class TestCreateUser:
    async def test_creates_user_successfully(self, db_session: AsyncSession) -> None:
        payload = UserCreate(username="newuser", password="password123", repassword="password123")
        user = await user_service.create_user(db_session, payload)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.password_hash != "password123"

    async def test_raises_on_duplicate_username(self, db_session: AsyncSession, saved_user: User) -> None:
        payload = UserCreate(username=saved_user.username, password="password123", repassword="password123")
        with pytest.raises(user_service.UserNameConflictError):
            await user_service.create_user(db_session, payload)

    async def test_raises_on_duplicate_email(self, db_session: AsyncSession) -> None:
        user = make_user(username="firstowner", email="taken@example.com")
        db_session.add(user)
        await db_session.commit()

        payload = UserCreate(
            username="seconduser",
            password="password123",
            repassword="password123",
            email="taken@example.com",
        )
        with pytest.raises(user_service.UserEmailConflictError):
            await user_service.create_user(db_session, payload)


class TestUpdateUser:
    async def test_updates_username(self, db_session: AsyncSession, saved_user: User) -> None:
        payload = UserUpdate(username="updateduser")
        result = await user_service.update_user(db_session, saved_user.public_id, payload)
        assert result.username == "updateduser"

    async def test_updates_email(self, db_session: AsyncSession, saved_user: User) -> None:
        payload = UserUpdate(email="new@example.com")
        result = await user_service.update_user(db_session, saved_user.public_id, payload)
        assert result.email == "new@example.com"

    async def test_updates_password_hash(self, db_session: AsyncSession, saved_user: User) -> None:
        old_hash = saved_user.password_hash
        payload = UserUpdate(password="newpassword123")
        result = await user_service.update_user(db_session, saved_user.public_id, payload)
        assert result.password_hash != old_hash

    async def test_raises_when_user_not_found(self, db_session: AsyncSession) -> None:
        with pytest.raises(user_service.UserNotFoundError):
            await user_service.update_user(db_session, "no-such-id", UserUpdate(nickname="ghost"))

    async def test_raises_on_username_conflict(self, db_session: AsyncSession, saved_user: User) -> None:
        other = make_user(username="otheruser")
        db_session.add(other)
        await db_session.commit()

        payload = UserUpdate(username=saved_user.username)
        with pytest.raises(user_service.UserNameConflictError):
            await user_service.update_user(db_session, other.public_id, payload)


class TestDisableUser:
    async def test_sets_disabled_at(self, db_session: AsyncSession, saved_user: User) -> None:
        result = await user_service.disable_user(db_session, saved_user.public_id)
        assert result.disabled_at is not None
        assert result.is_disabled is True

    async def test_raises_when_user_not_found(self, db_session: AsyncSession) -> None:
        with pytest.raises(user_service.UserNotFoundError):
            await user_service.disable_user(db_session, "no-such-id")


class TestDeleteUser:
    async def test_deletes_user(self, db_session: AsyncSession, saved_user: User) -> None:
        await user_service.delete_user(db_session, saved_user.public_id)
        result = await user_service.get_user_by_public_id(db_session, saved_user.public_id)
        assert result is None

    async def test_raises_when_user_not_found(self, db_session: AsyncSession) -> None:
        with pytest.raises(user_service.UserNotFoundError):
            await user_service.delete_user(db_session, "no-such-id")
