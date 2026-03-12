"""Human-like mouse movement engine using cubic Bézier curves + Fitts' Law.

Anti-detection features beyond basic Bézier:
- Wind perturbation: low-frequency random walk breaks mathematical smoothness
- Biological jitter: Gaussian noise simulates 8-12Hz hand tremor
- Overshoot + correction: long moves (>300px) overshoot, then correct back
- Micro-corrections: 2-4 small sub-movements near the target (homing behavior)
- Bell-shaped velocity: smoothstep easing (slow → fast → slow)
- Pre-click pause: 50-200ms dwell before mousedown (visual confirmation)
- Lognormal timing: biologically realistic delay distribution (not uniform)

Uses raw CDP ``Input.dispatchMouseEvent`` calls through nodriver.
"""

import asyncio
import math
import random
import logging

import nodriver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------
OVERSHOOT_THRESHOLD_PX = 300        # min distance to trigger overshoot
OVERSHOOT_DISTANCE = (5, 15)        # px past target
MICRO_CORRECTION_COUNT = (2, 4)     # sub-movements near target
MICRO_CORRECTION_RADIUS = (2, 5)    # px per correction step
JITTER_SIGMA = 0.8                  # Gaussian noise per mouseMoved point
PRE_CLICK_PAUSE = (0.05, 0.20)     # seconds before mousedown
CLICK_HOLD = (0.04, 0.12)          # mousedown → mouseup duration
WIND_MAGNITUDE = 2.0               # wind perturbation strength
WIND_CHANGE_INTERVAL = (5, 8)      # steps between wind direction changes
FITTS_A = 0.15                     # base reaction time (seconds)
FITTS_B = 0.12                     # movement coefficient
MIN_STEPS = 10
MAX_STEPS = 50
STEPS_PER_PX = 10                  # one step per this many pixels

# ---------------------------------------------------------------------------
# Global cursor state (process-isolated via Celery prefork)
# ---------------------------------------------------------------------------
_cursor_x: float = 0.0
_cursor_y: float = 0.0


# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------

def _cubic_bezier(t: float, p0: float, p1: float, p2: float, p3: float) -> float:
    """Evaluate cubic Bézier curve at parameter *t* (0..1)."""
    u = 1 - t
    return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3


def _ease_in_out(t: float) -> float:
    """Smoothstep easing: slow → fast → slow.  Maps [0,1] → [0,1]."""
    return t * t * (3.0 - 2.0 * t)


def _lognormal_delay(median: float, sigma: float = 0.3) -> float:
    """Sample a delay from a lognormal distribution centered on *median*.

    Lognormal matches human inter-event timing better than uniform random.
    """
    mu = math.log(max(median, 1e-6))
    return random.lognormvariate(mu, sigma)


def _fitts_duration(distance: float, target_size: float) -> float:
    """Estimate movement duration (seconds) using Fitts' Law.

    T = a + b * log2(D/W + 1)
    Coefficients calibrated for human mouse movement (~200-800ms typical).
    """
    if target_size < 1:
        target_size = 1
    return FITTS_A + FITTS_B * math.log2(distance / target_size + 1)


def _compute_step_delays(num_steps: int, total_duration: float) -> list[float]:
    """Compute per-step delays with a bell-shaped velocity profile.

    Uses smoothstep easing: delay is inversely proportional to velocity.
    Steps at start/end are slower, middle is faster.
    """
    if num_steps <= 1:
        return [total_duration]

    # Compute raw velocity at each step (derivative of smoothstep: 6t(1-t))
    raw_delays = []
    for i in range(num_steps):
        t = i / (num_steps - 1)
        velocity = 6.0 * t * (1.0 - t)  # peaks at t=0.5
        # Delay is inversely proportional to velocity (slow where velocity is low)
        delay = 1.0 / max(velocity, 0.15)
        raw_delays.append(delay)

    # Normalize to sum to total_duration
    raw_sum = sum(raw_delays)
    if raw_sum <= 0:
        return [total_duration / num_steps] * num_steps

    scale = total_duration / raw_sum
    delays = [d * scale for d in raw_delays]

    # Apply lognormal jitter to each delay
    delays = [_lognormal_delay(d, sigma=0.15) for d in delays]

    # Clamp extremes (no single step > 30% of total, no step < 1ms)
    max_delay = total_duration * 0.3
    delays = [max(0.001, min(d, max_delay)) for d in delays]

    return delays


# ---------------------------------------------------------------------------
# Path generation
# ---------------------------------------------------------------------------

def _generate_bezier_points(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    steps: int = 25,
) -> list[tuple[float, float]]:
    """Generate points along a cubic Bézier curve with wind perturbation and jitter.

    Control points are randomized for natural-looking curved paths.
    Wind perturbation adds low-frequency drift (random walk).
    Biological jitter adds high-frequency noise (hand tremor).
    """
    dx = end_x - start_x
    dy = end_y - start_y

    # Random control points — offset perpendicular to the direct path
    spread = max(abs(dx), abs(dy)) * random.uniform(0.1, 0.4)
    cp1_x = start_x + dx * random.uniform(0.2, 0.4) + random.uniform(-spread, spread)
    cp1_y = start_y + dy * random.uniform(0.2, 0.4) + random.uniform(-spread, spread)
    cp2_x = start_x + dx * random.uniform(0.6, 0.8) + random.uniform(-spread, spread)
    cp2_y = start_y + dy * random.uniform(0.6, 0.8) + random.uniform(-spread, spread)

    # Generate raw Bézier points
    points = []
    for i in range(steps + 1):
        t = i / steps
        x = _cubic_bezier(t, start_x, cp1_x, cp2_x, end_x)
        y = _cubic_bezier(t, start_y, cp1_y, cp2_y, end_y)
        points.append((x, y))

    # Wind perturbation: low-frequency random walk
    wind_x, wind_y = 0.0, 0.0
    change_interval = random.randint(*WIND_CHANGE_INTERVAL)
    for i in range(1, len(points) - 1):  # anchor first and last points
        if i % change_interval == 0:
            wind_x = random.gauss(0, WIND_MAGNITUDE)
            wind_y = random.gauss(0, WIND_MAGNITUDE)
        # Fade wind near endpoints (don't perturb start/end)
        fade = 1.0 - abs(2.0 * i / len(points) - 1.0)  # 0 at edges, 1 at center
        px, py = points[i]
        points[i] = (px + wind_x * fade, py + wind_y * fade)

    # Biological jitter: high-frequency Gaussian noise (hand tremor)
    for i in range(1, len(points) - 1):
        px, py = points[i]
        points[i] = (
            px + random.gauss(0, JITTER_SIGMA),
            py + random.gauss(0, JITTER_SIGMA),
        )

    return points


def _generate_overshoot_path(
    start_x: float,
    start_y: float,
    target_x: float,
    target_y: float,
    steps: int,
) -> list[tuple[float, float]]:
    """Generate a two-phase path: overshoot past the target, then correct back.

    Phase 1 (80% of steps): Bézier from start to overshoot point.
    Phase 2 (20% of steps): Bézier from overshoot back to target.
    """
    dx = target_x - start_x
    dy = target_y - start_y
    distance = math.hypot(dx, dy)
    if distance < 1:
        return [(target_x, target_y)]

    # Overshoot point: extend past target along the approach vector
    overshoot_dist = random.uniform(*OVERSHOOT_DISTANCE)
    overshoot_x = target_x + (dx / distance) * overshoot_dist + random.gauss(0, 3)
    overshoot_y = target_y + (dy / distance) * overshoot_dist + random.gauss(0, 3)

    # Phase 1: start → overshoot (80% of steps)
    phase1_steps = max(5, int(steps * 0.8))
    phase1 = _generate_bezier_points(start_x, start_y, overshoot_x, overshoot_y, phase1_steps)

    # Phase 2: overshoot → target (20% of steps)
    phase2_steps = max(3, steps - phase1_steps)
    phase2 = _generate_bezier_points(overshoot_x, overshoot_y, target_x, target_y, phase2_steps)

    # Skip the first point of phase2 (it's the same as the last of phase1)
    return phase1 + phase2[1:]


def _generate_micro_corrections(
    target_x: float,
    target_y: float,
    count: int,
) -> list[tuple[float, float]]:
    """Generate small sub-movements near the target (homing behavior).

    Real humans make 2-4 tiny adjustments as they fine-position the cursor.
    The final correction lands exactly on the target.
    """
    if count <= 0:
        return [(target_x, target_y)]

    corrections = []
    cx, cy = target_x, target_y
    # Generate correction points around the target
    for i in range(count - 1):
        radius = random.uniform(*MICRO_CORRECTION_RADIUS)
        angle = random.uniform(0, 2 * math.pi)
        cx = target_x + radius * math.cos(angle)
        cy = target_y + radius * math.sin(angle)
        corrections.append((cx, cy))

    # Final correction lands exactly on the target
    corrections.append((target_x, target_y))
    return corrections


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
# CDP dispatch layer
# ---------------------------------------------------------------------------

async def _dispatch_mouse(
    tab,
    event_type: str,
    x: float,
    y: float,
    button: str = "none",
    click_count: int = 0,
    delta_x: float = 0,
    delta_y: float = 0,
) -> None:
    """Send a single CDP Input.dispatchMouseEvent."""
    params = dict(
        type_=event_type,
        x=x,
        y=y,
        button=nodriver.cdp.input_.MouseButton(button),
        click_count=click_count,
        pointer_type="mouse",
    )
    if event_type == "mouseWheel":
        params["delta_x"] = delta_x
        params["delta_y"] = delta_y
    await tab.send(nodriver.cdp.input_.dispatch_mouse_event(**params))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def move_to(tab, x: float, y: float, target_size: float = 20) -> None:
    """Move cursor from current position to (x, y) with human-like trajectory."""
    global _cursor_x, _cursor_y

    distance = math.hypot(x - _cursor_x, y - _cursor_y)
    if distance < 2:
        _cursor_x, _cursor_y = x, y
        return

    # Number of steps proportional to distance
    steps = max(MIN_STEPS, min(MAX_STEPS, int(distance / STEPS_PER_PX)))

    # Choose path strategy based on distance
    if distance > OVERSHOOT_THRESHOLD_PX:
        points = _generate_overshoot_path(_cursor_x, _cursor_y, x, y, steps)
    else:
        points = _generate_bezier_points(_cursor_x, _cursor_y, x, y, steps)

    # Add micro-corrections at the end (homing behavior)
    micro_count = random.randint(*MICRO_CORRECTION_COUNT)
    corrections = _generate_micro_corrections(x, y, micro_count)
    points.extend(corrections)

    # Compute bell-shaped timing
    duration = _fitts_duration(distance, target_size)
    delays = _compute_step_delays(len(points), duration)

    # Dispatch each mouseMoved event
    for i, (px, py) in enumerate(points):
        await _dispatch_mouse(tab, "mouseMoved", px, py)
        if i < len(delays):
            await asyncio.sleep(delays[i])

    _cursor_x, _cursor_y = x, y


async def click_at(tab, x: float, y: float, target_size: float = 20) -> None:
    """Move cursor to (x, y) along Bézier curve, then click."""
    await move_to(tab, x, y, target_size=target_size)

    # Pre-click pause: humans dwell to visually confirm the target
    await asyncio.sleep(random.uniform(*PRE_CLICK_PAUSE))

    await _dispatch_mouse(tab, "mousePressed", x, y, button="left", click_count=1)
    await asyncio.sleep(random.uniform(*CLICK_HOLD))
    await _dispatch_mouse(tab, "mouseReleased", x, y, button="left", click_count=1)


async def click_element(tab, el: dict) -> None:
    """Click a random point within element rect *el* (from DomWalker)."""
    x, y = _random_point_in_element(el)
    target_size = min(el.get("w", 20), el.get("h", 20))
    await click_at(tab, x, y, target_size=target_size)


async def scroll(tab, delta_y: int) -> None:
    """Dispatch a single mouseWheel event at the current cursor position."""
    await _dispatch_mouse(
        tab, "mouseWheel", _cursor_x, _cursor_y,
        delta_x=0, delta_y=delta_y,
    )


def reset_cursor() -> None:
    """Reset tracked cursor position (call at start of each session)."""
    global _cursor_x, _cursor_y
    _cursor_x = 0.0
    _cursor_y = 0.0
