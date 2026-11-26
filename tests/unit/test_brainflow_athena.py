"""BrainFlowAthena around a stand-in BoardShim: no Bluetooth, only the wiring around the driver."""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest
from brainflow.board_shim import BoardShim, BrainFlowError, BrainFlowPresets, LogLevels

import mufuse.acquisition.brainflow_athena as bfa
from mufuse.acquisition.athena import ATHENA_BOARD_ID
from mufuse.acquisition.brainflow_athena import BrainFlowAthena
from mufuse.acquisition.types import SourceError, StreamKind
from mufuse.runlog import log_path

STATUS = '{"hw":"01.1","fw":"3.1.29","sp":"Athena","rc":0}'
DEBUG, WARN = LogLevels.LEVEL_DEBUG.value, LogLevels.LEVEL_WARN.value
EEG, MOTION, OPTICS = (
    BrainFlowPresets.DEFAULT_PRESET,
    BrainFlowPresets.AUXILIARY_PRESET,
    BrainFlowPresets.ANCILLARY_PRESET,
)


class FakeBoard:
    """What BrainFlowAthena uses of BoardShim, with failures that can be switched on."""

    calls: ClassVar[list[Any]]
    fail: ClassVar[dict[Any, Exception]]
    log: ClassVar[Path | None]
    data: ClassVar[dict[int, np.ndarray]]  # preset -> the next get_board_data result

    def __init__(self, board_id: int, params: object) -> None:
        self._step("create")

    @classmethod
    def _step(cls, name: Any) -> None:
        cls.calls.append(name)
        if name in cls.fail:
            raise cls.fail[name]

    @classmethod
    def set_log_level(cls, level: int) -> None:
        cls._step(("level", level))

    @classmethod
    def set_log_file(cls, path: str) -> None:
        cls._step("log_file")
        cls.log = Path(path)
        cls.log.touch()

    @classmethod
    def get_board_descr(cls, board_id: int, preset: int) -> dict[str, Any]:
        cls._step("descr")
        return BoardShim.get_board_descr(board_id, preset)

    @classmethod
    def get_version(cls) -> str:
        return "fake"

    def prepare_session(self) -> None:
        self._step("prepare")
        if self.log is not None:  # the reply to `v6`, as BrainFlow logs it at debug level
            packet = " ".join(str(b) for b in bytes([len(STATUS)]) + STATUS.encode())
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(f"[board_logger] [debug] Status packet: {packet}\n")

    def start_stream(self) -> None:
        self._step("start")

    def stop_stream(self) -> None:
        self._step("stop")

    def release_session(self) -> None:
        self._step("release")

    def get_board_data(self, num_samples: int | None = None, preset: int = 0) -> np.ndarray:
        rows = BoardShim.get_board_descr(ATHENA_BOARD_ID, preset)["num_rows"]
        return self.data.pop(int(preset), np.empty((rows, 0)))


@pytest.fixture
def board(monkeypatch: pytest.MonkeyPatch) -> type[FakeBoard]:
    class Board(FakeBoard):
        calls: ClassVar[list[Any]] = []
        fail: ClassVar[dict[Any, Exception]] = {}
        log: ClassVar[Path | None] = None
        data: ClassVar[dict[int, np.ndarray]] = {}

    monkeypatch.setattr(bfa, "BoardShim", Board)
    monkeypatch.setattr(bfa, "_log_ok", None)  # as in a new process
    monkeypatch.setattr(bfa, "_firmware", None)
    monkeypatch.setattr(bfa, "FIRMWARE_WAIT_S", 0.0)
    return Board


def _samples(preset: int, counters: list[float]) -> np.ndarray:
    """A get_board_data block: one column per sample, values unique so mix-ups show."""
    descr = BoardShim.get_board_descr(ATHENA_BOARD_ID, preset)
    raw = np.arange(descr["num_rows"] * len(counters), dtype=np.float64)
    raw = raw.reshape(descr["num_rows"], len(counters)) + 1000.0
    raw[descr["package_num_channel"]] = counters
    raw[descr["timestamp_channel"]] = 1_700_000_000.0 + np.arange(len(counters)) / 256
    return raw


# Connecting --------------------------------------------------------------------------------


def test_firmware_is_read_from_the_driver_log(board: type[FakeBoard]) -> None:
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.device.firmware == "3.1.29"
    assert board.calls.index(("level", DEBUG)) < board.calls.index("prepare")
    assert board.calls[-1] == ("level", WARN)  # the terminal stays quiet afterwards


def test_connects_when_the_log_cannot_be_redirected(board: type[FakeBoard]) -> None:
    board.fail["log_file"] = BrainFlowError("unable to redirect logs to a file", 2)
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.device.firmware is None
    assert ("level", DEBUG) not in board.calls  # debug lines would land on the terminal
    BrainFlowAthena(device_name="MuseS-TEST").start()  # a reconnect
    assert board.calls.count("log_file") == 1  # a failed redirect sticks; it is not retried


def test_connects_when_the_log_folder_cannot_be_made(
    board: type[FakeBoard], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "blocker").write_text("a file where the folder should be")
    monkeypatch.setenv("MUFUSE_LOG_DIR", str(tmp_path / "blocker" / "logs"))
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.device.firmware is None
    assert "log_file" not in board.calls


def test_connects_when_the_log_level_cannot_be_set(board: type[FakeBoard]) -> None:
    board.fail["level", DEBUG] = BrainFlowError("no logger", 2)
    board.fail["level", WARN] = OSError("no logger")
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.device.firmware is None


def test_connects_when_the_status_reply_cannot_be_parsed(
    board: type[FakeBoard], monkeypatch: pytest.MonkeyPatch
) -> None:
    def surprise(log: str) -> str | None:
        raise ValueError("not a status reply")

    monkeypatch.setattr(bfa, "firmware_from_log", surprise)
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.device.firmware is None
    assert source.read() == []  # connected and usable
    assert board.calls[-1] == ("level", WARN)


def test_reconnect_does_not_wait_for_a_firmware_it_already_knows(
    board: type[FakeBoard], monkeypatch: pytest.MonkeyPatch
) -> None:
    BrainFlowAthena(device_name="MuseS-TEST").start()
    del board.calls[:]

    def no_wait(log: Path, offset: int) -> str | None:
        raise AssertionError("waited for the firmware again")

    monkeypatch.setattr(bfa, "_wait_for_firmware", no_wait)
    again = BrainFlowAthena(device_name="MuseS-TEST")
    again.start()
    assert again.device.firmware == "3.1.29"
    assert "log_file" not in board.calls
    assert ("level", DEBUG) not in board.calls


def test_an_old_large_log_is_deleted_before_the_first_redirect(board: type[FakeBoard]) -> None:
    log = log_path().parent / "brainflow.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_bytes(b"x" * 1_100_000)
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert log.stat().st_size < 10_000
    assert source.device.firmware == "3.1.29"


def test_a_small_log_is_kept(board: type[FakeBoard]) -> None:
    log = log_path().parent / "brainflow.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("earlier run\n", encoding="utf-8")
    BrainFlowAthena(device_name="MuseS-TEST").start()
    assert log.read_text(encoding="utf-8").startswith("earlier run\n")


@pytest.mark.parametrize("step", ["prepare", "start"])
def test_failed_connect_releases_the_board(board: type[FakeBoard], step: str) -> None:
    board.fail[step] = BrainFlowError("BOARD_NOT_READY_ERROR", 7)
    source = BrainFlowAthena(device_name="MuseS-TEST")
    with pytest.raises(SourceError, match="Could not connect"):
        source.start()
    assert board.calls[-3:] == ["stop", "release", ("level", WARN)]
    with pytest.raises(SourceError):
        source.read()


@pytest.mark.parametrize("step", ["descr", "create"])
def test_driver_that_cannot_load_is_a_connect_error(board: type[FakeBoard], step: str) -> None:
    board.fail[step] = OSError("BoardController.dll: cannot load library")
    with pytest.raises(SourceError, match="cannot load library"):
        BrainFlowAthena(device_name="MuseS-TEST").start()


def test_making_a_source_does_not_touch_the_driver(board: type[FakeBoard]) -> None:
    BrainFlowAthena(device_name="MuseS-TEST")
    assert board.calls == []


# Reading -----------------------------------------------------------------------------------


def test_read_keeps_every_sample_and_counts_lost_subpackets(board: type[FakeBoard]) -> None:
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    assert source.lost_subpackets == dict.fromkeys(StreamKind, 0)

    raw = _samples(EEG, [254, 254, 255, 255, 1, 1])  # subpacket 0 never arrived
    board.data = {int(EEG): raw.copy(), int(OPTICS): _samples(OPTICS, [7, 8, 9])}
    eeg, optics = source.read()
    descr = BoardShim.get_board_descr(ATHENA_BOARD_ID, EEG)
    assert eeg.kind is StreamKind.EEG
    assert eeg.n_samples == 6
    assert eeg.data.shape[1] == descr["num_rows"] - 3  # all but counter, time and marker rows
    assert set(eeg.data[0]) <= set(raw[:, 0])
    assert raw[descr["package_num_channel"], 0] not in eeg.data[0]
    assert optics.n_samples == 3
    assert source.lost_subpackets == {StreamKind.EEG: 1, StreamKind.MOTION: 0, StreamKind.OPTICS: 0}

    board.data = {int(EEG): _samples(EEG, [4, 4, 5, 5])}  # 2 and 3 fell between two reads
    source.read()
    assert source.lost_subpackets[StreamKind.EEG] == 3

    source.stop()
    assert source.lost_subpackets[StreamKind.EEG] == 3  # still there for the manifest


def test_counting_never_changes_or_stops_a_read(board: type[FakeBoard]) -> None:
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    raw = _samples(EEG, [1, 1, float("nan"), 9])
    board.data = {int(EEG): raw.copy()}
    (eeg,) = source.read()
    assert eeg.n_samples == 4
    assert source.lost_subpackets[StreamKind.EEG] == 0  # an unreadable counter counts nothing


def test_package_number_low_byte_is_the_counter(board: type[FakeBoard]) -> None:
    source = BrainFlowAthena(device_name="MuseS-TEST")
    source.start()
    # BrainFlow packs (packet index << 8) | subpacket counter.
    board.data = {int(EEG): _samples(EEG, [(3 << 8) | 255, (4 << 8) | 0, (4 << 8) | 2])}
    source.read()
    assert source.lost_subpackets[StreamKind.EEG] == 1
