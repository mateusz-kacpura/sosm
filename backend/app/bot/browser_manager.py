import asyncio
import logging

import nodriver
import nodriver.cdp.network
import nodriver.cdp.page
import nodriver.cdp.runtime

from app.bot.donut_client import DonutClient
from app.bot.mouse_engine import reset_cursor
from app.core.config import settings

logger = logging.getLogger(__name__)

# Facebook session cookies critical for authentication state.
# Backed up in our DB to survive cloud sync failures after crashes.
_SESSION_COOKIE_NAMES = ("c_user", "xs")

# Wayfern on Linux lacks audio/video hardware access, so navigator.mediaDevices
# is undefined.  Real Chrome always exposes this API even without devices.
# This polyfill mimics a real PC where the user denied media permissions.
_BROWSER_POLYFILLS = """
if (!navigator.mediaDevices) {
    Object.defineProperty(navigator, 'mediaDevices', {
        value: {
            enumerateDevices: () => Promise.resolve([]),
            getUserMedia: () => Promise.reject(
                new DOMException('Permission denied', 'NotAllowedError')
            ),
            getSupportedConstraints: () => ({})
        },
        writable: false,
        configurable: true,
        enumerable: true
    });
}
if (!navigator.deviceMemory) {
    Object.defineProperty(navigator, 'deviceMemory', {
        value: 8,
        writable: false,
        configurable: true,
        enumerable: true
    });
}

// screenX/screenY CDP fix — CDP's Input.dispatchMouseEvent sets
// screenX===clientX and screenY===clientY. Real browsers add
// window position + chrome offsets. Override prototype getters
// to inject realistic offsets when CDP signature is detected.
(function() {
    var patchProto = function(proto) {
        var origX = Object.getOwnPropertyDescriptor(proto, 'screenX');
        var origY = Object.getOwnPropertyDescriptor(proto, 'screenY');
        if (origX && origX.get) {
            Object.defineProperty(proto, 'screenX', {
                get: function() {
                    var val = origX.get.call(this);
                    if (val === this.clientX) {
                        return val + (window.screenX || 0) +
                               (window.outerWidth - window.innerWidth);
                    }
                    return val;
                },
                configurable: true
            });
        }
        if (origY && origY.get) {
            Object.defineProperty(proto, 'screenY', {
                get: function() {
                    var val = origY.get.call(this);
                    if (val === this.clientY) {
                        return val + (window.screenY || 0) +
                               (window.outerHeight - window.innerHeight);
                    }
                    return val;
                },
                configurable: true
            });
        }
    };
    if (typeof MouseEvent !== 'undefined') patchProto(MouseEvent.prototype);
    if (typeof PointerEvent !== 'undefined') patchProto(PointerEvent.prototype);
})();
"""


class BrowserManager:
    """Manages a browser profile lifecycle via Donut Browser + nodriver (CDP).

    Donut Browser handles: C++ level fingerprint spoofing (Wayfern/Camoufox),
    BrowserForge statistical profiles, GPU-accelerated WebGL, proxy management.
    This class handles: connecting to CDP, session cookie backup/restore.

    NOTE: The worker must run on the host (not in Docker) because Donut Browser
    is a desktop app that needs GPU access for authentic WebGL rendering.
    """

    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        self.client = DonutClient(settings.DONUT_API_URL, settings.DONUT_API_TOKEN)
        self._browser: nodriver.Browser | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self, backup_cookies: dict | None = None):
        """Start Donut Browser profile and connect via CDP.

        Args:
            backup_cookies: Optional ``{name: value}`` dict of Facebook session
                cookies to restore before navigation (crash protection).
                Injected via ``Network.setCookies`` before visiting facebook.com.

        Returns:
            nodriver Tab (the active browser tab).
        """
        debugger_address = await self.client.start_profile(self.profile_id)
        host, port = self._parse_debugger_address(debugger_address)

        # Poll CDP endpoint until Donut Browser is ready to accept connections.
        await self._wait_for_cdp(host, port)

        # nodriver's Config.__init__() always calls find_chrome_executable()
        # even when connecting to an existing remote browser via host+port.
        # On systems without Chrome/Chromium this raises FileNotFoundError.
        # Passing any truthy path skips the search; the binary is never
        # launched when host+port are set (nodriver uses connect_existing).
        from app.api.system_endpoints import _donut_binary_path
        self._browser = await nodriver.Browser.create(
            browser_args=["--no-sandbox"],
            browser_executable_path=_donut_binary_path(),
            host=host,
            port=port,
        )
        tab = self._browser.main_tab
        reset_cursor()

        # Inject mediaDevices polyfill: once on current page, once for future navigations.
        # Wayfern on Linux doesn't expose navigator.mediaDevices (no audio/video hw).
        await tab.send(nodriver.cdp.runtime.evaluate(
            expression=_BROWSER_POLYFILLS,
        ))
        await tab.send(nodriver.cdp.page.add_script_to_evaluate_on_new_document(
            source=_BROWSER_POLYFILLS
        ))

        # Restore session cookies from our DB backup (crash protection).
        # If Donut Browser's session didn't persist after a worker crash, we inject
        # c_user + xs BEFORE navigating to facebook.com to avoid checkpoint.
        if backup_cookies:
            cookie_params = []
            for name, value in backup_cookies.items():
                cookie_params.append(
                    nodriver.cdp.network.CookieParam(
                        name=name,
                        value=value,
                        domain=".facebook.com",
                        path="/",
                    )
                )
            await tab.send(nodriver.cdp.network.set_cookies(cookies=cookie_params))
            logger.info("Restored %d backup cookies for profile %s", len(cookie_params), self.profile_id)

        return tab

    async def extract_session_cookies(self, tab) -> dict:
        """Extract critical Facebook cookies via CDP for backup in our DB.

        Returns dict like ``{"c_user": "123456", "xs": "abc..."}``.
        Should be called after each successful action, before stop().
        """
        cookies = await tab.send(nodriver.cdp.network.get_cookies())
        critical = {}
        for cookie in cookies:
            if cookie.name in _SESSION_COOKIE_NAMES:
                critical[cookie.name] = cookie.value
        return critical

    async def stop(self):
        """Disconnect from browser and stop Donut Browser profile."""
        if self._browser:
            try:
                self._browser.stop()
            except Exception as e:
                logger.warning("Error stopping nodriver browser: %s", e)
        await self.client.stop_profile(self.profile_id)

    @staticmethod
    async def _wait_for_cdp(host: str, port: int, timeout: float = 60.0) -> None:
        """Poll the CDP HTTP endpoint until the browser is stably ready.

        Wayfern briefly exposes the CDP port right after launch, then takes
        it down for ~30 s while initializing the BrowserForge fingerprint
        profile.  This method waits for two consecutive successful responses
        (with a 3 s gap) to avoid connecting during the initial false-ready
        window.
        """
        import httpx
        url = f"http://{host}:{port}/json/version"
        deadline = asyncio.get_event_loop().time() + timeout
        consecutive_ok = 0
        while asyncio.get_event_loop().time() < deadline:
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        consecutive_ok += 1
                        if consecutive_ok >= 2:
                            logger.debug("CDP stable at %s:%d", host, port)
                            return
                        # Wait before second check to survive the restart gap.
                        await asyncio.sleep(3)
                        continue
            except (httpx.ConnectError, httpx.ReadTimeout, OSError):
                consecutive_ok = 0
            await asyncio.sleep(1)
        raise RuntimeError(f"CDP endpoint at {host}:{port} not ready after {timeout}s")

    @staticmethod
    def _parse_debugger_address(address: str) -> tuple[str, int]:
        """Parse debugger address like ``127.0.0.1:PORT``.

        Returns:
            Tuple of (host, port).
        """
        host, port_str = address.rsplit(":", 1)
        return host, int(port_str)
