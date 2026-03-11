import logging
import os

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

        # Check if already logged in via cookies
        logged_in = await self.dom.find("div[aria-label='Facebook']", timeout=3.0)
        if logged_in:
            logger.info("Sesja juz aktywna - omijamy ekran logowania.")
            return True

        # Accept cookie banner
        accept_btn = await self.dom.find("button[data-cookiebanner='accept_button']", timeout=3.0)
        if accept_btn:
            await mouse_engine.click_element(self.tab, accept_btn)
            await HumanImitation.human_delay()

        # Enter email
        logger.info("Wprowadzanie poswiadczen...")
        email_field = await self.dom.find("input[name='email']")
        if email_field:
            await mouse_engine.click_element(self.tab, email_field)
            await HumanImitation.type_like_human(self.tab, self.account_email)
            await HumanImitation.human_delay()

        # Enter password
        pass_field = await self.dom.find("input[name='pass']")
        if pass_field:
            await mouse_engine.click_element(self.tab, pass_field)
            await HumanImitation.type_like_human(self.tab, password)

        # Click login button
        login_btn = await self.dom.find("button[name='login']")
        if login_btn:
            await mouse_engine.click_element(self.tab, login_btn)

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint/block
        if await CheckpointDetector.handle_checkpoint_if_needed(self.tab, self.screenshot_dir, self.account_email):
            logger.error("Logowanie zablokowane - Checkpoint!")
            return False

        logger.info("Pomyslnie zalogowano lub ominieto checkpointy.")
        return True

    async def publish_on_group(self, group_url: str, text: str, media_urls=None) -> bool:
        """Publish a text post to a Facebook group."""
        logger.info("Nawigacja do grupy: %s", group_url)

        await self.tab.get(group_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(self.tab, self.screenshot_dir, self.account_email):
            return False

        await HumanImitation.natural_scroll(self.tab, scrolls=2)

        try:
            # Find the "Write something" / "Create public post" button
            post_box = await self.dom.find_text("Napisz cos", tag="div[role='button']", timeout=15.0)
            if not post_box:
                post_box = await self.dom.find_text("Utwórz publiczny post", tag="div[role='button']", timeout=5.0)
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
