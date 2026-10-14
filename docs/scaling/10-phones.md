# 10 iPhones on one Windows PC by cable

Goal: 10 phones plugged in permanently, each one controllable by `iphctrl`, with no
babysitting except the weekly re-sign (free Apple ID) or never (paid account).

## 1. Hardware
| Item | Why / spec | Status |
|---|---|---|
| **Powered USB hub with its own power supply**, 10+ ports, USB 3.x upstream | Phones charge while plugged in. The PSU must deliver ~1 A per phone sustained (≥ 10–12 A total, i.e. 60 W+ for 10 phones). An unpowered hub browns out phones → they drop off usbmux. | Expected |
| Better: **two hubs on two different USB controllers** (e.g. one on a motherboard port, one on a PCIe USB card) | Each iPhone is a composite device with several endpoints. Windows' xHCI controllers run out of endpoint resources (Device Manager: "not enough USB controller resources") before bandwidth is the limit. 5 phones per controller is comfortable. | Expected; the per-controller limit is **Unknown** for your board, so measure it (step 4) |
| **Short, data-capable cables** (USB-A/C to Lightning or USB-C, ≤ 1 m, MFi/Apple) | Charge-only or worn cables are the #1 "phone not detected" cause. Buy 12 (2 spares). | Expected |
| Labels | UDID → phone → cable → hub port. You will need this when one misbehaves. | — |
| Shelf / rack with airflow | 10 phones, screens on 24/7 and charging, get warm; heat throttles and ages batteries. | Expected |
| Optional: smart plug on the hub PSU | Power-cycle the whole hub remotely. | Expected |

PC: any modern Windows 11 desktop is enough. Each phone's `serve` process uses little CPU;
screenshots are ~1–2 MB PNG each. 16 GB RAM is plenty for 10.

## 2. Software (once per PC) — Verified on one phone
1. Apple Mobile Device Service: install **iTunes** (non-Store, or the "Apple Mobile Device Support" MSI).
   `Get-Service 'Apple Mobile Device Service'` → Running, Startup Automatic.
2. `uv` + this repo: `uv sync` in `iphctrl`.
3. AltServer + **iCloud for Windows** (Microsoft Store) for free-account signing.
4. **Remove anything else that grabs phones**: AutoViral driver (`autoviral-driver disable`, admin), 3uTools, iMazing services, etc.
5. Windows power settings: Control Panel → Power Options → change plan → advanced →
   **USB selective suspend: Disabled**. Otherwise Windows powers idle hub ports down. *Expected*
6. Device Manager → each "USB Root Hub" / hub → Power Management → untick "Allow the computer to turn off this device". *Expected*

## 3. Phones
Run [phone-checklist.md](phone-checklist.md) on each phone **one at a time** with only that phone plugged in. Then build the inventory:

```
phones.csv
name,udid,model,ios,hub,port,apple_id,passcode
p01,00008110-001948C43A84401E,iPhone14,5,26.5,A,1,team1,******
```
Keep `phones.csv` out of git (passcodes). `.gitignore` it.

## 4. Bring-up: add phones one by one
Plug in phone 1, confirm `uv run iphctrl devices` lists it, then phone 2, and so on. After each one:
- `uv run iphctrl devices`: the count must go up by one.
- Device Manager: no yellow "!" and no "not enough USB controller resources".
- When a phone fails to appear, move it to the other hub/controller. **That's how you find your per-controller limit.** Write it down.

Then a soak test: all 10 plugged in, `devices` every minute for an hour. Any phone that drops
is a cable, a port, or a phone setting (Auto-Lock, Low Power Mode). Fix it before going further.

## 5. Signing WDA for 10 phones
| Option | Effort | Status |
|---|---|---|
| **Free Apple ID + AltServer**, Shift+click → Sideload .ipa per phone | ~1 min per phone **every 7 days**. Limits per free account: 3 sideloaded apps per device, **10 new App IDs per 7 days**. One WDA = 1 App ID per account, so one account can serve all 10 phones' WDA. The exact device cap per free account is **Unknown**; if AltServer refuses a phone, use a second free Apple ID. | Verified for 1 phone |
| **Paid Apple Developer Program** ($99/yr) | Register the 10 UDIDs once; sign WDA once with the distribution-free *development* profile; valid **1 year**; install to all phones with `pymobiledevice3 apps install`. | Expected |

At 10 phones, free is workable (10 minutes a week). Past ~20, pay.

## 6. Code changes needed for 10 phones (not done yet)
Today `serve` drives one phone and uses a single `cmd/` folder. For 10:
1. `python -m iphctrl.serve --udid <UDID>` → command folder `cmd/<name>/`, screenshots `shots/<name>/`.
2. A supervisor (`iphctrl fleet up`) that reads `phones.csv`, starts one `serve` per phone, and restarts it when it exits (phone unplugged / WDA crashed).
3. `IPHCTRL_PASSCODE` per phone from `phones.csv`.
4. Keypad / coordinate constants per model (they're measured for iPhone 13 only).
5. Health check: per phone, every N minutes: usbmux visible, screenshot not black, WDA `/status` OK → a status table.
6. Stagger work: never start 10 WDA sessions in the same second (each runner launch is heavy on the phone and on AMDS). *Expected*

## 7. Daily operations
- Morning: `fleet status`. Black screenshot = locked or asleep → `unlock`. Missing = cable / hub / reboot.
- Weekly (free account): re-sideload WDA on each phone before day 7.
- After an iOS update on any phone: re-check Developer Mode, DDI mount (automatic), WDA trust.
