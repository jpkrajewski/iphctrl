"""Keeps one Phone + WDA session open and runs commands dropped into a file.

    uv run python -m iphctrl.serve            # leave running
    echo "tap 585 1861" > cmd/next.txt         # from anywhere; result in cmd/result.txt

Starting WDA takes ~20 s, longer than a 30 s screen lock leaves for work, so
interactive control (an agent looking at screenshots between steps) goes
through this instead of one CLI process per action.

Commands (one per file, screenshot pixels):
    unlock | shot NAME | tap X Y | tapt TEXT | swipe X1 Y1 X2 Y2 | type TEXT
    press BUTTON | launch APP | kill APP | elements | source | browse SECONDS | quit
"""

import asyncio
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv

from iphctrl.human import Human
from iphctrl.phone import Phone

ROOT = Path(__file__).resolve().parents[2]
CMD_DIR = ROOT / "cmd"
SHOTS = ROOT / "shots"


async def _run(phone: Phone, line: str) -> str:
    ui = await phone.ui()
    verb, _, rest = line.strip().partition(" ")
    nums = [float(n) for n in rest.split()] if verb in ("tap", "swipe") else []
    match verb:
        case "unlock":
            await ui.unlock(os.environ.get("IPHCTRL_PASSCODE"))
        case "shot":
            return str(await phone.screenshot(SHOTS / f"{rest or 'serve'}.png"))
        case "tap":
            await ui.tap(*nums)
        case "tapt":
            await ui.tap_text(rest)
        case "swipe":
            await ui.swipe(*nums)
        case "type":
            await ui.type(rest)
        case "press":
            await ui.press(rest)
        case "launch":
            return f"pid {await phone.launch(rest)}"
        case "kill":
            await phone.kill(rest)
        case "elements":
            return "\n".join(
                f"{e['x']} {e['y']} {e['type']} {e['label']}"
                for e in await ui.elements()
            )
        case "source":
            return await ui.source()
        case "browse":
            return f"flicks {await Human(ui).browse_feed(float(rest))}"
        case _:
            return f"unknown command {verb!r}"
    return "ok"


async def main() -> None:
    load_dotenv(ROOT / ".env")
    CMD_DIR.mkdir(exist_ok=True)
    nxt, result = CMD_DIR / "next.txt", CMD_DIR / "result.txt"
    nxt.unlink(missing_ok=True)
    result.write_text("starting", encoding="utf-8")
    (CMD_DIR / "serve.pid").write_text(str(os.getpid()), encoding="utf-8")
    async with Phone() as phone:
        await phone.ui()
        result.write_text("ready", encoding="utf-8")
        print("ready", flush=True)
        while True:
            if not nxt.exists():
                await asyncio.sleep(0.2)
                continue
            line = nxt.read_text(encoding="utf-8").strip()
            nxt.unlink()
            if line == "quit":
                result.write_text("bye", encoding="utf-8")
                return
            try:
                out = await _run(phone, line)
            except Exception:  # noqa: BLE001 - report any failure, keep serving
                out = "ERROR\n" + traceback.format_exc(limit=3)
            result.write_text(f"{line}\n{out}", encoding="utf-8")
            print(f"> {line}: {out.splitlines()[0] if out else ''}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
