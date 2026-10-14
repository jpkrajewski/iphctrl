# What we learned getting one iPhone under cable control (2026-10-14)

Setup: Windows 11, iPhone 13 (iPhone14,5) on iOS 26.5, not jailbroken, USB cable only.
Every item below is something that actually broke or cost time, and how it was fixed.

## The stack that works
| Layer | What | Notes |
|---|---|---|
| USB transport | Apple Mobile Device Service (AMDS, from iTunes / Apple Mobile Device Support) | Listens on `127.0.0.1:27015` (usbmux). One service for all phones. |
| Device protocols | [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) (open source, Python) | Lockdown, Developer Disk Image, iOS 17+ tunnel, DVT, WDA client. |
| iOS 17+ tunnel | `UserspaceRsdTunnel` (pure-Python TCP stack) | **No admin rights, no tunneld service.** One tunnel per *process*. |
| Screenshots, open/close apps | DVT (Instruments) over the tunnel | Needs Developer Mode on. |
| Touch / type / read UI | WebDriverAgent (WDA) on the phone, driven over usbmux | Unsigned build from appium/WebDriverAgent, signed with AltServer. |
| Signing (free Apple ID) | AltServer + Apple's iCloud for Windows | iCloud supplies the real Apple device identity. 7-day signature. |

## Gotchas, in the order we hit them
1. **Phone visible to Windows but not to AMDS** (`usbmux list` = `[]`, Device Manager shows "Apple iPhone").
   Restarting AMDS and re-enumerating the USB device didn't fix it. A **phone reboot + replug** did.
   Rule: an empty usbmux list while the phone shows in Device Manager means the phone side is at fault (locked, mid-reboot, or a Developer Mode prompt).
2. **Phone drops off USB whenever it locks** (a passcode is set, so USB data is restricted while locked).
   This is the main cause of "Device is not connected". Fix: Auto-Lock **Never**.
3. **Low Power Mode silently forces Auto-Lock to 30 s** and greys the setting out. The user believed Auto-Lock was set to Never; it was really 30 s. Always verify in Settings → Display & Brightness.
4. **Developer Mode toggle is hidden** until a developer tool asks for it: `pymobiledevice3 amfi reveal-developer-mode`.
5. **The Developer Disk Image (personalized, iOS 17+)** is downloaded and mounted automatically, but it unmounts on every reboot. `Phone()` remounts it.
6. **WDA signing route**
   - Sideloadly: winget installer **hash mismatch**, so not used.
   - Impactor / plumesign: fakes the Apple device identity through a community server (`ani.sidestore.app`); the login failed (HTML instead of plist, then a panic). Rejected: untrusted.
   - AutoViral: sends your Apple ID **password to its own backend**, which signs for you. Rejected.
   - **AltServer + iCloud for Windows**: works, and your Apple ID only talks to Apple.
7. **The AltServer tray menu has no sideload item unless you Shift+click.** A plain click only offers "Install AltStore" (we installed AltStore by mistake first).
8. **AltServer's signer (ldid) rejects the `.dSYM` folder** inside the WDA build:
   `_assert(): Swap(mach_header_->filetype) == MH_EXECUTE ...`. Delete `*.dSYM` before zipping the IPA.
9. **A free account renames the bundle id**: `com.facebook.WebDriverAgentRunner.xctrunner.<TEAMID>`. Find the runner by substring, not by an exact id.
10. **WDA startup takes ~20 s per process.** One CLI process per action lets the screen lock in between. Use the persistent session `python -m iphctrl.serve` and send it commands.
11. **The passcode keypad is invisible to accessibility.** Digits must be tapped by position. `unlock` must first check that the lock screen is really showing; otherwise it taps "digits" into whatever app is open (it opened Night Shift once).
12. **WDA's own `/wda/unlock` pressed the lock button** (the screen went black). Use Home + swipe up + keypad instead.
13. **Settings (and Drive's file grid) return an empty or useless accessibility tree.** Tap by pixel from a fresh screenshot.
14. **Pages re-layout after load** (the Battery chart pushed Low Power Mode down ~700 px). Screenshot immediately before a pixel tap, never from a cached one.
15. **Notification banners cover the top of the screen** (an X notification hid the Threads header). Use Do Not Disturb / a Focus on automation phones.
16. **Apps may be logged out or ask for SMS verification** (Threads). Detect from the screenshot and stop. Don't tap blindly.
17. **Windows console is cp1250**: printing tool output with arrows/emoji crashes Python unless stdout is reconfigured to UTF-8.

## Coordinates
- Screenshot = 1170×2532 px on iPhone 13; WDA works in points (390×844); `Ui` converts (scale 3).
- Gestures in `human.py` are fractions of the screen, so they survive other models.
  The keypad positions in `ui.py` are measured for iPhone 13 / iOS 26: re-measure for other models.

## Verified recipes
- Unlock: `unlock` (Home → swipe up from the bottom → keypad by position, from `IPHCTRL_PASSCODE`).
- Settings change: launch Settings → screenshot → pixel tap → screenshot to confirm.
- Drive → Photos: Drive → folder → file's **...** → Send a copy → Save Video. The file lands as the newest item in Photos.
- Human-like feed: `Human(ui).browse_feed(seconds)`.
