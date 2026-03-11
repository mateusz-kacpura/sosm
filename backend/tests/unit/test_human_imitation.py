import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.human_imitation import HumanImitation


class TestBezierCurve:
    def test_bezier_curve_start_point(self):
        p0 = (0, 0)
        p1 = (50, 100)
        p2 = (150, 100)
        p3 = (200, 200)
        result = HumanImitation._bezier_curve(0.0, p0, p1, p2, p3)
        assert result == p0

    def test_bezier_curve_end_point(self):
        p0 = (0, 0)
        p1 = (50, 100)
        p2 = (150, 100)
        p3 = (200, 200)
        result = HumanImitation._bezier_curve(1.0, p0, p1, p2, p3)
        assert result == p3

    def test_bezier_curve_midpoint_reasonable(self):
        p0 = (0, 0)
        p1 = (50, 50)
        p2 = (150, 150)
        p3 = (200, 200)
        result = HumanImitation._bezier_curve(0.5, p0, p1, p2, p3)
        assert 0 <= result[0] <= 200
        assert 0 <= result[1] <= 200


class TestGenerateBezierPoints:
    def test_correct_number_of_points(self):
        points = HumanImitation._generate_bezier_points((0, 0), (100, 100), steps=15)
        assert len(points) == 15

    def test_starts_at_start(self):
        points = HumanImitation._generate_bezier_points((10, 20), (100, 200), steps=10)
        assert points[0] == (10, 20)

    def test_ends_at_end(self):
        points = HumanImitation._generate_bezier_points((10, 20), (100, 200), steps=10)
        assert points[-1] == (100, 200)

    def test_default_steps(self):
        points = HumanImitation._generate_bezier_points((0, 0), (100, 100))
        assert len(points) == 20


class TestNaturalMouseMove:
    async def test_calls_mouse_move_multiple_times(self):
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.move = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.natural_mouse_move(page, 0, 0, 100, 100)

        assert page.mouse.move.call_count > 1

    async def test_steps_depend_on_distance(self):
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.move = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.natural_mouse_move(page, 0, 0, 10, 10)
            short_calls = page.mouse.move.call_count

        page.mouse.move.reset_mock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.natural_mouse_move(page, 0, 0, 1000, 1000)
            long_calls = page.mouse.move.call_count

        assert long_calls >= short_calls


class TestTypeLikeHuman:
    async def test_types_each_character(self):
        page = MagicMock()
        element = AsyncMock()
        page.wait_for_selector = AsyncMock(return_value=element)
        page.keyboard = MagicMock()
        page.keyboard.press = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(page, "#input", "abc")

        assert page.keyboard.press.call_count == 3
        calls = [c.args[0] for c in page.keyboard.press.call_args_list]
        assert calls == ["a", "b", "c"]

    async def test_clicks_element_before_typing(self):
        page = MagicMock()
        element = AsyncMock()
        page.wait_for_selector = AsyncMock(return_value=element)
        page.keyboard = MagicMock()
        page.keyboard.press = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(page, "#input", "x")

        element.click.assert_called_once()


class TestHumanDelay:
    async def test_sleeps_within_range(self):
        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await HumanImitation.human_delay(1.0, 2.0)
            mock_sleep.assert_called_once()
            sleep_value = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_value <= 2.0


class TestNaturalScroll:
    async def test_calls_mouse_wheel(self):
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            with patch.object(HumanImitation, "human_delay", new_callable=AsyncMock):
                await HumanImitation.natural_scroll(page, scrolls=3)

        assert page.mouse.wheel.call_count == 3
