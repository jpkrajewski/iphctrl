"""`iphctrl` command line.

    iphctrl devices
    iphctrl info
    iphctrl screenshot [out.png]          # default shots/<timestamp>.png
    iphctrl launch snapchat               # alias or bundle id
    iphctrl kill snapchat
    iphctrl apps [filter]
Global: --udid UDID (default: first USB iPhone)
"""

import argparse
import asyncio
import io
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from iphctrl.phone import Phone, usb_devices

SHOTS = Path(__file__).resolve().parents[2] / "shots"


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="iphctrl", description="Control an iPhone over USB"
    )
    p.add_argument("--udid")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("devices")
    sub.add_parser("info")
    s = sub.add_parser("screenshot")
    s.add_argument("out", nargs="?")
    for name in ("launch", "kill"):
        s = sub.add_parser(name)
        s.add_argument("app")
    s = sub.add_parser("apps")
    s.add_argument("filter", nargs="?", default="")
    # touch / keyboard (WebDriverAgent); coordinates are screenshot pixels
    s = sub.add_parser("tap")
    s.add_argument("x", type=float, nargs="?")
    s.add_argument("y", type=float, nargs="?")
    s.add_argument("--text", help="tap element whose label contains this")
    s = sub.add_parser("hold")
    s.add_argument("x", type=float)
    s.add_argument("y", type=float)
    s.add_argument("--seconds", type=float, default=1.0)
    s = sub.add_parser("swipe")
    for c in ("x1", "y1", "x2", "y2"):
        s.add_argument(c, type=float)
    s = sub.add_parser("type")
    s.add_argument("text")
    s = sub.add_parser("press")
    s.add_argument("button", help="home, volumeup, volumedown, lock")
    sub.add_parser("elements", help="visible tappable elements with pixel centers")
    sub.add_parser("unlock", help="wake + swipe + IPHCTRL_PASSCODE from .env")
    return p


async def _run(a: argparse.Namespace) -> None:
    if a.cmd == "devices":
        print(
            "\n".join(await usb_devices())
            or "no iPhone visible on USB (unlock it, replug, tap Trust)"
        )
        return
    async with Phone(a.udid) as phone:
        match a.cmd:
            case "info":
                print(json.dumps(phone.info(), indent=2))
            case "screenshot":
                out = (
                    a.out or SHOTS / f"{datetime.now().astimezone():%Y%m%d-%H%M%S}.png"
                )
                print(await phone.screenshot(out))
            case "launch":
                print(f"launched {a.app} pid {await phone.launch(a.app)}")
            case "kill":
                await phone.kill(a.app)
                print(f"killed {a.app}")
            case "apps":
                for bundle, name in sorted(
                    (await phone.apps()).items(), key=lambda x: x[1].lower()
                ):
                    if a.filter.lower() in f"{bundle} {name}".lower():
                        print(f"{name:<30} {bundle}")
            case "tap":
                ui = await phone.ui()
                await (ui.tap_text(a.text) if a.text else ui.tap(a.x, a.y))
            case "hold":
                await (await phone.ui()).long_press(a.x, a.y, a.seconds)
            case "swipe":
                await (await phone.ui()).swipe(a.x1, a.y1, a.x2, a.y2)
            case "type":
                await (await phone.ui()).type(a.text)
            case "press":
                await (await phone.ui()).press(a.button)
            case "unlock":
                await (await phone.ui()).unlock(os.environ.get("IPHCTRL_PASSCODE"))
                print(await phone.screenshot(SHOTS / "unlocked.png"))
            case "elements":
                for e in await (await phone.ui()).elements():
                    print(f"{e['x']:>5} {e['y']:>5}  {e['type']:<15} {e['label']}")


def main() -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    if isinstance(
        sys.stdout, io.TextIOWrapper
    ):  # cp1250 consoles choke on arrows/emoji
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(_run(_parser().parse_args()))
