import pytest


class TestCreateAccount:
    async def test_create_account_success(self, client):
        response = await client.post(
            "/api/accounts/",
            json={
                "fb_email": "test@fb.com",
                "fb_password": "secret123",
                "proxy_url": "http://proxy:8080",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["fb_email"] == "test@fb.com"
        assert data["proxy_url"] == "http://proxy:8080"
        assert "id" in data
        assert "created_at" in data

    async def test_create_account_minimal(self, client):
        response = await client.post(
            "/api/accounts/",
            json={"fb_email": "minimal@fb.com", "fb_password": "pass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["proxy_url"] is None

    async def test_create_account_missing_email(self, client):
        response = await client.post(
            "/api/accounts/",
            json={"fb_password": "pass"},
        )
        assert response.status_code == 422

    async def test_create_account_missing_password(self, client):
        response = await client.post(
            "/api/accounts/",
            json={"fb_email": "test@fb.com"},
        )
        assert response.status_code == 422

    async def test_create_account_password_not_in_response(self, client):
        response = await client.post(
            "/api/accounts/",
            json={"fb_email": "nopass@fb.com", "fb_password": "secret"},
        )
        data = response.json()
        assert "fb_password" not in data


class TestListAccounts:
    async def test_list_accounts_empty(self, client):
        response = await client.get("/api/accounts/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_accounts_returns_all(self, client):
        for i in range(3):
            await client.post(
                "/api/accounts/",
                json={"fb_email": f"user{i}@fb.com", "fb_password": "pass"},
            )

        response = await client.get("/api/accounts/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_list_accounts_does_not_expose_password(self, client):
        await client.post(
            "/api/accounts/",
            json={"fb_email": "hidden@fb.com", "fb_password": "secret"},
        )

        response = await client.get("/api/accounts/")
        for account in response.json():
            assert "fb_password" not in account
