"""Tests for POST /accounts/{id}/create-profile endpoint."""
import pytest
from unittest.mock import AsyncMock, patch


class TestCreateBrowserProfile:
    async def test_creates_profile_and_links_to_account(self, client):
        # Create an account first
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "profile-test@fb.com", "fb_password": "pass123"},
        )
        account_id = resp.json()["id"]

        with patch(
            "app.bot.donut_client.DonutClient"
        ) as MockDonutClient:
            mock_instance = AsyncMock()
            mock_instance.create_profile = AsyncMock(return_value="new-donut-uuid")
            MockDonutClient.return_value = mock_instance

            with patch("app.bot.donut_auto_config.auto_configure", return_value="token"):
                response = await client.post(
                    f"/api/accounts/{account_id}/create-profile"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["profile_id"] == "new-donut-uuid"
        assert data["account_id"] == account_id

        # Verify account now has browser_profile_id
        acc_resp = await client.get("/api/accounts/")
        account = next(a for a in acc_resp.json() if a["id"] == account_id)
        assert account["browser_profile_id"] == "new-donut-uuid"

    async def test_returns_404_for_nonexistent_account(self, client):
        response = await client.post("/api/accounts/99999/create-profile")
        assert response.status_code == 404

    async def test_returns_409_if_profile_already_exists(self, client):
        # Create account with existing profile
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "existing@fb.com", "fb_password": "pass"},
        )
        account_id = resp.json()["id"]

        # First, set the browser_profile_id via a successful create-profile call
        with patch(
            "app.bot.donut_client.DonutClient"
        ) as MockDonutClient:
            mock_instance = AsyncMock()
            mock_instance.create_profile = AsyncMock(return_value="existing-uuid")
            MockDonutClient.return_value = mock_instance

            with patch("app.bot.donut_auto_config.auto_configure", return_value="token"):
                await client.post(f"/api/accounts/{account_id}/create-profile")

        # Try to create again — should fail
        response = await client.post(f"/api/accounts/{account_id}/create-profile")
        assert response.status_code == 409
        assert "already has a profile" in response.json()["detail"]

    async def test_returns_502_when_donut_unavailable(self, client):
        from app.bot.donut_client import DonutBrowserError

        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "donut-fail@fb.com", "fb_password": "pass"},
        )
        account_id = resp.json()["id"]

        with patch(
            "app.bot.donut_client.DonutClient"
        ) as MockDonutClient:
            mock_instance = AsyncMock()
            mock_instance.create_profile = AsyncMock(
                side_effect=DonutBrowserError("API unreachable")
            )
            MockDonutClient.return_value = mock_instance

            with patch("app.bot.donut_auto_config.auto_configure", return_value="token"):
                response = await client.post(
                    f"/api/accounts/{account_id}/create-profile"
                )

        assert response.status_code == 502
        assert "API unreachable" in response.json()["detail"]

    async def test_profile_name_contains_email(self, client):
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "named@fb.com", "fb_password": "pass"},
        )
        account_id = resp.json()["id"]

        with patch(
            "app.bot.donut_client.DonutClient"
        ) as MockDonutClient:
            mock_instance = AsyncMock()
            mock_instance.create_profile = AsyncMock(return_value="uuid-named")
            MockDonutClient.return_value = mock_instance

            with patch("app.bot.donut_auto_config.auto_configure", return_value="token"):
                await client.post(f"/api/accounts/{account_id}/create-profile")

        # Verify the profile was created with name containing email
        call_args = mock_instance.create_profile.call_args
        profile_name = call_args.kwargs.get("name") or call_args[0][0]
        assert "named@fb.com" in profile_name
