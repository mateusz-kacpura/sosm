"""CAPTCHA solver using CapMonster Cloud API.

Handles reCAPTCHA v2 (image challenge) detection and solving on Facebook pages.
Facebook uses reCAPTCHA v2 with image grids (select buses, crosswalks, motorcycles etc.).
Uses the capmonstercloudclient library for API communication.

Flow:
1. Detect reCAPTCHA on the page — extract sitekey and determine version (v2/v2 Enterprise)
2. Send task to CapMonster Cloud (they solve the image challenge on their servers)
3. Receive gRecaptchaResponse token (~10-60s)
4. Inject token into the page and trigger the callback
"""

import logging
from capmonstercloudclient import CapMonsterClient, ClientOptions
from capmonstercloudclient.requests import (
    RecaptchaV2Request,
    RecaptchaV2EnterpriseRequest,
)

from app.core.config import settings

logger = logging.getLogger(__name__)


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


async def inject_recaptcha_token(page, token: str) -> bool:
    """Inject a solved reCAPTCHA v2 token into the page.

    Fills the hidden g-recaptcha-response textarea and triggers
    the registered callback so the form recognizes the solution.
    """
    try:
        result = await page.evaluate("""(token) => {
            let injected = false;

            // 1. Fill ALL hidden textarea(s) used by reCAPTCHA
            const textareas = document.querySelectorAll(
                'textarea[name="g-recaptcha-response"], '
                + '#g-recaptcha-response, '
                + 'textarea[id*="g-recaptcha-response"]'
            );
            for (const ta of textareas) {
                ta.value = token;
                ta.innerHTML = token;
                injected = true;
            }

            // 2. Trigger the reCAPTCHA callback with the token
            // This is how reCAPTCHA v2 notifies the host page that
            // the challenge was solved.
            try {
                if (typeof ___grecaptcha_cfg !== 'undefined' && ___grecaptcha_cfg.clients) {
                    for (const clientId of Object.keys(___grecaptcha_cfg.clients)) {
                        const client = ___grecaptcha_cfg.clients[clientId];
                        // Walk nested objects to find callback functions
                        const findCallback = (obj, depth) => {
                            if (!obj || typeof obj !== 'object' || depth > 5) return;
                            if (typeof obj.callback === 'function') {
                                obj.callback(token);
                                return true;
                            }
                            for (const key of Object.keys(obj)) {
                                if (findCallback(obj[key], depth + 1)) return true;
                            }
                        };
                        findCallback(client, 0);
                    }
                    injected = true;
                }
            } catch(e) {}

            // 3. Also try direct grecaptcha callback approach
            try {
                if (typeof grecaptcha !== 'undefined') {
                    // getResponse() should now return our token
                    const origGetResponse = grecaptcha.getResponse;
                    grecaptcha.getResponse = function() { return token; };

                    // Override enterprise variant too
                    if (grecaptcha.enterprise) {
                        const origEnterpriseGetResponse = grecaptcha.enterprise.getResponse;
                        grecaptcha.enterprise.getResponse = function() { return token; };
                        grecaptcha.enterprise.execute = function() {
                            return Promise.resolve(token);
                        };
                    }
                    injected = true;
                }
            } catch(e) {}

            return injected;
        }""", token)

        logger.info("Token injection result: %s", result)
        return bool(result)

    except Exception as e:
        logger.warning("Token injection failed: %s", e)
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
    token = await solve_recaptcha_v2(
        page_url=page.url,
        sitekey=sitekey,
        enterprise=enterprise,
    )

    if not token:
        return False

    return await inject_recaptcha_token(page, token)


async def solve_captcha_on_checkpoint(page) -> bool:
    """Attempt to solve reCAPTCHA on a checkpoint/challenge page.

    Call this when a checkpoint is detected after login.
    Detects the CAPTCHA, solves it via CapMonster Cloud, injects the token,
    and submits the form.

    Returns True if CAPTCHA was solved and submitted.
    """
    recaptcha_info = await detect_recaptcha(page)
    if not recaptcha_info or not recaptcha_info.get("sitekey"):
        logger.info("No solvable reCAPTCHA found on checkpoint page")
        return False

    enterprise = recaptcha_info.get("enterprise", False)
    token = await solve_recaptcha_v2(
        page_url=page.url,
        sitekey=recaptcha_info["sitekey"],
        enterprise=enterprise,
    )

    if not token:
        return False

    injected = await inject_recaptcha_token(page, token)
    if not injected:
        return False

    # Try to submit the checkpoint form
    submitted = await page.evaluate("""(() => {
        // Look for a submit/continue button on the checkpoint page
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
                btn.click();
                return true;
            }
        }
        // Fallback: submit the first form with a recaptcha response
        const form = document.querySelector(
            'form:has(textarea[name="g-recaptcha-response"])'
        );
        if (form) { form.submit(); return true; }
        return false;
    })()""")

    if submitted:
        logger.info("Checkpoint form submitted after CAPTCHA solve")
    else:
        logger.warning("Could not find submit button on checkpoint page")

    return submitted
