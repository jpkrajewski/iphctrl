# Start iphctrl (daily)

## One command
Open PowerShell in `C:\Users\jakub\Documents\vs\iphctrl` and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

It checks everything below in order, fixes what it can (one admin prompt if needed),
starts the phone session in a minimized window, unlocks the phone and saves
`shots\startup.png`. Each check prints `[ok]`, `[!!]` (warning) or `[XX]` (stops, and says what to do).

Then drive the phone:
```powershell
uv run python -m iphctrl.send unlock "launch instagram" "browse 30" "shot ig"
uv run python -m iphctrl.send "launch com.google.Drive" "shot drive" elements
```
Stop: `powershell -ExecutionPolicy Bypass -File .\stop.ps1`

Session commands: `unlock`, `shot NAME`, `tap X Y`, `tapt TEXT`, `swipe X1 Y1 X2 Y2`,
`type TEXT`, `press home`, `launch APP`, `kill APP`, `elements`, `source`, `browse SECONDS`, `quit`.
Coordinates are screenshot pixels (1170x2532 on iPhone 13).

## What start.ps1 checks (and what to do when it stops)
| Check | If it fails |
|---|---|
| `uv` installed | `winget install astral-sh.uv` |
| Apple Mobile Device Service exists + running | Comes with iTunes. Not running: start.ps1 starts it (admin prompt). |
| AutoViral tasks disabled | start.ps1 disables them (admin prompt). They compete for the phone. |
| `uv sync` | Needs internet the first time. |
| Phone visible on USB (waits 90 s) | Phone ON, unlocked, cable in, tap **Trust**. Nothing in Device Manager either = cable/port/phone off. Shows in Device Manager but not here = restart the phone. |
| Developer Mode | Settings > Privacy & Security > Developer Mode > ON > restart > confirm. |
| WebDriverAgent installed | Re-sideload (below). |
| `.env` passcode | `IPHCTRL_PASSCODE=......` in `.env` (gitignored). Without it, unlock only works with no passcode. |
| Session start (WDA) | Fails ~7 days after the last sideload (free Apple ID signature expired) -> re-sideload. Log: `cmd\serve.log`. |

## Weekly: re-sideload WebDriverAgent (free Apple ID, every <7 days)
No `wda\WebDriverAgentRunner.ipa` (fresh clone)? Build it: `uv run python -m iphctrl.wda_ipa`.

1. Phone plugged in and unlocked. AltServer running (Start menu > AltServer; icon in the tray by the clock).
2. **Hold SHIFT** + click the AltServer tray icon > **Sideload .ipa...** > pick the iPhone >
   `C:\Users\jakub\Documents\vs\iphctrl\wda\WebDriverAgentRunner.ipa` (copy on the Desktop).
3. Apple ID + password + 2FA code if asked (in AltServer's window).
4. Phone: Settings > General > VPN & Device Management > your Apple ID > Trust (if asked).
5. `.\start.ps1` again.

## Phone settings that must stay this way
- Battery > **Low Power Mode OFF** (otherwise Auto-Lock is forced to 30 s and the phone keeps dropping off).
- Display & Brightness > Auto-Lock > **Never**.
- Privacy & Security > **Developer Mode ON**.
- Recommended: Focus/Do Not Disturb ON (banners cover the screen), Automatic iOS updates OFF.

## Everything installed on this PC for this (2026-10-14)
| What | How | Needed? |
|---|---|---|
| iTunes 12.13 + Apple Mobile Device Support 19.4 | already installed (Aug 2026) | **Yes**: USB service for iPhones |
| uv | already installed | **Yes** |
| `iphctrl` python env (pymobiledevice3 11.30, python-dotenv) | `uv sync` | **Yes** |
| AltServer 1.7.5 | `winget install RileyTestut.AltServer` (admin) | **Yes**: signs WDA weekly |
| iCloud for Windows (Microsoft Store) | `winget install 9PKTQ5699M62 --source msstore` | **Yes**: AltServer uses it for Apple's device identity |
| WebDriverAgent 16.15.0 IPA | `wda\WebDriverAgentRunner.ipa` (from appium/WebDriverAgent, `.dSYM` removed) | **Yes** |
| Impactor (PlumeImpactor) GUI 2.6.1 | winget `CLARATION.Impactor.GUI` | No: can uninstall (`winget uninstall CLARATION.Impactor.GUI`) |
| AutoViral driver 0.3.216 | their installer, `C:\ProgramData\autoviral-driver` | No: tasks disabled by start.ps1. Remove fully: admin PowerShell `autoviral-driver disable`, delete `C:\ProgramData\autoviral-driver`, `C:\autoviral-python`, revoke the API key in their dashboard |
| AutoViral's extras: tesseract (winget), uv CPython in `C:\autoviral-python` | their installer | No |

## On the phone (iPhone 13, UDID 00008110-001948C43A84401E)
- Trusted this PC; Developer Mode on; Auto-Lock Never; Low Power Mode off.
- Apps installed by us: **WebDriverAgentRunner-Runner** (needed), **AltStore** (installed by mistake, can delete).
- Passcode stored in `iphctrl\.env`.

More: `docs\LESSONS.md` (every problem and fix), `docs\scaling\` (10 / 50 phones, Mac).
