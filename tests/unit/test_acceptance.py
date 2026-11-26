from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from mufuse.acceptance import BOOT_S, CHECKS, LABELS, Result, wearer_for, wearer_from_env
from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.signal_check import classify_channel
from mufuse.acquisition.simulated import CTRL_C, Wearer
from mufuse.acquisition.types import Chunk, DeviceInfo, FloatArray, StreamKind
from mufuse.guide import READY_S
from mufuse.recording.format import Gap, Marker, ReconnectStep
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import FakeClock

DEVICE = DeviceInfo(name="MuseS-TEST", preset="p1041", driver="simulated", firmware="3.1.19")
RNG = np.random.default_rng(1)
EegShape = Callable[[FloatArray], FloatArray]  # relative times (n,) -> microvolts (n, 8)
SUBPACKET = {StreamKind.EEG: 2, StreamKind.MOTION: 3, StreamKind.OPTICS: 1}  # samples in each

# Shaped like a real Athena at rest (firmware 3.1.19, preset p1041): 11-18 µV of scatter on a
# steady offset. The data is not centred, and the amplifier's range ends near ±725 µV.
REST_UV = np.array([11.0, 18.0, 11.0, 13.0, 20.0, 20.0, 20.0, 20.0])
OFFSET_UV = np.array([40.0, -60.0, 25.0, -15.0, 0.0, 0.0, 0.0, 0.0])


def _quiet(rel: FloatArray) -> FloatArray:
    return OFFSET_UV + RNG.normal(0, 1, (rel.size, 8)) * REST_UV


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
    device: DeviceInfo = DEVICE,
    lose: Mapping[StreamKind, int] | None = None,
    counter: bool | None = True,
    open_gap_at: float | None = None,
) -> LoadedSession:
    """Session with every stream present during `spans` (seconds after start), then gaps.

    `lose` drops one subpacket in every N of a stream. The headset's own loss counter reports
    them (`counter=True`), misses them (False, so the loss looks like the PC's), or is absent
    from the manifest (None, as in sessions written before it existed).
    """
    t0 = clock.now
    writer = SessionWriter.create(tmp_path, device, ATHENA_STREAMS, clock=clock)
    lost = dict.fromkeys(ATHENA_STREAMS, 0)
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
            if lose and kind in lose:
                every = lose[kind]
                keep = (np.arange(rel.size) // SUBPACKET[kind]) % every != every - 1
                if counter:
                    lost[kind] += int((~keep).sum()) // SUBPACKET[kind]
                rel, data = rel[keep], data[keep]
            writer.write([Chunk(kind, t0 + rel, data)])
    for (_, b), (c, _) in itertools.pairwise(spans):
        writer.add_gap(Gap("all", t0 + b - 1 / 256, t0 + c, "disconnect"))
    if open_gap_at is not None:
        writer.add_gap(Gap("all", t0 + open_gap_at, None, "stall"))
    for at, label, source in markers:
        kind = "moment" if source == "keyboard" else "system"
        writer.add_marker(Marker(t0 + at, kind, label, source))  # type: ignore[arg-type]
    clock.advance(end if end is not None else spans[-1][1])
    if finalize:
        writer.finalize(None if counter is None else lost)
    else:
        writer.close_files()
    return load_session(writer.session_dir)


def _ok(result: Result) -> bool:
    print("\n".join(result.lines))
    return result.passed


def _said(result: Result, text: str, tag: str = "") -> bool:
    """Whether a line of the verdict (optionally only [ok], [FAIL] or [info] ones) has `text`."""
    return any(text in line for line in result.lines if line.startswith(tag))


def _cue_markers(check: str) -> list[tuple[float, str, str]]:
    return [(c.at, c.marker, "system") for c in CHECKS[check].cues if c.marker]


def _at(check: str) -> dict[str, float]:
    return {c.marker: c.at for c in CHECKS[check].cues if c.marker}


# The run as a whole ---------------------------------------------------------------------------

STOPPABLE = [c for c in CHECKS if c != "H7"]  # H7 asks for the early stop


@pytest.mark.parametrize("check", STOPPABLE)
def test_a_recording_that_was_stopped_early_says_so_first(
    tmp_path: Path, clock: FakeClock, check: str
) -> None:
    session = _record(tmp_path, clock, [(0, 12)], markers=_cue_markers(check))
    result = CHECKS[check].evaluate(session)
    assert not _ok(result)
    assert result.lines[0] == (
        f"[FAIL] the recording was stopped after 12 s of {CHECKS[check].duration:.0f} s "
        "(q or Ctrl+C): retry"
    )


@pytest.mark.parametrize("check", STOPPABLE)
def test_a_recording_that_ran_its_time_is_not_called_stopped(
    tmp_path: Path, clock: FakeClock, check: str
) -> None:
    length = CHECKS[check].duration
    session = _record(tmp_path, clock, [(0, length)], markers=_cue_markers(check), end=length + 0.3)
    assert not _said(CHECKS[check].evaluate(session), "was stopped after")


def test_h7_is_not_told_that_its_ctrl_c_stopped_the_recording(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 16)], markers=_cue_markers("H7"))
    result = CHECKS["H7"].evaluate(session)
    assert _ok(result)
    assert not _said(result, "was stopped after")


def test_a_crashed_recording_is_not_called_stopped(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 12)], markers=_cue_markers("H6"), finalize=False)
    assert not _said(CHECKS["H6"].evaluate(session), "was stopped after")


@pytest.mark.parametrize("check", list(CHECKS))
def test_a_session_without_a_single_sample_says_so_first(
    tmp_path: Path, clock: FakeClock, check: str
) -> None:
    session = _record(
        tmp_path, clock, [(0, 0)], markers=_cue_markers(check), end=CHECKS[check].duration
    )
    result = CHECKS[check].evaluate(session)
    assert not _ok(result)
    assert result.lines[0] == (
        "[FAIL] no samples were recorded at all: the connection was made but nothing arrived; retry"
    )
    assert not _said(result, "was stopped after")


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


def test_the_default_run_starts_with_the_preflight_and_ends_hands_free() -> None:
    order = list(CHECKS)
    assert order[0] == "P0"
    assert order[-1] == "H4"  # ten minutes with nothing to do come last
    assert set(order) == {"P0", "H4", "H5", "H6", "H7", "H8", "F1"}


@pytest.mark.parametrize("check", sorted(CHECKS))
def test_every_briefing_tells_about_the_release_wait(check: str) -> None:
    assert any("wait" in line and "release" in line for line in CHECKS[check].before)


def test_briefings_warn_about_the_known_traps() -> None:
    h7 = " ".join(CHECKS["H7"].before)
    assert "once" in h7
    assert "do not hold it" in h7
    assert "do not click in the window" in h7
    assert "If text gets highlighted, press Esc" in h7
    h5 = " ".join(CHECKS["H5"].before)
    assert "freeze for up to 15 s" in h5
    assert "press nothing" in h5
    h4 = " ".join(CHECKS["H4"].before)
    assert "worn or lie switched on within 2 m" in h4
    assert "nothing to do" in h4


# P0: preflight --------------------------------------------------------------------------------


def _p0_optics(battery: float) -> EegShape:
    def shape(rel: FloatArray) -> FloatArray:
        x = np.full((rel.size, 17), 5000.0) + RNG.normal(0, 30, (rel.size, 17))
        x[:, 16] = np.where(rel < 10, 0.0, battery)  # the level reads 0 for the first seconds
        return x

    return shape


def _p0_eeg(still: EegShape = _quiet) -> EegShape:
    """Wild while the headband is being adjusted, then `still`."""
    start = _at("P0")["still"]

    def shape(rel: FloatArray) -> FloatArray:
        x = still(rel)
        adjusting = rel < start - 2
        x[adjusting] = RNG.normal(0, 250, (int(adjusting.sum()), 8))
        return x

    return shape


def _p0(tmp_path: Path, clock: FakeClock, **how: object) -> Result:
    args: dict[str, object] = {"eeg": _p0_eeg(), "optics": _p0_optics(80.0)} | how
    session = _record(tmp_path, clock, [(0, CHECKS["P0"].duration)], **args)  # type: ignore[arg-type]
    return CHECKS["P0"].evaluate(session)


def test_p0_passes_a_charged_headband_that_fits(tmp_path: Path, clock: FakeClock) -> None:
    result = _p0(tmp_path, clock)
    assert _ok(result)
    assert _said(result, "firmware 3.1.19", "[info]")
    assert _said(result, "battery 80%", "[ok]")
    assert result.measures["battery_pct"] == 80.0
    assert result.measures["still.TP9.std_uv"] == pytest.approx(11, abs=2)
    assert result.measures["eeg.completeness_pct"] == 100.0


def test_p0_fails_a_low_battery_and_says_to_charge(tmp_path: Path, clock: FakeClock) -> None:
    result = _p0(tmp_path, clock, optics=_p0_optics(15.0))
    assert not _ok(result)
    assert _said(result, "charge first: the full sitting takes about half an hour", "[FAIL]")


def test_p0_does_not_fail_a_battery_level_that_was_never_reported(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _p0(tmp_path, clock, optics=_p0_optics(0.0))
    assert _ok(result)
    assert _said(result, "battery level was not reported", "[info]")


@pytest.mark.parametrize(
    ("firmware", "note"),
    [(None, "firmware was not reported"), ("3.2.0", "newer than 3.1.29")],
)
def test_p0_notes_an_unknown_or_newer_firmware_without_failing(
    tmp_path: Path, clock: FakeClock, firmware: str | None, note: str
) -> None:
    result = _p0(tmp_path, clock, device=replace(DEVICE, firmware=firmware))
    assert _ok(result)
    assert _said(result, note, "[info]")


def test_p0_fails_a_stream_well_under_its_nominal_rate(tmp_path: Path, clock: FakeClock) -> None:
    result = _p0(tmp_path, clock, lose={StreamKind.MOTION: 10})
    assert not _ok(result)
    assert _said(result, "motion 90.", "[FAIL]")


def test_p0_passes_but_warns_when_a_stream_would_fail_h4(tmp_path: Path, clock: FakeClock) -> None:
    result = _p0(tmp_path, clock, lose={StreamKind.EEG: 140})
    assert _ok(result)
    assert _said(result, "H4 is at risk", "[info]")


def _loose(channel: int) -> EegShape:
    """A sensor without skin contact, as the Athena's unconnected inputs look in real data:
    a steady level with a sharp dip towards the bottom of the range every 12 samples."""

    def shape(rel: FloatArray) -> FloatArray:
        x = _quiet(rel)
        x[:, channel] = _floating(rel.size)
        return x

    return shape


def _floating(n: int) -> FloatArray:
    x = 110 + RNG.normal(0, 10, n)
    dip = np.arange(n) % 12 < 3
    x[dip] = RNG.uniform(-620, -430, int(dip.sum()))
    return x


def _noisy(channel: int) -> EegShape:
    def shape(rel: FloatArray) -> FloatArray:
        x = _quiet(rel)
        x[:, channel] = RNG.normal(0, 120, rel.size)
        return x

    return shape


def test_a_floating_input_looks_ok_to_the_live_indicator() -> None:
    x = _floating(512)
    assert classify_channel(x - x.mean()) == "ok"  # why the judges cannot rely on the label alone


@pytest.mark.parametrize(
    ("still", "sensor"),
    [(_noisy(3), "TP10 (right ear)"), (_loose(0), "TP9 (left ear)")],
)
def test_p0_names_the_sensor_that_does_not_sit_well(
    tmp_path: Path, clock: FakeClock, still: EegShape, sensor: str
) -> None:
    result = _p0(tmp_path, clock, eeg=_p0_eeg(still))
    assert not _ok(result)
    failed = [line for line in result.lines if line.startswith("[FAIL]")]
    assert len(failed) == 1
    assert sensor in failed[0]


# H4 / SC-002 ----------------------------------------------------------------------------------


def test_h4_passes_a_complete_ten_minutes(tmp_path: Path, clock: FakeClock) -> None:
    result = CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 600)]))
    assert _ok(result)
    assert result.measures["eeg.completeness_pct"] == 100.0
    assert result.measures["eeg.rate_hz"] == pytest.approx(256.0)
    assert result.measures["optics.rate_hz"] == pytest.approx(64.0)


def test_h4_keeps_the_eeg_numbers_of_the_whole_recording_without_judging_them(
    tmp_path: Path, clock: FakeClock
) -> None:
    short = replace(CHECKS["H4"], duration=60.0)
    result = short.evaluate(_record(tmp_path, clock, [(0, 60)]))
    assert _ok(result)
    m = result.measures
    assert m["whole.TP9.spread_uv"] == pytest.approx(11, abs=2)
    assert m["whole.TP9.spread_p05_uv"] < m["whole.TP9.spread_uv"] < m["whole.TP9.spread_p95_uv"]
    assert m["whole.AF7.ok_share"] == 1.0
    assert _said(result, "over the whole recording", "[info]")
    assert not _said(result, "over the whole recording", "[ok]")


def test_h4_fails_when_samples_are_missing(tmp_path: Path, clock: FakeClock) -> None:
    result = CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 300), (305, 600)]))
    assert not _ok(result)
    assert _said(result, "gap at +300.0 s for 5.0 s", "[info]")
    assert not _said(result, "decision for the spec")


def test_h4_fails_a_short_recording(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(CHECKS["H4"].evaluate(_record(tmp_path, clock, [(0, 120)])))


def test_h4_says_plainly_when_only_the_headset_lost_samples(
    tmp_path: Path, clock: FakeClock
) -> None:
    # Published loss on the headset link: about 1 EEG subpacket in 140 never leaves the headband.
    session = _record(tmp_path, clock, [(0, 600)], lose={StreamKind.EEG: 140})
    result = CHECKS["H4"].evaluate(session)
    assert not _ok(result)  # SC-002 as written: still a FAIL
    assert _said(result, "eeg 99.29% complete", "[FAIL]")
    assert _said(result, "lost on the headset link", "[info]")
    assert _said(result, "decision for the spec", "[info]")
    assert result.measures["eeg.rate_hz"] == pytest.approx(254.2, abs=0.1)
    assert result.measures["eeg.lost_on_pc"] == 0
    assert result.measures["eeg.lost_on_headset"] == pytest.approx(1096, abs=4)


@pytest.mark.parametrize("counter", [False, None])
def test_h4_does_not_blame_the_headset_without_its_counter(
    tmp_path: Path, clock: FakeClock, counter: bool | None
) -> None:
    session = _record(tmp_path, clock, [(0, 600)], lose={StreamKind.EEG: 140}, counter=counter)
    result = CHECKS["H4"].evaluate(session)
    assert not _ok(result)
    assert not _said(result, "decision for the spec")


# H5 / SC-003 ----------------------------------------------------------------------------------

H5_MARKERS = [(20.0, "power_off", "system"), (30.0, "power_on", "system")]


def _h5(tmp_path: Path, clock: FakeClock, spans: Sequence[tuple[float, float]]) -> Result:
    session = _record(tmp_path, clock, spans, markers=H5_MARKERS, end=CHECKS["H5"].duration)
    return CHECKS["H5"].evaluate(session)


def test_h5_passes_when_streaming_resumes_soon_after_power_on(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h5(tmp_path, clock, [(0, 21), (36, 75)])
    assert _ok(result)
    assert result.measures["resume_s"] == pytest.approx(6.0)
    assert result.measures["gap_s"] == pytest.approx(15.0, abs=0.01)
    assert result.measures["hole_s"] == pytest.approx(15.0, abs=0.01)


def test_h5_fails_when_resume_takes_longer_than_20_s(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(_h5(tmp_path, clock, [(0, 21), (60, 75)]))


def test_h5_fails_an_idle_wearer_and_says_nothing_was_interrupted(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h5(tmp_path, clock, [(0, 75)])
    assert not _ok(result)
    assert _said(result, "no interruption was seen at all", "[FAIL]")


def test_h5_says_when_the_headband_never_came_back(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(
        tmp_path, clock, [(0, 21)], markers=H5_MARKERS, end=75, open_gap_at=21 - 1 / 256
    )
    result = CHECKS["H5"].evaluate(session)
    assert not _ok(result)
    assert _said(result, "the headband never came back (open gap from +21.0 s)", "[FAIL]")
    assert not _said(result, "no interruption was seen at all")


def test_h5_judges_the_gap_at_the_off_cue_not_a_longer_one_later(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h5(tmp_path, clock, [(0, 21), (33, 45), (58, 75)])
    assert _ok(result)
    assert result.measures["resume_s"] == pytest.approx(3.0)
    assert _said(result, "other gap at +45.0 s for 13.0 s", "[info]")


def test_h5_does_not_fail_switching_back_on_early(tmp_path: Path, clock: FakeClock) -> None:
    result = _h5(tmp_path, clock, [(0, 20.5), (29, 75)])
    assert _ok(result)
    assert _said(result, "before the power-on cue", "[info]")


def test_h5_fails_a_blip_too_short_to_be_a_power_cycle(tmp_path: Path, clock: FakeClock) -> None:
    result = _h5(tmp_path, clock, [(0, 21), (25, 75)])
    assert not _ok(result)
    assert _said(result, "need ≥ 8 s", "[FAIL]")


def test_h5_fails_when_the_only_gap_is_far_from_the_off_cue(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h5(tmp_path, clock, [(0, 45), (58, 75)])
    assert not _ok(result)
    assert _said(result, "no interruption started near the power-off cue", "[FAIL]")
    assert _said(result, "other gap at +45.0 s", "[info]")


def test_h5_fails_when_the_recorded_gap_does_not_match_the_hole_in_the_data(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 21), (36, 75)], markers=H5_MARKERS, end=75)
    (gap,) = session.gaps
    # gaps.jsonl says the signal stopped 2 s before the data does: 17 s against a hole of 15 s.
    result = CHECKS["H5"].evaluate(replace(session, gaps=[replace(gap, start=gap.start - 2.0)]))
    assert not _ok(result)
    failed = [line for line in result.lines if line.startswith("[FAIL]")]
    assert len(failed) == 1
    assert "recorded gap 17.00 s vs hole in the EEG data 15.00 s" in failed[0]


def test_h5_shows_where_the_time_away_went(tmp_path: Path, clock: FakeClock) -> None:
    t0 = clock.now
    session = _record(tmp_path, clock, [(0, 21), (53.5, 75)], markers=H5_MARKERS, end=75)
    steps = [
        ReconnectStep(t0 + 24.0, "lost", "stall"),
        ReconnectStep(t0 + 24.1, "released"),
        ReconnectStep(t0 + 25.0, "attempt"),
        ReconnectStep(t0 + 41.0, "failed", "no device"),
        ReconnectStep(t0 + 41.1, "attempt"),
        ReconnectStep(t0 + 46.4, "connected"),
        ReconnectStep(t0 + 53.5, "first_sample"),
    ]
    result = CHECKS["H5"].evaluate(replace(session, reconnects=steps))
    assert not _ok(result)  # back 23.5 s after the cue: the lines below say which stage took it
    said = [line for line in result.lines if line.startswith("[info] reconnect")]
    assert said == [
        "[info] reconnect +24.0 s (-6.0 s from the power-on cue): the signal counted as lost "
        "(stall)",
        "[info] reconnect +24.1 s (-5.9 s from the power-on cue): the old connection was let go",
        "[info] reconnect +25.0 s (-5.0 s from the power-on cue): an attempt to connect began",
        "[info] reconnect +41.0 s (+11.0 s from the power-on cue): that attempt failed (no device)",
        "[info] reconnect +41.1 s (+11.1 s from the power-on cue): an attempt to connect began",
        "[info] reconnect +46.4 s (+16.4 s from the power-on cue): connected",
        "[info] reconnect +53.5 s (+23.5 s from the power-on cue): the first sample arrived",
    ]
    assert not _said(result, "about 3 s")  # measured now, not estimated


def test_h5_shows_the_attempts_when_the_headband_never_came_back(
    tmp_path: Path, clock: FakeClock
) -> None:
    t0 = clock.now
    session = _record(
        tmp_path, clock, [(0, 21)], markers=H5_MARKERS, end=75, open_gap_at=21 - 1 / 256
    )
    steps = [ReconnectStep(t0 + 25.0, "attempt"), ReconnectStep(t0 + 41.0, "failed", "no device")]
    result = CHECKS["H5"].evaluate(replace(session, reconnects=steps))
    assert _said(result, "the headband never came back", "[FAIL]")
    assert _said(result, "+41.0 s (+11.0 s from the power-on cue): that attempt failed", "[info]")


# H6 / SC-004 ----------------------------------------------------------------------------------


def _h6(tmp_path: Path, clock: FakeClock, presses: Sequence[float]) -> Result:
    markers = [(at, "moment", "keyboard") for at in presses]
    return CHECKS["H6"].evaluate(_record(tmp_path, clock, [(0, 40)], markers=markers))


H6_CUES = sorted(_at("H6").values())


def test_h6_passes_three_presses_near_their_cues(tmp_path: Path, clock: FakeClock) -> None:
    result = _h6(tmp_path, clock, [t + 0.8 for t in H6_CUES])
    assert _ok(result)
    assert result.measures["press_2.offset_s"] == pytest.approx(0.8)


def test_h6_fails_with_a_missing_press(tmp_path: Path, clock: FakeClock) -> None:
    assert not _ok(_h6(tmp_path, clock, [t + 0.8 for t in H6_CUES[:2]]))


def test_h6_fails_an_idle_wearer(tmp_path: Path, clock: FakeClock) -> None:
    result = _h6(tmp_path, clock, [])
    assert not _ok(result)
    assert sum(line.startswith("[FAIL]") for line in result.lines) == 3


def test_h6_counts_one_press_per_cue_and_reports_the_extra_ones(
    tmp_path: Path, clock: FakeClock
) -> None:
    double_tap = [H6_CUES[0] + 0.8, H6_CUES[0] + 1.0, H6_CUES[1] + 0.8, H6_CUES[2] + 0.8, 38.0]
    result = _h6(tmp_path, clock, double_tap)
    assert _ok(result)
    assert _said(result, "2 extra", "[info]")
    assert result.measures["press_1.offset_s"] == pytest.approx(0.8)


def test_h6_does_not_let_one_press_serve_two_cues(tmp_path: Path, clock: FakeClock) -> None:
    between = (H6_CUES[0] + H6_CUES[1]) / 2 + 1.0  # inside both the first and the second window
    assert not _ok(_h6(tmp_path, clock, [between, H6_CUES[2]]))


@pytest.mark.parametrize("third", [H6_CUES[2] - READY_S - 0.5, H6_CUES[2] + 5.5])
def test_h6_fails_a_press_outside_the_window_of_its_cue(
    tmp_path: Path, clock: FakeClock, third: float
) -> None:
    result = _h6(tmp_path, clock, [H6_CUES[0] + 0.8, H6_CUES[1] + 0.8, third])
    assert not _ok(result)
    assert _said(result, "press 3: none in its window", "[FAIL]")
    assert _said(result, "3 SPACE markers, 1 extra", "[info]")


# H7 / SC-005 ----------------------------------------------------------------------------------

H7_CUE = [(15.0, "ctrl_c", "system")]


def test_h7_passes_a_session_stopped_after_the_ctrl_c_cue(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 16.5)], markers=H7_CUE)
    result = CHECKS["H7"].evaluate(session)
    assert _ok(result)
    assert result.measures["stopped_offset_s"] == pytest.approx(1.5)


def test_h7_fails_when_nobody_pressed_ctrl_c(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, CHECKS["H7"].guide().duration)], markers=H7_CUE)
    assert not _ok(CHECKS["H7"].evaluate(session))


def test_h7_fails_an_unfinalized_session(tmp_path: Path, clock: FakeClock) -> None:
    session = _record(tmp_path, clock, [(0, 16.5)], markers=H7_CUE, finalize=False)
    assert not _ok(CHECKS["H7"].evaluate(session))


# H8 -------------------------------------------------------------------------------------------


def _h8_eeg(
    *, lift: str = "floating", clench: str = "steady", lifted: int = 0, rest_flat: bool = False
) -> EegShape:
    """What the cues do to the signal. The wearer reacts half a second after each cue.

    lift: "floating" (the real unconnected-input shape), "rail" (pinned at the top of the range
    most of the time), "flat" or "none". clench: "steady" (60 µV, a moderate clench), "pulsed"
    (strong, but only half of each second) or "none". Blinks are large: 300 µV for 0.4 s.
    """
    at = _at("H8")

    def shape(rel: FloatArray) -> FloatArray:
        def during(start: str, end: str) -> np.ndarray:
            return (rel >= at[start] + 0.5) & (rel < at[end])

        x = _quiet(rel)
        up = during("lift_tp9", "replace")
        n = int(up.sum())
        if lift == "floating":
            x[up, lifted] = _floating(n)
        elif lift == "rail":
            x[up, lifted] = np.where(RNG.random(n) < 0.55, 724.96, RNG.uniform(640, 680, n))
        elif lift == "flat":
            x[up, lifted] = 0.0
        if rest_flat:
            x[rel < at["lift_tp9"], lifted] = 0.0
        jaw = during("clench", "relax_jaw")
        if clench == "pulsed":
            jaw &= (rel % 1.0) < 0.5
        if clench != "none":
            for ear in (0, 3):
                x[jaw, ear] += RNG.normal(0, 60 if clench == "steady" else 200, int(jaw.sum()))
        blinking = during("blink", "end") & ((rel % 1.0) < 0.4)
        x[blinking, 1:3] += 300.0
        return x

    return shape


def _h8(tmp_path: Path, clock: FakeClock, **how: object) -> Result:
    session = _record(
        tmp_path,
        clock,
        [(0, CHECKS["H8"].duration)],
        eeg=_h8_eeg(**how),  # type: ignore[arg-type]
        markers=_cue_markers("H8"),
    )
    return CHECKS["H8"].evaluate(session)


@pytest.mark.parametrize("lift", ["floating", "rail", "flat"])
def test_h8_passes_however_the_lifted_sensor_shows_up(
    tmp_path: Path, clock: FakeClock, lift: str
) -> None:
    result = _h8(tmp_path, clock, lift=lift)
    assert _ok(result)
    assert _said(result, "changed most while lifting: TP9", "[info]")


def test_h8_passes_a_clench_that_comes_in_bursts(tmp_path: Path, clock: FakeClock) -> None:
    assert _ok(_h8(tmp_path, clock, clench="pulsed"))


def test_h8_fails_only_the_lift_when_lifting_changes_nothing(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h8(tmp_path, clock, lift="none")
    assert not _ok(result)
    failed = [line for line in result.lines if line.startswith("[FAIL]")]
    assert len(failed) == 1
    assert "lifting" in failed[0]
    assert "µV" in failed[0]  # the numbers the verdict was made from
    assert _said(result, "no channel changed while lifting", "[info]")


def test_h8_fails_only_the_clench_when_the_jaw_stays_relaxed(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h8(tmp_path, clock, clench="none")
    assert not _ok(result)
    failed = [line for line in result.lines if line.startswith("[FAIL]")]
    assert len(failed) == 1
    assert "jaw clench" in failed[0]


def test_h8_names_the_other_ear_when_that_one_changed(tmp_path: Path, clock: FakeClock) -> None:
    result = _h8(tmp_path, clock, lifted=3)
    assert not _ok(result)
    assert _said(result, "changed most while lifting: TP10", "[info]")
    assert _said(result, "left and right", "[info]")


def test_h8_fails_a_sensor_that_already_looked_lifted_at_rest(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h8(tmp_path, clock, lift="flat", rest_flat=True)
    assert not _ok(result)
    assert _said(result, "at rest", "[FAIL]")


def test_h8_fails_a_channel_that_goes_flat_while_blinking(tmp_path: Path, clock: FakeClock) -> None:
    at = _at("H8")
    following = _h8_eeg()

    def shape(rel: FloatArray) -> FloatArray:
        x = following(rel)
        x[rel >= at["blink"], 2] = 0.0  # AF8 loses its signal for the whole blink phase
        return x

    session = _record(
        tmp_path, clock, [(0, CHECKS["H8"].duration)], eeg=shape, markers=_cue_markers("H8")
    )
    result = CHECKS["H8"].evaluate(session)
    assert not _ok(result)
    failed = [line for line in result.lines if line.startswith("[FAIL]")]
    assert len(failed) == 1
    assert "no channel went flat or railed: AF8 did in 100% of windows" in failed[0]


def test_h8_keeps_the_numbers_and_reports_labels_and_blinks(
    tmp_path: Path, clock: FakeClock
) -> None:
    result = _h8(tmp_path, clock)
    m = result.measures
    assert m["rest.TP9.std_uv"] == pytest.approx(11, abs=2)
    assert m["rest.AF7.spread_uv"] == pytest.approx(18, abs=4)
    assert m["rest.TP9.ptp_uv"] > 40
    assert m["rest.TP9.rail_share"] == 0.0
    assert m["rest.TP9.mains_50hz_share"] < 0.1
    assert m["rest.TP9.mains_60hz_share"] < 0.1
    assert m["lift.TP9.std_uv"] > 150
    assert m["lift.TP9.changed_share"] == 1.0
    assert m["lift.TP10.changed_share"] == 0.0
    assert m["clench.TP10.std_uv"] > 3 * m["rest.TP10.std_uv"]
    assert 7 <= m["blink.AF7.deflections"] <= 10
    assert m["blink.AF8.deflection_uv"] == pytest.approx(300, abs=80)
    assert _said(result, "labels at rest: TP9 ok 100%", "[info]")
    assert _said(result, "blink-like deflections", "[info]")


def test_h8_keeps_the_spread_percentiles_and_every_label_share_for_calibration(
    tmp_path: Path, clock: FakeClock
) -> None:
    m = _h8(tmp_path, clock, lift="flat").measures
    for phase in ("rest", "lift", "clench", "blink"):
        for ch in ("TP9", "AF7", "AF8", "TP10"):
            low, mid, high = (m[f"{phase}.{ch}.spread{p}_uv"] for p in ("_p05", "", "_p95"))
            assert low <= mid <= high
            shares = [m[f"{phase}.{ch}.{label}_share"] for label in LABELS]
            assert sum(shares) == pytest.approx(1.0, abs=1e-3)
    assert m["rest.TP9.spread_p95_uv"] < m["clench.TP9.spread_p05_uv"]  # 11 µV against 60 more
    assert m["lift.TP9.flat_share"] == 1.0
    assert m["lift.TP9.ok_share"] == 0.0
    assert m["rest.TP9.noisy_share"] == 0.0


def test_every_check_keeps_the_last_battery_level_its_recording_saw(
    tmp_path: Path, clock: FakeClock
) -> None:
    def draining(rel: FloatArray) -> FloatArray:
        x = np.full((rel.size, 17), 5000.0)
        x[:, 16] = np.where(rel < 10, 0.0, np.where(rel < 30, 64.0, 63.0))
        return x

    session = _record(tmp_path, clock, [(0, 40)], optics=draining, markers=_cue_markers("H6"))
    assert CHECKS["H6"].evaluate(session).measures["battery_end_pct"] == 63.0
    p0 = _p0(tmp_path / "p0", clock, optics=draining)
    assert (p0.measures["battery_pct"], p0.measures["battery_end_pct"]) == (64.0, 63.0)


def test_a_battery_level_that_was_never_reported_is_not_kept(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 40)], optics=_p0_optics(0.0))
    assert "battery_end_pct" not in CHECKS["H6"].evaluate(session).measures


def test_h8_fails_a_recording_that_stopped_before_the_last_phase(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 30)], eeg=_h8_eeg(), markers=_cue_markers("H8"))
    assert not _ok(CHECKS["H8"].evaluate(session))


# F1: optics ambient rows ----------------------------------------------------------------------

# Levels shaped like a real Athena on the head (wire order OPT1-16, firmware 3.1.19): the
# ambient rows OPT5-8 sit on a pedestal near 338 000 counts, whatever the light.
HEAD = np.array(
    [
        *(100_800, 103_000, 520, 500),  # red
        *(339_800, 335_900, 339_600, 335_800),  # ambient
        *(160_200, 160_800, 57_800, 72_400),  # 730 nm
        *(151_100, 138_600, 22_000, 28_000),  # 850 nm
    ],
    dtype=np.float64,
)
NOISE = np.array([95, 128, 23, 24, 41, 29, 41, 27, 262, 238, 1226, 498, 276, 339, 677, 320.0])
AMB = [4, 5, 6, 7]
LED = [i for i in range(16) if i not in AMB]
LIBMUSE = [0, 1, 2, 3, 10, 11, 14, 15, 8, 9, 4, 5, 12, 13, 6, 7]  # ambient at OPT11, 12, 15, 16


def _f1_optics(
    *,
    light: float = 3000.0,
    led: str = "hand",
    leak: float = 0.0,
    order: Sequence[int] = range(16),
    taken_off: bool = True,
) -> EegShape:
    """Counts per row through the four phases. `light` is what room light adds to an ambient row.

    The LED rows off the head are not known from real data, so three models: "hand" (little
    light, and a covering hand reflects 60% of the on-head level), "cloth" (near zero, dark
    cloth) and "ambient" (they also carry the room light; dark cloth).
    """
    at = _at("F1")
    lit_led = {"hand": 300.0, "cloth": 30.0, "ambient": light + 300.0}[led]

    def shape(rel: FloatArray) -> FloatArray:
        x = np.tile(HEAD, (rel.size, 1))
        if taken_off:
            off_head = rel >= at["room_light"]
            covered = (rel >= at["dark"]) & (rel < at["light_again"])
            x[np.ix_(off_head, LED)] = lit_led
            x[np.ix_(off_head, AMB)] += light
            x[np.ix_(covered, LED)] = HEAD[LED] * 0.6 if led == "hand" else 12.0
            x[np.ix_(covered, AMB)] = HEAD[AMB] + leak
        x += RNG.normal(0, 1, x.shape) * NOISE
        on_head = rel < at["room_light"]
        x[np.ix_(on_head, LED)] += 0.002 * HEAD[LED] * np.sin(2 * np.pi * 1.2 * rel[on_head, None])
        return np.column_stack([x[:, order], np.full(rel.size, 80.0)])

    return shape


def _f1(tmp_path: Path, clock: FakeClock, optics: EegShape | None) -> Result:
    session = _record(
        tmp_path, clock, [(0, CHECKS["F1"].duration)], optics=optics, markers=_cue_markers("F1")
    )
    return CHECKS["F1"].evaluate(session)


@pytest.mark.parametrize("led", ["hand", "cloth", "ambient"])
def test_f1_confirms_wire_order_on_top_of_the_ambient_pedestal(
    tmp_path: Path, clock: FakeClock, led: str
) -> None:
    result = _f1(tmp_path, clock, _f1_optics(led=led))
    assert _ok(result)
    assert _said(result, "wire order", "[ok]")
    assert result.measures["on_head.OPT5.median"] == pytest.approx(339_800, abs=30)
    assert result.measures["dark.OPT5.median"] == pytest.approx(339_800, abs=30)
    assert result.measures["room_light.OPT5.median"] == pytest.approx(342_800, abs=30)
    for phase in ("on head", "room light", "covered", "light again"):
        assert _said(result, f"{phase}: 1:", "[info]")  # medians of all 16 rows, every time


def test_f1_passes_when_a_weak_led_row_also_picks_up_room_light(
    tmp_path: Path, clock: FakeClock
) -> None:
    # OPT3 and OPT4 sit near their offset on the head (about 500 counts). Covered they read the
    # same, and off the head the room light adds to them: they behave as ambient rows too.
    at = _at("F1")
    base = _f1_optics()

    def shape(rel: FloatArray) -> FloatArray:
        x = base(rel)
        covered = (rel >= at["dark"]) & (rel < at["light_again"])
        lit = (rel >= at["room_light"]) & ~covered
        for row in (2, 3):
            x[:, row] = HEAD[row] + RNG.normal(0, NOISE[row], rel.size) + np.where(lit, 3000.0, 0)
        return x

    result = _f1(tmp_path, clock, shape)
    assert _ok(result)
    assert _said(result, "OPT5, OPT6, OPT7, OPT8: BrainFlow wire order", "[ok]")
    assert _said(result, "OPT3, OPT4 also behaved as ambient light", "[info]")
    assert [n for n in range(1, 17) if result.measures[f"ambient.OPT{n}"]] == [3, 4, 5, 6, 7, 8]


def test_f1_fails_when_a_libmuse_ambient_row_qualifies_beside_the_wire_ones(
    tmp_path: Path, clock: FakeClock
) -> None:
    at = _at("F1")
    base = _f1_optics()

    def shape(rel: FloatArray) -> FloatArray:
        x = base(rel)
        covered = (rel >= at["dark"]) & (rel < at["light_again"])
        lit = (rel >= at["room_light"]) & ~covered
        x[:, 10] = HEAD[10] + RNG.normal(0, NOISE[10], rel.size) + np.where(lit, 9000.0, 0)
        return x

    result = _f1(tmp_path, clock, shape)
    assert not _ok(result)
    assert _said(result, "OPT5, OPT6, OPT7, OPT8, OPT11: neither known order", "[FAIL]")


def test_f1_fails_and_names_libmuse_order(tmp_path: Path, clock: FakeClock) -> None:
    result = _f1(tmp_path, clock, _f1_optics(order=LIBMUSE))
    assert not _ok(result)
    assert _said(result, "OPT11, OPT12, OPT15, OPT16", "[FAIL]")
    assert _said(result, "libMuse order", "[FAIL]")


def test_f1_keeps_which_rows_behaved_as_ambient_light(tmp_path: Path, clock: FakeClock) -> None:
    wire = _f1(tmp_path / "wire", clock, _f1_optics()).measures
    assert [n for n in range(1, 17) if wire[f"ambient.OPT{n}"]] == [5, 6, 7, 8]

    libmuse = _f1(tmp_path / "libmuse", clock, _f1_optics(order=LIBMUSE)).measures
    assert [n for n in range(1, 17) if libmuse[f"ambient.OPT{n}"]] == [11, 12, 15, 16]


def test_f1_fails_an_idle_wearer_who_kept_the_headband_on(tmp_path: Path, clock: FakeClock) -> None:
    result = _f1(tmp_path, clock, _f1_optics(taken_off=False))
    assert not _ok(result)
    assert _said(result, "face a lamp or a window", "[FAIL]")


def test_f1_says_when_the_optics_stream_is_flat(tmp_path: Path, clock: FakeClock) -> None:
    result = _f1(tmp_path, clock, None)  # every row constant
    assert not _ok(result)
    assert _said(result, "optics stream is flat; check the preset and reconnect", "[FAIL]")


def test_f1_says_when_the_room_light_is_too_dim(tmp_path: Path, clock: FakeClock) -> None:
    result = _f1(tmp_path, clock, _f1_optics(light=500.0))
    assert not _ok(result)
    assert _said(result, "rose only about 500 counts", "[FAIL]")
    assert _said(result, "face a lamp or a window", "[FAIL]")


def test_f1_says_when_the_cover_leaked_light(tmp_path: Path, clock: FakeClock) -> None:
    result = _f1(tmp_path, clock, _f1_optics(light=5000.0, leak=4500.0))
    assert not _ok(result)
    assert _said(result, "the cover let light through", "[FAIL]")


def test_f1_fails_a_recording_that_stopped_before_the_last_phase(
    tmp_path: Path, clock: FakeClock
) -> None:
    session = _record(tmp_path, clock, [(0, 60)], optics=_f1_optics(), markers=_cue_markers("F1"))
    assert not _ok(CHECKS["F1"].evaluate(session))


# The simulated wearer's script ------------------------------------------------------------


def test_the_script_for_a_check_follows_its_cues_a_reaction_late() -> None:
    h8 = wearer_for(CHECKS["H8"], react=1.0)
    assert h8.lifted == ((16.0, 26.0, "TP9"),)
    assert h8.clench == ((36.0, 44.0),)
    assert h8.blinks == ((51.0, 61.0),)
    assert wearer_for(CHECKS["H6"], react=0.5).keys == ((10.5, " "), (18.5, " "), (26.5, " "))
    assert wearer_for(CHECKS["H7"], react=3.0).keys == ((18.0, CTRL_C),)
    assert wearer_for(CHECKS["H5"], react=1.0).off == ((21.0, 31.0 + BOOT_S),)
    assert wearer_for(CHECKS["F1"], react=2.0).optics == (
        (32.0, "light"),
        (57.0, "covered"),
        (82.0, "light"),
    )
    assert wearer_for(CHECKS["P0"]).lifted == ((0.0, 16.0, "TP9"),)  # adjusting, then still
    assert wearer_for(CHECKS["H4"]) == Wearer()  # nothing to do


@pytest.mark.parametrize("check_id", list(CHECKS))
def test_an_idle_wearer_keeps_the_headband_on_and_does_nothing(check_id: str) -> None:
    assert wearer_for(CHECKS[check_id], idle=True) == Wearer()


def test_the_wearer_is_chosen_by_an_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MUFUSE_SIM_WEARER", raising=False)
    assert wearer_from_env() is None
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "h8")
    assert wearer_from_env() == wearer_for(CHECKS["H8"])
    monkeypatch.setenv("MUFUSE_SIM_WEARER", "H5:idle")
    assert wearer_from_env() == Wearer()


@pytest.mark.parametrize("value", ["H9", "H8:asleep", ":idle"])
def test_an_unknown_wearer_is_refused_with_the_choices(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("MUFUSE_SIM_WEARER", value)
    with pytest.raises(ValueError, match=r"P0, H8, H6, H7, H5, F1, H4.*:idle"):
        wearer_from_env()
