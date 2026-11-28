"""The fNIRS reference: two simulated minutes with one response and one head turn (004 decision 9).

Shared by `scripts/make_fnirs_reference.py`, which writes it, and the test that reads it.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

import numpy as np

from mufuse.acquisition.types import StreamKind
from mufuse.fnirs.mbll import FNIRS_VERSION
from mufuse.fnirs.pipeline import Hemo, analyze
from mufuse.recording.reader import LoadedSession
from tests.conftest import QUICK, FakeClock, rehearse

REFERENCE = Path(__file__).resolve().parent / "data" / "fnirs_reference" / "hemo.json"
SECONDS = 120.0
EVERY = 32  # every 32nd sample (twice a second) is kept
WEARER = replace(QUICK, hemo=((40.0, 80.0, 1.0),), turns=((95.0, 98.0),))


def reference_hemo() -> Hemo:
    reads = rehearse(WEARER, FakeClock(), SECONDS)
    streams: dict[StreamKind, tuple[np.ndarray, np.ndarray]] = {}
    for kind in StreamKind:
        parts = [c for read in reads for c in read if c.kind is kind]
        streams[kind] = (
            np.concatenate([c.timestamps for c in parts]),
            np.vstack([c.data for c in parts]),
        )
    session = LoadedSession(
        path=Path(tempfile.gettempdir()), manifest={}, streams=streams, markers=[], gaps=[]
    )
    return analyze(session)


def _cells(x: np.ndarray) -> list[list[float | None]]:
    return [[None if not np.isfinite(v) else float(v) for v in row] for row in x[::EVERY]]


def to_json(hemo: Hemo) -> dict[str, object]:
    return {
        "fnirs": FNIRS_VERSION,
        "t": [round(float(v), 6) for v in (hemo.t - hemo.t[0])[::EVERY]],
        "hbo": _cells(hemo.hbo),
        "hbr": _cells(hemo.hbr),
        "moving": hemo.moving,
    }
