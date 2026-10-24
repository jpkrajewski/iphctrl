"""Instagram Professional dashboard views: last-30-days total + daily values.

    uv run python -m iphctrl.ig_views            # needs serve running (start.ps1)

Walks Profile -> Professional dashboard -> Views on the phone through serve.
The total comes from the dashboard text. Instagram exposes no per-day numbers
(the chart is a picture, tapping it shows nothing), so daily values are read off
the chart: axis labels from the UI tree give the scale, the magenta line's
pixels give the values. Expect them within ~1% of the chart's top value.
Writes data/ig_views_<date>.csv.
"""

import csv
import io
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import cast
from xml.etree import ElementTree

from PIL import Image

from iphctrl.send import send

ROOT = Path(__file__).resolve().parents[2]
SHOT = ROOT / "shots" / "ig_views.png"
DATA = ROOT / "data"
UNITS = {"": 1, "K": 1_000, "M": 1_000_000}
LOAD_TIMEOUT_S = 20


def parse_count(text: str) -> int:
    """'358.8K' -> 358800, '1,031' -> 1031."""
    m = re.fullmatch(r"([\d.,]+)\s*([KM]?)", text.strip())
    if not m:
        raise ValueError(f"not a count: {text!r}")
    return round(float(m[1].replace(",", "")) * UNITS[m[2]])


def static_texts(source: str) -> list[tuple[str, float, float]]:
    """(text, center x, center y) in WDA points for every visible StaticText."""
    out = []
    for e in ElementTree.fromstring(source).iter("XCUIElementTypeStaticText"):
        a = e.attrib
        text = a.get("label") or a.get("value") or ""
        if a.get("visible") != "true" or not text:
            continue
        x, y, w, h = (float(a[k]) for k in ("x", "y", "width", "height"))
        out.append((text.strip(), x + w / 2, y + h / 2))
    return out


def dashboard_total(source: str) -> int:
    """Views figure on the Professional dashboard (rounded, e.g. 358.8K)."""
    root = ElementTree.fromstring(source)
    views = next(
        e for e in root.iter("XCUIElementTypeButton") if e.get("label") == "Views"
    )
    row_y = float(views.attrib["y"])
    for text, _, y in static_texts(source):
        if abs(y - row_y - 10) < 12 and re.fullmatch(r"[\d.,]+[KM]?", text):
            return parse_count(text)
    raise ValueError("Views total not found on dashboard")


def chart_dates(labels: list[tuple[str, float, float]], today: date) -> list[date]:
    """Every day from the first to the last x-axis date label."""
    found = []
    for text, _, _ in labels:
        try:
            d = datetime.strptime(f"{text} {today.year}", "%b %d %Y").date()  # noqa: DTZ007 - calendar day, no time
        except ValueError:
            continue
        found.append(d.replace(year=d.year - 1) if d > today else d)
    first, last = found[0], found[-1]
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def y_axis(labels: list[tuple[str, float, float]]) -> tuple[float, float, int]:
    """(y of 0, y of top label, top value) in WDA points."""
    ticks = [
        (y, parse_count(t))
        for t, x, y in labels
        if x < 60 and re.fullmatch(r"[\d.]+[KM]?", t)
    ]
    zero_y = next(y for y, v in ticks if v == 0)
    ticks = [(y, v) for y, v in ticks if zero_y - 250 < y <= zero_y]  # skip badges
    top_y, top_v = max(ticks, key=lambda t: t[1])
    return zero_y, top_y, top_v


def pixel(img: Image.Image, x: int, y: int) -> tuple[int, ...]:
    return cast(tuple[int, ...], img.getpixel((x, y)))


def is_line(px: tuple[int, ...]) -> bool:
    r, g, b = px[:3]
    return r > 150 and b > 120 and g < 110  # Instagram's magenta


def is_grid(px: tuple[int, ...]) -> bool:
    r, _, b = px[:3]
    return 220 <= r <= 240 and 220 <= b <= 245 and abs(r - b) < 15  # light gray rule


def gridline_near(img: Image.Image, y: float, x0: int, x1: int) -> int:
    """Row of the horizontal gridline closest to pixel row `y` (axis label center)."""
    rows = [
        r
        for r in range(round(y) - 20, round(y) + 21)
        if sum(is_grid(pixel(img, x, r)) for x in range(x0, x1, 10)) * 10
        > (x1 - x0) * 0.6
    ]
    return min(rows, key=lambda r: abs(r - y))


def line_runs(img: Image.Image, top: int, bottom: int) -> dict[int, tuple[int, int]]:
    """Column -> (first, last) row of line pixels between `top` and `bottom`."""
    out = {}
    for x in range(img.width):
        ys = [y for y in range(top, bottom) if is_line(pixel(img, x, y))]
        if ys:
            out[x] = (ys[0], ys[-1])
    return out


def point_y(
    runs: dict[int, tuple[int, int]], x: int, step: float, stroke: float
) -> float:
    """Line center at a data point. At a peak/trough the column's run is stretched
    by the two slopes meeting there, so measure from the outer edge instead."""
    near = lambda c: runs[min(runs, key=lambda k: abs(k - c))]
    first, last = near(x)
    mid = (first + last) / 2
    before, after = (sum(near(round(x + d * step / 2))) / 2 for d in (-1, 1))
    if before > mid and after > mid:  # peak (rows grow downward)
        return first + stroke / 2
    if before < mid and after < mid:  # trough
        return last - stroke / 2
    return mid


def daily_views(
    img: Image.Image, labels: list[tuple[str, float, float]], scale: float, days: int
) -> list[float]:
    """Unscaled per-day values in units of the top axis label."""
    img = img.convert("RGB")
    zero_y, top_y, top_v = y_axis(labels)
    x0, x1 = round(img.width * 0.15), round(img.width * 0.85)
    zero_px = gridline_near(img, zero_y * scale, x0, x1)
    top_px = gridline_near(img, top_y * scale, x0, x1)
    runs = line_runs(img, top_px - 20, zero_px)
    stroke = sorted(b - a + 1 for a, b in runs.values())[len(runs) // 4]  # flat parts
    base = zero_px - 1 - stroke / 2  # stroke sits on the zero rule, not across it
    left, right = min(runs), max(runs)
    step = (right - left) / (days - 1)
    return [
        max(
            0.0,
            (base - point_y(runs, round(left + step * i), step, stroke))
            / (base - top_px)
            * top_v,
        )
        for i in range(days)
    ]


def scale_to_total(values: list[float], total: int) -> list[int]:
    """The chart gives the shape; the dashboard total fixes the scale."""
    k = total / sum(values)
    return [round(v * k) for v in values]


def _cmd(line: str) -> str:
    out = send(line)
    if "ERROR" in out or "TIMEOUT" in out:
        raise RuntimeError(out)
    return out.partition("\n")[2]


def _wait_for_chart() -> str:
    deadline = time.monotonic() + LOAD_TIMEOUT_S
    while time.monotonic() < deadline:
        source = _cmd("source")
        if 'label="0"' in source and re.search(
            r'label="[A-Z][a-z]{2} \d{1,2}"', source
        ):
            return source
        time.sleep(1)
    raise RuntimeError("Views chart did not load")


def main() -> None:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    for line in ("unlock", "kill instagram", "launch instagram"):
        _cmd(line)
    time.sleep(4)
    _cmd("tapt Profile")
    time.sleep(2)
    _cmd("tapt Professional dashboard entry point")
    time.sleep(3)
    total = dashboard_total(_cmd("source"))
    _cmd("tapt Views")
    source = _wait_for_chart()
    time.sleep(1)  # line animates in
    _cmd(f"shot {SHOT.stem}")

    img = Image.open(SHOT)
    root = ElementTree.fromstring(source)
    scale = img.width / float(
        next(root.iter("XCUIElementTypeApplication")).attrib["width"]
    )
    labels = static_texts(source)
    days = chart_dates(labels, datetime.now().astimezone().date())
    raw = daily_views(img, labels, scale, len(days))
    values = scale_to_total(raw, total)

    DATA.mkdir(exist_ok=True)
    out = DATA / f"ig_views_{datetime.now().astimezone().date()}.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "views_approx"])
        w.writerows(zip(days, values, strict=True))

    print(f"Views {days[0]} - {days[-1]}: {total:,} (dashboard, rounded)")
    print(f"Chart alone sums to {round(sum(raw)):,}; daily scaled to the total")
    for d, v in zip(days, values, strict=True):
        print(f"{d}  {v:>9,}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
