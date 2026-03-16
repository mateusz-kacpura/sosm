import logging
import os

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector
from . import mouse_engine

logger = logging.getLogger(__name__)


class AuthMixin:
    """Login and authentication methods for FBActions."""

    async def login(self, password: str) -> bool:
        """Log into Facebook, return True if successful."""
        self._last_password = password
        logger.info("Rozpoczynam logowanie dla: %s", self.account_email)
        await self.tab.get("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 5)

        # Check if already logged in via cookies.
        # The login form (input[name='email']) only exists when NOT logged in.
        login_form = await self.dom.find("input[name='email']", timeout=3.0)
        if not login_form:
            # Could be: (a) fully logged in, or (b) "Who is this?" account picker
            # The account picker has no nav bar and shows a big "Continue" button.
            nav_bar = await self.dom.find("div[role='banner']", timeout=2.0)
            if nav_bar:
                logger.info("Sesja juz aktywna - omijamy ekran logowania.")
                return True

            # No login form AND no nav bar -> likely the account picker screen.
            # Click the primary (blue) "Continue" button to proceed as saved user.
            logger.info("Wykryto ekran wyboru konta (account picker) — klikam Kontynuuj")
            if not await self._handle_account_picker(password):
                return False
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

    async def _handle_account_picker(self, password: str) -> bool:
        """Handle Facebook's 'Who is this?' / account picker screen.

        This screen appears when cookies exist but the session expired.
        It shows the user's photo/name + a 'Continue' button (blue CTA).
        After clicking Continue, Facebook asks for the password.

        Language-independent: finds the primary CTA by background color
        (blue/colored button = Continue), not by text matching.
        """
        from .dom_walker import _eval_js

        # Find the first large button — on the account picker page,
        # there are 2-3 buttons stacked vertically. The topmost one
        # is always "Continue" (blue CTA). FB applies color on inner
        # elements so we can't rely on backgroundColor of the button itself.
        continue_btn = await _eval_js(self.tab, """(() => {
            const btns = document.querySelectorAll(
                "div[role='button'], a[role='button'], span[role='button'], button"
            );
            let topBtn = null;
            let topY = Infinity;
            for (const btn of btns) {
                const r = btn.getBoundingClientRect();
                if (r.width < 100 || r.height < 30) continue;
                if (r.y < topY) { topY = r.y; topBtn = btn; }
            }
            if (!topBtn) return null;
            const r = topBtn.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height,
                    text: (topBtn.innerText || '').trim().slice(0, 80)};
        })()""")

        if not continue_btn:
            logger.warning("Nie znaleziono przycisku Kontynuuj na account picker")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir,
                             f"account_picker_no_btn_{self.account_email}.png")
            )
            return False

        logger.info("Klikam przycisk kontynuacji: '%s'", continue_btn.get("text", ""))
        await mouse_engine.click_element(self.tab, continue_btn)
        await HumanImitation.human_delay(3, 5)

        # After clicking Continue, Facebook should show a password field
        pass_field = await self.dom.find("input[name='pass']", timeout=8.0)
        if not pass_field:
            # Maybe it logged in directly without password (token still valid)
            nav_bar = await self.dom.find("div[role='banner']", timeout=3.0)
            if nav_bar:
                logger.info("Zalogowano po kliknieciu Kontynuuj (bez hasla)")
                return True
            logger.warning("Brak pola hasla po kliknieciu Kontynuuj")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir,
                             f"account_picker_no_pass_{self.account_email}.png")
            )
            return False

        logger.info("Wprowadzanie hasla po account picker...")
        await mouse_engine.click_element(self.tab, pass_field)
        await HumanImitation.type_like_human(self.tab, password)
        await HumanImitation.human_delay(0.5, 1.0)

        # Find and click the login/submit button
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Klikam przycisk logowania: '%s'", login_btn.get("text", ""))
            await mouse_engine.click_element(self.tab, login_btn)
        else:
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint
        if await CheckpointDetector.handle_checkpoint_if_needed(
            self.tab, self.screenshot_dir, self.account_email
        ):
            logger.error("Logowanie zablokowane - Checkpoint!")
            return False

        # Verify login
        nav_bar = await self.dom.find("div[role='banner']", timeout=5.0)
        if nav_bar:
            logger.info("Pomyslnie zalogowano (via account picker)")
            return True

        logger.error("Logowanie przez account picker nie powiodlo sie")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        await self.tab.save_screenshot(
            os.path.join(self.screenshot_dir,
                         f"login_failed_picker_{self.account_email}.png")
        )
        return False

    async def _handle_login_modal(self, password: str) -> bool:
        """Handle the Facebook login modal that appears on page URLs.

        This modal overlays the fanpage content and asks for email/password.
        It appears when visiting a Facebook page URL without an active session.
        Returns True if login through the modal succeeded.
        """
        from .dom_walker import _eval_js

        logger.info("Probuje logowanie przez modal na stronie FB")

        # Find email/phone input — it might not be name='email' in the modal
        email_field = await self.dom.find("input[name='email']", timeout=2.0)
        if not email_field:
            # Try other selectors for the email field in the modal
            email_field = await _eval_js(self.tab, """(() => {
                const inputs = document.querySelectorAll("input[type='text'], input[type='email'], input[name='email']");
                for (const inp of inputs) {
                    const r = inp.getBoundingClientRect();
                    if (r.width > 100 && r.height > 20 && r.y > 0) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height, text: ''};
                    }
                }
                return null;
            })()""")

        if not email_field:
            logger.warning("Nie znaleziono pola email w modalu logowania")
            return False

        # Fill in email
        await mouse_engine.click_element(self.tab, email_field)
        await HumanImitation.type_like_human(self.tab, self.account_email)
        await HumanImitation.human_delay(0.5, 1.0)

        # Fill in password
        pass_field = await self.dom.find("input[name='pass']", timeout=3.0)
        if not pass_field:
            pass_field = await _eval_js(self.tab, """(() => {
                const inputs = document.querySelectorAll("input[type='password']");
                for (const inp of inputs) {
                    const r = inp.getBoundingClientRect();
                    if (r.width > 100 && r.height > 20 && r.y > 0) {
                        return {x: r.x, y: r.y, w: r.width, h: r.height, text: ''};
                    }
                }
                return null;
            })()""")

        if not pass_field:
            logger.warning("Nie znaleziono pola hasla w modalu logowania")
            return False

        await mouse_engine.click_element(self.tab, pass_field)
        await HumanImitation.type_like_human(self.tab, password)
        await HumanImitation.human_delay(0.5, 1.0)

        # Click login button
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Klikam przycisk logowania w modalu: '%s'",
                        login_btn.get("text", ""))
            await mouse_engine.click_element(self.tab, login_btn)
        else:
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Verify login
        if await CheckpointDetector.handle_checkpoint_if_needed(
            self.tab, self.screenshot_dir, self.account_email
        ):
            logger.error("Logowanie przez modal zablokowane - Checkpoint!")
            return False

        nav_bar = await self.dom.find("div[role='banner']", timeout=5.0)
        if nav_bar:
            logger.info("Pomyslnie zalogowano przez modal na stronie FB")
            return True

        logger.warning("Logowanie przez modal moze nie powiodlo sie")
        return False

    async def _submit_login_form(self):
        """Submit login form via JS as last resort."""
        from .dom_walker import _eval_js
        await _eval_js(self.tab, """(() => {
            const form = document.querySelector('input[name="pass"]')?.closest('form');
            if (form) form.submit();
        })()""")
