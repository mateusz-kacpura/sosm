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
