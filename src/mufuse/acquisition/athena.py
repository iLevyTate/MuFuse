"""Muse S Athena stream layout, mirroring BrainFlow's board descriptors (board id 67).

tests/unit/test_types_and_layout.py checks this against the installed BrainFlow so a driver
change cannot silently shift channels.
"""

from __future__ import annotations

from types import MappingProxyType

from mufuse.acquisition.types import StreamKind, StreamSpec

ATHENA_BOARD_ID = 67  # BoardIds.MUSE_S_ATHENA_BOARD in BrainFlow >= 5.22

# Device presets documented by BrainFlow for Athena (p4129 appears only in the release blog).
# Preset names are hex codes: the headset reports the active one in its status reply as a decimal
# `ps`, e.g. 4161 = 0x1041. It ignores a preset it does not support, without an error.
ATHENA_PRESETS: frozenset[str] = frozenset(
    {"p1034", "p1035"} | {f"p{n}" for n in range(1041, 1047)} | {"p4129"}
)
# BrainFlow also accepts these older Muse presets, but on the Athena they give no optics at all
# (OpenMuse, muse-rs), and every MuFuse session records an optics stream.
NO_OPTICS_PRESETS: frozenset[str] = frozenset({"p20", "p21", "p50", "p51", "p60", "p61"})
DEFAULT_PRESET = "p1041"

_EEG = ("TP9", "AF7", "AF8", "TP10", "AUX1", "AUX2", "AUX3", "AUX4")
_MOTION = ("ACC_X", "ACC_Y", "ACC_Z", "GYRO_X", "GYRO_Y", "GYRO_Z")
# BrainFlow always exposes 16 optical rows in wire order. With the 16-channel presets (p1041,
# p1042) they are OPT1-4 red, 5-8 ambient, 9-12 730 nm, 13-16 850 nm, each group LI, RI, LO, RO.
# Those labels hold for the 16-channel presets only. The 8-channel presets (p1034, p1043, p1044)
# fill OPT1-8 and the 4-channel ones (p1035, p1045, p1046) OPT1-4; the other rows stay 0. libMuse
# names the 8 as 730 LO, 730 RO, 850 LO, 850 RO, 730 LI, 730 RI, 850 LI, 850 RI and the 4 as
# 730 LI, 730 RI, 850 LI, 850 RI; whether BrainFlow's rows follow that order is not verified.
# Neither layout has an ambient row.
# Never subtract the ambient rows in software: the headset appears to do it already (its LED rows
# read below the ambient level, and the power setting scales the LED rows, not the ambient ones).
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
    if preset in NO_OPTICS_PRESETS:
        raise ValueError(
            f"Preset {preset!r} gives no optics on the Muse S Athena, and MuFuse records them. "
            f"Use {DEFAULT_PRESET} (or p1042 for brighter optics)."
        )
    if preset not in ATHENA_PRESETS:
        valid = ", ".join(sorted(ATHENA_PRESETS))
        raise ValueError(f"Unknown Athena preset {preset!r}. Valid presets: {valid}")
    return preset


def preset_code(preset: str) -> int | None:
    """The number the headset reports for `preset` in its status reply: the name read as hex."""
    try:
        return int(preset.removeprefix("p"), 16)
    except ValueError:
        return None


def preset_from_code(code: int) -> str:
    return f"p{code:x}"


def preset_warning(requested: str, active: str | None) -> str | None:
    """What to say when the headset reports another preset than the one asked for."""
    if active is None or preset_code(active) == preset_code(requested):
        return None
    return (
        f"the headset reports preset {active}, not the requested {requested}: it ignores a "
        "preset it does not support. Reconnect, or choose another preset"
    )
