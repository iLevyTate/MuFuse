"""The strip's "now against your baseline" line, made in code (005 decision 6).

It describes the signal against the wearer's own earlier values and nothing else: no state, no
mood, no judgement (constitution II). With poor signal it shows no reading at all.
"""

from __future__ import annotations

from collections.abc import Mapping

LINE = (("blinks_per_min", "blinks"), ("alpha_share", "alpha"), ("hr_bpm", "heart rate"))
STEADY = {"hr_bpm"}  # "usual" reads as "steady" for these


def word(z: float | None) -> str | None:
    if z is None:
        return None
    size = abs(z)
    if size < 1.0:
        return "usual"
    way = "higher" if z > 0 else "lower"
    return f"a little {way}" if size < 2.0 else way


def baseline_line(z: Mapping[str, float | None], *, fix: str | None) -> str:
    """One short line; `fix` names a forehead sensor to fix when no forehead sensor is good."""
    if fix is not None:
        return f"fix {fix} first: no readings"
    parts: list[str] = []
    for series, name in LINE:
        said = word(z.get(series))
        if said is None:
            continue
        if said == "usual" and series in STEADY:
            said = "steady"
        parts.append(f"{name} {said}")
    return " · ".join(parts) if parts else "learning your baseline"
