import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.bot.actions import FBActions


def make_mock_cursor():
    cursor = MagicMock()
    cursor.click = AsyncMock()
    cursor.move = AsyncMock()
    return cursor


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

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=make_mock_cursor()):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            result = await actions.login("password123")

        assert result is True

    async def test_login_success_flow(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        # Not logged in initially
        page.query_selector = AsyncMock(return_value=None)
        # Cookie banner times out (no login_btn wait_for_selector needed — cursor.click handles it)
        page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                    result = await actions.login("password123")

        assert result is True
        # Ghost cursor clicked login button
        mock_cursor.click.assert_called_with("button[name='login']")

    async def test_login_checkpoint_blocked(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        page.query_selector = AsyncMock(return_value=None)
        page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                    result = await actions.login("password123")

        assert result is False

    async def test_cookie_banner_accepted(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        cookie_btn = AsyncMock()
        cookie_btn.click = AsyncMock()

        page.query_selector = AsyncMock(return_value=None)
        # Cookie banner found on first wait_for_selector
        page.wait_for_selector = AsyncMock(return_value=cookie_btn)

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                    await actions.login("password123")

        # Cookie banner clicked via ghost cursor
        mock_cursor.click.assert_any_call("button[data-cookiebanner='accept_button']")


class TestPublishOnGroup:
    async def test_publish_success(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        post_box = AsyncMock()
        editor = AsyncMock()
        publish_btn = AsyncMock()

        page.wait_for_selector = AsyncMock(side_effect=[
            post_box,     # Post creation box
            editor,       # Text editor
            publish_btn,  # Publish button
        ])

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is True
        # Ghost cursor clicked publish button
        assert mock_cursor.click.call_count >= 3  # post_box + editor + publish

    async def test_publish_checkpoint_detected(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False

    async def test_publish_timeout_error(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()
        page.wait_for_selector = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False
        page.screenshot.assert_called_once()

    async def test_publish_with_media_urls_no_crash(self):
        page = make_mock_page()
        mock_cursor = make_mock_cursor()

        post_box = AsyncMock()
        editor = AsyncMock()
        publish_btn = AsyncMock()

        page.wait_for_selector = AsyncMock(side_effect=[
            post_box, editor, publish_btn,
        ])

        with patch("app.bot.actions.HumanImitation.create_ghost_cursor", return_value=mock_cursor):
            actions = FBActions(page, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        result = await actions.publish_on_group(
                            "https://fb.com/groups/1", "Hello!", media_urls=["img.jpg"]
                        )

        assert result is True
