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

    async def test_list_accounts_includes_fanpages(self, client):
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "withfp@fb.com", "fb_password": "pass"},
        )
        account_id = resp.json()["id"]

        await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": "https://facebook.com/myfp", "fanpage_name": "My FP"},
        )

        response = await client.get("/api/accounts/")
        account = next(a for a in response.json() if a["id"] == account_id)
        assert "fanpages" in account
        assert len(account["fanpages"]) == 1
        assert account["fanpages"][0]["fanpage_url"] == "https://facebook.com/myfp"


class TestFanpageCRUD:
    async def _create_account(self, client) -> int:
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "fanpage_test@fb.com", "fb_password": "pass"},
        )
        return resp.json()["id"]

    async def test_add_fanpage_success(self, client):
        account_id = await self._create_account(client)
        response = await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": "https://facebook.com/page1", "fanpage_name": "Page 1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["fanpage_url"] == "https://facebook.com/page1"
        assert data["fanpage_name"] == "Page 1"
        assert data["account_id"] == account_id
        assert "id" in data
        assert "created_at" in data

    async def test_add_fanpage_minimal(self, client):
        account_id = await self._create_account(client)
        response = await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": "https://facebook.com/page2"},
        )
        assert response.status_code == 200
        assert response.json()["fanpage_name"] is None

    async def test_add_fanpage_nonexistent_account(self, client):
        response = await client.post(
            "/api/accounts/99999/fanpages",
            json={"fanpage_url": "https://facebook.com/page1"},
        )
        assert response.status_code == 404

    async def test_add_fanpage_duplicate(self, client):
        account_id = await self._create_account(client)
        url = "https://facebook.com/duplicate"
        await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": url},
        )
        response = await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": url},
        )
        assert response.status_code == 409

    async def test_list_fanpages(self, client):
        account_id = await self._create_account(client)
        for i in range(3):
            await client.post(
                f"/api/accounts/{account_id}/fanpages",
                json={"fanpage_url": f"https://facebook.com/fp{i}"},
            )
        response = await client.get(f"/api/accounts/{account_id}/fanpages")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_list_fanpages_empty(self, client):
        account_id = await self._create_account(client)
        response = await client.get(f"/api/accounts/{account_id}/fanpages")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_fanpages_nonexistent_account(self, client):
        response = await client.get("/api/accounts/99999/fanpages")
        assert response.status_code == 404

    async def test_delete_fanpage(self, client):
        account_id = await self._create_account(client)
        resp = await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": "https://facebook.com/todelete"},
        )
        fanpage_id = resp.json()["id"]

        response = await client.delete(f"/api/accounts/{account_id}/fanpages/{fanpage_id}")
        assert response.status_code == 200
        assert response.json()["detail"] == "Fanpage deleted"

        # Verify it's gone
        list_resp = await client.get(f"/api/accounts/{account_id}/fanpages")
        assert len(list_resp.json()) == 0

    async def test_delete_fanpage_not_found(self, client):
        account_id = await self._create_account(client)
        response = await client.delete(f"/api/accounts/{account_id}/fanpages/99999")
        assert response.status_code == 404

    async def test_delete_fanpage_wrong_account(self, client):
        account_id = await self._create_account(client)
        resp = await client.post(
            f"/api/accounts/{account_id}/fanpages",
            json={"fanpage_url": "https://facebook.com/wrong"},
        )
        fanpage_id = resp.json()["id"]

        # Try to delete from a different (nonexistent) account
        response = await client.delete(f"/api/accounts/99999/fanpages/{fanpage_id}")
        assert response.status_code == 404
