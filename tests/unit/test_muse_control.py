from __future__ import annotations

import pytest

from mufuse.acquisition.muse_control import (
    encode_command,
    parse_device_info,
    payload_text,
    reply_complete,
    split_device_info,
)


def test_command_is_length_prefixed_with_newline() -> None:
    assert encode_command("v6") == b"\x03v6\n"


@pytest.mark.parametrize("bad", ["", "vé", "x" * 255])
def test_command_rejects_empty_non_ascii_or_too_long(bad: str) -> None:
    with pytest.raises(ValueError, match="command"):
        encode_command(bad)


def test_fragment_length_prefix_is_stripped() -> None:
    fragment = bytes([7]) + b'{"fw":"' + b"\x00" * 12
    assert payload_text(fragment) == '{"fw":"'


def test_fragment_without_plausible_prefix_is_kept_whole() -> None:
    # '{' is 0x7B = 123, larger than the fragment, so it cannot be a length byte.
    assert payload_text(b'{"fw":"1.2"}') == '{"fw":"1.2"}'


def _fragment(text: str) -> bytes:
    """A 20-byte notification: length byte, text, zero padding."""
    body = text.encode("ascii")
    return bytes([len(body)]) + body + b"\x00" * (19 - len(body))


def test_reply_split_across_fragments_is_parsed() -> None:
    reply = '{"ap":"headset","sp":"Athena_RevB","tp":"consumer","hw":"3.1","bn":42,"fw":"3.4.2"}'
    fragments = [_fragment(reply[i : i + 19]) for i in range(0, len(reply), 19)]
    text = "".join(payload_text(f) for f in fragments)
    info = parse_device_info(text)
    assert info["fw"] == "3.4.2"
    assert info["hw"] == "3.1"
    assert info["bn"] == "42"
    assert info["sp"] == "Athena_RevB"
    assert reply_complete(text)


def test_reply_is_incomplete_until_closing_brace() -> None:
    assert not reply_complete('{"fw":"3.4.2","rc"')
    assert not reply_complete('{"hw":"3.1"}')  # no firmware field yet


def test_split_keeps_firmware_and_stable_fields_only() -> None:
    firmware, extra = split_device_info(
        {"fw": "3.4.2", "hw": "3.1", "bn": "42", "bp": "81", "rc": "0", "sp": "Athena_RevB"}
    )
    assert firmware == "3.4.2"
    assert extra == {"hw": "3.1", "bn": "42", "sp": "Athena_RevB"}


def test_split_without_firmware() -> None:
    assert split_device_info({}) == (None, {})
