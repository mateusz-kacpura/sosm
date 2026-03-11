import asyncio
import os
import json
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from playwright_stealth import stealth
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class BrowserManager:
    def __init__(self, account_email: str, proxy_url: str = None, session_file: str = None):
        self.account_email = account_email
        self.proxy_url = proxy_url
        
        # Tworzenie nazwy pliku sesji jeśli nie podano
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.session_file = session_file or os.path.join(base_dir, "sessions", f"{account_email}_storage.json")
        
        self._playwright = None
        self._browser: Browser = None
        self._context: BrowserContext = None
        
    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self) -> Page:
        self._playwright = await async_playwright().start()
        
        launch_args = {
            "headless": False, # TODO: Ustawić na True w produkcji
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        }
        
        if self.proxy_url:
            launch_args["proxy"] = {"server": self.proxy_url}
            
        self._browser = await self._playwright.chromium.launch(**launch_args)
        
        context_args = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        if os.path.exists(self.session_file):
            logger.info(f"Wczytywanie sesji z {self.session_file}")
            # Playwright obsługuje wczytywanie cookies + localstorage przez storage_state
            context_args["storage_state"] = self.session_file
            
        self._context = await self._browser.new_context(**context_args)
        
        page = await self._context.new_page()
        # Aplikujemy stealth do omijania detekcji "webdriver=true" itp.
        await stealth(page)
        
        return page
        
    async def save_session(self):
        """Zapisuje stan sesji (Local Storage / Ciasteczka) do pliku by ominąć ponowne logowanie"""
        if self._context:
            logger.info(f"Zapisywanie stanu sesji do {self.session_file}")
            await self._context.storage_state(path=self.session_file)

    async def stop(self):
        if self._context:
            await self.save_session()
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
