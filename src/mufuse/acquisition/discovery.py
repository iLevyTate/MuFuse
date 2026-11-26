"""BLE scan for nearby Muse headbands (no OS pairing needed)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from bleak import BleakScanner


@dataclass(frozen=True)
class FoundDevice:
    name: str
    address: str
    rssi: int


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
