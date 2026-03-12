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

        Collects ALL candidates and returns the one closest to the top of the page.
        Filters out comment boxes which live inside [role='article'], form, or
        deep inside [role='feed'] (below the first feed child).
        """
        js = """(() => {
            const avatars = [
                ...document.querySelectorAll('img'),
                ...document.querySelectorAll('svg'),
            ];

            const candidates = [];

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

                // If avatar is inside [role='feed'], only accept it if it's in the
                // first or second direct child (the composer area). Comment boxes
                // are in later children (actual posts).
                const feed = av.closest("[role='feed']");
                if (feed) {
                    let feedChild = av;
                    while (feedChild && feedChild.parentElement !== feed) {
                        feedChild = feedChild.parentElement;
                    }
                    if (feedChild) {
                        const children = [...feed.children];
                        const idx = children.indexOf(feedChild);
                        // Composer is typically the first or second child in the feed
                        if (idx > 2) continue;
                    }
                }

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
                        // Use absolute page position (not viewport) for stable sorting
                        const pageY = br.y + window.scrollY;
                        candidates.push({x: br.x, y: br.y, w: br.width, h: br.height, text: btnText, pageY: pageY});
                    }
                }
            }

            if (candidates.length === 0) return null;
            // Return the candidate closest to the top of the page
            candidates.sort((a, b) => a.pageY - b.pageY);
            const best = candidates[0];
            // Scroll it into view
            const el = document.elementFromPoint(best.x + best.w/2, best.y + best.h/2);
            if (el) el.scrollIntoView({block: 'center', behavior: 'instant'});
            // Re-read position after scroll
            if (el) {
                const r2 = el.getBoundingClientRect();
                return {x: r2.x, y: r2.y, w: r2.width, h: r2.height, text: best.text};
            }
            return best;
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
                        text: (btn.getAttribute('aria-label') || btn.innerText || '').slice(0, 200)};
            }

            // Strategy 0: find button by aria-label matching publish/submit keywords
            // This is the most reliable — FB "Opublikuj" button has transparent bg
            // but always has aria-label="Opublikuj" (PL) / "Post" (EN) / "Submit" (EN)
            const publishKeywords = ['opublikuj', 'publish', 'post', 'submit', 'prześlij'];
            for (const btn of buttons) {
                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                if (!label) continue;
                if (!publishKeywords.some(kw => label === kw)) continue;
                const r = btn.getBoundingClientRect();
                if (r.width < 50 || r.height < 20) continue;
                if (btn.getAttribute('aria-disabled') === 'true') continue;
                return mkRect(btn);
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
                // Skip close/back buttons (small, gray)
                if (r.width < 50 && r.height < 50) continue;
                return mkRect(btn);
            }

            // Strategy 2: fallback — widest, bottom-most enabled button
            let best = null;
            let bestScore = -1;
            for (const btn of buttons) {
                const r = btn.getBoundingClientRect();
                if (r.width < 100 || r.height < 25) continue;
                if (btn.getAttribute('aria-disabled') === 'true') continue;
                // Score by Y position (bottom) and width (wide = more likely CTA)
                const score = r.y * 1000 + r.width;
                if (score > bestScore) { best = btn; bestScore = score; }
            }
            if (best) return mkRect(best);

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

    async def find_bg_hide_button(self, timeout: float = 2.0) -> ElementRect | None:
        """Find 'Ukryj opcje tła' / 'Hide background options' button to close the grid."""
        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return null;

            const btns = dialog.querySelectorAll("[role='button'][aria-label]");
            for (const btn of btns) {
                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                if (label.includes('ukryj') && label.includes('t\u0142a')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.getAttribute('aria-label').slice(0, 40)};
                    }
                }
                if (label.includes('hide') && label.includes('background')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.getAttribute('aria-label').slice(0, 40)};
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
            await asyncio.sleep(0.3)

    async def find_bg_expand_button(self, timeout: float = 3.0) -> ElementRect | None:
        """Find the grid expand button (⊞) that reveals all decorative backgrounds.

        After clicking the Aa button, only ~5 decorative backgrounds are
        visible in a horizontal swatch row.  The expand button (aria-label
        'Opcje tła' in Polish, 'Background options' in English) opens the
        full grid with ~30 options.
        """
        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return null;

            // Search for button by aria-label keywords (language-independent).
            // Must NOT match "Ukryj opcje tła" (back/hide button) — only "Opcje tła" (expand).
            const btns = dialog.querySelectorAll("[role='button'][aria-label]");
            for (const btn of btns) {
                const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                // Polish: "Opcje tła" but NOT "Ukryj opcje tła"
                if (label.includes('opcje') && label.includes('t\u0142a')
                    && !label.includes('ukryj')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.getAttribute('aria-label').slice(0, 40)};
                    }
                }
                // English: "Background options" but NOT "Hide background options"
                if (label.includes('background') && label.includes('option')
                    && !label.includes('hide')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.getAttribute('aria-label').slice(0, 40)};
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
            await asyncio.sleep(0.3)

    async def find_bg_deco_by_index(self, index: int, timeout: float = 3.0) -> ElementRect | None:
        """Find a decorative background by its position (0-indexed) in the swatch row.

        After clicking the Aa button, Facebook shows all backgrounds in a
        horizontal scrollable row.  Each is a div[role='button'][aria-label]
        containing inner divs.  Decorative backgrounds have a computed
        backgroundImage (set via CSS class, NOT inline style).  Solid-color
        backgrounds only have backgroundColor.  We skip solid ones and count
        only the decorative (backgroundImage) entries.
        """
        js = f"""(() => {{
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {{
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) {{ dialog = d; break; }}
            }}
            if (!dialog) return null;

            // Find all swatch buttons: role='button' with aria-label, size 15-120px
            const btns = dialog.querySelectorAll("[role='button'][aria-label]");
            const decoButtons = [];
            for (const btn of btns) {{
                const r = btn.getBoundingClientRect();
                if (r.width > 120 || r.height > 120) continue;
                if (r.width < 15 || r.height < 15) continue;

                // Check if any child div has a computed backgroundImage
                const children = btn.querySelectorAll('div');
                let hasBgImage = false;
                for (const child of children) {{
                    const cs = window.getComputedStyle(child);
                    if (cs.backgroundImage && cs.backgroundImage !== 'none') {{
                        hasBgImage = true;
                        break;
                    }}
                }}
                if (!hasBgImage) continue;
                decoButtons.push(btn);
            }}

            if ({index} < decoButtons.length) {{
                const target = decoButtons[{index}];
                target.scrollIntoView({{block: 'nearest', behavior: 'instant'}});
                const r2 = target.getBoundingClientRect();
                return {{x: r2.x, y: r2.y, w: r2.width, h: r2.height,
                         text: (target.getAttribute('aria-label') || '').slice(0, 40),
                         total: decoButtons.length}};
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
