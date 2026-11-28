"""What `mufuse features` prints and writes: numbers only, never a word about the person."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import numpy as np

from mufuse.features.engine import SERIES, WITH_BASELINE, FeatureFrame
from mufuse.features.params import FEATURES_VERSION
from mufuse.quality.rules import RULES_VERSION

_UNITS = {
    "exponent": "",
    "theta_share": "",
    "alpha_share": "",
    "beta_share": "",
    "blinks_per_min": "/min",
    "hr_bpm": "bpm",
    "rmssd_ms": "ms",
    "alpha_hz": "Hz",
    "alpha_height": "log10",
    "fit_r2": "",
    "af7_exponent": "",
    "af8_exponent": "",
}
_NOTES = {"rmssd_ms": "experimental: reads high at 64 Hz"}


def summary_lines(frames: Sequence[FeatureFrame]) -> list[str]:
    """One line per series: how many seconds had it, and its median and middle half."""
    n = len(frames)
    lines = [
        f"Features (features {FEATURES_VERSION}, rules {RULES_VERSION}) over {n} s",
        f"  {'series':<15}{'seconds':>9}{'median':>11}{'middle half':>22}",
    ]
    for name in SERIES:
        values = np.array([f.values[name] for f in frames if f.values[name] is not None])
        share = f"{100 * values.size / n:.0f}%" if n else "-"
        if values.size == 0:
            lines.append(f"  {name:<15}{share:>9}{'not available':>33}")
            continue
        low, mid, high = np.percentile(values, [25, 50, 75])
        unit = _UNITS[name]
        note = f"  ({_NOTES[name]})" if name in _NOTES else ""
        lines.append(
            f"  {name:<15}{share:>9}{mid:>11.3g}{f'{low:.3g} to {high:.3g}':>22} {unit}{note}"
        )
    lines.append(
        "z-scores compare each second with your own earlier values (after a minute of them);"
        " they describe the signal, not how you are."
    )
    return lines


def write_csv(frames: Sequence[FeatureFrame], path: Path) -> None:
    """One row per second: its end time, the versions, every series and every z-score."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(["t", "features", "rules", *SERIES, *(f"z_{s}" for s in WITH_BASELINE)])
        for frame in frames:
            out.writerow(
                [
                    f"{frame.t:.6f}",
                    frame.features,
                    frame.rules,
                    *(_cell(frame.values[s]) for s in SERIES),
                    *(_cell(frame.z[s]) for s in WITH_BASELINE),
                ]
            )


def _cell(value: float | None) -> str:
    return "" if value is None else repr(float(value))
