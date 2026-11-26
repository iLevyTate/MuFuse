"""Muse S Athena stream layout, mirroring BrainFlow's board descriptors (board id 67).

tests/unit/test_types_and_layout.py checks this against the installed BrainFlow so a driver
change cannot silently shift channels.
"""

from __future__ import annotations

from types import MappingProxyType

from mufuse.acquisition.types import StreamKind, StreamSpec

ATHENA_BOARD_ID = 67  # BoardIds.MUSE_S_ATHENA_BOARD in BrainFlow >= 5.22

# Device presets documented by BrainFlow for Athena (p4129 appears only in the release blog).
ATHENA_PRESETS: frozenset[str] = frozenset(
    {"p20", "p21", "p50", "p51", "p60", "p61", "p1034", "p1035"}
    | {f"p{n}" for n in range(1041, 1047)}
    | {"p4129"}
)
DEFAULT_PRESET = "p1041"

_EEG = ("TP9", "AF7", "AF8", "TP10", "AUX1", "AUX2", "AUX3", "AUX4")
_MOTION = ("ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z")
# BrainFlow always exposes 16 optical rows; presets with fewer optics leave the rest unused.
_OPTICS = (*(f"OPT{i}" for i in range(1, 17)), "BATTERY")

ATHENA_STREAMS: MappingProxyType[StreamKind, StreamSpec] = MappingProxyType(
    {
        StreamKind.EEG: StreamSpec(StreamKind.EEG, _EEG, 256.0, ("uV",) * len(_EEG)),
        StreamKind.MOTION: StreamSpec(
            StreamKind.MOTION, _MOTION, 52.0, ("g",) * 3 + ("deg/s",) * 3
        ),
        StreamKind.OPTICS: StreamSpec(
            StreamKind.OPTICS, _OPTICS, 64.0, ("raw",) * 16 + ("percent",)
        ),
    }
)


def validate_preset(preset: str) -> str:
    if preset not in ATHENA_PRESETS:
        valid = ", ".join(sorted(ATHENA_PRESETS))
        raise ValueError(f"Unknown Athena preset {preset!r}. Valid presets: {valid}")
    return preset
