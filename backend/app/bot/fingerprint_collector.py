import logging

logger = logging.getLogger(__name__)

# Valid primary language codes (ISO 639-1)
_VALID_LANG_CODES = {
    "aa", "ab", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
    "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
    "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es", "et", "eu",
    "fa", "ff", "fi", "fj", "fo", "fr", "fy",
    "ga", "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
    "ia", "id", "ie", "ig", "ii", "ik", "in", "io", "is", "it", "iu",
    "ja", "jv",
    "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
    "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
    "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt",
    "qu",
    "rm", "rn", "ro", "ru", "rw",
    "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
    "ug", "uk", "ur", "uz",
    "ve", "vi", "vo",
    "wa", "wo",
    "xh",
    "yi", "yo",
    "za", "zh", "zu",
}

FINGERPRINT_JS = """
() => {
    const results = {};

    // --- Navigator ---
    results.navigator = {
        webdriver: navigator.webdriver,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        language: navigator.language,
        languages: Array.from(navigator.languages || []),
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory || null,
        maxTouchPoints: navigator.maxTouchPoints,
        vendor: navigator.vendor,
        pluginsLength: navigator.plugins.length,
        plugins: Array.from(navigator.plugins).map(p => p.name),
        cookieEnabled: navigator.cookieEnabled,
        doNotTrack: navigator.doNotTrack,
        pdfViewerEnabled: navigator.pdfViewerEnabled,
    };

    // --- Screen ---
    results.screen = {
        width: screen.width,
        height: screen.height,
        availWidth: screen.availWidth,
        availHeight: screen.availHeight,
        colorDepth: screen.colorDepth,
        pixelDepth: screen.pixelDepth,
        devicePixelRatio: window.devicePixelRatio,
        outerWidth: window.outerWidth,
        outerHeight: window.outerHeight,
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
    };

    // --- Canvas 2D ---
    try {
        const canvas = document.createElement('canvas');
        canvas.width = 200;
        canvas.height = 50;
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillStyle = '#f60';
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = '#069';
        ctx.fillText('Cwm fjordbank glyphs vext quiz', 2, 15);
        ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
        ctx.fillText('Cwm fjordbank glyphs vext quiz', 4, 17);
        const dataUrl = canvas.toDataURL();
        results.canvas = {
            hash: dataUrl.split('').reduce((a, b) => {
                a = ((a << 5) - a) + b.charCodeAt(0);
                return a & a;
            }, 0).toString(),
            supported: true,
        };
    } catch (e) {
        results.canvas = { supported: false, error: e.message };
    }

    // --- WebGL ---
    try {
        const gl = document.createElement('canvas').getContext('webgl');
        if (gl) {
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            results.webgl = {
                vendor: gl.getParameter(gl.VENDOR),
                renderer: gl.getParameter(gl.RENDERER),
                unmaskedVendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : null,
                unmaskedRenderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : null,
                version: gl.getParameter(gl.VERSION),
                shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
                extensionsCount: (gl.getSupportedExtensions() || []).length,
                supported: true,
            };
        } else {
            results.webgl = { supported: false };
        }
    } catch (e) {
        results.webgl = { supported: false, error: e.message };
    }

    // --- AudioContext ---
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) {
            const audioCtx = new AudioCtx();
            results.audio = {
                sampleRate: audioCtx.sampleRate,
                state: audioCtx.state,
                channelCount: audioCtx.destination.channelCount,
                maxChannelCount: audioCtx.destination.maxChannelCount,
                supported: true,
            };
            audioCtx.close();
        } else {
            results.audio = { supported: false };
        }
    } catch (e) {
        results.audio = { supported: false, error: e.message };
    }

    // --- Timezone ---
    results.timezone = {
        offset: new Date().getTimezoneOffset(),
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        locale: Intl.DateTimeFormat().resolvedOptions().locale,
    };

    // --- WebRTC ---
    results.webrtc = {
        rtcPeerConnectionExists: typeof RTCPeerConnection !== 'undefined',
        mediaDevicesExists: typeof navigator.mediaDevices !== 'undefined',
    };

    // --- Fonts ---
    try {
        const testFonts = [
            // Core web fonts (present on virtually every OS)
            'Arial', 'Verdana', 'Times New Roman', 'Courier New',
            'Georgia', 'Comic Sans MS', 'Impact', 'Trebuchet MS',
            'Palatino Linotype', 'Lucida Console', 'Tahoma',
            // Windows common
            'Segoe UI', 'Calibri', 'Cambria', 'Consolas', 'Candara',
            'Constantia', 'Corbel', 'Microsoft Sans Serif', 'Sylfaen',
            'Garamond', 'Book Antiqua', 'Century Gothic', 'Franklin Gothic Medium',
            'Lucida Sans Unicode', 'MS Reference Sans Serif',
            // Linux (Liberation — metric-compatible with MS fonts)
            'Liberation Sans', 'Liberation Serif', 'Liberation Mono',
            // Linux (DejaVu — extended Unicode coverage)
            'DejaVu Sans', 'DejaVu Serif', 'DejaVu Sans Mono',
            // Linux (FreeFont)
            'FreeSans', 'FreeSerif', 'FreeMono',
            // Linux (Noto — Google's universal font family)
            'Noto Sans', 'Noto Serif', 'Noto Mono',
            // Linux (CrosExtra — Chromebook metric-compatible)
            'Carlito', 'Caladea',
            // macOS common
            'Helvetica', 'Helvetica Neue', 'Menlo', 'Monaco',
            'Avenir', 'Futura', 'Optima', 'Gill Sans',
            // Cross-platform
            'Ubuntu', 'Roboto', 'Open Sans', 'Lato', 'Source Sans Pro',
        ];
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        const testString = 'mmmmmmmmmmlli';
        const testSize = '72px';
        const body = document.body || document.createElement('body');
        if (!document.body) document.documentElement.appendChild(body);
        const span = document.createElement('span');
        span.style.fontSize = testSize;
        span.innerHTML = testString;
        span.style.visibility = 'hidden';
        body.appendChild(span);

        const baseWidths = {};
        for (const base of baseFonts) {
            span.style.fontFamily = base;
            baseWidths[base] = span.offsetWidth;
        }

        const detectedFonts = [];
        for (const font of testFonts) {
            for (const base of baseFonts) {
                span.style.fontFamily = "'" + font + "', " + base;
                if (span.offsetWidth !== baseWidths[base]) {
                    detectedFonts.push(font);
                    break;
                }
            }
        }
        body.removeChild(span);
        results.fonts = { detected: detectedFonts, count: detectedFonts.length };
    } catch (e) {
        results.fonts = { detected: [], count: 0, error: e.message };
    }

    // --- Automation detection ---
    results.automation = {
        webdriver: navigator.webdriver,
        hasChrome: !!window.chrome,
        hasCallPhantom: !!window.callPhantom,
        hasPhantom: !!window._phantom,
        hasNightmare: !!window.__nightmare,
        hasSelenium: !!window._selenium,
        hasCDC: !!document.$cdc_asdjflasutopfhvcZLmcfl_,
        hasAutomation: !!navigator.webdriver,
    };

    return results;
}
"""


async def collect_fingerprint(page) -> dict:
    """Navigate to about:blank and collect fingerprint data via Playwright.

    Camoufox natively handles mediaDevices and deviceMemory spoofing,
    so no polyfills are needed.
    """
    await page.goto("about:blank")
    raw_data = await page.evaluate(f"({FINGERPRINT_JS})()")
    return raw_data


def analyze_fingerprint(raw_data: dict) -> dict:
    """Analyze raw fingerprint data and produce per-category pass/warn/fail + overall score."""
    categories = {}
    score = 100
    ua = raw_data.get("navigator", {}).get("userAgent", "")

    # --- Navigator ---
    nav = raw_data.get("navigator", {})
    nav_issues = []
    if nav.get("webdriver") is True:
        nav_issues.append("navigator.webdriver is true (wykrywalny jako automatyzacja)")
        score -= 30
    if nav.get("pluginsLength", 0) == 0:
        nav_issues.append("Brak pluginow (podejrzane dla desktopowej przegladarki)")
        score -= 10
    if not nav.get("languages") or len(nav.get("languages", [])) == 0:
        nav_issues.append("Brak ustawionych jezykow")
        score -= 5

    # Validate language code (BCP47: primary subtag must be valid ISO 639-1)
    lang = nav.get("language", "")
    if lang:
        primary = lang.split("-")[0].lower()
        if primary not in _VALID_LANG_CODES:
            nav_issues.append(f"Nieprawidlowy kod jezyka: '{lang}' — nie jest poprawnym kodem BCP47")
            score -= 15

    # maxTouchPoints — desktop=0, mobile/tablet=5 or 10, value 1 is a known spoofing glitch
    mtp = nav.get("maxTouchPoints")
    if mtp is not None and mtp == 1:
        nav_issues.append("maxTouchPoints=1 — anomalia, desktop powinien miec 0, ekrany dotykowe 5 lub 10")
        score -= 10

    # deviceMemory — Chrome-only API (not in Firefox spec).
    # Only flag for Chrome UAs where absence suggests restricted environment.
    if nav.get("deviceMemory") is None and "Firefox" not in ua:
        nav_issues.append("deviceMemory niedostepne — Chrome na prawdziwym PC zwraca ilosc RAM")
        score -= 5

    # DoNotTrack — only ~1% of real users enable this, making it a fingerprint signal
    dnt = nav.get("doNotTrack")
    if dnt is not None and str(dnt) == "1":
        nav_issues.append("DoNotTrack wlaczony — tylko ~1% uzytkownikow, wyroznia z tlumu")
        score -= 5

    nav_status = "pass"
    if any("webdriver" in i for i in nav_issues):
        nav_status = "fail"
    elif nav_issues:
        nav_status = "warn"

    categories["navigator"] = {
        "status": nav_status,
        "issues": nav_issues,
        "data": nav,
    }

    # --- Canvas ---
    canvas = raw_data.get("canvas", {})
    canvas_issues = []
    if not canvas.get("supported"):
        canvas_issues.append("Canvas nie jest wspierane lub zablokowane")
        score -= 10

    categories["canvas"] = {
        "status": "warn" if canvas_issues else "pass",
        "issues": canvas_issues,
        "data": {"hash": canvas.get("hash"), "supported": canvas.get("supported")},
    }

    # --- WebGL ---
    webgl = raw_data.get("webgl", {})
    webgl_issues = []
    webgl_status = "pass"
    if not webgl.get("supported"):
        webgl_issues.append("WebGL niedostepne — brak renderera GPU to natychmiastowy sygnal automatyzacji")
        score -= 25
        webgl_status = "fail"
    else:
        renderer = str(webgl.get("unmaskedRenderer", ""))
        vendor = str(webgl.get("unmaskedVendor", ""))
        if "SwiftShader" in renderer:
            webgl_issues.append("SwiftShader wykryty (typowy dla headless browsers)")
            score -= 20
            webgl_status = "fail"
        if "llvmpipe" in renderer.lower():
            webgl_issues.append("llvmpipe (software renderer) — wykrywalny jako srodowisko wirtualne")
            score -= 10
            if webgl_status != "fail":
                webgl_status = "warn"
        if not renderer or renderer == "None":
            webgl_issues.append("Brak unmaskedRenderer — podejrzane")
            score -= 15
            webgl_status = "fail"
        # ANGLE-style vendor ("Google Inc.") appears on both Chrome and Firefox
        # on Windows. Firefox has used ANGLE as WebGL backend since ~Firefox 70.
        # Only flag if the OS claims Linux/macOS (where ANGLE is not used).
        if "Google Inc" in vendor:
            is_linux_ua = "Linux" in ua and "Android" not in ua
            is_mac_ua = "Macintosh" in ua
            if is_linux_ua or is_mac_ua:
                webgl_issues.append(
                    f"WebGL vendor '{vendor}' jest w formacie ANGLE, ale UA wskazuje na {('Linux' if is_linux_ua else 'macOS')} — niespojnosc"
                )
                score -= 15
                webgl_status = "fail"
        # Ancient GPU detection — GPUs from before ~2012 paired with modern browsers
        # create temporal anomalies that anti-fraud systems flag automatically.
        renderer_lower = renderer.lower()
        _ancient_gpu_markers = [
            "radeon hd 2", "radeon hd 3", "radeon hd 4", "radeon hd 5",
            "geforce 6", "geforce 7", "geforce 8", "geforce 9",
            "geforce gt 1", "geforce gt 2", "geforce gt 3",
            "intel gma", "intel 945", "intel 965",
        ]
        if any(marker in renderer_lower for marker in _ancient_gpu_markers):
            webgl_issues.append(
                f"GPU '{renderer}' jest przestarzaly (sprzed ~2012) — anomalia z nowoczesna przegladarka"
            )
            score -= 15
            if webgl_status == "pass":
                webgl_status = "warn"

    categories["webgl"] = {
        "status": webgl_status,
        "issues": webgl_issues,
        "data": {
            "vendor": webgl.get("unmaskedVendor"),
            "renderer": webgl.get("unmaskedRenderer"),
            "version": webgl.get("version"),
        },
    }

    # --- Screen ---
    scr = raw_data.get("screen", {})
    screen_issues = []
    screen_status = "pass"
    if scr.get("width", 0) == 0 or scr.get("height", 0) == 0:
        screen_issues.append("Wymiary ekranu to zero")
        score -= 15
        screen_status = "warn"
    if scr.get("colorDepth", 0) not in [24, 30, 32, 48]:
        screen_issues.append(f"Nietypowa glebia kolorow: {scr.get('colorDepth')}")
        score -= 5
        if screen_status == "pass":
            screen_status = "warn"
    # outerWidth/outerHeight cannot exceed screen dimensions on real hardware
    outer_w = scr.get("outerWidth", 0)
    outer_h = scr.get("outerHeight", 0)
    scr_w = scr.get("width", 0)
    scr_h = scr.get("height", 0)
    if scr_w > 0 and outer_w > scr_w:
        screen_issues.append(
            f"outerWidth ({outer_w}) > screen.width ({scr_w}) — fizycznie niemozliwe"
        )
        score -= 15
        screen_status = "fail"
    if scr_h > 0 and outer_h > scr_h:
        screen_issues.append(
            f"outerHeight ({outer_h}) > screen.height ({scr_h}) — fizycznie niemozliwe"
        )
        score -= 15
        screen_status = "fail"
    # availWidth/availHeight should not exceed screen dimensions
    avail_w = scr.get("availWidth", 0)
    avail_h = scr.get("availHeight", 0)
    if scr_w > 0 and avail_w > scr_w:
        screen_issues.append(
            f"availWidth ({avail_w}) > screen.width ({scr_w}) — niespojne"
        )
        score -= 10
        if screen_status == "pass":
            screen_status = "warn"

    categories["screen"] = {
        "status": screen_status,
        "issues": screen_issues,
        "data": scr,
    }

    # --- Audio ---
    audio = raw_data.get("audio", {})
    audio_issues = []
    if not audio.get("supported"):
        audio_issues.append("AudioContext niedostepne")
        score -= 5

    categories["audio"] = {
        "status": "warn" if audio_issues else "pass",
        "issues": audio_issues,
        "data": audio,
    }

    # --- Fonts ---
    fonts = raw_data.get("fonts", {})
    fonts_issues = []
    if fonts.get("count", 0) == 0:
        fonts_issues.append("Brak wykrytych czcionek — mozliwy blad w srodowisku renderowania")
        score -= 10

    categories["fonts"] = {
        "status": "warn" if fonts_issues else "pass",
        "issues": fonts_issues,
        "data": fonts,
    }

    # --- WebRTC ---
    webrtc = raw_data.get("webrtc", {})
    webrtc_issues = []
    if not webrtc.get("mediaDevicesExists"):
        webrtc_issues.append("mediaDevices niedostepne — prawdziwe PC zawsze maja urzadzenia audio/wideo")
        score -= 10
    categories["webrtc"] = {
        "status": "warn" if webrtc_issues else "pass",
        "issues": webrtc_issues,
        "data": webrtc,
    }

    # --- Timezone ---
    tz = raw_data.get("timezone", {})
    tz_issues = []
    if not tz.get("timeZone"):
        tz_issues.append("Brak strefy czasowej")
        score -= 5

    categories["timezone"] = {
        "status": "warn" if tz_issues else "pass",
        "issues": tz_issues,
        "data": tz,
    }

    # --- Hardware consistency ---
    hw_issues = []
    hw_concurrency = nav.get("hardwareConcurrency", 0)
    webgl_renderer_str = str(raw_data.get("webgl", {}).get("unmaskedRenderer", "")).lower()
    # Flag extreme core counts with low/mid-tier GPUs
    _LOW_MID_GPU_KEYWORDS = [
        "gt 7", "gt 9", "gtx 7", "gtx 8", "gtx 9",
        "hd graphics", "hd 4", "hd 5", "hd 6",
        "radeon r5", "radeon r7", "radeon rx 4", "radeon rx 5",
        "mx1", "mx2", "mx3", "mx4",
        "intel uhd", "intel iris",
    ]
    if hw_concurrency and hw_concurrency >= 24:
        is_low_mid_gpu = any(kw in webgl_renderer_str for kw in _LOW_MID_GPU_KEYWORDS)
        if is_low_mid_gpu:
            hw_issues.append(
                f"hardwareConcurrency={hw_concurrency} z GPU klasy low/mid ({raw_data.get('webgl', {}).get('unmaskedRenderer', '')}) — niespojnosc"
            )
            score -= 10

    categories["hardware_consistency"] = {
        "status": "warn" if hw_issues else "pass",
        "issues": hw_issues,
        "data": {"hardwareConcurrency": hw_concurrency, "renderer": raw_data.get("webgl", {}).get("unmaskedRenderer")},
    }

    # --- User-Agent consistency ---
    platform = nav.get("platform", "")
    ua_issues = []
    if "Windows" in ua and "Win" not in platform:
        ua_issues.append("UA mowi Windows ale platform sie nie zgadza")
        score -= 15
    if "Linux" in ua and "Linux" not in platform:
        ua_issues.append("UA mowi Linux ale platform sie nie zgadza")
        score -= 15

    categories["user_agent"] = {
        "status": "fail" if ua_issues else "pass",
        "issues": ua_issues,
        "data": {"userAgent": ua, "platform": platform},
    }

    # --- Automation detection ---
    auto = raw_data.get("automation", {})
    auto_issues = []
    if auto.get("webdriver"):
        auto_issues.append("navigator.webdriver jest true")
    if auto.get("hasCDC"):
        auto_issues.append("Markery Chrome DevTools Protocol wykryte")
        score -= 20
    if auto.get("hasSelenium"):
        auto_issues.append("Markery Selenium wykryte")
        score -= 20
    if auto.get("hasPhantom") or auto.get("hasCallPhantom"):
        auto_issues.append("Markery PhantomJS wykryte")
        score -= 20

    categories["automation_detection"] = {
        "status": "fail" if auto_issues else "pass",
        "issues": auto_issues,
        "data": auto,
    }

    score = max(0, min(100, score))
    if score >= 80:
        overall_status = "pass"
    elif score >= 50:
        overall_status = "warn"
    else:
        overall_status = "fail"

    return {
        "categories": categories,
        "overall_score": score,
        "overall_status": overall_status,
    }
