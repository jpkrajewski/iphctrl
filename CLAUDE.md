# CLAUDE.md — iphctrl

Control normal (non-jailbroken) iPhones over **USB cable** from Windows, in Python,
with [pymobiledevice3](https://github.com/doronz88/pymobiledevice3). No cloud, no
vendor driver. Read README.md for the full background.

## Run
- Start everything: `powershell -ExecutionPolicy Bypass -File .\start.ps1` (STARTUP.md). Then `uv run python -m iphctrl.send <cmd>...`.
- Always `uv run iphctrl ...` / `uv run python ...` from this folder. Unset a foreign
  `VIRTUAL_ENV` first if uv warns about it.
- Commands: `devices`, `info`, `screenshot [out]`, `launch <app>`, `kill <app>`, `apps [filter]`, global `--udid`.
- Python: `async with Phone() as phone:` (src/iphctrl/phone.py). One `Phone` per process.
- Aliases (snapchat, instagram, tiktok, ...) live in `src/iphctrl/apps.py`. Unknown
  app: `iphctrl apps <word>` to find the bundle id, then add an alias.
- Raw tool for anything not wrapped yet: `uv run pymobiledevice3 --help`
  (e.g. `developer dvt ls /`, `syslog live`, `springboard ...`).

## Working rules
- After every action, take a screenshot and look at it (Read the PNG) before the next step.
- Screenshots go to `shots/` (gitignored). Don't spray files elsewhere.
- Never post, send snaps/DMs, follow, delete or change account settings unless the user
  asked for that exact action in this session.
- Before blaming code, run `uv run iphctrl devices`. Empty = phone not visible to
  Apple Mobile Device Service: user must unlock, replug, tap Trust (see README troubleshooting).

## Capabilities
- Developer Mode only: screenshot, launch/kill app, list apps, device info.
- With WebDriverAgent installed (README §WebDriverAgent): `tap x y` / `tap --text`, `hold`,
  `swipe`, `type`, `press home`, `elements` (`src/iphctrl/ui.py`). Coordinates are
  **screenshot pixels**: read the PNG, pick the point, tap it. Prefer `elements` /
  `tap --text` over guessed coordinates.
- WDA "not installed" or fails to start = the 7-day free signature expired: re-sideload it with AltServer (README). The Apple ID login is the user's; never handle their password.
- The phone must have Auto-Lock = Never, or it drops off USB once the screen locks.

## Code style
- Small modules, one job each. Async all the way (pymobiledevice3 is async).
- Add new device actions as `Phone` methods + a CLI subcommand; keep the CLI thin.

## Unlock + human-like use
- Locked/black screen: `uv run iphctrl unlock` (wake, swipe, types IPHCTRL_PASSCODE from .env;
  keypad tapped by position, it's hidden from accessibility). Do it in the same process as the
  next steps when scripting: the screen may sleep between separate CLI calls.
- `src/iphctrl/human.py`: `Human(ui).browse_feed(seconds)` = random flick length/speed/drift,
  skewed pauses, occasional scroll-back and long lingers. Use it for any feed scrolling.
- Check the screenshot after opening an app: login / verification screens (e.g. Threads SMS code)
  stop the flow, report them instead of tapping blindly.

## Interactive control: use the persistent session
- Start once (background): `uv run python -m iphctrl.serve`. Then drop one command into
  `cmd/next.txt` and read `cmd/result.txt` (commands listed in `src/iphctrl/serve.py`).
  WDA startup is ~20 s per process, so never drive step-by-step with separate CLI calls.
- Many apps (Settings!) expose an empty accessibility tree. Then: `shot`, read the PNG,
  tap by pixel. Pages re-layout while loading (charts etc.): screenshot right before tapping.
- `unlock` is a no-op when already unlocked (it checks the lock screen first); still batch
  `unlock` in front of any step sequence.
- Phone baseline (already set on the iPhone 13): Auto-Lock Never, Low Power Mode off.
  Low Power Mode silently forces Auto-Lock 30 s and greys the setting out.

## Recipes (verified)
- **Drive -> Photos**: `launch com.google.Drive` -> `tapt <folder>` -> tap the file's **...** ->
  `tapt Send a copy` (wait ~4 s for download) -> `elements` -> tap **Save Video** / **Save Image**.
  Lands as the newest item in Photos (bottom-right of Library). Drive's sheets ARE readable
  via `elements`; Drive's grid needs pixel taps from a screenshot.

## Docs
- Read docs/LESSONS.md before debugging connection/WDA issues; docs/scaling/ for multi-phone work.
