import os
import re
import logging
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Browser, Page, BrowserContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# Maps ANGLE-style "Google Inc. (VENDOR)" to Firefox-native "VENDOR Corporation".
# Camoufox's WebGL database sometimes picks Chrome/ANGLE entries, which don't match
# a Firefox User-Agent.  Firefox uses the raw GPU vendor name from the driver.
_ANGLE_VENDOR_RE = re.compile(r"^Google Inc\.?\s*\((.+?)\)$")

# Polyfill for navigator.mediaDevices — Camoufox strips it at C++ level,
# but real browsers always expose it.  Injected via context.add_init_script().
_MEDIA_DEVICES_POLYFILL = """(() => {
    if (typeof navigator.mediaDevices !== 'undefined') return;
    const md = {
        enumerateDevices: () => Promise.resolve([
            {deviceId: 'default', kind: 'audioinput',  label: '', groupId: 'default'},
            {deviceId: 'default', kind: 'audiooutput', label: '', groupId: 'default'},
        ]),
        getUserMedia: () => Promise.reject(
            new DOMException('NotAllowedError', 'NotAllowedError')
        ),
        getSupportedConstraints: () => ({
            width: true, height: true, aspectRatio: true, frameRate: true,
            facingMode: true, resizeMode: true, sampleRate: true,
            sampleSize: true, echoCancellation: true, autoGainControl: true,
            noiseSuppression: true, latency: true, channelCount: true,
            deviceId: true, groupId: true,
        }),
    };
    Object.defineProperty(navigator, 'mediaDevices', {
        value: md, configurable: true, enumerable: true,
    });
})()"""

# BrowserForge generates ISO 639-3 codes, but real browsers always use ISO 639-1.
# A 3-letter language code in navigator.language is an immediate detection vector.
_LANG3_TO_LANG2 = {
    "tts": "th",  # Northeastern Thai → Thai
    "mfa": "ms",  # Pattani Malay → Malay
    "zsm": "ms",  # Standard Malay → Malay
    "arb": "ar",  # Standard Arabic → Arabic
    "cmn": "zh",  # Mandarin Chinese → Chinese
    "swh": "sw",  # Swahili → Swahili
    "uzn": "uz",  # Northern Uzbek → Uzbek
    "pes": "fa",  # Iranian Persian → Persian
    "zlm": "ms",  # Malay (individual) → Malay
    "khk": "mn",  # Halh Mongolian → Mongolian
    "lvs": "lv",  # Standard Latvian → Latvian
    "ekk": "et",  # Standard Estonian → Estonian
    "nob": "nb",  # Norwegian Bokmål
    "nno": "nn",  # Norwegian Nynorsk
    "knn": "kok", # Konkani → Konkani (stays 3-letter, valid in BCP47)
    "pbu": "ps",  # Northern Pashto → Pashto
    "ydd": "yi",  # Eastern Yiddish → Yiddish
}

class BrowserManager:
    def __init__(self, account_email: str, proxy_url: str = None, session_file: str = None):
        self.account_email = account_email
        self.proxy_url = proxy_url

        # Tworzenie nazwy pliku sesji jeśli nie podano
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.session_file = session_file or os.path.join(base_dir, "sessions", f"{account_email}_storage.json")

        self._camoufox_cm = None
        self._browser: Browser = None
        self._context: BrowserContext = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self) -> Page:
        camoufox_kwargs = {
            "headless": "virtual",
            "geoip": True,
            "os": "linux",
            "block_webgl": False,
            "i_know_what_im_doing": True,
            "config": {
                # Desktop without touchscreen → 0. Value 1 is a known spoofing glitch.
                "navigator.maxTouchPoints": 0,
                # Realistic core count for a desktop PC (4-16 is normal consumer range).
                "navigator.hardwareConcurrency": 8,
                # DoNotTrack "unspecified" = not set (default for ~99% of users).
                # BrowserForge sometimes generates "1" which is a fingerprint signal.
                "navigator.doNotTrack": "unspecified",
            },
            "firefox_user_prefs": {
                # DoNotTrack — only ~1% of real users enable this, making it a fingerprint
                "privacy.donottrackheader.enabled": False,
                # Ensure navigator.mediaDevices is available (real browsers always have it).
                # Camoufox/Firefox may disable this; without it mediaDevices is undefined.
                "media.navigator.enabled": True,
                # Provide fake media streams so enumerateDevices() returns realistic
                # audio/video devices even without real hardware in Docker.
                "media.navigator.streams.fake": True,
            },
        }

        if self.proxy_url:
            camoufox_kwargs["proxy"] = {"server": self.proxy_url}

        self._camoufox_cm = AsyncCamoufox(**camoufox_kwargs)
        self._browser = await self._camoufox_cm.__aenter__()

        context_args = {}
        if os.path.exists(self.session_file):
            logger.info(f"Wczytywanie sesji z {self.session_file}")
            context_args["storage_state"] = self.session_file

        self._context = await self._browser.new_context(**context_args)

        await self._context.add_init_script(_MEDIA_DEVICES_POLYFILL)

        page = await self._context.new_page()

        # --- Fix WebGL vendor if Camoufox picked an ANGLE/Chrome entry ---
        # Firefox returns raw GPU vendor ("NVIDIA Corporation"), never "Google Inc. (NVIDIA)".
        # Camoufox patches WebGL at C++ level, but we can override the specific parameters
        # by closing and re-launching with explicit webgl config values.
        try:
            webgl_info = await page.evaluate("""() => {
                const gl = document.createElement('canvas').getContext('webgl');
                if (!gl) return null;
                const dbg = gl.getExtension('WEBGL_debug_renderer_info');
                if (!dbg) return null;
                return {
                    vendor: gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL),
                };
            }""")
            if webgl_info:
                vendor = webgl_info.get("vendor", "")
                m = _ANGLE_VENDOR_RE.match(vendor)
                if m:
                    native_vendor = m.group(1)
                    # Add " Corporation" if not already present (e.g. "NVIDIA" → "NVIDIA Corporation")
                    if not native_vendor.endswith(("Corporation", "Inc.", "Ltd.")):
                        native_vendor = f"{native_vendor} Corporation"
                    renderer = webgl_info.get("renderer", "")
                    logger.info(f"Fixing WebGL vendor: '{vendor}' -> '{native_vendor}'")
                    # Close everything and re-launch with explicit WebGL config
                    await page.close()
                    await self._context.close()
                    await self._browser.close()
                    await self._camoufox_cm.__aexit__(None, None, None)
                    camoufox_kwargs["config"]["webgl:unmaskedVendor"] = native_vendor
                    camoufox_kwargs["config"]["webgl:unmaskedRenderer"] = renderer
                    self._camoufox_cm = AsyncCamoufox(**camoufox_kwargs)
                    self._browser = await self._camoufox_cm.__aenter__()
                    self._context = await self._browser.new_context(**context_args)
                    await self._context.add_init_script(_MEDIA_DEVICES_POLYFILL)
                    page = await self._context.new_page()
        except Exception as e:
            logger.warning(f"Nie udalo sie poprawic WebGL vendor: {e}")

        # Fix invalid language codes from BrowserForge (ISO 639-3 → ISO 639-1).
        # Real browsers always use 2-letter codes; a 3-letter code is detectable.
        try:
            lang = await page.evaluate("navigator.language")
            if lang:
                primary = lang.split("-")[0].lower()
                if len(primary) >= 3 and primary in _LANG3_TO_LANG2:
                    region = lang.split("-")[1] if "-" in lang else ""
                    correct = _LANG3_TO_LANG2[primary]
                    fixed_locale = f"{correct}-{region}" if region else correct
                    logger.info(f"Fixing language: {lang} -> {fixed_locale}")
                    await page.close()
                    await self._context.close()
                    context_args["locale"] = fixed_locale
                    self._context = await self._browser.new_context(**context_args)
                    await self._context.add_init_script(_MEDIA_DEVICES_POLYFILL)
                    page = await self._context.new_page()
        except Exception as e:
            logger.warning(f"Nie udalo sie poprawic jezyka: {e}")

        # Adjust viewport to fit within BrowserForge's spoofed screen dimensions.
        # In headless mode the default viewport can exceed screen.width,
        # which is physically impossible on real hardware and a detection vector.
        try:
            screen_dims = await page.evaluate("({w: screen.width, h: screen.height})")
            scr_w = screen_dims.get("w", 1920)
            scr_h = screen_dims.get("h", 1080)
            vp_w = max(800, scr_w - 28)
            vp_h = max(600, scr_h - 85)
            await page.set_viewport_size({"width": vp_w, "height": vp_h})
        except Exception as e:
            logger.warning(f"Nie udalo sie dopasowac viewport do screen: {e}")

        return page

    async def save_session(self):
        """Zapisuje stan sesji (Local Storage / Ciasteczka) do pliku by ominąć ponowne logowanie"""
        if self._context:
            logger.info(f"Zapisywanie stanu sesji do {self.session_file}")
            os.makedirs(os.path.dirname(self.session_file), exist_ok=True)
            await self._context.storage_state(path=self.session_file)

    async def stop(self):
        if self._context:
            await self.save_session()
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._camoufox_cm:
            await self._camoufox_cm.__aexit__(None, None, None)
