import json as _json
import logging
import os

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector
from . import mouse_engine

logger = logging.getLogger(__name__)


class PublishMixin:
    """Publishing methods for FBActions (group, fanpage, composer, background)."""

    # Placeholder texts used across Facebook locales to identify the
    # "Create a post" composer trigger button on the home feed.
    _COMPOSER_PLACEHOLDERS = [
        'o czym myślisz', 'napisz, co myślisz',
        'co słychać', 'co nowego',
        "what's on your mind", "create a post",
        'เขียนอะไรบางอย่าง', 'คุณกำลังคิดอะไร',
    ]

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
            # Click the expand button to reveal full grid (~30).
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

    async def _find_home_composer(self) -> dict | None:
        """Find the composer trigger on facebook.com HOME.

        Uses full placeholder list + textbox fallback + group composer
        fallback.  Returns element rect or None.
        The found element is scrolled into view and coordinates are
        refreshed after scroll.
        """
        from .dom_walker import _eval_js

        placeholders_json = _json.dumps(self._COMPOSER_PLACEHOLDERS)
        result = await _eval_js(self.tab, f"""(() => {{
            const placeholders = {placeholders_json};

            // Strategy A: div[role='button'] with placeholder text
            const btns = document.querySelectorAll(
                "div[role='button'], span[role='button']"
            );
            for (const btn of btns) {{
                const text = (btn.innerText || '').trim().toLowerCase();
                if (text.length > 50) continue;
                if (placeholders.some(p => text.includes(p))) {{
                    const r = btn.getBoundingClientRect();
                    if (r.width > 100 && r.height > 10 && r.y > 0) {{
                        btn.scrollIntoView({{block: 'center', behavior: 'instant'}});
                        const r2 = btn.getBoundingClientRect();
                        return {{x: r2.x, y: r2.y, w: r2.width, h: r2.height,
                                text: btn.innerText.trim().slice(0, 80)}};
                    }}
                }}
            }}

            // Strategy B: textbox with aria-placeholder
            const textboxes = document.querySelectorAll(
                "div[role='textbox'][aria-placeholder], "
                + "div[contenteditable='true'][aria-placeholder]"
            );
            for (const tb of textboxes) {{
                const r = tb.getBoundingClientRect();
                if (r.width > 100 && r.height > 10 && r.y > 0) {{
                    tb.scrollIntoView({{block: 'center', behavior: 'instant'}});
                    const r2 = tb.getBoundingClientRect();
                    return {{x: r2.x, y: r2.y, w: r2.width, h: r2.height,
                            text: (tb.getAttribute('aria-placeholder') || '').slice(0, 80)}};
                }}
            }}
            return null;
        }})()""")

        if result:
            return result

        # Fallback: structural group composer finder
        return await self.dom.find_group_composer(timeout=5.0)

    async def verify_identity_as_fanpage(self) -> bool:
        """Navigate to HOME and verify the active identity IS the fanpage.

        Must be called AFTER switch_to_page_profile().
        Returns True if confirmed (or inconclusive), False on mismatch.
        """
        from .dom_walker import _eval_js

        logger.info("Weryfikacja tozsamosci: oczekiwany profil fanpage")
        await self.tab.get("https://www.facebook.com/")
        await HumanImitation.human_delay(3, 6)

        await _eval_js(self.tab, "window.scrollTo(0, 0)")
        await HumanImitation.human_delay(1, 2)

        post_box = await self._find_home_composer()
        if not post_box:
            logger.warning("Nie znaleziono composera na HOME — nie mozna zweryfikowac tozsamosci")
            return True

        composer_text = (post_box.get("text", "") or "").lower()
        page_name = (self._current_page_name or "").lower()
        personal_name = (self._personal_profile_name or "").lower()

        if page_name and page_name in composer_text:
            logger.info("IDENTITY OK: composer potwierdza fanpage '%s'",
                        self._current_page_name)
            return True
        elif personal_name and personal_name in composer_text:
            logger.error(
                "IDENTITY MISMATCH: composer zawiera profil osobisty '%s', "
                "nie fanpage '%s'",
                self._personal_profile_name, self._current_page_name,
            )
            return False
        elif page_name:
            logger.warning(
                "Nie mozna potwierdzic tozsamosci z composera ('%s'), "
                "oczekiwano fanpage '%s' — kontynuuje z ostrzezeniem",
                post_box.get("text", ""), self._current_page_name,
            )
        return True

    async def verify_identity_as_personal(self) -> bool:
        """Navigate to HOME and verify the active identity is NOT a fanpage.

        Call before publishing as personal profile to catch leftover switches.
        Returns True if personal profile confirmed (or inconclusive),
        False if a fanpage identity is detected.
        """
        from .dom_walker import _eval_js

        # Quick check: if no page switch happened, we're almost certainly personal
        if not self._current_page_name:
            logger.info("IDENTITY OK: profil osobisty (brak przelaczenia na fanpage)")
            return True

        # _current_page_name is set — a switch happened and wasn't cleared properly
        logger.warning(
            "Wykryto _current_page_name='%s' — sprawdzam composer na HOME",
            self._current_page_name,
        )
        await self.tab.get("https://www.facebook.com/")
        await HumanImitation.human_delay(3, 6)

        await _eval_js(self.tab, "window.scrollTo(0, 0)")
        await HumanImitation.human_delay(1, 2)

        post_box = await self._find_home_composer()
        if not post_box:
            logger.warning("Nie znaleziono composera na HOME — nie mozna zweryfikowac")
            return True

        composer_text = (post_box.get("text", "") or "").lower()
        page_name = (self._current_page_name or "").lower()
        personal_name = (self._personal_profile_name or "").lower()

        if page_name and page_name in composer_text:
            logger.error(
                "IDENTITY MISMATCH: nadal aktywny profil fanpage '%s' zamiast osobistego",
                self._current_page_name,
            )
            return False
        elif personal_name and personal_name in composer_text:
            logger.info("IDENTITY OK: profil osobisty '%s' (zweryfikowano na HOME)",
                        self._personal_profile_name)
            self._current_page_name = None
            return True

        # Generic placeholder without names — likely personal (default)
        logger.info("IDENTITY OK: composer bez nazwy profilu — prawdopodobnie osobisty")
        self._current_page_name = None
        return True

    async def publish_on_group(self, group_url: str, text: str, media_urls=None,
                               background_style: str = None) -> bool:
        """Publish a text post to a Facebook group."""
        from .dom_walker import _eval_js

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

    async def publish_on_fanpage(self, fanpage_url: str, text: str,
                                  background_style: str = None) -> bool:
        """Publish a text post on a Facebook fanpage AS the fanpage.

        Switches identity to the fanpage before posting, and switches back
        to the personal profile after (even on failure).
        """
        # Step 0: Switch identity to the fanpage
        switched = await self.switch_to_page_profile(fanpage_url)
        if not switched:
            logger.error("Nie udalo sie przelaczac na profil fanpage — przerywam publikacje")
            return False

        try:
            # Step 1: Navigate to HOME and verify identity as fanpage
            identity_ok = await self.verify_identity_as_fanpage()
            if not identity_ok:
                return False

            if await CheckpointDetector.handle_checkpoint_if_needed(
                self.tab, self.screenshot_dir, self.account_email
            ):
                return False

            # Step 2: Find the composer (already on HOME from verification)
            post_box = await self._find_home_composer()
            if not post_box:
                raise TimeoutError("Nie znaleziono composera na stronie glownej")

            logger.info("Znaleziono composer fanpage: '%s'", post_box.get("text", "")[:50])
            await mouse_engine.click_element(self.tab, post_box)
            await HumanImitation.human_delay(2, 4)

            # Check if dialog opened
            dialog_check = await self.dom.find("div[role='dialog']", timeout=3.0)
            if not dialog_check:
                logger.warning("Klikniecie composera nie otworzylo dialogu — retry")
                post_box2 = await self._find_home_composer()
                if post_box2:
                    await mouse_engine.click_element(self.tab, post_box2)
                    await HumanImitation.human_delay(2, 4)

            # Step 3: Find the text editor — in dialog or inline
            editor = await self.dom.find(
                "div[role='dialog'] div[role='textbox'][contenteditable='true']",
                timeout=5.0,
            )
            if not editor:
                editor = await self.dom.find(
                    "div[role='textbox'][contenteditable='true']", timeout=3.0
                )
            if not editor:
                editor = await self.dom.find(
                    "div[contenteditable='true'][data-lexical-editor]", timeout=3.0
                )
            if not editor:
                raise TimeoutError("Nie znaleziono edytora tekstowego na fanpage")

            # Step 3b: Select background BEFORE typing
            if background_style:
                bg_text = text[:100]
                bg_ok = await self._select_post_background(background_style)
                if bg_ok:
                    logger.info("Tlo wybrane: %s, tekst skrocony do %d znakow",
                                background_style, len(bg_text))
                    text = bg_text
                    editor = await self.dom.find(
                        "div[role='dialog'] div[role='textbox'][contenteditable='true']",
                        timeout=5.0,
                    )
                    if not editor:
                        editor = await self.dom.find(
                            "div[role='textbox'][contenteditable='true']", timeout=3.0
                        )
                    if not editor:
                        raise TimeoutError("Nie znaleziono edytora po wybraniu tla")
                else:
                    logger.warning("Nie udalo sie wybrac tla, kontynuuje bez tla")

            # Step 4: Type content
            await mouse_engine.click_element(self.tab, editor)
            await HumanImitation.type_like_human(self.tab, text, delay_range=(0.02, 0.08))
            await HumanImitation.human_delay(2, 4)

            # Step 5: Click Publish
            publish_btn = await self.dom.find_dialog_submit_button(timeout=5.0)
            if not publish_btn:
                raise TimeoutError("Nie znaleziono przycisku Opublikuj na fanpage")

            logger.info("Klikam przycisk publikacji: '%s'", publish_btn.get("text", "")[:50])
            await mouse_engine.click_element(self.tab, publish_btn)
            await HumanImitation.human_delay(3, 5)

            # Step 6: Handle post-publish confirmation dialogs
            for attempt in range(3):
                confirm_btn = await self.dom.find_dialog_submit_button(timeout=3.0)
                if not confirm_btn:
                    break
                logger.info("Dialog potwierdzenia (proba %d): '%s'",
                            attempt + 1, confirm_btn.get("text", "")[:50])
                await mouse_engine.click_element(self.tab, confirm_btn)
                await HumanImitation.human_delay(2, 4)

            # Step 7: Verify publication — wait for dialog to disappear
            dialog_gone = False
            for _ in range(8):
                remaining_dialog = await self.dom.find("div[role='dialog']", timeout=1.0)
                if not remaining_dialog:
                    dialog_gone = True
                    break
                await HumanImitation.human_delay(1, 2)

            if not dialog_gone:
                logger.warning("Dialog nadal widoczny po publikacji — post moze nie zostal opublikowany")
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.tab.save_screenshot(
                    os.path.join(self.screenshot_dir, f"publish_dialog_stuck_{self.account_email}.png")
                )
                return False

            logger.info(
                "Post na fanpage opublikowany jako '%s' (dialog zamkniety)",
                self._current_page_name or "unknown",
            )
            return True

        except (TimeoutError, Exception) as e:
            logger.error("Blad publikacji na fanpage: %s", e)
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.tab.save_screenshot(
                os.path.join(self.screenshot_dir, f"error_fanpage_{self.account_email}.png")
            )
            return False

        finally:
            # Always switch back to personal profile and clear identity
            try:
                await self.switch_to_personal_profile()
            except Exception as e:
                logger.warning("Nie udalo sie przywrocic profilu osobistego: %s", e)
            self._current_page_name = None
