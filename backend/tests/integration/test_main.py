import pytest


class TestCorsConfiguration:
    async def test_cors_allows_localhost_3010(self, client):
        response = await client.options(
            "/api/accounts/",
            headers={
                "Origin": "http://localhost:3010",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3010"

    async def test_cors_allows_localhost_3000(self, client):
        response = await client.options(
            "/api/accounts/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    async def test_cors_allows_credentials(self, client):
        response = await client.options(
            "/api/accounts/",
            headers={
                "Origin": "http://localhost:3010",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers["access-control-allow-credentials"] == "true"

    async def test_cors_allows_all_methods(self, client):
        response = await client.options(
            "/api/accounts/",
            headers={
                "Origin": "http://localhost:3010",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        assert response.status_code == 200
        allowed = response.headers["access-control-allow-methods"]
        assert "DELETE" in allowed


class TestAppRouting:
    async def test_api_prefix(self, client):
        response = await client.get("/api/accounts/")
        assert response.status_code == 200

    async def test_root_no_route(self, client):
        response = await client.get("/")
        assert response.status_code in (404, 405)

    async def test_health_outside_api(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
