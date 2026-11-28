"""What `mufuse fnirs show` prints and writes. Every line says EXPERIMENTAL and relative."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from mufuse.fnirs.mbll import DETECTORS, DISTANCE_CM, EXPERIMENTAL
from mufuse.fnirs.pipeline import Hemo


def _spread(x: np.ndarray) -> str:
    x = x[np.isfinite(x)]
    if x.size == 0:
        return "not available"
    low, high = np.percentile(x, [5, 95])
    return f"{low:+.2f} to {high:+.2f}"


def hemo_lines(hemo: Hemo) -> list[str]:
    n = hemo.t.size
    lines = [
        f"fNIRS (fnirs {hemo.version}) - {EXPERIMENTAL}: relative ΔHbO/ΔHbR in µM, distances are"
        " estimates",
        f"  samples {n}, used {100 * hemo.used_share:.0f}%; left out: too much light {hemo.glare},"
        f" head moving {hemo.moving}, pieces too short {hemo.short_pieces}",
        f"  {'detector':<9}{'distance':>9}{'ΔHbO 5-95%':>20}{'ΔHbR 5-95%':>20}{'SQI':>7}",
    ]
    for k, d in enumerate(DETECTORS):
        sqi = hemo.sqi.get(d)
        lines.append(
            f"  {d:<9}{DISTANCE_CM[d]:>7.1f}cm{_spread(hemo.hbo[:, k]):>20}"
            f"{_spread(hemo.hbr[:, k]):>20}{'-' if sqi is None else f'{sqi:.2f}':>7}"
        )
    if hemo.short_channel:
        lines.append("  short-channel regression on (unverified geometry)")
    lines.append("SQI: minus the HbO-HbR correlation over 10 s windows; higher is better.")
    return lines


def write_csv(hemo: Hemo, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(
            ["t", "fnirs", *(f"hbo_{d}" for d in DETECTORS), *(f"hbr_{d}" for d in DETECTORS)]
        )
        for i in range(hemo.t.size):
            values = [*hemo.hbo[i], *hemo.hbr[i]]
            out.writerow(
                [
                    f"{hemo.t[i]:.6f}",
                    hemo.version,
                    *("" if not np.isfinite(v) else f"{v:.6g}" for v in values),
                ]
            )
