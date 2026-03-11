import pytest
from unittest.mock import patch, MagicMock


async def create_test_account(client, email="fp_test@fb.com"):
    resp = await client.post(
        "/api/accounts/",
        json={"fb_email": email, "fb_password": "pass"},
    )
    return resp.json()["id"]


class TestCreateFingerprintTest:
    async def test_create_success_no_account(self, client):
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            response = await client.post(
                "/api/fingerprint-tests/",
                json={},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "RUNNING"
        assert data["account_id"] is None
        assert data["proxy_url_used"] is None

    async def test_create_success_with_account(self, client):
        account_id = await create_test_account(client)
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            response = await client.post(
                "/api/fingerprint-tests/",
                json={"account_id": account_id},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "RUNNING"
        assert data["account_id"] == account_id

    async def test_create_account_not_found(self, client):
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            response = await client.post(
                "/api/fingerprint-tests/",
                json={"account_id": 9999},
            )
        assert response.status_code == 404


class TestListFingerprintTests:
    async def test_list_empty(self, client):
        response = await client.get("/api/fingerprint-tests/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_returns_created_tests(self, client):
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            await client.post("/api/fingerprint-tests/", json={})
            await client.post("/api/fingerprint-tests/", json={})

        response = await client.get("/api/fingerprint-tests/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2


class TestGetFingerprintTest:
    async def test_get_success(self, client):
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            create_resp = await client.post("/api/fingerprint-tests/", json={})
        test_id = create_resp.json()["id"]

        response = await client.get(f"/api/fingerprint-tests/{test_id}")
        assert response.status_code == 200
        assert response.json()["id"] == test_id

    async def test_get_not_found(self, client):
        response = await client.get("/api/fingerprint-tests/9999")
        assert response.status_code == 404


class TestDeleteFingerprintTest:
    async def test_delete_success(self, client):
        with patch("app.worker.run_fingerprint_test_task") as mock_task:
            mock_task.delay = MagicMock()
            create_resp = await client.post("/api/fingerprint-tests/", json={})
        test_id = create_resp.json()["id"]

        response = await client.delete(f"/api/fingerprint-tests/{test_id}")
        assert response.status_code == 200

        get_resp = await client.get(f"/api/fingerprint-tests/{test_id}")
        assert get_resp.status_code == 404

    async def test_delete_not_found(self, client):
        response = await client.delete("/api/fingerprint-tests/9999")
        assert response.status_code == 404
