"""The check before a guided run: is the headband on well enough to begin?

It waits until both forehead sensors read good and motion data flows, then starts by itself. If
that has not happened after `WAIT_S`, the wearer decides: start anyway (`s`) or stop (`q`); a fit
that comes good while they decide still starts the run. A missing sensor is never a show stopper:
what was out is said on screen and kept as a `check:` marker in the recording. The ear sensors
are noted and never wait for (issue #12, docs/KNOWN-ISSUES.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from mufuse.acquisition.contact import SensorView
from mufuse.guide import Cue, Guide

WAIT_S = 60.0  # how long the check waits for a good fit before the wearer decides
FOREHEAD = ("AF7", "AF8")
EARS = ("TP9", "TP10")
START_KEYS = ("s", "\r", "\n")  # start anyway

Phase = Literal["waiting", "ready", "decide"]

_SAID = {
    "none": "is not connected",
    "noisy": "is noisy",
    "settling": "is still settling",
    "waiting": "has no signal yet",
}


class Preflight:
    """Judges each refresh of the live view; holds no clock of its own."""

    def __init__(self, wait_s: float = WAIT_S) -> None:
        self.wait_s = wait_s

    def phase(self, sensors: Sequence[SensorView], *, motion: bool, elapsed: float) -> Phase:
        if motion and all(_shown(sensors, name) == "good" for name in FOREHEAD):
            return "ready"
        return "decide" if elapsed >= self.wait_s else "waiting"

    def guide(self, *, deciding: bool) -> Guide:
        """What the guide panel shows while the check runs."""
        if deciding:
            text = "Forehead not good yet: keep fitting, s = start anyway, q = stop"
        else:
            text = "Fit the headband until AF7 and AF8 (forehead) read good · s = start anyway"
        # Long enough never to run out: the check ends on the fit or on a key, not on a clock.
        return Guide(cues=(Cue(0.0, text),), duration=24 * 3600.0, title="Pre-flight check")

    def outcome(
        self, sensors: Sequence[SensorView], *, motion: bool, anyway: bool
    ) -> tuple[str, ...]:
        """What the check found, for the screen, once it ends."""
        out = [s for s in sensors if s.shown != "good"]
        if not out and motion:
            return ("Pre-flight: all four EEG sensors good, motion streaming. Starting.",)
        head = "Started without a full fit:" if anyway else "Pre-flight: forehead good. Starting."
        lines = [head]
        lines += [f"  {s.name} {_SAID.get(s.shown, s.shown)}" for s in out]
        if not motion:
            lines.append("  motion data is not streaming: head turns cannot be judged")
        if any(s.name in EARS for s in out):
            lines.append("  the ear sensors are noted only: no conclusion is drawn from them (#12)")
        return tuple(lines)

    def marker(self, sensors: Sequence[SensorView], *, anyway: bool) -> str:
        """The `check:` marker label kept in the recording: how it started and what was out."""
        out = ",".join(s.name for s in sensors if s.shown != "good")
        label = f"check:{'anyway' if anyway else 'ready'}"
        return f"{label}:{out}" if out else label


def _shown(sensors: Sequence[SensorView], name: str) -> str:
    return next((s.shown for s in sensors if s.name == name), "waiting")
