"""Heart rate and pulse-based variability from one optics row (003 decision 7).

Beats are the peaks of the band-passed pulse wave, at least 0.33 s apart, each refined to
sub-sample time by a parabola through its three highest samples: at 64 Hz, rounding to a sample
would add about 11 ms to every successive difference. This is pulse-based variability from the
forehead, not ECG heart-rate variability, and it is named so.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal as _scipy_signal  # pyright: ignore[reportMissingTypeStubs]

from mufuse.acquisition.optics import PULSE_SHARE, pulse_share
from mufuse.acquisition.types import FloatArray
from mufuse.features.params import PARAMS, Params

_signal: Any = _scipy_signal  # scipy ships no type stubs; its results are typed where used


@dataclass(frozen=True)
class Heart:
    bpm: float | None
    rmssd_ms: float | None
    beats: int


def has_pulse(x: FloatArray, fs: float) -> bool:
    """Whether a heartbeat stands out in the row: the live view's own test (`optics.py`)."""
    return np.asarray(x).size >= fs * 2 and pulse_share(x, fs) >= PULSE_SHARE


def _band(x: FloatArray, fs: float, p: Params) -> FloatArray:
    sos = _signal.butter(2, p.pulse_band_hz, btype="bandpass", fs=fs, output="sos")
    y = np.asarray(x, dtype=np.float64)
    return np.asarray(_signal.sosfiltfilt(sos, y - y.mean()), dtype=np.float64)


def beat_times(x: FloatArray, fs: float, p: Params = PARAMS) -> FloatArray:
    """The time of each beat (the top of each pulse wave), in seconds from the first sample."""
    if np.asarray(x).size < fs * 2:
        return np.empty(0)
    y = _band(x, fs, p)
    spread = float(np.std(y))
    if spread == 0:
        return np.empty(0)
    found = _signal.find_peaks(y, distance=max(int(p.beat_min_s * fs), 1), prominence=0.5 * spread)
    peaks = np.asarray(found[0], dtype=np.intp)
    peaks = peaks[(peaks > 0) & (peaks < y.size - 1)]
    a, b, c = y[peaks - 1], y[peaks], y[peaks + 1]
    bend = a - 2 * b + c
    shift = np.where(bend != 0, 0.5 * (a - c) / np.where(bend != 0, bend, 1.0), 0.0)
    return (peaks + np.clip(shift, -0.5, 0.5)) / fs


def combined(rows: FloatArray, fs: float, p: Params = PARAMS) -> FloatArray | None:
    """One pulse wave from every row (column) that shows a heartbeat; None if none does.

    Each row is band-passed and scaled to unit spread, turned to match the clearest row (a row
    that dips with each beat counts as much as one that rises), then all are averaged: the beat is
    shared and the noise is not, so the average is cleaner than any one row.
    """
    x = np.asarray(rows, dtype=np.float64)
    beating = [k for k in range(x.shape[1]) if has_pulse(x[:, k], fs)]
    if not beating:
        return None
    waves = [_band(x[:, k], fs, p) for k in beating]
    waves = [w / s for w in waves if (s := float(np.std(w))) > 0]
    if not waves:
        return None
    best = max(range(len(waves)), key=lambda i: pulse_share(x[:, beating[i]], fs))
    return np.mean([w if float(w @ waves[best]) >= 0 else -w for w in waves], axis=0)


def _kept(intervals: FloatArray, p: Params) -> np.ndarray:
    """Which intervals are plausible: in 0.33-1.5 s and within 30% of their median."""
    ok = (intervals >= p.beat_min_s) & (intervals <= p.beat_max_s)
    if not ok.any():
        return ok
    median = float(np.median(intervals[ok]))
    return ok & (np.abs(intervals - median) <= p.beat_off_median * median)


def plausible(intervals: FloatArray, p: Params = PARAMS) -> np.ndarray:
    """Which beat intervals are plausible (0.33-1.5 s, within 30% of their median)."""
    return _kept(np.asarray(intervals, dtype=np.float64), p)


def rmssd_ms(intervals: FloatArray, p: Params = PARAMS) -> float | None:
    """Root mean square of successive differences, over neighbouring intervals both kept."""
    kept = _kept(np.asarray(intervals, dtype=np.float64), p)
    pairs = kept[1:] & kept[:-1]
    if int(kept.sum()) < p.rmssd_min_intervals or not pairs.any():
        return None
    diffs = np.diff(intervals)[pairs]
    return float(np.sqrt(np.mean(diffs**2)) * 1000.0)


def heart(x: FloatArray, fs: float, p: Params = PARAMS) -> Heart | None:
    """Heart rate and RMSSD from a window of one optics row; None when no beat is found."""
    beats = beat_times(x, fs, p)
    if beats.size < 3:
        return None
    intervals = np.diff(beats)
    kept = _kept(intervals, p)
    bpm = 60.0 / float(np.median(intervals[kept])) if int(kept.sum()) >= 2 else None
    return Heart(bpm=bpm, rmssd_ms=rmssd_ms(intervals, p), beats=int(beats.size))
