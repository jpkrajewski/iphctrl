"""Builds wda/WebDriverAgentRunner.ipa from the official appium/WebDriverAgent release.

    uv run python -m iphctrl.wda_ipa            # default version below

Downloads the unsigned real-device build, checks its sha256, drops the `.dSYM`
folders (AltServer's ldid rejects them) and zips `Payload/*.app` as an IPA.
Sign/install it with AltServer (STARTUP.md).
"""

import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v16.15.0"
SHA256 = "ca02adb06055722e969a417726eb7689138b78b09414d4baf425f80fab3cca1e"
URL = f"https://github.com/appium/WebDriverAgent/releases/download/{VERSION}/WebDriverAgentRunner-Runner.zip"
WDA_DIR = Path(__file__).resolve().parents[2] / "wda"


def build() -> Path:
    src, build_dir = (
        WDA_DIR / "src" / "WebDriverAgentRunner-Runner.zip",
        WDA_DIR / "build",
    )
    src.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        urllib.request.urlretrieve(URL, src)
    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != SHA256:
        src.unlink()
        raise SystemExit(f"sha256 mismatch for {URL}: {digest}")

    shutil.rmtree(build_dir, ignore_errors=True)
    with zipfile.ZipFile(src) as z:
        z.extractall(build_dir / "Payload")
    for dsym in list((build_dir / "Payload").rglob("*.dSYM")):
        shutil.rmtree(dsym)
    out = WDA_DIR / "WebDriverAgentRunner"
    shutil.make_archive(str(out), "zip", build_dir, "Payload")
    ipa = out.with_suffix(".ipa")
    out.with_suffix(".zip").replace(ipa)
    return ipa


if __name__ == "__main__":
    if isinstance(
        sys.stdout, io.TextIOWrapper
    ):  # cp1250 consoles choke on arrows/emoji
        sys.stdout.reconfigure(encoding="utf-8")
    print(build())
