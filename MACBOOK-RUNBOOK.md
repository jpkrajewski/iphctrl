# MacBook bring-up runbook — prod-FARM-IOS-Core

Execute top to bottom. Steps marked **HUMAN** need the user's hands or eyes —
stop, say what you need, wait. Every step has a verify: do not continue past a
failed verify. Context and reasons: READTHIS.MD.

Target: one iPhone farm running on this MacBook — appium + wda:service +
worker + web, phone registered, live screen in the dashboard.

---

## Phase 0 — before you start (HUMAN, the evening before)

- [ ] Start the **Xcode download from the App Store** — it's 20+ GB, takes a while.
- [ ] Have ready: the MacBook logged into a graphical desktop (signing needs
      the login keychain — a bare SSH session will fail), Apple ID email +
      password + a trusted device for 2FA, the iPhone, a known-good data
      cable, the iPhone's passcode.

## Phase 1 — machine preflight

```bash
sw_vers                                  # verify macOS
xcode-select -p                          # must print /Applications/Xcode.app/Contents/Developer
```

- If it prints `/Library/Developer/CommandLineTools` or nothing → **HUMAN:**
  install Xcode from the App Store, open it once. Then:

```bash
sudo xcodebuild -license accept
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
xcodebuild -runFirstLaunch
xcode-select -p                          # VERIFY: ends with Xcode.app/Contents/Developer
```

- If Homebrew is missing (`command -v brew` empty) → **HUMAN runs:**
  `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
  (needs the MacBook admin password). Then:

```bash
brew install node@22 git tmux
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"   # add to ~/.zshrc too
node --version                           # VERIFY: v22.x
git --version
```

## Phase 2 — Apple ID in Xcode (HUMAN) + extract Team ID (you)

- [ ] **HUMAN:** Xcode → Settings → Accounts → `+` → Apple ID → sign in (2FA) →
      select the team. A free personal team is enough for ONE phone today.

```bash
security find-identity -v -p codesigning   # VERIFY: "Apple Development: <name> (<TEAMID>)"
```

Record `TEAMID` — that's `XCODE_ORG_ID`. If the list is empty → Apple ID step
didn't stick, go back.

## Phase 3 — phone pairing

- [ ] **HUMAN:** plug the iPhone in, unlock it, tap **Trust**, enter passcode.

```bash
xcrun xctrace list devices               # VERIFY: iPhone listed under "Devices" (not Offline)
system_profiler SPUSBDataType | grep -B2 -A8 -i iphone   # shows on USB
```

- Phone charges but `xctrace` shows nothing → **HUMAN:** System Settings →
  Privacy & Security → **Accessories** → approve the iPhone (or set Automatic).
  This is the #1 time-waster — see READTHIS.MD.
- [ ] **HUMAN:** on the iPhone: Settings → Privacy & Security → **Developer
      Mode** → on → restart → confirm "Turn On". (If the toggle is missing, it
      appears a minute after the first Xcode pair.)

```bash
xcrun devicectl list devices             # note the UDID and the OS version
```

Record: `UDID`, `IOS_VERSION` (e.g. `26.5`).

## Phase 4 — repo + database

```bash
cd ~
git clone https://github.com/Git-Agni/prod-FARM-IOS-Core.git phone-farm
cd phone-farm
npm install
npm run appium:install-driver            # XCUITest driver into ./.appium2

brew install postgresql@16
brew services start postgresql@16
psql postgres \
  -c "CREATE ROLE phone_farm LOGIN PASSWORD 'farm' CREATEDB;" \
  -c "CREATE DATABASE phone_farm OWNER phone_farm;"

cp .env.example .env
```

Edit `.env` (agent does this with the recorded values):

| Key | Value |
|---|---|
| `IOS_PLATFORM_VERSION` | the OS version from Phase 3 (e.g. `26.5`) |
| `XCODE_ORG_ID` | `TEAMID` from Phase 2 |
| `WDA_BUNDLE_ID` | pick one, e.g. `com.jakub.farm.WebDriverAgentRunner` |
| `DATABASE_URL` | `postgresql://phone_farm:farm@127.0.0.1:5432/phone_farm` |
| `POSTGRES_PASSWORD` | `farm` |

```bash
npm run db:migrate                       # VERIFY: migrations apply cleanly
```

## Phase 5 — build + sign WDA

Must run in the MacBook's graphical session (Terminal/iTerm — fine; SSH without
keychain unlock — not fine).

```bash
cd ~/phone-farm
npm run wda:prepare -- --udid <UDID>     # VERIFY: ends "** TEST BUILD SUCCEEDED **"
```

- Fails with `errSecInternalComponent` → keychain locked. Either run from the
  MacBook's own terminal, or **HUMAN** runs:
  `security unlock-keychain ~/Library/Keychains/login.keychain-db` and
  `security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k <login-pw> ~/Library/Keychains/login.keychain-db`
- Stale/corrupt build → delete `~/Library/Developer/Xcode/DerivedData/WebDriverAgent-*` and re-run.

## Phase 6 — start the four processes

```bash
cd ~/phone-farm
mkdir -p logs
tmux new -d -s appium  'npm run appium      2>&1 | tee logs/appium.log'
tmux new -d -s wda     'npm run wda:service 2>&1 | tee logs/wda.log'
tmux new -d -s worker  'npm run worker      2>&1 | tee logs/worker.log'
tmux new -d -s web     'npm run web         2>&1 | tee logs/web.log'
tmux ls                                  # VERIFY: 4 sessions
```

Give wda:service ~60 s to launch WDA, then:

```bash
curl -s http://127.0.0.1:4725/status | head -c 200        # VERIFY: appium up
curl -s http://127.0.0.1:8100/status | head -c 200        # VERIFY: WDA up on the phone port
curl -s --unix-socket .wda/wda-service.sock http://x/health   # VERIFY: per-device state "ready"
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/   # VERIFY: 200 or redirect
```

Not ready? Read the matching log (`tmux attach -t wda`, or `logs/*.log`):
`unlock-required` = **HUMAN** unlocks the phone once; `Appium unavailable` =
appium session died, reattach; `wda: error … stale` = re-run Phase 5.

## Phase 7 — register the device

- [ ] **HUMAN + agent:** open `http://127.0.0.1:3000` in a browser on the
      MacBook → **Register device** → step through the checks. Each check names
      the exact broken link (Xcode / usbmux / signing / DDI / WDA) — fix and
      re-check.
- [ ] **HUMAN:** when asked, enter the iPhone's passcode (stored in
      `devices.json`, `0600`, never returned by the API).

## Phase 8 — acceptance test

On the device page in the dashboard: live MJPEG screen renders, remote
tap/swipe works. Then from the shell:

```bash
curl -s http://127.0.0.1:8100/wda/locked          # false
curl -s -X POST http://127.0.0.1:8100/wda/homescreen   # home screen, no error
```

Schedule the built-in TikTok `doomscroll` task "now" from the device page;
**Activity** shows a running execution with logs. Done.

---

## If a tmux session dies later

```bash
tmux new -d -s <name> 'cd ~/phone-farm && npm run <script> 2>&1 | tee -a logs/<name>.log'
```

## Tomorrow's known unknowns

- **Free team = 1 device.** Phone #2 needs the paid Apple Developer Program
  ($99/yr) — buy it before scaling, not after. READTHIS.MD has the table.
- Xcode's first launch downloads the phone's Developer Disk Image in the
  background ("Preparing" in Devices and Simulators) — registration's DDI check
  passes on its own once that finishes; give it a minute.
- Keep the iPhone unlocked and on the "Never" auto-lock setting while testing,
  or it drops off USB when the screen locks.
