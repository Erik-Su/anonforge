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
