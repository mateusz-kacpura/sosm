import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.checkpoint_detector import CheckpointDetector


class TestIsCheckpointActive:
    async def test_no_checkpoint_returns_false(self):
        page = MagicMock()
        page.query_selector = AsyncMock(return_value=None)
        page.url = "https://www.facebook.com/home"

        result = await CheckpointDetector.is_checkpoint_active(page)
        assert result is False

    async def test_checkpoint_selector_detected(self):
        for selector in CheckpointDetector.CHECKPOINT_SELECTORS:
            page = MagicMock()

            async def side_effect(s):
                if s == selector:
                    return MagicMock()  # truthy element
                return None

            page.query_selector = AsyncMock(side_effect=side_effect)
            page.url = "https://www.facebook.com/home"

            result = await CheckpointDetector.is_checkpoint_active(page)
            assert result is True, f"Should detect checkpoint for selector: {selector}"

    async def test_checkpoint_url_detected(self):
        page = MagicMock()
        page.query_selector = AsyncMock(return_value=None)
        page.url = "https://www.facebook.com/checkpoint/123456"

        result = await CheckpointDetector.is_checkpoint_active(page)
        assert result is True

    async def test_challenge_url_detected(self):
        page = MagicMock()
        page.query_selector = AsyncMock(return_value=None)
        page.url = "https://www.facebook.com/challenge/789"

        result = await CheckpointDetector.is_checkpoint_active(page)
        assert result is True

    async def test_exception_in_detection_returns_false(self):
        page = MagicMock()
        page.query_selector = AsyncMock(side_effect=Exception("DOM error"))
        page.url = "https://www.facebook.com/home"

        result = await CheckpointDetector.is_checkpoint_active(page)
        assert result is False


class TestHandleCheckpointIfNeeded:
    async def test_takes_screenshot_when_detected(self):
        page = MagicMock()
        page.screenshot = AsyncMock()

        with patch.object(
            CheckpointDetector, "is_checkpoint_active", new_callable=AsyncMock, return_value=True
        ):
            with patch("app.bot.checkpoint_detector.asyncio.sleep", new_callable=AsyncMock):
                with patch("os.makedirs"):
                    result = await CheckpointDetector.handle_checkpoint_if_needed(
                        page, "/tmp/screenshots", "test@fb.com"
                    )

        assert result is True
        page.screenshot.assert_called_once()
        screenshot_path = page.screenshot.call_args[1]["path"]
        assert "test@fb.com" in screenshot_path

    async def test_returns_false_when_clean(self):
        page = MagicMock()
        page.screenshot = AsyncMock()

        with patch.object(
            CheckpointDetector, "is_checkpoint_active", new_callable=AsyncMock, return_value=False
        ):
            result = await CheckpointDetector.handle_checkpoint_if_needed(
                page, "/tmp/screenshots", "test@fb.com"
            )

        assert result is False
        page.screenshot.assert_not_called()
