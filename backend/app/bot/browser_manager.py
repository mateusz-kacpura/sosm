import asyncio
import os
import logging

from app.bot.mouse_engine import reset_cursor
from app.core.config import settings

logger = logging.getLogger(__name__)

# Facebook session cookies critical for authentication state.
_SESSION_COOKIE_NAMES = ("c_user", "xs")


class BrowserManager:
    """Manages a browser profile lifecycle via Camoufox (Playwright/Firefox).

    Camoufox handles: C++ level fingerprint spoofing (BrowserForge),
    human-like cursor movement (humanize=True), GPU WebGL rendering.
    This class handles: persistent profile directories, session cookie
    backup/restore, browser startup/shutdown.

    NOTE: The worker must run on the host (not in Docker) because Camoufox
    needs GPU access for authentic WebGL rendering.
    """

    def __init__(self, account_id: int):
        self.account_id = account_id
        self._context = None  # Playwright BrowserContext
        self._camoufox = None  # AsyncCamoufox context manager

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self, backup_cookies: dict | None = None, proxy: dict | None = None):
        """Start Camoufox browser with persistent profile and connect.

        Args:
            backup_cookies: Optional ``{name: value}`` dict of Facebook session
                cookies to restore before navigation (crash protection).
            proxy: Optional Playwright proxy dict
                ``{"server": "http://host:port", "username": "...", "password": "..."}``.

        Returns:
            Playwright Page (the active browser page).
        """
        profile_dir = os.path.join(settings.CAMOUFOX_DIR, str(self.account_id))
        os.makedirs(profile_dir, exist_ok=True)

        # Resolve headless mode
        headless = settings.CAMOUFOX_HEADLESS
        if headless == "true":
            headless = True
        elif headless == "false":
            headless = False
        # else: "virtual" stays as string (Xvfb mode)

        kwargs = dict(
            persistent_context=True,
            user_data_dir=profile_dir,
            humanize=True,
            headless=headless,
        )
        if proxy:
            kwargs["proxy"] = proxy
        if settings.CAMOUFOX_BINARY:
            kwargs["executable_path"] = settings.CAMOUFOX_BINARY

        from camoufox.async_api import AsyncCamoufox
        self._camoufox = AsyncCamoufox(**kwargs)
        self._context = await self._camoufox.__aenter__()

        # Get or create a page
        if self._context.pages:
            page = self._context.pages[0]
        else:
            page = await self._context.new_page()

        reset_cursor()

        # Restore session cookies from our DB backup (crash protection).
        if backup_cookies:
            cookie_params = []
            for name, value in backup_cookies.items():
                cookie_params.append({
                    "name": name,
                    "value": value,
                    "domain": ".facebook.com",
                    "path": "/",
                })
            await self._context.add_cookies(cookie_params)
            logger.info("Restored %d backup cookies for account %s", len(cookie_params), self.account_id)

        logger.info("Camoufox started for account %s, profile: %s", self.account_id, profile_dir)
        return page

    async def extract_session_cookies(self, page) -> dict:
        """Extract critical Facebook cookies for backup in our DB.

        Returns dict like ``{"c_user": "123456", "xs": "abc..."}``.
        Should be called after each successful action, before stop().
        """
        if not self._context:
            return {}
        cookies = await self._context.cookies(["https://www.facebook.com"])
        critical = {}
        for cookie in cookies:
            if cookie["name"] in _SESSION_COOKIE_NAMES:
                critical[cookie["name"]] = cookie["value"]
        return critical

    async def stop(self):
        """Close browser and clean up Camoufox context."""
        if self._camoufox:
            try:
                await self._camoufox.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Error stopping Camoufox browser: %s", e)
            self._camoufox = None
            self._context = None
