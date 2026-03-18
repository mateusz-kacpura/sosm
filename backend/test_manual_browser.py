"""Launch Camoufox browser for manual testing. Press Enter to close."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from camoufox.async_api import AsyncCamoufox
from camoufox.addons import DefaultAddons
from app.bot.browser_manager import (
    _build_real_config, _detect_system, _WEBGL_CONFIG,
)

PROFILE_DIR = "/home/s8lls/.local/share/DonutBrowser/profiles/9bf892ca-53c8-4685-b527-f87609c3f606/profile"
BINARY = "/home/s8lls/.local/share/DonutBrowser/binaries/camoufox/v149.0b9-beta.25/camoufox-bin"


async def main():
    print("Starting Camoufox v149 (with production config)...")
    print(f"Binary: {BINARY}")
    print(f"Profile: {PROFILE_DIR}")

    # Use production config (system detection, real fonts, etc.)
    config = _build_real_config({})
    sys_info = _detect_system()

    print(f"Config: {len(config)} keys, screen={sys_info['screen_width']}x{sys_info['screen_height']}, "
          f"locale={sys_info['language']}, cores={sys_info['cpu_count']}")

    cm = AsyncCamoufox(
        persistent_context=True,
        user_data_dir=PROFILE_DIR,
        executable_path=BINARY,
        headless=False,
        os="linux",
        ff_version=149,
        window=(sys_info["outer_width"], sys_info["outer_height"]),
        viewport={"width": sys_info["inner_width"], "height": sys_info["inner_height"]},
        webgl_config=_WEBGL_CONFIG,
        exclude_addons=list(DefaultAddons),
        i_know_what_im_doing=True,
        config=config,
        locale=sys_info["language"],
        color_scheme="dark" if sys_info["dark_theme"] else "light",
        firefox_user_prefs={
            "intl.locale.requested": sys_info["language"],
            "ui.systemUsesDarkTheme": 1 if sys_info["dark_theme"] else 0,
        },
        timeout=60000,
    )
    print("Launching...")
    context = await cm.__aenter__()
    print("SUCCESS: Browser connected via Playwright!")

    if context.pages:
        page = context.pages[0]
    else:
        page = await context.new_page()

    try:
        await page.goto("https://tls.peet.ws/api/all", timeout=30000)
        print("Navigated to tls.peet.ws/api/all")
    except Exception as e:
        print(f"goto failed (navigate manually): {e}")
    print("Browser is open. Test URLs:")
    print("  1. https://tls.peet.ws/api/all        — TLS/JA3/HTTP2 fingerprint")
    print("  2. https://abrahamjuliot.github.io/creepjs/  — CreepJS (comprehensive)")
    print("  3. https://bot.sannysoft.com/           — Bot detection")
    print("  4. https://browserleaks.com/webrtc      — WebRTC IP leak")
    print("  5. https://browserleaks.com/canvas      — Canvas fingerprint")
    print("  6. https://ipleak.net/                  — IP/DNS leak")
    print("Close this script (Ctrl+C) to shut down the browser.")

    try:
        await asyncio.sleep(7200)  # Keep open 2 hours
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    await cm.__aexit__(None, None, None)
    print("Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
