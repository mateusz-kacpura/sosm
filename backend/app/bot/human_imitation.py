import asyncio
import random
from typing import Tuple

import nodriver
import nodriver.cdp.input_

from . import mouse_engine


class HumanImitation:
    """Human-like behavior simulation using nodriver + CDP mouse engine."""

    @staticmethod
    async def type_like_human(tab, text: str, delay_range: Tuple[float, float] = (0.05, 0.15)):
        """Type text character by character with human-like timing."""
        for char in text:
            await tab.send(
                nodriver.cdp.input_.dispatch_key_event(
                    type_="keyDown",
                    text=char,
                )
            )
            await tab.send(
                nodriver.cdp.input_.dispatch_key_event(
                    type_="keyUp",
                    text=char,
                )
            )
            await asyncio.sleep(random.uniform(*delay_range))

    @staticmethod
    async def human_delay(min_sec: float = 1.0, max_sec: float = 3.5):
        """Random delay simulating reading or thinking."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    @staticmethod
    async def natural_scroll(tab, scrolls: int = 3):
        """Simulate natural page scrolling."""
        for _ in range(scrolls):
            direction = random.choice([1, -1]) if random.random() < 0.2 else 1
            distance = random.randint(100, 400) * direction
            await mouse_engine.scroll(tab, distance)
            await HumanImitation.human_delay(0.5, 2.0)
