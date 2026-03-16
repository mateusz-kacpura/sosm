import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.actions import FBActions


def make_mock_page(url="https://www.facebook.com/"):
    """Create a mock Playwright Page."""
    page = AsyncMock()
    page.goto = AsyncMock()
    page.evaluate = AsyncMock()
    page.screenshot = AsyncMock()
    page.url = url
    page.keyboard = AsyncMock()
    page.mouse = AsyncMock()
    return page


def make_mock_dom_walker():
    """Create a mock DomWalker."""
    walker = AsyncMock()
    walker.find = AsyncMock(return_value=None)
    walker.find_text = AsyncMock(return_value=None)
    walker.find_activity_review_dialog = AsyncMock(return_value=None)
    return walker


# Patch paths — HumanImitation is imported in auth_mixin/publish_mixin, not actions
_HUMAN_DELAY = "app.bot.auth_mixin.HumanImitation.human_delay"
_TYPE_HUMAN = "app.bot.auth_mixin.HumanImitation.type_like_human"
_MOUSE_CLICK = "app.bot.auth_mixin.mouse_engine.click_element"
_CHECKPOINT = "app.bot.auth_mixin.CheckpointDetector.handle_checkpoint_if_needed"

_PUB_HUMAN_DELAY = "app.bot.publish_mixin.HumanImitation.human_delay"
_PUB_NATURAL_SCROLL = "app.bot.publish_mixin.HumanImitation.natural_scroll"
_PUB_TYPE_HUMAN = "app.bot.publish_mixin.HumanImitation.type_like_human"
_PUB_MOUSE_CLICK = "app.bot.publish_mixin.mouse_engine.click_element"
_PUB_CHECKPOINT = "app.bot.publish_mixin.CheckpointDetector.handle_checkpoint_if_needed"


class TestLogin:
    async def test_already_logged_in(self):
        """When input[name='email'] is NOT found and nav bar is present, user is already logged in."""
        page = make_mock_page()
        walker = make_mock_dom_walker()
        nav_bar = {"x": 0, "y": 0, "w": 1000, "h": 50, "text": ""}
        # No login form found, but nav bar found → already logged in
        walker.find = AsyncMock(side_effect=[
            None,     # input[name='email'] not found
            nav_bar,  # div[role='banner'] found → session active
        ])

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_HUMAN_DELAY, new_callable=AsyncMock):
            result = await actions.login("password123")

        assert result is True

    async def test_login_success_flow(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()
        email_field = {"x": 100, "y": 200, "w": 200, "h": 30, "text": ""}
        login_btn = {"x": 100, "y": 300, "w": 100, "h": 40, "text": "Log in"}

        walker.find = AsyncMock(side_effect=[
            email_field,  # Login form found → need to login
            None,         # Cookie banner not found
            {"x": 100, "y": 250, "w": 200, "h": 30, "text": ""},  # pass field
            None,         # Verification: login form gone → success
        ])
        walker.find_login_button = AsyncMock(return_value=login_btn)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_TYPE_HUMAN, new_callable=AsyncMock):
                with patch(_MOUSE_CLICK, new_callable=AsyncMock) as mock_click:
                    with patch(_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                        result = await actions.login("password123")

        assert result is True
        assert mock_click.call_count >= 2

    async def test_login_checkpoint_blocked(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()
        email_field = {"x": 100, "y": 200, "w": 200, "h": 30, "text": ""}

        walker.find = AsyncMock(side_effect=[
            email_field,  # Login form found → need to login
            None,         # Cookie banner
            {"x": 100, "y": 250, "w": 200, "h": 30, "text": ""},  # pass field
        ])
        walker.find_login_button = AsyncMock(
            return_value={"x": 100, "y": 300, "w": 100, "h": 40, "text": "Log in"}
        )

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_TYPE_HUMAN, new_callable=AsyncMock):
                with patch(_MOUSE_CLICK, new_callable=AsyncMock):
                    with patch(_CHECKPOINT, new_callable=AsyncMock, return_value=True):
                        result = await actions.login("password123")

        assert result is False

    async def test_cookie_banner_accepted(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()
        email_field = {"x": 100, "y": 200, "w": 200, "h": 30, "text": ""}
        cookie_btn = {"x": 400, "y": 300, "w": 120, "h": 40, "text": "Accept"}

        walker.find = AsyncMock(side_effect=[
            email_field,  # Login form found
            cookie_btn,   # Cookie banner found
            email_field,  # Re-find email after cookie accept
            {"x": 100, "y": 250, "w": 200, "h": 30, "text": ""},  # pass
            None,         # Verification: login form gone
        ])
        walker.find_login_button = AsyncMock(
            return_value={"x": 100, "y": 300, "w": 100, "h": 40, "text": "Log in"}
        )

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_TYPE_HUMAN, new_callable=AsyncMock):
                with patch(_MOUSE_CLICK, new_callable=AsyncMock) as mock_click:
                    with patch(_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                        await actions.login("password123")

        mock_click.assert_any_call(page, cookie_btn)


class TestPublishOnGroup:
    async def test_publish_success(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()

        composer = {"x": 100, "y": 200, "w": 500, "h": 40, "text": "Write something"}
        dialog_el = {"x": 0, "y": 0, "w": 800, "h": 600, "text": ""}
        editor = {"x": 100, "y": 300, "w": 500, "h": 200, "text": ""}
        publish_btn = {"x": 400, "y": 550, "w": 100, "h": 40, "text": "Post"}

        walker.find_group_composer = AsyncMock(return_value=composer)
        walker.find_dialog_submit_button = AsyncMock(side_effect=[publish_btn, None])
        walker.find = AsyncMock(side_effect=[dialog_el, editor])

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_PUB_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_PUB_NATURAL_SCROLL, new_callable=AsyncMock):
                with patch(_PUB_TYPE_HUMAN, new_callable=AsyncMock):
                    with patch(_PUB_MOUSE_CLICK, new_callable=AsyncMock):
                        with patch(_PUB_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                            with patch("app.bot.dom_walker._eval_js", new_callable=AsyncMock, return_value=None):
                                result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is True

    async def test_publish_checkpoint_detected(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_PUB_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_PUB_NATURAL_SCROLL, new_callable=AsyncMock):
                with patch(_PUB_CHECKPOINT, new_callable=AsyncMock, return_value=True):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False

    async def test_publish_composer_not_found(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()
        walker.find_group_composer = AsyncMock(return_value=None)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_PUB_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_PUB_NATURAL_SCROLL, new_callable=AsyncMock):
                with patch(_PUB_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                    with patch("app.bot.dom_walker._eval_js", new_callable=AsyncMock, return_value=None):
                        result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False
        page.screenshot.assert_called_once()

    async def test_publish_handles_confirmation_dialog(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()

        composer = {"x": 100, "y": 200, "w": 500, "h": 40, "text": "Write"}
        editor = {"x": 100, "y": 300, "w": 500, "h": 200, "text": ""}
        publish_btn = {"x": 400, "y": 550, "w": 100, "h": 40, "text": "Post"}
        confirm_btn = {"x": 400, "y": 400, "w": 200, "h": 40, "text": "Accept"}

        walker.find_group_composer = AsyncMock(return_value=composer)
        walker.find_dialog_submit_button = AsyncMock(
            side_effect=[publish_btn, confirm_btn, None]
        )
        walker.find = AsyncMock(return_value=editor)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_PUB_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_PUB_NATURAL_SCROLL, new_callable=AsyncMock):
                with patch(_PUB_TYPE_HUMAN, new_callable=AsyncMock):
                    with patch(_PUB_MOUSE_CLICK, new_callable=AsyncMock) as mock_click:
                        with patch(_PUB_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                            with patch("app.bot.dom_walker._eval_js", new_callable=AsyncMock, return_value=None):
                                result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is True
        assert mock_click.call_count >= 3

    async def test_publish_with_media_urls_no_crash(self):
        page = make_mock_page()
        walker = make_mock_dom_walker()

        composer = {"x": 100, "y": 200, "w": 500, "h": 40, "text": "Write something"}
        dialog_el = {"x": 0, "y": 0, "w": 800, "h": 600, "text": ""}
        editor = {"x": 100, "y": 300, "w": 500, "h": 200, "text": ""}
        publish_btn = {"x": 400, "y": 550, "w": 100, "h": 40, "text": "Post"}

        walker.find_group_composer = AsyncMock(return_value=composer)
        walker.find_dialog_submit_button = AsyncMock(side_effect=[publish_btn, None])
        walker.find = AsyncMock(side_effect=[dialog_el, editor])

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(page, "test@fb.com")

        with patch(_PUB_HUMAN_DELAY, new_callable=AsyncMock):
            with patch(_PUB_NATURAL_SCROLL, new_callable=AsyncMock):
                with patch(_PUB_TYPE_HUMAN, new_callable=AsyncMock):
                    with patch(_PUB_MOUSE_CLICK, new_callable=AsyncMock):
                        with patch(_PUB_CHECKPOINT, new_callable=AsyncMock, return_value=False):
                            with patch("app.bot.dom_walker._eval_js", new_callable=AsyncMock, return_value=None):
                                result = await actions.publish_on_group(
                                    "https://fb.com/groups/1", "Hello!", media_urls=["img.jpg"]
                                )

        assert result is True
