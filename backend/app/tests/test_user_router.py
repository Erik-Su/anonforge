from __future__ import annotations

import httpx

from app.models.user import User
from app.utils.string_tools import hash_password
from app.utils.time_tools import utc_now


BASE = "/api/users"


def make_create_payload(**kwargs: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "username": "newuser",
        "password": "password123",
        "repassword": "password123",
    }
    defaults.update(kwargs)
    return defaults


class TestListUsers:
    async def test_returns_empty_list(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.get(BASE + "/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_existing_users(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.get(BASE + "/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["username"] == saved_user.username

    async def test_response_excludes_password_hash(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.get(BASE + "/")
        assert "password_hash" not in response.json()[0]


class TestGetUserDetail:
    async def test_returns_user(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.get(f"{BASE}/{saved_user.public_id}")
        assert response.status_code == 200
        assert response.json()["public_id"] == saved_user.public_id

    async def test_returns_404_when_not_found(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.get(f"{BASE}/no-such-id")
        assert response.status_code == 404

    async def test_response_excludes_password_hash(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.get(f"{BASE}/{saved_user.public_id}")
        assert "password_hash" not in response.json()


class TestCreateUser:
    async def test_creates_user(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(BASE + "/", json=make_create_payload())
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "newuser"
        assert "public_id" in data

    async def test_returns_409_on_duplicate_username(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.post(
            BASE + "/", json=make_create_payload(username=saved_user.username)
        )
        assert response.status_code == 409

    async def test_returns_409_on_duplicate_email(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.post(
            BASE + "/",
            json=make_create_payload(username="otherone", email=saved_user.email),
        )
        assert response.status_code == 409

    async def test_returns_422_on_password_mismatch(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(
            BASE + "/",
            json=make_create_payload(password="aaa111bbb", repassword="different"),
        )
        assert response.status_code == 422

    async def test_returns_422_on_missing_fields(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(BASE + "/", json={})
        assert response.status_code == 422

    async def test_response_excludes_password_hash(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(BASE + "/", json=make_create_payload())
        assert "password_hash" not in response.json()


class TestUpdateUser:
    async def test_updates_user(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.put(
            f"{BASE}/{saved_user.public_id}",
            json={"username": "updatedname"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "updatedname"

    async def test_returns_404_when_not_found(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.put(f"{BASE}/no-such-id", json={"nickname": "ghost"})
        assert response.status_code == 404

    async def test_returns_409_on_username_conflict(
        self, api_client: httpx.AsyncClient, saved_user: User, db_session: object
    ) -> None:
        create_resp = await api_client.post(
            BASE + "/",
            json=make_create_payload(username="conflictuser"),
        )
        other_public_id = create_resp.json()["public_id"]

        response = await api_client.put(
            f"{BASE}/{other_public_id}",
            json={"username": saved_user.username},
        )
        assert response.status_code == 409


class TestDisableUser:
    async def test_disables_user(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.patch(f"{BASE}/{saved_user.public_id}/disable")
        assert response.status_code == 200
        assert response.json()["disabled_at"] is not None

    async def test_returns_404_when_not_found(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.patch(f"{BASE}/no-such-id/disable")
        assert response.status_code == 404


class TestDeleteUser:
    async def test_deletes_user(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.delete(f"{BASE}/{saved_user.public_id}")
        assert response.status_code == 204

        get_resp = await api_client.get(f"{BASE}/{saved_user.public_id}")
        assert get_resp.status_code == 404

    async def test_returns_404_when_not_found(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.delete(f"{BASE}/no-such-id")
        assert response.status_code == 404


class TestLoginUser:
    async def test_login_success(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.post(
            BASE + "/login",
            json={"username": saved_user.username, "password": "password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert data["user"]["username"] == saved_user.username

    async def test_returns_401_on_wrong_password(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.post(
            BASE + "/login",
            json={"username": saved_user.username, "password": "wrongpassword"},
        )
        assert response.status_code == 401

    async def test_returns_401_on_nonexistent_user(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(
            BASE + "/login",
            json={"username": "ghostuser", "password": "password123"},
        )
        assert response.status_code == 401

    async def test_returns_403_when_user_disabled(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        await api_client.patch(f"{BASE}/{saved_user.public_id}/disable")

        response = await api_client.post(
            BASE + "/login",
            json={"username": saved_user.username, "password": "password123"},
        )
        assert response.status_code == 403

    async def test_response_excludes_password_hash(self, api_client: httpx.AsyncClient, saved_user: User) -> None:
        response = await api_client.post(
            BASE + "/login",
            json={"username": saved_user.username, "password": "password123"},
        )
        data = response.json()
        assert "password_hash" not in data
        assert "password_hash" not in data.get("user", {})

    async def test_returns_422_on_missing_fields(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(BASE + "/login", json={})
        assert response.status_code == 422

    async def test_returns_422_on_short_password(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.post(
            BASE + "/login",
            json={"username": "someuser", "password": "short"},
        )
        assert response.status_code == 422


class TestAuthRequired:
    """验证受保护路由在无 Bearer token 时返回 401。"""

    async def test_list_users_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.get(BASE + "/")
        assert response.status_code == 401

    async def test_get_user_detail_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.get(f"{BASE}/some-id")
        assert response.status_code == 401

    async def test_create_user_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.post(BASE + "/", json=make_create_payload())
        assert response.status_code == 401

    async def test_update_user_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.put(f"{BASE}/some-id", json={"username": "x"})
        assert response.status_code == 401

    async def test_disable_user_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.patch(f"{BASE}/some-id/disable")
        assert response.status_code == 401

    async def test_delete_user_requires_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.delete(f"{BASE}/some-id")
        assert response.status_code == 401

    async def test_login_does_not_require_auth(self, raw_api_client: httpx.AsyncClient) -> None:
        response = await raw_api_client.post(
            BASE + "/login",
            json={"username": "ghost", "password": "password123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "用户名或密码错误"
