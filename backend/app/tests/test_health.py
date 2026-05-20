from __future__ import annotations

import httpx


class TestMainApi:
    async def test_health_endpoint_returns_ok(self, api_client: httpx.AsyncClient) -> None:
        response = await api_client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
