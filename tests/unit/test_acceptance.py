from __future__ import annotations

import itertools
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
import pytest

from mufuse.acceptance import CHECKS, Result
from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import Chunk, DeviceInfo, FloatArray, StreamKind
from mufuse.guide import READY_S
from mufuse.recording.format import Gap, Marker
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock

DEVICE = DeviceInfo(name="MuseS-TEST", preset="p1041", driver="simulated")
RNG = np.random.default_rng(1)
EegShape = Callable[[FloatArray], FloatArray]  # relative times (n,) -> microvolts (n, 8)


def _quiet(rel: FloatArray) -> FloatArray:
    return RNG.normal(0, 15, (rel.size, 8))


def _record(
    tmp_path: Path,
    clock: FakeClock,
    spans: Sequence[tuple[float, float]],
    *,
    eeg: EegShape = _quiet,
    optics: EegShape | None = None,
    markers: Sequence[tuple[float, str, str]] = (),
    end: float | None = None,
    finalize: bool = True,
) -> LoadedSession:
    """Session with every stream present during `spans` (seconds after start), then gaps."""
    t0 = clock.now
    writer = SessionWriter.create(tmp_path, DEVICE, ATHENA_STREAMS, clock=clock)
    for kind, spec in ATHENA_STREAMS.items():
        for a, b in spans:
            rel = np.arange(round(a * spec.sampling_rate), round(b * spec.sampling_rate))
            rel = rel / spec.sampling_rate
            n_ch = len(spec.channel_names)
            if kind is StreamKind.EEG:
                data = eeg(rel)[:, :n_ch]
            elif kind is StreamKind.OPTICS and optics is not None:
                data = optics(rel)
            else:
                data = np.ones((rel.size, n_ch))
            writer.write([Chunk(kind, t0 + rel, data)])
    for (_, b), (c, _) in itertools.pairwise(spans):
        writer.add_gap(Gap("all", t0 + b - 1 / 256, t0 + c, "disconnect"))
    for at, label, source in markers:
        kind = "moment" if source == "keyboard" else "system"
        writer.add_marker(Marker(t0 + at, kind, label, source))  # type: ignore[arg-type]
    clock.advance(end if end is not None else spans[-1][1])
    if finalize:
        writer.finalize()
    else:
        writer.close_files()
    return load_session(writer.session_dir)


def _ok(result: Result) -> bool:
    print("\n".join(result.lines))
    return result.passed


@pytest.mark.parametrize("check", sorted(CHECKS))
def test_every_action_gets_a_ready_countdown(check: str) -> None:
    guide = CHECKS[check].guide()
    times = [c.at for c in guide.cues]
    assert times == sorted(times)
    assert times[0] >= 0
    assert times[-1] < guide.duration
    for cue in guide.cues:
        if cue.text.startswith(">>"):
            assert any(c.at == cue.at - READY_S and "Get ready" in c.text for c in guide.cues)


def test_h4_passes_a_complete_ten_minutes(tmp_path: Path, clock: FakeClock) -> None:
    assert _ok(CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 600)])))


def test_h4_fails_when_samples_are_missing(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 300), (305, 600)])))


def test_h4_fails_a_short_recording(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 120)])))


H5_MARKERS = [(20.0, "power_off", "system"), (30.0, "power_on", "system")]


def test_h5_passes_when_streaming_resumes_soon_after_power_on(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 21), (36, 75)], markers=H5_MARKERS)
    assert _ok(CHECKS["H5"].evaluate(session))


def test_h5_fails_when_resume_takes_longer_than_20_s(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 21), (60, 75)], markers=H5_MARKERS)
    assert not _ok(CHECKS["H5"].evaluate(session))


def test_h5_fails_when_no_gap_was_recorded(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(CHECKS["H5"].evaluate(_record(tmp_path, clock, [(0, 75)], markers=H5_MARKERS)))


def _presses(*ats: float) -> list[tuple[float, str, str]]:
    return [(at, "moment", "keyboard") for at in ats]


def test_h6_passes_three_presses_near_their_cues(tmp_path: Path, clock: FakeClock) -> None:
    cue_times = [c.at for c in CHECKS["H6"].guide().cues if c.marker]
    session = _record(tmp_path, clock, [(0, 40)], markers=_presses(*(t + 0.8 for t in cue_times)))
    assert _ok(CHECKS["H6"].evaluate(session))


def test_h6_fails_with_a_missing_press(tmp_path: Path, clock: FakeClock) -> None:
    cue_times = [c.at for c in CHECKS["H6"].guide().cues if c.marker]
    session = _record(
        tmp_path, clock, [(0, 40)], markers=_presses(*(t + 0.8 for t in cue_times[:2]))
    )
    assert not _ok(CHECKS["H6"].evaluate(session))


H7_CUE = [(15.0, "ctrl_c", "system")]


def test_h7_passes_a_session_stopped_after_the_ctrl_c_cue(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 16.5)], markers=H7_CUE)
    assert _ok(CHECKS["H7"].evaluate(session))


def test_h7_fails_when_nobody_pressed_ctrl_c(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, CHECKS["H7"].guide().duration)], markers=H7_CUE)
    assert not _ok(CHECKS["H7"].evaluate(session))


def test_h7_fails_an_unfinalized_session(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 16.5)], markers=H7_CUE, finalize=False)
    assert not _ok(CHECKS["H7"].evaluate(session))


def _h8_markers() -> list[tuple[float, str, str]]:
    return [(c.at, c.marker, "system") for c in CHECKS["H8"].guide().cues if c.marker]


def _h8_eeg(*, lift_goes_flat: bool) -> EegShape:
    phases = {label: at for at, label, _ in _h8_markers()}

    def shape(rel: FloatArray) -> FloatArray:
        x = RNG.normal(0, 15, (rel.size, 8))
        lift = (rel >= phases["lift_tp9"]) & (rel < phases["replace"])
        clench = (rel >= phases["clench"]) & (rel < phases["relax_jaw"])
        blink = (rel >= phases["blink"]) & (rel < phases["end"])
        if lift_goes_flat:
            x[lift, 0] = 0.0
        x[clench, 0] = RNG.normal(0, 200, int(clench.sum()))
        x[clench, 3] = RNG.normal(0, 200, int(clench.sum()))
        blinking = blink & ((rel % 1.0) < 0.25)
        x[blinking, 1:3] += 150.0
        return x

    return shape


def test_h8_passes_when_each_action_shows_up_on_the_right_channels(
    tmp_path: Path, clock: FakeClock
) -> None:
    duration = CHECKS["H8"].guide().duration
    session = _record(
        tmp_path, clock, [(0, duration)], eeg=_h8_eeg(lift_goes_flat=True), markers=_h8_markers()
    )
    assert _ok(CHECKS["H8"].evaluate(session))


def test_h8_fails_when_lifting_the_sensor_changes_nothing(tmp_path: Path, clock: FakeClock) -> None:
    duration = CHECKS["H8"].guide().duration
    session = _record(
        tmp_path, clock, [(0, duration)], eeg=_h8_eeg(lift_goes_flat=False), markers=_h8_markers()
    )
    result = CHECKS["H8"].evaluate(session)
    assert not _ok(result)
    assert any("µV" in line for line in result.lines)  # spreads reported for threshold tuning


def _f1_markers() -> list[tuple[float, str, str]]:
    return [(c.at, c.marker, "system") for c in CHECKS["F1"].guide().cues if c.marker]


def _f1_optics(ambient_rows: Sequence[int]) -> EegShape:
    """Rows are 1-based OPT numbers; LED rows carry a pulse on the head, ambient rows don't."""
    phases = {label: at for at, label, _ in _f1_markers()}
    amb = [r - 1 for r in ambient_rows]
    led = [i for i in range(16) if i not in amb]

    def shape(rel: FloatArray) -> FloatArray:
        x = np.zeros((rel.size, 17))
        on_head = rel < phases["room_light"]
        dark = (rel >= phases["dark"]) & (rel < phases["light_again"])
        x[:, led] = 3000.0
        x[:, amb] = 2000.0
        x[np.ix_(on_head, led)] = 1000.0 + 40 * np.sin(2 * np.pi * 1.2 * rel[on_head])[:, None]
        x[np.ix_(on_head, amb)] = 20.0
        x[np.ix_(dark, led)] = 400.0
        x[np.ix_(dark, amb)] = 8.0
        x[:, :16] += RNG.normal(0, 2, (rel.size, 16))
        x[:, 16] = 80.0  # battery
        return x

    return shape


def test_f1_confirms_brainflow_wire_order_when_rows_5_to_8_are_ambient(
    tmp_path: Path, clock: FakeClock
) -> None:
    duration = CHECKS["F1"].guide().duration
    session = _record(
        tmp_path, clock, [(0, duration)], optics=_f1_optics((5, 6, 7, 8)), markers=_f1_markers()
    )
    result = CHECKS["F1"].evaluate(session)
    assert _ok(result)
    assert any("wire order" in line for line in result.lines)


def test_f1_fails_when_ambient_shows_up_elsewhere(tmp_path: Path, clock: FakeClock) -> None:
    duration = CHECKS["F1"].guide().duration
    session = _record(
        tmp_path, clock, [(0, duration)], optics=_f1_optics((11, 12, 15, 16)), markers=_f1_markers()
    )
    result = CHECKS["F1"].evaluate(session)
    assert not _ok(result)
    assert any("libMuse order" in line for line in result.lines)
