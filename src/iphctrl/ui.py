"""Touch and keyboard through WebDriverAgent (WDA) running on the phone.

`Phone.ui()` starts the WDA runner app over the XCUITest channel and returns a
`Ui`. Coordinates are **screenshot pixels** (what you see in shots/*.png); they
are converted to the screen points WDA expects.
"""

import asyncio
from contextlib import suppress
from typing import Any
from xml.etree import ElementTree

from pymobiledevice3.cli.developer.wda import wait_for_xctest_app
from pymobiledevice3.exceptions import WdaError
from pymobiledevice3.services.wda import WdaServiceClient

RUNNER_MARK = "WebDriverAgentRunner.xctrunner"  # AltServer may append .<TEAMID>
TAPPABLE = {
    "Button",
    "Cell",
    "Icon",
    "Link",
    "Switch",
    "TextField",
    "SecureTextField",
    "SearchField",
    "Key",
    "Tab",
}


class Ui:
    def __init__(
        self, client: WdaServiceClient, runner: asyncio.Future[None], scale: float
    ) -> None:
        self._wda = client
        self._runner = runner
        self.scale = scale  # screenshot pixels per WDA point

    @classmethod
    async def start(
        cls, lockdown: Any, rsd: Any, runner_bundle: str, screenshot_width: int
    ) -> "Ui":
        runner = await wait_for_xctest_app(rsd, runner_bundle)
        client = WdaServiceClient(service_provider=lockdown, timeout=30.0)
        await client.start_session()
        size = await client._request_json(
            "GET", f"/session/{client.session_id}/window/size"
        )
        return cls(client, runner, screenshot_width / size["value"]["width"])

    async def close(self) -> None:
        self._runner.cancel()
        with suppress(asyncio.CancelledError):
            await self._runner

    def _pt(self, v: float) -> float:
        return round(v / self.scale, 1)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._wda._request_json(
            "POST", f"/session/{self._wda.session_id}{path}", payload
        )

    # -- touch --------------------------------------------------------------------
    async def tap(self, x: float, y: float) -> None:
        await self._post("/wda/tap", {"x": self._pt(x), "y": self._pt(y)})

    async def long_press(self, x: float, y: float, seconds: float = 1.0) -> None:
        await self._post(
            "/wda/touchAndHold",
            {"x": self._pt(x), "y": self._pt(y), "duration": seconds},
        )

    async def swipe(
        self, x1: float, y1: float, x2: float, y2: float, seconds: float = 0.3
    ) -> None:
        await self._wda.swipe(
            round(self._pt(x1)),
            round(self._pt(y1)),
            round(self._pt(x2)),
            round(self._pt(y2)),
            seconds,
            self._wda.session_id,
        )

    async def tap_text(self, text: str, scrolls: int = 4) -> None:
        """Taps the first element whose label/name/value contains `text`,
        scrolling down up to `scrolls` times to find it."""
        q = f"label CONTAINS '{text}' OR name CONTAINS '{text}' OR value CONTAINS '{text}'"
        for attempt in range(scrolls + 1):
            try:
                element = await self._wda.find_element(
                    "predicate string", q, self._wda.session_id
                )
                break
            except WdaError:
                if attempt == scrolls:
                    raise
                await self.scroll_down()
        await self._wda.click(element, self._wda.session_id)

    async def scroll_down(self) -> None:
        """About half a screen down (finger moves bottom to top)."""
        size = await self._wda._request_json(
            "GET", f"/session/{self._wda.session_id}/window/size"
        )
        w, h = size["value"]["width"], size["value"]["height"]
        await self._wda.swipe(
            round(w / 2),
            round(h * 0.7),
            round(w / 2),
            round(h * 0.3),
            0.3,
            self._wda.session_id,
        )
        await asyncio.sleep(0.6)

    # -- lock screen ----------------------------------------------------------------
    # The passcode keypad is hidden from accessibility, so digits are tapped by
    # position (fractions of the screenshot, measured on iPhone 13 / iOS 26).
    KEYPAD_COLS = (0.2385, 0.5, 0.7615)
    KEYPAD_ROWS = (0.3945, 0.5083, 0.622, 0.7358)

    def _key(self, digit: str, w: float, h: float) -> tuple[float, float]:
        if digit == "0":
            return w * self.KEYPAD_COLS[1], h * self.KEYPAD_ROWS[3]
        i = int(digit) - 1
        return w * self.KEYPAD_COLS[i % 3], h * self.KEYPAD_ROWS[i // 3]

    async def is_locked(self) -> bool:
        """Lock screen or passcode keypad is showing (also true while the display is off)."""
        src = await self.source()
        return (
            'label="Locked"' in src
            or "Passcode" in src
            or 'name="SBUIPasscodeEntryField"' in src
        )

    async def unlock(self, passcode: str | None) -> None:
        """Wakes the screen, swipes up and types the passcode (if any).
        Does nothing when the phone is already unlocked, so it never taps into an app."""
        if not await self.is_locked():
            return
        size = await self._wda._request_json(
            "GET", f"/session/{self._wda.session_id}/window/size"
        )
        w, h = size["value"]["width"] * self.scale, size["value"]["height"] * self.scale
        await self.press("home")
        await asyncio.sleep(0.8)
        await self.swipe(w / 2, h * 0.985, w / 2, h * 0.35, 0.25)
        await asyncio.sleep(1.2)
        for digit in passcode or "":
            await self.tap(*self._key(digit, w, h))
            await asyncio.sleep(0.25)
        await asyncio.sleep(1.0)

    # -- keyboard / buttons -------------------------------------------------------
    async def type(self, text: str) -> None:
        """Types into the focused field (tap the field first)."""
        await self._wda.send_keys(text, self._wda.session_id)

    async def press(self, button: str) -> None:
        """home, volumeup, volumedown, lock."""
        await self._wda.press_button(button, self._wda.session_id)

    # -- reading ----------------------------------------------------------------------
    async def source(self) -> str:
        return await self._wda.get_source(self._wda.session_id)

    async def elements(self) -> list[dict[str, Any]]:
        """Visible tappable elements with centers in screenshot pixels."""
        root = ElementTree.fromstring(await self.source())
        out = []
        for e in root.iter():
            a = e.attrib
            kind = e.tag.removeprefix("XCUIElementType")
            if kind not in TAPPABLE or a.get("visible") != "true":
                continue
            x, y, w, h = (float(a.get(k, 0)) for k in ("x", "y", "width", "height"))
            label = a.get("label") or a.get("name") or a.get("value") or ""
            out.append(
                {
                    "type": kind,
                    "label": label,
                    "x": round((x + w / 2) * self.scale),
                    "y": round((y + h / 2) * self.scale),
                }
            )
        return out
