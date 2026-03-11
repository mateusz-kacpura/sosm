import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.browser_manager import BrowserManager


def make_camoufox_mocks():
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.storage_state = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_browser)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    return mock_cm, mock_browser, mock_context, mock_page


class TestBrowserManagerStart:
    async def test_launches_camoufox(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm):
            with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                manager = BrowserManager("test@fb.com")
                page = await manager.start()

        mock_browser.new_context.assert_called_once()
        mock_context.new_page.assert_called_once()

    async def test_with_proxy(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm) as mock_camoufox_cls:
            with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                manager = BrowserManager("test@fb.com", proxy_url="http://proxy:8080")
                await manager.start()

        camoufox_kwargs = mock_camoufox_cls.call_args[1]
        assert camoufox_kwargs["proxy"] == {"server": "http://proxy:8080"}

    async def test_loads_session_file(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm):
            with patch("app.bot.browser_manager.os.path.exists", return_value=True):
                manager = BrowserManager("test@fb.com", session_file="/tmp/session.json")
                await manager.start()

        context_kwargs = mock_browser.new_context.call_args[1]
        assert context_kwargs["storage_state"] == "/tmp/session.json"

    async def test_no_session_file(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm):
            with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                manager = BrowserManager("test@fb.com")
                await manager.start()

        context_kwargs = mock_browser.new_context.call_args[1]
        assert "storage_state" not in context_kwargs

    async def test_headless_and_geoip_enabled(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm) as mock_camoufox_cls:
            with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                manager = BrowserManager("test@fb.com")
                await manager.start()

        camoufox_kwargs = mock_camoufox_cls.call_args[1]
        assert camoufox_kwargs["headless"] == "virtual"
        assert camoufox_kwargs["geoip"] is True
        assert camoufox_kwargs["block_webgl"] is False
        assert camoufox_kwargs["os"] == "linux"
        assert camoufox_kwargs["config"]["navigator.maxTouchPoints"] == 0
        assert camoufox_kwargs["config"]["navigator.hardwareConcurrency"] == 8


class TestBrowserManagerStop:
    async def test_saves_session_and_closes(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        manager = BrowserManager("test@fb.com")
        manager._camoufox_cm = mock_cm
        manager._browser = mock_browser
        manager._context = mock_context

        with patch("app.bot.browser_manager.os.makedirs"):
            await manager.stop()

        mock_context.storage_state.assert_called_once()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_cm.__aexit__.assert_called_once()


class TestBrowserManagerContextManager:
    async def test_context_manager_lifecycle(self):
        mock_cm, mock_browser, mock_context, mock_page = make_camoufox_mocks()

        with patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_cm):
            with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                with patch("app.bot.browser_manager.os.makedirs"):
                    async with BrowserManager("test@fb.com") as manager:
                        assert manager is not None

        # After exiting, stop should have been called
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
