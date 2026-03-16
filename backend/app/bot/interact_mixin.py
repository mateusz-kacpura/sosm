import logging

import nodriver.cdp.input_

from .human_imitation import HumanImitation
from .checkpoint_detector import CheckpointDetector
from . import mouse_engine

logger = logging.getLogger(__name__)


class InteractMixin:
    """Social interaction methods for FBActions (like, comment, message)."""

    async def like_page(self, page_url: str) -> bool:
        """Navigate to a Facebook page and click the Like button."""
        logger.info("Nawigacja do strony: %s", page_url)
        await self.tab.get(page_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(
            self.tab, self.screenshot_dir, self.account_email
        ):
            return False

        try:
            # Look for Like/Follow button by aria-label pattern
            from .dom_walker import _eval_js
            like_btn = await _eval_js(self.tab, """(() => {
                const btns = document.querySelectorAll('div[role="button"], a[role="button"]');
                for (const btn of btns) {
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const text = (btn.textContent || '').toLowerCase();
                    if (label.includes('like') || label.includes('lubię')
                        || text.includes('like') || text.includes('lubię to')) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20) {
                            return {x: r.x, y: r.y, w: r.width, h: r.height, text: btn.textContent.trim().substring(0, 50)};
                        }
                    }
                }
                return null;
            })()""")

            if not like_btn:
                logger.warning("Nie znaleziono przycisku Like na stronie")
                return False

            logger.info("Klikam przycisk Like: '%s'", like_btn.get("text", ""))
            await mouse_engine.click_element(self.tab, like_btn)
            await HumanImitation.human_delay(1, 3)

            logger.info("Strona polubiona")
            return True

        except Exception as e:
            logger.error("Blad polubienia strony: %s", e)
            return False

    async def comment_on_post(self, post_url: str, comment_text: str) -> bool:
        """Navigate to a post and add a comment."""
        logger.info("Nawigacja do posta: %s", post_url)
        await self.tab.get(post_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(
            self.tab, self.screenshot_dir, self.account_email
        ):
            return False

        try:
            # Find the comment input box
            comment_box = await self.dom.find(
                "div[role='textbox'][contenteditable='true']", timeout=8.0
            )
            if not comment_box:
                # Try clicking "Write a comment" placeholder first
                from .dom_walker import _eval_js
                placeholder = await _eval_js(self.tab, """(() => {
                    const els = document.querySelectorAll('div[role="button"]');
                    for (const el of els) {
                        const t = el.textContent.toLowerCase();
                        if (t.includes('comment') || t.includes('komentarz') || t.includes('napisz')) {
                            const r = el.getBoundingClientRect();
                            if (r.width > 50) return {x: r.x, y: r.y, w: r.width, h: r.height};
                        }
                    }
                    return null;
                })()""")
                if placeholder:
                    await mouse_engine.click_element(self.tab, placeholder)
                    await HumanImitation.human_delay(1, 2)
                    comment_box = await self.dom.find(
                        "div[role='textbox'][contenteditable='true']", timeout=5.0
                    )

            if not comment_box:
                raise TimeoutError("Nie znaleziono pola komentarza")

            await mouse_engine.click_element(self.tab, comment_box)
            await HumanImitation.type_like_human(self.tab, comment_text, delay_range=(0.03, 0.09))
            await HumanImitation.human_delay(1, 2)

            # Submit comment with Enter key
            await self.tab.send(nodriver.cdp.input_.dispatch_key_event(
                type_="keyDown", key="Enter", code="Enter",
                windows_virtual_key_code=13, native_virtual_key_code=13,
            ))
            await HumanImitation.human_delay(2, 4)

            logger.info("Komentarz dodany")
            return True

        except (TimeoutError, Exception) as e:
            logger.error("Blad dodawania komentarza: %s", e)
            return False

    async def send_message(self, profile_url: str, message_text: str) -> bool:
        """Navigate to a profile and send a message via Messenger."""
        logger.info("Nawigacja do profilu: %s", profile_url)
        await self.tab.get(profile_url)
        await HumanImitation.human_delay(3, 6)

        if await CheckpointDetector.handle_checkpoint_if_needed(
            self.tab, self.screenshot_dir, self.account_email
        ):
            return False

        try:
            # Find and click the Message button on the profile
            from .dom_walker import _eval_js
            msg_btn = await _eval_js(self.tab, """(() => {
                const btns = document.querySelectorAll('div[role="button"], a[role="button"], a');
                for (const btn of btns) {
                    const label = (btn.getAttribute('aria-label') || '').toLowerCase();
                    const text = (btn.textContent || '').toLowerCase();
                    if (label.includes('message') || label.includes('wiadomość')
                        || text.includes('message') || text.includes('wyślij wiadomość')) {
                        const r = btn.getBoundingClientRect();
                        if (r.width > 30 && r.height > 20) {
                            return {x: r.x, y: r.y, w: r.width, h: r.height, text: btn.textContent.trim().substring(0, 50)};
                        }
                    }
                }
                return null;
            })()""")

            if not msg_btn:
                raise TimeoutError("Nie znaleziono przycisku Wiadomość na profilu")

            await mouse_engine.click_element(self.tab, msg_btn)
            await HumanImitation.human_delay(3, 5)

            # Find the message input in the chat window
            msg_input = await self.dom.find(
                "div[role='textbox'][contenteditable='true']", timeout=8.0
            )
            if not msg_input:
                raise TimeoutError("Nie znaleziono pola wiadomości")

            await mouse_engine.click_element(self.tab, msg_input)
            await HumanImitation.type_like_human(self.tab, message_text, delay_range=(0.03, 0.09))
            await HumanImitation.human_delay(1, 2)

            # Send with Enter
            await self.tab.send(nodriver.cdp.input_.dispatch_key_event(
                type_="keyDown", key="Enter", code="Enter",
                windows_virtual_key_code=13, native_virtual_key_code=13,
            ))
            await HumanImitation.human_delay(2, 4)

            logger.info("Wiadomość wysłana")
            return True

        except (TimeoutError, Exception) as e:
            logger.error("Blad wysylania wiadomosci: %s", e)
            return False
