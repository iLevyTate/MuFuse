"""BLE scan for nearby Muse headbands and firmware query (no OS pairing needed)."""

from __future__ import annotations

import asyncio
import contextlib

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.exc import BleakError

from mufuse.acquisition.muse_control import (
    CONTROL_UUID,
    VERSION_COMMAND,
    DeviceInfoError,
    encode_command,
    parse_device_info,
    payload_text,
    reply_complete,
)
from mufuse.acquisition.types import FoundDevice

__all__ = ["FoundDevice", "read_device_info", "scan_for_muse"]

REPLY_TIMEOUT_S = 3.0


def scan_for_muse(timeout_s: float = 8.0) -> list[FoundDevice]:
    """Return Muse devices sorted strongest signal first."""
    return asyncio.run(_scan(timeout_s))


async def _scan(timeout_s: float) -> list[FoundDevice]:
    found = await BleakScanner.discover(timeout=timeout_s, return_adv=True)
    devices = [
        FoundDevice(name=dev.name or "", address=dev.address, rssi=adv.rssi)
        for dev, adv in found.values()
        if (dev.name or "").lower().startswith("muse")
    ]
    return sorted(devices, key=lambda d: d.rssi, reverse=True)


def read_device_info(
    *, name: str | None, address: str | None, timeout_s: float = 8.0, settle_s: float = 1.0
) -> dict[str, str]:
    """Ask the headband for its version information ("fw", "hw", ...).

    Connects briefly, sends the version query, then disconnects and waits `settle_s` so the OS
    releases the link before BrainFlow connects. Raises DeviceInfoError on any failure.
    """
    try:
        return asyncio.run(_read_device_info(name, address, timeout_s, settle_s))
    except (BleakError, TimeoutError, OSError) as exc:
        raise DeviceInfoError(str(exc) or type(exc).__name__) from exc


async def _read_device_info(
    name: str | None, address: str | None, timeout_s: float, settle_s: float
) -> dict[str, str]:
    device = None
    if address:
        device = await BleakScanner.find_device_by_address(address, timeout=timeout_s)
    if device is None and name:
        device = await BleakScanner.find_device_by_name(name, timeout=timeout_s)
    if device is None:
        raise DeviceInfoError("headband not found")

    parts: list[str] = []
    done = asyncio.Event()

    def on_control(_char: BleakGATTCharacteristic, data: bytearray) -> None:
        parts.append(payload_text(bytes(data)))
        if reply_complete("".join(parts)):
            done.set()

    async with BleakClient(device, timeout=timeout_s) as client:
        await client.start_notify(CONTROL_UUID, on_control)
        await client.write_gatt_char(CONTROL_UUID, encode_command(VERSION_COMMAND), response=False)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(done.wait(), timeout=REPLY_TIMEOUT_S)
        with contextlib.suppress(BleakError, OSError):
            await client.stop_notify(CONTROL_UUID)
    await asyncio.sleep(settle_s)

    info = parse_device_info("".join(parts))
    if "fw" not in info:
        raise DeviceInfoError("the headband replied without a firmware version")
    return info
