import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.bot.actions import FBActions


def make_mock_page(url="https://www.facebook.com/"):
    page = MagicMock()
    page.goto = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock()
    page.screenshot = AsyncMock()
    type(page).url = PropertyMock(return_value=url)
    page.mouse = MagicMock()
    page.mouse.move = AsyncMock()
    page.mouse.wheel = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.press = AsyncMock()
    return page


class TestLogin:
    async def test_already_logged_in(self):
        page = make_mock_page()
        page.query_selector = AsyncMock(return_value=MagicMock())  # Finds the logged-in indicator

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            result = await actions.login("password123")

        assert result is True

    async def test_login_success_flow(self):
        page = make_mock_page()

        login_btn = AsyncMock()
        login_btn.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 80, "height": 30})
        login_btn.click = AsyncMock()

        # Not logged in initially
        page.query_selector = AsyncMock(return_value=None)
        # Cookie banner times out
        page.wait_for_selector = AsyncMock(side_effect=[
            PlaywrightTimeoutError("timeout"),  # Cookie banner
            login_btn,  # Login button
        ])

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_mouse_move", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        result = await actions.login("password123")

        assert result is True

    async def test_login_checkpoint_blocked(self):
        page = make_mock_page()

        login_btn = AsyncMock()
        login_btn.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 80, "height": 30})
        login_btn.click = AsyncMock()

        page.query_selector = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(side_effect=[
            PlaywrightTimeoutError("timeout"),  # Cookie banner
            login_btn,  # Login button
        ])

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_mouse_move", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                        result = await actions.login("password123")

        assert result is False

    async def test_cookie_banner_accepted(self):
        page = make_mock_page()

        cookie_btn = AsyncMock()
        cookie_btn.click = AsyncMock()

        login_btn = AsyncMock()
        login_btn.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 80, "height": 30})
        login_btn.click = AsyncMock()

        page.query_selector = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(side_effect=[
            cookie_btn,  # Cookie banner found
            login_btn,  # Login button
        ])

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_mouse_move", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        await actions.login("password123")

        cookie_btn.click.assert_called_once()


class TestPublishOnGroup:
    async def test_publish_success(self):
        page = make_mock_page()

        post_box = AsyncMock()
        post_box.bounding_box = AsyncMock(return_value={"x": 200, "y": 300, "width": 500, "height": 50})
        post_box.click = AsyncMock()

        editor = AsyncMock()
        editor.click = AsyncMock()

        publish_btn = AsyncMock()
        publish_btn.click = AsyncMock()

        page.wait_for_selector = AsyncMock(side_effect=[
            post_box,     # Post creation box
            editor,       # Text editor
            publish_btn,  # Publish button
        ])

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_mouse_move", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                    with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                        with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                            result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is True
        publish_btn.click.assert_called_once()

    async def test_publish_checkpoint_detected(self):
        page = make_mock_page()

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False

    async def test_publish_timeout_error(self):
        page = make_mock_page()
        page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False
        page.screenshot.assert_called_once()

    async def test_publish_with_media_urls_no_crash(self):
        page = make_mock_page()

        post_box = AsyncMock()
        post_box.bounding_box = AsyncMock(return_value={"x": 200, "y": 300, "width": 500, "height": 50})
        post_box.click = AsyncMock()

        editor = AsyncMock()
        editor.click = AsyncMock()

        publish_btn = AsyncMock()
        publish_btn.click = AsyncMock()

        page.wait_for_selector = AsyncMock(side_effect=[
            post_box, editor, publish_btn,
        ])

        actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_mouse_move", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                    with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                        with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                            result = await actions.publish_on_group(
                                "https://fb.com/groups/1", "Hello!", media_urls=["img.jpg"]
                            )

        assert result is True
