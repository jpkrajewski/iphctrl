# Per-phone checklist

Do this for every phone before it joins the rack. About 10 minutes per phone by hand.
Status: **Verified** on the iPhone 13 unless marked.

## On the phone
- [ ] iOS **17.4 or newer**. The no-admin userspace tunnel needs it; 17.0–17.3 need the admin `tunneld`.
- [ ] Signed in to the Apple ID you'll use for that phone's apps (optional for control itself).
- [ ] **Passcode**: either off, or a known passcode stored as `IPHCTRL_PASSCODE` (per phone once multi-phone code exists).
      Off is simplest: no USB data restriction, no keypad taps.
- [ ] Settings → Battery → **Low Power Mode OFF**.
- [ ] Settings → Display & Brightness → Auto-Lock → **Never** (check it says Never; it's greyed out while Low Power Mode is on).
- [ ] Settings → Face ID & Passcode → **Accessories ON** (only matters with a passcode).
- [ ] Settings → Privacy & Security → **Developer Mode ON** → restart → confirm "Turn On".
      Toggle missing: `uv run pymobiledevice3 amfi reveal-developer-mode --udid <UDID>`.
- [ ] **Focus / Do Not Disturb ON**, all day, so banners don't cover the UI.
- [ ] Settings → General → Software Update → Automatic Updates **OFF** (an update reboot unmounts the DDI and breaks WDA trust). *Expected*
- [ ] Brightness low, True Tone and Night Shift off (saves heat; screenshots stay consistent). *Expected*

## Over the cable
- [ ] Plug in, unlock, **Trust**, enter the passcode.
- [ ] `uv run iphctrl devices` lists its UDID. Write the UDID on a label on the phone and its cable.
- [ ] `uv run iphctrl --udid <UDID> info`: model + iOS recorded in the inventory (see `phones.csv` in 10-phones.md).
- [ ] Install WDA (AltServer: Shift+click → Sideload .ipa) → on the phone, VPN & Device Management → Trust.
- [ ] `uv run iphctrl --udid <UDID> elements` returns home-screen icons. The phone is ready.

## After a phone reboot
Unlock once by hand if it has a passcode ("Before First Unlock" blocks everything), then
run any `iphctrl` command; the Developer Disk Image is remounted automatically.
