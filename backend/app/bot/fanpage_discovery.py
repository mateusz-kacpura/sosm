"""Automatic fanpage discovery via Facebook profile switcher.

Enumerates all managed pages by opening the avatar dropdown,
clicking "See all profiles", then switching to each page to
capture its URL via /me redirect.
"""
import json as _json
import logging

from .human_imitation import HumanImitation
from . import mouse_engine

logger = logging.getLogger(__name__)

_GOTO_TIMEOUT = 15_000


async def _safe_goto(page, url: str):
    """Navigate tolerating Juggler timeout (FF149 nav events unreliable)."""
    try:
        await page.goto(url, wait_until="commit", timeout=_GOTO_TIMEOUT)
    except Exception:
        pass  # Page loads fine, events just don't fire in FF149 Juggler
    # Always wait for content to render
    await HumanImitation.human_delay(3, 5)


async def discover_fanpages(actions) -> list[dict]:
    """Discover all fanpages managed by the logged-in account.

    Args:
        actions: FBActions instance (already logged in).

    Returns:
        List of dicts: [{"fanpage_url": "...", "fanpage_name": "..."}]
    """
    from .dom_walker import _eval_js

    page = actions.page

    # --- Step 1: Capture personal identity via /me redirect ---
    logger.info("[discovery] Navigating to /me to capture personal identity")
    await _safe_goto(page, "https://www.facebook.com/me")
    await HumanImitation.human_delay(3, 5)

    # Wait for redirect (URL should no longer be /me)
    personal_url = page.url
    for _ in range(10):
        if "/me" not in page.url:
            personal_url = page.url
            break
        await HumanImitation.human_delay(1, 2)

    personal_name = await _eval_js(page, """(() => {
        const og = document.querySelector('meta[property="og:title"]');
        if (og) {
            const c = og.getAttribute('content');
            if (c) return c.replace(/\\s*[|·].*$/, '').trim();
        }
        const t = document.title.replace(/\\s*[|·-]\\s*Facebook.*$/i, '').trim();
        if (t && t !== 'Facebook') return t;
        return null;
    })()""")
    logger.info("[discovery] Personal profile: name='%s', url='%s'",
                personal_name, personal_url)

    # --- Step 2: Open profile switcher and enumerate entries ---
    if not await actions._click_profile_avatar():
        logger.error("[discovery] Could not open avatar dropdown")
        return []
    await HumanImitation.human_delay(1.5, 3)

    # Click "See all profiles" if available
    see_all = await _eval_js(page, """(() => {
        const byLabel = document.querySelector(
            "div[role='button'][aria-label*='wszystkie profile'], "
            + "div[role='button'][aria-label*='all profiles'], "
            + "div[role='button'][aria-label*='ดูโปรไฟล์ทั้งหมด']"
        );
        if (byLabel) {
            const r = byLabel.getBoundingClientRect();
            if (r.width > 30 && r.height > 20)
                return {x: r.x, y: r.y, w: r.width, h: r.height,
                        text: (byLabel.innerText || byLabel.getAttribute('aria-label') || '').trim().slice(0, 100)};
        }
        const btns = document.querySelectorAll("div[role='button'], a[role='button']");
        for (const btn of btns) {
            const text = (btn.innerText || '').trim().toLowerCase();
            if (text.includes('wszystkie profile') || text.includes('all profiles')) {
                const r = btn.getBoundingClientRect();
                if (r.width > 30 && r.height > 20 && r.y > 0)
                    return {x: r.x, y: r.y, w: r.width, h: r.height,
                            text: btn.innerText.trim().slice(0, 100)};
            }
        }
        return null;
    })()""")

    if see_all:
        logger.info("[discovery] Clicking 'See all profiles': '%s'", see_all.get("text", ""))
        await mouse_engine.click_element(page, see_all)
        await HumanImitation.human_delay(2, 4)

    # Enumerate all profile entries
    profiles = await _eval_js(page, """(() => {
        const entries = [];
        const btns = document.querySelectorAll(
            "div[role='button'][aria-label], a[role='button'][aria-label]"
        );
        for (const btn of btns) {
            const label = btn.getAttribute('aria-label') || '';
            const r = btn.getBoundingClientRect();
            if (r.width < 30 || r.height < 20 || r.y <= 0) continue;
            const m = label.match(
                /(?:Przełącz na profil|Switch to)\\s+(.+?)(?:'s profile)?$/i
            );
            if (m) {
                entries.push({
                    name: m[1].trim(),
                    x: r.x, y: r.y, w: r.width, h: r.height,
                    label: label.slice(0, 200)
                });
            }
        }
        return entries;
    })()""")

    # Close menu
    await page.keyboard.press("Escape")
    await HumanImitation.human_delay(0.5, 1)

    if not profiles:
        logger.info("[discovery] No profile entries found in switcher")
        return []

    # Filter out personal profile
    page_profiles = [
        p for p in profiles
        if personal_name and p["name"] != personal_name
    ]
    if not page_profiles and profiles:
        # If personal_name not captured, assume all entries might be pages
        # (rare fallback — the personal profile is usually the active one and not shown as "Switch to")
        page_profiles = profiles

    logger.info("[discovery] Found %d page profile(s) to check: %s",
                len(page_profiles), [p["name"] for p in page_profiles])

    # --- Step 3: Switch to each page and capture URL ---
    discovered = []
    for i, profile in enumerate(page_profiles):
        name = profile["name"]
        logger.info("[discovery] [%d/%d] Switching to page: '%s'",
                    i + 1, len(page_profiles), name)

        fanpage_url = None
        for attempt in range(2):
            if attempt > 0:
                logger.info("[discovery] Retry switch to '%s' (attempt %d)", name, attempt + 1)

            if not await _switch_to_profile_by_name(actions, page, name):
                logger.warning("[discovery] Failed to switch to '%s', skipping", name)
                break

            # After profile switch, navigate to homepage and extract page URL
            # from the nav bar profile link (the avatar link changes to the
            # current identity's profile URL). /me ALWAYS goes to personal profile.
            await _safe_goto(page, "https://www.facebook.com/")
            await HumanImitation.human_delay(2, 4)

            fanpage_url = await _extract_current_profile_url(page)
            if fanpage_url and fanpage_url != personal_url:
                break  # Switch verified
            logger.warning("[discovery] Switch not verified — URL still personal (attempt %d)", attempt + 1)
            fanpage_url = None

        # Use name from the profile switcher — navigating to the page
        # profile while acting AS the page shows "Zarządzanie stroną"
        # (admin dashboard) instead of the actual page name.
        fanpage_name = name

        if fanpage_url and fanpage_url != personal_url:
            logger.info("[discovery] Discovered: name='%s', url='%s'",
                        fanpage_name, fanpage_url)
            discovered.append({
                "fanpage_url": fanpage_url,
                "fanpage_name": fanpage_name,
            })
        else:
            logger.warning("[discovery] Could not resolve URL for '%s' (got '%s')",
                           name, fanpage_url)

    # --- Step 4: Switch back to personal profile ---
    if discovered:
        logger.info("[discovery] Switching back to personal profile")
        await actions.switch_to_personal_profile()

    logger.info("[discovery] Discovery complete: %d fanpage(s) found", len(discovered))
    return discovered


async def _extract_current_profile_url(page) -> str | None:
    """Extract the current identity's profile URL from the nav bar.

    After a page switch, the avatar link in the nav bar points to the
    current identity's profile. Works for both personal and page profiles.
    """
    from .dom_walker import _eval_js

    url = await _eval_js(page, """(() => {
        // Method 1: Profile avatar link in nav bar
        const profileLink = document.querySelector(
            'a[aria-label="Twój profil"], '
            + 'a[aria-label="Your profile"], '
            + 'a[aria-label="โปรไฟล์ของคุณ"]'
        );
        if (profileLink && profileLink.href) return profileLink.href;

        // Method 2: Avatar link with svg/image inside nav banner
        const banner = document.querySelector('div[role="banner"]');
        if (banner) {
            // The rightmost link with an image/svg is usually the profile link
            const links = banner.querySelectorAll('a[href*="/profile"], a[href*="facebook.com/"]');
            for (const link of links) {
                const href = link.getAttribute('href') || '';
                if (href.includes('/profile') || href.match(/facebook\\.com\\/[^/]+\\/?$/)) {
                    if (link.querySelector('image, img, svg')) {
                        return link.href;
                    }
                }
            }
        }

        // Method 3: Look for the profile link in the top-right account section
        const accountLinks = document.querySelectorAll(
            'div[role="navigation"] a[href*="/profile"], '
            + 'div[role="navigation"] a[href*="facebook.com/"]'
        );
        for (const link of accountLinks) {
            const href = link.getAttribute('href') || '';
            if (href.includes('/profile.php?id=') || href.match(/facebook\\.com\\/[a-zA-Z0-9.]+\\/?$/)) {
                return link.href;
            }
        }

        return null;
    })()""")

    if url:
        logger.info("[discovery] Current profile URL from nav bar: %s", url[:120])
    else:
        logger.warning("[discovery] Could not find profile URL in nav bar")

    return url


async def _switch_to_profile_by_name(actions, page, name: str) -> bool:
    """Open profile switcher, find entry by name, and click it.

    Uses Playwright locator.click() for reliable React event dispatch.
    Falls back to mouse_engine if locator approach fails.
    Retries once if the switch doesn't take effect.
    """
    from .dom_walker import _eval_js

    for attempt in range(2):
        if attempt > 0:
            logger.info("[discovery] Retry #%d for profile switch to '%s'", attempt, name)
            await HumanImitation.human_delay(2, 3)

        if not await actions._click_profile_avatar():
            return False
        await HumanImitation.human_delay(1.5, 3)

        # Try "See all profiles" first — use locator for reliable click
        see_all_selectors = [
            "div[role='button'][aria-label*='wszystkie profile']",
            "div[role='button'][aria-label*='all profiles']",
        ]
        see_all_clicked = False
        for sel in see_all_selectors:
            loc = page.locator(sel).first
            try:
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    see_all_clicked = True
                    break
            except Exception:
                continue

        if not see_all_clicked:
            # Fallback: text-based search
            see_all = await _eval_js(page, """(() => {
                const btns = document.querySelectorAll("div[role='button'], a[role='button']");
                for (const btn of btns) {
                    const text = (btn.innerText || '').trim().toLowerCase();
                    if (text.includes('wszystkie profile') || text.includes('all profiles')) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20 && r.y > 0)
                            return {x: r.x, y: r.y, w: r.width, h: r.height};
                    }
                }
                return null;
            })()""")
            if see_all:
                await mouse_engine.click_element(page, see_all)

        await HumanImitation.human_delay(2, 4)

        # Click the profile entry — scroll into view first then JS click
        # (the entry may be below the visible area of the profiles panel)
        name_json = _json.dumps(name)
        click_ok = await _eval_js(page, f"""(async () => {{
            const targetName = {name_json};
            const allBtns = document.querySelectorAll(
                "div[role='button'][aria-label], a[role='button'][aria-label]"
            );
            for (const btn of allBtns) {{
                const label = btn.getAttribute('aria-label') || '';
                if (!label.includes(targetName)) continue;
                // Scroll into view in case it's in a scrollable container
                btn.scrollIntoView({{block: 'center', behavior: 'instant'}});
                await new Promise(r => setTimeout(r, 300));
                // Dispatch full click event sequence (React needs all three)
                btn.dispatchEvent(new MouseEvent('mousedown', {{bubbles: true, cancelable: true}}));
                await new Promise(r => setTimeout(r, 80));
                btn.dispatchEvent(new MouseEvent('mouseup', {{bubbles: true, cancelable: true}}));
                btn.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                return label.slice(0, 100);
            }}
            return null;
        }})()""")

        if click_ok:
            logger.info("[discovery] Clicked profile entry (JS): '%s'", click_ok)
        else:
            logger.warning("[discovery] Entry not found for '%s'", name)
            await page.keyboard.press("Escape")
            if attempt == 0:
                continue  # retry
            return False

        # Wait for page reload — Facebook does a full reload after profile switch
        await HumanImitation.human_delay(5, 8)
        return True

    return False
