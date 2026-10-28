# READTHIS — running the iPhone farm (findings)

The plan for the phone-farm machine: what repo, what it uses, how to start it,
and how to grow 0 → 1 → 5 phones, MacBook → Mac mini, and what the Apple
accounts actually cost.

## The repo

**Git-Agni/prod-FARM-IOS-Core** — <https://github.com/Git-Agni/prod-FARM-IOS-Core>

Open-source phone farm: drives physical iPhones from a local dashboard with a
PostgreSQL scheduler and a built-in TikTok plugin. Engineering writeup:
gethandler.ai/tiktok-iphone-farm

### What it uses

| Layer | What | Notes |
|---|---|---|
| Language/runtime | Node 22+, TypeScript via tsx | No build step for the server |
| Dashboard/API | Fastify + server-rendered HTMX, MJPEG live screen | Loopback by default; refuses non-loopback bind without an auth plugin |
| Database | PostgreSQL 14+ with pg-boss job queues | One queue per device |
| Device control | Appium 3 + XCUITest driver + patched appium-webdriveragent 8.9.1 | No pymobiledevice3 — everything USB goes through Xcode's toolchain |
| Signing | `xcodebuild build-for-testing`, automatic signing (`XCODE_ORG_ID`) | Needs the Mac's login keychain unlocked → run from a graphical session |
| Live video | WDA's built-in MJPEG server on phone port 9100, USB-forwarded to host 9100+n | `<img>` renders it; dashboard grid uses polled stills instead |
| Scheduling | Versioned task envelopes: `pluginId + taskType + taskVersion + JSON payload` | Old schedules fail loudly instead of running changed logic |

### How to start it

Requirements: macOS + full Xcode (App Store, not just CLT), Node 22+,
PostgreSQL 14+, an iPhone (Developer Mode on, trusted), an Apple team.

```bash
git clone https://github.com/Git-Agni/prod-FARM-IOS-Core.git phone-farm
cd phone-farm
npm install
npm run appium:install-driver     # XCUITest driver into ./.appium2

cp .env.example .env              # fill in XCODE_ORG_ID, WDA_BUNDLE_ID,
                                  # IOS_PLATFORM_VERSION, DATABASE_URL, POSTGRES_PASSWORD

npm run db:up                     # bundled Postgres (or your own)
npm run db:migrate
npm run wda:prepare               # patch + build + sign WDA (phone plugged in!)
                                  # -- --udid <udid> for one phone, -- --all for bulk

# four long-lived processes (launchd/systemd units for always-on):
npm run appium                    # Appium :4725
npm run wda:service               # per-device WDA supervisor (:8100+/:9100+, socket .wda/)
npm run worker                    # scheduler worker
npm run web                       # dashboard http://127.0.0.1:3000
```

Then open the dashboard → **Register device** → step through the wizard's
checks (Xcode selected → device on usbmux → signing identity → DDI mounted →
WDA reachable). Each check probes one link and tells you which is broken.

**Why touch requires all this:** iOS only accepts injected touches from a
process with the private XCTest entitlement — Apple's `testmanagerd` daemon.
WDA is the standard prebuilt XCUITest bundle with an HTTP server. There is no
non-jailbreak alternative for tap/swipe/type; everything else (launch, kill,
screenshots, syslog) can be done signing-free via pymobiledevice3, like iphctrl
does.

## 0 → 1 phone (bring-up, one afternoon)

1. **Xcode preflight:** install full Xcode, accept license, `xcode-select -p`
   must print Xcode.app. Add Apple ID under Xcode → Settings → Accounts, note
   the Team ID → `XCODE_ORG_ID`.
2. **Phone:** USB cable, unlock, tap **Trust**, enable Developer Mode
   (Settings → Privacy & Security → restart → confirm).
3. **Mac gotcha that costs hours:** phone charges but never shows in Finder /
   `xcrun xctrace list devices` / `usbmux list` → System Settings → Privacy &
   Security → **Accessories** → allow the device (or set Automatic).
4. `npm install` … four processes (above).
5. **Gotcha two:** `wda:prepare` signs with the login keychain, which only
   unlocks in a graphical session. Over SSH it dies with
   `errSecInternalComponent` unless you run `security unlock-keychain` +
   `security set-key-partition-list` first. Just run it from Terminal while
   logged in.
6. Verify: `xcrun xctrace list devices` (phone under "Devices"), WDA
   `http://127.0.0.1:8100/status` answers, dashboard :3000 loads, live screen
   streams on the device page.

## 1 → 5 phones

- **USB is the wall, not CPU.** Each iPhone eats several USB endpoints per
  controller; controllers run out around 4–6 phones. A MacBook's 2–3 ports sit
  on 1–2 controllers → realistic MacBook ceiling ~4–6 phones.
- **Hubs must be powered** (own PSU, ≥ 1 A per phone). Bus-powered hubs brown
  out and phones drop off usbmux at random.
- **Cables:** short, data-capable, MFi. Charge-only cables are the #1
  "phone not detected."
- **Signing forces the paid account at phone #2** (see below). Paid team also
  gives 1-year signatures — no weekly re-signing chore.
- **Per phone:** run the per-phone checklist (Auto-Lock Never, Low Power off,
  DND on, Developer Mode on, Trust, approve in Mac's Accessories).
  Register in the wizard, then `npm run wda:prepare -- --udid <udid>`.
  `devices.json` assigns per-device ports (`wdaLocalPort: 8100+n`,
  `mjpegLocalPort: 9100+n`).
- **Bring-up method:** add one at a time; after each, the device count in
  `xcrun xctrace list devices` must go up by one and stay up. Then soak: all
  phones plugged in, poll every minute for an hour. Any vanisher = cable, port,
  or a phone setting. That soak finds your real per-Mac number — write it down.

## MacBook → Mac mini

The MacBook is a bad farm host (lid sleep, thermals, battery on 24/7 duty,
few USB controllers) and a great console. The Mac mini is the appliance.

- A Mac mini **is a full Mac** — same macOS, same Xcode — just no screen or
  keyboard in the box.
- **Setup:** plug any monitor/TV + keyboard for ~20 min of first-boot setup,
  install Xcode, then unplug everything and shelve it with the phones.
- **Remote control from the MacBook:** Screen Sharing (System Settings →
  Sharing → Screen Sharing) gives you the mini's screen in a window; Remote
  Login (SSH) for commands.
- **Two settings that make it survive power cuts:** Users → **automatic
  login ON** (requires FileVault off — the login keychain must be unlocked for
  signing, and that only happens in an active graphical session) and Energy →
  prevent automatic sleeping.
- **Dashboard from the MacBook:** simplest is an SSH tunnel,
  `ssh -L 3000:localhost:3000 <mini>`, then open `localhost:3000`. Binding the
  dashboard to the LAN directly requires an auth plugin
  (`PHONE_FARM_AUTH_PLUGIN`) — the app refuses a non-loopback bind without one.
- **Hardware:** CPU is not the wall, so a used M1/M2 mini (~$300) runs 10
  phones fine. Plan 10–15 per mini, spread across powered hubs on different
  ports/controllers; measure your real number with the soak test.
- **End state:** MacBook = daily machine + farm console; Mac mini = headless
  24/7 box holding the phones.

## Accounts, logins, costs, capacity — the real math

| Item | Free Apple ID | Paid Apple Developer Program |
|---|---|---|
| Price | $0 | **$99/yr** |
| Devices for signing | **1** (device list expires weekly) | **100 registered per year** |
| Signature lifetime | 7 days (re-sign by hand weekly) | 1 year |
| Sideloaded apps per device | 3 (WDA = 1) | n/a (proper development install) |
| App IDs | 10 per week | not a practical limit |
| Xcode login | Apple ID + 2FA in Xcode → Settings → Accounts, must be a graphical session (login keychain) | same |

**Operating costs beyond Apple:**
- Mac mini: ~$300 used M1/M2, ~$600 new M4.
- Powered hubs with ≥ 1 A/port: ~$30–60 each.
- Short MFi data cables: ~$10 each, buy spares.
- Phone shelf + labels (UDID → phone → cable → port).

**Capacity summary:**
- MacBook: **4–6 phones** (USB controller bound), single free Apple ID is fine
  for exactly 1, paid account from phone 2 up.
- Mac mini: **10–15 planned, more measured** — the per-controller limit is
  unknown until your soak test says so.
- The binding limit across everything is **Apple's 100-device-per-year
  registration**, not the hardware.
