"""Human-looking timing and gestures on top of `Ui`.

Nothing here is exact on purpose: taps land a few pixels off-center, swipes
vary in length, speed and drift, and pauses follow a skewed distribution
(mostly short, sometimes long) like a person reading a feed.
"""

import asyncio
import random

from iphctrl.ui import Ui

# Screen size in screenshot pixels (iPhone 13). Gestures are expressed as
# fractions of it so they adapt if `Human` is built with another size.
DEFAULT_W, DEFAULT_H = 1170, 2532


async def pause(low: float = 0.4, high: float = 1.6) -> None:
    """Skewed pause: usually near `low`, occasionally up to `high`."""
    await asyncio.sleep(low + (high - low) * random.betavariate(1.5, 4))


class Human:
    def __init__(self, ui: Ui, w: int = DEFAULT_W, h: int = DEFAULT_H) -> None:
        self.ui, self.w, self.h = ui, w, h

    async def tap(self, x: float, y: float, jitter: float = 12) -> None:
        await self.ui.tap(
            x + random.uniform(-jitter, jitter), y + random.uniform(-jitter, jitter)
        )

    async def scroll(self, up: bool = False) -> None:
        """One feed flick: varying length, speed and a slight sideways drift."""
        x = self.w * random.uniform(0.35, 0.7)
        length = self.h * random.uniform(0.25, 0.55)
        start = self.h * random.uniform(0.65, 0.8)
        end = start - length
        drift = random.uniform(-40, 40)
        if up:
            start, end = end, start
        await self.ui.swipe(x, start, x + drift, end, random.uniform(0.12, 0.35))

    async def browse_feed(self, seconds: float) -> int:
        """Scrolls a feed for about `seconds`: reads, flicks, sometimes goes back
        up or lingers on a post. Returns how many flicks it did."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        flicks = 0
        while loop.time() < deadline:
            roll = random.random()
            if roll < 0.08:
                await self.scroll(up=True)  # "wait, what was that"
            else:
                await self.scroll()
            flicks += 1
            if roll > 0.9:
                await pause(4, 12)  # watching a video / reading
            else:
                await pause(0.8, 4)
        return flicks
