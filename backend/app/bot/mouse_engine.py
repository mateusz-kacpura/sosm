"""Human-like mouse movement engine for Playwright.

Generates Bézier curve trajectories with Gaussian distortion and
easeOutQuad timing, dispatched as individual mouse.move() calls
with asyncio.sleep() delays between them. This produces visually
smooth, human-like cursor movement on screen.

Algorithm ported from Camoufox C++ MouseTrajectories.hpp
(which itself is based on HumanCursor by riflosnake).
"""

import asyncio
import math
import random
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global cursor state (process-isolated via Celery prefork)
# ---------------------------------------------------------------------------
_cursor_x: float = 0.0
_cursor_y: float = 0.0

# Pre-click pause range (seconds) — visual confirmation before mousedown
PRE_CLICK_PAUSE = (0.08, 0.25)

# Mouse-down hold duration (seconds) — humans don't release instantly
CLICK_HOLD = (0.04, 0.12)

# Base delay between trajectory points (seconds)
# Actual delay = BASE_STEP_DELAY * easing factor
BASE_STEP_DELAY = 0.012


# ---------------------------------------------------------------------------
# Bézier curve trajectory generation
# ---------------------------------------------------------------------------

def _bernstein(n: int, k: int, t: float) -> float:
    """Bernstein basis polynomial."""
    coeff = math.comb(n, k)
    return coeff * (t ** k) * ((1 - t) ** (n - k))


def _bezier_point(
    control_points: list[tuple[float, float]], t: float
) -> tuple[float, float]:
    """Evaluate Bézier curve at parameter t."""
    n = len(control_points) - 1
    x = sum(p[0] * _bernstein(n, i, t) for i, p in enumerate(control_points))
    y = sum(p[1] * _bernstein(n, i, t) for i, p in enumerate(control_points))
    return x, y


def _generate_trajectory(
    from_x: float, from_y: float, to_x: float, to_y: float
) -> list[tuple[float, float]]:
    """Generate a human-like mouse trajectory using Bézier curves.

    Returns a list of (x, y) points along the curve, with easeOutQuad
    timing applied (fast start, slow approach to target).
    """
    distance = math.hypot(to_x - from_x, to_y - from_y)

    if distance < 3:
        # Too short for a curve — just go directly
        return [(to_x, to_y)]

    # Boundary for random control knots (±80px around the path)
    left = min(from_x, to_x) - 80
    right = max(from_x, to_x) + 80
    top = min(from_y, to_y) - 80
    bottom = max(from_y, to_y) + 80

    # Generate 2 random internal knots for the Bézier curve
    knots = [
        (random.uniform(left, right), random.uniform(top, bottom)),
        (random.uniform(left, right), random.uniform(top, bottom)),
    ]

    # Control points: start → knot1 → knot2 → end
    control_points = [(from_x, from_y)] + knots + [(to_x, to_y)]

    # Number of raw curve samples = distance
    n_samples = max(int(distance), 10)
    raw_points = [_bezier_point(control_points, i / (n_samples - 1))
                  for i in range(n_samples)]

    # Apply Gaussian distortion to intermediate points
    distorted = [raw_points[0]]
    for i in range(1, len(raw_points) - 1):
        x, y = raw_points[i]
        if random.random() < 0.5:
            y += round(random.gauss(1.0, 1.0))
        distorted.append((x, y))
    distorted.append(raw_points[-1])

    # Calculate total path length for timing
    total_length = sum(
        math.hypot(distorted[i][0] - distorted[i - 1][0],
                    distorted[i][1] - distorted[i - 1][1])
        for i in range(1, len(distorted))
    )

    # Target number of output points (Fitts' Law scaling)
    target_points = min(150, max(8, int(total_length ** 0.25 * 20)))

    # Resample with easeOutQuad timing
    trajectory = []
    for i in range(target_points):
        t = i / (target_points - 1)
        eased_t = -t * (t - 2)  # easeOutQuad: fast start, slow end
        idx = int(eased_t * (len(distorted) - 1))
        idx = min(idx, len(distorted) - 1)
        trajectory.append(distorted[idx])

    # Ensure the last point is exactly the target
    trajectory[-1] = (to_x, to_y)
    return trajectory


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

async def move_to(page, x: float, y: float) -> None:
    """Move cursor to (x, y) along a human-like Bézier trajectory."""
    global _cursor_x, _cursor_y

    trajectory = _generate_trajectory(_cursor_x, _cursor_y, x, y)

    for i, (px, py) in enumerate(trajectory):
        await page.mouse.move(px, py)

        # Variable delay: slower at start/end, faster in middle
        if i < len(trajectory) - 1:
            # Add jitter to prevent uniform timing detection
            delay = BASE_STEP_DELAY * (0.7 + random.random() * 0.6)
            await asyncio.sleep(delay)

    _cursor_x, _cursor_y = x, y


async def click_at(page, x: float, y: float) -> None:
    """Move cursor to (x, y) with Bézier trajectory, then click."""
    global _cursor_x, _cursor_y

    # Move along trajectory
    await move_to(page, x, y)

    # Pre-click dwell: humans pause to visually confirm target
    await asyncio.sleep(random.uniform(*PRE_CLICK_PAUSE))

    # Separate mousedown/mouseup with realistic hold duration
    await page.mouse.down()
    await asyncio.sleep(random.uniform(*CLICK_HOLD))
    await page.mouse.up()

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
