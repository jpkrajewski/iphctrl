# Scaling on macOS (fewest problems)

If you can choose, run the phones from Macs. Same `iphctrl` code, fewer moving parts.

## Why Mac is easier
| Problem on Windows | On Mac |
|---|---|
| AMDS (iTunes service) must be installed and can hang | `usbmuxd` is built into macOS. *Expected* |
| WDA signing needs AltServer + iCloud for Windows, one phone at a time, by hand | **Xcode** builds and signs WDA for every connected phone: `xcodebuild -project WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination id=<UDID> test`. Xcode manages certificates and profiles. *Expected* |
| Free account: 7-day re-sign by hand | Still 7 days with a free account, but re-signing is one scripted `xcodebuild build-for-testing` + install loop. *Expected* |
| Bulk phone setup by hand | **Apple Configurator** (free, Mac only): prepare/supervise phones, apply profiles, install apps to many phones at once over USB. *Expected* |
| iOS 17.0–17.3 tunnel needs admin + wintun | `sudo pymobiledevice3 remote tunneld`: one daemon serves tunnels for all phones. *Expected* |

## Hardware
- **Mac mini (Apple silicon)**. Plan 10–15 phones per Mini to start and measure; Apple silicon
  USB/Thunderbolt controllers are generally more tolerant than consumer Windows boards,
  but the per-Mac phone limit is **Unknown** until tested.
- **Powered hubs** as in 10-phones.md (≥ 1 A per phone). Thunderbolt docks with many USB ports
  also give additional controllers. *Expected*
- Keep each Mini headless with the screen locked; set "Prevent automatic sleeping" (Energy settings) and auto-login + start the supervisor at login (launchd). *Expected*

## Setup per Mac
1. Install Xcode (App Store) → `sudo xcodebuild -license accept` → open Xcode once.
2. Xcode → Settings → Accounts → add the Apple ID (free or paid team).
3. `brew install uv`; clone the repo; `uv sync`.
4. Clone appium/WebDriverAgent; in Xcode set the WebDriverAgentRunner target's team and a unique bundle id.
5. For each phone: plug in → Trust → Developer Mode → `xcodebuild ... -destination id=<UDID> test`
   once (installs and trusts WDA; on the phone, trust the developer once).
6. Run the phone checklist (phone-checklist.md). Apple Configurator can do the Wi-Fi /
   restriction profiles in bulk. Auto-Lock and Low Power Mode are still set per phone by hand
   or via `iphctrl` (no profile setting forces Auto-Lock to Never).

## Signing strategy
- ≤ 10 phones: a free Apple ID per Mac, re-sign weekly with a script (`xcodebuild build-for-testing` once, then `test-without-building -destination id=<UDID>` per phone).
- More: paid team ($99/yr, 100 iPhones). Xcode "Automatically manage signing" registers each UDID when you build to it. One year validity.

## Code notes
- `Phone()` already works on macOS (pymobiledevice3 is cross-platform; the userspace tunnel needs no sudo).
- At fleet size prefer `tunneld` (one sudo daemon) over one userspace tunnel per process: less CPU, and the phones' tunnels survive `serve` restarts. That needs a `--tunnel` option in `Phone` (not implemented yet).
- The rest (supervisor, per-phone `serve`, inventory, health checks) is identical to Windows (10-phones.md §6).

## Recommended path
1. Prove 10 phones on the **current Windows PC** (10-phones.md); it's mostly hardware and hygiene.
2. Move phone 11+ to a **Mac mini** with a paid developer account.
3. Grow by adding Minis of 10–15 phones each.
