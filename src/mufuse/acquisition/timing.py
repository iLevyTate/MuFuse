"""Turn jittery arrival-time stamps into a smooth, strictly increasing sample clock.

BrainFlow stamps Athena samples with host arrival time: samples from one BLE packet share a
timestamp and packets jitter by tens of ms (measured: ~24% duplicate EEG timestamps, max jitter
~79 ms). Dropping duplicates loses real data; using them raw breaks spectral analysis. Instead
each sample advances by the nominal period, nudged a little toward the host time so the clock
cannot drift. A jump larger than `gap_s` is treated as a real data gap and re-anchored, never
smoothed over (constitution IV).

Limitation: without device-side counters a long BLE stall followed by a burst of delayed
samples looks like a gap; the error then decays within about 1/alpha samples.
"""

from __future__ import annotations

import numpy as np

from mufuse.acquisition.types import FloatArray


class Retimer:
    def __init__(self, sampling_rate: float, *, alpha: float = 0.01, gap_s: float = 0.25) -> None:
        self._period = 1.0 / sampling_rate
        self._alpha = alpha
        self._gap_s = gap_s
        self._last: float | None = None

    def retime(self, host_ts: FloatArray) -> FloatArray:
        out = np.empty(host_ts.shape, dtype=np.float64)
        t = self._last
        for i, host in enumerate(host_ts.tolist()):
            if t is None or host - (t + self._period) > self._gap_s:
                t = host  # first sample or real gap: anchor to the host clock
            else:
                expected = t + self._period
                nudged = expected + self._alpha * (host - expected)
                t = max(nudged, t + 0.5 * self._period)
            out[i] = t
        self._last = t
        return out
