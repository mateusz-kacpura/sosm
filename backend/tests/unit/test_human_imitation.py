import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.human_imitation import HumanImitation


class TestTypeLikeHuman:
    async def test_types_each_character(self):
        page = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(page, "abc")

        # Each character calls page.keyboard.insert_text once
        assert page.keyboard.insert_text.call_count == 3

    async def test_types_single_character(self):
        page = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(page, "x")

        assert page.keyboard.insert_text.call_count == 1


class TestHumanDelay:
    async def test_sleeps_within_range(self):
        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await HumanImitation.human_delay(1.0, 2.0)
            mock_sleep.assert_called_once()
            sleep_value = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_value <= 2.0


class TestNaturalScroll:
    async def test_calls_mouse_engine_scroll(self):
        page = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            with patch("app.bot.human_imitation.mouse_engine.scroll", new_callable=AsyncMock) as mock_scroll:
                with patch.object(HumanImitation, "human_delay", new_callable=AsyncMock):
                    await HumanImitation.natural_scroll(page, scrolls=3)

        assert mock_scroll.call_count == 3
