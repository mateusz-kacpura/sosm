"""Mouse movement engine — thin adapter over Camoufox's built-in humanization.

Camoufox ``humanize=True`` implements human-like cursor movement at the C++
level (Bézier curves, overshoot, micro-corrections, Fitts' Law timing).
This module provides a simple public API and delegates the heavy lifting
to Camoufox/Playwright.

Uses Playwright's ``page.mouse.*`` methods.
"""

import asyncio
import random
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global cursor state (process-isolated via Celery prefork)
# ---------------------------------------------------------------------------
_cursor_x: float = 0.0
_cursor_y: float = 0.0

# Pre-click pause range (seconds) — visual confirmation before mousedown
PRE_CLICK_PAUSE = (0.05, 0.20)


# ---------------------------------------------------------------------------
# Element targeting
# ---------------------------------------------------------------------------

def _random_point_in_element(el: dict) -> tuple[float, float]:
    """Pick a random click point within the element rect.

    Avoids clicking the exact center (detection vector).
    Uses a Gaussian distribution centered on the element.
    """
    cx = el["x"] + el["w"] / 2
    cy = el["y"] + el["h"] / 2

    # Gaussian offset — 68% of clicks within inner 60% of element
    sigma_x = el["w"] * 0.15
    sigma_y = el["h"] * 0.15
    offset_x = random.gauss(0, sigma_x)
    offset_y = random.gauss(0, sigma_y)

    # Clamp within element bounds (with 2px padding)
    x = max(el["x"] + 2, min(el["x"] + el["w"] - 2, cx + offset_x))
    y = max(el["y"] + 2, min(el["y"] + el["h"] - 2, cy + offset_y))

    return x, y


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def move_to(page, x: float, y: float, target_size: float = 20) -> None:
    """Move cursor to (x, y). Camoufox humanize handles the trajectory."""
    global _cursor_x, _cursor_y
    await page.mouse.move(x, y)
    _cursor_x, _cursor_y = x, y


async def click_at(page, x: float, y: float, target_size: float = 20) -> None:
    """Move cursor to (x, y), then click."""
    global _cursor_x, _cursor_y

    # Pre-click pause: humans dwell to visually confirm the target
    await asyncio.sleep(random.uniform(*PRE_CLICK_PAUSE))

    await page.mouse.click(x, y)
    _cursor_x, _cursor_y = x, y


async def click_element(page, el: dict) -> None:
    """Click a random point within element rect *el* (from DomWalker)."""
    x, y = _random_point_in_element(el)
    await click_at(page, x, y)


async def scroll(page, delta_y: int) -> None:
    """Dispatch a mouse wheel event at the current cursor position."""
    await page.mouse.wheel(0, delta_y)


def reset_cursor() -> None:
    """Reset tracked cursor position (call at start of each session)."""
    global _cursor_x, _cursor_y
    _cursor_x = 0.0
    _cursor_y = 0.0
