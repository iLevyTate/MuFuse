"""The answer for one stretch: what later features read instead of judging the signal again."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from mufuse.acquisition.contact import SENSORS as _SENSORS
from mufuse.quality.rules import RULES_VERSION

State = Literal["good", "settling", "noisy", "none"]
Reason = Literal["flat", "railed", "hum", "floating", "loud"]
Level = Literal["full", "reduced", "one_forehead", "none"]
Mark = Literal["yes", "no", "unavailable"]
Movement = Literal["still", "moving", "unknown"]
SpanKind = Literal["tension", "movement"]

SENSORS: tuple[str, ...] = tuple(_SENSORS)  # TP9, AF7, AF8, TP10
FOREHEAD = ("AF7", "AF8")  # the only EEG sensors a mark may read


@dataclass(frozen=True)
class ContactState:
    """How one sensor touches the skin in one stretch. `noisy` and `none` always carry a reason."""

    sensor: str
    state: State
    reason: Reason | None
    spread_uv: float
    mains_share: float


@dataclass(frozen=True)
class Coverage:
    """How much of the head a stretch covers, and the sensors that are out (TP9, AF7, AF8, TP10)."""

    level: Level
    out: tuple[str, ...]


def coverage_of(contact: Sequence[ContactState]) -> Coverage:
    """`full`, else `reduced` when both forehead sensors are good, else what is left."""
    out = tuple(c.sensor for c in contact if c.state != "good")
    forehead = sum(name not in out for name in FOREHEAD)
    if not out:
        return Coverage("full", ())
    level: Level = "reduced" if forehead == 2 else "one_forehead" if forehead == 1 else "none"
    return Coverage(level, out)


@dataclass(frozen=True)
class Blink:
    """One blink or short eye movement on the forehead sensors."""

    t: float  # its first sample, seconds
    duration_s: float


@dataclass(frozen=True)
class Span:
    """Stretches in a row with the same mark, from the start of the first to the end of the last."""

    kind: SpanKind
    start: float
    end: float


@dataclass(frozen=True)
class SessionQuality:
    """The whole of one session, in time order: what `judge()` returns."""

    rules: str
    answers: tuple[QualityAnswer, ...]
    blinks: tuple[Blink, ...]
    tension_spans: tuple[Span, ...]
    movement_spans: tuple[Span, ...]

    @classmethod
    def of(
        cls,
        answers: Sequence[QualityAnswer],
        blinks: Sequence[Blink],
        rules: str = RULES_VERSION,
    ) -> SessionQuality:
        answers = tuple(answers)
        return cls(
            rules=rules,
            answers=answers,
            blinks=tuple(blinks),
            tension_spans=spans(answers, "tension"),
            movement_spans=spans(answers, "movement"),
        )


def spans(answers: Sequence[QualityAnswer], kind: SpanKind) -> tuple[Span, ...]:
    """Marked stretches in a row are one span; an unmarked stretch or a gap ends it (rules §7)."""
    found: list[Span] = []
    start = end = 0.0
    open_ = False
    for answer in answers:
        marked = not answer.no_data and (
            answer.tension == "yes" if kind == "tension" else answer.movement == "moving"
        )
        if marked:
            start, end, open_ = (start if open_ else answer.start), answer.end, True
        elif open_:
            found.append(Span(kind, start, end))
            open_ = False
    if open_:
        found.append(Span(kind, start, end))
    return tuple(found)


@dataclass(frozen=True)
class QualityAnswer:
    """One stretch of a session: contact per sensor, coverage, and the three marks."""

    start: float
    end: float
    rules: str
    contact: tuple[ContactState, ...]
    coverage: Coverage
    eye: Mark
    tension: Mark
    tension_uv: float | None
    movement: Movement
    no_data: bool = False

    @classmethod
    def gap(cls, start: float, end: float) -> QualityAnswer:
        """The answer for a time without samples."""
        return cls(
            start=start,
            end=end,
            rules=RULES_VERSION,
            contact=(),
            coverage=Coverage("none", SENSORS),
            eye="unavailable",
            tension="unavailable",
            tension_uv=None,
            movement="unknown",
            no_data=True,
        )

    def state(self, sensor: str) -> ContactState:
        for contact in self.contact:
            if contact.sensor == sensor:
                return contact
        raise KeyError(sensor)

    @property
    def disturbances(self) -> tuple[str, ...]:
        """What disturbs every sensor of the stretch: the marks first, then what is not known."""
        if self.no_data:
            return ("no_data",)
        found: list[str] = []
        if self.eye == "yes":
            found.append("eye")
        if self.tension == "yes":
            found.append("tension")
        if self.movement == "moving":
            found.append("movement")
        if self.eye == "unavailable":
            found.append("eye_unavailable")
        if self.tension == "unavailable":
            found.append("tension_unavailable")
        if self.movement == "unknown":
            found.append("movement_unknown")
        return tuple(found)

    def clean(self, sensor: str) -> bool:
        return not self.reasons(sensor)

    def reasons(self, sensor: str) -> tuple[str, ...]:
        """Why `sensor` is not clean in this stretch; empty when it is."""
        if self.no_data:
            return ("no_data",)
        contact = self.state(sensor)
        if contact.state == "good":
            return self.disturbances
        part = contact.state if contact.reason is None else f"{contact.state}:{contact.reason}"
        return (part, *self.disturbances)
