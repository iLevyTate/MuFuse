"""Paced breathing (009): the guide, the simulated breathing in the pulse, the measures."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.acquisition.simulated import rsa_phase
from mufuse.exercises.breathe import (
    QUIET_S,
    BreatheReport,
    Phase,
    breathe_guide,
    phase_measure,
    report_lines,
    still,
)
from mufuse.quality.answer import Span


def test_the_guide_has_three_phases_with_markers_and_pacing_every_half_breath() -> None:
    guide = breathe_guide(rate=6.0, minutes=2.0)
    markers = [(c.at, c.marker) for c in guide.cues if c.marker]
    assert markers == [
        (0.0, "b:before"),
        (QUIET_S, "b:pace"),
        (QUIET_S + 120.0, "b:after"),
        (QUIET_S + 240.0, "b:end"),
    ]
    pacing = [c for c in guide.cues if not c.step]
    assert len(pacing) == 24  # 12 breaths, in and out
    assert [c.at for c in pacing[:3]] == [QUIET_S, QUIET_S + 5.0, QUIET_S + 10.0]
    assert pacing[0].text == "Breathe in (1 of 12)"
    assert pacing[1].text == "Breathe out (1 of 12)"
    assert guide.current(QUIET_S + 6.0)[0] == "Breathe out (1 of 12)"


def test_pacing_cues_stay_out_of_the_timeline() -> None:
    steps = [text for _, text, _ in breathe_guide(6.0, 2.0).timeline(0.0)]
    assert len(steps) == 4
    assert not any(text.startswith("Breathe") for text in steps)


@pytest.mark.parametrize(("rate", "minutes"), [(2.0, 5.0), (13.0, 5.0), (6.0, 0.5), (6.0, 31.0)])
def test_a_rate_or_length_out_of_range_is_refused(rate: float, minutes: float) -> None:
    with pytest.raises(ValueError, match="--"):
        breathe_guide(rate, minutes)


def test_breathing_in_the_pulse_swings_the_beat_interval_by_the_given_amount() -> None:
    fs, heart_hz = 1000.0, 1.2
    t = np.arange(0.0, 120.0, 1 / fs)
    phase = 2 * np.pi * heart_hz * t + rsa_phase(t, heart_hz, ((20.0, 100.0, 6.0, 150.0),))
    beats = t[1:][(np.diff(np.mod(phase, 2 * np.pi)) < 0)]  # each wrap of the phase is a beat
    intervals, ends = np.diff(beats), beats[1:]
    during = intervals[(ends > 30.0) & (ends < 90.0)]
    outside = intervals[ends < 19.0]
    assert np.ptp(during) * 1000 == pytest.approx(150.0, rel=0.15)
    assert np.ptp(outside) * 1000 < 2.0


def test_outside_its_spans_the_breathing_adds_nothing() -> None:
    t = np.array([0.0, 5.0])
    assert np.all(rsa_phase(t, 1.2, ((10.0, 20.0, 6.0, 100.0),)) == 0.0)
    after = rsa_phase(np.array([25.0, 30.0]), 1.2, ((10.0, 20.0, 6.0, 100.0),))
    assert after[0] == after[1]  # constant once the span is over


def test_a_phase_too_short_to_measure_says_nothing() -> None:
    t = np.arange(0.0, 10.0, 1 / 64)
    phase = phase_measure("before", t, np.ones((t.size, 17)), 10.0)
    assert (phase.hr_bpm, phase.swing_ms, phase.windows) == (None, None, 0)


def test_the_result_describes_and_says_raised_or_not() -> None:
    def ph(name: str, swing: float, rmssd: float) -> Phase:
        return Phase(name, 120.0, 70.0, swing, rmssd, 12)

    r = BreatheReport(
        6.0,
        {"before": ph("before", 90, 50), "pace": ph("pace", 200, 45), "after": ph("after", 80, 48)},
    )
    text = "\n".join(report_lines(r))
    assert "During paced breathing the beat-interval swing was 200 ms against 90 ms before" in text
    assert "swing  vs before: raised" in text
    assert "RMSSD  vs before: not raised" in text
    assert "you are" not in text.lower()


def test_without_a_pulse_it_says_not_measured() -> None:
    empty = Phase("before", 120.0, None, None, None, 0)
    r = BreatheReport(6.0, {"before": empty, "pace": empty, "after": empty})
    assert report_lines(r)[-1] == "Not measured: too little pulse signal in a phase."


def test_a_beat_interval_touching_a_moving_span_is_left_out() -> None:
    beats = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    moving = (Span("movement", 1.5, 2.5), Span("movement", 4.9, 6.0))
    # intervals 0-1, 1-2, 2-3, 3-4, 4-5: 1-2 and 2-3 overlap the first span, 4-5 the second
    assert still(beats, moving).tolist() == [True, False, False, True, False]
    assert still(beats, ()).all()


def test_the_result_says_how_long_the_head_moved_in_a_phase() -> None:
    def ph(name: str, moving: float) -> Phase:
        return Phase(name, 120.0, 70.0, 100.0, 50.0, 12, moving_s=moving)

    r = BreatheReport(
        6.0, {"before": ph("before", 0.0), "pace": ph("pace", 7.0), "after": ph("after", 0.0)}
    )
    lines = report_lines(r)
    assert sum("moving" in line for line in lines) == 1
    assert "7 s moving left out" in next(line for line in lines if line.strip().startswith("pace"))
