import asyncio
import logging
import os

from .dom_walker import DomWalker

logger = logging.getLogger(__name__)


class CheckpointDetector:
    """Detects Facebook security checkpoints and account locks."""

    CHECKPOINT_TEXTS = [
        "Podejrzane logowanie",
        "Sprawdź swoje powiadomienia na innym urządzeniu",
        "Wprowadź kod z generatora kodów",
        "Pomóż nam potwierdzić Twoją tożsamość",
        "Your Account Has Been Locked",
        "Twoje konto zostało zablokowane",
        "Security Check",
    ]

    CHECKPOINT_SELECTORS = [
        "input[name='approvals_code']",
        "div[aria-label='Captcha']",
    ]

    @staticmethod
    async def is_checkpoint_active(tab) -> bool:
        """Check if the current page shows a checkpoint/block."""
        try:
            dom = DomWalker(tab)

            # Check text-based selectors
            for text in CheckpointDetector.CHECKPOINT_TEXTS:
                el = await dom.find_text(text, timeout=0.5)
                if el:
                    logger.warning("Wykryto potencjalny checkpoint/blokade: %s", text)
                    return True

            # Check CSS selectors
            for selector in CheckpointDetector.CHECKPOINT_SELECTORS:
                el = await dom.find(selector, timeout=0.5)
                if el:
                    logger.warning("Wykryto potencjalny checkpoint/blokade: %s", selector)
                    return True

            # Check URL
            current_url = tab.url or ""
            if "checkpoint" in current_url or "challenge" in current_url:
                logger.warning("Wykryto URL z checkpointem: %s", current_url)
                return True

        except Exception as e:
            logger.error("Blad podczas sprawdzania checkpointow: %s", e)

        return False

    @staticmethod
    async def handle_checkpoint_if_needed(tab, screenshot_dir: str, account_email: str) -> bool:
        """If checkpoint detected, take screenshot and return True."""
        if await CheckpointDetector.is_checkpoint_active(tab):
            await asyncio.sleep(2)

            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"checkpoint_{account_email}.png")

            await tab.save_screenshot(screenshot_path)
            logger.error("Zapisano zrzut ekranu checkpointu w: %s", screenshot_path)
            return True

        return False
