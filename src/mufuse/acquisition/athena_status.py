"""Read the Athena's status reply (firmware version) out of BrainFlow's debug log.

BrainFlow sends `v6` on connect but only logs the reply, as decimal bytes:
`Status packet: 19 123 34 102 119 ...`. Each BLE packet is a length byte followed by a slice of
a JSON object, so the text is the printable bytes of consecutive packets joined together.
Packets come in more than one size: 20 bytes on the classic link, longer with a larger MTU.
"""

from __future__ import annotations

import re

_STATUS = re.compile(r"Status packet: ([\d ]+)")
_FIRMWARE = re.compile(r'"fw"\s*:\s*"([^"]+)"')


def firmware_from_log(log: str) -> str | None:
    text = "".join(_packet_text(m.group(1)) for m in _STATUS.finditer(log))
    match = _FIRMWARE.search(text)
    return match.group(1) if match else None


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
