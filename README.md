# iphctrl

> **Daily start: see [STARTUP.md](STARTUP.md)** - one command: `powershell -ExecutionPolicy Bypass -File .\start.ps1`

Drive normal iPhones over a USB cable from Windows with Python. Built on
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3), an open-source
re-implementation of Apple's device protocols.

```
Python (iphctrl) ── pymobiledevice3 ── Apple Mobile Device Service (usbmux, 127.0.0.1:27015) ── USB ── iPhone
                                   └── iOS 17+ RSD tunnel (userspace, no admin) ── DVT / Instruments services
```

## One-time setup per PC
1. **Apple Mobile Device Service** must be running. It comes with iTunes or Apple Devices.
   Check with `Get-Service 'Apple Mobile Device Service'`.
   (The AutoViral installer added it on this PC.)
2. Install `uv`, then run `uv sync` in this folder.

## One-time setup per phone
1. Plug it in with a data cable, unlock it, and tap **Trust** (then enter the passcode).
2. Turn on **Developer Mode**: Settings → Privacy & Security → Developer Mode → restart →
   after the restart, unlock and confirm **Turn On**.
   If the toggle is missing, run `uv run pymobiledevice3 amfi reveal-developer-mode` with the phone plugged in.
   If the phone has no passcode, `uv run pymobiledevice3 amfi enable-developer-mode` can do it from the PC.
3. Check: `uv run iphctrl info`.
   The first run downloads and mounts the Developer Disk Image (personalized on iOS 17+). That needs internet once per boot.

## Commands

```powershell
uv run iphctrl devices                 # UDIDs visible on USB
uv run iphctrl info                    # model, iOS, name
uv run iphctrl screenshot              # shots/<time>.png
uv run iphctrl launch snapchat         # alias or bundle id
uv run iphctrl kill snapchat
uv run iphctrl apps snap               # find bundle ids
uv run iphctrl --udid <UDID> ...       # pick a phone when several are plugged in
```

```python
import asyncio
from iphctrl import Phone

async def main():
    async with Phone() as phone:
        await phone.launch("instagram")
        await phone.screenshot("shots/ig.png")

asyncio.run(main())
```

## How it works
- **usbmux**: Apple Mobile Device Service multiplexes TCP to the phone over USB. `lockdownd` (port 62078) is the entry point; pairing (Trust) creates a pair record stored by the service.
- **Developer Disk Image (DDI)**: enables developer services (screenshots, process control). iOS 17+ uses a *personalized* image signed by Apple per device. pymobiledevice3 fetches it automatically. It stays mounted until the phone reboots.
- **iOS 17+ tunnel**: developer services moved behind RemoteXPC / RSD over a tunnel. pymobiledevice3's `UserspaceRsdTunnel` runs the tunnel's TCP/IP stack in Python, so no admin rights and no `tunneld` service are needed. It needs iOS 17.4+; older 17.x versions need `sudo pymobiledevice3 remote tunneld` (admin) instead.
- **DVT (Instruments)**: `Screenshot` and `ProcessControl` (launch/kill by bundle id).

## WebDriverAgent (tap / swipe / type)
iOS doesn't let a host inject touches.
[WebDriverAgent](https://github.com/appium/WebDriverAgent) (WDA) is an XCUITest runner app on
the phone that serves an HTTP API on port 8100. `Phone.ui()` starts it through the XCUITest
channel and talks to it over usbmux (`src/iphctrl/ui.py`).

**Files**
- `wda/WebDriverAgentRunner.ipa`: the unsigned real-device build `WebDriverAgentRunner-Runner.zip` from appium/WebDriverAgent v16.15.0 (sha256 `ca02adb0…cca1e`), repacked as `Payload/*.app` with the `.dSYM` debug folder removed (AltServer's signer, ldid, rejects it with `_assert(): Swap(mach_header_->filetype) == MH_EXECUTE ...`). A copy is on the Desktop.
- Signer: **AltServer** (by Riley Testut, `winget install RileyTestut.AltServer`). It gets Apple's device identity from **Apple's own iCloud for Windows** (Microsoft Store), so your Apple ID only ever talks to Apple. No third-party identity server is involved.
  Not used: Impactor/plumesign and Sideloadly fake that identity through community servers (`ani.sidestore.app`). AutoViral sends your Apple ID password to its own backend, which does the signing.

**Install / re-sign (every 7 days with a free Apple ID)**
1. Phone unlocked and plugged in; AltServer running (its icon is in the system tray, by the clock).
2. **Shift + click** the AltServer tray icon → **Sideload .ipa…** → pick the iPhone → choose `WebDriverAgentRunner.ipa`.
3. Enter the Apple ID and password, then the 2FA code (in AltServer's own window).
   A free account can't use `com.facebook.*`, so AltServer appends your team id to the bundle id. That's fine.
4. On the phone: Settings → General → VPN & Device Management → your Apple ID → Trust.
5. `uv run iphctrl elements`. The first touch command starts WDA, which takes a few seconds.
   The runner is found automatically: any installed bundle id containing `WebDriverAgentRunner.xctrunner`.

Free Apple ID limits: 3 sideloaded apps per device and 10 app IDs per week. The signature expires after 7 days; when it does, WDA fails to start, and you repeat step 2.

**Touch commands** (coordinates are screenshot pixels, read from `shots/*.png`)
```powershell
uv run iphctrl elements                # tappable things + pixel centers
uv run iphctrl tap 585 1300            # or: tap --text "Search"
uv run iphctrl type "hello"            # into the focused field
uv run iphctrl swipe 585 2000 585 600  # scroll up
uv run iphctrl hold 585 1300 --seconds 1
uv run iphctrl press home              # home, volumeup, volumedown, lock
```
Each CLI call starts WDA again (a few seconds). For many steps, use Python with one `Phone`:
```python
async with Phone() as phone:
    ui = await phone.ui()
    await ui.tap_text("Search"); await ui.type("cats")
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| Phone vanishes a minute after it worked | The screen locked. Set Settings → Display & Brightness → Auto-Lock → **Never**, keep Low Power Mode **off** (it forces a 30 s lock), and turn on Settings → Face ID & Passcode → **Accessories**. |
| `iphctrl devices` empty, but Windows shows "Apple iPhone" | Unlock the phone, unplug it, plug it back in and tap Trust. Try another cable or port (a charge-only cable won't work). If that fails, restart Apple Mobile Device Service from an admin window. |
| `DeveloperModeIsNotEnabledError` / mount fails | Turn on Developer Mode (above) and unlock the phone. |
| Pairing / `PasswordRequiredError` | Unlock the phone and accept Trust. |
| `UserspaceTunnelUnavailableError` | iOS 17.0–17.3: update iOS, or run `pymobiledevice3 remote tunneld` in an admin window and use `--tunnel`. |
| Other tools hold the phone (AutoViral driver, iTunes) | Quit them (`autoviral-driver disable` in an admin window, or stop the scheduled task) and replug. |

## Phones seen on this PC
- `00008110-001948C43A84401E`: iPhone 13 (iPhone14,5), iOS 26.5.

## More docs
- [docs/LESSONS.md](docs/LESSONS.md): everything that broke on the first phone and how it was fixed.
- [docs/scaling/](docs/scaling/README.md): 10 phones by cable, 50 on Windows, Mac setup, per-phone checklist.
