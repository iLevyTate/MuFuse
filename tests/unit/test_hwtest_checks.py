from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from mufuse.acquisition.types import StreamKind
from mufuse.hwtest.checks import (
    Condition,
    Pause,
    evaluate_connect,
    evaluate_contact,
    evaluate_interrupt,
    evaluate_markers,
    evaluate_power,
    evaluate_record,
    evaluate_streams,
    skipped,
    window_statuses,
)
from mufuse.recording.format import Gap, Marker
from mufuse.recording.reader import LoadedSession

RNG = np.random.default_rng(1)
RATE = 256.0


def _session(
    *,
    completeness: dict[str, dict[str, int]] | None = None,
    finalized: bool = True,
    eeg_ts: np.ndarray | None = None,
    markers: list[Marker] | None = None,
    gaps: list[Gap] | None = None,
    firmware: str | None = "3.4.2",
) -> LoadedSession:
    ts = eeg_ts if eeg_ts is not None else 1000.0 + np.arange(2560) / RATE
    manifest: dict[str, Any] = {
        "session_id": "s",
        "started_at": 1000.0,
        "ended_at": 1600.0 if finalized else None,
        "device": {"name": "MuseS-TEST", "firmware": firmware},
        "completeness": completeness,
    }
    return LoadedSession(
        path=Path("s"),
        manifest=manifest,
        streams={StreamKind.EEG: (ts, np.zeros((ts.size, 8)))},
        markers=markers or [],
        gaps=gaps or [],
    )


def _complete(eeg: float = 1.0, motion: float = 1.0, optics: float = 1.0) -> dict[str, Any]:
    return {
        "eeg": {"expected": 100_000, "received": round(100_000 * eeg)},
        "motion": {"expected": 20_000, "received": round(20_000 * motion)},
        "optics": {"expected": 40_000, "received": round(40_000 * optics)},
    }


# --- every sensor streams -------------------------------------------------------------------


def test_streams_pass_at_nominal_rate() -> None:
    result = evaluate_streams(
        {StreamKind.EEG: 7680, StreamKind.MOTION: 1560, StreamKind.OPTICS: 1920}, 30.0, 80.0
    )
    assert result.status == "pass"
    assert "battery 80%" in result.measured


def test_streams_fail_when_one_stream_is_short() -> None:
    result = evaluate_streams(
        {StreamKind.EEG: 7680, StreamKind.MOTION: 1000, StreamKind.OPTICS: 1920}, 30.0, None
    )
    assert result.status == "fail"
    assert "motion" in result.measured


# --- time to live signal --------------------------------------------------------------------


def test_connect_passes_with_nine_of_ten_fast() -> None:
    result = evaluate_connect([4.0] * 9 + [16.0])
    assert result.status == "pass"
    assert "9 of 10" in result.measured


def test_connect_fails_with_two_failures() -> None:
    result = evaluate_connect([4.0] * 8 + [None, 16.0])
    assert result.status == "fail"


def test_connect_scales_with_attempt_count() -> None:
    assert evaluate_connect([3.0, 3.0, 3.0]).status == "pass"
    assert evaluate_connect([3.0, 3.0, None]).status == "fail"


# --- sensor contact -------------------------------------------------------------------------


def _eeg(n: int, *, scale: float = 10.0) -> np.ndarray:
    return scale * RNG.standard_normal((n, 8))


def test_window_statuses_cover_the_signal() -> None:
    statuses = window_statuses(_eeg(5 * 256)[:, 0], RATE, 2.0)
    assert len(statuses) == 4  # 2 s windows, 1 s hop over 5 s
    assert set(statuses) == {"ok"}


def test_contact_passes_for_expected_patterns() -> None:
    rest = _eeg(2560)
    blink = _eeg(2560)
    clench = _eeg(1280)
    clench[:, [0, 3]] *= 20  # TP9/TP10 noisy
    lift = _eeg(2048)
    lift[:, 0] = 0.1 * RNG.standard_normal(2048)  # TP9 flat
    result = evaluate_contact(
        {
            Condition.REST: rest,
            Condition.BLINK: blink,
            Condition.CLENCH: clench,
            Condition.LIFT_TP9: lift,
        },
        RATE,
        2.0,
    )
    assert result.status == "pass", result.measured
    table = result.details["conditions"]
    assert table["clench"]["TP9"]["noisy"] == 1.0
    assert table["rest"]["AF7"]["spread_uv"] > 0


def test_contact_fails_and_names_the_rule() -> None:
    noisy_rest = _eeg(2560, scale=200.0)
    result = evaluate_contact({Condition.REST: noisy_rest}, RATE, 2.0)
    assert result.status == "fail"
    assert "rest" in result.measured


# --- 10-minute recording --------------------------------------------------------------------


def test_record_passes_when_complete() -> None:
    result = evaluate_record(_session(completeness=_complete()))
    assert result.status == "pass"
    assert result.details["firmware"] == "3.4.2"
    assert result.measured.startswith("10.0 min recorded")


def test_record_fails_below_threshold() -> None:
    result = evaluate_record(_session(completeness=_complete(optics=0.99)))
    assert result.status == "fail"
    assert "optics" in result.measured


def test_record_fails_when_not_finalized() -> None:
    assert evaluate_record(_session(completeness=None, finalized=False)).status == "fail"


# --- markers --------------------------------------------------------------------------------


def _marker(t: float) -> Marker:
    return Marker(t=t, kind="moment", label="moment", source="keyboard")


def test_markers_pass_when_aligned() -> None:
    captured = [1001.0, 1003.0, 1005.0]
    session = _session(markers=[_marker(t) for t in captured])
    result = evaluate_markers(session, captured, expected=3)
    assert result.status == "pass", result.measured


def test_markers_fail_when_one_is_missing() -> None:
    captured = [1001.0, 1003.0]
    result = evaluate_markers(_session(markers=[_marker(t) for t in captured]), captured, 3)
    assert result.status == "fail"
    assert "2 of 3" in result.measured


def test_markers_fail_when_far_from_any_sample() -> None:
    captured = [1001.0, 1003.0, 1500.0]  # last one is long after the data ends
    result = evaluate_markers(_session(markers=[_marker(t) for t in captured]), captured, 3)
    assert result.status == "fail"


# --- power-off recovery ---------------------------------------------------------------------


def test_power_passes_with_one_accurate_gap() -> None:
    gap = Gap(stream="all", start=100.0, end=113.4, reason="stall")
    result = evaluate_power(_session(gaps=[gap]), Pause(100.05, 113.38), resume_after_on_s=6.0)
    assert result.status == "pass", result.measured


def test_power_fails_when_resume_is_slow() -> None:
    gap = Gap(stream="all", start=100.0, end=130.0, reason="stall")
    result = evaluate_power(_session(gaps=[gap]), Pause(100.0, 130.0), resume_after_on_s=21.0)
    assert result.status == "fail"


def test_power_fails_when_gap_is_inaccurate() -> None:
    gap = Gap(stream="all", start=100.0, end=112.0, reason="stall")
    result = evaluate_power(_session(gaps=[gap]), Pause(100.0, 113.0), resume_after_on_s=5.0)
    assert result.status == "fail"


def test_power_fails_without_an_outage() -> None:
    result = evaluate_power(_session(), None, None, note="The data never stopped.")
    assert result.status == "fail"
    assert "never stopped" in result.measured


# --- Ctrl+C ---------------------------------------------------------------------------------


def test_interrupt_passes_for_finalized_session() -> None:
    assert evaluate_interrupt(_session(), interrupted=True).status == "pass"


def test_interrupt_fails_without_ctrl_c() -> None:
    result = evaluate_interrupt(_session(), interrupted=False)
    assert result.status == "fail"


def test_interrupt_fails_for_unfinalized_session() -> None:
    assert evaluate_interrupt(_session(finalized=False), interrupted=True).status == "fail"


def test_skipped_carries_reason() -> None:
    result = skipped("power", "not selected")
    assert result.status == "skipped"
    assert result.measured == "not selected"
