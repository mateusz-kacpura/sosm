"""Human-like mouse movement engine using cubic Bézier curves + Fitts' Law.

Replaces ``python-ghost-cursor`` (Playwright-only) with raw CDP
``Input.dispatchMouseEvent`` calls through nodriver.

Key properties:
- Cubic Bézier curves with random control points (not straight lines)
- Fitts' Law timing: movement duration = f(distance, target size)
- Random offset from element center (not perfect center clicks)
- Variable step timing with micro-jitter
"""

import asyncio
import math
import random
import logging

import nodriver

logger = logging.getLogger(__name__)

# Current cursor position (tracked across calls)
_cursor_x: float = 0.0
_cursor_y: float = 0.0


def _cubic_bezier(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Evaluate cubic Bézier curve at parameter *t* (0..1)."""
    u = 1 - t
    return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3


def _generate_bezier_points(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    steps: int = 25,
) -> list[tuple[float, float]]:
    """Generate points along a cubic Bézier curve from start to end.

    Control points are randomized to create natural-looking curved paths.
    """
    dx = end_x - start_x
    dy = end_y - start_y

    # Random control points — offset perpendicular to the direct path
    spread = max(abs(dx), abs(dy)) * random.uniform(0.1, 0.4)
    cp1_x = start_x + dx * random.uniform(0.2, 0.4) + random.uniform(-spread, spread)
    cp1_y = start_y + dy * random.uniform(0.2, 0.4) + random.uniform(-spread, spread)
    cp2_x = start_x + dx * random.uniform(0.6, 0.8) + random.uniform(-spread, spread)
    cp2_y = start_y + dy * random.uniform(0.6, 0.8) + random.uniform(-spread, spread)

    points = []
    for i in range(steps + 1):
        t = i / steps
        x = _cubic_bezier(t, start_x, cp1_x, cp2_x, end_x)
        y = _cubic_bezier(t, start_y, cp1_y, cp2_y, end_y)
        points.append((x, y))

    return points


def _fitts_duration(distance: float, target_size: float) -> float:
    """Estimate movement duration (seconds) using Fitts' Law.

    T = a + b * log2(D/W + 1)

    Coefficients calibrated for human mouse movement (~200-800ms typical).
    """
    a = 0.15  # base reaction time
    b = 0.12  # movement coefficient
    if target_size < 1:
        target_size = 1
    return a + b * math.log2(distance / target_size + 1)


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


async def _dispatch_mouse(
    tab, event_type: str, x: float, y: float, button: str = "none", click_count: int = 0
) -> None:
    """Send a single CDP Input.dispatchMouseEvent."""
    await tab.send(
        nodriver.cdp.input_.dispatch_mouse_event(
            type_=event_type,
            x=x,
            y=y,
            button=nodriver.cdp.input_.MouseButton(button),
            click_count=click_count,
        )
    )


async def move_to(tab, x: float, y: float) -> None:
    """Move cursor from current position to (x, y) along a Bézier curve."""
    global _cursor_x, _cursor_y

    distance = math.hypot(x - _cursor_x, y - _cursor_y)
    if distance < 2:
        _cursor_x, _cursor_y = x, y
        return

    # Number of steps proportional to distance (min 10, max 50)
    steps = max(10, min(50, int(distance / 10)))

    points = _generate_bezier_points(_cursor_x, _cursor_y, x, y, steps)
    duration = _fitts_duration(distance, 20)  # assume ~20px average target
    step_delay = duration / len(points)

    for px, py in points:
        await _dispatch_mouse(tab, "mouseMoved", px, py)
        # Micro-jitter on timing (±30%)
        jitter = step_delay * random.uniform(0.7, 1.3)
        await asyncio.sleep(jitter)

    _cursor_x, _cursor_y = x, y


async def click_at(tab, x: float, y: float) -> None:
    """Move cursor to (x, y) along Bézier curve, then click."""
    await move_to(tab, x, y)
    await _dispatch_mouse(tab, "mousePressed", x, y, button="left", click_count=1)
    await asyncio.sleep(random.uniform(0.04, 0.12))  # human key-down duration
    await _dispatch_mouse(tab, "mouseReleased", x, y, button="left", click_count=1)


async def click_element(tab, el: dict) -> None:
    """Click a random point within element rect *el* (from DomWalker)."""
    x, y = _random_point_in_element(el)
    await click_at(tab, x, y)


async def scroll(tab, delta_y: int) -> None:
    """Dispatch a mouseWheel event at the current cursor position."""
    global _cursor_x, _cursor_y
    await _dispatch_mouse(tab, "mouseWheel", _cursor_x, _cursor_y)
    # mouseWheel needs deltaX/deltaY — use the lower-level send
    await tab.send(
        nodriver.cdp.input_.dispatch_mouse_event(
            type_="mouseWheel",
            x=_cursor_x,
            y=_cursor_y,
            delta_x=0,
            delta_y=delta_y,
        )
    )


def reset_cursor() -> None:
    """Reset tracked cursor position (call at start of each session)."""
    global _cursor_x, _cursor_y
    _cursor_x = 0.0
    _cursor_y = 0.0
