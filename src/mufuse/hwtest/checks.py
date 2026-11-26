"""What each hardware check measures and how it is graded (spec 001 success criteria).

Pure functions over numbers and loaded sessions, so the grading is unit-tested without a headband.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.signal_check import ChannelStatus, classify_channel
from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.recording.reader import LoadedSession

Status = Literal["pass", "fail", "skipped"]

STREAM_MIN_SHARE = 0.95  # each stream delivers at least this share of its nominal rate
CONNECT_MAX_S = 15.0  # SC-001
CONNECT_MIN_SHARE = 0.9  # SC-001: 9 of 10 attempts
COMPLETE_MIN = 0.995  # SC-002: under 0.5% missing
MARKER_TOL_S = 1.0 / ATHENA_STREAMS[StreamKind.EEG].sampling_rate  # SC-004: one EEG sample
RESUME_MAX_S = 20.0  # SC-003
GAP_TOL_S = 0.5  # SC-003
EEG_NAMES = ATHENA_STREAMS[StreamKind.EEG].channel_names[:4]


@dataclass(frozen=True)
class CheckInfo:
    title: str
    spec: str


CHECKS: dict[str, CheckInfo] = {
    "find": CheckInfo("Find the headband", "FR-001"),
    "firmware": CheckInfo("Read the firmware version", "T025"),
    "streams": CheckInfo("Every sensor streams", "FR-002"),
    "connect": CheckInfo("Time to live signal", "SC-001"),
    "contact": CheckInfo("Sensor contact check", "threshold tuning"),
    "record": CheckInfo("Long recording is complete", "SC-002"),
    "markers": CheckInfo("Markers line up with the data", "SC-004"),
    "power": CheckInfo("Recovers after power-off", "SC-003"),
    "interrupt": CheckInfo("Ctrl+C leaves a readable recording", "SC-005"),
}
CHECK_ORDER: tuple[str, ...] = tuple(CHECKS)


@dataclass(frozen=True)
class Timings:
    """Every duration in the guided run. The defaults are the real acceptance test."""

    scan_s: float = 8.0
    info_timeout_s: float = 8.0
    settle_s: float = 2.0
    stream_s: float = 30.0
    connect_attempts: int = 10
    connect_pause_s: float = 3.0
    connect_timeout_s: float = 30.0
    countdown_s: int = 3
    rest_s: float = 10.0
    blink_s: float = 10.0
    clench_s: float = 5.0
    lift_s: float = 8.0
    contact_window_s: float = 2.0
    recover_s: float = 3.0
    record_s: float = 600.0
    marker_at_s: tuple[float, ...] = (60.0, 120.0, 180.0)
    marker_wait_s: float = 20.0
    progress_every_s: float = 60.0
    power_lead_s: float = 15.0
    power_off_s: float = 10.0
    power_detect_s: float = 30.0
    resume_wait_s: float = 60.0
    power_tail_s: float = 10.0
    interrupt_lead_s: float = 5.0
    interrupt_wait_s: float = 60.0
    drain_s: float = 0.5
    poll_s: float = 0.05
    pause_threshold_s: float = 1.0
    stall_after_s: float = 3.0
    backoff_s: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0)

    @classmethod
    def practice(cls) -> Timings:
        """Shortened run (about 5 minutes) for rehearsing; not valid as the acceptance record."""
        return cls(
            stream_s=10.0,
            connect_attempts=3,
            rest_s=6.0,
            blink_s=6.0,
            clench_s=4.0,
            lift_s=5.0,
            record_s=90.0,
            marker_at_s=(20.0, 40.0, 60.0),
            progress_every_s=30.0,
            power_lead_s=8.0,
        )


@dataclass
class CheckResult:
    key: str
    title: str
    spec: str
    status: Status
    measured: str
    criterion: str = ""
    details: dict[str, Any] = field(default_factory=dict[str, Any])

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "spec": self.spec,
            "status": self.status,
            "criterion": self.criterion,
            "measured": self.measured,
            "details": self.details,
        }


def result(
    key: str,
    passed: bool,
    measured: str,
    criterion: str,
    details: dict[str, Any] | None = None,
) -> CheckResult:
    info = CHECKS[key]
    return CheckResult(
        key,
        info.title,
        info.spec,
        "pass" if passed else "fail",
        measured,
        criterion,
        details or {},
    )


def skipped(key: str, reason: str) -> CheckResult:
    info = CHECKS[key]
    return CheckResult(key, info.title, info.spec, "skipped", reason)


# --- every sensor streams -------------------------------------------------------------------


def evaluate_streams(
    received: Mapping[StreamKind, int], seconds: float, battery: float | None
) -> CheckResult:
    shares = {
        kind: received.get(kind, 0) / (seconds * spec.sampling_rate)
        for kind, spec in ATHENA_STREAMS.items()
    }
    short = [k.value for k, share in shares.items() if share < STREAM_MIN_SHARE]
    measured = " · ".join(f"{k.value} {100 * s:.1f}%" for k, s in shares.items())
    if battery is not None:
        measured += f" · battery {battery:.0f}%"
    if short:
        measured += f" (too low: {', '.join(short)})"
    return result(
        "streams",
        not short and seconds > 0,
        measured,
        f"Each stream delivers ≥ {100 * STREAM_MIN_SHARE:.0f}% of its nominal rate "
        f"for {seconds:.0f} s",
        {"seconds": seconds, "share": {k.value: s for k, s in shares.items()}, "battery": battery},
    )


# --- time to live signal --------------------------------------------------------------------


def evaluate_connect(times: Sequence[float | None]) -> CheckResult:
    n = len(times)
    need = math.ceil(CONNECT_MIN_SHARE * n)
    ok = [t for t in times if t is not None]
    fast = [t for t in ok if t <= CONNECT_MAX_S]
    measured = f"{len(fast)} of {n} under {CONNECT_MAX_S:.0f} s"
    if ok:
        measured += f" (median {float(np.median(ok)):.1f} s, slowest {max(ok):.1f} s)"
    failed = n - len(ok)
    if failed:
        measured += f"; {failed} failed to connect"
    return result(
        "connect",
        n > 0 and len(fast) >= need,
        measured,
        f"Live EEG within {CONNECT_MAX_S:.0f} s of connecting in ≥ {need} of {n} attempts",
        {"seconds": list(times)},
    )


# --- sensor contact -------------------------------------------------------------------------


class Condition(StrEnum):
    REST = "rest"
    BLINK = "blink"
    CLENCH = "clench"
    LIFT_TP9 = "lift_tp9"

    @property
    def label(self) -> str:
        return {
            "rest": "At rest",
            "blink": "Blinking",
            "clench": "Jaw clenched",
            "lift_tp9": "TP9 lifted",
        }[self.value]


@dataclass(frozen=True)
class ContactRule:
    channels: tuple[str, ...]
    expect: frozenset[ChannelStatus]
    min_share: float
    meaning: str


CONTACT_RULES: dict[Condition, ContactRule] = {
    Condition.REST: ContactRule(EEG_NAMES, frozenset({"ok"}), 0.8, "all four read ok at rest"),
    Condition.BLINK: ContactRule(
        ("AF7", "AF8"), frozenset({"ok"}), 0.8, "blinks do not trip AF7/AF8"
    ),
    Condition.CLENCH: ContactRule(
        ("TP9", "TP10"), frozenset({"noisy", "railed"}), 0.6, "jaw clench reads noisy on TP9/TP10"
    ),
    Condition.LIFT_TP9: ContactRule(
        ("TP9",), frozenset({"flat", "railed"}), 0.6, "lifted TP9 reads flat or railed"
    ),
}


def robust_spread(x: FloatArray) -> float:
    """Scaled median absolute deviation, the spread `classify_channel` thresholds on."""
    if x.size == 0:
        return 0.0
    return 1.4826 * float(np.median(np.abs(x - np.median(x))))


def window_statuses(x: FloatArray, rate: float, window_s: float) -> list[ChannelStatus]:
    """Classify overlapping windows (hop = half a window) of one channel, as the live view does."""
    size = max(1, round(window_s * rate))
    hop = max(1, size // 2)
    out: list[ChannelStatus] = []
    for start in range(0, x.size - size + 1, hop):
        window = x[start : start + size]
        out.append(classify_channel(window - window.mean()))
    return out


def _channel_summary(x: FloatArray, rate: float, window_s: float) -> dict[str, float]:
    statuses = window_statuses(x, rate, window_s)
    n = len(statuses) or 1
    summary = {s: statuses.count(s) / n for s in ("ok", "flat", "noisy", "railed")}
    summary["windows"] = float(len(statuses))
    summary["spread_uv"] = robust_spread(x - x.mean()) if x.size else 0.0
    return summary


def evaluate_contact(
    samples: Mapping[Condition, FloatArray], rate: float, window_s: float
) -> CheckResult:
    table: dict[str, dict[str, dict[str, float]]] = {}
    failed: list[str] = []
    for condition, data in samples.items():
        table[condition.value] = {
            name: _channel_summary(data[:, i], rate, window_s) for i, name in enumerate(EEG_NAMES)
        }
        rule = CONTACT_RULES[condition]
        for name in rule.channels:
            row = table[condition.value][name]
            share = sum(row[s] for s in rule.expect)
            if row["windows"] == 0 or share < rule.min_share:
                failed.append(f"{condition.value}: {name}")
    missing = [c.value for c in CONTACT_RULES if c not in samples]
    measured = (
        "Every condition read as expected"
        if not failed and not missing
        else "Unexpected readings: " + ", ".join(failed + [f"{m}: no data" for m in missing])
    )
    return result(
        "contact",
        not failed and not missing,
        measured,
        "; ".join(rule.meaning for rule in CONTACT_RULES.values()),
        {"conditions": table},
    )


# --- 10-minute recording and markers --------------------------------------------------------


def evaluate_record(session: LoadedSession) -> CheckResult:
    criterion = f"Every stream ≥ {100 * COMPLETE_MIN:.1f}% complete"
    completeness: dict[str, dict[str, int]] | None = session.manifest.get("completeness")
    firmware = session.manifest.get("device", {}).get("firmware")
    if not session.finalized or not completeness:
        return result("record", False, "The recording was not finalized", criterion)
    shares = {
        kind: (c["received"] / c["expected"]) if c["expected"] else 0.0
        for kind, c in completeness.items()
    }
    short = [k for k, s in shares.items() if s < COMPLETE_MIN]
    seconds = float(session.manifest["ended_at"]) - float(session.manifest["started_at"])
    measured = f"{seconds / 60:.1f} min recorded · "
    measured += " · ".join(f"{k} {100 * s:.2f}%" for k, s in shares.items())
    measured += f" · {len(session.gaps)} gaps"
    if short:
        measured += f" (incomplete: {', '.join(short)})"
    return result(
        "record",
        not short,
        measured,
        criterion,
        {
            "session": session.manifest.get("session_id"),
            "completeness": completeness,
            "gaps": len(session.gaps),
            "seconds": seconds,
            "firmware": firmware,
        },
    )


def evaluate_markers(
    session: LoadedSession, captured: Sequence[float], expected: int
) -> CheckResult:
    eeg_ts = session.streams[StreamKind.EEG][0] if StreamKind.EEG in session.streams else None
    stored = [m.t for m in session.markers if m.kind == "moment"]
    offsets: list[float] = []
    misplaced = 0
    for t in captured:
        if not any(abs(s - t) <= MARKER_TOL_S for s in stored):
            misplaced += 1
            continue
        if eeg_ts is None or eeg_ts.size == 0:
            misplaced += 1
            continue
        offset = float(np.min(np.abs(eeg_ts - t)))
        offsets.append(offset)
        if offset > MARKER_TOL_S:
            misplaced += 1
    found = len(captured) - misplaced
    measured = f"{found} of {expected} markers saved and aligned"
    if offsets:
        measured += f"; worst distance to nearest EEG sample {1000 * max(offsets):.1f} ms"
    return result(
        "markers",
        len(captured) == expected and misplaced == 0 and len(stored) == expected,
        measured,
        f"{expected} SPACE presses give {expected} markers, each within one EEG sample "
        f"({1000 * MARKER_TOL_S:.1f} ms) of the data",
        {"captured": list(captured), "stored": stored, "offsets_s": offsets},
    )


# --- power-off recovery ---------------------------------------------------------------------


@dataclass(frozen=True)
class Pause:
    """Host times of the last data before a pause and the first data after it."""

    stopped_at: float
    resumed_at: float

    @property
    def duration(self) -> float:
        return self.resumed_at - self.stopped_at


def evaluate_power(
    session: LoadedSession | None,
    outage: Pause | None,
    resume_after_on_s: float | None,
    note: str = "",
) -> CheckResult:
    criterion = (
        f"Streaming resumes ≤ {RESUME_MAX_S:.0f} s after power-on; one gap recorded, within "
        f"±{GAP_TOL_S} s of the real outage"
    )
    if outage is None or resume_after_on_s is None or session is None:
        return result("power", False, note or "No outage was measured", criterion)
    gaps = [g for g in session.gaps if g.end is not None]
    details: dict[str, Any] = {
        "resume_after_power_on_s": resume_after_on_s,
        "measured_outage_s": outage.duration,
        "gaps": [g.end - g.start for g in gaps if g.end is not None],
    }
    measured = f"Resumed {resume_after_on_s:.1f} s after the power-on prompt"
    problems: list[str] = []
    if resume_after_on_s > RESUME_MAX_S:
        problems.append("resumed too slowly")
    if len(gaps) != 1:
        problems.append(f"{len(gaps)} gaps recorded instead of 1")
    else:
        gap = gaps[0]
        assert gap.end is not None
        error = (gap.end - gap.start) - outage.duration
        measured += (
            f"; recorded gap {gap.end - gap.start:.2f} s vs measured outage "
            f"{outage.duration:.2f} s (off by {abs(error):.2f} s)"
        )
        if abs(error) > GAP_TOL_S:
            problems.append("gap duration inaccurate")
    if problems:
        measured += f" ({'; '.join(problems)})"
    return result("power", not problems, measured, criterion, details)


# --- Ctrl+C ---------------------------------------------------------------------------------


def evaluate_interrupt(
    session: LoadedSession | None, *, interrupted: bool, note: str = ""
) -> CheckResult:
    criterion = "A recording stopped with Ctrl+C reloads as finalized"
    if not interrupted:
        return result("interrupt", False, note or "No Ctrl+C arrived", criterion)
    if session is None:
        return result("interrupt", False, note or "The recording could not be reloaded", criterion)
    eeg = session.streams.get(StreamKind.EEG)
    samples = 0 if eeg is None else int(eeg[0].size)
    passed = session.finalized and samples > 0
    measured = (
        f"Reloaded as finalized with {samples:,} EEG samples"
        if passed
        else f"Reloaded but {'not finalized' if not session.finalized else 'empty'}"
    )
    return result("interrupt", passed, measured, criterion, {"eeg_samples": samples})
