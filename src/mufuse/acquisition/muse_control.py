"""Muse control-channel framing, used to ask the headband for its firmware version.

BrainFlow does not expose the firmware, so MuFuse asks for it itself over BLE before BrainFlow
connects (the headband accepts one connection at a time). The framing follows OpenMuse and
muse-lsl: commands are a length byte, ASCII text and a newline, written to the control
characteristic; replies are JSON text that arrives in notification fragments on the same
characteristic, each fragment usually starting with its own length byte. "v6" is the version query
OpenMuse sends to the Athena; the reply carries "fw" (firmware) and related fields.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

CONTROL_UUID = "273e0001-4c4d-454d-96be-f03bac821358"
VERSION_COMMAND = "v6"

# Reply fields that describe the device rather than its momentary state (battery "bp" and the
# return code "rc" change from call to call, so they are not stored with recordings).
STABLE_FIELDS = ("hw", "bn", "bl", "sp", "tp", "pv")

_FIELD = re.compile(r'"(?P<key>[a-z]{2})"\s*:\s*(?:"(?P<text>[^"]*)"|(?P<number>-?[\d.]+))')


class DeviceInfoError(RuntimeError):
    """The headband's version information could not be read."""


def encode_command(token: str) -> bytes:
    """Frame a control command: one length byte (text + newline), ASCII text, newline."""
    if not token or not token.isascii():
        raise ValueError(f"Invalid Muse command {token!r}: must be non-empty ASCII")
    payload = (token + "\n").encode("ascii")
    if len(payload) > 255:
        raise ValueError("Muse command too long (max 254 characters)")
    return bytes([len(payload)]) + payload


def payload_text(fragment: bytes) -> str:
    """Text carried by one notification fragment.

    When the first byte is a plausible length for the rest of the fragment it is a length prefix
    and only that many bytes are kept; otherwise the whole fragment is text.
    """
    prefixed = bool(fragment) and fragment[0] < len(fragment)
    body = fragment[1 : 1 + fragment[0]] if prefixed else fragment
    return body.decode("ascii", errors="ignore")


def parse_device_info(text: str) -> dict[str, str]:
    """All two-letter JSON fields found in the reply text, values as strings."""
    info: dict[str, str] = {}
    for match in _FIELD.finditer(text):
        text_value = match.group("text")
        info[match.group("key")] = (
            text_value if text_value is not None else match.group("number") or ""
        )
    return info


def reply_complete(text: str) -> bool:
    return "fw" in parse_device_info(text) and text.rstrip().endswith("}")


def split_device_info(info: Mapping[str, str]) -> tuple[str | None, dict[str, str]]:
    """Firmware version plus the stable fields worth keeping with every recording."""
    return info.get("fw"), {k: info[k] for k in STABLE_FIELDS if k in info}
