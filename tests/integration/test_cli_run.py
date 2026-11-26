"""The record loop itself, driven with a fake clock, scripted keys and raised signals."""

from __future__ import annotations

import io
import os
import signal
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from mufuse.acceptance import CHECKS
from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import SimulatedAthena
from mufuse.acquisition.source import HeadbandSource
from mufuse.acquisition.supervisor import State, StreamSupervisor
from mufuse.acquisition.types import DeviceInfo, SourceError, StreamKind
from mufuse.cli import (
    EXIT_INTERRUPTED,
    EXIT_WRITE,
    LiveStats,
    SourceKind,
    _Attempt,  # pyright: ignore[reportPrivateUsage]
    _guide_panel,  # pyright: ignore[reportPrivateUsage]
    _render,  # pyright: ignore[reportPrivateUsage]
    _run,  # pyright: ignore[reportPrivateUsage]
    app,
    use_utf8_output,
)
from mufuse.guide import Cue, Guide
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from mufuse.runlog import log_path, read_runs
from tests.conftest import FakeClock


class Sim(SimulatedAthena):
    """Simulated headband on the fake clock that reports how it was released."""

    def __init__(self, clock: FakeClock, **kwargs: object) -> None:
        super().__init__(clock=clock, **kwargs)  # type: ignore[arg-type]
        self.stops = 0
        self.on_stop: Callable[[], None] = lambda: None

    def stop(self) -> None:
        self.stops += 1
        self.on_stop()
        super().stop()


class Keys:
    """Scripted keyboard: each key becomes available at its time after the script was made."""

    def __init__(self, clock: FakeClock, presses: list[tuple[float, str]]) -> None:
        self._clock = clock
        self._t0 = clock.now
        self._presses = sorted(presses)

    def __call__(self) -> str | None:
        if self._presses and self._clock.now - self._t0 >= self._presses[0][0]:
            return self._presses.pop(0)[1]
        return None


def _record(
    tmp_path: Path,
    clock: FakeClock,
    factory: Callable[[], HeadbandSource],
    duration: float | None,
    *,
    keys: Callable[[], str | None] = lambda: None,
    sleep: Callable[[float], None] | None = None,
    source: SourceKind = SourceKind.sim,
) -> None:
    _run(
        _Attempt("record", source, "p1041", clock.now),
        factory,
        duration,
        lambda src: SessionWriter.create(tmp_path, src.device, src.streams, clock=clock),
        clock=clock,
        sleep=sleep or clock.advance,
        read_key=keys,
    )


def _session(tmp_path: Path) -> LoadedSession:
    (session_dir,) = tmp_path.iterdir()
    return load_session(session_dir)


def _length(session: LoadedSession) -> float:
    return session.manifest["ended_at"] - session.manifest["started_at"]


# Stopping ----------------------------------------------------------------------------------


def test_session_is_saved_before_the_slow_release(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    sim = Sim(clock)
    sim.on_stop = lambda: clock.advance(8.0)  # letting go of the headband takes seconds
    _record(tmp_path, clock, lambda: sim, 1.0, source=SourceKind.athena)
    assert sim.stops == 1
    assert _length(_session(tmp_path)) == pytest.approx(1.0, abs=0.1)  # not 9 s
    out = capsys.readouterr().out
    assert out.index("Saved session") < out.index("Releasing the headband")
    assert "Nothing to press" in out


def test_simulated_source_does_not_announce_a_slow_release(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    _record(tmp_path, clock, lambda: Sim(clock), 0.5)
    assert "Releasing the headband" not in capsys.readouterr().out


def test_ctrl_c_stops_the_recording_and_saves_it(tmp_path: Path, clock: FakeClock) -> None:
    handler_before = signal.getsignal(signal.SIGINT)

    def sleep(seconds: float) -> None:
        clock.advance(seconds)
        if 0.5 <= clock.now - t0 < 0.55:
            signal.raise_signal(signal.SIGINT)

    t0 = clock.now
    sim = Sim(clock)
    _record(tmp_path, clock, lambda: sim, None, sleep=sleep)
    session = _session(tmp_path)
    assert session.finalized
    assert _length(session) == pytest.approx(0.5, abs=0.1)
    assert sim.stops == 1
    assert signal.getsignal(signal.SIGINT) is handler_before


def test_second_ctrl_c_during_the_release_cannot_cost_the_session(
    tmp_path: Path, clock: FakeClock
) -> None:
    sim = Sim(clock)
    sim.on_stop = lambda: signal.raise_signal(signal.SIGINT)  # an impatient second press
    _record(tmp_path, clock, lambda: sim, 0.5)
    assert _session(tmp_path).finalized


def test_release_error_still_leaves_a_saved_session(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail() -> None:
        raise RuntimeError("driver crashed")

    sim = Sim(clock)
    sim.on_stop = fail
    _record(tmp_path, clock, lambda: sim, 0.5)
    assert _session(tmp_path).finalized
    assert "driver crashed" in capsys.readouterr().out
    (run,) = read_runs(log_path())
    assert run.outcome == "signal"


def test_ctrl_c_while_connecting_releases_and_exits(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    class PressedWhileConnecting(Sim):
        def start(self) -> None:
            signal.raise_signal(signal.SIGINT)  # held back by the driver until connect returns
            super().start()

    handler_before = signal.getsignal(signal.SIGINT)
    sim = PressedWhileConnecting(clock)
    with pytest.raises(typer.Exit) as stopped:
        _record(tmp_path, clock, lambda: sim, 5.0)
    assert stopped.value.exit_code == EXIT_INTERRUPTED
    assert sim.stops == 1
    assert list(tmp_path.iterdir()) == []  # nothing was recorded
    assert "Stopped before" in capsys.readouterr().out
    (run,) = read_runs(log_path())
    assert run.outcome == "interrupted"
    assert signal.getsignal(signal.SIGINT) is handler_before


def test_headband_is_released_when_saving_fails(tmp_path: Path, clock: FakeClock) -> None:
    class DiskFull(SessionWriter):
        def finalize(self, lost_subpackets: object = None) -> None:
            self.close_files()
            raise OSError("No space left on device")

    sim = Sim(clock)

    def writer(src: HeadbandSource) -> SessionWriter:
        made = SessionWriter.create(tmp_path, src.device, src.streams, clock=clock)
        made.__class__ = DiskFull
        return made

    attempt = _Attempt("record", SourceKind.sim, "p1041", clock.now)
    with pytest.raises(typer.Exit) as failed:
        _run(attempt, lambda: sim, 0.5, writer, clock=clock, sleep=clock.advance)
    assert failed.value.exit_code == EXIT_WRITE
    assert sim.stops == 1


# Gaps --------------------------------------------------------------------------------------


def test_recording_that_ends_while_reconnecting_saves_the_open_gap(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    t0 = clock.now
    attempts: list[float] = []

    class Gone(Sim):
        def start(self) -> None:
            attempts.append(clock.now - t0)
            clock.advance(3.0)  # a failed scan blocks for seconds
            raise SourceError("no device")

    sources = iter([Sim(clock, dropouts=[(1.0, 1e9)])])
    _record(tmp_path, clock, lambda: next(sources, Gone(clock)), 6.0)

    session = _session(tmp_path)
    assert session.finalized
    (gap,) = session.gaps
    assert gap.end is None
    assert gap.reason == "stall"
    assert gap.start - t0 == pytest.approx(1.0, abs=0.01)
    assert "Stopped before the signal returned" in capsys.readouterr().out
    # The scan that began before the end ran over it; no new one was started afterwards.
    assert len(attempts) == 1
    assert attempts[0] < 6.0


def test_closed_gap_is_not_saved_twice(tmp_path: Path, clock: FakeClock) -> None:
    sources = iter([Sim(clock, dropouts=[(1.0, 1e9)])])
    _record(tmp_path, clock, lambda: next(sources, Sim(clock)), 7.0)
    (gap,) = _session(tmp_path).gaps
    assert gap.end is not None


def test_the_steps_of_a_reconnect_are_saved_with_the_session(
    tmp_path: Path, clock: FakeClock
) -> None:
    t0 = clock.now

    class Gone(Sim):
        def start(self) -> None:
            clock.advance(3.0)
            raise SourceError("no device")

    sources = iter([Sim(clock, dropouts=[(1.0, 1e9)]), Gone(clock)])
    _record(tmp_path, clock, lambda: next(sources, Sim(clock)), 12.0)
    session = _session(tmp_path)
    assert [(s.what, s.detail) for s in session.reconnects] == [
        ("lost", "stall"),
        ("released", None),
        ("attempt", None),
        ("failed", "no device"),
        ("attempt", None),
        ("connected", None),
        ("first_sample", None),
    ]
    assert session.reconnects[0].t - t0 == pytest.approx(4.0, abs=0.1)  # 3 s after the last sample
    (gap,) = session.gaps
    assert session.reconnects[-1].t == pytest.approx(gap.end, abs=0.1)


# Keys and view -----------------------------------------------------------------------------


def test_keys_typed_before_the_recording_starts_are_dropped(
    tmp_path: Path, clock: FakeClock
) -> None:
    keys = Keys(clock, [(-1.0, "q"), (-0.5, " ")])  # pressed while it was still connecting
    _record(tmp_path, clock, lambda: Sim(clock), 1.0, keys=keys)
    session = _session(tmp_path)
    assert _length(session) == pytest.approx(1.0, abs=0.1)
    assert session.markers == []


def test_key_presses_are_saved_and_counted_on_screen(
    tmp_path: Path, clock: FakeClock, capsys: pytest.CaptureFixture[str]
) -> None:
    keys = Keys(clock, [(0.3, " "), (0.5, "1"), (0.7, "1"), (0.9, "q")])
    _record(tmp_path, clock, lambda: Sim(clock), 5.0, keys=keys)
    session = _session(tmp_path)
    assert [m.kind for m in session.markers] == ["moment", "block_start", "block_end"]
    assert _length(session) == pytest.approx(0.9, abs=0.1)
    assert "3 saved" in capsys.readouterr().out


def test_q_stops_a_stream_without_recording(clock: FakeClock) -> None:
    sim = Sim(clock)
    attempt = _Attempt("stream", SourceKind.sim, "p1041", clock.now)
    keys = Keys(clock, [(0.3, " "), (0.5, "q")])
    _run(attempt, lambda: sim, None, clock=clock, sleep=clock.advance, read_key=keys)
    assert sim.stops == 1


def test_view_shows_why_the_last_reconnect_attempt_failed(clock: FakeClock) -> None:
    class Dead(Sim):
        def read(self) -> list:  # type: ignore[type-arg]
            raise SourceError("device lost")

    class Refuses(Sim):
        def start(self) -> None:
            raise SourceError("Bluetooth is off")

    sources = iter([Dead(clock)])
    sup = StreamSupervisor(lambda: next(sources, Refuses(clock)), clock=clock)
    sup.start()
    sup.poll()
    clock.advance(1.1)
    sup.poll()
    assert sup.state is State.RECONNECTING
    out = io.StringIO()
    Console(file=out, width=100).print(_render(sup, LiveStats(), None))
    assert "Bluetooth is off" in out.getvalue()


# Console encoding --------------------------------------------------------------------------


def test_output_survives_a_cp1252_pipe(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("MuseS-TEST", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    writer.finalize()
    judge_lines = CHECKS["H4"].evaluate(load_session(writer.session_dir)).lines
    assert any("≥" in line for line in judge_lines)
    guide = Guide(cues=(Cue(0, "Keep still"), Cue(1, "Blink once")), duration=2.0)

    def show() -> None:
        out = Console(width=80)
        out.print(_guide_panel(guide, 1.5))
        for line in judge_lines:
            print(line)
        sys.stdout.flush()

    raw = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(raw, encoding="cp1252"))
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    with pytest.raises(UnicodeEncodeError):
        show()
    use_utf8_output()
    show()
    text = raw.getvalue().decode("utf-8")
    assert "▶" in text
    assert "≥" in text
    assert StreamKind.EEG.value in text


def test_utf8_switch_leaves_other_streams_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", io.StringIO())  # nothing to reconfigure
    use_utf8_output()


# Loss on the headset link ------------------------------------------------------------------


def test_recording_stores_and_inspect_shows_lost_subpackets(
    tmp_path: Path, clock: FakeClock
) -> None:
    class Lossy(Sim):
        @property
        def lost_subpackets(self) -> dict[StreamKind, int]:
            return {StreamKind.EEG: 4, StreamKind.MOTION: 0, StreamKind.OPTICS: 1}

    _record(tmp_path, clock, lambda: Lossy(clock), 0.5)
    session = _session(tmp_path)
    assert session.manifest["lost_subpackets"] == {"eeg": 4, "motion": 0, "optics": 1}
    shown = CliRunner().invoke(app, ["inspect", str(session.path)])
    assert shown.exit_code == 0, shown.output
    assert "subpackets lost on the headset link: eeg 4  motion 0  optics 1" in shown.output


def test_inspect_reads_a_session_from_before_lost_subpackets(
    tmp_path: Path, clock: FakeClock
) -> None:
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("MuseS-TEST", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    writer.finalize()
    shown = CliRunner().invoke(app, ["inspect", str(writer.session_dir)])
    assert shown.exit_code == 0, shown.output
    assert "subpackets" not in shown.output


def test_run_off_the_main_thread_leaves_signal_handlers_alone(
    tmp_path: Path, clock: FakeClock
) -> None:
    thread = threading.Thread(target=_record, args=(tmp_path, clock, lambda: Sim(clock), 0.5))
    thread.start()
    thread.join()
    assert _session(tmp_path).finalized


def test_guided_recording_piped_through_a_legacy_code_page(tmp_path: Path) -> None:
    guide_file = tmp_path / "guide.json"
    Guide(cues=(Cue(0, "Keep still"), Cue(0.1, "Blink once")), duration=0.3).save(guide_file)
    env = {**os.environ, "MUFUSE_GUIDE": str(guide_file), "PYTHONIOENCODING": "cp1252"}
    env.pop("PYTHONUTF8", None)
    command = [sys.executable, "-c", "from mufuse.cli import app; app()"]
    command += ["record", "--source", "sim", "--duration", "0.3", "--out", str(tmp_path / "rec")]
    done = subprocess.run(command, env=env, capture_output=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr.decode("utf-8", errors="replace")
    assert "✓" in done.stdout.decode("utf-8")
    assert _session(tmp_path / "rec").finalized
