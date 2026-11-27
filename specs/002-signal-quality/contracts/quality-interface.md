# Contract: Quality interface

What the live view, `inspect`, the scorer and later features (003, 005, 006) use. They read these answers; they do
not judge quality themselves (FR-014).

```python
# mufuse.quality
RULES_VERSION: str  # "1"


class QualityEngine:
    def __init__(self, rules: Rules = RULES) -> None: ...
    def feed(self, chunks: Sequence[Chunk]) -> Judged: ...  # any chunk sizes, any stream order
    def finish(self) -> Judged: ...  # end of session: judge what still waits


@dataclass(frozen=True)
class Judged:
    answers: tuple[QualityAnswer, ...]  # newly judged stretches and gaps, in time order
    blinks: tuple[Blink, ...]  # blinks that ended since the last call


def judge(session: LoadedSession, rules: Rules = RULES) -> SessionQuality: ...
def summarize(quality: SessionQuality) -> QualitySummary: ...


class QualityAnswer:  # fields: data-model.md
    def clean(self, sensor: str) -> bool: ...
    def reasons(self, sensor: str) -> tuple[str, ...]: ...
    @property
    def disturbances(self) -> tuple[str, ...]: ...


def to_json(quality: SessionQuality) -> dict[str, object]: ...
```

Guarantees:

- **Same data, same answers.** Feeding the same samples and timestamps gives the same answers and blinks, whatever
  the chunk sizes, the order of streams within one `feed()` call, the time of day or the machine. `judge(session)`
  equals the collected results of `feed()` plus `finish()` over the live run that wrote the session.
- **No clock, no network, no file.** The engine reads only what it is fed and writes nothing.
- **Forehead only.** Replacing the TP9 and TP10 columns by any signal changes only the contact states of TP9 and
  TP10, the coverage level between `full` and `reduced`, and `out`. No mark, blink, level or AF7/AF8 state changes.
- **Never silent.** A value that cannot be judged is `unavailable`, `unknown` or a no-data answer. It is never
  `no`, `still`, zero or clean.
- **Final.** An answer is not changed after it is returned. A stretch is returned about 0.25 s after its end.
- **Versioned.** Every answer, summary and score report carries `rules`.
- **Cost.** `feed()` for one second of signal takes under 5 ms on the user's machine; `judge()` of a 60-minute
  session takes under 30 s including loading.

## JSON form

Used by the golden file and, later, by `mufuse serve` (005). Keys are stable within a rules version.

```json
{
  "rules": "1",
  "answers": [
    {
      "start": 12.0, "end": 13.0,
      "contact": {
        "TP9":  {"state": "none",  "reason": "hum", "spread_uv": 212.4, "mains_share": 0.93},
        "AF7":  {"state": "good",  "reason": null,  "spread_uv": 14.1,  "mains_share": 0.41},
        "AF8":  {"state": "good",  "reason": null,  "spread_uv": 15.0,  "mains_share": 0.38},
        "TP10": {"state": "good",  "reason": null,  "spread_uv": 13.2,  "mains_share": 0.40}
      },
      "coverage": {"level": "reduced", "out": ["TP9"]},
      "eye": "yes", "tension": "no", "tension_uv": 4.8, "movement": "still"
    },
    {"start": 13.0, "end": 15.4, "no_data": true}
  ],
  "blinks": [{"t": 12.41, "duration_s": 0.27}],
  "tension_spans": [],
  "movement_spans": [{"start": 20.0, "end": 22.0}]
}
```

## What a later feature may do

- Skip a stretch for a sensor when `clean(sensor)` is false, or accept some reasons on purpose (for example, a
  blink counter reads `blinks` and ignores the eye mark).
- Use AF7 and AF8 when coverage is `reduced`. `reduced` is a usable session.
- Never treat `unavailable` or `unknown` as "nothing happened".
