import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

FAKE_PROFILE_ID = "test-uuid-1234"
FAKE_PROFILE_DATA = {
    "id": FAKE_PROFILE_ID,
    "browser": "camoufox",
    "camoufox_config": {
        "fingerprint": (
            '{"navigator.userAgent": "Mozilla/5.0 Test",'
            ' "webGl:vendor": "Google Inc. (NVIDIA)",'
            ' "webGl:renderer": "ANGLE (GTX 980 D3D11)",'
            ' "canvas:aaOffset": 17,'
            ' "fonts": ["Arial", "Verdana"],'
            ' "timezone": "Asia/Bangkok"}'
        ),
    },
}
FAKE_BINARY = "/fake/camoufox-bin"


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


def _patch_browser_deps(mock_camoufox):
    """Return stacked patches for BrowserManager dependencies."""
    return [
        patch("app.bot.browser_manager.AsyncCamoufox", return_value=mock_camoufox),
        patch("app.bot.browser_manager.reset_cursor"),
        patch(
            "app.bot.browser_manager.BrowserManager._load_profile_data",
            new_callable=AsyncMock,
            return_value=FAKE_PROFILE_DATA,
        ),
        patch(
            "app.bot.browser_manager._find_camoufox_binary",
            return_value=FAKE_BINARY,
        ),
    ]


class TestBrowserManagerStart:
    async def test_creates_camoufox_with_real_config(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        patches = _patch_browser_deps(mock_camoufox)

        with patches[0] as mock_cls, patches[1], patches[2], patches[3]:
            from app.bot.browser_manager import BrowserManager
            manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
            page = await manager.start()

        assert page == mock_page
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["persistent_context"] is True
        assert call_kwargs["humanize"] is True
        assert call_kwargs["os"] == "linux"
        assert call_kwargs["webgl_config"] == (
            "NVIDIA Corporation", "NVIDIA GeForce RTX 4050 Laptop GPU/PCIe/SSE2"
        )
        assert call_kwargs["i_know_what_im_doing"] is True

        config = call_kwargs["config"]
        # Real system values
        assert config["navigator.hardwareConcurrency"] == os.cpu_count()
        assert config["navigator.language"] == "en-US"
        assert config["screen.width"] == 1920
        assert config["screen.height"] == 1080
        assert config["mediaDevices:enabled"] is True

        # WebGL handled via webgl_config, not config dict
        assert "webGl:vendor" not in config
        assert "webGl:renderer" not in config

        # Safe BrowserForge values kept
        assert config["canvas:aaOffset"] == 17
        assert config["timezone"] == "Asia/Bangkok"
        # Fonts must be Linux-native (not BrowserForge's Windows fonts)
        assert "Liberation Sans" in config["fonts"]
        assert "DejaVu Sans" in config["fonts"]

        # BrowserForge navigator.userAgent must NOT be in config
        # (let Camoufox generate from os='linux')
        assert "navigator.userAgent" not in config

    async def test_raises_without_profile_id(self):
        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager(42)

        with pytest.raises(ValueError, match="no Donut Browser profile ID"):
            await manager.start()

    async def test_restores_backup_cookies(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        patches = _patch_browser_deps(mock_camoufox)

        with patches[0], patches[1], patches[2], patches[3]:
            from app.bot.browser_manager import BrowserManager
            manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
            backup = {"c_user": "123456", "xs": "abc_token"}
            await manager.start(backup_cookies=backup)

        mock_context.add_cookies.assert_called_once()
        cookies = mock_context.add_cookies.call_args[0][0]
        assert len(cookies) == 2
        assert any(c["name"] == "c_user" for c in cookies)

    async def test_no_cookies_without_backup(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        patches = _patch_browser_deps(mock_camoufox)

        with patches[0], patches[1], patches[2], patches[3]:
            from app.bot.browser_manager import BrowserManager
            manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
            await manager.start()

        mock_context.add_cookies.assert_not_called()

    async def test_resets_cursor_position(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        patches = _patch_browser_deps(mock_camoufox)

        with patches[0], patches[1] as mock_reset, patches[2], patches[3]:
            from app.bot.browser_manager import BrowserManager
            manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
            await manager.start()

        mock_reset.assert_called_once()


class TestBuildRealConfig:
    def test_keeps_safe_browserforge_keys(self):
        from app.bot.browser_manager import _build_real_config
        bf = {
            "canvas:aaOffset": 42,
            "canvas:aaCapOffset": True,
            "fonts": ["Arial"],
            "fonts:spacing_seed": 12345,
            "timezone": "Europe/Warsaw",
            "geolocation:latitude": 52.23,
        }
        result = _build_real_config(bf)
        assert result["canvas:aaOffset"] == 42
        # fonts:spacing_seed is kept but fonts list is replaced with Linux fonts
        assert result["fonts:spacing_seed"] == 12345
        assert result["timezone"] == "Europe/Warsaw"
        assert result["geolocation:latitude"] == 52.23

    def test_replaces_browserforge_fonts_with_linux(self):
        from app.bot.browser_manager import _build_real_config
        bf = {"fonts": ["Segoe UI", "Calibri", "Arial", "Verdana"]}
        result = _build_real_config(bf)
        # Must use Linux-native fonts, not BrowserForge's Windows fonts
        assert "Liberation Sans" in result["fonts"]
        assert "DejaVu Sans" in result["fonts"]
        assert "Segoe UI" not in result["fonts"]
        assert "Calibri" not in result["fonts"]

    def test_excludes_webgl_from_config(self):
        """WebGL is handled via webgl_config kwarg, not config dict."""
        from app.bot.browser_manager import _build_real_config
        bf = {
            "webGl:vendor": "Google Inc. (NVIDIA)",
            "webGl:renderer": "ANGLE (GTX 980)",
            "webGl:parameters": {"key": "val"},
            "webGl2:supportedExtensions": ["ext1"],
        }
        result = _build_real_config(bf)
        # WebGL keys should NOT be in config — handled by webgl_config param
        assert "webGl:vendor" not in result
        assert "webGl:renderer" not in result
        assert "webGl:parameters" not in result
        assert "webGl2:supportedExtensions" not in result

    def test_removes_navigator_ua_and_platform(self):
        from app.bot.browser_manager import _build_real_config
        bf = {
            "navigator.userAgent": "Mozilla/5.0 (Windows NT 10.0; ...)",
            "navigator.platform": "Win32",
            "navigator.oscpu": "Windows NT 10.0; Win64; x64",
            "navigator.appVersion": "5.0 (Windows)",
        }
        result = _build_real_config(bf)
        assert "navigator.userAgent" not in result
        assert "navigator.platform" not in result
        assert "navigator.oscpu" not in result
        assert "navigator.appVersion" not in result

    def test_sets_real_hardware_values(self):
        from app.bot.browser_manager import _build_real_config
        result = _build_real_config({})
        assert result["navigator.hardwareConcurrency"] == os.cpu_count()
        assert result["screen.width"] == 1920
        assert result["screen.height"] == 1080
        assert result["navigator.language"] == "en-US"
        assert result["mediaDevices:enabled"] is True

    def test_empty_browserforge_returns_real_config(self):
        from app.bot.browser_manager import _build_real_config
        result = _build_real_config({})
        assert len(result) > 0
        assert "navigator.hardwareConcurrency" in result
        assert "screen.width" in result


class TestBrowserManagerStop:
    async def test_stops_camoufox(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()

        from app.bot.browser_manager import BrowserManager
        manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
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
        manager = BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID)
        manager._context = mock_context
        cookies = await manager.extract_session_cookies(mock_page)

        assert cookies == {"c_user": "123456", "xs": "abc_token"}
        assert "fr" not in cookies


class TestBrowserManagerContextManager:
    async def test_context_manager_lifecycle(self):
        mock_camoufox, mock_context, mock_page = make_camoufox_mocks()
        patches = _patch_browser_deps(mock_camoufox)

        with patches[0], patches[1], patches[2], patches[3]:
            from app.bot.browser_manager import BrowserManager
            async with BrowserManager(42, donut_profile_id=FAKE_PROFILE_ID) as manager:
                assert manager is not None

        mock_camoufox.__aexit__.assert_called_once()
