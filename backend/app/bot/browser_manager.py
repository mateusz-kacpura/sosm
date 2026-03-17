"""Browser manager — launches Camoufox using Donut Browser's profile & binary.

Donut Browser manages: profile creation, fingerprint generation (BrowserForge),
proxy settings, and persistent browser data on disk.

SOSM reads the Donut profile's fingerprint config and launches Camoufox
directly via the Python `camoufox` package (AsyncCamoufox), pointing at
Donut's binary and profile directory.  This avoids modifying Donut Browser
and lets SOSM control the automation lifecycle (login, publish, workflow).

The worker runs on the host because Camoufox needs GPU access for
authentic WebGL rendering.
"""

import asyncio
import json
import logging
import os

from camoufox.async_api import AsyncCamoufox
from camoufox import DefaultAddons

from app.bot.donut_client import DonutClient, DonutBrowserError
from app.bot.donut_auto_config import auto_configure
from app.bot.mouse_engine import reset_cursor
from app.core.config import settings

logger = logging.getLogger(__name__)

# Facebook session cookies critical for authentication state.
_SESSION_COOKIE_NAMES = ("c_user", "xs")

# WebGL vendor/renderer pair from Camoufox's WebGL database.
# Must match an exact entry in webgl_data.db (vendor, renderer columns).
# This selects a COHERENT fingerprint (vendor + renderer + 147 GL params
# + extensions) that the browser uses consistently.
# "GTX 980/PCIe/SSE2" is the closest NVIDIA entry without the suspicious
# ", or similar" suffix that reveals spoofing.
_WEBGL_CONFIG = ("NVIDIA Corporation", "NVIDIA GeForce RTX 4050 Laptop GPU/PCIe/SSE2")


def _donut_data_dir() -> str:
    """Return Donut Browser data directory (respects DONUT_DATA_DIR setting)."""
    if settings.DONUT_DATA_DIR:
        return settings.DONUT_DATA_DIR
    return os.path.join(
        os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
        "DonutBrowser",
    )


def _find_camoufox_binary() -> str:
    """Find Camoufox binary from Donut Browser's downloaded browsers.

    Reads downloaded_browsers.json to find the installed Camoufox version,
    then returns path to camoufox-bin.
    """
    data_dir = _donut_data_dir()
    db_file = os.path.join(data_dir, "data", "downloaded_browsers.json")

    if not os.path.isfile(db_file):
        raise DonutBrowserError(
            f"Donut Browser downloaded_browsers.json not found at {db_file}. "
            f"Install Camoufox in Donut Browser first."
        )

    with open(db_file) as f:
        db = json.load(f)

    camoufox_versions = db.get("browsers", {}).get("camoufox", {})
    if not camoufox_versions:
        raise DonutBrowserError(
            "No Camoufox browser installed in Donut Browser. "
            "Download Camoufox from Donut Browser settings."
        )

    # Use the latest version
    version_key = sorted(camoufox_versions.keys())[-1]
    entry = camoufox_versions[version_key]
    binary_dir = entry.get("file_path", "")
    binary_path = os.path.join(binary_dir, "camoufox-bin")

    if not os.path.isfile(binary_path):
        raise DonutBrowserError(
            f"Camoufox binary not found at {binary_path}. "
            f"Re-download Camoufox in Donut Browser."
        )

    return binary_path


def _read_profile_from_disk(profile_id: str) -> dict:
    """Read Donut Browser profile metadata.json from disk.

    Returns the parsed JSON dict (BrowserProfile structure).
    """
    data_dir = _donut_data_dir()
    metadata_path = os.path.join(data_dir, "profiles", profile_id, "metadata.json")

    if not os.path.isfile(metadata_path):
        raise DonutBrowserError(
            f"Profile metadata not found at {metadata_path}. "
            f"Create a Camoufox profile in Donut Browser first."
        )

    with open(metadata_path) as f:
        return json.load(f)


def _extract_fingerprint_config(profile_data: dict) -> dict:
    """Build Camoufox config using real system values + safe BrowserForge extras.

    BrowserForge generates internally inconsistent fingerprints:
    - Chrome WebGL (ANGLE/Direct3D, "Google Inc.") in a Firefox browser
    - Chrome/Edge/WebKit plugins in Firefox
    - Windows platform on a Linux host
    - Wrong CPU cores, screen resolution, etc.

    Instead we keep only conflict-free BrowserForge values (canvas noise,
    fonts, geolocation, timezone) and set everything else to real system
    values.  This produces a consistent fingerprint that matches the
    actual hardware.
    """
    raw_config = {}
    camou_config = profile_data.get("camoufox_config")
    if camou_config:
        fp_str = camou_config.get("fingerprint")
        if fp_str:
            raw_config = json.loads(fp_str)
        else:
            logger.warning(
                "Profile %s has no stored fingerprint",
                profile_data.get("id", "?"),
            )

    return _build_real_config(raw_config)


# Fonts actually installed on the host Linux system.
# BrowserForge generates Windows fonts (Segoe UI, Calibri, etc.) which are
# anomalous on a Linux platform and immediately detectable.
_LINUX_FONTS = [
    # Liberation family (metric-compatible with Arial/Times/Courier)
    "Liberation Sans", "Liberation Serif", "Liberation Mono",
    # DejaVu family (extended Unicode coverage, default on many distros)
    "DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono",
    # Ubuntu family
    "Ubuntu", "Ubuntu Mono",
    # Noto family (Google, broad coverage)
    "Noto Sans", "Noto Serif", "Noto Sans Mono", "Noto Color Emoji",
    # URW/Ghostscript (metric-compatible classics)
    "Nimbus Sans", "Nimbus Roman", "Nimbus Mono PS",
    # Free fonts (GNU FreeFont project)
    "FreeSans", "FreeSerif", "FreeMono",
    # Other common Linux fonts
    "Bitstream Charter", "Courier 10 Pitch", "Droid Sans Fallback",
    "C059", "P052", "URW Bookman", "URW Gothic",
]


def _build_real_config(browserforge_config: dict) -> dict:
    """Build Camoufox config matching the real host system.

    Keeps useful BrowserForge values (canvas noise, geolocation) but replaces
    hardware/browser-identifying properties with real system values.
    This avoids cross-browser/cross-platform inconsistencies that
    BrowserForge generates (Chrome WebGL in Firefox, Windows platform
    on Linux, Windows fonts on Linux, etc.).
    """
    config = {}

    # === KEEP from BrowserForge (valuable, no cross-browser conflicts) ===
    _KEEP_KEYS = {
        "canvas:aaCapOffset", "canvas:aaOffset",       # canvas noise
        "fonts:spacing_seed",                            # font metric randomization
        "geolocation:latitude", "geolocation:longitude", "geolocation:accuracy",
        "timezone",
    }
    for key in _KEEP_KEYS:
        if key in browserforge_config:
            config[key] = browserforge_config[key]

    # === Fonts: use real Linux system fonts ===
    # BrowserForge generates Windows fonts (Segoe UI, Calibri, etc.) that
    # don't exist on Linux — a critical anomaly for fingerprint detection.
    config["fonts"] = _LINUX_FONTS

    # === WebGL: handled via webgl_config parameter ===
    # Camoufox ignores manual webGl:vendor/webGl:renderer config keys — the C++
    # code uses the complete WebGL profile from sample_webgl() (vendor + renderer
    # + 147 GL parameters + extensions).  We use the webgl_config parameter
    # in AsyncCamoufox kwargs to select a coherent NVIDIA entry from the database.
    # See _WEBGL_CONFIG below.

    # === REMOVE: navigator.userAgent, platform, oscpu, appVersion ===
    # Let Camoufox + BrowserForge generate from os='linux' param.
    # This produces correct UA like:
    # "Mozilla/5.0 (X11; Linux x86_64; rv:135.0) Gecko/20100101 Firefox/135.0"

    # === REAL navigator values ===
    config["navigator.hardwareConcurrency"] = os.cpu_count() or 16
    config["navigator.maxTouchPoints"] = 0
    config["navigator.doNotTrack"] = "unspecified"
    config["navigator.language"] = "en-US"
    config["navigator.languages"] = ["en-US", "en"]

    # === REAL screen & window values ===
    # Maximized Firefox on 1920x1080 Linux with ~40px XFCE taskbar:
    #   screen:    1920×1080 (physical monitor)
    #   available: 1920×1040 (minus 40px taskbar)
    #   outer:     1920×1040 (maximized = fills available area)
    #   inner:     1920× 960 (minus ~80px browser chrome: tab + address bar)
    config["screen.width"] = 1920
    config["screen.height"] = 1080
    config["screen.availWidth"] = 1920
    config["screen.availHeight"] = 1040
    config["screen.colorDepth"] = 24
    config["screen.pixelDepth"] = 24
    config["window.devicePixelRatio"] = 1.0
    config["window.outerWidth"] = 1920
    config["window.outerHeight"] = 1040
    config["window.innerWidth"] = 1920
    config["window.innerHeight"] = 960
    config["window.screenX"] = 0
    config["window.screenY"] = 0

    # === mediaDevices — real PCs always have audio/video devices ===
    config["mediaDevices:enabled"] = True
    config["mediaDevices:webcams"] = 1
    config["mediaDevices:micros"] = 1
    config["mediaDevices:speakers"] = 1

    # === HTTP headers ===
    # Camoufox v146 advertises zstd in Accept-Encoding but Juggler's
    # convertString() has no zstd converter — pages show raw binary.
    # MaskConfig overrides Accept-Encoding at C++ level (nsHttpHandler).
    config["headers.Accept-Encoding"] = "gzip, deflate, br"

    logger.debug(
        "Built real-system config: %d keys (kept %d from BrowserForge, "
        "set %d Linux fonts, webGl blockIfNotDefined=True)",
        len(config),
        sum(1 for k in config if k in _KEEP_KEYS),
        len(_LINUX_FONTS),
    )
    return config


def _get_profile_data_dir(profile_id: str) -> str:
    """Return path to Donut profile's browser data directory."""
    data_dir = _donut_data_dir()
    profile_dir = os.path.join(data_dir, "profiles", profile_id, "profile")
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir


class BrowserManager:
    """Manages Camoufox browser lifecycle using Donut Browser's profile.

    Donut Browser handles: profile creation, fingerprint generation
    (BrowserForge statistical profiles), proxy config, persistent storage.

    This class handles: reading Donut profile data, launching Camoufox
    with the profile's fingerprint config, session cookie backup/restore.
    """

    def __init__(self, account_id: int, donut_profile_id: str | None = None):
        self.account_id = account_id
        self.donut_profile_id = donut_profile_id
        self._camoufox = None     # AsyncCamoufox context manager
        self._context = None      # Playwright BrowserContext

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self, backup_cookies: dict | None = None):
        """Launch Camoufox with Donut Browser's profile and fingerprint.

        Args:
            backup_cookies: Optional ``{name: value}`` dict of Facebook session
                cookies to restore before navigation (crash protection).

        Returns:
            Playwright Page (the active browser page).

        Raises:
            DonutBrowserError: If Donut Browser profile or binary not found.
            ValueError: If no donut_profile_id is configured for this account.
        """
        if not self.donut_profile_id:
            raise ValueError(
                f"Account {self.account_id} has no Donut Browser profile ID "
                f"(browser_profile_id). Create a profile in Donut Browser and "
                f"assign it to this account."
            )

        # Read profile from Donut API (preferred) or from disk (fallback)
        profile_data = await self._load_profile_data()

        # Extract fingerprint config (dotted-key dict for AsyncCamoufox)
        fingerprint_config = _extract_fingerprint_config(profile_data)

        # Find Camoufox binary from Donut's downloads.
        # Always use _find_camoufox_binary() instead of the profile's executable_path
        # to avoid stale paths after upgrading the Camoufox version.
        camou_config = profile_data.get("camoufox_config", {}) or {}
        executable_path = _find_camoufox_binary()

        # Profile data directory (persistent browser state)
        user_data_dir = _get_profile_data_dir(self.donut_profile_id)

        # Proxy from Donut profile config
        proxy = None
        proxy_url = camou_config.get("proxy")
        if proxy_url:
            proxy = {"server": proxy_url}

        # Headless mode
        headless = settings.CAMOUFOX_HEADLESS
        if headless == "true":
            headless_val = True
        elif headless == "false":
            headless_val = False
        else:
            headless_val = headless  # "virtual" for Xvfb

        # Build AsyncCamoufox kwargs.
        # os='linux' ensures BrowserForge generates Linux-compatible values
        # (UA, platform, oscpu) for any keys not set in our config.
        # geoip=True spoofs WebRTC IPs without blocking mediaDevices.
        # Extract Firefox version from binary directory name (e.g. "v146.0.1-alpha.25" → 146).
        # Required by camoufox 0.5+ to avoid calling installed_verstr() which needs
        # an official camoufox binary install (we use Donut Browser's binary instead).
        ff_version = None
        if executable_path:
            version_dir = os.path.basename(os.path.dirname(executable_path))
            try:
                ff_version = int(version_dir.lstrip("v").split(".")[0])
            except (ValueError, IndexError):
                pass

        kwargs = dict(
            persistent_context=True,
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            humanize=True,
            headless=headless_val,
            config=fingerprint_config if fingerprint_config else None,
            proxy=proxy,
            os="linux",
            ff_version=ff_version,
            window=(1920, 1040),
            # Playwright viewport must match config window.innerWidth/Height.
            # Camoufox's from_browserforge() puts viewport in context_options
            # but that only goes into CAMOU_CONFIG env vars, not to Playwright.
            viewport={"width": 1920, "height": 960},
            geoip=camou_config.get("geoip", True),
            webgl_config=_WEBGL_CONFIG,
            exclude_addons=list(DefaultAddons),
            i_know_what_im_doing=True,
        )

        logger.info(
            "Launching Camoufox for account %s (profile %s, binary %s)",
            self.account_id, self.donut_profile_id,
            os.path.basename(os.path.dirname(executable_path)),
        )

        self._camoufox = AsyncCamoufox(**kwargs)
        self._context = await self._camoufox.__aenter__()

        # Get or create a page
        if self._context.pages:
            page = self._context.pages[0]
        else:
            page = await self._context.new_page()

        reset_cursor()

        # Restore session cookies from our DB backup (crash protection)
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
            logger.info(
                "Restored %d backup cookies for account %s",
                len(cookie_params), self.account_id,
            )

        logger.info(
            "Browser ready for account %s (Donut profile %s)",
            self.account_id, self.donut_profile_id,
        )
        return page

    async def _load_profile_data(self) -> dict:
        """Load Donut profile data from API (preferred) or disk (fallback)."""
        # Try Donut API first
        try:
            api_token = settings.DONUT_API_TOKEN
            if not api_token:
                api_token = auto_configure() or ""

            if api_token:
                client = DonutClient(
                    api_url=settings.DONUT_API_URL,
                    api_token=api_token,
                )
                profile = await client.get_profile(self.donut_profile_id)
                if profile:
                    logger.debug("Profile %s loaded from Donut API", self.donut_profile_id)
                    return profile
        except Exception as e:
            logger.debug("Donut API unavailable, falling back to disk: %s", e)

        # Fallback: read from disk
        profile = _read_profile_from_disk(self.donut_profile_id)
        logger.debug("Profile %s loaded from disk", self.donut_profile_id)
        return profile

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
        """Close the Camoufox browser (profile data persists on disk)."""
        if self._camoufox:
            try:
                await self._camoufox.__aexit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing Camoufox: %s", e)
            self._camoufox = None
            self._context = None
