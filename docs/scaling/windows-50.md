# Scaling to ~50 phones on Windows

Read [10-phones.md](10-phones.md) first; this is what changes past 10.

## Topology: several hosts, not one giant PC
Plan **10–15 phones per Windows host** and scale out by adding hosts (5 hosts × 10 phones).
Why, rather than one PC with 50:
- **USB controller resources**: Windows xHCI controllers have a fixed endpoint budget, and every iPhone uses several endpoints. Past ~10–15 phones per host you need more independent controllers (PCIe cards **with one controller per port group**, e.g. 4-controller USB 3 cards; most cheap cards share one controller). *Expected*; measure per board.
- **AMDS is one service per host.** When it hangs, every phone on that host is gone until it restarts. Smaller hosts limit the blast radius.
- **WDA processes**: each phone runs its own runner + `serve` process; 50 on one machine is CPU/RAM-heavy during startup storms.
- One dead host = 10 phones down, not 50.

Hosts can be cheap mini PCs (Intel N100-class with 16 GB RAM) *if* they have at least 2 independent USB controllers; otherwise use desktops with PCIe slots. *Expected*

## Per-host hardware (×5)
- 2 × 10-port powered hubs, each on a **different controller**, PSU sized at ≥ 1 A per phone.
- 10 data cables + spares, labels, shelf with airflow.
- Wired Ethernet (WDA traffic is local USB; the network is for your control plane and the apps).
- Optional: smart PDU / smart plugs to power-cycle hubs.

## Signing at 50 phones
**Pay for the Apple Developer Program ($99/yr).** Free accounts don't scale here:
- AltServer re-sign is manual, per phone, every 7 days (50 phones = an hour a week of clicking).
- Free accounts: 10 App IDs per 7 days, 3 sideloaded apps per device, device caps per account.
With a paid team: register 50 UDIDs (limit 100 iPhones per membership year), create one
development certificate + one provisioning profile listing all UDIDs, sign WDA once, and push
it to every phone with `pymobiledevice3 apps install`. Valid one year. *Expected*

Signing on Windows with a paid account doesn't need Xcode: create the certificate (CSR from
OpenSSL) and the profile on developer.apple.com, then sign with
[`rcodesign`](https://github.com/indygreg/apple-platform-rs) (open source). *Expected*. On a Mac it's simpler (see mac.md).

## Control plane
Each host runs the `fleet` supervisor (see 10-phones.md §6). Add a small HTTP API per host
(list phones, send a command, fetch the last screenshot) so one dashboard or agent can drive
all 5 hosts. Keep phone state (UDID → host, account, passcode) in one inventory (a DB or `phones.csv` per host).

## Windows-specific hardening
- USB selective suspend **off**; hub power management **off** (10-phones.md §2).
- Windows Update: active hours / pause driver updates. A driver update can rebind the Apple USB driver. *Expected*
- Run each host's supervisor as a scheduled task at boot (user logged in or not), with auto-restart.
- AMDS watchdog: if `usbmux list` is empty while Device Manager shows Apple devices, restart AMDS (needs admin, so run the watchdog as SYSTEM). If that doesn't help, it's the phones (lesson 1 in LESSONS.md).
- Exclude the repo and `shots/` from Defender real-time scanning (thousands of screenshots). *Expected*

## Biggest risks at 50
1. Phones dropping off USB (power, cables, locking). The fix is hygiene, plus a health check that alerts.
2. WDA signature expiry (free accounts) or trust being revoked after iOS updates.
3. Coordinate drift across models and iOS versions: standardize on **one model + one iOS version** per fleet if at all possible.
4. Apps' anti-automation and account checks: out of scope for the transport layer.
