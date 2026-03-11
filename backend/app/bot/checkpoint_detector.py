import asyncio
import logging
from playwright.async_api import Page
from .human_imitation import HumanImitation

logger = logging.getLogger(__name__)

class CheckpointDetector:
    """Moduł odpowiedzialny za weryfikację czy konto nie dostało blokady / weryfikacji."""
    
    CHECKPOINT_SELECTORS = [
        "text='Podejrzane logowanie'",
        "text='Sprawdź swoje powiadomienia na innym urządzeniu'",
        "text='Wprowadź kod z generatora kodów'",
        "text='Pomóż nam potwierdzić Twoją tożsamość'",
        "text='Your Account Has Been Locked'",
        "text='Twoje konto zostało zablokowane'",
        "text='Security Check'",
        "input[name='approvals_code']", # Kod SMS/2FA
        "div[aria-label='Captcha']"
    ]
    
    @staticmethod
    async def is_checkpoint_active(page: Page) -> bool:
        """Sprawdza czy na obencym ekranie widnieją informacje o checkpointach."""
        try:
            for selector in CheckpointDetector.CHECKPOINT_SELECTORS:
                # Szybki timeout by nie spowalniać bota za bardzo jeśli wszystko ok
                element = await page.query_selector(selector)
                if element:
                    logger.warning(f"Wykryto potencjalny checkpoint/blokadę: {selector}")
                    return True
            
            # Dodatkowe sprawdzenie po URL
            current_url = page.url
            if "checkpoint" in current_url or "challenge" in current_url:
                logger.warning(f"Wykryto URL z checkpointem: {current_url}")
                return True
                
        except Exception as e:
            logger.error(f"Błąd podczas sprawdzania checkpointów: {str(e)}")
            
        return False
        
    @staticmethod
    async def handle_checkpoint_if_needed(page: Page, screenshot_dir: str, account_email: str) -> bool:
        """Jeżeli wykryje checkpoint, robi screenshot i zwraca True (wymagana interwencja logiki nadrzędnej)"""
        if await CheckpointDetector.is_checkpoint_active(page):
            # Czekamy na załadowanie się w pełni ewentualnego formularza SMS/CAPTCH-y
            await asyncio.sleep(2)
            
            import os
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"checkpoint_{account_email}.png")
            
            await page.screenshot(path=screenshot_path)
            logger.error(f"Zapisano zrzut ekranu checkpointu w: {screenshot_path}")
            return True
            
        return False
