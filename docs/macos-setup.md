# iphctrl on macOS — personal setup notes (2026-10-28)

Notes from getting iphctrl (written for Windows, see [../README.md](../README.md))
working on a MacBook for one personally-connected iPhone. Everything here was
verified on that machine unless noted.

## What's different from the Windows README
- No "Apple Mobile Device Service" needed — macOS has usbmuxd built in.
- No AltServer/winget signing flow needed for basic app launch/screenshot
  (that's only required for WebDriverAgent-based tap/swipe/type).
- Everything installs via `uv sync` the same way.

## The blocker that cost the most time
Phone showed as charging but never appeared in Finder, `system_profiler`,
or `pymobiledevice3 usbmux list` (always empty), despite correct cable,
correct port, and Trust already tapped.

**Root cause:** macOS Settings → Privacy & Security → **Accessories**
("Allow accessories to connect") was not set to allow this device.
Once set to **Automatically** (or the device approved there), the phone
showed up immediately.

## Working setup steps (macOS)
```bash
# one-time
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/jpkrajewski/iphctrl.git
cd iphctrl
uv sync

# check connection
uv run iphctrl devices
uv run pymobiledevice3 lockdown info          # quick, no DDI needed
uv run pymobiledevice3 amfi developer-mode-status

# mount developer disk image (needed once per phone reboot)
# iphctrl's own `info`/auto-mount path hung indefinitely for me —
# calling pymobiledevice3 directly worked and gave visible success/failure:
uv run pymobiledevice3 mounter auto-mount

# now app control works
uv run iphctrl apps instagram        # find bundle id
uv run iphctrl launch instagram      # launches it (DVT process control, no WDA needed)
uv run iphctrl screenshot            # saves to shots/
```

## Not set up (stopped here)
Tap/swipe/scroll via WebDriverAgent — needs Xcode with an Apple ID added
under Settings → Accounts, then building/signing WebDriverAgentRunner and
installing it on the phone. See [scaling/mac.md](scaling/mac.md) for that
route. Not completed in this session.
