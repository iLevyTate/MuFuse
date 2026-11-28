"""The features reference: one simulated resting minute and a half, and its frames (003 gate).

Shared by `scripts/make_features_reference.py`, which writes it, and the test that reads it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from mufuse.features.engine import FeatureEngine, FeatureFrame
from mufuse.features.params import FEATURES_VERSION
from tests.conftest import QUICK, FakeClock, rehearse

REFERENCE = Path(__file__).resolve().parent / "data" / "features_reference" / "frames.json"
SECONDS = 90.0
WEARER = replace(
    QUICK,
    resting=True,
    exponent=1.4,
    heart_bpm=66.0,
    blinks=tuple((float(t), t + 0.5) for t in range(10, 90, 5)),
    turns=((70.0, 72.0),),
    lifted=((40.0, 44.0, "AF8"),),
)


def reference_frames() -> list[FeatureFrame]:
    engine = FeatureEngine()
    frames = [f for read in rehearse(WEARER, FakeClock(), SECONDS) for f in engine.feed(read)]
    return frames + engine.finish()


def to_json(frames: list[FeatureFrame]) -> dict[str, object]:
    t0 = frames[0].t if frames else 0.0
    return {
        "features": FEATURES_VERSION,
        "frames": [
            {"t": round(f.t - t0, 6), "values": dict(f.values), "z": dict(f.z)} for f in frames
        ],
    }
