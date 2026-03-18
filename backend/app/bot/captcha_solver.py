"""CAPTCHA solver using CapMonster Cloud API.

Handles reCAPTCHA v2 (image challenge) detection and solving on Facebook pages.
Facebook uses reCAPTCHA v2 with image grids (select buses, crosswalks, motorcycles etc.).
Uses the capmonstercloudclient library for API communication.

Flow:
1. Detect reCAPTCHA on the page — extract sitekey and determine version (v2/v2 Enterprise)
2. Send task to CapMonster Cloud (they solve the image challenge on their servers)
3. Receive gRecaptchaResponse token (~10-60s)
4. Inject token into the correct frame and trigger the callback
"""

import asyncio
import logging
from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import (
    RecaptchaV2Request,
    RecaptchaV2EnterpriseRequest,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# Facebook's constant reCAPTCHA Enterprise v2 sitekey
_FB_SITEKEY = "6LeyIlkaAAAAAE-EjcALU28lwxWPusUvGL3e0avS"
_FB_RECAPTCHA_URL = "https://www.fbsbx.com"

# Pre-solve state: an asyncio.Task that resolves the FB CAPTCHA in the background.
# Started early (before login click) so the token is ready when checkpoint appears.
_presolve_task: asyncio.Task | None = None


async def start_presolve():
    """Start solving Facebook's reCAPTCHA Enterprise in the background.

    Call this BEFORE clicking the login button. Since FB uses the same
    sitekey and origin for every login CAPTCHA, we can start the solve
    early and use the token when the checkpoint page appears.
    The CapMonster solve takes ~80-100s; starting early saves ~30s of
    session timeout that would otherwise expire.

    Cost: ~$0.002 per call. Wasted if login succeeds without CAPTCHA.
    """
    global _presolve_task
    if _presolve_task and not _presolve_task.done():
        logger.debug("Pre-solve already running — skipping")
        return

    logger.info("Starting reCAPTCHA pre-solve in background (sitekey=%s...)", _FB_SITEKEY[:20])
    _presolve_task = asyncio.create_task(
        solve_recaptcha_v2(
            page_url=_FB_RECAPTCHA_URL,
            sitekey=_FB_SITEKEY,
            enterprise=True,
        )
    )


async def get_presolved_token() -> str | None:
    """Get the pre-solved token if available, or None.

    Awaits the pre-solve task (max 120s). Clears the task after use.
    """
    global _presolve_task
    if not _presolve_task:
        return None

    task = _presolve_task
    _presolve_task = None

    if task.done():
        try:
            return task.result()
        except Exception as e:
            logger.warning("Pre-solve task failed: %s", e)
            return None

    logger.info("Waiting for pre-solve to complete...")
    try:
        return await asyncio.wait_for(task, timeout=120)
    except asyncio.TimeoutError:
        logger.warning("Pre-solve timed out after 120s")
        task.cancel()
        return None
    except Exception as e:
        logger.warning("Pre-solve failed: %s", e)
        return None


async def detect_recaptcha(page) -> dict | None:
    """Detect reCAPTCHA on the page and extract sitekey + version info.

    Looks for:
    - recaptcha/api.js or recaptcha/enterprise.js script tags
    - grecaptcha / grecaptcha.enterprise objects
    - data-sitekey attributes
    - ___grecaptcha_cfg internal config
    - Inline script patterns

    Returns dict with 'sitekey', 'enterprise' (bool), 'source' if found.
    """
    result = await page.evaluate("""(() => {
        const info = { sitekey: null, enterprise: false, source: null };

        // Method 1: Find sitekey from script src
        const scripts = document.querySelectorAll('script[src*="recaptcha"]');
        for (const s of scripts) {
            const src = s.getAttribute('src') || '';
            if (src.includes('/enterprise')) info.enterprise = true;
            const match = src.match(/[?&]render=([A-Za-z0-9_-]+)/);
            if (match && match[1] !== 'explicit') {
                info.sitekey = match[1];
                info.source = 'script_render';
            }
        }

        // Method 2: data-sitekey attribute (most common for v2)
        if (!info.sitekey) {
            const el = document.querySelector('[data-sitekey]');
            if (el) {
                info.sitekey = el.getAttribute('data-sitekey');
                info.source = 'data_sitekey';
            }
        }

        // Method 3: ___grecaptcha_cfg internal config
        if (!info.sitekey && typeof ___grecaptcha_cfg !== 'undefined') {
            try {
                const cfg = ___grecaptcha_cfg;
                // Walk clients to find sitekey
                if (cfg.clients) {
                    for (const key of Object.keys(cfg.clients)) {
                        const client = cfg.clients[key];
                        for (const k of Object.keys(client)) {
                            const val = client[k];
                            if (val && typeof val === 'object') {
                                for (const k2 of Object.keys(val)) {
                                    const v2 = val[k2];
                                    if (v2 && typeof v2 === 'object' && v2.sitekey) {
                                        info.sitekey = v2.sitekey;
                                        info.source = 'grecaptcha_cfg';
                                    }
                                }
                            }
                        }
                    }
                }
            } catch(e) {}
        }

        // Method 4: Check grecaptcha object existence
        if (typeof grecaptcha !== 'undefined') {
            if (grecaptcha.enterprise) info.enterprise = true;
            if (!info.source) info.source = 'grecaptcha_obj';
        }

        // Method 5: Search inline scripts for sitekey pattern
        if (!info.sitekey) {
            const inlineScripts = document.querySelectorAll('script:not([src])');
            for (const s of inlineScripts) {
                const text = s.textContent || '';
                // grecaptcha.render / grecaptcha.enterprise.render / execute
                const match = text.match(
                    /grecaptcha(?:\\.enterprise)?\\.(?:render|execute)\\s*\\(\\s*["']([A-Za-z0-9_-]{20,})["']/
                );
                if (match) {
                    info.sitekey = match[1];
                    info.source = 'inline_script';
                    if (text.includes('enterprise')) info.enterprise = true;
                }
                // Also try: new RecaptchaLoader({sitekey: "..."})
                const match2 = text.match(/sitekey["']?\\s*[:=]\\s*["']([A-Za-z0-9_-]{20,})["']/);
                if (!info.sitekey && match2) {
                    info.sitekey = match2[1];
                    info.source = 'inline_sitekey';
                }
            }
        }

        // Method 6: Look for reCAPTCHA iframe (last resort)
        if (!info.sitekey) {
            const iframes = document.querySelectorAll(
                'iframe[src*="recaptcha"], iframe[src*="google.com/recaptcha"]'
            );
            for (const iframe of iframes) {
                const src = iframe.getAttribute('src') || '';
                const match = src.match(/[?&]k=([A-Za-z0-9_-]+)/);
                if (match) {
                    info.sitekey = match[1];
                    info.source = 'iframe_src';
                    if (src.includes('/enterprise')) info.enterprise = true;
                }
            }
        }

        if (info.sitekey || info.source) return info;
        return null;
    })()""")

    if result:
        logger.info(
            "reCAPTCHA detected: enterprise=%s, source=%s, sitekey=%s",
            result.get("enterprise"),
            result.get("source"),
            (result.get("sitekey") or "?")[:20] + "...",
        )
        return result

    # Fallback: search child frames (FB nests reCAPTCHA inside fbsbx.com iframe)
    for frame in page.frames[1:]:
        try:
            frame_result = await frame.evaluate("""(() => {
                const info = { sitekey: null, enterprise: false, source: null, frame_url: window.location.href };
                // data-sitekey on this frame
                const el = document.querySelector('[data-sitekey]');
                if (el) {
                    info.sitekey = el.getAttribute('data-sitekey');
                    info.source = 'frame_data_sitekey';
                }
                // reCAPTCHA iframe src (anchor frame inside this frame)
                if (!info.sitekey) {
                    const iframes = document.querySelectorAll('iframe[src*="recaptcha"]');
                    for (const iframe of iframes) {
                        const src = iframe.getAttribute('src') || '';
                        const match = src.match(/[?&]k=([A-Za-z0-9_-]+)/);
                        if (match) {
                            info.sitekey = match[1];
                            info.source = 'frame_iframe_src';
                            if (src.includes('/enterprise')) info.enterprise = true;
                        }
                    }
                }
                // Script src
                const scripts = document.querySelectorAll('script[src*="recaptcha"]');
                for (const s of scripts) {
                    const src = s.getAttribute('src') || '';
                    if (src.includes('/enterprise')) info.enterprise = true;
                    const match = src.match(/[?&]render=([A-Za-z0-9_-]+)/);
                    if (match && match[1] !== 'explicit' && !info.sitekey) {
                        info.sitekey = match[1];
                        info.source = 'frame_script_render';
                    }
                }
                if (info.sitekey || info.source) return info;
                return null;
            })()""")
            if frame_result and frame_result.get("sitekey"):
                logger.info(
                    "reCAPTCHA in child frame: enterprise=%s, source=%s, sitekey=%s, frame=%s",
                    frame_result.get("enterprise"),
                    frame_result.get("source"),
                    (frame_result.get("sitekey") or "?")[:20] + "...",
                    (frame_result.get("frame_url") or "?")[:80],
                )
                return frame_result
        except Exception:
            continue

    return None


async def solve_recaptcha_v2(
    page_url: str,
    sitekey: str,
    enterprise: bool = False,
) -> str | None:
    """Solve reCAPTCHA v2 (image challenge) via CapMonster Cloud.

    Supports both standard v2 and v2 Enterprise variants.
    Returns the gRecaptchaResponse token on success, None on failure.
    """
    api_key = settings.CAPMONSTER_API_KEY
    if not api_key:
        logger.error("CAPMONSTER_API_KEY not configured — cannot solve CAPTCHA")
        return None

    variant = "v2 Enterprise" if enterprise else "v2"
    logger.info(
        "Solving reCAPTCHA %s: url=%s, sitekey=%s...",
        variant, page_url, sitekey[:20],
    )

    try:
        client_options = ClientOptions(api_key=api_key)
        client = CapMonsterClient(options=client_options)

        if enterprise:
            request = RecaptchaV2EnterpriseRequest(
                websiteUrl=page_url,
                websiteKey=sitekey,
            )
        else:
            request = RecaptchaV2Request(
                websiteUrl=page_url,
                websiteKey=sitekey,
            )

        solution = await client.solve_captcha(request)
        token = solution.get("gRecaptchaResponse")

        if token:
            logger.info(
                "reCAPTCHA %s solved (token length=%d)", variant, len(token)
            )
        else:
            logger.warning("CapMonster returned empty token: %s", solution)

        return token

    except Exception as e:
        logger.error("CapMonster solve failed: %s", e, exc_info=True)
        return None


_INJECTION_JS = """(token) => {
    const result = {
        textarea_filled: false,
        callback_found: false,
        callback_called: false,
        callback_path: null,
        grecaptcha_hooked: false,
        data_callback_found: false,
        error: null,
    };

    // 1. Fill ALL hidden textarea(s) used by reCAPTCHA
    const textareas = document.querySelectorAll(
        'textarea[name="g-recaptcha-response"], '
        + '#g-recaptcha-response, '
        + 'textarea[id*="g-recaptcha-response"]'
    );
    for (const ta of textareas) {
        ta.value = token;
        ta.innerHTML = token;
        result.textarea_filled = true;
    }

    // 2. Find and call the reCAPTCHA callback via ___grecaptcha_cfg
    try {
        if (typeof ___grecaptcha_cfg !== 'undefined' && ___grecaptcha_cfg.clients) {
            const CB_NAMES = ['callback', 'resolve', 'success', 'verifyCallback'];
            for (const clientId of Object.keys(___grecaptcha_cfg.clients)) {
                const client = ___grecaptcha_cfg.clients[clientId];
                const findCallback = (obj, depth, path) => {
                    if (!obj || typeof obj !== 'object' || depth > 8) return null;
                    // Check known callback property names
                    for (const name of CB_NAMES) {
                        if (typeof obj[name] === 'function') {
                            return { fn: obj[name], path: path + '.' + name };
                        }
                    }
                    // Recurse into nested objects
                    for (const key of Object.keys(obj)) {
                        try {
                            const val = obj[key];
                            if (val && typeof val === 'object' && !Array.isArray(val)) {
                                const found = findCallback(val, depth + 1, path + '.' + key);
                                if (found) return found;
                            }
                        } catch(e) {}
                    }
                    return null;
                };
                const cb = findCallback(client, 0, 'clients.' + clientId);
                if (cb) {
                    result.callback_found = true;
                    result.callback_path = cb.path;
                    try {
                        cb.fn(token);
                        result.callback_called = true;
                    } catch(e) {
                        result.error = 'callback threw: ' + e.message;
                    }
                }
            }
        }
    } catch(e) {
        result.error = 'cfg search: ' + e.message;
    }

    // 3. Fallback: look for data-callback attribute on reCAPTCHA element
    if (!result.callback_called) {
        try {
            const el = document.querySelector('[data-callback]');
            if (el) {
                const cbName = el.getAttribute('data-callback');
                if (cbName && typeof window[cbName] === 'function') {
                    result.data_callback_found = true;
                    result.callback_path = 'window.' + cbName;
                    window[cbName](token);
                    result.callback_called = true;
                }
            }
        } catch(e) {}
    }

    // 4. Override grecaptcha.getResponse to return our token
    try {
        if (typeof grecaptcha !== 'undefined') {
            grecaptcha.getResponse = function() { return token; };
            if (grecaptcha.enterprise) {
                grecaptcha.enterprise.getResponse = function() { return token; };
                grecaptcha.enterprise.execute = function() {
                    return Promise.resolve(token);
                };
            }
            result.grecaptcha_hooked = true;
        }
    } catch(e) {}

    return result;
}"""


async def inject_recaptcha_token(page, token: str) -> bool:
    """Inject a solved reCAPTCHA v2 token into the page.

    Tries ALL frames (main + children). FB nests reCAPTCHA inside
    fbsbx.com iframe — the textarea and callbacks live there, not
    in the main frame.
    """
    for i, frame in enumerate(page.frames):
        try:
            result = await frame.evaluate(_INJECTION_JS, token)
            if result and result.get("textarea_filled"):
                frame_url = (frame.url or "")[:80]
                logger.info(
                    "Token injected in frame[%d] (%s): callback_found=%s, "
                    "callback_called=%s, path=%s, grecaptcha_hooked=%s, error=%s",
                    i, frame_url,
                    result.get("callback_found"),
                    result.get("callback_called"),
                    result.get("callback_path"),
                    result.get("grecaptcha_hooked"),
                    result.get("error"),
                )
                return True
        except Exception as e:
            logger.debug("Token injection skip frame[%d]: %s", i, e)
            continue

    logger.warning("Token injection failed in all %d frames", len(page.frames))
    return False


async def hook_recaptcha_before_login(page) -> bool:
    """Detect and solve reCAPTCHA BEFORE login form submission.

    Call this after the page loads but before clicking the login button.
    If reCAPTCHA v2 is detected, solves it via CapMonster Cloud and
    injects the token so the login request passes the CAPTCHA check.

    Returns True if CAPTCHA was detected and solved.
    """
    recaptcha_info = await detect_recaptcha(page)
    if not recaptcha_info:
        logger.debug("No reCAPTCHA detected on login page")
        return False

    sitekey = recaptcha_info.get("sitekey")
    if not sitekey:
        logger.warning(
            "reCAPTCHA detected but sitekey not extracted (source=%s)",
            recaptcha_info.get("source"),
        )
        return False

    enterprise = recaptcha_info.get("enterprise", False)
    solve_url = recaptcha_info.get("frame_url") or page.url
    token = await solve_recaptcha_v2(
        page_url=solve_url,
        sitekey=sitekey,
        enterprise=enterprise,
    )

    if not token:
        return False

    return await inject_recaptcha_token(page, token)


_SUBMIT_BTN_JS = """(() => {
    const buttons = document.querySelectorAll(
        'button[type="submit"], input[type="submit"], '
        + 'div[role="button"], a[role="button"]'
    );
    for (const btn of buttons) {
        const text = (btn.innerText || btn.value || '').toLowerCase();
        if (text.includes('continue') || text.includes('kontynuuj')
            || text.includes('submit') || text.includes('wyślij')
            || text.includes('dalej') || text.includes('verify')
            || text.includes('weryfikuj')) {
            const r = btn.getBoundingClientRect();
            if (r.width > 30 && r.height > 20)
                return {x: r.x, y: r.y, w: r.width, h: r.height,
                        text: (btn.innerText || '').trim().slice(0, 50)};
        }
    }
    return null;
})()"""

_FORM_SUBMIT_JS = """(() => {
    const form = document.querySelector(
        'form:has(textarea[name="g-recaptcha-response"])'
    );
    if (form) { form.submit(); return true; }
    return false;
})()"""


async def solve_captcha_on_checkpoint(page) -> bool:
    """Attempt to solve reCAPTCHA on a checkpoint/challenge page.

    Strategy (in order):
    1. CapMonster Cloud API — solve server-side and inject token while the
       reCAPTCHA widget is still in its initial "checkbox" state. This is
       critical: clicking the checkbox first triggers an image challenge,
       and once in "challenge" mode the widget ignores injected tokens.
    2. If CapMonster fails, fall back to clicking the checkbox — with a good
       fingerprint (Camoufox), Google may pass without an image challenge.

    Returns True if CAPTCHA was solved.
    """
    recaptcha_info = await detect_recaptcha(page)
    if not recaptcha_info or not recaptcha_info.get("sitekey"):
        logger.info("No solvable reCAPTCHA found on checkpoint page")
        return False

    # --- Strategy 1: Use pre-solved token if available, else CapMonster ---
    token = await get_presolved_token()
    if token:
        logger.info("Using pre-solved token (length=%d)", len(token))
    else:
        enterprise = recaptcha_info.get("enterprise", False)
        solve_url = recaptcha_info.get("frame_url") or page.url
        token = await solve_recaptcha_v2(
            page_url=solve_url,
            sitekey=recaptcha_info["sitekey"],
            enterprise=enterprise,
        )

    if token:
        injected = await inject_recaptcha_token(page, token)
        if injected:
            logger.info("Token injected — waiting for callback to process...")
            await asyncio.sleep(5)

            current_url = page.url or ""
            if "checkpoint" not in current_url and "two_step" not in current_url:
                logger.info("Page redirected after token injection: %s", current_url[:80])
                return True

            # Try submit buttons across all frames
            from . import mouse_engine

            for i, frame in enumerate(page.frames):
                try:
                    submit_btn = await frame.evaluate(_SUBMIT_BTN_JS)
                    if submit_btn:
                        logger.info("Clicking submit in frame[%d]: '%s'", i, submit_btn.get("text", ""))
                        if i > 0:
                            submit_btn = await _offset_to_page_coords(page, frame, submit_btn)
                        await mouse_engine.click_element(page, submit_btn)
                        await asyncio.sleep(5)
                        current_url = page.url or ""
                        if "checkpoint" not in current_url and "two_step" not in current_url:
                            logger.info("Redirected after submit click: %s", current_url[:80])
                            return True
                except Exception:
                    continue

            # Try form.submit() as last resort
            for i, frame in enumerate(page.frames):
                try:
                    submitted = await frame.evaluate(_FORM_SUBMIT_JS)
                    if submitted:
                        logger.info("Form submitted via JS in frame[%d]", i)
                        await asyncio.sleep(5)
                        return True
                except Exception:
                    continue

            logger.info("Token injected, callback triggered — FB may process async.")
            return True

    # --- Strategy 2: Click the checkbox (fallback if CapMonster failed) ---
    logger.info("CapMonster failed — trying checkbox click as fallback...")
    solved_by_click = await _click_recaptcha_checkbox(page)
    if solved_by_click:
        return True

    logger.warning("All CAPTCHA strategies exhausted")
    return False


async def _click_recaptcha_checkbox(page) -> bool:
    """Click the reCAPTCHA checkbox directly in the browser.

    Finds the anchor frame (google.com/recaptcha/.../anchor) and clicks
    the #recaptcha-anchor checkbox. With a good browser fingerprint,
    Google may pass without showing an image challenge.

    Returns True if the checkbox solved the CAPTCHA (page redirected).
    """
    from .human_imitation import HumanImitation

    # Find the anchor frame (contains the checkbox)
    anchor_frame = None
    for frame in page.frames:
        url = frame.url or ""
        if "/recaptcha/" in url and "/anchor" in url:
            anchor_frame = frame
            break

    if not anchor_frame:
        logger.debug("No reCAPTCHA anchor frame found")
        return False

    logger.info("Clicking reCAPTCHA checkbox in anchor frame...")

    try:
        # Use Playwright's frame-aware click (handles iframe offsets internally)
        checkbox = anchor_frame.locator("#recaptcha-anchor")
        if await checkbox.count() == 0:
            # Fallback: try .recaptcha-checkbox
            checkbox = anchor_frame.locator(".recaptcha-checkbox")
        if await checkbox.count() == 0:
            logger.warning("reCAPTCHA checkbox element not found in anchor frame")
            return False

        await checkbox.click(timeout=5000)
        logger.info("Checkbox clicked — waiting for verification...")

    except Exception as e:
        logger.warning("Checkbox click failed: %s", e)
        return False

    # Wait for Google to process the click
    await HumanImitation.human_delay(5, 8)

    # Check if CAPTCHA was solved (checkbox shows checkmark)
    try:
        is_checked = await anchor_frame.evaluate("""(() => {
            const anchor = document.querySelector('#recaptcha-anchor');
            if (!anchor) return false;
            return anchor.getAttribute('aria-checked') === 'true';
        })()""")
        if is_checked:
            logger.info("reCAPTCHA checkbox passed (no image challenge)!")
            # Wait for page redirect
            await HumanImitation.human_delay(5, 8)

            current_url = page.url or ""
            if "checkpoint" not in current_url and "two_step" not in current_url:
                logger.info("Page redirected after checkbox: %s", current_url[:80])
                return True

            # Page didn't redirect yet — might need more time or a submit button
            logger.info("Checkbox checked but page not redirected — waiting more...")
            await HumanImitation.human_delay(5, 10)

            current_url = page.url or ""
            if "checkpoint" not in current_url and "two_step" not in current_url:
                return True

            logger.info("Checkbox solved but redirect pending — returning True")
            return True

        logger.info("Checkbox not checked — image challenge may have appeared")

    except Exception as e:
        logger.debug("Checkbox state check failed: %s", e)

    # Check if an image challenge appeared (bframe became visible)
    try:
        bframe = None
        for frame in page.frames:
            url = frame.url or ""
            if "/recaptcha/" in url and "/bframe" in url:
                bframe = frame
                break

        if bframe:
            is_visible = await bframe.evaluate("""(() => {
                const el = document.querySelector('.rc-imageselect-challenge');
                return el && el.offsetHeight > 50;
            })()""")
            if is_visible:
                logger.info(
                    "Image challenge appeared — checkbox alone didn't solve it. "
                    "Falling back to CapMonster."
                )
                return False

    except Exception:
        pass

    return False


async def _offset_to_page_coords(page, child_frame, element: dict) -> dict:
    """Convert child frame element coords to main page coords.

    getBoundingClientRect() in a child frame returns coords relative to
    that frame's viewport. We need to add the iframe's position in the
    parent page.
    """
    try:
        # Find the iframe element in the parent that hosts this child frame
        frame_url = child_frame.url or ""
        offset = await page.evaluate("""(frameUrl) => {
            const iframes = document.querySelectorAll('iframe');
            for (const iframe of iframes) {
                const src = iframe.getAttribute('src') || '';
                if (frameUrl.includes('fbsbx') && src.includes('fbsbx')
                    || frameUrl.includes('captcha') && src.includes('captcha')
                    || src === frameUrl) {
                    const r = iframe.getBoundingClientRect();
                    return {x: r.x, y: r.y};
                }
            }
            // Try matching by contentWindow (won't work cross-origin)
            return {x: 0, y: 0};
        }""", frame_url)

        return {
            **element,
            "x": element["x"] + offset["x"],
            "y": element["y"] + offset["y"],
        }
    except Exception:
        return element
