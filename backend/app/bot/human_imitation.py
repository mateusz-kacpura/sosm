import random
import asyncio
from typing import Tuple
from playwright.async_api import Page
from python_ghost_cursor.playwright_async import create_cursor

class HumanImitation:
    """Implementuje metody zachowań ludzkich dla bota Playwright."""

    @staticmethod
    def create_ghost_cursor(page: Page):
        """Tworzy instancję Ghost Cursor dla danej strony — humanizacja ruchów myszy."""
        return create_cursor(page)

    @staticmethod
    async def type_like_human(page: Page, selector: str, text: str, delay_range: Tuple[float, float] = (0.05, 0.15)):
        """Wpisuje tekst literka po literce, jak człowiek z ew. dłuższymi przerwami."""
        element = await page.wait_for_selector(selector)
        if element:
            await element.click()
            for char in text:
                await page.keyboard.press(char)
                await asyncio.sleep(random.uniform(*delay_range))

    @staticmethod
    async def human_delay(min_sec: float = 1.0, max_sec: float = 3.5):
        """Losowo wstrzymuje wykonanie symulując czytanie lub zastanawianie się"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def natural_scroll(page: Page, scrolls: int = 3):
        """Sprawia wrażenie czytania lub nawigowania w dół strony / grupy FB"""
        for _ in range(scrolls):
            direction = random.choice([1, -1]) if random.random() < 0.2 else 1  # 80% szans w dół
            distance = random.randint(100, 400) * direction
            await page.mouse.wheel(delta_x=0, delta_y=distance)
            await HumanImitation.human_delay(0.5, 2.0)
