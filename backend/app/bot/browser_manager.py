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
import functools
import glob as _glob
import json
import logging
import os
import re
import subprocess

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
    "Noto Sans", "Noto Serif", "Noto Sans Mono", "Noto Mono", "Noto Color Emoji",
    "Noto Sans CJK HK", "Noto Serif CJK JP", "Noto Serif CJK SC",
    "Noto Sans Mono CJK SC",
    "Noto Sans Canadian Aboriginal", "Noto Sans Gunjala Gondi",
    "Noto Sans Masaram Gondi", "Noto Serif Yezidi",
    # Full font names (family + style) — needed because PixelScan and some
    # detection tools test by full name (e.g. "Noto Sans Canadian Aboriginal
    # Regular") which Firefox's font.system.whitelist must also allow.
    "Noto Sans Canadian Aboriginal Regular", "Noto Sans Gunjala Gondi Regular",
    "Noto Sans Masaram Gondi Regular", "Noto Serif Yezidi Regular",
    # URW/Ghostscript (metric-compatible classics)
    "Nimbus Sans", "Nimbus Roman", "Nimbus Mono PS",
    # Free fonts (GNU FreeFont project)
    "FreeSans", "FreeSerif", "FreeMono",
    # Other common Linux fonts
    "Abyssinica SIL", "OpenSymbol",
    "Bitstream Charter", "Courier 10 Pitch", "Droid Sans Fallback",
    "C059", "P052", "URW Bookman", "URW Gothic",
]

# Height of Firefox browser chrome (tab bar + navigation bar).
# Used to compute window.innerHeight = outerHeight - chrome.
_BROWSER_CHROME_HEIGHT = 80

# Force C locale for subprocess output parsing (language-independent).
_SUBPROCESS_ENV = {**os.environ, "LANG": "C", "LC_ALL": "C"}

# Well-known font families on Linux — used as intersection filter
# against fc-list output so we don't report obscure fonts (TeX, MathJax)
# that would make the fingerprint too unique.
_KNOWN_FONT_FAMILIES = {
    # Liberation (metric-compatible with Arial/Times/Courier)
    "Liberation Sans", "Liberation Serif", "Liberation Mono",
    # DejaVu (default on many distros)
    "DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono",
    # Ubuntu
    "Ubuntu", "Ubuntu Mono", "Ubuntu Condensed",
    # Noto (Google, broad Unicode)
    "Noto Sans", "Noto Serif", "Noto Sans Mono", "Noto Mono", "Noto Color Emoji",
    "Noto Kufi Arabic",
    "Noto Sans CJK HK", "Noto Serif CJK JP", "Noto Serif CJK SC",
    "Noto Sans Mono CJK SC",
    "Noto Sans Canadian Aboriginal", "Noto Sans Gunjala Gondi",
    "Noto Sans Masaram Gondi", "Noto Serif Yezidi",
    "Noto Sans Canadian Aboriginal Regular", "Noto Sans Gunjala Gondi Regular",
    "Noto Sans Masaram Gondi Regular", "Noto Serif Yezidi Regular",
    # URW/Ghostscript
    "Nimbus Sans", "Nimbus Sans Narrow", "Nimbus Roman", "Nimbus Mono PS",
    "C059", "P052", "URW Bookman", "URW Gothic",
    # GNU FreeFont
    "FreeSans", "FreeSerif", "FreeMono",
    # GNOME/GTK
    "Cantarell",
    # LibreOffice / SIL
    "OpenSymbol", "Abyssinica SIL",
    # Common system fonts
    "Bitstream Charter", "Courier 10 Pitch",
    "Droid Sans", "Droid Sans Fallback", "Droid Serif", "Droid Sans Mono",
    # Popular user-installed fonts
    "Roboto", "Roboto Mono", "Roboto Condensed", "Roboto Slab",
    "Open Sans", "Lato", "Inter",
    "Fira Sans", "Fira Code", "Fira Mono",
    "Source Sans 3", "Source Serif 4", "Source Code Pro",
    "Hack", "JetBrains Mono", "Inconsolata",
    # KDE/Plasma
    "Oxygen", "Oxygen Mono",
    # Red Hat / IBM
    "Red Hat Display", "Red Hat Text", "Red Hat Mono",
    "IBM Plex Sans", "IBM Plex Serif", "IBM Plex Mono",
}


def _detect_screen(info: dict) -> None:
    """Detect screen resolution via xrandr (primary monitor)."""
    try:
        out = subprocess.check_output(
            ["xrandr", "--current"], text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        primary_w, primary_h = None, None
        current_w, current_h = None, None
        for line in out.splitlines():
            if " primary " in line:
                match = re.search(r"(\d{3,5})x(\d{3,5})\+", line)
                if match:
                    primary_w = int(match.group(1))
                    primary_h = int(match.group(2))
            if "*" in line and current_w is None:
                match = re.search(r"(\d{3,5})x(\d{3,5})", line)
                if match:
                    current_w = int(match.group(1))
                    current_h = int(match.group(2))
        if primary_w:
            info["screen_width"] = primary_w
            info["screen_height"] = primary_h
        elif current_w:
            info["screen_width"] = current_w
            info["screen_height"] = current_h
    except Exception as e:
        logger.debug("xrandr failed (using default screen): %s", e)


def _detect_workarea(info: dict) -> None:
    """Detect available work area via _NET_WORKAREA."""
    try:
        out = subprocess.check_output(
            ["xprop", "-root", "_NET_WORKAREA"], text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        match = re.search(r"=\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)", out)
        if match:
            wa_x = int(match.group(1))
            wa_y = int(match.group(2))
            wa_w = int(match.group(3))
            wa_h = int(match.group(4))
            info["avail_width"] = min(wa_w, info["screen_width"])
            info["avail_height"] = min(wa_h, info["screen_height"])
            info["screen_x"] = wa_x
            info["screen_y"] = wa_y
    except Exception as e:
        logger.debug("xprop failed (using default workarea): %s", e)
        info["avail_width"] = info["screen_width"]
        info["avail_height"] = info["screen_height"] - 40


def _detect_color_depth(info: dict) -> None:
    """Detect color depth via xdpyinfo."""
    try:
        out = subprocess.check_output(
            ["xdpyinfo"], text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        match = re.search(r"depth of root window:\s*(\d+)", out)
        if match:
            depth = int(match.group(1))
            if depth in (8, 16, 24, 30, 32):
                info["color_depth"] = depth
    except Exception as e:
        logger.debug("xdpyinfo failed (using default color depth): %s", e)


def _detect_dpr(info: dict) -> None:
    """Detect device pixel ratio (HiDPI) via GDK_SCALE or xrdb."""
    try:
        gdk_scale = os.environ.get("GDK_SCALE")
        if gdk_scale:
            info["device_pixel_ratio"] = float(gdk_scale)
        else:
            out = subprocess.check_output(
                ["xrdb", "-query"], text=True, timeout=5,
                stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
            )
            for line in out.splitlines():
                if "Xft.dpi" in line:
                    m = re.search(r"(\d+)", line.split(":")[-1])
                    if m:
                        dpi = int(m.group(1))
                        if dpi > 0:
                            info["device_pixel_ratio"] = round(dpi / 96.0, 2)
                    break
    except Exception as e:
        logger.debug("DPI detection failed (using default): %s", e)


def _detect_locale(info: dict) -> None:
    """Detect system locale for navigator.language."""
    try:
        locale_str = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
            or ""
        )
        if locale_str:
            base = locale_str.split(".")[0]
            if "_" in base:
                parts = base.split("_")
                lang = f"{parts[0]}-{parts[1]}"
                info["language"] = lang
                info["languages"] = [lang, parts[0]]
    except Exception as e:
        logger.debug("Locale detection failed (using default en-US): %s", e)


def _detect_media_devices(info: dict) -> None:
    """Detect webcams, microphones, and speakers."""
    try:
        video_devs = _glob("/dev/video*")
        info["webcams"] = max(len(video_devs) // 2, 0)
    except Exception as e:
        logger.debug("Webcam detection failed: %s", e)

    try:
        out = subprocess.check_output(
            ["arecord", "-l"], text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        cards = {line.split(":")[0] for line in out.splitlines() if line.startswith("card")}
        info["micros"] = len(cards) if cards else 0
    except Exception as e:
        logger.debug("Microphone detection failed (arecord): %s", e)

    try:
        out = subprocess.check_output(
            ["aplay", "-l"], text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        cards = {line.split(":")[0] for line in out.splitlines() if line.startswith("card")}
        info["speakers"] = len(cards) if cards else 0
    except Exception as e:
        logger.debug("Speaker detection failed (aplay): %s", e)


def _detect_dark_theme(info: dict) -> None:
    """Detect dark theme via GTK settings."""
    info["dark_theme"] = False
    try:
        gtk_theme = subprocess.check_output(
            ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
            text=True, timeout=5,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        ).strip().strip("'\"").lower()
        if "dark" in gtk_theme:
            info["dark_theme"] = True
    except Exception as e:
        logger.debug("GTK theme detection failed: %s", e)
    if not info["dark_theme"]:
        try:
            color_scheme = subprocess.check_output(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                text=True, timeout=5,
                stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
            ).strip().strip("'\"").lower()
            if "dark" in color_scheme:
                info["dark_theme"] = True
        except Exception as e:
            logger.debug("Color scheme detection failed: %s", e)


@functools.lru_cache(maxsize=1)
def _detect_system() -> dict:
    """Detect real display, locale, media device, and CPU properties.

    Cached per process — values don't change during runtime.
    Falls back to sensible defaults if detection tools are unavailable
    (e.g. headless server, Wayland without xrandr, container).
    """
    info = {
        "screen_width": 1920, "screen_height": 1080,
        "avail_width": 1920, "avail_height": 1040,
        "screen_x": 0, "screen_y": 0,
        "color_depth": 24,
        "device_pixel_ratio": 1.0,
        "language": "en-US", "languages": ["en-US", "en"],
        "webcams": 0, "micros": 1, "speakers": 1,
        "cpu_count": os.cpu_count() or 8,
    }

    _detect_screen(info)
    _detect_workarea(info)
    _detect_color_depth(info)
    _detect_dpr(info)
    _detect_locale(info)
    _detect_media_devices(info)
    _detect_dark_theme(info)

    info["outer_width"] = info["avail_width"]
    info["outer_height"] = info["avail_height"]
    info["inner_width"] = info["avail_width"]
    info["inner_height"] = info["avail_height"] - _BROWSER_CHROME_HEIGHT

    logger.info(
        "System detected: screen=%dx%d, avail=%dx%d, dpr=%.1f, "
        "depth=%d, locale=%s, devices=%d/%d/%d, cpu=%d, dark=%s",
        info["screen_width"], info["screen_height"],
        info["avail_width"], info["avail_height"],
        info["device_pixel_ratio"], info["color_depth"],
        info["language"],
        info["webcams"], info["micros"], info["speakers"],
        info["cpu_count"], info["dark_theme"],
    )
    return info


@functools.lru_cache(maxsize=1)
def _detect_fonts() -> list[str]:
    """Detect installed fonts via fc-list, filtered to well-known families.

    Queries BOTH family names (%{family}) and full names (%{fullname}) because
    some detection tools (PixelScan) test fonts by full name including style
    suffix (e.g. "Noto Sans Canadian Aboriginal Regular").  Firefox's
    font.system.whitelist must contain the exact lookup string used by CSS
    font-family for the font to be visible.

    Returns only fonts that are BOTH installed on the system AND in the
    _KNOWN_FONT_FAMILIES whitelist — avoids obscure fonts (TeX, MathJax)
    that would make the fingerprint uniquely identifiable.
    Falls back to _LINUX_FONTS if fc-list is unavailable.
    """
    try:
        out = subprocess.check_output(
            ["fc-list", "--format", "%{family}\n%{fullname}\n"],
            text=True, timeout=10,
            stderr=subprocess.DEVNULL, env=_SUBPROCESS_ENV,
        )
        installed = set()
        for line in out.splitlines():
            for name in line.strip().split(","):
                name = name.strip()
                if name:
                    installed.add(name)

        matched = sorted(installed & _KNOWN_FONT_FAMILIES)
        if matched:
            logger.info(
                "Detected %d fonts (from %d installed, %d known)",
                len(matched), len(installed), len(_KNOWN_FONT_FAMILIES),
            )
            return matched
    except Exception as e:
        logger.warning("fc-list failed: %s", e)

    logger.info("fc-list unavailable — using fallback font list (%d fonts)", len(_LINUX_FONTS))
    return _LINUX_FONTS


def _build_real_config(browserforge_config: dict) -> dict:
    """Build Camoufox config matching the real host system.

    Keeps useful BrowserForge values (geolocation, font spacing) but replaces
    hardware/browser-identifying properties with values detected from the
    actual system (screen, CPU, locale, fonts, media devices).
    All values are applied at C++ level via CAMOU_CONFIG env vars — no
    JavaScript injection, undetectable by page scripts.
    """
    sys_info = _detect_system()
    fonts = _detect_fonts()
    config = {}

    # === KEEP from BrowserForge (valuable, no cross-browser conflicts) ===
    _KEEP_KEYS = {
        "fonts:spacing_seed",                            # font metric randomization
        "geolocation:latitude", "geolocation:longitude", "geolocation:accuracy",
        "timezone",
    }
    for key in _KEEP_KEYS:
        if key in browserforge_config:
            config[key] = browserforge_config[key]

    # === Canvas noise: DISABLED ===
    # Camoufox adds +/-1 pixel noise to canvas via CanvasFingerprintManager.
    # Facebook detects this: (1) noise pattern is identifiable, (2) canvas
    # rendering becomes ~10x slower which is measurable by timing attacks.
    # We use real hardware (GPU, screen, fonts) so the natural canvas
    # fingerprint is already unique and consistent.  Seed=0 is a no-op
    # in C++ (ApplyCanvasNoise returns immediately).
    # Also prevents Camoufox Python lib from generating a random seed
    # (merge_into/set_into won't overwrite an existing key).
    config["canvas:seed"] = 0

    # === Fonts: only report fonts actually installed on the system ===
    # BrowserForge generates Windows fonts (Segoe UI, Calibri) that don't
    # exist on Linux.  _detect_fonts() intersects fc-list output with a
    # whitelist of well-known families to avoid unique fingerprints.
    config["fonts"] = fonts

    # === WebGL: handled via webgl_config parameter ===
    # Camoufox ignores manual webGl:vendor/webGl:renderer config keys — the C++
    # code uses the complete WebGL profile from sample_webgl() (vendor + renderer
    # + 147 GL parameters + extensions).  We use the webgl_config parameter
    # in AsyncCamoufox kwargs to select a coherent NVIDIA entry from the database.

    # === REMOVE: navigator.userAgent, platform, oscpu, appVersion ===
    # Let Camoufox + BrowserForge generate from os='linux' param.

    # === Navigator values (detected from system) ===
    config["navigator.hardwareConcurrency"] = sys_info["cpu_count"]
    config["navigator.maxTouchPoints"] = 0
    config["navigator.doNotTrack"] = "unspecified"
    config["navigator.language"] = sys_info["language"]
    config["navigator.languages"] = sys_info["languages"]

    # === Screen & window values (detected via xrandr + _NET_WORKAREA) ===
    # Maximized browser: outer = available screen, inner = outer - chrome.
    config["screen.width"] = sys_info["screen_width"]
    config["screen.height"] = sys_info["screen_height"]
    config["screen.availWidth"] = sys_info["avail_width"]
    config["screen.availHeight"] = sys_info["avail_height"]
    config["screen.colorDepth"] = sys_info["color_depth"]
    config["screen.pixelDepth"] = sys_info["color_depth"]
    config["window.devicePixelRatio"] = sys_info["device_pixel_ratio"]
    config["window.outerWidth"] = sys_info["outer_width"]
    config["window.outerHeight"] = sys_info["outer_height"]
    config["window.innerWidth"] = sys_info["inner_width"]
    config["window.innerHeight"] = sys_info["inner_height"]
    config["window.screenX"] = sys_info["screen_x"]
    config["window.screenY"] = sys_info["screen_y"]

    # === Media devices (detected via /dev/video*, arecord, aplay) ===
    config["mediaDevices:enabled"] = True
    config["mediaDevices:webcams"] = sys_info["webcams"]
    config["mediaDevices:micros"] = sys_info["micros"]
    config["mediaDevices:speakers"] = sys_info["speakers"]

    # === HTTP headers ===
    # Camoufox v146 advertises zstd in Accept-Encoding but Juggler's
    # convertString() has no zstd converter — pages show raw binary.
    # MaskConfig overrides Accept-Encoding at C++ level (nsHttpHandler).
    config["headers.Accept-Encoding"] = "gzip, deflate, br"

    logger.debug(
        "Built real-system config: %d keys (kept %d from BrowserForge, "
        "%d fonts detected, screen=%dx%d, locale=%s)",
        len(config),
        sum(1 for k in config if k in _KEEP_KEYS),
        len(fonts),
        sys_info["screen_width"], sys_info["screen_height"],
        sys_info["language"],
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

        sys_info = _detect_system()
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
            # Window/viewport must match detected screen dimensions.
            window=(sys_info["outer_width"], sys_info["outer_height"]),
            viewport={"width": sys_info["inner_width"], "height": sys_info["inner_height"]},
            geoip=camou_config.get("geoip", True),
            webgl_config=_WEBGL_CONFIG,
            exclude_addons=list(DefaultAddons),
            i_know_what_im_doing=True,
            # Sync Firefox Intl locale with navigator.language.
            # locale= triggers Playwright's Browser.setLocaleOverride via Juggler,
            # which sets docShell.languageOverride → JS::SetRealmLocaleOverride.
            # Without this, Intl.DateTimeFormat().resolvedOptions().locale returns
            # en-US instead of matching navigator.language (detectable by PixelScan).
            locale=sys_info["language"],
            # Match system dark/light theme so prefers-color-scheme is correct.
            # Camoufox can't detect the GTK theme, so we detect it in Python
            # and pass via Playwright's color_scheme (Juggler's setColorScheme).
            # Without this, prefersLightColor=true leaks on PixelScan.
            color_scheme="dark" if sys_info["dark_theme"] else "light",
            firefox_user_prefs={
                "intl.locale.requested": sys_info["language"],
                "ui.systemUsesDarkTheme": 1 if sys_info["dark_theme"] else 0,
            },
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
