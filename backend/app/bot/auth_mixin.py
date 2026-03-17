import logging
import os

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector
from . import mouse_engine
from . import captcha_solver

logger = logging.getLogger(__name__)


class AuthMixin:
    """Login and authentication methods for FBActions."""

    async def login(self, password: str) -> bool:
        """Log into Facebook, return True if successful."""
        self._last_password = password
        logger.info("Rozpoczynam logowanie dla: %s", self.account_email)
        await self.page.goto("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 5)

        # Dismiss cookie consent banner FIRST — it can overlay the login form
        # and prevent input[name='email'] from being found.
        accept_btn = await self.dom.find(
            "button[data-cookiebanner='accept_button']", timeout=3.0
        )
        if accept_btn:
            logger.info("Zamykam baner cookies")
            await mouse_engine.click_element(self.page, accept_btn)
            await HumanImitation.human_delay(1, 2)

        # Check if already logged in via cookies.
        # The login form (input[name='email']) only exists when NOT logged in.
        login_form = await self.dom.find("input[name='email']", timeout=5.0)
        if not login_form:
            # Could be: (a) fully logged in, or (b) "Who is this?" account picker
            # The account picker has no nav bar and shows a big "Continue" button.
            nav_bar = await self.dom.find("div[role='banner']", timeout=2.0)
            if nav_bar:
                logger.info("Sesja juz aktywna - omijamy ekran logowania.")
                return True

            # No login form AND no nav bar -> wait for SPA to hydrate
            logger.info("Brak formularza i paska — czekam na pelny render strony...")
            await HumanImitation.human_delay(5, 8)

            # Re-check after longer wait
            login_form_retry = await self.dom.find("input[name='email']", timeout=5.0)
            if login_form_retry:
                logger.info("Formularz logowania znaleziony po dluższym oczekiwaniu")
                login_form = login_form_retry
                # Fall through to the email entry below
            else:
                nav_bar_retry = await self.dom.find("div[role='banner']", timeout=3.0)
                if nav_bar_retry:
                    logger.info("Sesja aktywna (wykryta po dluższym oczekiwaniu)")
                    return True

                # Likely the account picker screen.
                logger.info("Wykryto ekran wyboru konta (account picker) — klikam Kontynuuj")
                if not await self._handle_account_picker(password):
                    return False
                return True

        # Enter email
        logger.info("Wprowadzanie poswiadczen...")
        if login_form:
            await mouse_engine.click_element(self.page, login_form)
            await HumanImitation.type_like_human(self.page, self.account_email)
            await HumanImitation.human_delay()

        # Enter password
        pass_field = await self.dom.find("input[name='pass']")
        if pass_field:
            await mouse_engine.click_element(self.page, pass_field)
            await HumanImitation.type_like_human(self.page, password)

        # Hook reCAPTCHA v3 Enterprise before login submission
        if await captcha_solver.hook_recaptcha_before_login(self.page):
            logger.info("reCAPTCHA v3 Enterprise solved and hooked before login")

        # Click login button.
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Znaleziono przycisk logowania: %s", login_btn.get("text", ""))
            await mouse_engine.click_element(self.page, login_btn)
        else:
            # Debug: log what buttons exist on the page
            all_btns = await self.dom.find_all("button")
            logger.warning("Nie znaleziono przycisku logowania. Przyciski na stronie: %s",
                           [(b.get("text", "")[:50], b.get("w", 0), b.get("h", 0)) for b in all_btns])
            logger.info("Probuje submit formularza przez JS")
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint/block — try CAPTCHA solving before giving up
        if await CheckpointDetector.is_checkpoint_active(self.page):
            logger.warning("Checkpoint detected after login — attempting CAPTCHA solve...")
            if await captcha_solver.solve_captcha_on_checkpoint(self.page):
                logger.info("CAPTCHA solved on checkpoint — waiting for redirect...")
                await HumanImitation.human_delay(5, 8)
                # Re-check if checkpoint is still active
                if not await CheckpointDetector.is_checkpoint_active(self.page):
                    logger.info("Checkpoint cleared after CAPTCHA solve")
                else:
                    logger.error("Checkpoint still active after CAPTCHA solve")
                    await CheckpointDetector.handle_checkpoint_if_needed(
                        self.page, self.screenshot_dir, self.account_email
                    )
                    return False
            else:
                logger.error("Logowanie zablokowane - Checkpoint (CAPTCHA solve failed)")
                await CheckpointDetector.handle_checkpoint_if_needed(
                    self.page, self.screenshot_dir, self.account_email
                )
                return False

        # Verify login succeeded — login form should be gone
        still_login = await self.dom.find("input[name='email']", timeout=2.0)
        if still_login:
            logger.error("Logowanie nie powiodlo sie - formularz nadal widoczny")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
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
        continue_btn = await _eval_js(self.page, """(() => {
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
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir,
                             f"account_picker_no_btn_{self.account_email}.png")
            )
            return False

        logger.info("Klikam przycisk kontynuacji: '%s'", continue_btn.get("text", ""))
        await mouse_engine.click_element(self.page, continue_btn)
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
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir,
                             f"account_picker_no_pass_{self.account_email}.png")
            )
            return False

        logger.info("Wprowadzanie hasla po account picker...")
        await mouse_engine.click_element(self.page, pass_field)
        await HumanImitation.type_like_human(self.page, password)
        await HumanImitation.human_delay(0.5, 1.0)

        # Find and click the login/submit button
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Klikam przycisk logowania: '%s'", login_btn.get("text", ""))
            await mouse_engine.click_element(self.page, login_btn)
        else:
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint — try CAPTCHA solving
        if await CheckpointDetector.is_checkpoint_active(self.page):
            logger.warning("Checkpoint after account picker — attempting CAPTCHA solve...")
            if await captcha_solver.solve_captcha_on_checkpoint(self.page):
                logger.info("CAPTCHA solved on checkpoint — waiting for redirect...")
                await HumanImitation.human_delay(5, 8)
                if await CheckpointDetector.is_checkpoint_active(self.page):
                    logger.error("Checkpoint still active after CAPTCHA solve (account picker)")
                    await CheckpointDetector.handle_checkpoint_if_needed(
                        self.page, self.screenshot_dir, self.account_email
                    )
                    return False
            else:
                logger.error("Logowanie zablokowane - Checkpoint (account picker, CAPTCHA unsolvable)")
                await CheckpointDetector.handle_checkpoint_if_needed(
                    self.page, self.screenshot_dir, self.account_email
                )
                return False

        # Verify login
        nav_bar = await self.dom.find("div[role='banner']", timeout=5.0)
        if nav_bar:
            logger.info("Pomyslnie zalogowano (via account picker)")
            return True

        logger.error("Logowanie przez account picker nie powiodlo sie")
        os.makedirs(self.screenshot_dir, exist_ok=True)
        await self.page.screenshot(path=
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
            email_field = await _eval_js(self.page, """(() => {
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
        await mouse_engine.click_element(self.page, email_field)
        await HumanImitation.type_like_human(self.page, self.account_email)
        await HumanImitation.human_delay(0.5, 1.0)

        # Fill in password
        pass_field = await self.dom.find("input[name='pass']", timeout=3.0)
        if not pass_field:
            pass_field = await _eval_js(self.page, """(() => {
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

        await mouse_engine.click_element(self.page, pass_field)
        await HumanImitation.type_like_human(self.page, password)
        await HumanImitation.human_delay(0.5, 1.0)

        # Click login button
        login_btn = await self.dom.find_login_button(timeout=5.0)
        if login_btn:
            logger.info("Klikam przycisk logowania w modalu: '%s'",
                        login_btn.get("text", ""))
            await mouse_engine.click_element(self.page, login_btn)
        else:
            await self._submit_login_form()

        await HumanImitation.human_delay(4, 7)

        # Check for checkpoint — try CAPTCHA solving
        if await CheckpointDetector.is_checkpoint_active(self.page):
            logger.warning("Checkpoint after modal login — attempting CAPTCHA solve...")
            if await captcha_solver.solve_captcha_on_checkpoint(self.page):
                logger.info("CAPTCHA solved on checkpoint (modal) — waiting...")
                await HumanImitation.human_delay(5, 8)
                if await CheckpointDetector.is_checkpoint_active(self.page):
                    logger.error("Checkpoint still active after CAPTCHA solve (modal)")
                    await CheckpointDetector.handle_checkpoint_if_needed(
                        self.page, self.screenshot_dir, self.account_email
                    )
                    return False
            else:
                logger.error("Logowanie przez modal zablokowane - Checkpoint!")
                await CheckpointDetector.handle_checkpoint_if_needed(
                    self.page, self.screenshot_dir, self.account_email
                )
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
        await _eval_js(self.page, """(() => {
            const form = document.querySelector('input[name="pass"]')?.closest('form');
            if (form) form.submit();
        })()""")
