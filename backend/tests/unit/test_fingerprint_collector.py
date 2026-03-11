from app.bot.fingerprint_collector import analyze_fingerprint


def _make_good_fingerprint():
    """Return a clean fingerprint dict that should pass all checks."""
    return {
        "navigator": {
            "webdriver": False,
            "userAgent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
            "platform": "Linux x86_64",
            "language": "en-US",
            "languages": ["en-US", "en"],
            "hardwareConcurrency": 8,
            "deviceMemory": 8,
            "maxTouchPoints": 0,
            "vendor": "",
            "pluginsLength": 5,
            "plugins": ["PDF Viewer", "Chrome PDF Viewer", "Chromium PDF Viewer", "Microsoft Edge PDF Viewer", "WebKit built-in PDF"],
            "cookieEnabled": True,
            "doNotTrack": None,
            "pdfViewerEnabled": True,
        },
        "screen": {
            "width": 1920,
            "height": 1080,
            "availWidth": 1920,
            "availHeight": 1080,
            "colorDepth": 24,
            "pixelDepth": 24,
            "devicePixelRatio": 1,
            "outerWidth": 1920,
            "outerHeight": 1080,
            "innerWidth": 1920,
            "innerHeight": 969,
        },
        "canvas": {
            "hash": "-12345678",
            "supported": True,
        },
        "webgl": {
            "vendor": "Mozilla",
            "renderer": "Mozilla",
            "unmaskedVendor": "NVIDIA Corporation",
            "unmaskedRenderer": "NVIDIA GeForce GTX 1080/PCIe/SSE2",
            "version": "WebGL 1.0",
            "shadingLanguageVersion": "WebGL GLSL ES 1.0",
            "extensionsCount": 30,
            "supported": True,
        },
        "audio": {
            "sampleRate": 44100,
            "state": "suspended",
            "channelCount": 2,
            "maxChannelCount": 0,
            "supported": True,
        },
        "timezone": {
            "offset": -60,
            "timeZone": "Europe/Warsaw",
            "locale": "en-US",
        },
        "webrtc": {
            "rtcPeerConnectionExists": True,
            "mediaDevicesExists": True,
        },
        "fonts": {
            "detected": ["Arial", "Verdana", "Times New Roman", "Courier New", "Georgia"],
            "count": 5,
        },
        "automation": {
            "webdriver": False,
            "hasChrome": False,
            "hasCallPhantom": False,
            "hasPhantom": False,
            "hasNightmare": False,
            "hasSelenium": False,
            "hasCDC": False,
            "hasAutomation": False,
        },
    }


class TestAnalyzeFingerprintPerfect:
    def test_perfect_fingerprint_scores_high(self):
        data = _make_good_fingerprint()
        result = analyze_fingerprint(data)
        assert result["overall_score"] >= 80
        assert result["overall_status"] == "pass"

    def test_all_categories_pass(self):
        data = _make_good_fingerprint()
        result = analyze_fingerprint(data)
        for name, cat in result["categories"].items():
            assert cat["status"] == "pass", f"{name} should pass but got {cat['status']}"


class TestAnalyzeFingerprintFailures:
    def test_webdriver_true_causes_fail(self):
        data = _make_good_fingerprint()
        data["navigator"]["webdriver"] = True
        data["automation"]["webdriver"] = True
        data["automation"]["hasAutomation"] = True
        result = analyze_fingerprint(data)
        assert result["categories"]["navigator"]["status"] == "fail"
        assert result["categories"]["automation_detection"]["status"] == "fail"
        assert result["overall_score"] < 80

    def test_swiftshader_detected_fails_webgl(self):
        data = _make_good_fingerprint()
        data["webgl"]["unmaskedRenderer"] = "Google SwiftShader"
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "fail"
        assert result["overall_score"] <= 80

    def test_ua_platform_mismatch_windows(self):
        data = _make_good_fingerprint()
        data["navigator"]["userAgent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/128.0"
        data["navigator"]["platform"] = "Linux x86_64"
        result = analyze_fingerprint(data)
        assert result["categories"]["user_agent"]["status"] == "fail"

    def test_cdc_markers_detected(self):
        data = _make_good_fingerprint()
        data["automation"]["hasCDC"] = True
        result = analyze_fingerprint(data)
        assert result["categories"]["automation_detection"]["status"] == "fail"
        assert result["overall_score"] <= 80

    def test_webgl_unsupported_causes_fail(self):
        data = _make_good_fingerprint()
        data["webgl"] = {"supported": False}
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "fail"
        assert result["overall_score"] <= 75

    def test_webgl_empty_renderer_causes_fail(self):
        data = _make_good_fingerprint()
        data["webgl"]["unmaskedRenderer"] = None
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "fail"

    def test_outer_width_exceeds_screen_width_causes_fail(self):
        data = _make_good_fingerprint()
        data["screen"]["outerWidth"] = 2190
        data["screen"]["width"] = 2176
        result = analyze_fingerprint(data)
        assert result["categories"]["screen"]["status"] == "fail"
        assert any("outerWidth" in i for i in result["categories"]["screen"]["issues"])

    def test_outer_height_exceeds_screen_height_causes_fail(self):
        data = _make_good_fingerprint()
        data["screen"]["outerHeight"] = 1200
        data["screen"]["height"] = 1080
        result = analyze_fingerprint(data)
        assert result["categories"]["screen"]["status"] == "fail"
        assert any("outerHeight" in i for i in result["categories"]["screen"]["issues"])

    def test_invalid_language_code_causes_warn(self):
        data = _make_good_fingerprint()
        data["navigator"]["language"] = "tts-TH"
        result = analyze_fingerprint(data)
        assert result["categories"]["navigator"]["status"] == "warn"
        assert any("BCP47" in i for i in result["categories"]["navigator"]["issues"])
        assert result["overall_score"] < 100


class TestAnalyzeFingerprintWarnings:
    def test_no_plugins_warns(self):
        data = _make_good_fingerprint()
        data["navigator"]["pluginsLength"] = 0
        result = analyze_fingerprint(data)
        assert result["categories"]["navigator"]["status"] == "warn"

    def test_canvas_not_supported_warns(self):
        data = _make_good_fingerprint()
        data["canvas"] = {"supported": False}
        result = analyze_fingerprint(data)
        assert result["categories"]["canvas"]["status"] == "warn"

    def test_zero_font_count_warns(self):
        """Zero fonts detected indicates a rendering environment error."""
        data = _make_good_fingerprint()
        data["fonts"] = {"detected": [], "count": 0}
        result = analyze_fingerprint(data)
        assert result["categories"]["fonts"]["status"] == "warn"

    def test_low_font_count_passes(self):
        """Low font count (e.g. 3) is expected with Camoufox RFP — should NOT warn."""
        data = _make_good_fingerprint()
        data["fonts"] = {"detected": ["Arial", "Times New Roman", "Courier New"], "count": 3}
        result = analyze_fingerprint(data)
        assert result["categories"]["fonts"]["status"] == "pass"

    def test_zero_screen_dimensions_warns(self):
        data = _make_good_fingerprint()
        data["screen"]["width"] = 0
        data["screen"]["height"] = 0
        result = analyze_fingerprint(data)
        assert result["categories"]["screen"]["status"] == "warn"

    def test_llvmpipe_renderer_warns(self):
        data = _make_good_fingerprint()
        data["webgl"]["unmaskedRenderer"] = "llvmpipe (LLVM 15.0.6, 256 bits)"
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "warn"
        assert any("llvmpipe" in i for i in result["categories"]["webgl"]["issues"])


class TestAnalyzeFingerprintNewVectors:
    def test_dnt_enabled_warns(self):
        data = _make_good_fingerprint()
        data["navigator"]["doNotTrack"] = "1"
        result = analyze_fingerprint(data)
        assert result["categories"]["navigator"]["status"] == "warn"
        assert any("DoNotTrack" in i for i in result["categories"]["navigator"]["issues"])

    def test_media_devices_missing_warns(self):
        data = _make_good_fingerprint()
        data["webrtc"]["mediaDevicesExists"] = False
        result = analyze_fingerprint(data)
        assert result["categories"]["webrtc"]["status"] == "warn"
        assert any("mediaDevices" in i for i in result["categories"]["webrtc"]["issues"])

    def test_angle_vendor_with_firefox_ua_fails(self):
        data = _make_good_fingerprint()
        data["navigator"]["userAgent"] = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
        data["webgl"]["unmaskedVendor"] = "Google Inc. (NVIDIA)"
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "fail"
        assert any("ANGLE" in i for i in result["categories"]["webgl"]["issues"])

    def test_angle_vendor_with_chrome_ua_passes(self):
        """ANGLE vendor is normal for Chrome — should NOT fail."""
        data = _make_good_fingerprint()
        data["navigator"]["userAgent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0"
        data["webgl"]["unmaskedVendor"] = "Google Inc. (NVIDIA)"
        result = analyze_fingerprint(data)
        # WebGL should pass (ANGLE is expected for Chrome)
        assert result["categories"]["webgl"]["status"] == "pass"

    def test_high_cores_low_gpu_warns(self):
        data = _make_good_fingerprint()
        data["navigator"]["hardwareConcurrency"] = 32
        data["webgl"]["unmaskedRenderer"] = "NVIDIA GeForce GTX 980/PCIe/SSE2"
        result = analyze_fingerprint(data)
        assert result["categories"]["hardware_consistency"]["status"] == "warn"
        assert any("hardwareConcurrency" in i for i in result["categories"]["hardware_consistency"]["issues"])

    def test_normal_cores_gpu_passes(self):
        data = _make_good_fingerprint()
        data["navigator"]["hardwareConcurrency"] = 8
        data["webgl"]["unmaskedRenderer"] = "NVIDIA GeForce GTX 1080/PCIe/SSE2"
        result = analyze_fingerprint(data)
        assert result["categories"]["hardware_consistency"]["status"] == "pass"

    def test_max_touch_points_1_warns(self):
        data = _make_good_fingerprint()
        data["navigator"]["maxTouchPoints"] = 1
        result = analyze_fingerprint(data)
        assert result["categories"]["navigator"]["status"] == "warn"
        assert any("maxTouchPoints" in i for i in result["categories"]["navigator"]["issues"])

    def test_max_touch_points_0_passes(self):
        data = _make_good_fingerprint()
        data["navigator"]["maxTouchPoints"] = 0
        result = analyze_fingerprint(data)
        # maxTouchPoints=0 is fine for desktop
        assert not any("maxTouchPoints" in i for i in result["categories"]["navigator"]["issues"])

    def test_ancient_gpu_warns(self):
        """GPUs from before ~2012 are temporal anomalies with modern browsers."""
        data = _make_good_fingerprint()
        data["webgl"]["unmaskedRenderer"] = "Radeon HD 3200 Graphics, or similar"
        result = analyze_fingerprint(data)
        assert result["categories"]["webgl"]["status"] == "warn"
        assert any("przestarzaly" in i for i in result["categories"]["webgl"]["issues"])

    def test_modern_gpu_passes(self):
        """Modern integrated GPU should not trigger age warning."""
        data = _make_good_fingerprint()
        data["webgl"]["unmaskedRenderer"] = "Intel(R) HD Graphics, or similar"
        data["webgl"]["unmaskedVendor"] = "Intel"
        result = analyze_fingerprint(data)
        assert not any("przestarzaly" in i for i in result["categories"]["webgl"]["issues"])


class TestAnalyzeFingerprintScoreBounds:
    def test_score_clamped_to_0_minimum(self):
        data = _make_good_fingerprint()
        data["navigator"]["webdriver"] = True
        data["navigator"]["pluginsLength"] = 0
        data["navigator"]["languages"] = []
        data["canvas"] = {"supported": False}
        data["webgl"]["unmaskedRenderer"] = "Google SwiftShader"
        data["screen"]["width"] = 0
        data["screen"]["height"] = 0
        data["screen"]["colorDepth"] = 1
        data["audio"] = {"supported": False}
        data["fonts"] = {"detected": [], "count": 0}
        data["timezone"] = {}
        data["automation"]["webdriver"] = True
        data["automation"]["hasCDC"] = True
        data["automation"]["hasSelenium"] = True
        data["automation"]["hasPhantom"] = True
        result = analyze_fingerprint(data)
        assert result["overall_score"] >= 0
        assert result["overall_status"] == "fail"

    def test_score_never_exceeds_100(self):
        data = _make_good_fingerprint()
        result = analyze_fingerprint(data)
        assert result["overall_score"] <= 100
