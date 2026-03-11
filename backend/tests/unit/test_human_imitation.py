import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.human_imitation import HumanImitation


class TestTypeLikeHuman:
    async def test_types_each_character(self):
        tab = AsyncMock()
        tab.send = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(tab, "abc")

        # Each character generates keyDown + keyUp = 2 calls per char
        assert tab.send.call_count == 6  # 3 chars * 2 events

    async def test_types_single_character(self):
        tab = AsyncMock()
        tab.send = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            await HumanImitation.type_like_human(tab, "x")

        assert tab.send.call_count == 2  # keyDown + keyUp


class TestHumanDelay:
    async def test_sleeps_within_range(self):
        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await HumanImitation.human_delay(1.0, 2.0)
            mock_sleep.assert_called_once()
            sleep_value = mock_sleep.call_args[0][0]
            assert 1.0 <= sleep_value <= 2.0


class TestNaturalScroll:
    async def test_calls_mouse_engine_scroll(self):
        tab = AsyncMock()

        with patch("app.bot.human_imitation.asyncio.sleep", new_callable=AsyncMock):
            with patch("app.bot.human_imitation.mouse_engine.scroll", new_callable=AsyncMock) as mock_scroll:
                with patch.object(HumanImitation, "human_delay", new_callable=AsyncMock):
                    await HumanImitation.natural_scroll(tab, scrolls=3)

        assert mock_scroll.call_count == 3
