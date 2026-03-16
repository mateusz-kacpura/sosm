import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_camoufox_mocks():
    """Create mock AsyncCamoufox context and page."""
    mock_page = AsyncMock()
    mock_page.mouse = AsyncMock()

    mock_context = AsyncMock()
    mock_context.pages = [mock_page]
    mock_context.add_cookies = AsyncMock()
    mock_context.cookies = AsyncMock(return_value=[])

    mock_camoufox = AsyncMock()
    mock_camoufox.__aenter__ = AsyncMock(return_value=mock_context)
    mock_camoufox.__aexit__ = AsyncMock(return_value=None)

    return mock_camoufox, mock_context, mock_page


class TestBrowserManagerStart:
    async def test_creates_camoufox_with_profile_dir(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        with patch("camoufox.async_api.AsyncCamoufox", return_value=mock_camoufox) as mock_cls:
            with patch("app.bot.browser_manager.reset_cursor"):
                from app.bot.browser_manager import BrowserManager
                manager = BrowserManager(42)
                page = await manager.start()

        assert page == mock_page
        # Verify AsyncCamoufox was called with persistent_context and humanize
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["persistent_context"] is True
        assert call_kwargs["humanize"] is True
        assert "42" in call_kwargs["user_data_dir"]

    async def test_restores_backup_cookies(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        with patch("camoufox.async_api.AsyncCamoufox", return_value=mock_camoufox):
            with patch("app.bot.browser_manager.reset_cursor"):
                from app.bot.browser_manager import BrowserManager
                manager = BrowserManager(42)
                backup = {"c_user": "123456", "xs": "abc_token"}
                await manager.start(backup_cookies=backup)

        mock_context.add_cookies.assert_called_once()
        cookies = mock_context.add_cookies.call_args[0][0]
        assert len(cookies) == 2
        assert any(c["name"] == "c_user" for c in cookies)

    async def test_no_cookies_without_backup(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        with patch("camoufox.async_api.AsyncCamoufox", return_value=mock_camoufox):
            with patch("app.bot.browser_manager.reset_cursor"):
                from app.bot.browser_manager import BrowserManager
                manager = BrowserManager(42)
                await manager.start()

        mock_context.add_cookies.assert_not_called()

    async def test_resets_cursor_position(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        with patch("camoufox.async_api.AsyncCamoufox", return_value=mock_camoufox):
            with patch("app.bot.browser_manager.reset_cursor") as mock_reset:
                from app.bot.browser_manager import BrowserManager
                manager = BrowserManager(42)
                await manager.start()

        mock_reset.assert_called_once()


class TestBrowserManagerStop:
    async def test_stops_camoufox(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager(42)
        manager._camoufox = mock_camoufox
        manager._context = mock_context

        await manager.stop()

        mock_camoufox.__aexit__.assert_called_once()


class TestBrowserManagerExtractCookies:
    async def test_extracts_critical_cookies(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        mock_context.cookies = AsyncMock(return_value=[
            {"name": "c_user", "value": "123456"},
            {"name": "xs", "value": "abc_token"},
            {"name": "fr", "value": "tracking"},
        ])

        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager(42)
        manager._context = mock_context
        cookies = await manager.extract_session_cookies(mock_page)

        assert cookies == {"c_user": "123456", "xs": "abc_token"}
        assert "fr" not in cookies


class TestBrowserManagerContextManager:
    async def test_context_manager_lifecycle(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        with patch("camoufox.async_api.AsyncCamoufox", return_value=mock_camoufox):
            with patch("app.bot.browser_manager.reset_cursor"):
                from app.bot.browser_manager import BrowserManager
                async with BrowserManager(42) as manager:
                    assert manager is not None

        mock_camoufox.__aexit__.assert_called_once()
