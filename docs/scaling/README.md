# Scaling iphctrl to many phones by cable

| Doc | For |
|---|---|
| [10-phones.md](10-phones.md) | **Start here.** Exact shopping list and steps to put 10 iPhones on one PC by cable. |
| [windows-50.md](windows-50.md) | Growing to ~50 phones on Windows: hosts, USB controllers, signing, operations. |
| [mac.md](mac.md) | The same on macOS, the path with the fewest problems. |
| [phone-checklist.md](phone-checklist.md) | Per-phone setup you repeat for every device. |

## The short version
- **Signing is the real bottleneck, not USB.** A free Apple ID gives a 7-day WDA signature and AltServer signs one phone at a time by hand. For more than a handful of phones, pay for the **Apple Developer Program ($99/yr)**: 1-year signatures, up to 100 iPhones per year, scriptable.
- **USB controllers matter more than ports.** A phone uses several USB endpoints; one controller runs out of resources long before a 20-port hub is full. Spread phones across **several independent controllers**.
- **One process per phone.** pymobiledevice3's userspace tunnel is one per process, and WDA sessions are per device. Today's code drives one phone per `serve` process; see "Code changes" in each doc.
- **Mac is easier than Windows** for this: native usbmuxd, Xcode builds and signs WDA for every phone in one command, and Apple Configurator handles bulk setup. Windows works; it just needs more workarounds.

## Status labels used in these docs
- **Verified**: done on our iPhone 13 / Windows 11 setup.
- **Expected**: standard practice or vendor documentation, not yet tested here.
- **Unknown**: has to be measured on your hardware.
