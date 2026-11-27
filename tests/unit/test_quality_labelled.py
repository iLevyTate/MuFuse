"""The guided labelled session and its scorer (contracts/labelled-session.md)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

import pytest

from mufuse.quality.answer import (
    SENSORS,
    Blink,
    ContactState,
    Coverage,
    QualityAnswer,
    SessionQuality,
)
from mufuse.quality.labelled import (
    ALLOWED_S,
    END_S,
    RUN_S,
    LabelCue,
    ScoreReport,
    cues_from_markers,
    labelled_guide,
    rehearsal_wearer,
    report_lines,
    schedule,
    score,
)
from mufuse.quality.rules import RULES_VERSION
from mufuse.recording.format import Marker

T0 = 1000.0


# The schedule --------------------------------------------------------------------------------


def _times(kind: str) -> list[float]:
    return [c.t for c in schedule() if c.kind == kind]


def test_the_schedule_of_the_contract() -> None:
    assert _times("quiet_open") == [20.0]
    assert _times("quiet_closed") == [80.0]
    assert _times("blink") == [150.0 + 4 * k for k in range(20)]
    assert _times("clench") == [240.0 + 5 * k for k in range(20)]
    assert _times("turn") == [350.0 + 5 * k for k in range(20)]
    lifts = [(c.t, c.sensor) for c in schedule() if c.kind == "lift"]
    downs = [(c.t, c.sensor) for c in schedule() if c.kind == "down"]
    assert lifts == [(460.0 + 10 * k, "AF7" if k % 2 == 0 else "AF8") for k in range(10)]
    assert downs == [(t + 5.0, s) for t, s in lifts]
    assert _times("end") == [END_S] == [565.0]
    assert len(schedule()) == 83
    assert [c.t for c in schedule()] == sorted(c.t for c in schedule())


def test_a_cue_is_a_marker_label_and_back() -> None:
    assert LabelCue(150.0, "blink").label == "q:blink"
    assert LabelCue(460.0, "lift", "AF7").label == "q:lift:AF7"
    for cue in schedule():
        assert LabelCue.parse(cue.t, cue.label) == cue
    assert LabelCue.parse(1.0, "note") is None
    assert LabelCue.parse(1.0, "q:wink") is None
    assert LabelCue.parse(1.0, "q:lift") is None  # a lift names its sensor
    assert LabelCue.parse(1.0, "q:lift:TP9") is None  # ... a forehead one


def test_the_guide_writes_every_cue_as_a_marker_and_counts_on_screen() -> None:
    guide = labelled_guide()
    assert [(c.at, c.marker) for c in guide.cues if c.marker] == [
        (c.t, c.label) for c in schedule()
    ]
    assert guide.duration == RUN_S > END_S
    texts = [c.text for c in guide.cues]
    assert any("Blink 7 of 20" in t for t in texts)
    assert any("10 of 10" in t for t in texts)
    assert [c.at for c in guide.cues if c.bell] == [140.0]  # the end of eyes closed


def test_cues_are_read_back_from_the_markers_of_a_session() -> None:
    markers = [
        Marker(T0 + 150.0, "system", "q:blink", "system"),
        Marker(T0 + 151.0, "moment", "q:blink", "keyboard"),  # typed, not a cue
        Marker(T0 + 152.0, "system", "adjust", "system"),
        Marker(T0 + 460.0, "system", "q:lift:AF7", "system"),
    ]
    assert cues_from_markers(markers) == (
        LabelCue(T0 + 150.0, "blink"),
        LabelCue(T0 + 460.0, "lift", "AF7"),
    )


def test_the_rehearsal_wearer_follows_the_cues() -> None:
    wearer = rehearsal_wearer(react_s=0.4)
    assert len(wearer.blinks) == len(wearer.clench) == len(wearer.turns) == 20
    assert len(wearer.lifted) == 10
    assert wearer.blinks[0][0] == pytest.approx(150.4)
    assert wearer.blinks[0][1] - wearer.blinks[0][0] < 1.0  # one blink per cue
    assert wearer.lifted[1] == (pytest.approx(470.4), pytest.approx(475.4), "AF8")


# The scorer ----------------------------------------------------------------------------------


def _cues() -> tuple[LabelCue, ...]:
    return tuple(replace(c, t=T0 + c.t) for c in schedule())


def _answer(second: int, **change: object) -> QualityAnswer:
    states = {name: str(change.pop(name, "good")) for name in SENSORS}
    reason = {"good": None, "noisy": "loud", "none": "floating"}
    contact = tuple(
        ContactState(n, s, reason[s], 10.0, 0.1)  # type: ignore[arg-type]
        for n, s in states.items()
    )
    base = QualityAnswer(
        start=T0 + second,
        end=T0 + second + 1.0,
        rules=RULES_VERSION,
        contact=contact,
        coverage=Coverage("full", ()),
        eye="no",
        tension="no",
        tension_uv=4.0,
        movement="still",
    )
    return replace(base, **change)  # type: ignore[arg-type]


def _session(
    *,
    tension: Iterable[int] = (),
    moving: Iterable[int] = (),
    blinks: Iterable[float] = (),
    sensor: dict[int, dict[str, str]] | None = None,
    eye: dict[int, str] | None = None,
) -> SessionQuality:
    tension, moving, sensor, eye = set(tension), set(moving), sensor or {}, eye or {}
    answers = [
        _answer(
            s,
            tension="yes" if s in tension else "no",
            movement="moving" if s in moving else "still",
            eye=eye.get(s, "no"),
            **sensor.get(s, {}),
        )
        for s in range(570)
    ]
    return SessionQuality.of(answers, [Blink(T0 + t, 0.3) for t in sorted(blinks)])


def _perfect(**change: object) -> dict[str, object]:
    """What a wearer who follows every cue leaves: a blink, a span, a lift for each cue."""
    marks: dict[str, object] = {
        "blinks": [t + 0.5 for t in _times("blink")],
        "tension": [int(t) for t in _times("clench")],
        "moving": [int(t) + k for t in _times("turn") for k in (0, 1)],
        "sensor": {
            int(t) + k: {s: "none"}
            for t, s in ((c.t, c.sensor) for c in schedule() if c.kind == "lift")
            for k in range(1, 5)
            if s is not None
        },
    }
    marks.update(change)
    return marks


def _score(**change: object) -> ScoreReport:
    return score(_session(**_perfect(**change)), _cues())  # type: ignore[arg-type]


def test_a_wearer_who_follows_every_cue_passes() -> None:
    report = _score()
    assert (report.blinks.found, report.blinks.total, report.blinks.passed) == (20, 20, True)
    assert (report.clenches.found, report.turns.found, report.lifts.found) == (20, 20, 10)
    assert report.quiet.passed is True
    assert report.quiet.false_marks == 0
    assert report.replay_identical is None  # not checked here
    assert report.passed
    assert report.allowed_s == ALLOWED_S == 2.0
    assert report.rules == RULES_VERSION


def test_a_blink_counts_within_2_s_after_its_cue_and_for_one_cue_only() -> None:
    late = [t + 2.5 for t in _times("blink")[:3]] + [t + 0.5 for t in _times("blink")[3:]]
    assert _score(blinks=late).blinks.found == 17
    early = [t - 0.2 for t in _times("blink")[:1]] + [t + 0.5 for t in _times("blink")[1:]]
    assert _score(blinks=early).blinks.found == 19
    two_cues = (LabelCue(T0 + 10.0, "blink"), LabelCue(T0 + 11.0, "blink"))
    report = score(_session(blinks=[11.5]), two_cues)
    assert (report.blinks.found, report.blinks.total) == (1, 2)


def test_a_span_counts_from_the_stretch_of_its_cue_to_2_s_after_it() -> None:
    clench = [int(t) for t in _times("clench")]
    started_before = [*(c - 1 for c in clench[:1]), *clench]  # the first span begins earlier
    assert _score(tension=started_before).clenches.found == 19
    a_second_late = [c + 1 for c in clench]
    assert _score(tension=a_second_late).clenches.found == 20
    three_late = [c + 3 for c in clench]
    assert _score(tension=three_late).clenches.found == 0
    assert _score(moving=[]).turns.found == 0


def test_the_pass_limits() -> None:
    blinks = [t + 0.5 for t in _times("blink")]
    assert _score(blinks=blinks[2:]).blinks.passed is True  # 18 of 20
    assert _score(blinks=blinks[3:]).blinks.passed is False  # 17 of 20
    assert not _score(blinks=blinks[3:]).passed


def test_quiet_shares_false_marks_and_eyes_closed_blinks() -> None:
    quiet = _score(tension=[*(int(t) for t in _times("clench")), 30, 31], blinks=[
        *(t + 0.5 for t in _times("blink")), 100.5, 110.5, 120.5
    ])  # fmt: skip
    q = quiet.quiet
    assert q.tension_share == pytest.approx(2 / (56 + 56))  # stretches 23..78 and 83..138
    assert q.movement_share == 0.0
    assert q.blinks_per_min_closed == pytest.approx(3 / (56 / 60))
    assert q.false_marks == 1 + 3  # one tension span begins in quiet, three blinks eyes closed
    assert q.passed is False  # above 2 blinks per minute with the eyes closed


def test_quiet_with_too_much_left_out_is_not_scored() -> None:
    report = _score(eye={s: "unavailable" for s in range(83, 100)})
    assert report.quiet.passed is None
    assert not report.passed
    assert "not scored" in "\n".join(report_lines(report))


def test_the_lift_rule() -> None:
    lifts = [(int(c.t), c.sensor) for c in schedule() if c.kind == "lift"]
    first_t, first_s = lifts[0]
    assert first_s is not None
    late: dict[int, dict[str, str]] = {
        t + k: {s: "none"} for t, s in lifts[1:] if s is not None for k in range(1, 5)
    }
    late[first_t + 4] = {first_s: "none"}  # not good only from cue + 4 s: in time
    assert _score(sensor=late).lifts.found == 10
    later = {**late}
    del later[first_t + 4]
    later[first_t + 5] = {first_s: "none"}  # cue + 5 s: too late
    assert _score(sensor=later).lifts.found == 9
    noisy = {**late, first_t + 1: {first_s: "noisy"}, first_t + 2: {first_s: "noisy"}}
    noisy[first_t + 3] = {first_s: "noisy"}  # three noisy stretches in a row
    noisy[first_t + 4] = {first_s: "none"}
    assert _score(sensor=noisy).lifts.found == 9
    noisy_two = {**late, first_t + 1: {first_s: "noisy"}, first_t + 2: {first_s: "none"}}
    assert _score(sensor=noisy_two).lifts.found == 10


def test_a_kind_without_cues_is_not_scored_never_passed() -> None:
    only_blinks = tuple(c for c in _cues() if c.kind in ("blink", "end"))
    report = score(_session(blinks=[t + 0.5 for t in _times("blink")]), only_blinks)
    assert report.blinks.passed is True
    assert report.clenches.passed is None
    assert report.lifts.passed is None
    assert not report.passed


def test_the_report_reads_like_the_contract() -> None:
    report = replace(_score(), replay_identical=True)
    assert report_lines(report) == [
        f"Labelled session score (rules {RULES_VERSION}, a mark counts within 2.0 s of its cue)",
        "  blinks        20 of 20   pass",
        "  jaw clenches  20 of 20   pass",
        "  head turns    20 of 20   pass",
        "  quiet         muscle activity 0.0% · head movement 0.0% · 0.0 blinks per minute, "
        "eyes closed   pass",
        "  lifts         10 of 10   pass",
        "  false marks   0 in quiet stretches",
        "  replay        identical to live",
        "  RESULT        pass",
    ]
    failed = replace(report, replay_identical=False)
    assert report_lines(failed)[-2:] == [
        "  replay        differs from live",
        "  RESULT        fail",
    ]
    assert report_lines(_score())[-2] == "  replay        not checked"


def test_the_report_holds_numbers_only() -> None:
    text = "\n".join(report_lines(_score()))
    for word in ("\\", "/", "Muse", "recordings", ".f64"):
        assert word not in text
