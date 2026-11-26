"""Read the Athena's status replies (firmware, battery, active preset) from BrainFlow's debug log.

BrainFlow sends `v6` and `s` on connect but only logs the replies, as decimal bytes:
`Status packet: 19 123 34 102 119 ...`. Each BLE packet is a length byte followed by a slice of
a JSON object, so the text is the printable bytes of consecutive packets joined together.
Packets come in more than one size: 20 bytes on the classic link, longer with a larger MTU.

The reply to `v6` carries the firmware (`fw`). The reply to `s` carries the battery level as the
headset itself computes it (`bp`, percent) and the active preset (`ps`, the preset's hex name
written in decimal: 4161 = 0x1041 = p1041). It comes more than once while connecting, and the
first one after power-up still shows the power-up preset, so the last one counts. It also
carries the headset's name, serial number and address: none of that is kept.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mufuse.acquisition.athena import preset_from_code

_STATUS = re.compile(r"Status packet: ([\d ]+)")
_FIRMWARE = re.compile(r'"fw"\s*:\s*"([^"]+)"')
_BATTERY = re.compile(r'"bp"\s*:\s*(\d+(?:\.\d+)?)')
_PRESET = re.compile(r'"ps"\s*:\s*(\d+)')
# BrainFlow (5.24) divides the raw battery value by 512 where the headset counts in 256ths, so its
# battery row reads half of `bp`. muse-rs checked 256 against `bp`; OpenMuse and muse.js use 256.
BATTERY_MATCH_PCT = 2.0  # the row counts as half of `bp` within this many percentage points


@dataclass(frozen=True)
class HeadsetStatus:
    firmware: str | None = None
    battery_pct: float | None = None  # `bp`, from the last reply that had one
    preset_code: int | None = None  # `ps`, from the last reply that had one

    @property
    def active_preset(self) -> str | None:
        return None if self.preset_code is None else preset_from_code(self.preset_code)

    @property
    def complete(self) -> bool:
        return None not in (self.firmware, self.battery_pct, self.preset_code)


def status_from_log(log: str) -> HeadsetStatus:
    text = "".join(_packet_text(m.group(1)) for m in _STATUS.finditer(log))
    firmware = _FIRMWARE.search(text)
    battery = _BATTERY.findall(text)
    preset = _PRESET.findall(text)
    return HeadsetStatus(
        firmware=firmware.group(1) if firmware else None,
        battery_pct=float(battery[-1]) if battery else None,
        preset_code=int(preset[-1]) if preset else None,
    )


def firmware_from_log(log: str) -> str | None:
    return status_from_log(log).firmware


def battery_scale(row: float, status_pct: float | None) -> float:
    """2 when BrainFlow's battery row reads half of the headset's own value, else 1."""
    if status_pct is None or row <= 0:
        return 1.0
    if abs(2 * row - status_pct) <= BATTERY_MATCH_PCT < abs(row - status_pct):
        return 2.0
    return 1.0


def _packet_text(decimal_bytes: str) -> str:
    data = [int(b) for b in decimal_bytes.split()]
    if not data:
        return ""
    # A length byte counts the text bytes after it. Below 32 it cannot be text, and whatever
    # follows the counted bytes is stale. From 32 up it is also a printable character, so it is
    # taken as a length only when it matches exactly.
    if data[0] == len(data) - 1 or data[0] < 32:
        data = data[1 : 1 + data[0]]
    return "".join(chr(b) for b in data if 32 <= b < 127)
