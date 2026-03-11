import logging
import os
from playwright.async_api import Page, TimeoutError

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector

logger = logging.getLogger(__name__)

from typing import List

class FBActions:
    """Implementuje docelowe akcje bota na profilu np. Logowanie, Rzucanie posta na grupkę.
       Wymaga wstrzykniętej podstrony Playwright (Page) stworzonej przez BrowserManager.
    """

    def __init__(self, page: Page, account_email: str):
        self.page = page
        self.account_email = account_email
        self.screenshot_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")
        self.cursor = HumanImitation.create_ghost_cursor(page)

    async def login(self, password: str) -> bool:
        """Przeprowadza proces logowania, jeśli ciasteczka/sesja wygasły"""
        logger.info(f"Rozpoczynam logowanie dla: {self.account_email}")
        await self.page.goto("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 5)

        # Sprawdzamy czy już jesteśmy zalogowani po ciasteczkach
        if await self.page.query_selector("div[aria-label='Facebook']"):
            logger.info("Sesja już aktywna - omijamy ekran logowania.")
            return True

        # Akceptacja cookies
        try:
            accept_button = await self.page.wait_for_selector("button[data-cookiebanner='accept_button']", timeout=3000)
            if accept_button:
                await self.cursor.click("button[data-cookiebanner='accept_button']")
                await HumanImitation.human_delay()
        except TimeoutError:
            pass  # Nie było ekranu RODO/Cookies

        # Wpisanie Loginu i Hasła z ruchem kursora do pola
        logger.info("Wprowadzanie poświadczeń...")
        await self.cursor.move("input[name='email']")
        await HumanImitation.type_like_human(self.page, "input[name='email']", self.account_email)
        await HumanImitation.human_delay()
        await self.cursor.move("input[name='pass']")
        await HumanImitation.type_like_human(self.page, "input[name='pass']", password)

        # Kliknięcie "Zaloguj" z Ghost Cursor (ruch po krzywej Béziera + klik)
        await self.cursor.click("button[name='login']")

        await HumanImitation.human_delay(4, 7)

        # Weryfikacja czy zostaliśmy wpuszczeni czy wyrzuceni na checkpoint
        if await CheckpointDetector.handle_checkpoint_if_needed(self.page, self.screenshot_dir, self.account_email):
            logger.error("Logowanie zablokowane - Checkpoint!")
            return False

        logger.info("Pomyślnie zalogowano lub ominięto checkpointy.")
        return True

    async def publish_on_group(self, group_url: str, text: str, media_urls: List[str] = None) -> bool:
        """Publikuje post do podlinkowanej grupy z tekstową zawartością"""
        logger.info(f"Nawigacja do grupy: {group_url}")

        await self.page.goto(group_url, wait_until="domcontentloaded")
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(self.page, self.screenshot_dir, self.account_email):
            return False

        await HumanImitation.natural_scroll(self.page, scrolls=2)

        try:
            # Selektory FB czesto się zmieniają - szukamy pola 'Utwórz publiczny post', 'Napisz coś...', etc.
            post_box_selector = "div[role='button']:has-text('Napisz coś'), div[role='button']:has-text('Utwórz publiczny post')"
            await self.page.wait_for_selector(post_box_selector, timeout=15000)
            await self.cursor.click(post_box_selector)

            await HumanImitation.human_delay()

            # Modal się pojawił - szukamy pola tekstowego
            editor_selector = "div[role='textbox'][contenteditable='true']"
            await self.page.wait_for_selector(editor_selector)
            await self.cursor.click(editor_selector)
            await HumanImitation.type_like_human(self.page, editor_selector, text, delay_range=(0.02, 0.08))

            if media_urls:
                logger.info("TODO: Dodawanie zdjęć nieobsługiwane w pierwszym MVP")

            await HumanImitation.human_delay(2, 4)

            # Wciśnij Opublikuj
            publish_selector = "div[aria-label='Opublikuj'], button:has-text('Opublikuj')"
            await self.page.wait_for_selector(publish_selector, state="visible")
            await self.cursor.click(publish_selector)

            # Okienko może jeszcze chwilę wisieć po wysłaniu pakietu POST do GraphAPI FB
            await HumanImitation.human_delay(5, 8)

            logger.info("Sukces: Post opublikowany (lub wysłany do akceptacji admina)")
            return True

        except TimeoutError:
            logger.error("Nie znaleziono pola tekstowego na grupie (brak uprawnień lub nowy UI / blokada)")
            await self.page.screenshot(path=os.path.join(self.screenshot_dir, f"error_group_{self.account_email}.png"))
            return False
