"""One conversation (007 decisions 1, 6-8): crisis check, then the summary, a model, the filter.

`ChatSession.ask` holds no engine state and no lock: the caller makes the summary, then asks, so a
slow model never holds up the headband loop.
"""

from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from mufuse.chat.crisis import CRISIS_REPLY, is_crisis
from mufuse.chat.filter import check
from mufuse.chat.models import Model, ModelUnavailableError, Turn
from mufuse.chat.summary import PARK, Summary, template_answer

Source = Literal["model", "template", "filtered", "crisis", "late"]
NIGHT = (23, 5)  # 23:00 to 05:00 local time
NIGHT_PER_HOUR = 20
HISTORY = 12  # turns kept for the model

_HEAVY = re.compile(
    r"\b(?:grief|griev\w*|loss|lost\s+(?:my|a)|died|funeral|panic\w*|can'?t\s+cope|"
    r"breaking\s+down|falling\s+apart|hopeless\w*|worthless|terrified|abuse\w*)\b",
    re.IGNORECASE,
)

SYSTEM = """You word short replies for MuFuse, a headband tool that describes the wearer's own
signals against their own baseline. Rules you must keep:
- Use only the facts in the summary below. Never invent numbers or changes.
- Answer in three short parts: what changed, how far to trust it (signal quality), and one open
  question back to the wearer.
- Describe signals, never the person: no "you are/seem/feel", no states, moods or traits.
- No conditions, diagnoses, symptoms, treatment or medical advice, no accuracy claims.
- Never claim to know what the wearer thinks or feels. Plain words, at most four sentences.
- Plain text only: no Markdown, no headings, labels, bold or bullet points.

Summary (made by code):
{summary}"""

LATE = (
    "It's late, and we've talked a lot this hour. " + PARK + " The check-ins and the strip keep"
    " working in the meantime."
)


@dataclass(frozen=True)
class Reply:
    text: str
    source: Source
    model: str | None
    cloud: bool
    blocked: tuple[str, ...] = ()


class ChatSession:
    def __init__(
        self,
        models: Callable[[], Sequence[Model]],
        *,
        clock: Callable[[], float] = time.time,
        hour_of: Callable[[float], int] = lambda t: datetime.fromtimestamp(t).hour,
    ) -> None:
        self._models = models  # asked each turn: cloud may be switched on or off in between
        self._clock = clock
        self._hour_of = hour_of
        self._turns: deque[Turn] = deque(maxlen=HISTORY)
        self._night: deque[float] = deque()

    def _late(self, now: float) -> bool:
        hour = self._hour_of(now)
        if not (hour >= NIGHT[0] or hour < NIGHT[1]):
            return False
        while self._night and self._night[0] <= now - 3600:
            self._night.popleft()
        if len(self._night) >= NIGHT_PER_HOUR:
            return True
        self._night.append(now)
        return False

    def ask(self, text: str, summary: Summary) -> Reply:
        if is_crisis(text):
            return Reply(CRISIS_REPLY, "crisis", None, cloud=False)  # nothing goes to a model
        now = self._clock()
        if self._late(now):
            return Reply(LATE, "late", None, cloud=False)
        heavy = _HEAVY.search(text) is not None
        fallback = template_answer(summary, heavy=heavy)
        system = SYSTEM.format(summary=summary.as_text())
        if heavy:
            system += "\nThe wearer has said something heavy: do not ask back; offer to park it."
        turns = [*self._turns, {"role": "user", "content": text}]
        reply = Reply(fallback, "template", None, cloud=False)
        for model in self._models():
            try:
                worded = model.reply(system, turns)
            except ModelUnavailableError:
                continue
            verdict = check(worded)
            if verdict.ok:
                reply = Reply(worded, "model", model.name, model.cloud)
            else:
                reply = Reply(fallback, "filtered", model.name, model.cloud, verdict.reasons)
            break
        self._turns.append({"role": "user", "content": text})
        self._turns.append({"role": "assistant", "content": reply.text})
        return reply
