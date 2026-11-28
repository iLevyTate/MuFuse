"""Feature frames, one per judged second, from samples only (003 decisions 1-10).

The engine runs its own quality engine, so it needs nothing but chunks. A frame for a second is
made once the quality answers reach `SETTLE_S` past it and the optics reach its end: by then every
blink that began in it is known and every optics sample it reads is in. So a recording gives the
same frames however its samples were delivered, live or replayed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from mufuse.acquisition.optics import LED_ROWS, OPTICS_HZ, too_much_light
from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.features.baseline import Baseline
from mufuse.features.params import FEATURES_VERSION, PARAMS, Params
from mufuse.features.pulse import Heart, combined, heart
from mufuse.features.spectrum import alpha_peak, band_shares, fit_aperiodic, pair_spectrum
from mufuse.quality.answer import FOREHEAD, Blink, QualityAnswer
from mufuse.quality.engine import JUDGE_STEP_S, QualityEngine
from mufuse.quality.rules import RULES_VERSION

if TYPE_CHECKING:
    from mufuse.recording.reader import LoadedSession

EEG_HZ = 256.0
SETTLE_S = 2.0  # a frame waits until the answers reach this far past its second
_KEEP_S = 70.0  # samples and answers older than this are never read again
_SENSOR_COLUMN = {"AF7": 1, "AF8": 2}  # in the EEG chunk: TP9, AF7, AF8, TP10

# The series of a frame, in the order a table shows them. The ones with a baseline come first.
WITH_BASELINE = (
    "exponent",
    "theta_share",
    "alpha_share",
    "beta_share",
    "blinks_per_min",
    "hr_bpm",
    "rmssd_ms",
)
SERIES = (
    *WITH_BASELINE,
    "alpha_hz",
    "alpha_height",
    "fit_r2",
    "af7_exponent",
    "af8_exponent",
)


@dataclass(frozen=True)
class FeatureFrame:
    """The features of one second (`t` is its end), and their z-scores against the baseline."""

    t: float
    values: Mapping[str, float | None]
    z: Mapping[str, float | None]
    features: str = FEATURES_VERSION
    rules: str = RULES_VERSION


@dataclass
class _Buffer:
    t: deque[FloatArray] = field(default_factory=deque[FloatArray])
    x: deque[FloatArray] = field(default_factory=deque[FloatArray])

    def add(self, t: FloatArray, x: FloatArray) -> None:
        if t.size:
            self.t.append(t)
            self.x.append(x)

    def newest(self) -> float:
        return float(self.t[-1][-1]) if self.t else -np.inf

    def between(self, start: float, end: float) -> tuple[FloatArray, FloatArray]:
        """The samples with start <= t < end."""
        if not self.t:
            return np.empty(0), np.empty((0, 0))
        t, x = np.concatenate(self.t), np.vstack(self.x)
        keep = (t >= start) & (t < end)
        return t[keep], x[keep]

    def drop_before(self, t0: float) -> None:
        while self.t and self.t[0][-1] < t0:
            self.t.popleft()
            self.x.popleft()


class FeatureEngine:
    def __init__(self, params: Params = PARAMS) -> None:
        self._p = params
        self._quality = QualityEngine()
        self._eeg, self._optics = _Buffer(), _Buffer()
        self._answers: deque[QualityAnswer] = deque()  # judged, kept for the windows that read them
        self._pending: deque[QualityAnswer] = deque()  # judged, no frame yet
        self._blinks: deque[Blink] = deque()
        self._pairs: dict[str, deque[tuple[float, FloatArray]]] = {s: deque() for s in FOREHEAD}
        self._freqs: FloatArray = np.fft.rfftfreq(params.pair_n, d=1 / EEG_HZ)
        self._baselines = {name: Baseline() for name in WITH_BASELINE}

    def feed(self, chunks: Sequence[Chunk]) -> list[FeatureFrame]:
        for chunk in chunks:
            if chunk.kind is StreamKind.EEG:
                self._eeg.add(chunk.timestamps, chunk.data[:, :4])
            elif chunk.kind is StreamKind.OPTICS:
                self._optics.add(chunk.timestamps, chunk.data)
        judged = self._quality.feed(chunks)
        self._take(judged.answers, judged.blinks)
        return self._ready(final=False)

    def finish(self) -> list[FeatureFrame]:
        """The frames that still wait, made with the samples that exist."""
        judged = self._quality.finish()
        self._take(judged.answers, judged.blinks)
        return self._ready(final=True)

    def _take(self, answers: Iterable[QualityAnswer], blinks: Iterable[Blink]) -> None:
        self._blinks.extend(blinks)
        for answer in answers:
            self._answers.append(answer)
            if not answer.no_data:
                self._pending.append(answer)

    def _ready(self, *, final: bool) -> list[FeatureFrame]:
        reached = self._answers[-1].end if self._answers else -np.inf
        frames: list[FeatureFrame] = []
        while self._pending:
            answer = self._pending[0]
            settled = reached >= answer.end + SETTLE_S and self._optics.newest() >= answer.end
            if not (final or settled):
                break
            self._pending.popleft()
            frames.append(self._frame(answer))
        if frames:
            self._forget(frames[-1].t - _KEEP_S)
        return frames

    def _forget(self, t0: float) -> None:
        self._eeg.drop_before(t0)
        self._optics.drop_before(t0)
        while self._answers and self._answers[0].end < t0:
            self._answers.popleft()
        while self._blinks and self._blinks[0].t < t0:
            self._blinks.popleft()

    # One frame ---------------------------------------------------------------------------------

    def _frame(self, answer: QualityAnswer) -> FeatureFrame:
        values: dict[str, float | None] = dict.fromkeys(SERIES)
        values.update(self._spectral(answer))
        values["blinks_per_min"] = self._blink_rate(answer.end)
        found = self._heart(answer.end)
        if found is not None:
            values["hr_bpm"], values["rmssd_ms"] = found.bpm, found.rmssd_ms
        z = {name: self._baselines[name].add(values[name], t=answer.end) for name in WITH_BASELINE}
        return FeatureFrame(t=answer.end, values=values, z=z)

    def _before(self, answer: QualityAnswer) -> QualityAnswer | None:
        """The judged second just before `answer`, if it touches it."""
        for earlier in reversed(self._answers):
            if earlier.end <= answer.start + 1e-6:
                touches = not earlier.no_data and abs(earlier.end - answer.start) < 0.5 / EEG_HZ
                return earlier if touches else None
        return None

    def _spectral(self, answer: QualityAnswer) -> dict[str, float | None]:
        p, out = self._p, dict[str, float | None]()
        before = self._before(answer)
        spectra: list[FloatArray] = []
        exponents: list[float] = []
        for sensor in FOREHEAD:
            pairs = self._pairs[sensor]
            if before is not None and answer.clean(sensor) and before.clean(sensor):
                _, x = self._eeg.between(before.start, answer.end)
                if x.shape[0] == p.pair_n:
                    pairs.append(
                        (answer.end, pair_spectrum(x[:, _SENSOR_COLUMN[sensor]], EEG_HZ)[1])
                    )
            while pairs and pairs[0][0] <= answer.end - p.spectrum_window_s:
                pairs.popleft()
            if len(pairs) < p.spectrum_min_pairs:
                continue
            psd = np.mean([s for _, s in pairs], axis=0)
            fit = fit_aperiodic(self._freqs, psd, p)
            if fit is None:
                continue
            out[f"{sensor.lower()}_exponent"] = fit.exponent
            exponents.append(fit.exponent)
            spectra.append(psd)
        if not spectra:
            return out
        psd = np.mean(spectra, axis=0)  # both forehead sensors, when both count
        fit = fit_aperiodic(self._freqs, psd, p)
        if fit is None:
            return out
        shares = band_shares(self._freqs, psd, p)
        peak = alpha_peak(self._freqs, psd, fit, p)
        out |= {
            "exponent": float(np.mean(exponents)),
            "fit_r2": fit.r2,
            "theta_share": shares.theta,
            "alpha_share": shares.alpha,
            "beta_share": shares.beta,
            "alpha_hz": None if peak is None else peak.hz,
            "alpha_height": None if peak is None else peak.height,
        }
        return out

    def _blink_rate(self, end: float) -> float | None:
        """Blinks per minute over the last minute, if the eye mark was available all through it."""
        window = self._p.blink_window_s
        seen = [a for a in self._answers if a.end > end - window and a.end <= end]
        if not seen or seen[0].start > end - window + 1.0:  # less than a minute judged so far
            return None
        if any(a.no_data or a.eye == "unavailable" for a in seen):
            return None
        count = sum(1 for b in self._blinks if end - window < b.t <= end)
        return count * 60.0 / window

    def _heart(self, end: float) -> Heart | None:
        p = self._p
        start = end - p.pulse_window_s
        if any(a.movement == "moving" for a in self._answers if a.end > start and a.start < end):
            return None
        _, x = self._optics.between(start, end)
        if x.shape[0] < 0.95 * p.pulse_window_s * OPTICS_HZ:
            return None
        sixteen = x.shape[1] - 1 == 16
        if too_much_light(x, sixteen_channels=sixteen).any():
            return None
        rows = list(LED_ROWS if sixteen else range(x.shape[1] - 1))
        wave = combined(x[:, rows], OPTICS_HZ, p)
        # Already band-passed: a second pass of the same band changes nothing that matters here.
        return None if wave is None else heart(wave, OPTICS_HZ, p)


def extract(session: LoadedSession, params: Params = PARAMS) -> list[FeatureFrame]:
    """The frames of a recorded session, the same as live (the recording is only read)."""
    engine = FeatureEngine(params)
    frames: list[FeatureFrame] = []
    streams = [(kind, ts, data) for kind, (ts, data) in session.streams.items() if ts.size]
    if streams:
        first = min(float(ts[0]) for _, ts, _ in streams)
        last = max(float(ts[-1]) for _, ts, _ in streams)
        steps = int((last - first) // JUDGE_STEP_S) + 1
        edges = first + JUDGE_STEP_S * np.arange(steps + 1)
        edges[-1] = np.inf
        cuts = [np.searchsorted(ts, edges) for _, ts, _ in streams]
        for step in range(steps):
            frames += engine.feed(
                [
                    Chunk(kind, ts[cut[step] : cut[step + 1]], data[cut[step] : cut[step + 1]])
                    for (kind, ts, data), cut in zip(streams, cuts, strict=True)
                    if cut[step + 1] > cut[step]
                ]
            )
    return frames + engine.finish()
