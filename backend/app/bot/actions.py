import logging
import os

import nodriver.cdp.input_

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector
from .dom_walker import DomWalker
from . import mouse_engine

logger = logging.getLogger(__name__)


class FBActions:
    """Facebook actions (login, publish) using nodriver Tab + CDP mouse engine.

    Requires an active nodriver Tab created by BrowserManager.
    """

    def __init__(self, tab, account_email: str):
        self.tab = tab
        self.account_email = account_email
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        self.dom = DomWalker(tab)

    async def login(self, password: str) -> bool:
        """Log into Facebook, return True if successful."""
        logger.info("Rozpoczynam logowanie dla: %s", self.account_email)
        await self.tab.get("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 5)

        # Check if already logged in via cookies.
        # The login form (input[name='email']) only exists when NOT logged in.
        login_form = await self.dom.find("input[name='email']", timeout=3.0)
        if not login_form:
            logger.info("Sesja juz aktywna - omijamy ekran logowania.")
            return True

        # Accept cookie banner
        accept_btn = await self.dom.find("button[data-cookiebanner='accept_button']", timeout=3.0)
        if accept_btn:
            await mouse_engine.click_element(self.tab, accept_btn)
            await HumanImitation.human_delay()
            # Re-find email field after accepting cookies (DOM may have changed)
            login_form = await self.dom.find("input[name='email']", timeout=5.0)

        # Enter email
        logger.info("Wprowadzanie poswiadczen...")
        if login_form:
            await mouse_engine.click_element(self.tab, login_form)
            await HumanImitation.type_like_human(self.tab, self.account_email)
            await HumanImitation.human_delay()

        # Enter password
        pass_field = await self.dom.find("input[name='pass']")
        if pass_field:
            await mouse_engine.click_element(self.tab, pass_field)
            await HumanImitation.type_like_human(self.tab, password)

        # Click login button.
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Znaleziono przycisk logowania: %s", login_btn.get("text", ""))
            await mouse_engine.click_element(self.tab, login_btn)
        else:
            # Debug: log what buttons exist on the page
            all_btns = await self.dom.find_all("button")
            logger.warning("Nie znaleziono przycisku logowania. Przyciski na stronie: %s",
                           [(b.get("text", "")[:50], b.get("w", 0), b.get("h", 0)) for b in all_btns])
            logger.info("Probuje submit formularza przez JS")
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint/block
        if await CheckpointDetector.handle_checkpoint_if_needed(self.tab, self.screenshot_dir, self.account_email):
            logger.error("Logowanie zablokowane - Checkpoint!")
            return False

        # Verify login succeeded — login form should be gone
        still_login = await self.dom.find("input[name='email']", timeout=2.0)
        if still_login:
            logger.error("Logowanie nie powiodlo sie - formularz nadal widoczny")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir, f"login_failed_{self.account_email}.png")
            )
            return False

        logger.info("Pomyslnie zalogowano.")
        return True

    async def _submit_login_form(self):
        """Submit login form via JS as last resort."""
        from .dom_walker import _eval_js
        await _eval_js(self.tab, """(() => {
            const form = document.querySelector('input[name="pass"]')?.closest('form');
            if (form) form.submit();
        })()""")

    async def publish_on_group(self, group_url: str, text: str, media_urls=None) -> bool:
        """Publish a text post to a Facebook group."""
        logger.info("Nawigacja do grupy: %s", group_url)

        await self.tab.get(group_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(self.tab, self.screenshot_dir, self.account_email):
            return False

        await HumanImitation.natural_scroll(self.tab, scrolls=2)

        try:
            # Find the "Write something" / "Create public post" button.
            # Try language-independent approach first, then fall back to text matching.
            post_box = await self.dom.find_text("Napisz co\u015b", tag="div[role='button']", timeout=10.0)
            if not post_box:
                post_box = await self.dom.find_text("Write something", tag="div[role='button']", timeout=3.0)
            if not post_box:
                post_box = await self.dom.find_text("Utw\u00f3rz publiczny post", tag="div[role='button']", timeout=3.0)
            if not post_box:
                post_box = await self.dom.find_text("Create public post", tag="div[role='button']", timeout=3.0)
            if not post_box:
                raise TimeoutError("Nie znaleziono pola do tworzenia postu")

            await mouse_engine.click_element(self.tab, post_box)
            await HumanImitation.human_delay()

            # Find the text editor in the modal
            editor = await self.dom.find("div[role='textbox'][contenteditable='true']")
            if not editor:
                raise TimeoutError("Nie znaleziono edytora tekstowego")

            await mouse_engine.click_element(self.tab, editor)
            await HumanImitation.type_like_human(self.tab, text, delay_range=(0.02, 0.08))

            if media_urls:
                logger.info("TODO: Dodawanie zdjec nieobslugiwane w pierwszym MVP")

            await HumanImitation.human_delay(2, 4)

            # Click Publish button
            publish_btn = await self.dom.find_text("Opublikuj", timeout=5.0)
            if not publish_btn:
                publish_btn = await self.dom.find_text("Post", tag="div[role='button']", timeout=3.0)
            if not publish_btn:
                raise TimeoutError("Nie znaleziono przycisku Opublikuj")

            await mouse_engine.click_element(self.tab, publish_btn)

            await HumanImitation.human_delay(5, 8)

            logger.info("Sukces: Post opublikowany (lub wyslany do akceptacji admina)")
            return True

        except (TimeoutError, Exception) as e:
            logger.error("Nie znaleziono pola tekstowego na grupie: %s", e)
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir, f"error_group_{self.account_email}.png")
            )
            return False
