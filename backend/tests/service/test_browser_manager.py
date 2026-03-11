import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_donut_mocks():
    """Create mock DonutClient and nodriver Browser."""
    mock_client = AsyncMock()
    mock_client.start_profile = AsyncMock(return_value="127.0.0.1:12345")
    mock_client.stop_profile = AsyncMock()

    mock_tab = AsyncMock()
    mock_tab.send = AsyncMock()

    mock_browser = MagicMock()
    mock_browser.main_tab = mock_tab
    mock_browser.stop = MagicMock()

    return mock_client, mock_browser, mock_tab


# Patch _wait_for_cdp in all tests that call start() — no real CDP in unit tests.
_PATCH_CDP_WAIT = patch(
    "app.bot.browser_manager.BrowserManager._wait_for_cdp",
    new_callable=AsyncMock,
)


class TestBrowserManagerStart:
    async def test_connects_to_donut_profile(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        with _PATCH_CDP_WAIT:
            with patch("app.bot.browser_manager.DonutClient", return_value=mock_client):
                with patch("app.bot.browser_manager.nodriver.Browser.create", new_callable=AsyncMock, return_value=mock_browser):
                    from app.bot.browser_manager import BrowserManager
                    manager = BrowserManager("profile_123")
                    tab = await manager.start()

        mock_client.start_profile.assert_called_once_with("profile_123")
        assert tab == mock_tab

    async def test_restores_backup_cookies(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        with _PATCH_CDP_WAIT:
            with patch("app.bot.browser_manager.DonutClient", return_value=mock_client):
                with patch("app.bot.browser_manager.nodriver.Browser.create", new_callable=AsyncMock, return_value=mock_browser):
                    from app.bot.browser_manager import BrowserManager
                    manager = BrowserManager("profile_123")
                    backup = {"c_user": "123456", "xs": "abc_token"}
                    await manager.start(backup_cookies=backup)

        # Network.setCookies should have been called
        mock_tab.send.assert_called()

    async def test_no_cookies_without_backup(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        with _PATCH_CDP_WAIT:
            with patch("app.bot.browser_manager.DonutClient", return_value=mock_client):
                with patch("app.bot.browser_manager.nodriver.Browser.create", new_callable=AsyncMock, return_value=mock_browser):
                    from app.bot.browser_manager import BrowserManager
                    manager = BrowserManager("profile_123")
                    await manager.start()

        # Only the mediaDevices polyfill calls (runtime + page), no cookie restoration
        assert mock_tab.send.call_count == 2

    async def test_resets_cursor_position(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        with _PATCH_CDP_WAIT:
            with patch("app.bot.browser_manager.DonutClient", return_value=mock_client):
                with patch("app.bot.browser_manager.nodriver.Browser.create", new_callable=AsyncMock, return_value=mock_browser):
                    with patch("app.bot.browser_manager.reset_cursor") as mock_reset:
                        from app.bot.browser_manager import BrowserManager
                        manager = BrowserManager("profile_123")
                        await manager.start()

        mock_reset.assert_called_once()


class TestBrowserManagerStop:
    async def test_stops_browser_and_profile(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager("profile_123")
        manager.client = mock_client
        manager._browser = mock_browser

        await manager.stop()

        mock_browser.stop.assert_called_once()
        mock_client.stop_profile.assert_called_once_with("profile_123")


class TestBrowserManagerExtractCookies:
    async def test_extracts_critical_cookies(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        # Mock CDP response with cookie objects
        mock_cookie_cuser = MagicMock()
        mock_cookie_cuser.name = "c_user"
        mock_cookie_cuser.value = "123456"
        mock_cookie_xs = MagicMock()
        mock_cookie_xs.name = "xs"
        mock_cookie_xs.value = "abc_token"
        mock_cookie_other = MagicMock()
        mock_cookie_other.name = "fr"
        mock_cookie_other.value = "tracking"

        mock_tab.send = AsyncMock(return_value=[mock_cookie_cuser, mock_cookie_xs, mock_cookie_other])

        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager("profile_123")
        cookies = await manager.extract_session_cookies(mock_tab)

        assert cookies == {"c_user": "123456", "xs": "abc_token"}
        assert "fr" not in cookies


class TestBrowserManagerContextManager:
    async def test_context_manager_lifecycle(self):
        mock_client, mock_browser, mock_tab = make_donut_mocks()

        with _PATCH_CDP_WAIT:
            with patch("app.bot.browser_manager.DonutClient", return_value=mock_client):
                with patch("app.bot.browser_manager.nodriver.Browser.create", new_callable=AsyncMock, return_value=mock_browser):
                    from app.bot.browser_manager import BrowserManager
                    async with BrowserManager("profile_123") as manager:
                        assert manager is not None

        mock_browser.stop.assert_called_once()
        mock_client.stop_profile.assert_called_once()


class TestBrowserManagerParseDebuggerAddress:
    def test_parse_address(self):
        from app.bot.browser_manager import BrowserManager
        assert BrowserManager._parse_debugger_address("127.0.0.1:12345") == ("127.0.0.1", 12345)

    def test_parse_address_localhost(self):
        from app.bot.browser_manager import BrowserManager
        assert BrowserManager._parse_debugger_address("localhost:9222") == ("localhost", 9222)
