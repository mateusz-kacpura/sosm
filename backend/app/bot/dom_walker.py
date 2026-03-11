"""Lightweight DOM query wrapper that delegates work to the browser's V8 engine.

Instead of parsing raw CDP Node Arrays in Python (slow, error-prone on
React-mutated DOMs), we inject small JS snippets via ``Runtime.evaluate``
and get back ready-to-use coordinates ``{x, y, w, h}``.

Usage::

    walker = DomWalker(tab)
    el = await walker.find("input[name='email']")
    if el:
        await mouse_engine.click_at(tab, el["x"] + el["w"]/2, el["y"] + el["h"]/2)
"""

import asyncio
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Return type for found elements
ElementRect = dict  # {x, y, w, h, text}


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
            result = await self.tab.evaluate(js)
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
            result = await self.tab.evaluate(js)
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
        result = await self.tab.evaluate(js)
        return result or []

    async def get_attribute(self, selector: str, attr: str) -> str | None:
        """Get a single attribute value from the first matching element."""
        js = f"""(() => {{
            const el = document.querySelector({json.dumps(selector)});
            return el ? el.getAttribute({json.dumps(attr)}) : null;
        }})()"""
        return await self.tab.evaluate(js)
