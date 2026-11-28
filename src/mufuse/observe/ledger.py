"""Each interpreter's standing, from the store: judged at its looks, switched for early feedback.

`review` is called when `mufuse serve` starts and by `mufuse interpreters`; a look that has been
reached since the last review is judged then, and only then (006 decisions 7-8).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from mufuse.companion.store import InterpreterState, Store
from mufuse.observe.evaluate import Point, Verdict, next_look, verdict
from mufuse.observe.interpreters import Interpreter


@dataclass(frozen=True)
class Standing:
    interpreter: Interpreter
    state: InterpreterState
    verdict: Verdict

    @property
    def next_look(self) -> int:
        return next_look(self.verdict.evaluation.n, self.interpreter.manifest.looks)


def _day(t: float) -> int:
    return datetime.fromtimestamp(t).toordinal()  # the wearer's own calendar day


def review(store: Store, interpreter: Interpreter) -> Standing:
    m = interpreter.manifest
    state = store.interpreter(m.id)
    points = [
        Point(day=_day(s.asked_t), score=s.score, target=s.answer in m.target)
        for s in store.scored(m.id)
    ]
    found = verdict(
        points,
        state="promoted" if state.state == "promoted" else "shadow",
        last_look=state.last_look,
        looks=m.looks,
        threshold=m.threshold,
    )
    new = replace(state, state=found.state, last_look=found.look)
    if new != state:
        store.set_interpreter(new)
    return Standing(interpreter, new, found)


def set_early(store: Store, interpreter_id: str, on: bool) -> None:
    """Early feedback on or off for one interpreter; never touches its evaluation."""
    store.set_interpreter(replace(store.interpreter(interpreter_id), early=on))


def counts(store: Store, interpreter: Interpreter) -> tuple[int, int]:
    """(target answers where it fired, times it fired) over the evaluated random check-ins."""
    m = interpreter.manifest
    fired = [s for s in store.scored(m.id) if s.score >= m.threshold]
    return sum(s.answer in m.target for s in fired), len(fired)
