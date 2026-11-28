"""What the chat knows, as a summary made by code, and the three-part answer made from it alone.

The summary is all a model ever receives about the signal (007 decision 4): no raw samples, no
recordings. The template answer is what is sent when no model answers or the filter blocks one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

QUESTION_BACK = "What was going on for you just then?"
PARK = "We can park this for later; it will keep."


@dataclass(frozen=True)
class Summary:
    forehead_good: int  # 0-2 forehead sensors with good contact
    fix: str | None  # the sensor to fix when neither is good
    line: str  # describe.baseline_line: words for the signal against the baseline
    observations: Sequence[tuple[str, float]] = field(default_factory=tuple[tuple[str, float]])
    last_answer: str | None = None  # the newest check-in answer, if any

    def as_text(self) -> str:
        """The summary as plain lines, for a model."""
        lines = [
            f"Signal: {self.forehead_good} of 2 forehead sensors good"
            + (f"; fix {self.fix} first" if self.fix else ""),
            f"Against the wearer's baseline: {self.line}",
        ]
        for text, minutes in self.observations:
            lines.append(f"Observation: {text} for about {_minutes(minutes)}")
        if self.last_answer:
            lines.append(f"Last check-in answer: {self.last_answer}")
        lines.append("Ear sensors are not read (known hardware issue).")
        return "\n".join(lines)


def _minutes(m: float) -> str:
    return "1 minute" if round(m) <= 1 else f"{round(m)} minutes"


def template_answer(s: Summary, *, heavy: bool = False) -> str:
    """What changed, how far to trust it, and a question back (or a pause after a heavy answer)."""
    if s.forehead_good == 0:
        return (
            f"I can't read anything right now: the signal is poor (fix {s.fix or 'the forehead'}"
            " first). Once it is good again I can tell you what changes."
        )
    if s.observations:
        changed = "; ".join(f"{t} for about {_minutes(m)}" for t, m in s.observations)
        what = changed[0].upper() + changed[1:] + "."
    elif s.line == "learning your baseline":
        what = "I'm still learning your baseline, so I can't compare yet."
    else:
        what = f"Nothing stands out against your baseline: {s.line}."
    trust = f"Signal is good on {s.forehead_good} of 2 forehead sensors."
    return f"{what} {trust} {PARK if heavy else QUESTION_BACK}"
