"""A recorded session's optics -> relative ΔHbO and ΔHbR per detector (004 decisions 1-5).

EXPERIMENTAL until the validation protocol passes on the wearer's own head. Steps, in order:
leave out frames with too much light and samples in seconds judged as moving (002); optical
density against the mean of the first 30 s of used samples; band-pass 0.01-0.2 Hz, zero-phase,
on each piece of optics between time gaps (left-out samples bridged by a straight line only so
the filter can run, then set back to NaN); the 2x2 Beer-Lambert solve; optionally short-channel
regression.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
from scipy import signal as _scipy_signal  # pyright: ignore[reportMissingTypeStubs]

from mufuse.acquisition.optics import OPTICS_HZ, too_much_light
from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.fnirs.mbll import (
    AGE,
    DETECTORS,
    DISTANCE_CM,
    FNIRS_VERSION,
    OUTER,
    concentrations,
    optical_density,
    rows_of,
)
from mufuse.quality.answer import SessionQuality

if TYPE_CHECKING:
    from mufuse.recording.reader import LoadedSession

_signal: Any = _scipy_signal  # scipy ships no type stubs; its results are typed where used

BAND_HZ = (0.01, 0.2)  # drift out, heartbeat out
BASELINE_S = 30.0  # I0: the mean of the first 30 s of used samples
GAP_S = 0.25  # optics further apart than this are separate pieces
MIN_PIECE_S = 20.0  # a shorter piece is too short to filter: left out
SQI_WINDOW_S = 10.0
SHORT_PAIRS = (("LO", "LI"), ("RO", "RI"))  # outer, inner on each side


class NotAvailableError(Exception):
    """The session has no 16-channel optics to work from."""


@dataclass(frozen=True)
class Hemo:
    """ΔHbO and ΔHbR (µM, relative) per detector, columns in DETECTORS order; NaN = left out."""

    t: FloatArray
    hbo: FloatArray
    hbr: FloatArray
    glare: int  # samples left out for too much light
    moving: int  # samples left out because the head moved
    short_pieces: int  # samples left out in pieces too short to filter
    sqi: dict[str, float | None] = field(default_factory=dict[str, float | None])
    short_channel: bool = False
    version: str = FNIRS_VERSION

    @property
    def used_share(self) -> float:
        return float(np.isfinite(self.hbo).all(axis=1).mean()) if self.t.size else 0.0

    def outer_hbo(self) -> FloatArray:
        """The mean ΔHbO of the outer detectors, NaN where neither has a value."""
        cols = [DETECTORS.index(d) for d in OUTER]
        x = self.hbo[:, cols]
        n = np.isfinite(x).sum(axis=1)
        total = np.nansum(x, axis=1)
        return np.where(n > 0, total / np.maximum(n, 1), np.nan)


def moving_mask(t: FloatArray, quality: SessionQuality) -> np.ndarray:
    """Optics samples that fall in a second judged as moving."""
    mask = np.zeros(t.size, dtype=bool)
    for answer in quality.answers:
        if not answer.no_data and answer.movement == "moving":
            mask |= (t >= answer.start) & (t < answer.end)
    return mask


def _pieces(t: FloatArray) -> list[slice]:
    cuts = np.flatnonzero(np.diff(t) > GAP_S) + 1
    edges = [0, *cuts.tolist(), t.size]
    return [slice(a, b) for a, b in itertools.pairwise(edges) if b > a]


def _band(x: FloatArray, keep: np.ndarray) -> FloatArray | None:
    """Band-pass one piece, bridging the left-out samples; None if nothing is kept."""
    if not keep.any():
        return None
    idx = np.arange(x.size)
    bridged = np.interp(idx, idx[keep], x[keep])
    sos = _signal.butter(2, BAND_HZ, btype="bandpass", fs=OPTICS_HZ, output="sos")
    return np.asarray(_signal.sosfiltfilt(sos, bridged), dtype=np.float64)


def _sqi(hbo: FloatArray, hbr: FloatArray) -> float | None:
    """Median over 10 s windows of minus the HbO-HbR correlation."""
    n = int(SQI_WINDOW_S * OPTICS_HZ)
    found: list[float] = []
    for start in range(0, hbo.size - n + 1, n):
        a, b = hbo[start : start + n], hbr[start : start + n]
        ok = np.isfinite(a) & np.isfinite(b)
        if ok.sum() < 0.8 * n or np.std(a[ok]) == 0 or np.std(b[ok]) == 0:
            continue
        found.append(-float(np.corrcoef(a[ok], b[ok])[0, 1]))
    return float(np.median(found)) if found else None


def _regress_short(x: FloatArray) -> FloatArray:
    """Outer minus beta times inner, per side, beta by least squares over the shared samples."""
    out = x.copy()
    for outer, inner in SHORT_PAIRS:
        o, i = DETECTORS.index(outer), DETECTORS.index(inner)
        ok = np.isfinite(x[:, o]) & np.isfinite(x[:, i])
        denom = float((x[ok, i] ** 2).sum())
        if ok.any() and denom > 0:
            beta = float((x[ok, o] * x[ok, i]).sum()) / denom
            out[:, o] = x[:, o] - beta * x[:, i]
    return out


def analyze(
    session: LoadedSession,
    quality: SessionQuality | None = None,
    *,
    short_channel: bool = False,
    age: float = AGE,
    distances: dict[str, float] | None = None,
) -> Hemo:
    distances = distances or DISTANCE_CM
    if StreamKind.OPTICS not in session.streams:
        raise NotAvailableError("the session has no optics")
    t, data = session.streams[StreamKind.OPTICS]
    if data.ndim != 2 or data.shape[1] - 1 != 16:
        raise NotAvailableError("fNIRS needs a 16-channel optics preset (p1041 or p1042)")
    if quality is None:
        from mufuse.quality.engine import judge

        quality = judge(session)
    frames = data[:, :16]
    glare = too_much_light(frames, sixteen_channels=True)
    moving = moving_mask(t, quality) & ~glare
    n = t.size
    hbo, hbr = np.full((n, 4), np.nan), np.full((n, 4), np.nan)
    short = np.zeros(n, dtype=bool)
    for piece in _pieces(t):
        if (t[piece.stop - 1] - t[piece.start]) < MIN_PIECE_S:
            short[piece] = True
    for k, detector in enumerate(DETECTORS):
        r730, r850 = rows_of(detector)
        i730, i850 = frames[:, r730], frames[:, r850]
        used = ~glare & ~moving & ~short & (i730 > 0) & (i850 > 0)
        if not used.any():
            continue
        first = t[used][0]
        base = used & (t < first + BASELINE_S)
        od730 = optical_density(np.where(i730 > 0, i730, 1.0), float(i730[base].mean()))
        od850 = optical_density(np.where(i850 > 0, i850, 1.0), float(i850[base].mean()))
        f730, f850 = np.full(n, np.nan), np.full(n, np.nan)
        for piece in _pieces(t):
            keep = used[piece]
            a, b = _band(od730[piece], keep), _band(od850[piece], keep)
            if a is not None and b is not None and not short[piece].any():
                f730[piece], f850[piece] = a, b
        o, r = concentrations(f730, f850, distances[detector], age)
        hbo[:, k] = np.where(used, o, np.nan)
        hbr[:, k] = np.where(used, r, np.nan)
    if short_channel:
        hbo, hbr = _regress_short(hbo), _regress_short(hbr)
    sqi = {d: _sqi(hbo[:, k], hbr[:, k]) for k, d in enumerate(DETECTORS)}
    return Hemo(
        t=t,
        hbo=hbo,
        hbr=hbr,
        glare=int(glare.sum()),
        moving=int(moving.sum()),
        short_pieces=int((short & ~glare & ~moving).sum()),
        sqi=sqi,
        short_channel=short_channel,
    )
