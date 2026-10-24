"""Keeps one Phone + WDA session open and runs commands dropped into a file.

    uv run python -m iphctrl.serve            # leave running
    echo "tap 585 1861" > cmd/next.txt         # from anywhere; result in cmd/result.txt

Starting WDA takes ~20 s, longer than a 30 s screen lock leaves for work, so
interactive control (an agent looking at screenshots between steps) goes
through this instead of one CLI process per action.

Every command has a timeout. If the link to the phone drops (tunnel reset,
WDA killed), serve reconnects and runs the interrupted command once more.

Commands (one per file, screenshot pixels):
    unlock | shot NAME | tap X Y | tapt TEXT | swipe X1 Y1 X2 Y2 | type TEXT
    press BUTTON | launch APP | kill APP | elements | source | browse SECONDS | quit
"""

import asyncio
import os
import traceback
from pathlib import Path

from dotenv import load_dotenv
from pymobiledevice3.exceptions import ConnectionTerminatedError, WdaError

from iphctrl.human import Human
from iphctrl.phone import Phone

ROOT = Path(__file__).resolve().parents[2]
CMD_DIR = ROOT / "cmd"
SHOTS = ROOT / "shots"
CMD_TIMEOUT_S = 60
CONNECT_TIMEOUT_S = 120
RECONNECT_DELAY_S = 3
MAX_FAILURES = 10


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


def _timeout(line: str) -> float:
    verb, _, rest = line.partition(" ")
    return float(rest) + 60 if verb == "browse" else CMD_TIMEOUT_S


def _lost(exc: BaseException) -> bool:
    """The link to the phone is gone (vs. an ordinary failure like a missing button)."""
    if isinstance(exc, WdaError):
        return exc.status_code is None  # no HTTP answer at all
    return isinstance(exc, (TimeoutError, OSError, ConnectionTerminatedError, EOFError))


async def _serve(phone: Phone, nxt: Path, result: Path, retry: str | None) -> None:
    """Runs commands until `quit` (returns) or the link drops (raises _Lost)."""
    while True:
        if retry is not None:
            line, retry = retry, None
            again = True
        elif nxt.exists():
            line = nxt.read_text(encoding="utf-8").strip()
            nxt.unlink()
            again = False
        else:
            await asyncio.sleep(0.2)
            continue
        if line == "quit":
            result.write_text("bye", encoding="utf-8")
            return
        try:
            out = await asyncio.wait_for(_run(phone, line), _timeout(line))
        except Exception as e:
            if _lost(e) and not again:
                raise _Lost(line) from e
            out = "ERROR\n" + traceback.format_exc(limit=3)
        result.write_text(f"{line}\n{out}", encoding="utf-8")
        print(f"> {line}: {out.splitlines()[0] if out else ''}", flush=True)


class _Lost(Exception):
    def __init__(self, line: str) -> None:
        self.line = line


async def main() -> None:
    load_dotenv(ROOT / ".env")
    CMD_DIR.mkdir(exist_ok=True)
    nxt, result = CMD_DIR / "next.txt", CMD_DIR / "result.txt"
    nxt.unlink(missing_ok=True)
    result.write_text("starting", encoding="utf-8")
    (CMD_DIR / "serve.pid").write_text(str(os.getpid()), encoding="utf-8")
    retry: str | None = None
    failures = 0
    while True:
        try:
            async with Phone() as phone:
                await asyncio.wait_for(phone.ui(), CONNECT_TIMEOUT_S)
                failures = 0
                if retry is None:
                    result.write_text("ready", encoding="utf-8")
                print(f"ready ({phone.tunnel} tunnel)", flush=True)
                await _serve(phone, nxt, result, retry)
                return
        except _Lost as lost:
            retry = lost.line
            print(f"link to phone lost during {retry!r}: reconnecting", flush=True)
        except Exception:
            failures += 1
            print(f"connect failed ({failures}/{MAX_FAILURES})", flush=True)
            traceback.print_exc(limit=2)
            if failures >= MAX_FAILURES:
                result.write_text(
                    "ERROR\nphone unreachable, serve stopped", encoding="utf-8"
                )
                raise
        await asyncio.sleep(RECONNECT_DELAY_S)


if __name__ == "__main__":
    asyncio.run(main())
