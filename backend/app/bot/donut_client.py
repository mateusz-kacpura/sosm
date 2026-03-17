import asyncio
import random
import logging

import httpx

logger = logging.getLogger(__name__)


class DonutBrowserError(Exception):
    """Raised when Donut Browser Local API returns an error."""


class DonutClient:
    """Async HTTP client for Donut Browser Local REST API (port 10108).

    Donut Browser handles: C++ level fingerprint spoofing (Wayfern/Camoufox),
    BrowserForge statistical profiles, GPU-accelerated WebGL rendering,
    proxy management, session persistence.

    This client handles: starting/stopping browser profiles via REST API
    and extracting the CDP debugging port for nodriver connection.

    The API requires Bearer token authentication (generated in Donut Browser
    Settings after enabling the API feature).
    """

    def __init__(self, api_url: str = "http://127.0.0.1:10108", api_token: str = ""):
        self.api_url = api_url.rstrip("/")
        self.api_token = api_token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_token}"}

    async def start_profile(self, profile_id: str) -> str:
        """Start a Donut Browser profile and return its CDP debugger address.

        Sends POST /v1/profiles/{id}/run to the Donut Browser daemon.
        The daemon launches the Wayfern (Chromium) or Camoufox (Firefox) engine
        with a remote debugging port for CDP connection.

        Applies a random jitter (1-5 s) before the request to avoid
        overwhelming the API when many Celery tasks fire simultaneously.

        Returns:
            Debugger address in ``host:port`` format (e.g. ``127.0.0.1:9222``).
        """
        jitter = random.uniform(1.0, 5.0)
        logger.debug("Donut start_profile(%s): jitter %.1fs", profile_id, jitter)
        await asyncio.sleep(jitter)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.api_url}/v1/profiles/{profile_id}/run",
                headers=self._headers(),
                json={},
            )

            # Donut Browser returns 500 if profile is already running.
            # Kill it and retry once.
            if resp.status_code == 500:
                logger.warning("Donut profile %s may already be running, killing and retrying", profile_id)
                await client.post(
                    f"{self.api_url}/v1/profiles/{profile_id}/kill",
                    headers=self._headers(),
                )
                await asyncio.sleep(2)
                resp = await client.post(
                    f"{self.api_url}/v1/profiles/{profile_id}/run",
                    headers=self._headers(),
                    json={},
                )

        if resp.status_code >= 400:
            raise DonutBrowserError(
                f"Failed to start profile {profile_id}: HTTP {resp.status_code} {resp.text}"
            )

        data = resp.json()
        port = data.get("remote_debugging_port")
        if not port:
            raise DonutBrowserError(
                f"No remote_debugging_port in response for {profile_id}: {data}"
            )

        debugger_address = f"127.0.0.1:{port}"
        logger.info("Donut profile %s started, CDP: %s", profile_id, debugger_address)
        return debugger_address

    async def start_profile_immediate(self, profile_id: str) -> dict:
        """Start a profile WITHOUT jitter delay. Returns full API response.

        For use from the system management UI where instant feedback is needed,
        not from Celery tasks (use start_profile() for those).
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.api_url}/v1/profiles/{profile_id}/run",
                headers=self._headers(),
                json={},
            )

            if resp.status_code == 500:
                logger.warning("Donut profile %s may already be running, killing and retrying", profile_id)
                await client.post(
                    f"{self.api_url}/v1/profiles/{profile_id}/kill",
                    headers=self._headers(),
                )
                await asyncio.sleep(2)
                resp = await client.post(
                    f"{self.api_url}/v1/profiles/{profile_id}/run",
                    headers=self._headers(),
                    json={},
                )

        if resp.status_code >= 400:
            raise DonutBrowserError(
                f"Failed to start profile {profile_id}: HTTP {resp.status_code} {resp.text}"
            )

        data = resp.json()
        logger.info("Donut profile %s started (immediate), data: %s", profile_id, data)
        return data

    async def list_profiles(self) -> dict:
        """List all Donut Browser profiles.

        Returns:
            Dict with 'profiles' list and 'total' count.
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.api_url}/v1/profiles",
                headers=self._headers(),
            )

        if resp.status_code >= 400:
            raise DonutBrowserError(
                f"Failed to list profiles: HTTP {resp.status_code} {resp.text}"
            )
        return resp.json()

    async def check_health(self) -> bool:
        """Check if Donut Browser daemon API is reachable.

        Returns:
            True if the API responds successfully, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    f"{self.api_url}/v1/profiles",
                    headers=self._headers(),
                )
            return resp.status_code < 500
        except (httpx.ConnectError, httpx.ReadTimeout, OSError):
            return False

    async def create_profile(
        self,
        name: str,
        browser: str = "camoufox",
        version: str | None = None,
        os_spoof: str | None = None,
    ) -> str:
        """Create a new Donut Browser profile with a unique fingerprint.

        Args:
            name: Profile display name.
            browser: Browser engine — "camoufox" or "wayfern".
            version: Browser version string. If None, auto-detects from
                Donut's downloaded browsers.
            os_spoof: OS to emulate — "windows", "macos", "linux", or None.

        Returns:
            The UUID of the newly created profile.
        """
        if not version:
            version = await self.get_installed_browser_version(browser)

        payload: dict = {
            "name": name,
            "browser": browser,
            "version": version,
        }

        if browser == "camoufox":
            camou_config: dict = {
                "geoip": True,
                "block_webrtc": True,
            }
            if os_spoof:
                camou_config["os"] = os_spoof
            payload["camoufox_config"] = camou_config

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_url}/v1/profiles",
                headers=self._headers(),
                json=payload,
            )

        if resp.status_code >= 400:
            raise DonutBrowserError(
                f"Failed to create profile '{name}': HTTP {resp.status_code} {resp.text}"
            )

        data = resp.json()
        profile_id = data["profile"]["id"]
        logger.info("Donut %s profile created: %s (name=%s)", browser, profile_id, name)
        return profile_id

    async def get_installed_browser_version(self, browser: str = "camoufox") -> str:
        """Get the installed version of a browser engine from Donut.

        Reads downloaded_browsers.json to find installed versions.

        Raises:
            DonutBrowserError: If no version of the browser is installed.
        """
        import json
        import os

        # Try to find from Donut data dir on disk
        from app.bot.donut_auto_config import _donut_data_dir
        data_dir = _donut_data_dir()
        db_file = os.path.join(data_dir, "data", "downloaded_browsers.json")

        if os.path.isfile(db_file):
            with open(db_file) as f:
                db = json.load(f)
            versions = db.get("browsers", {}).get(browser, {})
            if versions:
                return sorted(versions.keys())[-1]

        raise DonutBrowserError(
            f"No {browser} browser installed in Donut Browser. "
            f"Download it from Donut Browser settings first."
        )

    async def delete_profile(self, profile_id: str) -> None:
        """Delete a Donut Browser profile and its data permanently."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{self.api_url}/v1/profiles/{profile_id}",
                headers=self._headers(),
            )

        if resp.status_code >= 400:
            logger.warning(
                "Donut delete_profile(%s) returned HTTP %d: %s",
                profile_id, resp.status_code, resp.text,
            )
        else:
            logger.info("Donut profile %s deleted", profile_id)

    async def get_profile(self, profile_id: str) -> dict:
        """Get full profile data including camoufox_config.

        Returns:
            Dict with profile fields (BrowserProfile structure).
        """
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.api_url}/v1/profiles/{profile_id}",
                headers=self._headers(),
            )

        if resp.status_code >= 400:
            raise DonutBrowserError(
                f"Failed to get profile {profile_id}: HTTP {resp.status_code} {resp.text}"
            )
        data = resp.json()
        return data.get("profile", data)

    async def stop_profile(self, profile_id: str) -> None:
        """Stop (kill) a Donut Browser profile.

        Sends POST /v1/profiles/{id}/kill to terminate the browser process
        and release resources.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_url}/v1/profiles/{profile_id}/kill",
                headers=self._headers(),
            )

        if resp.status_code >= 400:
            logger.warning(
                "Donut stop_profile(%s) returned HTTP %d: %s",
                profile_id, resp.status_code, resp.text,
            )
        else:
            logger.info("Donut profile %s stopped", profile_id)
