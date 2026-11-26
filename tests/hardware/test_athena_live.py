"""Real-headband acceptance tests. Run with the Muse S Athena on and the Muse app closed:

uv run pytest -m hardware -s
"""

from __future__ import annotations

import time

import pytest

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.brainflow_athena import BrainFlowAthena
from mufuse.acquisition.discovery import scan_for_muse
from mufuse.acquisition.types import StreamKind

pytestmark = pytest.mark.hardware


def test_headband_is_discoverable() -> None:
    found = scan_for_muse(timeout_s=8.0)
    assert found, "No Muse found — powered on? Muse app closed?"
    print(f"found: {found}")


def test_streams_all_signals_for_30_seconds() -> None:
    src = BrainFlowAthena()
    t0 = time.time()
    src.start()
    print(f"connected in {time.time() - t0:.1f} s")  # SC-001 target ≤ 15 s
    counts = dict.fromkeys(StreamKind, 0)
    try:
        end = time.time() + 30
        while time.time() < end:
            for chunk in src.read():
                counts[chunk.kind] += chunk.n_samples
            time.sleep(0.05)
    finally:
        src.stop()
    for kind, n in counts.items():
        expected = 30 * ATHENA_STREAMS[kind].sampling_rate
        print(f"{kind.value}: {n} / {expected:.0f} ({100 * n / expected:.1f}%)")
        assert n >= 0.95 * expected
