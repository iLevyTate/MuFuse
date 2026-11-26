"""Real Muse S Athena source via BrainFlow native BLE (hardware; exercised by tests/hardware)."""

# BrainFlow ships without type stubs; relax unknown-type checks at this hardware boundary only.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping
from pathlib import Path

import numpy as np
from brainflow.board_shim import (
    BoardShim,
    BrainFlowError,
    BrainFlowInputParams,
    BrainFlowPresets,
    LogLevels,
)

from mufuse.acquisition.athena import (
    ATHENA_BOARD_ID,
    ATHENA_STREAMS,
    DEFAULT_PRESET,
    validate_preset,
)
from mufuse.acquisition.athena_status import HeadsetStatus, battery_scale, status_from_log
from mufuse.acquisition.loss import skipped_subpackets
from mufuse.acquisition.timing import Retimer
from mufuse.acquisition.types import (
    Chunk,
    DeviceInfo,
    FloatArray,
    SourceError,
    StreamKind,
    StreamSpec,
)
from mufuse.runlog import log_path

FIRMWARE_WAIT_S = 0.3  # the status replies to BrainFlow's `v6` and `s` land while connecting
LOG_KEEP_BYTES = 1_000_000  # the debug log grows with every connection; start over above this

_BF_PRESET = {
    StreamKind.EEG: BrainFlowPresets.DEFAULT_PRESET,
    StreamKind.MOTION: BrainFlowPresets.AUXILIARY_PRESET,
    StreamKind.OPTICS: BrainFlowPresets.ANCILLARY_PRESET,
}

# Reading the firmware is a nicety that must never cost a connection. BrainFlow's log file is
# set per process and a failed redirect sticks, so it is tried once: None = not tried yet.
_log_ok: bool | None = None
_firmware: str | None = None  # once read, reconnects in this process skip the readout
_status: HeadsetStatus | None = None  # the headset's own battery and active preset, if read
# Whether BrainFlow's battery row reads half of the headset's value (see athena_status.py):
# decided at the first reading, kept for reconnects. None = not decided yet.
_battery_scale: float | None = None


class BrainFlowAthena:
    def __init__(
        self,
        *,
        device_name: str | None = None,
        mac_address: str | None = None,
        preset: str = DEFAULT_PRESET,
        low_latency: bool = True,
        timeout_s: int = 15,
    ) -> None:
        self._preset = validate_preset(preset)
        self._params = BrainFlowInputParams()
        self._params.serial_number = device_name or ""
        self._params.mac_address = mac_address or ""
        self._params.timeout = timeout_s
        latency = "true" if low_latency else "false"
        self._params.other_info = f"preset={self._preset};low_latency={latency}"
        self._name = device_name or "MuseS-Athena"
        self._address = mac_address
        self._board: BoardShim | None = None
        # Per stream: timestamp row, package number row, data rows.
        self._rows: dict[StreamKind, tuple[int, int, list[int]]] = {}
        self._retimers: dict[StreamKind, Retimer] = {}
        self._lost = dict.fromkeys(ATHENA_STREAMS, 0)
        self._last_counter: dict[StreamKind, int] = {}
        self._bf_log = log_path().parent / "brainflow.log"

    @property
    def device(self) -> DeviceInfo:
        extra: dict[str, str] = {}
        if _status is not None and _status.active_preset is not None:
            extra["active_preset"] = _status.active_preset
        if _status is not None and _status.battery_pct is not None:
            extra["status_battery_pct"] = str(_status.battery_pct)
        return DeviceInfo(
            name=self._name,
            preset=self._preset,
            driver=f"brainflow-{BoardShim.get_version()}",
            address=self._address,
            firmware=_firmware,
            extra=extra,
        )

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    @property
    def lost_subpackets(self) -> Mapping[StreamKind, int]:
        return dict(self._lost)

    def start(self) -> None:
        global _firmware, _status
        # BrainFlow only logs the status replies at debug level, so log to a file while
        # connecting and read them back (see athena_status.py).
        log_from = None if _firmware else _debug_log_offset(self._bf_log)
        if log_from is None:
            _set_log_level(LogLevels.LEVEL_WARN)
        board: BoardShim | None = None
        try:
            for kind, bf_preset in _BF_PRESET.items():
                descr = BoardShim.get_board_descr(ATHENA_BOARD_ID, bf_preset)
                skip = {
                    descr[k] for k in ("package_num_channel", "timestamp_channel", "marker_channel")
                }
                data_rows = [r for r in range(descr["num_rows"]) if r not in skip]
                self._rows[kind] = (
                    descr["timestamp_channel"],
                    descr["package_num_channel"],
                    data_rows,
                )
            board = BoardShim(ATHENA_BOARD_ID, self._params)
            board.prepare_session()
            board.start_stream()
            if log_from is not None:
                _status = _wait_for_status(self._bf_log, log_from)
                _firmware = _status.firmware
        except (BrainFlowError, OSError) as exc:  # OSError: the driver library did not load
            if board is not None:
                _safe_release(board)
            raise SourceError(
                "Could not connect to the Muse S Athena. Check it is powered on, Bluetooth is on, "
                f"and no other app (e.g. the Muse app) is connected. ({exc})"
            ) from exc
        finally:
            _set_log_level(LogLevels.LEVEL_WARN)
        self._board = board
        self._retimers = {k: Retimer(spec.sampling_rate) for k, spec in ATHENA_STREAMS.items()}
        self._last_counter = {}

    def read(self) -> list[Chunk]:
        if self._board is None:
            raise SourceError("BrainFlowAthena.read() called before start()")
        chunks: list[Chunk] = []
        try:
            for kind, bf_preset in _BF_PRESET.items():
                raw = self._board.get_board_data(preset=bf_preset)
                if raw.shape[1] == 0:
                    continue
                ts_row, counter_row, data_rows = self._rows[kind]
                # Keep every sample; arrival-time stamps are duplicated/jittery (see timing.py).
                ts = self._retimers[kind].retime(raw[ts_row].astype(np.float64))
                data = raw[data_rows].T.astype(np.float64)
                if kind is StreamKind.OPTICS:
                    _correct_battery(data[:, -1])
                chunks.append(Chunk(kind, ts, data))
                self._count_lost(kind, raw, counter_row)
        except BrainFlowError as exc:
            raise SourceError(f"Lost the headband stream: {exc}") from exc
        return chunks

    def _count_lost(self, kind: StreamKind, raw: FloatArray, counter_row: int) -> None:
        """Add up subpackets that never arrived. Bookkeeping only: it can never stop a read."""
        with contextlib.suppress(Exception):
            counters = [int(v) & 0xFF for v in raw[counter_row]]
            lost = skipped_subpackets(counters, self._last_counter.get(kind))
            self._last_counter[kind] = counters[-1]
            self._lost[kind] += lost

    def stop(self) -> None:
        if self._board is not None:
            _safe_release(self._board)
            self._board = None


def _correct_battery(battery: FloatArray) -> None:
    """Double BrainFlow's battery readings in place when they read half of the headset's own
    level (it divides by 512, not 256). 0 means not reported yet and stays 0."""
    global _battery_scale
    reported = battery > 0
    if _battery_scale is None and reported.any():
        _battery_scale = battery_scale(float(battery[reported][0]), _status and _status.battery_pct)
    if _battery_scale is not None:
        battery[reported] *= _battery_scale


def _safe_release(board: BoardShim) -> None:
    for action in (board.stop_stream, board.release_session):
        with contextlib.suppress(BrainFlowError):
            action()


def _set_log_level(level: LogLevels) -> None:
    with contextlib.suppress(Exception):
        BoardShim.set_log_level(level.value)


def _debug_log_offset(log: Path) -> int | None:
    """Turn on BrainFlow's debug log in `log`; returns where this connection's lines start.

    None when the file cannot be used. Then nothing is logged at debug level (it would land on
    the terminal) and nothing waits for the firmware.
    """
    global _log_ok
    try:
        if _log_ok is None:
            _log_ok = False
            log.parent.mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(OSError):
                if log.stat().st_size > LOG_KEEP_BYTES:
                    log.unlink()
            BoardShim.set_log_file(str(log))
            _log_ok = True
        if not _log_ok:
            return None
        offset = log.stat().st_size if log.exists() else 0
        BoardShim.set_log_level(LogLevels.LEVEL_DEBUG.value)
        return offset
    except Exception:
        return None


def _wait_for_status(log: Path, offset: int) -> HeadsetStatus:
    deadline = time.monotonic() + FIRMWARE_WAIT_S
    try:
        while True:
            with log.open("rb") as fh:
                fh.seek(offset)
                text = fh.read().decode("utf-8", errors="replace")
            status = status_from_log(text)
            if status.complete or time.monotonic() >= deadline:
                return status
            time.sleep(0.1)
    except Exception:  # an unreadable log or reply is no reason to give up a connection
        return HeadsetStatus()
