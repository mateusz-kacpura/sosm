import json as _json
import logging
import os

from .human_imitation import HumanImitation
from . import mouse_engine

logger = logging.getLogger(__name__)


class ProfileMixin:
    """Profile switching methods for FBActions."""

    async def _click_profile_avatar(self) -> bool:
        """Click the top-right profile avatar to open account menu."""
        from .dom_walker import _eval_js

        avatar = await _eval_js(self.page, """(() => {
            const nav = document.querySelector("div[role='banner']")
                        || document.querySelector("div[role='navigation']");
            if (!nav) return null;

            // Collect all clickable elements with images in the top bar
            const btns = nav.querySelectorAll("a, div[role='button'], a[role='button']");
            let rightMost = null;
            let rightX = -1;

            for (const btn of btns) {
                const r = btn.getBoundingClientRect();
                if (r.width < 20 || r.height < 20 || r.width > 60 || r.height > 60) continue;
                if (r.y > 60) continue;
                const img = btn.querySelector('img, svg image, svg');
                if (!img) continue;
                if (r.x > rightX) { rightX = r.x; rightMost = btn; }
            }

            if (!rightMost) return null;
            const r = rightMost.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height, text: 'avatar'};
        })()""")

        if not avatar:
            logger.warning("Nie znaleziono avatara w prawym gornym rogu")
            return False

        await mouse_engine.click_element(self.page, avatar)
        await HumanImitation.human_delay(1.5, 3)
        return True

    async def switch_to_page_profile(self, fanpage_url: str) -> bool:
        """Switch Facebook identity to a fanpage via the avatar profile switcher.

        1. Navigate to fanpage to extract its name.
        2. Click avatar in top-right corner to open dropdown.
        3. Find the fanpage entry in 'Szybkie przełączanie profili'
           (Quick profile switching) list via aria-label.
        4. If not visible, click 'Zobacz wszystkie profile' and search there.
        """
        from .dom_walker import _eval_js

        # Navigate to the fanpage to get its name
        logger.info("Nawigacja do fanpage: %s", fanpage_url)
        await self.page.goto(fanpage_url)
        await HumanImitation.human_delay(3, 5)

        # Wait for the page to actually load (title changes from generic "Facebook")
        title = None
        for _ in range(10):
            title = await _eval_js(self.page, "document.title")
            if title and title != "Facebook" and "|" in str(title):
                break
            await HumanImitation.human_delay(1.5, 2.5)
        logger.info("Tytul strony fanpage: '%s'", title)

        # Check if we hit a login modal (session expired).
        # Facebook may show a "See more from [Page]" login overlay on top
        # of a partially-rendered page — the div[role='banner'] can exist
        # BEHIND the modal, so we don't rely on banner absence.
        login_modal = await _eval_js(self.page, """(() => {
            const emailField = document.querySelector(
                "input[name='email'], input[type='email']"
            );
            const passField = document.querySelector(
                "input[name='pass'], input[type='password']"
            );
            if (!emailField || !passField) return false;
            const er = emailField.getBoundingClientRect();
            const pr = passField.getBoundingClientRect();
            if (er.width < 100 || er.height < 20
                || pr.width < 100 || pr.height < 20) return false;

            // In a dialog = definitely a login modal
            if (emailField.closest("div[role='dialog']")) return true;
            // No banner = not logged in, needs login
            if (!document.querySelector("div[role='banner']")) return true;
            // Banner present but login fields also visible and stacked
            // = login overlay on top of page content
            if (Math.abs(er.y - pr.y) < 300) return true;
            return false;
        })()""")
        if login_modal:
            logger.warning("Sesja wygasla — wykryto modal logowania, probuje zalogowac")
            # Get password from the executor context (stored in instance)
            password = getattr(self, '_last_password', None)
            if password and await self._handle_login_modal(password):
                # After login, navigate to the fanpage again
                await self.page.goto(fanpage_url)
                await HumanImitation.human_delay(3, 5)
            else:
                logger.error("Nie udalo sie zalogowac przez modal")
                return False

        # Extract page name — og:title first, then title, then h1 as fallback.
        # h1 is unreliable because the sidebar header "Zarządzanie stroną"
        # is often the first h1 on the page management layout.
        page_name = await _eval_js(self.page, """(() => {
            const og = document.querySelector('meta[property="og:title"]');
            if (og) {
                const c = og.getAttribute('content');
                if (c) return c.replace(/\\s*[|·].*$/, '').trim();
            }
            const t = document.title.replace(/\\s*[|·-]\\s*Facebook.*$/i, '').trim();
            if (t && t !== 'Facebook') return t;
            // h1 last resort — skip known sidebar headings
            const h1s = document.querySelectorAll('h1');
            for (const h1 of h1s) {
                const text = h1.innerText.trim();
                if (text && text !== 'Zarządzanie stroną'
                    && text !== 'Page management' && text !== 'Facebook') {
                    return text;
                }
            }
            return null;
        })()""")

        if not page_name:
            logger.error("Nie udalo sie pobrac nazwy fanpage")
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"fanpage_no_name_{self.account_email}.png"))
            return False
        self._current_page_name = page_name
        logger.info("Nazwa fanpage: '%s'", page_name)

        # Open the avatar dropdown menu
        if not await self._click_profile_avatar():
            os.makedirs(self.screenshot_dir, exist_ok=True)
            await self.page.screenshot(path=
                os.path.join(self.screenshot_dir, f"fanpage_avatar_fail_{self.account_email}.png"))
            return False

        # Look for the fanpage entry in the profile switcher.
        # FB uses aria-label like "Przełącz na profil [Name]" (PL),
        # "Switch to [Name]'s profile" (EN), etc.
        # Also capture personal profile name for later switch-back.
        page_name_json = _json.dumps(page_name)
        search_result = await _eval_js(self.page, f"""(() => {{
            const pageName = {page_name_json};
            let fanpageBtn = null;
            let personalName = null;

            const allBtns = document.querySelectorAll(
                "div[role='button'][aria-label], a[role='button'][aria-label]"
            );
            for (const btn of allBtns) {{
                const label = btn.getAttribute('aria-label') || '';
                const r = btn.getBoundingClientRect();
                if (r.width < 30 || r.height < 20 || r.y <= 0) continue;

                if (label.includes(pageName) && !fanpageBtn) {{
                    fanpageBtn = {{x: r.x, y: r.y, w: r.width, h: r.height,
                                  text: label.slice(0, 100)}};
                }}
                // Capture personal profile name (any "Switch to" that isn't the fanpage)
                const switchMatch = label.match(/(?:Przełącz na profil|Switch to)\\s+(.+?)(?:'s profile)?$/i);
                if (switchMatch && !label.includes(pageName)) {{
                    personalName = switchMatch[1].trim();
                }}
            }}

            if (!fanpageBtn) {{
                // Fallback: search by visible text
                const textBtns = document.querySelectorAll(
                    "div[role='button'], div[role='menuitem'], div[role='listitem']"
                );
                for (const btn of textBtns) {{
                    const text = (btn.innerText || '').trim();
                    if (text.includes(pageName) && text.length < 200) {{
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20 && r.y > 0) {{
                            fanpageBtn = {{x: r.x, y: r.y, w: r.width, h: r.height,
                                          text: text.slice(0, 100)}};
                            break;
                        }}
                    }}
                }}
            }}

            return {{fanpageBtn, personalName}};
        }})()""")

        if search_result and search_result.get("personalName"):
            self._personal_profile_name = search_result["personalName"]
            logger.info("Zapamiętano profil osobisty: '%s'", self._personal_profile_name)

        profile_btn = search_result.get("fanpageBtn") if search_result else None

        if profile_btn:
            logger.info("Znaleziono profil fanpage w menu: '%s'",
                        profile_btn.get("text", ""))
            await mouse_engine.click_element(self.page, profile_btn)
            await HumanImitation.human_delay(3, 5)
            logger.info("Przelaczono na profil fanpage: %s", page_name)
            return True

        # Fanpage not in the quick list — click "Zobacz wszystkie profile"
        see_all = await _eval_js(self.page, """(() => {
            const byLabel = document.querySelector(
                "div[role='button'][aria-label*='wszystkie profile'], "
                + "div[role='button'][aria-label*='all profiles'], "
                + "div[role='button'][aria-label*='ดูโปรไฟล์ทั้งหมด']"
            );
            if (byLabel) {
                const r = byLabel.getBoundingClientRect();
                if (r.width > 30 && r.height > 20)
                    return {x: r.x, y: r.y, w: r.width, h: r.height,
                            text: (byLabel.innerText || byLabel.getAttribute('aria-label') || '').trim().slice(0, 100)};
            }
            const btns = document.querySelectorAll("div[role='button'], a[role='button']");
            for (const btn of btns) {
                const text = (btn.innerText || '').trim().toLowerCase();
                if (text.includes('wszystkie profile') || text.includes('all profiles')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 30 && r.height > 20 && r.y > 0)
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.innerText.trim().slice(0, 100)};
                }
            }
            return null;
        })()""")

        if see_all:
            logger.info("Klikam: '%s'", see_all.get("text", ""))
            await mouse_engine.click_element(self.page, see_all)
            await HumanImitation.human_delay(2, 4)

            profile_btn = await _eval_js(self.page, f"""(() => {{
                const pageName = {page_name_json};
                const btns = document.querySelectorAll(
                    "div[role='button'], div[role='menuitem'], div[role='listitem'], a[role='button']"
                );
                for (const btn of btns) {{
                    const label = btn.getAttribute('aria-label') || '';
                    const text = (btn.innerText || '').trim();
                    if ((label.includes(pageName) || text.includes(pageName))
                        && text.length < 200) {{
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20 && r.y > 0) {{
                            return {{x: r.x, y: r.y, w: r.width, h: r.height,
                                    text: (label || text).slice(0, 100)}};
                        }}
                    }}
                }}
                return null;
            }})()""")

            if profile_btn:
                logger.info("Znaleziono fanpage na liscie profili: '%s'",
                            profile_btn.get("text", ""))
                await mouse_engine.click_element(self.page, profile_btn)
                await HumanImitation.human_delay(3, 5)
                logger.info("Przelaczono na profil fanpage: %s", page_name)
                return True

        # Close any open menu
        logger.warning("Nie znaleziono profilu fanpage '%s' w menu", page_name)
        os.makedirs(self.screenshot_dir, exist_ok=True)
        await self.page.screenshot(path=
            os.path.join(self.screenshot_dir, f"fanpage_not_in_menu_{self.account_email}.png"))
        await self.page.keyboard.press("Escape")
        return False

    async def verify_fanpage_ownership(self, fanpage_url: str) -> dict:
        """Check if the logged-in account manages a fanpage (without switching).

        Returns dict: {"found": bool, "page_name": str|None, "error": str|None}
        """
        from .dom_walker import _eval_js

        result = {"found": False, "page_name": None, "error": None}

        # Navigate to fanpage to extract its name
        logger.info("[verify] Nawigacja do fanpage: %s", fanpage_url)
        await self.page.goto(fanpage_url)
        await HumanImitation.human_delay(3, 5)

        # Wait for the page to load
        title = None
        for _ in range(10):
            title = await _eval_js(self.page, "document.title")
            if title and title != "Facebook" and "|" in str(title):
                break
            await HumanImitation.human_delay(1.5, 2.5)

        # Check for login modal
        login_modal = await _eval_js(self.page, """(() => {
            const emailField = document.querySelector(
                "input[name='email'], input[type='email']"
            );
            const passField = document.querySelector(
                "input[name='pass'], input[type='password']"
            );
            if (!emailField || !passField) return false;
            const er = emailField.getBoundingClientRect();
            const pr = passField.getBoundingClientRect();
            if (er.width < 100 || er.height < 20
                || pr.width < 100 || pr.height < 20) return false;
            if (emailField.closest("div[role='dialog']")) return true;
            if (!document.querySelector("div[role='banner']")) return true;
            if (Math.abs(er.y - pr.y) < 300) return true;
            return false;
        })()""")
        if login_modal:
            logger.warning("[verify] Sesja wygasla — modal logowania")
            password = getattr(self, '_last_password', None)
            if password and await self._handle_login_modal(password):
                await self.page.goto(fanpage_url)
                await HumanImitation.human_delay(3, 5)
            else:
                result["error"] = "Login session expired and re-login failed"
                return result

        # Extract page name
        page_name = await _eval_js(self.page, """(() => {
            const og = document.querySelector('meta[property="og:title"]');
            if (og) {
                const c = og.getAttribute('content');
                if (c) return c.replace(/\\s*[|·].*$/, '').trim();
            }
            const t = document.title.replace(/\\s*[|·-]\\s*Facebook.*$/i, '').trim();
            if (t && t !== 'Facebook') return t;
            const h1s = document.querySelectorAll('h1');
            for (const h1 of h1s) {
                const text = h1.innerText.trim();
                if (text && text !== 'Zarządzanie stroną'
                    && text !== 'Page management' && text !== 'Facebook') {
                    return text;
                }
            }
            return null;
        })()""")

        if not page_name:
            result["error"] = "Could not extract fanpage name from page"
            return result
        result["page_name"] = page_name
        logger.info("[verify] Nazwa fanpage: '%s'", page_name)

        # Open avatar dropdown
        if not await self._click_profile_avatar():
            result["error"] = "Could not open profile avatar menu"
            return result

        # Search for fanpage in profile switcher
        page_name_json = _json.dumps(page_name)
        search_result = await _eval_js(self.page, f"""(() => {{
            const pageName = {page_name_json};
            const allBtns = document.querySelectorAll(
                "div[role='button'][aria-label], a[role='button'][aria-label]"
            );
            for (const btn of allBtns) {{
                const label = btn.getAttribute('aria-label') || '';
                const r = btn.getBoundingClientRect();
                if (r.width < 30 || r.height < 20 || r.y <= 0) continue;
                if (label.includes(pageName)) {{
                    return {{found: true, text: label.slice(0, 100)}};
                }}
            }}
            // Fallback: search by visible text
            const textBtns = document.querySelectorAll(
                "div[role='button'], div[role='menuitem'], div[role='listitem']"
            );
            for (const btn of textBtns) {{
                const text = (btn.innerText || '').trim();
                if (text.includes(pageName) && text.length < 200) {{
                    const r = btn.getBoundingClientRect();
                    if (r.width > 30 && r.height > 20 && r.y > 0) {{
                        return {{found: true, text: text.slice(0, 100)}};
                    }}
                }}
            }}
            return {{found: false}};
        }})()""")

        if search_result and search_result.get("found"):
            logger.info("[verify] Fanpage FOUND in quick switcher: '%s'",
                        search_result.get("text", ""))
            result["found"] = True
            await self.page.keyboard.press("Escape")
            return result

        # Not in quick list — try "Zobacz wszystkie profile"
        see_all = await _eval_js(self.page, """(() => {
            const byLabel = document.querySelector(
                "div[role='button'][aria-label*='wszystkie profile'], "
                + "div[role='button'][aria-label*='all profiles']"
            );
            if (byLabel) {
                const r = byLabel.getBoundingClientRect();
                if (r.width > 30 && r.height > 20)
                    return {x: r.x, y: r.y, w: r.width, h: r.height,
                            text: (byLabel.innerText || byLabel.getAttribute('aria-label') || '').trim().slice(0, 100)};
            }
            const btns = document.querySelectorAll("div[role='button'], a[role='button']");
            for (const btn of btns) {
                const text = (btn.innerText || '').trim().toLowerCase();
                if (text.includes('wszystkie profile') || text.includes('all profiles')) {
                    const r = btn.getBoundingClientRect();
                    if (r.width > 30 && r.height > 20 && r.y > 0)
                        return {x: r.x, y: r.y, w: r.width, h: r.height,
                                text: btn.innerText.trim().slice(0, 100)};
                }
            }
            return null;
        })()""")

        if see_all:
            logger.info("[verify] Klikam: '%s'", see_all.get("text", ""))
            await mouse_engine.click_element(self.page, see_all)
            await HumanImitation.human_delay(2, 4)

            expanded_result = await _eval_js(self.page, f"""(() => {{
                const pageName = {page_name_json};
                const btns = document.querySelectorAll(
                    "div[role='button'], div[role='menuitem'], div[role='listitem'], a[role='button']"
                );
                for (const btn of btns) {{
                    const label = btn.getAttribute('aria-label') || '';
                    const text = (btn.innerText || '').trim();
                    if ((label.includes(pageName) || text.includes(pageName))
                        && text.length < 200) {{
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20 && r.y > 0) {{
                            return {{found: true, text: (label || text).slice(0, 100)}};
                        }}
                    }}
                }}
                return {{found: false}};
            }})()""")

            if expanded_result and expanded_result.get("found"):
                logger.info("[verify] Fanpage FOUND in expanded list: '%s'",
                            expanded_result.get("text", ""))
                result["found"] = True

        if not result["found"]:
            logger.warning("[verify] Fanpage '%s' NOT found in profile switcher", page_name)

        # Close menu
        await self.page.keyboard.press("Escape")
        await HumanImitation.human_delay(0.5, 1)
        return result

    async def switch_to_personal_profile(self) -> bool:
        """Switch back to the personal Facebook profile via avatar dropdown.

        Uses the personal profile name captured during switch_to_page_profile()
        (stored in self._personal_profile_name) for targeted matching.
        Falls back to first "Switch to" button if name not available.
        """
        from .dom_walker import _eval_js

        # Navigate to Facebook home for consistent UI
        await self.page.goto("https://www.facebook.com/")
        await HumanImitation.human_delay(2, 4)

        if not await self._click_profile_avatar():
            logger.warning("Nie udalo sie otworzyc menu profilu (switch back)")
            return False

        # Build JS that prefers matching by remembered name, falls back to first entry
        personal_name_json = _json.dumps(self._personal_profile_name or "")
        personal_btn = await _eval_js(self.page, f"""(() => {{
            const targetName = {personal_name_json};

            // Strategy 1: find by remembered personal name in aria-label
            if (targetName) {{
                const allBtns = document.querySelectorAll(
                    "div[role='button'][aria-label], a[role='button'][aria-label]"
                );
                for (const btn of allBtns) {{
                    const label = btn.getAttribute('aria-label') || '';
                    if (label.includes(targetName)) {{
                        const r = btn.getBoundingClientRect();
                        if (r.width > 50 && r.height > 30 && r.y > 0) {{
                            return {{x: r.x, y: r.y, w: r.width, h: r.height,
                                    text: label.slice(0, 100), strategy: 'name_match'}};
                        }}
                    }}
                }}
            }}

            // Strategy 2: find in profile switching list
            const list = document.querySelector(
                "div[aria-label*='przełączanie profili'], "
                + "div[aria-label*='switching profiles'], "
                + "div[aria-label*='สลับโปรไฟล์']"
            );
            if (list) {{
                const btns = list.querySelectorAll("div[role='button']");
                for (const btn of btns) {{
                    const r = btn.getBoundingClientRect();
                    if (r.width > 50 && r.height > 30 && r.y > 0) {{
                        return {{x: r.x, y: r.y, w: r.width, h: r.height,
                                text: (btn.getAttribute('aria-label') || btn.innerText || '').trim().slice(0, 100),
                                strategy: 'profile_list'}};
                    }}
                }}
            }}

            // Strategy 3: any "Switch to profile" button
            const allBtns = document.querySelectorAll(
                "div[role='button'][aria-label*='Przełącz na profil'], "
                + "div[role='button'][aria-label*='Switch to']"
            );
            for (const btn of allBtns) {{
                const r = btn.getBoundingClientRect();
                if (r.width > 50 && r.height > 30 && r.y > 0) {{
                    return {{x: r.x, y: r.y, w: r.width, h: r.height,
                            text: (btn.getAttribute('aria-label') || btn.innerText || '').trim().slice(0, 100),
                            strategy: 'any_switch'}};
                }}
            }}
            return null;
        }})()""")

        if personal_btn:
            logger.info("Klikam profil osobisty: '%s' (via %s)",
                        personal_btn.get("text", ""),
                        personal_btn.get("strategy", "?"))
            await mouse_engine.click_element(self.page, personal_btn)
            await HumanImitation.human_delay(3, 5)
            logger.info("Przywrocono profil osobisty")
            return True

        # Fallback: click "Zobacz wszystkie profile" and pick the first one
        see_all = await _eval_js(self.page, """(() => {
            const btn = document.querySelector(
                "div[role='button'][aria-label*='wszystkie profile'], "
                + "div[role='button'][aria-label*='all profiles']"
            );
            if (!btn) return null;
            const r = btn.getBoundingClientRect();
            if (r.width < 30 || r.height < 20) return null;
            return {x: r.x, y: r.y, w: r.width, h: r.height,
                    text: (btn.getAttribute('aria-label') || btn.innerText || '').trim().slice(0, 100)};
        })()""")

        if see_all:
            logger.info("Klikam: '%s'", see_all.get("text", ""))
            await mouse_engine.click_element(self.page, see_all)
            await HumanImitation.human_delay(2, 4)

            # Find personal profile by name, or first entry
            first_profile = await _eval_js(self.page, f"""(() => {{
                const targetName = {personal_name_json};
                const btns = document.querySelectorAll(
                    "div[role='button'][aria-label*='Przełącz na profil'], "
                    + "div[role='button'][aria-label*='Switch to']"
                );
                // Prefer name match
                if (targetName) {{
                    for (const btn of btns) {{
                        const label = btn.getAttribute('aria-label') || '';
                        if (label.includes(targetName)) {{
                            const r = btn.getBoundingClientRect();
                            if (r.width > 50 && r.height > 30 && r.y > 0) {{
                                return {{x: r.x, y: r.y, w: r.width, h: r.height,
                                        text: label.slice(0, 100)}};
                            }}
                        }}
                    }}
                }}
                // Fallback: first entry
                for (const btn of btns) {{
                    const r = btn.getBoundingClientRect();
                    if (r.width > 50 && r.height > 30 && r.y > 0) {{
                        return {{x: r.x, y: r.y, w: r.width, h: r.height,
                                text: (btn.getAttribute('aria-label') || btn.innerText || '').trim().slice(0, 100)}};
                    }}
                }}
                return null;
            }})()""")

            if first_profile:
                logger.info("Klikam profil osobisty: '%s'", first_profile.get("text", ""))
                await mouse_engine.click_element(self.page, first_profile)
                await HumanImitation.human_delay(3, 5)
                logger.info("Przywrocono profil osobisty")
                return True

        logger.warning("Nie znaleziono profilu osobistego na liscie")
        return False
