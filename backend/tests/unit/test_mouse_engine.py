import random
from unittest.mock import AsyncMock, patch

import pytest


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


class TestMoveTo:
    async def test_updates_cursor_position(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        page = AsyncMock()
        await mouse_engine.move_to(page, 200, 150)
        assert mouse_engine._cursor_x == 200
        assert mouse_engine._cursor_y == 150
        page.mouse.move.assert_called_once_with(200, 150)


class TestClickAt:
    async def test_calls_page_mouse_click(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        page = AsyncMock()
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.click_at(page, 50, 50)
        page.mouse.click.assert_called_once_with(50, 50)

    async def test_cursor_at_target_after_click(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        page = AsyncMock()
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.click_at(page, 75, 80)
        assert mouse_engine._cursor_x == 75
        assert mouse_engine._cursor_y == 80


class TestClickElement:
    async def test_clicks_within_element_bounds(self):
        from app.bot import mouse_engine
        mouse_engine.reset_cursor()
        page = AsyncMock()
        el = {"x": 100, "y": 200, "w": 80, "h": 30, "text": "Click"}
        random.seed(42)
        with patch("app.bot.mouse_engine.asyncio.sleep", new_callable=AsyncMock):
            await mouse_engine.click_element(page, el)
        # Cursor should be within element bounds
        assert el["x"] <= mouse_engine._cursor_x <= el["x"] + el["w"]
        assert el["y"] <= mouse_engine._cursor_y <= el["y"] + el["h"]


class TestScroll:
    async def test_calls_page_mouse_wheel(self):
        from app.bot import mouse_engine
        page = AsyncMock()
        await mouse_engine.scroll(page, 300)
        page.mouse.wheel.assert_called_once_with(0, 300)


class TestResetCursor:
    def test_resets_to_zero(self):
        from app.bot import mouse_engine
        mouse_engine._cursor_x = 999.0
        mouse_engine._cursor_y = 888.0
        mouse_engine.reset_cursor()
        assert mouse_engine._cursor_x == 0.0
        assert mouse_engine._cursor_y == 0.0
