"""Lightweight DOM query wrapper that delegates work to the browser's V8 engine.

Instead of parsing raw CDP Node Arrays in Python (slow, error-prone on
React-mutated DOMs), we inject small JS snippets via ``Runtime.evaluate``
and get back ready-to-use coordinates ``{x, y, w, h}``.

Usage::

    walker = DomWalker(tab)
    el = await walker.find("input[name='email']")
    if el:
        await mouse_engine.click_at(tab, el["x"] + el["w"]/2, el["y"] + el["h"]/2)

NOTE: We use ``tab.send(cdp.runtime.evaluate(..., return_by_value=True))``
instead of ``tab.evaluate()`` because nodriver's evaluate() forces
``serialization_options="deep"`` which returns dicts as lists.
"""

import asyncio
import json
import logging

import nodriver.cdp.runtime

logger = logging.getLogger(__name__)

# Return type for found elements
ElementRect = dict  # {x, y, w, h, text}


async def _eval_js(tab, js: str):
    """Evaluate JS via CDP with return_by_value=True to get proper Python types.

    nodriver's tab.evaluate() uses deep serialization which corrupts dicts
    into lists. This bypasses that by using the CDP protocol directly.
    """
    result = await tab.send(nodriver.cdp.runtime.evaluate(
        expression=js,
        return_by_value=True,
    ))
    # result is a tuple (RemoteObject, ExceptionDetails | None)
    remote_object = result[0] if isinstance(result, tuple) else result
    return remote_object.value


class DomWalker:
    """Thin wrapper around nodriver tab that queries DOM via JS injection."""

    def __init__(self, tab):
        self.tab = tab

    async def find(
        self, selector: str, timeout: float = 10.0
    ) -> ElementRect | None:
        """Find element by CSS selector, return bounding rect or None.

        Retries until *timeout* seconds elapse (handles React lazy rendering).
        """
        js = f"""(() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{x: r.x, y: r.y, w: r.width, h: r.height, text: (el.innerText || '').slice(0, 200)}};
        }})()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_text(
        self, text: str, tag: str = "*", timeout: float = 10.0
    ) -> ElementRect | None:
        """Find element containing *text* (replaces Playwright's ``:has-text()``).

        Searches within elements matching *tag*.
        """
        js = f"""(() => {{
            const els = document.querySelectorAll({json.dumps(tag)});
            for (const el of els) {{
                if (el.innerText && el.innerText.includes({json.dumps(text)})) {{
                    const r = el.getBoundingClientRect();
                    return {{x: r.x, y: r.y, w: r.width, h: r.height, text: el.innerText.slice(0, 200)}};
                }}
            }}
            return null;
        }})()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_all(self, selector: str) -> list[ElementRect]:
        """Return bounding rects for all elements matching *selector*."""
        js = f"""(() => {{
            const els = document.querySelectorAll({json.dumps(selector)});
            return Array.from(els).map(el => {{
                const r = el.getBoundingClientRect();
                return {{x: r.x, y: r.y, w: r.width, h: r.height, text: (el.innerText || '').slice(0, 200)}};
            }});
        }})()"""
        result = await _eval_js(self.tab, js)
        return result or []

    async def get_attribute(self, selector: str, attr: str) -> str | None:
        """Get a single attribute value from the first matching element."""
        js = f"""(() => {{
            const el = document.querySelector({json.dumps(selector)});
            return el ? el.getAttribute({json.dumps(attr)}) : null;
        }})()"""
        return await _eval_js(self.tab, js)

    async def find_group_composer(self, timeout: float = 10.0) -> ElementRect | None:
        """Find Facebook group's 'Write something' composer trigger — language independent.

        Works bottom-up: finds avatar-sized SVG/img elements (30-50px),
        walks up to a wide container (~680px, <130px tall), then returns
        the nested div[role='button'] inside it (the actual clickable input).

        Filters out comment boxes which live inside [role='article'] or form elements.
        """
        js = """(() => {
            const avatars = [
                ...document.querySelectorAll('img'),
                ...document.querySelectorAll('svg'),
            ];

            for (const av of avatars) {
                const ar = av.getBoundingClientRect();
                if (ar.width < 30 || ar.width > 50) continue;
                if (ar.height < 30 || ar.height > 50) continue;
                // Skip avatars in the navbar area (< 100px from top)
                if (ar.y < 100) continue;
                // Skip avatars inside posts (comment boxes) — they sit inside role='article'
                if (av.closest("[role='article']")) continue;
                // Skip avatars inside forms (comment input forms)
                if (av.closest("form")) continue;

                let el = av.parentElement;
                for (let depth = 0; depth < 10 && el; depth++, el = el.parentElement) {
                    const r = el.getBoundingClientRect();
                    // Composer container: wide, moderate height
                    if (r.width < 400 || r.height < 40 || r.height > 140) continue;
                    const text = (el.innerText || '').trim();
                    // Container text should be short-ish (placeholder + maybe a few labels)
                    if (text.length < 2 || text.length > 80) continue;
                    // Must NOT be inside a post article or comment form
                    if (el.closest("[role='article']") || el.closest("form")) continue;

                    // Look for a div[role='button'] INSIDE — that's the clickable input
                    const btns = el.querySelectorAll("div[role='button']");
                    for (const btn of btns) {
                        const br = btn.getBoundingClientRect();
                        // The composer input button is wide (>200px) and short
                        if (br.width < 200 || br.height < 20 || br.height > 50) continue;
                        const btnText = (btn.innerText || '').trim();
                        // Short placeholder text, not a menu item
                        if (btnText.length < 2 || btnText.length > 40) continue;
                        // Scroll into view if below viewport
                        btn.scrollIntoView({block: 'center', behavior: 'instant'});
                        // Re-read rect after scrolling
                        const br2 = btn.getBoundingClientRect();
                        return {x: br2.x, y: br2.y, w: br2.width, h: br2.height, text: btnText};
                    }
                }
            }
            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_dialog_submit_button(self, timeout: float = 5.0) -> ElementRect | None:
        """Find the primary submit/publish button inside a Facebook dialog.

        Language independent — identifies the CTA button by its colored
        (non-transparent, non-white) background, which distinguishes it
        from option toggles and icon buttons in the dialog.
        Falls back to the bottom-most button if no colored button is found.
        """
        js = """(() => {
            // Facebook has many hidden dialog containers; find the visible one
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return null;

            const buttons = dialog.querySelectorAll(
                "div[role='button'], span[role='button'], button, a[role='button']"
            );

            function mkRect(btn) {
                const r = btn.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height,
                        text: (btn.innerText || '').slice(0, 200)};
            }

            // Strategy 1: find button with colored background (primary CTA)
            for (const btn of buttons) {
                const r = btn.getBoundingClientRect();
                if (r.width < 100 || r.height < 25) continue;
                if (btn.getAttribute('aria-disabled') === 'true') continue;
                const bg = window.getComputedStyle(btn).backgroundColor;
                if (!bg) continue;
                if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') continue;
                if (bg === 'rgb(255, 255, 255)') continue;
                return mkRect(btn);
            }

            // Strategy 2: fallback — bottom-most, non-tiny, enabled button
            let best = null;
            let bestY = -1;
            for (const btn of buttons) {
                const r = btn.getBoundingClientRect();
                if (r.width < 50 || r.height < 25) continue;
                if (btn.getAttribute('aria-disabled') === 'true') continue;
                if (r.y > bestY) { best = btn; bestY = r.y; }
            }
            if (best) return mkRect(best);

            // Strategy 3: scan ALL elements in dialog for wide colored CTA
            const allEls = dialog.querySelectorAll('*');
            for (const el of allEls) {
                const r = el.getBoundingClientRect();
                if (r.width < 100 || r.height < 30 || r.height > 60) continue;
                const bg = window.getComputedStyle(el).backgroundColor;
                if (!bg) continue;
                if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') continue;
                if (bg === 'rgb(255, 255, 255)') continue;
                return mkRect(el);
            }
            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_activity_review_dialog(self, timeout: float = 5.0) -> dict | None:
        """Detect Facebook's 'Activity Review' dialog (group rules question).

        This dialog appears when first posting to a group and asks the user to
        confirm they'll follow the rules (radio buttons + submit).
        Returns dict with 'radio' (first radio option) and 'submit' rects,
        or None if no such dialog is present.
        """
        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width < 300 || r.height < 200) continue;

                // Look for radio buttons inside the dialog
                const radios = d.querySelectorAll(
                    "input[type='radio'], div[role='radio']"
                );
                if (radios.length === 0) continue;

                // Found a dialog with radio buttons — this is the activity review
                const firstRadio = radios[0];
                // For input[type='radio'], click the parent label/container
                const radioTarget = firstRadio.closest('label')
                    || firstRadio.parentElement;
                const rr = radioTarget.getBoundingClientRect();

                // Find the submit button (colored CTA at bottom of dialog)
                const btns = d.querySelectorAll(
                    "div[role='button'], span[role='button'], button"
                );
                let submitBtn = null;
                let submitY = -1;
                for (const btn of btns) {
                    const br = btn.getBoundingClientRect();
                    if (br.width < 50 || br.height < 25) continue;
                    if (btn.getAttribute('aria-disabled') === 'true') continue;
                    if (br.y > submitY) { submitBtn = btn; submitY = br.y; }
                }

                if (!submitBtn) continue;
                const sr = submitBtn.getBoundingClientRect();

                return {
                    radio: {x: rr.x, y: rr.y, w: rr.width, h: rr.height},
                    submit: {x: sr.x, y: sr.y, w: sr.width, h: sr.height,
                             text: (submitBtn.innerText || '').slice(0, 50)},
                };
            }
            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_background_button(self, timeout: float = 5.0) -> ElementRect | None:
        """Find the Aa background color button in the post creation dialog.

        Language-independent: looks for a small img element (~24-32px) inside
        the dialog toolbar area, below the text editor.
        Uses multiple strategies to handle Facebook's frequent DOM changes.
        """
        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return null;

            function mkResult(el, tag) {
                const clickable = el.closest("[role='button'], [tabindex]") || el.parentElement;
                const r = clickable.getBoundingClientRect();
                if (r.width > 10 && r.height > 10) {
                    return {x: r.x, y: r.y, w: r.width, h: r.height, text: tag};
                }
                return null;
            }

            const imgs = dialog.querySelectorAll('img');

            // Strategy 1: img with SATP_Aa or Aa-related patterns in src
            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                if (src.includes('SATP_Aa') || src.includes('Aa_square')) {
                    const res = mkResult(img, 'src_match');
                    if (res) return res;
                }
            }

            // Strategy 2: Find the "Add to your post" toolbar and identify
            // the Aa button among its icons by toolbar-row detection.
            const textbox = dialog.querySelector("div[role='textbox']");
            if (!textbox) return null;
            const tbRect = textbox.getBoundingClientRect();

            // Collect all small images below the textbox
            const candidates = [];
            for (const img of imgs) {
                const r = img.getBoundingClientRect();
                if (r.width < 18 || r.width > 48) continue;
                if (r.height < 18 || r.height > 48) continue;
                if (r.y < tbRect.bottom - 10) continue;
                // Skip profile pictures (hosted on scontent CDN, avatar-like)
                const src = img.getAttribute('src') || '';
                if (src.includes('/p') && (src.includes('scontent') || src.includes('fbcdn.net/v/'))) continue;
                candidates.push({ img, r });
            }

            // Group by Y-position to find toolbar rows
            if (candidates.length > 0) {
                candidates.sort((a, b) => a.r.y - b.r.y);
                const rows = [[candidates[0]]];
                for (let i = 1; i < candidates.length; i++) {
                    const lastRow = rows[rows.length - 1];
                    if (Math.abs(candidates[i].r.y - lastRow[0].r.y) < 15) {
                        lastRow.push(candidates[i]);
                    } else {
                        rows.push([candidates[i]]);
                    }
                }

                // The toolbar row has multiple icons (>=2)
                let toolbarRow = null;
                for (const row of rows) {
                    if (row.length >= 2) { toolbarRow = row; break; }
                }

                if (toolbarRow) {
                    // Check URL patterns in toolbar icons
                    for (const c of toolbarRow) {
                        const src = c.img.getAttribute('src') || '';
                        const srcLower = src.toLowerCase();
                        if (srcLower.includes('aa') || srcLower.includes('background')
                            || srcLower.includes('bgsel') || src.includes('SAT')) {
                            const res = mkResult(c.img, 'toolbar_url');
                            if (res) return res;
                        }
                    }
                    // Fallback: first toolbar icon that's not a common FB CDN asset pattern
                    // (photo/video icons usually have specific CDN paths)
                    for (const c of toolbarRow) {
                        const res = mkResult(c.img, 'toolbar_first');
                        if (res) return res;
                    }
                }
            }

            // Strategy 3: any small square img below textbox in a clickable container
            for (const c of candidates) {
                const res = mkResult(c.img, 'fallback');
                if (res) return res;
            }

            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                logger.info("Background button found via: %s", result.get("text", "?"))
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)

    async def find_bg_color_button(self, target_rgb: str, timeout: float = 3.0) -> ElementRect | None:
        """Find a solid color button by its background-color CSS value.

        Used for the Red and Black solid background options.
        """
        js = f"""(() => {{
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {{
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) {{ dialog = d; break; }}
            }}
            if (!dialog) return null;

            const allEls = dialog.querySelectorAll('div');
            for (const el of allEls) {{
                const bg = window.getComputedStyle(el).backgroundColor;
                if (bg === {json.dumps(target_rgb)}) {{
                    const r = el.getBoundingClientRect();
                    if (r.width >= 20 && r.width <= 50 && r.height >= 20 && r.height <= 50) {{
                        const clickable = el.closest("[role='button'], [tabindex]") || el;
                        const cr = clickable.getBoundingClientRect();
                        return {{x: cr.x, y: cr.y, w: cr.width, h: cr.height, text: ''}};
                    }}
                }}
            }}
            return null;
        }})()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.3)

    async def find_bg_expand_button(self, timeout: float = 3.0) -> ElementRect | None:
        """Find the expand button that shows decorative backgrounds.

        This is a small icon (CSS background-image sprite) that opens the
        full grid of decorative background options.
        """
        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return null;

            // The expand button uses a CSS sprite (background-image on <i>)
            const icons = dialog.querySelectorAll('i[style*="background-image"]');
            for (const icon of icons) {
                const r = icon.getBoundingClientRect();
                if (r.width < 12 || r.width > 24) continue;
                if (r.height < 12 || r.height > 24) continue;
                const clickable = icon.closest("[role='button'], [tabindex]") || icon.parentElement;
                const cr = clickable.getBoundingClientRect();
                return {x: cr.x, y: cr.y, w: cr.width, h: cr.height, text: ''};
            }
            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.3)

    async def find_bg_deco_by_index(self, index: int, timeout: float = 3.0) -> ElementRect | None:
        """Find a decorative background by its position (0-indexed) in the grid.

        After clicking the expand button, Facebook shows a horizontal/grid list
        of background options. Each is a div with background-image or
        background-color style, wrapped in a role='button' container.
        """
        js = f"""(() => {{
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {{
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) {{ dialog = d; break; }}
            }}
            if (!dialog) return null;

            // Find all decorative background buttons in the picker grid.
            // Each is a role='button' containing a div with background-image
            // or background-color style.
            const btns = dialog.querySelectorAll("[role='button']");
            const decoButtons = [];
            for (const btn of btns) {{
                const inner = btn.querySelector('div[style*="background-image"], div[style*="background-color"]');
                if (!inner) continue;
                const r = inner.getBoundingClientRect();
                // Decorative swatches are small squares (~30-50px)
                if (r.width < 20 || r.width > 60 || r.height < 20 || r.height > 60) continue;
                decoButtons.push(btn);
            }}

            if ({index} < decoButtons.length) {{
                const target = decoButtons[{index}];
                const r = target.getBoundingClientRect();
                // Scroll into view if needed
                target.scrollIntoView({{block: 'nearest', behavior: 'instant'}});
                const r2 = target.getBoundingClientRect();
                return {{x: r2.x, y: r2.y, w: r2.width, h: r2.height, text: ''}};
            }}
            return null;
        }})()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.3)

    async def find_login_button(self, timeout: float = 5.0) -> ElementRect | None:
        """Find Facebook login submit button across all page layouts/languages.

        Facebook uses various HTML structures depending on locale and A/B tests.
        Sometimes the "button" is a <div role="button">, <span>, or <a> element.
        """
        js = """(() => {
            // Strategy 1: explicit name attribute (FB homepage layout)
            let btn = document.querySelector("button[name='login']");
            if (btn) { const r = btn.getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height, text:btn.innerText}; }

            // Strategy 2: Facebook test IDs
            btn = document.querySelector("[data-testid='royal_login_button']");
            if (btn) { const r = btn.getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height, text:btn.innerText}; }

            // Strategy 3: any <button> on the page (regardless of attributes)
            const buttons = document.querySelectorAll('button');
            for (const b of buttons) {
                const r = b.getBoundingClientRect();
                if (r.width > 50 && r.height > 20) {
                    return {x:r.x, y:r.y, w:r.width, h:r.height, text:(b.innerText||'').slice(0,100)};
                }
            }

            // Strategy 4: div[role='button'] or clickable elements near password field
            const passInput = document.querySelector("input[name='pass']");
            if (passInput) {
                const passRect = passInput.getBoundingClientRect();
                const candidates = document.querySelectorAll("div[role='button'], a[role='button'], span[role='button'], [type='submit']");
                for (const c of candidates) {
                    const cr = c.getBoundingClientRect();
                    if (cr.y > passRect.y && cr.width > 100 && cr.height > 20) {
                        return {x:cr.x, y:cr.y, w:cr.width, h:cr.height, text:(c.innerText||'').slice(0,100)};
                    }
                }
            }

            // Strategy 5: largest clickable element on page
            const allClickable = document.querySelectorAll("div[role='button'], a[role='button'], button, input[type='submit']");
            let largest = null;
            let largestArea = 0;
            for (const el of allClickable) {
                const r = el.getBoundingClientRect();
                const area = r.width * r.height;
                if (area > largestArea && r.width > 100) {
                    largest = el;
                    largestArea = area;
                }
            }
            if (largest) {
                const r = largest.getBoundingClientRect();
                return {x:r.x, y:r.y, w:r.width, h:r.height, text:(largest.innerText||'').slice(0,100)};
            }

            return null;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            result = await _eval_js(self.tab, js)
            if result is not None:
                return result
            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(0.5)
