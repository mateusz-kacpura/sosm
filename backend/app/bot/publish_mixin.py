import asyncio
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
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"bg_aa_not_found_{self.account_email}.png")
            )
            return False

        logger.info("Klikam przycisk tla (Aa), detected via: %s", bg_btn.get("text", "?"))
        await mouse_engine.click_element(self.page, bg_btn)
        await HumanImitation.human_delay(1, 2)

        if background_style in ("red", "black"):
            # Solid colors are shown directly as colored circles/divs
            color_rgb = "rgb(226, 1, 59)" if background_style == "red" else "rgb(17, 17, 17)"
            solid_btn = await self.dom.find_bg_color_button(color_rgb, timeout=3.0)
            if not solid_btn:
                logger.warning("Nie znaleziono przycisku koloru: %s (szukam %s)", background_style, color_rgb)
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.page.screenshot(path=
                    os.path.join(self.screenshot_dir, f"bg_color_not_found_{self.account_email}.png")
                )
                return False
            await mouse_engine.click_element(self.page, solid_btn)
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
                await mouse_engine.click_element(self.page, expand_btn)
                await HumanImitation.human_delay(1, 2)
            else:
                logger.warning("Nie znaleziono przycisku expand (Opcje tla) - probuje bez niego")

            deco_btn = await self.dom.find_bg_deco_by_index(deco_index, timeout=5.0)
            if not deco_btn:
                logger.warning("Nie znaleziono tla dekoracyjnego o indeksie: %d", deco_index)
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.page.screenshot(path=
                    os.path.join(self.screenshot_dir, f"bg_deco_not_found_{self.account_email}.png")
                )
                return False
            logger.info("Tlo dekoracyjne znalezione: '%s' (total=%s)",
                        deco_btn.get("text", "")[:40], deco_btn.get("total", "?"))
            await mouse_engine.click_element(self.page, deco_btn)
            await HumanImitation.human_delay(0.5, 1.5)
            logger.info("Tlo dekoracyjne wybrane: deco_%d", deco_index)

            # Close the expanded background grid by clicking "Ukryj opcje tła"
            # (otherwise the grid stays open and blocks the Publish button)
            hide_btn = await self.dom.find_bg_hide_button(timeout=2.0)
            if hide_btn:
                logger.info("Zamykam siatke tel: '%s'", hide_btn.get("text", "?"))
                await mouse_engine.click_element(self.page, hide_btn)
                await HumanImitation.human_delay(0.5, 1.0)

            return True

        logger.warning("Nieznany styl tla: %s", background_style)
        return False

    async def _attach_media(self, media_paths: list[str]) -> bool:
        """Attach media files to the current post composer via Playwright.

        1. Click "Zdjęcie/film" button via find_media_button()
        2. Use Playwright's set_input_files() on the <input type="file">
        3. Wait for preview thumbnails
        """
        logger.info("Attaching %d media file(s)", len(media_paths))

        media_paths = [os.path.realpath(p) for p in media_paths]

        for path in media_paths:
            if not os.path.isfile(path):
                logger.error("Media file not found: %s", path)
                return False

        # Step 1: Click the media button in the dialog toolbar
        media_btn = await self.dom.find_media_button(timeout=5.0)
        if not media_btn:
            logger.warning("Nie znaleziono przycisku Zdjecie/film")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"media_btn_not_found_{self.account_email}.png")
            )
            return False

        logger.info("Klikam przycisk Zdjecie/film: '%s'", media_btn.get("text", "?"))
        await mouse_engine.click_element(self.page, media_btn)
        await HumanImitation.human_delay(1, 2)

        # Step 2: Set files via Playwright (replaces 67-line CDP dance)
        # Target the file input INSIDE the dialog — FB has multiple hidden
        # input[type='file'] on the page; only the dialog one triggers upload.
        logger.info("Ustawiam pliki via Playwright: %s", [os.path.basename(p) for p in media_paths])
        try:
            file_input = self.page.locator("div[role='dialog'] input[type='file']").first
            await file_input.set_input_files(media_paths)
        except Exception as e:
            logger.error("Playwright set_input_files failed: %s", e)
            return False

        # Step 3: Wait for media preview to appear
        preview_ok = await self._verify_media_preview(timeout=15.0)
        if not preview_ok:
            logger.warning("Media preview nie pojawil sie — pliki mogly nie zostac zaladowane")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"media_preview_missing_{self.account_email}.png")
            )
            return False

        logger.info("Media preview confirmed — %d plik(ow) zaladowanych", len(media_paths))
        return True

    async def _verify_media_preview(self, timeout: float = 15.0) -> bool:
        """Verify media thumbnails appeared in composer dialog."""
        from .dom_walker import _eval_js

        js = """(() => {
            const dialogs = document.querySelectorAll("div[role='dialog']");
            let dialog = null;
            for (const d of dialogs) {
                const r = d.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) { dialog = d; break; }
            }
            if (!dialog) return false;

            // Look for preview images: blob: or data: src, or large thumbnails
            const imgs = dialog.querySelectorAll('img');
            for (const img of imgs) {
                const src = img.getAttribute('src') || '';
                const r = img.getBoundingClientRect();
                // Media previews are typically > 60px and use blob: URLs
                if (r.width > 60 && r.height > 60) {
                    if (src.startsWith('blob:') || src.startsWith('data:')) return true;
                    // FB sometimes uses scontent CDN for uploaded previews
                    if (src.includes('scontent') && r.width > 100) return true;
                }
            }

            // Also check for video elements (video previews)
            const videos = dialog.querySelectorAll('video');
            for (const v of videos) {
                const r = v.getBoundingClientRect();
                if (r.width > 60 && r.height > 60) return true;
            }

            // Check for any new container that appeared after file selection
            // (FB adds a media preview area with specific structure)
            const previews = dialog.querySelectorAll('[data-testid*="media"], [data-testid*="photo"], [data-testid*="video"]');
            if (previews.length > 0) return true;

            return false;
        })()"""

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            result = await _eval_js(self.page, js)
            if result:
                return True
            await asyncio.sleep(1.0)
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
        result = await _eval_js(self.page, f"""(() => {{
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
        await self.page.goto("https://www.facebook.com/")
        await HumanImitation.human_delay(3, 6)

        await _eval_js(self.page, "window.scrollTo(0, 0)")
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
        """Verify and ensure the active identity is the personal profile.

        Always performs a real check (never relies on in-memory state alone),
        because the browser may still be on a fanpage from a previous run.
        If a fanpage identity is detected, automatically switches to personal.

        Returns True if personal profile confirmed or restored,
        False only if auto-recovery failed.
        """
        from .dom_walker import _eval_js
        import re

        logger.info("Weryfikacja tozsamosci: oczekiwany profil osobisty")

        # Step 1: Navigate to /me and check redirect URL + page indicators
        await self.page.goto("https://www.facebook.com/me")
        await HumanImitation.human_delay(3, 5)

        me_check = await _eval_js(self.page, """(() => {
            const url = window.location.href;
            const og = document.querySelector('meta[property="og:title"]');
            const name = og ? og.getAttribute('content') || ''
                           : document.title.replace(/\\s*[|·-]\\s*Facebook.*$/i, '').trim();

            // Page-specific management UI (never on personal profiles)
            const pageEls = document.querySelectorAll(
                '[href*="professional_dashboard"], '
                + '[href*="business.facebook.com"], '
                + '[data-pageid], '
                + 'a[href*="/insights/"]'
            );
            let pageCount = 0;
            for (const el of pageEls) {
                const r = el.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) pageCount++;
            }

            return { url, name, pageCount };
        })()""")

        is_fanpage = False
        detected_page_name = None

        if me_check:
            me_url = me_check.get("url", "")
            me_name = me_check.get("name", "")
            page_count = me_check.get("pageCount", 0)

            # Signal 1: page management elements on the profile page
            if page_count > 0:
                is_fanpage = True
                detected_page_name = me_name
                logger.warning("Wykryto %d elementow zarzadzania strona na /me", page_count)

            # Signal 2: /me URL contains /people/Name/ID/ with non-personal ID
            # Personal IDs start with '100', page IDs typically don't
            page_id_match = re.search(r'/people/[^/]+/(\d{10,})/?', me_url)
            if page_id_match and not page_id_match.group(1).startswith('100'):
                is_fanpage = True
                detected_page_name = me_name
                logger.warning("/me przekierowal do URL strony: %s", me_url)

            # Signal 3: known fanpage name matches /me profile
            if self._current_page_name and me_name and \
               self._current_page_name.lower() in me_name.lower():
                is_fanpage = True
                detected_page_name = me_name

        # Step 2: Also check HOME composer for additional confirmation
        if not is_fanpage:
            await self.page.goto("https://www.facebook.com/")
            await HumanImitation.human_delay(3, 6)
            await _eval_js(self.page, "window.scrollTo(0, 0)")
            await HumanImitation.human_delay(1, 2)

            post_box = await self._find_home_composer()
            if post_box:
                composer_text = (post_box.get("text", "") or "").lower()
                page_name = (self._current_page_name or "").lower()
                personal_name = (self._personal_profile_name or "").lower()

                if page_name and page_name in composer_text:
                    is_fanpage = True
                    detected_page_name = self._current_page_name
                    logger.warning("Composer zawiera nazwe fanpage '%s'",
                                   self._current_page_name)
                elif personal_name and personal_name in composer_text:
                    logger.info("IDENTITY OK: profil osobisty '%s' (composer)",
                                self._personal_profile_name)
                    self._current_page_name = None
                    return True

        # Step 3: If fanpage detected → auto-switch to personal
        if is_fanpage:
            if detected_page_name and not self._current_page_name:
                self._current_page_name = detected_page_name
            logger.warning(
                "IDENTITY MISMATCH: aktywny profil fanpage '%s' "
                "— przelaczam na profil osobisty",
                detected_page_name or "unknown",
            )
            switched = await self.switch_to_personal_profile()
            if switched:
                self._current_page_name = None
                logger.info("Auto-naprawa: przywrocono profil osobisty")
                return True
            logger.error("Auto-naprawa nie powiodla sie — nie mozna "
                         "przywrocic profilu osobistego")
            return False

        # No fanpage detected — personal is the default
        logger.info("IDENTITY OK: profil osobisty")
        self._current_page_name = None
        return True

    async def publish_on_group(self, group_url: str, text: str, media_urls=None,
                               background_style: str = None) -> bool:
        """Publish a text post to a Facebook group."""
        from .dom_walker import _eval_js

        logger.info("Nawigacja do grupy: %s", group_url)

        await self.page.goto(group_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(self.page, self.screenshot_dir, self.account_email):
            return False

        # Handle Activity Review dialog (group rules question) if present
        activity_review = await self.dom.find_activity_review_dialog(timeout=3.0)
        if activity_review:
            logger.info(
                "Wykryto dialog aktywnosci (regulamin grupy), akceptuje..."
            )
            # Click the first radio option ("Tak" / "Yes")
            await mouse_engine.click_element(self.page, activity_review["radio"])
            await HumanImitation.human_delay(0.5, 1.5)
            # Click the submit button ("Prześlij" / "Submit")
            await mouse_engine.click_element(self.page, activity_review["submit"])
            await HumanImitation.human_delay(2, 4)

        # Scroll naturally to seem human, then scroll down to reveal the feed
        # (group headers can be 600-800px, pushing composer below the fold)
        await HumanImitation.natural_scroll(self.page, scrolls=2)
        await HumanImitation.human_delay(1, 2)
        # Scroll past the group header so the composer is centered
        await _eval_js(self.page, """(() => {
            // Find tab bar (Dyskusja/Discussion) as anchor point
            const tabs = document.querySelectorAll(
                "a[role='tab'], div[role='tablist']"
            );
            for (const t of tabs) {
                const r = t.getBoundingClientRect();
                if (r.width > 200 && r.y > 100) {
                    // Scroll so tab bar is near the top of viewport
                    window.scrollTo(0, window.scrollY + r.y - 60);
                    return true;
                }
            }
            // Fallback: scroll down 400px to get past most group headers
            window.scrollBy(0, 400);
            return false;
        })()""")
        await HumanImitation.human_delay(1, 2)

        try:
            # Step 1: Find the composer trigger — structural match only (language-independent).
            post_box = await self.dom.find_group_composer(timeout=10.0)
            if not post_box:
                raise TimeoutError("Nie znaleziono pola do tworzenia postu (composer)")

            logger.info("Znaleziono composer: '%s' at y=%.0f", post_box.get("text", "")[:50], post_box.get("y", 0))

            # Scroll composer into viewport if it's outside visible area
            comp_y = post_box.get("y", 0)
            if comp_y < 0 or comp_y > 800:
                scroll_by = comp_y - 200  # position composer ~200px from top
                await _eval_js(self.page, f"window.scrollBy(0, {scroll_by})")
                await HumanImitation.human_delay(0.5, 1)
                # Re-find after scroll (coordinates changed)
                post_box = await self.dom.find_group_composer(timeout=5.0)
                if post_box:
                    logger.info("Composer po scroll: y=%.0f", post_box.get("y", 0))

            await mouse_engine.click_element(self.page, post_box)
            await HumanImitation.human_delay(1, 3)

            # Diagnostic: verify a dialog opened (not a comment box)
            dialog_check = await self.dom.find("div[role='dialog']", timeout=3.0)
            if not dialog_check:
                logger.warning("Klikniecie composera nie otworzylo dialogu - probuje FAB i retry")
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.page.screenshot(path=
                    os.path.join(self.screenshot_dir, f"no_dialog_{self.account_email}.png")
                )

                # Fallback 1: FAB (floating action button) — compose icon near tab bar
                fab = await _eval_js(self.page, """(() => {
                    // Strategy A: aria-label with compose/create/write keywords
                    const composeLabels = [
                        'napisz', 'utwórz', 'create', 'compose', 'write',
                        'new post', 'nowy post', 'เขียน', 'สร้าง'
                    ];
                    const allEls = document.querySelectorAll(
                        "div[role='button'], a[role='button'], a[role='link'], " +
                        "button, [tabindex='0']"
                    );
                    for (const el of allEls) {
                        const label = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (!label) continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 15 || r.height < 15 || r.y < 100) continue;
                        if (el.closest("[role='article']")) continue;
                        if (composeLabels.some(l => label.includes(l))) {
                            return {x: r.x, y: r.y, w: r.width, h: r.height,
                                    text: label.slice(0, 80), strategy: 'aria-label'};
                        }
                    }

                    // Strategy B: small round button with SVG near bottom-right
                    for (const el of allEls) {
                        const r = el.getBoundingClientRect();
                        if (r.width < 25 || r.width > 70) continue;
                        if (r.height < 25 || r.height > 70) continue;
                        if (Math.abs(r.width - r.height) > 15) continue;
                        // Right half of page, lower half
                        const vw = window.innerWidth;
                        const vh = window.innerHeight;
                        if (r.x < vw * 0.6 || r.y < vh * 0.5) continue;
                        if (el.closest("[role='article']")) continue;
                        // Must have SVG or icon child
                        const hasSvg = el.querySelector('svg')
                            || el.querySelector('i')
                            || el.querySelector('img');
                        if (!hasSvg) continue;
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: (el.getAttribute('aria-label') || 'FAB'),
                                strategy: 'svg-position'};
                    }
                    return null;
                })()""")

                if fab:
                    logger.info("Znaleziono FAB (compose) w prawym dolnym rogu")
                    await mouse_engine.click_element(self.page, fab)
                    await HumanImitation.human_delay(2, 4)
                    dialog_check = await self.dom.find("div[role='dialog']", timeout=3.0)

                # Fallback 2: Scroll to top and retry inline composer
                if not dialog_check:
                    await _eval_js(self.page, "window.scrollTo(0, 0)")
                    await HumanImitation.human_delay(1, 2)
                    post_box = await self.dom.find_group_composer(timeout=10.0)
                    if post_box:
                        logger.info("Retry: composer at y=%.0f, text='%s'",
                                    post_box.get("y", 0), post_box.get("text", "")[:50])
                        await mouse_engine.click_element(self.page, post_box)
                        await HumanImitation.human_delay(1, 3)

            # Step 2: Find the text editor in the post creation modal.
            # Firefox/Camoufox may need more time for the rich editor to render.
            editor = await self.dom.find(
                "div[role='dialog'] div[role='textbox'][contenteditable='true']",
                timeout=15.0,
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

            await mouse_engine.click_element(self.page, editor)
            await HumanImitation.type_like_human(self.page, text, delay_range=(0.02, 0.08))

            if media_urls and not background_style:
                from app.core.config import settings
                media_paths = [os.path.join(settings.MEDIA_DIR, fn) for fn in media_urls]
                media_ok = await self._attach_media(media_paths)
                if not media_ok:
                    logger.warning("Nie udalo sie dolaczyc mediow — kontynuuje publikacje bez mediow")

            await HumanImitation.human_delay(2, 4)

            # Step 3: Click Publish button — structural match (bottom-most in dialog).
            publish_btn = await self.dom.find_dialog_submit_button(timeout=5.0)
            if not publish_btn:
                raise TimeoutError("Nie znaleziono przycisku Opublikuj w modalu")

            logger.info("Klikam przycisk publikacji: '%s'", publish_btn.get("text", "")[:50])
            await mouse_engine.click_element(self.page, publish_btn)

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
                await mouse_engine.click_element(self.page, confirm_btn)
                await HumanImitation.human_delay(2, 4)

            # Final verification: take screenshot for debugging
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
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
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"error_group_{self.account_email}.png")
            )
            return False

    async def publish_on_fanpage(self, fanpage_url: str, text: str,
                                  background_style: str = None,
                                  media_urls=None) -> bool:
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
                self.page, self.screenshot_dir, self.account_email
            ):
                return False

            # Step 2: Find the composer (already on HOME from verification)
            post_box = await self._find_home_composer()
            if not post_box:
                raise TimeoutError("Nie znaleziono composera na stronie glownej")

            logger.info("Znaleziono composer fanpage: '%s'", post_box.get("text", "")[:50])
            await mouse_engine.click_element(self.page, post_box)
            await HumanImitation.human_delay(2, 4)

            # Check if dialog opened
            dialog_check = await self.dom.find("div[role='dialog']", timeout=3.0)
            if not dialog_check:
                logger.warning("Klikniecie composera nie otworzylo dialogu — screenshot + retry")
                os.makedirs(self.screenshot_dir, exist_ok=True)
                await self.page.screenshot(path=
                    os.path.join(self.screenshot_dir, f"fanpage_no_dialog_{self.account_email}.png")
                )

                # Scroll to top and retry with fresh composer search
                from .dom_walker import _eval_js
                await _eval_js(self.page, "window.scrollTo(0, 0)")
                await HumanImitation.human_delay(1, 2)

                post_box2 = await self._find_home_composer()
                if post_box2:
                    logger.info("Retry composer: '%s' at y=%.0f",
                                post_box2.get("text", "")[:50], post_box2.get("y", 0))
                    await mouse_engine.click_element(self.page, post_box2)
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
            await mouse_engine.click_element(self.page, editor)
            await HumanImitation.type_like_human(self.page, text, delay_range=(0.02, 0.08))

            # Step 4b: Attach media files (mutually exclusive with background)
            if media_urls and not background_style:
                from app.core.config import settings
                media_paths = [os.path.join(settings.MEDIA_DIR, fn) for fn in media_urls]
                media_ok = await self._attach_media(media_paths)
                if not media_ok:
                    logger.warning("Nie udalo sie dolaczyc mediow — kontynuuje publikacje bez mediow")

            await HumanImitation.human_delay(2, 4)

            # Step 5: Click Publish
            publish_btn = await self.dom.find_dialog_submit_button(timeout=5.0)
            if not publish_btn:
                raise TimeoutError("Nie znaleziono przycisku Opublikuj na fanpage")

            logger.info("Klikam przycisk publikacji: '%s'", publish_btn.get("text", "")[:50])
            await mouse_engine.click_element(self.page, publish_btn)
            await HumanImitation.human_delay(3, 5)

            # Step 6: Handle post-publish confirmation dialogs
            for attempt in range(3):
                confirm_btn = await self.dom.find_dialog_submit_button(timeout=3.0)
                if not confirm_btn:
                    break
                logger.info("Dialog potwierdzenia (proba %d): '%s'",
                            attempt + 1, confirm_btn.get("text", "")[:50])
                await mouse_engine.click_element(self.page, confirm_btn)
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
                await self.page.screenshot(path=
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
            await self.page.screenshot(path=
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
