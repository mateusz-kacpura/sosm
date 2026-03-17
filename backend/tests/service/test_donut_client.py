"""Tests for DonutClient — Donut Browser REST API client."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from app.bot.donut_client import DonutClient, DonutBrowserError


@pytest.fixture
def donut_client():
    return DonutClient(api_url="http://127.0.0.1:10108", api_token="test-token")


class TestStartProfile:
    async def test_returns_debugger_address(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"remote_debugging_port": 9222}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.start_profile("uuid-123")

        assert result == "127.0.0.1:9222"

    async def test_retries_on_500(self, donut_client):
        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        mock_resp_500.text = "already running"

        mock_resp_kill = MagicMock()
        mock_resp_kill.status_code = 200

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.json.return_value = {"remote_debugging_port": 9333}

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=[mock_resp_500, mock_resp_kill, mock_resp_ok]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.start_profile("uuid-123")

        assert result == "127.0.0.1:9333"
        assert mock_client.post.call_count == 3  # 500 + kill + retry

    async def test_raises_on_missing_port(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "running"}  # no port

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(DonutBrowserError, match="No remote_debugging_port"):
                await donut_client.start_profile("uuid-123")

    async def test_raises_on_http_error(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(DonutBrowserError, match="Failed to start"):
                await donut_client.start_profile("uuid-123")


class TestCheckHealth:
    async def test_returns_true_when_healthy(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.check_health()

        assert result is True

    async def test_returns_false_on_connection_error(self, donut_client):
        import httpx

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.check_health()

        assert result is False


class TestCreateProfile:
    async def test_creates_camoufox_profile(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "profile": {"id": "new-uuid-123", "name": "Test", "browser": "camoufox"}
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch.object(
                donut_client,
                "get_installed_browser_version",
                new_callable=AsyncMock,
                return_value="v135.0.1-beta.24",
            ):
                result = await donut_client.create_profile("Test Profile")

        assert result == "new-uuid-123"
        # Verify camoufox_config was sent
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["browser"] == "camoufox"
        assert "camoufox_config" in payload
        assert payload["camoufox_config"]["geoip"] is True
        assert payload["camoufox_config"]["block_webrtc"] is True

    async def test_creates_with_explicit_version(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "profile": {"id": "uuid-456", "name": "Test", "browser": "camoufox"}
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.create_profile(
                "Test", version="v135.0.1-beta.24"
            )

        assert result == "uuid-456"

    async def test_creates_with_os_spoof(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "profile": {"id": "uuid-789", "name": "Test", "browser": "camoufox"}
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch.object(
                donut_client,
                "get_installed_browser_version",
                new_callable=AsyncMock,
                return_value="v135",
            ):
                result = await donut_client.create_profile(
                    "Test", os_spoof="windows"
                )

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["camoufox_config"]["os"] == "windows"

    async def test_raises_on_error(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with patch.object(
                donut_client,
                "get_installed_browser_version",
                new_callable=AsyncMock,
                return_value="v135",
            ):
                with pytest.raises(DonutBrowserError, match="Failed to create"):
                    await donut_client.create_profile("Test")


class TestGetProfile:
    async def test_returns_profile_data(self, donut_client):
        profile_data = {
            "profile": {
                "id": "uuid-123",
                "browser": "camoufox",
                "camoufox_config": {"fingerprint": '{"key": "val"}'},
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = profile_data

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            result = await donut_client.get_profile("uuid-123")

        assert result["id"] == "uuid-123"
        assert result["browser"] == "camoufox"

    async def test_raises_on_not_found(self, donut_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "not found"

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            with pytest.raises(DonutBrowserError, match="Failed to get"):
                await donut_client.get_profile("bad-uuid")


class TestGetInstalledBrowserVersion:
    async def test_reads_version_from_disk(self, donut_client, tmp_path):
        data_dir = tmp_path / "DonutBrowser"
        (data_dir / "data").mkdir(parents=True)
        db_file = data_dir / "data" / "downloaded_browsers.json"
        db_file.write_text(json.dumps({
            "browsers": {
                "camoufox": {
                    "v135.0.1-beta.24": {
                        "browser": "camoufox",
                        "version": "v135.0.1-beta.24",
                        "file_path": "/fake/path",
                    }
                }
            }
        }))

        with patch(
            "app.bot.donut_auto_config._donut_data_dir",
            return_value=str(data_dir),
        ):
            result = await donut_client.get_installed_browser_version("camoufox")

        assert result == "v135.0.1-beta.24"

    async def test_raises_when_no_browser_installed(self, donut_client, tmp_path):
        data_dir = tmp_path / "DonutBrowser"
        (data_dir / "data").mkdir(parents=True)
        db_file = data_dir / "data" / "downloaded_browsers.json"
        db_file.write_text(json.dumps({"browsers": {}}))

        with patch(
            "app.bot.donut_auto_config._donut_data_dir",
            return_value=str(data_dir),
        ):
            with pytest.raises(DonutBrowserError, match="No camoufox browser installed"):
                await donut_client.get_installed_browser_version("camoufox")

    async def test_raises_when_file_missing(self, donut_client, tmp_path):
        data_dir = tmp_path / "DonutBrowser"
        data_dir.mkdir(parents=True)
        # No downloaded_browsers.json

        with patch(
            "app.bot.donut_auto_config._donut_data_dir",
            return_value=str(data_dir),
        ):
            with pytest.raises(DonutBrowserError, match="No camoufox browser installed"):
                await donut_client.get_installed_browser_version("camoufox")
