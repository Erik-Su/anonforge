from __future__ import annotations

import pytest

from app.models.user import User
from app.utils.time_tools import utc_now


class TestUserModelProperties:
    def test_tablename(self) -> None:
        assert User.__tablename__ == "af_user"  # type: ignore[attr-defined]

    def test_defaults_to_active(self) -> None:
        user = User(username="u", password_hash="h")
        assert user.is_active is True
        assert user.is_disabled is False

    def test_is_disabled_when_disabled_at_is_set(self) -> None:
        user = User(username="u", password_hash="h", disabled_at=utc_now())
        assert user.is_disabled is True
        assert user.is_active is False

    def test_last_login_at_defaults_to_none(self) -> None:
        user = User(username="u", password_hash="h")
        assert user.last_login_at is None

    def test_public_id_auto_generated(self) -> None:
        user = User(username="u", password_hash="h")
        assert user.public_id is not None
        assert len(user.public_id) == 36

    def test_two_users_have_different_public_ids(self) -> None:
        u1 = User(username="u1", password_hash="h")
        u2 = User(username="u2", password_hash="h")
        assert u1.public_id != u2.public_id


class TestUserModelMethods:
    async def test_disable_sets_disabled_at(self) -> None:
        user = User(username="u", password_hash="h")
        assert user.disabled_at is None
        await user.disable()
        assert user.disabled_at is not None

    async def test_disable_is_idempotent(self) -> None:
        user = User(username="u", password_hash="h")
        await user.disable()
        await user.disable()
        assert user.disabled_at is not None
        assert user.is_disabled is True

    async def test_enable_clears_disabled_at(self) -> None:
        user = User(username="u", password_hash="h", disabled_at=utc_now())
        await user.enable()
        assert user.disabled_at is None

    async def test_enable_on_active_user_is_safe(self) -> None:
        user = User(username="u", password_hash="h")
        await user.enable()
        assert user.disabled_at is None

    async def test_update_last_login_sets_timestamp(self) -> None:
        user = User(username="u", password_hash="h")
        assert user.last_login_at is None
        await user.update_last_login()
        assert user.last_login_at is not None

    async def test_update_last_login_updates_existing_timestamp(self) -> None:
        from datetime import timedelta
        old_time = utc_now() - timedelta(seconds=1)
        user = User(username="u", password_hash="h", last_login_at=old_time)
        await user.update_last_login()
        assert user.last_login_at is not None
        assert user.last_login_at > old_time
