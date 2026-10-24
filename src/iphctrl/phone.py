"""One iPhone over USB, through pymobiledevice3.

    async with Phone() as phone:          # first USB iPhone, or Phone(udid)
        await phone.screenshot("shot.png")
        await phone.launch("snapchat")

Opening a Phone:
1. connects to lockdownd through Apple Mobile Device Service (usbmux),
2. mounts the Developer Disk Image if it is not mounted (iOS 17+: personalized,
   downloaded and signed on the fly),
3. uses the kernel tunnel from `pymobiledevice3 remote tunneld` (admin, started
   by start.ps1) when it runs; otherwise opens an RSD tunnel in-process with
   pymobiledevice3's userspace TCP stack (no admin, but drops more easily),
4. opens the DVT (Instruments) channel used for screenshots and app launch.

Only one Phone may be open per process (the userspace stack is a process-wide
singleton).
"""

from pathlib import Path
from typing import Any, Self

from pymobiledevice3.exceptions import AlreadyMountedError, TunneldConnectionError
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.process_control import ProcessControl
from pymobiledevice3.services.dvt.instruments.screenshot import Screenshot
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.services.mobile_image_mounter import auto_mount
from pymobiledevice3.tunneld.api import get_tunneld_device_by_udid
from pymobiledevice3.usbmux import list_devices

from iphctrl.apps import resolve_bundle
from iphctrl.ui import RUNNER_MARK, Ui


async def usb_devices() -> list[str]:
    """UDIDs of iPhones on USB that Apple Mobile Device Service can see."""
    return [d.serial for d in await list_devices() if d.connection_type == "USB"]


class Phone:
    def __init__(self, udid: str | None = None) -> None:
        self.udid = udid
        self.lockdown: Any = None
        self._tunnel: UserspaceRsdTunnel | None = None
        self._rsd: Any = None
        self._dvt: DvtProvider | None = None
        self._ui: Ui | None = None

    async def __aenter__(self) -> Self:
        self.lockdown = await create_using_usbmux(serial=self.udid)
        self.udid = self.lockdown.udid
        try:
            await auto_mount(self.lockdown)
        except AlreadyMountedError:
            pass
        self._rsd = await self._kernel_tunnel()
        if self._rsd is None:
            self._tunnel = UserspaceRsdTunnel(serial=self.udid)
            self._rsd = await self._tunnel.aopen()
        self._dvt = DvtProvider(self._rsd)
        await self._dvt.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ui:
            await self._ui.close()
        if self._dvt:
            await self._dvt.__aexit__(*exc)
        if self._tunnel:
            await self._tunnel.aclose()
        elif self._rsd:
            await self._rsd.close()
        if self.lockdown:
            await self.lockdown.close()

    async def _kernel_tunnel(self) -> Any:
        try:
            return await get_tunneld_device_by_udid(self.lockdown.udid)
        except TunneldConnectionError:  # tunneld not running
            return None

    @property
    def tunnel(self) -> str:
        return "userspace" if self._tunnel else "kernel"

    @property
    def dvt(self) -> DvtProvider:
        if self._dvt is None:
            raise RuntimeError("Phone is not open - use 'async with Phone()'")
        return self._dvt

    # -- info -------------------------------------------------------------------
    def info(self) -> dict[str, Any]:
        v = self.lockdown.all_values
        keys = (
            "DeviceName",
            "ProductType",
            "ProductVersion",
            "BuildVersion",
            "UniqueDeviceID",
        )
        return {k: v.get(k) for k in keys}

    async def apps(self) -> dict[str, str]:
        """User-installed apps: bundle id -> display name."""
        apps = await InstallationProxyService(self.lockdown).get_apps(
            application_type="User"
        )
        return {
            b: a.get("CFBundleDisplayName") or a.get("CFBundleName", b)
            for b, a in apps.items()
        }

    # -- touch (WebDriverAgent) ------------------------------------------------------
    async def ui(self) -> Ui:
        """Starts WebDriverAgent once per Phone and returns the touch/keyboard API."""
        if self._ui is None:
            runner = next((b for b in await self.apps() if RUNNER_MARK in b), None)
            if runner is None:
                raise RuntimeError(
                    "WebDriverAgent is not installed - see README 'WebDriverAgent'"
                )
            width = int.from_bytes((await self._png())[16:20], "big")  # PNG IHDR width
            self._ui = await Ui.start(self.lockdown, self._rsd, runner, width)
        return self._ui

    # -- screen -----------------------------------------------------------------
    async def _png(self) -> bytes:
        async with Screenshot(self.dvt) as shot:
            return await shot.get_screenshot()

    async def screenshot(self, path: str | Path) -> Path:
        png = await self._png()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(png)
        return out

    # -- apps -------------------------------------------------------------------
    async def launch(self, app: str, kill_existing: bool = False) -> int:
        """Brings an app to the front; `app` is a bundle id or an alias (apps.py). Returns its pid."""
        async with ProcessControl(self.dvt) as pc:
            return await pc.launch(
                bundle_id=resolve_bundle(app), kill_existing=kill_existing
            )

    async def kill(self, app: str) -> None:
        async with ProcessControl(self.dvt) as pc:
            pid = await pc.process_identifier_for_bundle_identifier(resolve_bundle(app))
            if pid:
                await pc.kill(pid)
