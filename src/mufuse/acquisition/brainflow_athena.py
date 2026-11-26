"""Real Muse S Athena source via BrainFlow native BLE (hardware; exercised by tests/hardware)."""

# BrainFlow ships without type stubs; relax unknown-type checks at this hardware boundary only.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from __future__ import annotations

import contextlib
from collections.abc import Mapping

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
from mufuse.acquisition.timing import Retimer
from mufuse.acquisition.types import Chunk, DeviceInfo, SourceError, StreamKind, StreamSpec

_BF_PRESET = {
    StreamKind.EEG: BrainFlowPresets.DEFAULT_PRESET,
    StreamKind.MOTION: BrainFlowPresets.AUXILIARY_PRESET,
    StreamKind.OPTICS: BrainFlowPresets.ANCILLARY_PRESET,
}


class BrainFlowAthena:
    def __init__(
        self,
        *,
        device_name: str | None = None,
        mac_address: str | None = None,
        preset: str = DEFAULT_PRESET,
        low_latency: bool = True,
        timeout_s: int = 15,
        firmware: str | None = None,
        device_extra: Mapping[str, str] | None = None,
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
        self._firmware = firmware  # read beforehand over BLE; BrainFlow does not report it
        self._extra = dict(device_extra or {})
        self._board: BoardShim | None = None
        self._rows: dict[StreamKind, tuple[int, list[int]]] = {}
        self._retimers: dict[StreamKind, Retimer] = {}
        BoardShim.set_log_level(LogLevels.LEVEL_WARN.value)

    @property
    def device(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._name,
            preset=self._preset,
            driver=f"brainflow-{BoardShim.get_version()}",
            address=self._address,
            firmware=self._firmware,
            extra=dict(self._extra),
        )

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    def start(self) -> None:
        for kind, bf_preset in _BF_PRESET.items():
            descr = BoardShim.get_board_descr(ATHENA_BOARD_ID, bf_preset)
            skip = {
                descr[k] for k in ("package_num_channel", "timestamp_channel", "marker_channel")
            }
            data_rows = [r for r in range(descr["num_rows"]) if r not in skip]
            self._rows[kind] = (descr["timestamp_channel"], data_rows)
        board = BoardShim(ATHENA_BOARD_ID, self._params)
        try:
            board.prepare_session()
            board.start_stream()
        except BrainFlowError as exc:
            _safe_release(board)
            raise SourceError(
                "Could not connect to the Muse S Athena. Check it is powered on, Bluetooth is on, "
                f"and no other app (e.g. the Muse app) is connected. ({exc})"
            ) from exc
        self._board = board
        self._retimers = {k: Retimer(spec.sampling_rate) for k, spec in ATHENA_STREAMS.items()}

    def read(self) -> list[Chunk]:
        if self._board is None:
            raise SourceError("BrainFlowAthena.read() called before start()")
        chunks: list[Chunk] = []
        try:
            for kind, bf_preset in _BF_PRESET.items():
                raw = self._board.get_board_data(preset=bf_preset)
                if raw.shape[1] == 0:
                    continue
                ts_row, data_rows = self._rows[kind]
                # Keep every sample; arrival-time stamps are duplicated/jittery (see timing.py).
                ts = self._retimers[kind].retime(raw[ts_row].astype(np.float64))
                chunks.append(Chunk(kind, ts, raw[data_rows].T.astype(np.float64)))
        except BrainFlowError as exc:
            raise SourceError(f"Lost the headband stream: {exc}") from exc
        return chunks

    def stop(self) -> None:
        if self._board is not None:
            _safe_release(self._board)
            self._board = None


def _safe_release(board: BoardShim) -> None:
    for action in (board.stop_stream, board.release_session):
        with contextlib.suppress(BrainFlowError):
            action()
