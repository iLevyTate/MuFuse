"""The quality summary of a recorded session, for `mufuse inspect` (data-model.md, QualitySummary).

Shares are over judged time, so time without data is left out of all of them. A share with
nothing to divide by is None ("not available"), never 0.
Every text describes a sensor or the signal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from mufuse.quality.answer import SENSORS, QualityAnswer, SessionQuality

LEVELS = ("full", "reduced", "one_forehead", "none")
LEVEL_WORDS = {
    "full": "full",
    "reduced": "reduced",
    "one_forehead": "one forehead sensor",
    "none": "none",
}
NOT_AVAILABLE = "not available"


@dataclass(frozen=True)
class SensorShares:
    """One sensor's share of judged time in each contact state, and clean."""

    good: float | None
    settling: float | None
    noisy: float | None
    none: float | None
    clean: float | None


@dataclass(frozen=True)
class QualitySummary:
    rules: str
    judged_s: float
    no_data_s: float
    sensors: Mapping[str, SensorShares]
    coverage: Mapping[str, float | None]
    blinks: int | None
    blinks_per_min: float | None
    blink_available_s: float
    tension_share: float | None
    movement_share: float | None
    movement_unknown_s: float


def summarize(quality: SessionQuality) -> QualitySummary:
    judged = [a for a in quality.answers if not a.no_data]
    judged_s = _seconds(judged)

    def share(marked: Callable[[QualityAnswer], bool]) -> float | None:
        return _seconds([a for a in judged if marked(a)]) / judged_s if judged_s > 0 else None

    def shares(name: str) -> SensorShares:
        return SensorShares(
            good=share(lambda a: a.state(name).state == "good"),
            settling=share(lambda a: a.state(name).state == "settling"),
            noisy=share(lambda a: a.state(name).state == "noisy"),
            none=share(lambda a: a.state(name).state == "none"),
            clean=share(lambda a: a.clean(name)),
        )

    available_s = _seconds([a for a in judged if a.eye != "unavailable"])
    blinks = len(quality.blinks) if available_s > 0 else None
    return QualitySummary(
        rules=quality.rules,
        judged_s=judged_s,
        no_data_s=_seconds([a for a in quality.answers if a.no_data]),
        sensors={name: shares(name) for name in SENSORS},
        coverage={level: share(lambda a, lv=level: a.coverage.level == lv) for level in LEVELS},
        blinks=blinks,
        blinks_per_min=None if blinks is None else blinks / (available_s / 60.0),
        blink_available_s=available_s,
        tension_share=share(lambda a: a.tension == "yes"),
        movement_share=share(lambda a: a.movement == "moving"),
        movement_unknown_s=_seconds([a for a in judged if a.movement == "unknown"]),
    )


def _seconds(answers: list[QualityAnswer]) -> float:
    return float(sum(a.end - a.start for a in answers))


def _mmss(seconds: float) -> str:
    whole = round(seconds)
    return f"{whole // 60}:{whole % 60:02d}"


def _pct(value: float | None) -> str:
    return NOT_AVAILABLE if value is None else f"{100 * value:.0f}%"


def summary_lines(s: QualitySummary) -> list[str]:
    """The block `mufuse inspect` prints (contracts/cli.md)."""
    lines = [
        f"Signal quality (rules {s.rules})",
        f"  judged {_mmss(s.judged_s)} · no data {_mmss(s.no_data_s)}",
    ]
    if s.judged_s <= 0:
        return [
            *lines,
            f"  shares    {NOT_AVAILABLE}: no second of signal was judged",
            f"  blinks    {NOT_AVAILABLE}",
            f"  marked    {NOT_AVAILABLE}",
        ]
    lines.append("  sensor   good  settling  noisy  no contact  clean")
    for name, x in s.sensors.items():
        lines.append(
            f"  {name:<6}{_pct(x.good):>7}{_pct(x.settling):>10}{_pct(x.noisy):>7}"
            f"{_pct(x.none):>12}{_pct(x.clean):>7}"
        )
    levels = " · ".join(f"{LEVEL_WORDS[lv]} {_pct(s.coverage[lv])}" for lv in LEVELS)
    lines.append(f"  coverage  {levels}")
    if s.blinks is None or s.blinks_per_min is None:
        lines.append(f"  blinks    {NOT_AVAILABLE}")
    else:
        rate = f"{s.blinks_per_min:.1f} per minute over {_mmss(s.blink_available_s)}"
        lines.append(f"  blinks    {s.blinks} ({rate})")
    lines.append(
        f"  marked    muscle activity {_pct(s.tension_share)} · head movement "
        f"{_pct(s.movement_share)} · movement unknown {_mmss(s.movement_unknown_s)}"
    )
    return lines
