import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.checkpoint_detector import CheckpointDetector


def make_mock_tab(url="https://www.facebook.com/home"):
    tab = AsyncMock()
    tab.url = url
    tab.save_screenshot = AsyncMock()
    return tab


def make_mock_dom_walker(find_result=None, find_text_result=None):
    walker = AsyncMock()
    walker.find = AsyncMock(return_value=find_result)
    walker.find_text = AsyncMock(return_value=find_text_result)
    return walker


class TestIsCheckpointActive:
    async def test_no_checkpoint_returns_false(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()

        with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
            result = await CheckpointDetector.is_checkpoint_active(tab)

        assert result is False

    async def test_checkpoint_text_detected(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()

        # find_text returns a hit for the first checkpoint text
        walker.find_text = AsyncMock(
            return_value={"x": 0, "y": 0, "w": 100, "h": 50, "text": "Podejrzane logowanie"}
        )

        with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
            result = await CheckpointDetector.is_checkpoint_active(tab)

        assert result is True

    async def test_checkpoint_selector_detected(self):
        for selector in CheckpointDetector.CHECKPOINT_SELECTORS:
            tab = make_mock_tab()
            walker = make_mock_dom_walker()

            # find_text returns None (no text match), but find returns a match for the selector
            walker.find_text = AsyncMock(return_value=None)

            async def find_side_effect(s, timeout=10.0, _sel=selector):
                if s == _sel:
                    return {"x": 0, "y": 0, "w": 100, "h": 50, "text": ""}
                return None

            walker.find = AsyncMock(side_effect=find_side_effect)

            with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
                result = await CheckpointDetector.is_checkpoint_active(tab)

            assert result is True, f"Should detect checkpoint for selector: {selector}"

    async def test_checkpoint_url_detected(self):
        tab = make_mock_tab(url="https://www.facebook.com/checkpoint/123456")
        walker = make_mock_dom_walker()

        with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
            result = await CheckpointDetector.is_checkpoint_active(tab)

        assert result is True

    async def test_challenge_url_detected(self):
        tab = make_mock_tab(url="https://www.facebook.com/challenge/789")
        walker = make_mock_dom_walker()

        with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
            result = await CheckpointDetector.is_checkpoint_active(tab)

        assert result is True

    async def test_exception_in_detection_returns_false(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()
        walker.find_text = AsyncMock(side_effect=Exception("DOM error"))

        with patch("app.bot.checkpoint_detector.DomWalker", return_value=walker):
            result = await CheckpointDetector.is_checkpoint_active(tab)

        assert result is False


class TestHandleCheckpointIfNeeded:
    async def test_takes_screenshot_when_detected(self):
        tab = make_mock_tab()

        with patch.object(
            CheckpointDetector, "is_checkpoint_active", new_callable=AsyncMock, return_value=True
        ):
            with patch("app.bot.checkpoint_detector.asyncio.sleep", new_callable=AsyncMock):
                with patch("app.bot.checkpoint_detector.os.makedirs"):
                    result = await CheckpointDetector.handle_checkpoint_if_needed(
                        tab, "/tmp/screenshots", "test@fb.com"
                    )

        assert result is True
        tab.save_screenshot.assert_called_once()
        screenshot_path = tab.save_screenshot.call_args[0][0]
        assert "test@fb.com" in screenshot_path

    async def test_returns_false_when_clean(self):
        tab = make_mock_tab()

        with patch.object(
            CheckpointDetector, "is_checkpoint_active", new_callable=AsyncMock, return_value=False
        ):
            result = await CheckpointDetector.handle_checkpoint_if_needed(
                tab, "/tmp/screenshots", "test@fb.com"
            )

        assert result is False
        tab.save_screenshot.assert_not_called()
