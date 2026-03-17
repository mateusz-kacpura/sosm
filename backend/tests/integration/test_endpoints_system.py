"""Tests for /system/* endpoints — Donut Browser proxy and host management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


class TestSystemStatus:
    async def test_returns_service_statuses(self, client):
        response = await client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"]["status"] == "ok"
        assert "api" in data
        assert data["api"]["status"] == "ok"


class TestListDonutProfiles:
    async def test_returns_profiles_when_donut_available(self, client):
        mock_profiles = {
            "profiles": [
                {"id": "uuid-1", "name": "Profile 1", "browser": "camoufox"},
                {"id": "uuid-2", "name": "Profile 2", "browser": "wayfern"},
            ],
            "total": 2,
        }
        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.list_profiles = AsyncMock(return_value=mock_profiles)
            mock_get_client.return_value = mock_client

            response = await client.get("/api/system/donut/profiles")

        assert response.status_code == 200
        data = response.json()
        assert len(data["profiles"]) == 2
        assert data["profiles"][0]["browser"] == "camoufox"

    async def test_returns_502_when_donut_error(self, client):
        from app.bot.donut_client import DonutBrowserError

        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.list_profiles = AsyncMock(
                side_effect=DonutBrowserError("API unreachable")
            )
            mock_get_client.return_value = mock_client

            response = await client.get("/api/system/donut/profiles")

        assert response.status_code == 502

    async def test_returns_503_when_connection_error(self, client):
        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.list_profiles = AsyncMock(
                side_effect=ConnectionError("refused")
            )
            mock_get_client.return_value = mock_client

            response = await client.get("/api/system/donut/profiles")

        assert response.status_code == 503


class TestRunDonutProfile:
    async def test_starts_profile_and_returns_data(self, client):
        mock_data = {"remote_debugging_port": 9222, "status": "running"}
        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.start_profile_immediate = AsyncMock(return_value=mock_data)
            mock_get_client.return_value = mock_client

            response = await client.post("/api/system/donut/profiles/uuid-1/run")

        assert response.status_code == 200
        assert response.json()["remote_debugging_port"] == 9222

    async def test_returns_502_on_donut_error(self, client):
        from app.bot.donut_client import DonutBrowserError

        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.start_profile_immediate = AsyncMock(
                side_effect=DonutBrowserError("profile not found")
            )
            mock_get_client.return_value = mock_client

            response = await client.post("/api/system/donut/profiles/bad-id/run")

        assert response.status_code == 502


class TestKillDonutProfile:
    async def test_stops_profile(self, client):
        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.stop_profile = AsyncMock()
            mock_get_client.return_value = mock_client

            response = await client.post("/api/system/donut/profiles/uuid-1/kill")

        assert response.status_code == 200
        assert response.json()["detail"] == "Profil zatrzymany"

    async def test_returns_502_on_donut_error(self, client):
        from app.bot.donut_client import DonutBrowserError

        with patch(
            "app.api.system_endpoints._get_donut_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.stop_profile = AsyncMock(
                side_effect=DonutBrowserError("failed")
            )
            mock_get_client.return_value = mock_client

            response = await client.post("/api/system/donut/profiles/uuid-1/kill")

        assert response.status_code == 502


class TestHostStatus:
    async def test_returns_host_status(self, client):
        with patch(
            "app.api.system_endpoints._get_daemon_pid", return_value=None
        ):
            response = await client.get("/api/system/host/status")

        assert response.status_code == 200
        data = response.json()
        assert data["donut_daemon"]["running"] is False
        assert data["donut_daemon"]["pid"] is None

    async def test_returns_running_daemon_with_api(self, client):
        with patch(
            "app.api.system_endpoints._get_daemon_pid", return_value=12345
        ):
            with patch(
                "app.api.system_endpoints._get_donut_client"
            ) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.check_health = AsyncMock(return_value=True)
                mock_get_client.return_value = mock_client

                response = await client.get("/api/system/host/status")

        assert response.status_code == 200
        data = response.json()
        assert data["donut_daemon"]["running"] is True
        assert data["donut_daemon"]["pid"] == 12345
        assert data["donut_daemon"]["api_available"] is True
