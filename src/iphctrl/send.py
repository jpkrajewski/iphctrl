"""Send commands to a running `iphctrl.serve` and print the results.

    uv run python -m iphctrl.send unlock "launch instagram" "browse 30" "shot ig"

Each argument is one command (see serve.py). Waits for each result before the next.
"""

import io
import sys
import time
from pathlib import Path

CMD_DIR = Path(__file__).resolve().parents[2] / "cmd"
TIMEOUT_S = 180


def send(line: str) -> str:
    result = CMD_DIR / "result.txt"
    before = result.stat().st_mtime_ns if result.exists() else 0
    (CMD_DIR / "next.txt").write_text(line, encoding="utf-8")
    deadline = time.monotonic() + TIMEOUT_S
    while time.monotonic() < deadline:
        if result.exists() and result.stat().st_mtime_ns != before:
            time.sleep(0.05)  # let the writer finish
            return result.read_text(encoding="utf-8")
        time.sleep(0.1)
    return f"{line}\nTIMEOUT: is serve running? (start.ps1)"


def main() -> None:
    if isinstance(
        sys.stdout, io.TextIOWrapper
    ):  # cp1250 consoles choke on arrows/emoji
        sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.argv[1:]:
        print(send(line))


if __name__ == "__main__":
    main()
