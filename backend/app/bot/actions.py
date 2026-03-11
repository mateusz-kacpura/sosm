import logging
import asyncio
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
        
    async def login(self, password: str) -> bool:
        """Przeprowadza proces logowania, jeśli ciasteczka/sesja wygasły"""
        logger.info(f"Rozpoczynam logowanie dla: {self.account_email}")
        await self.page.goto("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 5) # Czekamy jak normalny user by strona załadowała skrypty trackujące FB
        
        # Sprawdzamy czy już jesteśmy zalogowani po ciasteczkach
        if await self.page.query_selector("div[aria-label='Facebook']"):
            logger.info("Sesja już aktywna - omijamy ekran logowania.")
            return True
            
        # Akceptacja cookies
        try:
            accept_button = await self.page.wait_for_selector("button[data-cookiebanner='accept_button']", timeout=3000)
            if accept_button:
                await accept_button.click()
                await HumanImitation.human_delay()
        except TimeoutError:
            pass # Nie było ekranu RODO/Cookies
            
        # Symulacja ruchu kursorem w rejon formularza
        await HumanImitation.natural_mouse_move(self.page, 100, 100, 600, 300)
        
        # Wpisanie Loginu i Hasła
        logger.info("Wprowadzanie poświadczeń...")
        await HumanImitation.type_like_human(self.page, "input[name='email']", self.account_email)
        await HumanImitation.human_delay()
        await HumanImitation.type_like_human(self.page, "input[name='pass']", password)
        
        # Kliknięcie "Zaloguj" krzywą Beziera
        login_btn = await self.page.wait_for_selector("button[name='login']")
        box = await login_btn.bounding_box()
        if box:
            target_x = box['x'] + box['width'] / 2
            target_y = box['y'] + box['height'] / 2
            await HumanImitation.natural_mouse_move(self.page, 600, 300, target_x, target_y)
            await login_btn.click()
            
        await HumanImitation.human_delay(4, 7) # FB miele logowanie
        
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

        await HumanImitation.natural_scroll(self.page, scrolls=2) # Scrolling po powiadomieniach i dyskusji z grupy
        
        try:
            # Selektory FB czesto się zmieniają - szukamy pola 'Utwórz publiczny post', 'Napisz coś...', etc.
            post_box = await self.page.wait_for_selector("div[role='button']:has-text('Napisz coś'), div[role='button']:has-text('Utwórz publiczny post')", timeout=15000)
            
            box = await post_box.bounding_box()
            if box:
                await HumanImitation.natural_mouse_move(self.page, 500, 500, box['x'] + 20, box['y'] + 10)
                await post_box.click()
                
            await HumanImitation.human_delay()
            
            # Modal się pojawił - szukamy pola tekstowego
            editor = await self.page.wait_for_selector("div[role='textbox'][contenteditable='true']")
            await editor.click()
            await HumanImitation.type_like_human(self.page, "div[role='textbox'][contenteditable='true']", text, delay_range=(0.02, 0.08))
            
            if media_urls:
               logger.info("TODO: Dodawanie zdjęć nieobsługiwane w pierwszym MVP")
            
            await HumanImitation.human_delay(2, 4)
            
            # Wciśnij Opublikuj
            publish_btn = await self.page.wait_for_selector("div[aria-label='Opublikuj'], button:has-text('Opublikuj')", state="visible")
            await publish_btn.click()
            
            # Okienko może jeszcze chwilę wisieć po wysłaniu pakietu POST do GraphAPI FB
            await HumanImitation.human_delay(5, 8)
            
            logger.info("Sukces: Post opublikowany (lub wysłany do akceptacji admina)")
            return True
            
        except TimeoutError:
            logger.error("Nie znaleziono pola tekstowego na grupie (brak uprawnień lub nowy UI / blokada)")
            await self.page.screenshot(path=os.path.join(self.screenshot_dir, f"error_group_{self.account_email}.png"))
            return False
