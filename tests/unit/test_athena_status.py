from __future__ import annotations

import pytest

from mufuse.acquisition.athena_status import battery_scale, firmware_from_log, status_from_log


def _log_lines(
    reply: str, prefix: str = "[2026-11-26 10:00:00.123] [board_logger] [debug] "
) -> str:
    """How BrainFlow logs a status reply: BLE packets of [length, ascii...], as decimal bytes."""
    lines = []
    raw = reply.encode("ascii")
    for i in range(0, len(raw), 19):
        part = raw[i : i + 19]
        packet = bytes([len(part)]) + part + b"\x00" * (19 - len(part))
        lines.append(prefix + "Status packet: " + " ".join(str(b) for b in packet))
    return "\n".join(lines)


def test_reads_firmware_from_a_split_status_reply() -> None:
    reply = '{"fw":"3.1.29","hw":"03.4","bl":"2.0.1","sp":"Athena","rc":0}'
    log = "\n".join(["[info] Connected to MuseAthena Device", _log_lines(reply), "[info] done"])
    assert firmware_from_log(log) == "3.1.29"


def test_takes_the_first_firmware_when_status_repeats() -> None:
    log = _log_lines('{"fw":"3.1.23","rc":0}') + "\n" + _log_lines('{"fw":"3.1.23","bp":80}')
    assert firmware_from_log(log) == "3.1.23"


def test_no_status_packets_means_unknown() -> None:
    assert firmware_from_log("[info] Connected to MuseAthena Device") is None
    assert firmware_from_log(_log_lines('{"bp":80,"rc":0}')) is None


def test_packets_without_a_length_byte_are_read_as_text() -> None:
    reply = '{"fw":"3.1.29","rc":0}'
    log = "Status packet: " + " ".join(str(b) for b in reply.encode("ascii"))
    assert firmware_from_log(log) == "3.1.29"


def test_long_fragments_have_a_printable_length_byte() -> None:
    # Larger BLE packets are [length, text...] with nothing after the text. A length of 32 or
    # more is itself a printable character and must not end up inside the firmware version.
    reply = (
        '{"hw":"01.1","bn":1,"fw":"3.1.29","tp":"consumer","sp":"Athena",'
        '"bl":"1.0.10","be":"1.5.1","rc":0}'
    )
    payload = reply.encode("ascii")
    lines: list[str] = []
    at = 0
    for size in (9, 20, 33, 40):
        part = payload[at : at + size - 1]
        at += len(part)
        assert len(part) == size - 1
        lines.append("Status packet: " + " ".join(str(b) for b in bytes([len(part)]) + part))
    assert at == len(payload)
    assert payload[26:32] == b"3.1.29"  # split between the 20- and the 33-byte fragment
    assert firmware_from_log("\n".join(lines)) == "3.1.29"


def test_stale_bytes_after_a_short_length_are_ignored() -> None:
    packet = bytes([14]) + b'{"fw":"3.1.19"' + b"zzzzz"  # 20-byte packet, old bytes left behind
    log = "Status packet: " + " ".join(str(b) for b in packet)
    log += "\nStatus packet: " + " ".join(str(b) for b in bytes([8]) + b',"rc":0}')
    assert firmware_from_log(log) == "3.1.19"


# Battery and active preset: the second reply, to `s` ---------------------------------------
# Made-up identifiers: a real reply also carries the headset's name, serial and address.
_FIRST = '{"fw":"3.1.31","bn":1,"tp":"consumer","sp":"Athena","rc":0}'
_POWER_UP = '{"hn":"MuseS-1A2B","sn":"0000-TEST","id":"0","bp":99.46,"ps":4129,"rc":0}'
_APPLIED = '{"hn":"MuseS-1A2B","sn":"0000-TEST","id":"0","bp":99.40,"ps":4161,"rc":0}'


def test_reads_battery_and_preset_from_the_status_replies() -> None:
    log = "\n".join(_log_lines(r) for r in (_FIRST, _POWER_UP, '{"rc":0}', _APPLIED))
    status = status_from_log(log)
    assert status.firmware == "3.1.31"
    # The first reply after power-up still shows the power-up preset; the last one counts.
    assert status.preset_code == 4161
    assert status.active_preset == "p1041"
    assert status.battery_pct == pytest.approx(99.40)
    assert status.complete


def test_a_reply_without_battery_or_preset_leaves_them_unknown() -> None:
    status = status_from_log(_log_lines(_FIRST))
    assert (status.battery_pct, status.preset_code, status.active_preset) == (None, None, None)
    assert not status.complete
    assert status_from_log("").firmware is None


@pytest.mark.parametrize(
    ("row", "bp", "scale"),
    [
        (49.73, 99.46, 2.0),  # BrainFlow divides by 512 where the headset counts in 256ths
        (49.0, 99.46, 2.0),  # a little drained since the status reply
        (99.4, 99.46, 1.0),  # a driver that already reads it right
        (30.0, 99.46, 1.0),  # neither: leave it alone
        (49.73, None, 1.0),  # no status reply: nothing to compare with
        (0.0, 99.46, 1.0),  # not reported yet
    ],
)
def test_battery_row_is_doubled_only_when_it_reads_half_the_headset_value(
    row: float, bp: float | None, scale: float
) -> None:
    assert battery_scale(row, bp) == scale
