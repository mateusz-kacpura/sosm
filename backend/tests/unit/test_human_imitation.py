import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.human_imitation import HumanImitation


class TestCreateGhostCursor:
    def test_creates_cursor_for_page(self):
        page = MagicMock()
        with patch("app.bot.human_imitation.create_cursor") as mock_create:
            mock_create.return_value = MagicMock()
            cursor = HumanImitation.create_ghost_cursor(page)
            mock_create.assert_called_once_with(page)
            assert cursor is not None


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
