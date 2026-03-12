import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.actions import FBActions


def make_mock_tab(url="https://www.facebook.com/"):
    """Create a mock nodriver Tab."""
    tab = AsyncMock()
    tab.get = AsyncMock()
    tab.evaluate = AsyncMock()
    tab.save_screenshot = AsyncMock()
    tab.url = url
    return tab


def make_mock_dom_walker():
    """Create a mock DomWalker."""
    walker = AsyncMock()
    walker.find = AsyncMock(return_value=None)
    walker.find_text = AsyncMock(return_value=None)
    return walker


class TestLogin:
    async def test_already_logged_in(self):
        """When input[name='email'] is NOT found, user is already logged in."""
        tab = make_mock_tab()
        walker = make_mock_dom_walker()
        # No login form found → already logged in
        walker.find = AsyncMock(return_value=None)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            result = await actions.login("password123")

        assert result is True

    async def test_login_success_flow(self):
        tab = make_mock_tab()
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
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.mouse_engine.click_element", new_callable=AsyncMock) as mock_click:
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        result = await actions.login("password123")

        assert result is True
        assert mock_click.call_count >= 2

    async def test_login_checkpoint_blocked(self):
        tab = make_mock_tab()
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
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.mouse_engine.click_element", new_callable=AsyncMock):
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                        result = await actions.login("password123")

        assert result is False

    async def test_cookie_banner_accepted(self):
        tab = make_mock_tab()
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
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                with patch("app.bot.actions.mouse_engine.click_element", new_callable=AsyncMock) as mock_click:
                    with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                        await actions.login("password123")

        mock_click.assert_any_call(tab, cookie_btn)


class TestPublishOnGroup:
    async def test_publish_success(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()

        post_box = {"x": 100, "y": 200, "w": 500, "h": 40, "text": "Napisz cos"}
        editor = {"x": 100, "y": 300, "w": 500, "h": 200, "text": ""}
        publish_btn = {"x": 400, "y": 550, "w": 100, "h": 40, "text": "Opublikuj"}

        walker.find_text = AsyncMock(side_effect=[post_box, publish_btn])
        walker.find = AsyncMock(return_value=editor)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.mouse_engine.click_element", new_callable=AsyncMock):
                        with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                            result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is True

    async def test_publish_checkpoint_detected(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=True):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False

    async def test_publish_timeout_returns_false(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()
        walker.find_text = AsyncMock(return_value=None)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                    result = await actions.publish_on_group("https://fb.com/groups/1", "Hello!")

        assert result is False
        tab.save_screenshot.assert_called_once()

    async def test_publish_with_media_urls_no_crash(self):
        tab = make_mock_tab()
        walker = make_mock_dom_walker()

        post_box = {"x": 100, "y": 200, "w": 500, "h": 40, "text": "Napisz cos"}
        editor = {"x": 100, "y": 300, "w": 500, "h": 200, "text": ""}
        publish_btn = {"x": 400, "y": 550, "w": 100, "h": 40, "text": "Opublikuj"}

        walker.find_text = AsyncMock(side_effect=[post_box, publish_btn])
        walker.find = AsyncMock(return_value=editor)

        with patch("app.bot.actions.DomWalker", return_value=walker):
            actions = FBActions(tab, "test@fb.com")

        with patch("app.bot.actions.HumanImitation.human_delay", new_callable=AsyncMock):
            with patch("app.bot.actions.HumanImitation.natural_scroll", new_callable=AsyncMock):
                with patch("app.bot.actions.HumanImitation.type_like_human", new_callable=AsyncMock):
                    with patch("app.bot.actions.mouse_engine.click_element", new_callable=AsyncMock):
                        with patch("app.bot.actions.CheckpointDetector.handle_checkpoint_if_needed", new_callable=AsyncMock, return_value=False):
                            result = await actions.publish_on_group(
                                "https://fb.com/groups/1", "Hello!", media_urls=["img.jpg"]
                            )

        assert result is True
