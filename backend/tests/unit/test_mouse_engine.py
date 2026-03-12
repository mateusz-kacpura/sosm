import math
import random
from unittest.mock import AsyncMock, patch

import pytest


# --- Pure math helpers ---

class TestCubicBezier:
    def test_start_equals_p0(self):
        from app.bot.mouse_engine import _cubic_bezier
        assert _cubic_bezier(0, 10, 20, 30, 40) == 10

    def test_end_equals_p3(self):
        from app.bot.mouse_engine import _cubic_bezier
        assert _cubic_bezier(1, 10, 20, 30, 40) == 40

    def test_midpoint_between_endpoints(self):
        from app.bot.mouse_engine import _cubic_bezier
        mid = _cubic_bezier(0.5, 0, 100, 100, 200)
        assert 0 < mid < 200


class TestEaseInOut:
    def test_zero(self):
        from app.bot.mouse_engine import _ease_in_out
        assert _ease_in_out(0) == 0

    def test_one(self):
        from app.bot.mouse_engine import _ease_in_out
        assert _ease_in_out(1) == 1

    def test_half_is_half(self):
        from app.bot.mouse_engine import _ease_in_out
        assert _ease_in_out(0.5) == pytest.approx(0.5)

    def test_slow_start(self):
        from app.bot.mouse_engine import _ease_in_out
        # At t=0.25, eased value should be less than 0.25 (slow start)
        assert _ease_in_out(0.25) < 0.25

    def test_fast_end_approach(self):
        from app.bot.mouse_engine import _ease_in_out
        # At t=0.75, eased value should be greater than 0.75 (slow end)
        assert _ease_in_out(0.75) > 0.75


class TestLognormalDelay:
    def test_always_positive(self):
        from app.bot.mouse_engine import _lognormal_delay
        random.seed(42)
        for _ in range(100):
            assert _lognormal_delay(0.1) > 0

    def test_median_near_input(self):
        from app.bot.mouse_engine import _lognormal_delay
        random.seed(42)
        samples = [_lognormal_delay(0.5, sigma=0.1) for _ in range(1000)]
        median = sorted(samples)[500]
        assert 0.3 < median < 0.7


class TestFittsDuration:
    def test_zero_distance(self):
        from app.bot.mouse_engine import _fitts_duration
        result = _fitts_duration(0, 20)
        assert result == pytest.approx(0.15, abs=0.01)

    def test_increases_with_distance(self):
        from app.bot.mouse_engine import _fitts_duration
        short = _fitts_duration(100, 20)
        long = _fitts_duration(500, 20)
        assert long > short

    def test_decreases_with_target_size(self):
        from app.bot.mouse_engine import _fitts_duration
        small_target = _fitts_duration(200, 10)
        big_target = _fitts_duration(200, 50)
        assert small_target > big_target

    def test_clamps_tiny_target(self):
        from app.bot.mouse_engine import _fitts_duration
        result = _fitts_duration(100, 0.1)
        assert result > 0


class TestComputeStepDelays:
    def test_sum_approximates_total(self):
        from app.bot.mouse_engine import _compute_step_delays
        random.seed(42)
        delays = _compute_step_delays(20, 0.5)
        # Sum should be in reasonable range of total (lognormal jitter shifts it)
        assert 0.2 < sum(delays) < 1.5

    def test_all_positive(self):
        from app.bot.mouse_engine import _compute_step_delays
        random.seed(42)
        delays = _compute_step_delays(20, 0.5)
        assert all(d > 0 for d in delays)

    def test_bell_shaped(self):
        """Middle delays should be shorter than edge delays (higher velocity)."""
        from app.bot.mouse_engine import _compute_step_delays
        random.seed(42)
        delays = _compute_step_delays(30, 1.0)
        # Average of first+last 5 should be bigger than average of middle 5
        edge_avg = (sum(delays[:5]) + sum(delays[-5:])) / 10
        mid_start = len(delays) // 2 - 2
        mid_avg = sum(delays[mid_start:mid_start + 5]) / 5
        assert edge_avg > mid_avg

    def test_single_step(self):
        from app.bot.mouse_engine import _compute_step_delays
        delays = _compute_step_delays(1, 0.3)
        assert len(delays) == 1


# --- Path generation ---

class TestGenerateBezierPoints:
    def test_start_matches(self):
        from app.bot.mouse_engine import _generate_bezier_points
        random.seed(42)
        points = _generate_bezier_points(10, 20, 300, 400, 25)
        assert points[0] == (10, 20)

    def test_end_near_target(self):
        from app.bot.mouse_engine import _generate_bezier_points
        random.seed(42)
        points = _generate_bezier_points(10, 20, 300, 400, 25)
        ex, ey = points[-1]
        # Last point is anchored (no jitter applied to endpoints)
        assert ex == pytest.approx(300, abs=0.01)
        assert ey == pytest.approx(400, abs=0.01)

    def test_correct_count(self):
        from app.bot.mouse_engine import _generate_bezier_points
        random.seed(42)
        points = _generate_bezier_points(0, 0, 100, 100, 30)
        assert len(points) == 31  # steps + 1

    def test_not_straight_line(self):
        """Points should deviate from the direct path (jitter + wind)."""
        from app.bot.mouse_engine import _generate_bezier_points
        random.seed(42)
        points = _generate_bezier_points(0, 0, 100, 0, 20)
        # If perfectly straight, all y coords would be 0
        y_coords = [p[1] for p in points[1:-1]]
        assert any(abs(y) > 0.01 for y in y_coords)


class TestOvershootPath:
    def test_overshoots_past_target(self):
        from app.bot.mouse_engine import _generate_overshoot_path
        random.seed(42)
        points = _generate_overshoot_path(0, 0, 500, 0, 30)
        # Some point should be past x=500
        max_x = max(p[0] for p in points)
        assert max_x > 500

    def test_ends_near_target(self):
        from app.bot.mouse_engine import _generate_overshoot_path
        random.seed(42)
        points = _generate_overshoot_path(0, 0, 500, 0, 30)
        ex, ey = points[-1]
        assert ex == pytest.approx(500, abs=1)
        assert ey == pytest.approx(0, abs=1)

    def test_has_enough_points(self):
        from app.bot.mouse_engine import _generate_overshoot_path
        random.seed(42)
        points = _generate_overshoot_path(0, 0, 500, 0, 30)
        assert len(points) >= 20


class TestMicroCorrections:
    def test_correct_count(self):
        from app.bot.mouse_engine import _generate_micro_corrections
        random.seed(42)
        corrections = _generate_micro_corrections(100, 200, 3)
        assert len(corrections) == 3

    def test_ends_at_target(self):
        from app.bot.mouse_engine import _generate_micro_corrections
        random.seed(42)
        corrections = _generate_micro_corrections(100, 200, 4)
        assert corrections[-1] == (100, 200)

    def test_small_movements(self):
        from app.bot.mouse_engine import _generate_micro_corrections
        random.seed(42)
        corrections = _generate_micro_corrections(100, 200, 3)
        for cx, cy in corrections[:-1]:
            dist = math.hypot(cx - 100, cy - 200)
            assert dist <= 6  # within MICRO_CORRECTION_RADIUS max + margin

    def test_zero_count_returns_target(self):
        from app.bot.mouse_engine import _generate_micro_corrections
        corrections = _generate_micro_corrections(50, 60, 0)
        assert corrections == [(50, 60)]


class TestRandomPointInElement:
    def test_within_bounds(self):
        from app.bot.mouse_engine import _random_point_in_element
        random.seed(42)
        el = {"x": 100, "y": 200, "w": 80, "h": 30}
        for _ in range(1000):
            x, y = _random_point_in_element(el)
            assert el["x"] + 2 <= x <= el["x"] + el["w"] - 2
            assert el["y"] + 2 <= y <= el["y"] + el["h"] - 2

    def test_near_center(self):
        from app.bot.mouse_engine import _random_point_in_element
        random.seed(42)
        el = {"x": 0, "y": 0, "w": 200, "h": 200}
        xs, ys = [], []
        for _ in range(1000):
            x, y = _random_point_in_element(el)
            xs.append(x)
            ys.append(y)
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        assert 80 < mean_x < 120
        assert 80 < mean_y < 120


# --- CDP dispatch ---

class TestDispatchMouse:
    async def test_sends_cdp_command(self):
        from app.bot.mouse_engine import _dispatch_mouse
        tab = AsyncMock()
        await _dispatch_mouse(tab, "mouseMoved", 100, 200)
        tab.send.assert_called_once()

    async def test_wheel_includes_deltas(self):
        from app.bot.mouse_engine import _dispatch_mouse
        tab = AsyncMock()
        await _dispatch_mouse(tab, "mouseWheel", 50, 60, delta_x=0, delta_y=300)
        tab.send.assert_called_once()


# --- Public API ---

class TestMoveTo:
    async def test_updates_cursor_position(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.move_to(tab, 200, 150)
        assert mouse_engine._cursor_x == 200
        assert mouse_engine._cursor_y == 150

    async def test_short_distance_skips_dispatch(self):
        from app.bot import mouse_engine
        mouse_engine._cursor_x = 100.0
        mouse_engine._cursor_y = 100.0
        tab = AsyncMock()
        await mouse_engine.move_to(tab, 100.5, 100.5)
        tab.send.assert_not_called()

    async def test_dispatches_mouse_moved_events(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        random.seed(42)
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.move_to(tab, 100, 100)
        # Should dispatch multiple mouseMoved events
        assert tab.send.call_count >= 10

    async def test_long_distance_uses_overshoot(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        random.seed(42)
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.move_to(tab, 500, 0)
        # Overshoot generates more points than regular
        assert tab.send.call_count >= 15


class TestClickAt:
    async def test_dispatches_press_and_release(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        random.seed(42)
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await mouse_engine.click_at(tab, 50, 50)
        # Should have at least one sleep for pre-click pause
        assert mock_sleep.call_count >= 3  # step delays + pre-click + click hold

    async def test_cursor_at_target_after_click(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.click_at(tab, 75, 80)
        assert mouse_engine._cursor_x == 75
        assert mouse_engine._cursor_y == 80


class TestClickElement:
    async def test_passes_element_size(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        tab = AsyncMock()
        el = {"x": 100, "y": 200, "w": 80, "h": 30, "text": "Click"}
        random.seed(42)
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.click_element(tab, el)
        # Cursor should be within element bounds
        assert el["x"] <= mouse_engine._cursor_x <= el["x"] + el["w"]
        assert el["y"] <= mouse_engine._cursor_y <= el["y"] + el["h"]


class TestScroll:
    async def test_single_dispatch(self):
        from app.bot import mouse_engine
        mouse_engine._cursor_x = 50.0
        mouse_engine._cursor_y = 60.0
        tab = AsyncMock()
        await mouse_engine.scroll(tab, 300)
        # Exactly one CDP call (no more double dispatch)
        assert tab.send.call_count == 1

    async def test_uses_cursor_position(self):
        from app.bot import mouse_engine
        mouse_engine._cursor_x = 123.0
        mouse_engine._cursor_y = 456.0
        tab = AsyncMock()
        await mouse_engine.scroll(tab, 200)
        tab.send.assert_called_once()


class TestResetCursor:
    def test_resets_to_zero(self):
        from app.bot import mouse_engine
        mouse_engine._cursor_x = 999.0
        mouse_engine._cursor_y = 888.0
        mouse_engine.reset_cursor()
        assert mouse_engine._cursor_x == 0.0
        assert mouse_engine._cursor_y == 0.0
