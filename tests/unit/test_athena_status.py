from __future__ import annotations

from mufuse.acquisition.athena_status import firmware_from_log


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
