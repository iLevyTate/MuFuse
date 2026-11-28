"""Deterministic Athena-shaped synthetic sources for development and CI (no hardware).

`SimulatedAthena` is a clean signal that nothing happens to. `Rehearsal` puts a scripted wearer
on it, so the hardware acceptance checks can be rehearsed without the headband. The wearer
encodes guesses about the real device: a green rehearsal proves the pipeline, not the
physiology.
"""

from __future__ import annotations

import signal
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS, DEFAULT_PRESET, validate_preset
from mufuse.acquisition.types import (
    Chunk,
    DeviceInfo,
    FloatArray,
    SourceError,
    StreamKind,
    StreamSpec,
)

Clock = Callable[[], float]


class SimulatedAthena:
    """Generates plausible signals sample-accurately from a (possibly fake) clock.

    EEG: 10 Hz alpha + broadband noise (µV). Motion: gravity on Z + noise. Optics: DC + 1.2 Hz
    pulse. ``dropouts`` are (start, end) windows in seconds after ``start()`` with no samples,
    used to exercise stall handling.
    """

    def __init__(
        self,
        *,
        clock: Clock = time.time,
        seed: int = 0,
        preset: str = DEFAULT_PRESET,
        dropouts: Sequence[tuple[float, float]] = (),
    ) -> None:
        self._clock = clock
        self._seed = seed
        self._dropouts = tuple(dropouts)
        self._device = DeviceInfo(
            name="SimulatedAthena", preset=validate_preset(preset), driver="simulated"
        )
        self._t0: float | None = None
        self._emitted: dict[StreamKind, int] = {}
        self._rngs: dict[StreamKind, np.random.Generator] = {}

    @property
    def device(self) -> DeviceInfo:
        return self._device

    @property
    def streams(self) -> Mapping[StreamKind, StreamSpec]:
        return ATHENA_STREAMS

    @property
    def lost_subpackets(self) -> Mapping[StreamKind, int]:
        return dict.fromkeys(ATHENA_STREAMS, 0)  # no headset link, so nothing is lost on it

    def start(self) -> None:
        self._t0 = self._clock()
        self._emitted = dict.fromkeys(StreamKind, 0)
        self._rngs = {k: np.random.default_rng([self._seed, i]) for i, k in enumerate(StreamKind)}

    def stop(self) -> None:
        self._t0 = None

    def read(self) -> list[Chunk]:
        if self._t0 is None:
            raise SourceError("SimulatedAthena.read() called before start()")
        elapsed = self._clock() - self._t0
        chunks: list[Chunk] = []
        for kind, spec in ATHENA_STREAMS.items():
            # UNIX-epoch floats resolve only ~0.24 µs, so allow 1/1000 sample of rounding slack.
            due = int(elapsed * spec.sampling_rate + 1e-3)
            idx = np.arange(self._emitted[kind], due)
            self._emitted[kind] = due
            rel = idx / spec.sampling_rate
            # Signals are generated for every index so the RNG stays aligned, then masked.
            data = self._generate(kind, spec, rel)
            keep = ~self._in_dropout(rel)
            if keep.any():
                chunks.append(Chunk(kind, self._t0 + rel[keep], data[keep]))
        return chunks

    def _in_dropout(self, rel: FloatArray) -> np.ndarray:
        mask = np.zeros(rel.shape, dtype=bool)
        for start, end in self._dropouts:
            mask |= (rel >= start) & (rel < end)
        return mask

    def _generate(self, kind: StreamKind, spec: StreamSpec, rel: FloatArray) -> FloatArray:
        rng = self._rngs[kind]
        n, c = rel.size, len(spec.channel_names)
        noise = rng.standard_normal((n, c))
        if kind is StreamKind.EEG:
            alpha = 20.0 * np.sin(2 * np.pi * 10.0 * rel)[:, None]
            return alpha + 8.0 * noise
        if kind is StreamKind.MOTION:
            gravity = np.zeros((n, c))
            gravity[:, 2] = 1.0
            return gravity + 0.01 * noise
        pulse = np.sin(2 * np.pi * 1.2 * rel)[:, None]
        optics = 20_000.0 + 150.0 * pulse + 5.0 * noise
        optics[:, -1] = 100.0 - rel / 600.0  # battery percent, slowly draining
        return optics


# A scripted wearer ----------------------------------------------------------------------------
# Where the numbers come from. Measured: the EEG range, the rest offsets, the input without
# skin contact, and the optics levels with their scatter, all from the public muse-rs capture of
# an Athena (firmware 3.1.19, preset p1041; docs/research/2026-11-25-athena-fnirs-resources.md,
# section 2.5); the link timings from this project's own headband (4.2-5.8 s from connect to the
# first EEG, 7.3 s to release, a scan that gives up after 15 s). Guessed, because no capture
# shows them: a blink, a jaw clench, the LED rows off the head, what room light adds to the
# ambient rows, how long the headband takes to start up, and how fast a lost link is let go;
# also a noisy sensor, a clench as the forehead sees it, and a head turn.

CTRL_C = "ctrl_c"  # a scripted key that arrives as the console's interrupt signal
Sensors = Literal["head", "light", "covered"]  # where the optical sensors are

EEG_RANGE_UV = (-725.04, 724.96)  # (raw - 8192) * 1450 / 16383 for a 14-bit raw value
REST_OFFSET_UV = (1.0, -54.0, 10.0, 2.0)  # TP9, AF7, AF8, TP10: real data is not centred
# An input without skin contact floats at a steady level and dips sharply every 12 samples.
FLOAT_UV, FLOAT_SCATTER_UV = 115.0, 25.0
FLOAT_DIP_UV = np.array([-75.0, -675.0, -460.0] + [0.0] * 9)  # one cycle, from the level
CLENCH_UV = 80.0  # broadband, at both ears
CLENCH_FOREHEAD_UV = 30.0  # ... and weaker on the forehead
NOISY_UV = 150.0  # broadband, on a sensor that touches badly
BLINK_UV, BLINK_S = 150.0, 0.3  # one bump a second on the forehead

# OPT1-16 in BrainFlow wire order (red, ambient, 730 nm, 850 nm), medians on the head. The
# ambient rows OPT5-8 sit on a pedestal near 338 000 counts whatever the light.
OPTICS_HEAD = np.array(
    [
        *(100_792, 103_027, 525, 498),  # red
        *(339_776, 335_887, 339_644, 335_806),  # ambient
        *(160_210, 160_784, 57_752, 72_414),  # 730 nm
        *(151_087, 138_646, 22_010, 28_026),  # 850 nm
    ],
    dtype=np.float64,
)
OPTICS_SCATTER = np.array(
    [95, 128, 23, 24, 41, 29, 41, 27, 262, 238, 1226, 498, 276, 338, 676, 320], dtype=np.float64
)
_AMBIENT, _LED = np.r_[4:8], np.r_[0:4, 8:16]
PULSE_SHARE = 0.002  # heartbeat on the LED rows while on the head
LIGHT_COUNTS = 3000.0  # what room light adds to the ambient rows
LED_IN_LIGHT = 300.0  # an LED row with no skin in front of it
LED_COVERED = 0.6  # ... and under a hand, as a share of its level on the head
BATTERY_SILENT_S = 10.0  # the battery reads 0 until the headband's first status message

# A head turn: there and back, once every two seconds, about the vertical axis.
TURN_DPS, TURN_ACC_G, TURN_HZ = 100.0, 0.04, 0.5
_ACC_X, _GYRO_Z = 0, 5  # MOTION columns


def _optics_levels() -> dict[Sensors, FloatArray]:
    light, covered = OPTICS_HEAD.copy(), OPTICS_HEAD.copy()
    light[_AMBIENT] += LIGHT_COUNTS
    light[_LED] = LED_IN_LIGHT
    covered[_LED] *= LED_COVERED
    return {"head": OPTICS_HEAD, "light": light, "covered": covered}


_OPTICS_LEVEL = _optics_levels()


@dataclass(frozen=True)
class Wearer:
    """What the wearer and the headband do. Times are seconds after the first connection is up."""

    off: tuple[tuple[float, float], ...] = ()  # (from, to): the headband is switched off
    lifted: tuple[tuple[float, float, str], ...] = ()  # (from, to, EEG channel) off the skin
    clench: tuple[tuple[float, float], ...] = ()  # (from, to): jaw clenched
    blinks: tuple[tuple[float, float], ...] = ()  # (from, to): blinking once a second
    noisy: tuple[tuple[float, float, str], ...] = ()  # (from, to, EEG channel) touching badly
    flat: tuple[tuple[float, float, str], ...] = ()  # (from, to, EEG channel) gives one value
    railed: tuple[tuple[float, float, str], ...] = ()  # (from, to, EEG channel) at its limit
    turns: tuple[tuple[float, float], ...] = ()  # (from, to): the head turns there and back
    optics: tuple[tuple[float, Sensors], ...] = ()  # (from, where), in order; on the head before
    keys: tuple[tuple[float, str], ...] = ()  # (when, key); CTRL_C is the signal, not a key
    firmware: str = "3.1.19"
    battery: float = 80.0  # percent
    connect_s: float = 4.0  # how long start() takes
    first_data_s: float = 0.5  # ... and how much later the first sample comes
    scan_s: float = 16.0  # how long start() looks for a headband that is off before it gives up
    stop_s: float = 7.3  # how long stop() takes to release a live link


class Rehearsal:
    """One sitting with a scripted wearer.

    Every source it makes shares one timeline, which begins when the first connection is up, so
    a reconnect finds the wearer where the script has them by then. ``sleep`` is how the modelled
    connect, scan and release times pass.
    """

    def __init__(
        self,
        wearer: Wearer,
        *,
        clock: Clock = time.time,
        sleep: Callable[[float], None] = time.sleep,
        seed: int = 0,
        preset: str = DEFAULT_PRESET,
    ) -> None:
        self.wearer = wearer
        self.clock = clock
        self.sleep = sleep
        self.seed = seed
        self.preset = validate_preset(preset)
        self.t0: float | None = None
        self._keys = sorted(wearer.keys, key=lambda key: key[0])

    def source(self) -> SimulatedAthena:
        return _WornAthena(self)

    def now(self) -> float:
        """Seconds into the script; 0 until it begins."""
        return 0.0 if self.t0 is None else self.clock() - self.t0

    def delay_script(self, seconds: float) -> None:
        """Move everything the wearer still has to do `seconds` later.

        A guided run may wait for a good fit before its first cue; the scripted wearer, who follows
        the cues, waits with it. The headband's own timings (connect, scan, release, switched off)
        stay where they are.
        """
        w = self.wearer

        def spans(xs: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
            return tuple((a + seconds, b + seconds) for a, b in xs)

        def on(xs: tuple[tuple[float, float, str], ...]) -> tuple[tuple[float, float, str], ...]:
            return tuple((a + seconds, b + seconds, ch) for a, b, ch in xs)

        self.wearer = replace(
            w,
            lifted=on(w.lifted),
            clench=spans(w.clench),
            blinks=spans(w.blinks),
            noisy=on(w.noisy),
            flat=on(w.flat),
            railed=on(w.railed),
            turns=spans(w.turns),
            optics=tuple((t + seconds, where) for t, where in w.optics),
        )
        self._keys = [(t + seconds, key) for t, key in self._keys]

    def read_key(self) -> str | None:
        """The next scripted key that is due, the way the CLI's key reader hands keys over."""
        if self.t0 is None or not self._keys or self._keys[0][0] > self.now():
            return None
        _, key = self._keys.pop(0)
        if key == CTRL_C:
            signal.raise_signal(signal.SIGINT)
            return None
        return key


class _WornAthena(SimulatedAthena):
    """One connection to the headband of a `Rehearsal`."""

    def __init__(self, rehearsal: Rehearsal) -> None:
        super().__init__(clock=rehearsal.clock, seed=rehearsal.seed, preset=rehearsal.preset)
        self._rehearsal = rehearsal
        self._device = DeviceInfo(
            name="SimulatedAthena",
            preset=rehearsal.preset,
            driver="simulated",
            firmware=self._wearer.firmware,
        )
        self._shift = 0.0  # this connection's start on the script's timeline
        self._lost_at = np.inf  # ... and when its link dies: the next time the headband goes off
        self._own: dict[StreamKind, np.random.Generator] = {}

    @property
    def _wearer(self) -> Wearer:
        return self._rehearsal.wearer  # read each time: the script may be delayed (delay_script)

    def start(self) -> None:
        now = self._rehearsal.now()
        if any(start <= now < end for start, end in self._wearer.off):
            self._rehearsal.sleep(self._wearer.scan_s)
            raise SourceError("The simulated headband is switched off.")
        self._rehearsal.sleep(self._wearer.connect_s)
        super().start()
        assert self._t0 is not None
        if self._rehearsal.t0 is None:
            self._rehearsal.t0 = self._t0
        self._shift = self._t0 - self._rehearsal.t0
        self._lost_at = min(
            (start for start, end in self._wearer.off if end > self._shift), default=np.inf
        )
        seed = self._rehearsal.seed
        self._own = {k: np.random.default_rng([seed, 10 + i]) for i, k in enumerate(StreamKind)}

    def stop(self) -> None:
        # BrainFlow's release skips its waits when the link is already gone.
        if self._t0 is not None and self._rehearsal.now() < self._lost_at:
            self._rehearsal.sleep(self._wearer.stop_s)
        super().stop()

    def _in_dropout(self, rel: FloatArray) -> np.ndarray:
        # A lost link stays lost: only a new connection brings the data back.
        return (rel < self._wearer.first_data_s) | (self._shift + rel >= self._lost_at)

    def _generate(self, kind: StreamKind, spec: StreamSpec, rel: FloatArray) -> FloatArray:
        data = super()._generate(kind, spec, rel)
        # Drawn for every index, like the signal itself, so the generator stays aligned.
        noise = self._own[kind].standard_normal(data.shape)
        t = self._shift + rel
        if kind is StreamKind.EEG:
            return self._eeg(data, noise, np.rint(rel * spec.sampling_rate).astype(int), t)
        if kind is StreamKind.OPTICS:
            return self._optics(noise, rel, t)
        return self._motion(data, t)

    def _eeg(
        self, data: FloatArray, noise: FloatArray, index: np.ndarray, t: FloatArray
    ) -> FloatArray:
        wearer, names = self._wearer, ATHENA_STREAMS[StreamKind.EEG].channel_names
        data[:, :4] += REST_OFFSET_UV
        for start, end, channel in wearer.lifted:
            rows, ch = (t >= start) & (t < end), names.index(channel)
            floating = FLOAT_UV + FLOAT_DIP_UV[index % 12] + FLOAT_SCATTER_UV * noise[:, ch]
            data[rows, ch] = floating[rows]
        for start, end in wearer.clench:
            rows = (t >= start) & (t < end)
            for ear in (names.index("TP9"), names.index("TP10")):
                data[rows, ear] += CLENCH_UV * noise[rows, ear]
            for forehead in (names.index("AF7"), names.index("AF8")):
                data[rows, forehead] += CLENCH_FOREHEAD_UV * noise[rows, forehead]
        for start, end in wearer.blinks:
            phase = (t - start) % 1.0
            rows = (t >= start) & (t < end) & (phase < BLINK_S)
            bump = BLINK_UV * np.sin(np.pi * phase[rows] / BLINK_S)
            for forehead in (names.index("AF7"), names.index("AF8")):
                data[rows, forehead] += bump
        for start, end, channel in wearer.noisy:
            rows, ch = (t >= start) & (t < end), names.index(channel)
            data[rows, ch] += NOISY_UV * noise[rows, ch]
        for start, end, channel in wearer.flat:
            rows, ch = (t >= start) & (t < end), names.index(channel)
            data[rows, ch] = REST_OFFSET_UV[ch]
        for start, end, channel in wearer.railed:
            data[(t >= start) & (t < end), names.index(channel)] = EEG_RANGE_UV[1]
        return np.clip(data, *EEG_RANGE_UV)

    def _motion(self, data: FloatArray, t: FloatArray) -> FloatArray:
        for start, end in self._wearer.turns:
            rows = (t >= start) & (t < end)
            swing = np.sin(2 * np.pi * TURN_HZ * (t[rows] - start))
            data[rows, _GYRO_Z] += TURN_DPS * swing
            data[rows, _ACC_X] += TURN_ACC_G * swing
        return data

    def _optics(self, noise: FloatArray, rel: FloatArray, t: FloatArray) -> FloatArray:
        wearer = self._wearer
        level = np.tile(OPTICS_HEAD, (rel.size, 1))
        on_head = np.ones(rel.size, dtype=bool)
        for start, sensors in wearer.optics:  # in order, so each holds until the next
            rows = t >= start
            level[rows] = _OPTICS_LEVEL[sensors]
            on_head[rows] = sensors == "head"
        pulse = PULSE_SHARE * np.sin(2 * np.pi * 1.2 * t) * on_head
        level[:, _LED] *= 1 + pulse[:, None]
        optics = np.empty((rel.size, 17))
        optics[:, :16] = level + OPTICS_SCATTER * noise[:, :16]
        optics[:, 16] = np.where(rel < BATTERY_SILENT_S, 0.0, wearer.battery)
        return optics
