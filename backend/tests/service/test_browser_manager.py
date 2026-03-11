import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.browser_manager import BrowserManager


def make_playwright_mocks():
    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.storage_state = AsyncMock()
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_chromium = MagicMock()
    mock_chromium.launch = AsyncMock(return_value=mock_browser)

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium
    mock_pw.stop = AsyncMock()

    return mock_pw, mock_browser, mock_context, mock_page


class TestBrowserManagerStart:
    async def test_launches_chromium(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        with patch("app.bot.browser_manager.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)
            with patch("app.bot.browser_manager.stealth", new_callable=AsyncMock) as mock_stealth:
                with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                    manager = BrowserManager("test@fb.com")
                    page = await manager.start()

        mock_pw.chromium.launch.assert_called_once()
        launch_kwargs = mock_pw.chromium.launch.call_args[1]
        assert launch_kwargs["headless"] is False
        assert "args" in launch_kwargs

        mock_browser.new_context.assert_called_once()
        context_kwargs = mock_browser.new_context.call_args[1]
        assert context_kwargs["viewport"] == {"width": 1920, "height": 1080}
        assert "user_agent" in context_kwargs

        mock_stealth.assert_called_once_with(mock_page)

    async def test_with_proxy(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        with patch("app.bot.browser_manager.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)
            with patch("app.bot.browser_manager.stealth", new_callable=AsyncMock):
                with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                    manager = BrowserManager("test@fb.com", proxy_url="http://proxy:8080")
                    await manager.start()

        launch_kwargs = mock_pw.chromium.launch.call_args[1]
        assert launch_kwargs["proxy"] == {"server": "http://proxy:8080"}

    async def test_loads_session_file(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        with patch("app.bot.browser_manager.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)
            with patch("app.bot.browser_manager.stealth", new_callable=AsyncMock):
                with patch("app.bot.browser_manager.os.path.exists", return_value=True):
                    manager = BrowserManager("test@fb.com", session_file="/tmp/session.json")
                    await manager.start()

        context_kwargs = mock_browser.new_context.call_args[1]
        assert context_kwargs["storage_state"] == "/tmp/session.json"

    async def test_no_session_file(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        with patch("app.bot.browser_manager.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)
            with patch("app.bot.browser_manager.stealth", new_callable=AsyncMock):
                with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                    manager = BrowserManager("test@fb.com")
                    await manager.start()

        context_kwargs = mock_browser.new_context.call_args[1]
        assert "storage_state" not in context_kwargs


class TestBrowserManagerStop:
    async def test_saves_session_and_closes(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        manager = BrowserManager("test@fb.com")
        manager._playwright = mock_pw
        manager._browser = mock_browser
        manager._context = mock_context

        await manager.stop()

        mock_context.storage_state.assert_called_once()
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()


class TestBrowserManagerContextManager:
    async def test_context_manager_lifecycle(self):
        mock_pw, mock_browser, mock_context, mock_page = make_playwright_mocks()

        with patch("app.bot.browser_manager.async_playwright") as mock_async_pw:
            mock_async_pw.return_value.start = AsyncMock(return_value=mock_pw)
            with patch("app.bot.browser_manager.stealth", new_callable=AsyncMock):
                with patch("app.bot.browser_manager.os.path.exists", return_value=False):
                    async with BrowserManager("test@fb.com") as manager:
                        assert manager is not None

        # After exiting, stop should have been called
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
