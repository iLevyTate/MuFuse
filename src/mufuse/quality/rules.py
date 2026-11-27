"""Rules v1: every limit the quality answer depends on, in one place.

The rules are stated in `specs/002-signal-quality/contracts/quality-rules.md`. A change here that
changes an answer for the reference recording is a new rules version.
"""

from __future__ import annotations

from dataclasses import dataclass

from mufuse.acquisition.contact import MAINS_SHARE
from mufuse.acquisition.signal_check import FLAT_UV, NOISY_UV, RAIL_FRACTION, RAIL_UV

RULES_VERSION = "1"


@dataclass(frozen=True)
class Rules:
    """The limits of one rules version. Lengths ending in `_n` count EEG samples at 256 Hz."""

    version: str = RULES_VERSION

    # Stretches (section 1)
    stretch_n: int = 256
    gap_s: float = 0.25
    ahead_n: int = 64  # samples after a stretch that its eye mark reads
    motion_wait_s: float = 1.0

    # Contact (section 2). `grade_window` holds these limits; they are repeated here to be read.
    rail_uv: float = RAIL_UV
    rail_share: float = RAIL_FRACTION
    flat_uv: float = FLAT_UV
    noisy_uv: float = NOISY_UV
    mains_share: float = MAINS_SHARE
    hold_stretches: int = 3

    # Eye mark and blinks (section 4)
    eye_band_hz: tuple[float, float] = (1.0, 10.0)
    envelope_n: int = 32
    limit_s: float = 30.0
    limit_every_n: int = 8
    eye_mad_factor: float = 4.0
    eye_floor_uv: float = 15.0
    eye_min_n: int = 16
    eye_margin_n: int = 32  # an eye event this close to a stretch marks it too
    eye_warmup: int = 5  # stretches after an anchor without an eye mark
    blink_max_n: int = 307
    blink_apart_s: float = 0.8

    # Tension (section 5)
    tension_bands_hz: tuple[tuple[int, int], ...] = ((30, 48), (66, 98))
    tension_skip_hz: tuple[int, ...] = (42, 43, 44, 84, 85, 86)
    tension_uv: float = 10.0

    # Movement (section 6)
    motion_min_n: int = 26
    gyro_dps: float = 20.0
    acc_std_g: float = 0.05


RULES = Rules()
