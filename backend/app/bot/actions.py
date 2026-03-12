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

    async def _select_post_background(self, background_style: str) -> bool:
        """Select a post background color in the Facebook composer dialog.

        Must be called BEFORE typing text. Language-independent — uses
        structural/visual matching (element sizes, background-color CSS).

        Args:
            background_style: "red", "black", or "deco_N" (N = 0-32 index)

        Returns:
            True if background was selected successfully.
        """
        logger.info("Ustawianie tla: %s", background_style)

        # Step 1: Find the Aa background button in the dialog toolbar.
        bg_btn = await self.dom.find_background_button(timeout=5.0)
        if not bg_btn:
            logger.warning("Nie znaleziono przycisku tla (Aa) w dialogu")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir, f"bg_aa_not_found_{self.account_email}.png")
            )
            return False

        logger.info("Klikam przycisk tla (Aa), detected via: %s", bg_btn.get("text", "?"))
        await mouse_engine.click_element(self.tab, bg_btn)
        await HumanImitation.human_delay(1, 2)

        if background_style in ("red", "black"):
            # Solid colors are shown directly as colored circles/divs
            color_rgb = "rgb(226, 1, 59)" if background_style == "red" else "rgb(17, 17, 17)"
            solid_btn = await self.dom.find_bg_color_button(color_rgb, timeout=3.0)
            if not solid_btn:
                logger.warning("Nie znaleziono przycisku koloru: %s (szukam %s)", background_style, color_rgb)
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.tab.save_screenshot(
                    os.path.join(self.screenshot_dir, f"bg_color_not_found_{self.account_email}.png")
                )
                return False
            await mouse_engine.click_element(self.tab, solid_btn)
            await HumanImitation.human_delay(0.5, 1.5)
            logger.info("Tlo solid wybrane: %s", background_style)
            return True

        elif background_style.startswith("deco_"):
            deco_index = int(background_style.replace("deco_", ""))

            # After clicking Aa, only ~5 decorative backgrounds are visible.
            # Click the expand button (⊞ "Opcje tła") to reveal full grid (~30).
            expand_btn = await self.dom.find_bg_expand_button(timeout=3.0)
            if expand_btn:
                logger.info("Klikam expand (Opcje tla): '%s'", expand_btn.get("text", "?"))
                await mouse_engine.click_element(self.tab, expand_btn)
                await HumanImitation.human_delay(1, 2)
            else:
                logger.warning("Nie znaleziono przycisku expand (Opcje tla) - probuje bez niego")

            deco_btn = await self.dom.find_bg_deco_by_index(deco_index, timeout=5.0)
            if not deco_btn:
                logger.warning("Nie znaleziono tla dekoracyjnego o indeksie: %d", deco_index)
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.tab.save_screenshot(
                    os.path.join(self.screenshot_dir, f"bg_deco_not_found_{self.account_email}.png")
                )
                return False
            logger.info("Tlo dekoracyjne znalezione: '%s' (total=%s)",
                        deco_btn.get("text", "")[:40], deco_btn.get("total", "?"))
            await mouse_engine.click_element(self.tab, deco_btn)
            await HumanImitation.human_delay(0.5, 1.5)
            logger.info("Tlo dekoracyjne wybrane: deco_%d", deco_index)

            # Close the expanded background grid by clicking "Ukryj opcje tła"
            # (otherwise the grid stays open and blocks the Publish button)
            hide_btn = await self.dom.find_bg_hide_button(timeout=2.0)
            if hide_btn:
                logger.info("Zamykam siatke tel: '%s'", hide_btn.get("text", "?"))
                await mouse_engine.click_element(self.tab, hide_btn)
                await HumanImitation.human_delay(0.5, 1.0)

            return True

        logger.warning("Nieznany styl tla: %s", background_style)
        return False

    async def publish_on_group(self, group_url: str, text: str, media_urls=None,
                               background_style: str = None) -> bool:
        """Publish a text post to a Facebook group."""
        logger.info("Nawigacja do grupy: %s", group_url)

        await self.tab.get(group_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(self.tab, self.screenshot_dir, self.account_email):
            return False

        # Handle Activity Review dialog (group rules question) if present
        activity_review = await self.dom.find_activity_review_dialog(timeout=3.0)
        if activity_review:
            logger.info(
                "Wykryto dialog aktywnosci (regulamin grupy), akceptuje..."
            )
            # Click the first radio option ("Tak" / "Yes")
            await mouse_engine.click_element(self.tab, activity_review["radio"])
            await HumanImitation.human_delay(0.5, 1.5)
            # Click the submit button ("Prześlij" / "Submit")
            await mouse_engine.click_element(self.tab, activity_review["submit"])
            await HumanImitation.human_delay(2, 4)

        # Scroll naturally to seem human, then back to top so composer is visible
        await HumanImitation.natural_scroll(self.tab, scrolls=2)
        await HumanImitation.human_delay(1, 2)
        from .dom_walker import _eval_js
        await _eval_js(self.tab, "window.scrollTo(0, 0)")
        await HumanImitation.human_delay(0.5, 1.0)

        try:
            # Step 1: Find the composer trigger — structural match only (language-independent).
            post_box = await self.dom.find_group_composer(timeout=10.0)
            if not post_box:
                raise TimeoutError("Nie znaleziono pola do tworzenia postu (composer)")

            logger.info("Znaleziono composer: '%s' at y=%.0f", post_box.get("text", "")[:50], post_box.get("y", 0))
            await mouse_engine.click_element(self.tab, post_box)
            await HumanImitation.human_delay(1, 3)

            # Diagnostic: verify a dialog opened (not a comment box)
            dialog_check = await self.dom.find("div[role='dialog']", timeout=3.0)
            if not dialog_check:
                logger.warning("Klikniecie composera nie otworzylo dialogu - prawdopodobnie trafiono w pole komentarza. Probuje ponownie.")
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.tab.save_screenshot(
                    os.path.join(self.screenshot_dir, f"no_dialog_{self.account_email}.png")
                )
                # Scroll to very top and retry
                await _eval_js(self.tab, "window.scrollTo(0, 0)")
                await HumanImitation.human_delay(1, 2)
                post_box = await self.dom.find_group_composer(timeout=10.0)
                if not post_box:
                    raise TimeoutError("Nie znaleziono composera po ponownej probie")
                logger.info("Retry: composer at y=%.0f, text='%s'", post_box.get("y", 0), post_box.get("text", "")[:50])
                await mouse_engine.click_element(self.tab, post_box)
                await HumanImitation.human_delay(1, 3)

            # Step 2: Find the text editor in the post creation modal.
            editor = await self.dom.find(
                "div[role='dialog'] div[role='textbox'][contenteditable='true']",
                timeout=5.0,
            )
            if not editor:
                raise TimeoutError("Nie znaleziono edytora tekstowego w modalu")

            # Step 2b: Select background BEFORE typing (FB requirement).
            if background_style:
                bg_text = text[:100]  # Background posts limited to 100 chars
                bg_ok = await self._select_post_background(background_style)
                if bg_ok:
                    logger.info("Tlo wybrane: %s, tekst skrocony do %d znakow", background_style, len(bg_text))
                    text = bg_text
                    # Re-find textbox — FB moves it ~94px down after background selection
                    editor = await self.dom.find(
                        "div[role='dialog'] div[role='textbox'][contenteditable='true']",
                        timeout=5.0,
                    )
                    if not editor:
                        raise TimeoutError("Nie znaleziono edytora po wybraniu tla")
                else:
                    logger.warning("Nie udalo sie wybrac tla, kontynuuje bez tla")

            await mouse_engine.click_element(self.tab, editor)
            await HumanImitation.type_like_human(self.tab, text, delay_range=(0.02, 0.08))

            if media_urls:
                logger.info("TODO: Dodawanie zdjec nieobslugiwane w pierwszym MVP")

            await HumanImitation.human_delay(2, 4)

            # Step 3: Click Publish button — structural match (bottom-most in dialog).
            publish_btn = await self.dom.find_dialog_submit_button(timeout=5.0)
            if not publish_btn:
                raise TimeoutError("Nie znaleziono przycisku Opublikuj w modalu")

            logger.info("Klikam przycisk publikacji: '%s'", publish_btn.get("text", "")[:50])
            await mouse_engine.click_element(self.tab, publish_btn)

            await HumanImitation.human_delay(3, 5)

            # Step 4: Handle post-publish dialogs (e.g. group rules acceptance).
            # After clicking Publish, Facebook may show a rules/terms dialog.
            # Try up to 3 times to find and click a CTA button in any visible dialog.
            for attempt in range(3):
                confirm_btn = await self.dom.find_dialog_submit_button(timeout=3.0)
                if not confirm_btn:
                    break  # No more dialogs to confirm — success!
                logger.info(
                    "Dialog potwierdzenia (proba %d): '%s'",
                    attempt + 1, confirm_btn.get("text", "")[:50],
                )
                await mouse_engine.click_element(self.tab, confirm_btn)
                await HumanImitation.human_delay(2, 4)

            # Final verification: take screenshot for debugging
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(
                    self.screenshot_dir,
                    f"after_publish_{self.account_email}.png",
                )
            )

            logger.info("Post opublikowany (kliknięto Opublikuj + potwierdzenia)")
            return True

        except (TimeoutError, Exception) as e:
            logger.error("Blad publikacji na grupie: %s", e)
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir, f"error_group_{self.account_email}.png")
            )
            return False
