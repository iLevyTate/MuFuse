"""Write the quality reference: a simulated session and the answers the rules give for it.

    uv run python scripts/make_quality_reference.py

It replaces `tests/data/quality_reference/session/` and `answers.json` (simulator data only, no
personal data). Run it when a rules change is meant, and raise `RULES_VERSION` in
`src/mufuse/quality/rules.py` in the same commit when any answer changed. It refuses to write when a
measured value lies within 5% of its limit, since such a value could flip on another machine.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import Rehearsal, Wearer
from mufuse.acquisition.types import Chunk, StreamKind
from mufuse.quality.answer import SessionQuality, to_json
from mufuse.quality.engine import judge
from mufuse.quality.rules import RULES
from mufuse.recording.reader import LoadedSession, load_session
from mufuse.recording.writer import SessionWriter

REFERENCE = Path(__file__).resolve().parents[1] / "tests" / "data" / "quality_reference"
T0 = 1_800_000_000.0  # a fixed start, so the session id and every timestamp are the same each run
SECONDS = 48.0
GAP = (36.0, 37.5)  # samples left out: a time without data
MARGIN = 0.05

WEARER = Wearer(
    blinks=((8.0, 12.0), (32.0, 34.0)),
    clench=((13.0, 15.0),),
    turns=((16.0, 18.0),),
    lifted=((19.0, 22.0, "AF8"),),
    # The ears are made clearly noisy during the clench: the clench alone puts them near 75 µV.
    noisy=((23.0, 25.0, "TP10"), (13.0, 15.0, "TP9"), (13.0, 15.0, "TP10")),
    flat=((26.0, 28.0, "TP9"),),
    railed=((29.0, 31.0, "AF7"),),
    connect_s=0.0,
    first_data_s=0.0,
    scan_s=0.0,
    stop_s=0.0,
)


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _without_gap(chunk: Chunk, first: float) -> Chunk | None:
    keep = ~((chunk.timestamps - first >= GAP[0]) & (chunk.timestamps - first < GAP[1]))
    if not keep.any():
        return None
    return Chunk(chunk.kind, chunk.timestamps[keep], chunk.data[keep])


def record(root: Path) -> Path:
    clock = _Clock(T0)
    source = Rehearsal(WEARER, clock=clock, sleep=clock.advance).source()
    kinds = (StreamKind.EEG, StreamKind.MOTION)
    writer = SessionWriter.create(
        root, source.device, {k: ATHENA_STREAMS[k] for k in kinds}, clock=clock
    )
    source.start()
    first: float | None = None
    for _ in range(round(SECONDS / 0.25)):
        clock.advance(0.25)
        for chunk in source.read():
            if chunk.kind not in kinds or not chunk.n_samples:
                continue
            first = float(chunk.timestamps[0]) if first is None else first
            kept = _without_gap(chunk, first)
            if kept is not None:
                writer.write([kept])
    writer.finalize()
    return writer.session_dir


def too_close(session: LoadedSession, quality: SessionQuality) -> list[str]:
    """Every measured value within 5% of the limit it is compared with."""
    near: list[str] = []

    def check(where: str, value: float, limit: float) -> None:
        if abs(value - limit) < MARGIN * limit:
            near.append(f"{where}: {value:.4g} against {limit:.4g}")

    ts, motion = session.streams[StreamKind.MOTION]
    for a in quality.answers:
        if a.no_data:
            continue
        at = f"{a.start - T0:.0f}"
        for c in a.contact:
            check(f"{at} {c.sensor} spread", c.spread_uv, RULES.flat_uv)
            check(f"{at} {c.sensor} spread", c.spread_uv, RULES.noisy_uv)
            if c.spread_uv > RULES.noisy_uv:
                check(f"{at} {c.sensor} mains share", c.mains_share, RULES.mains_share)
        if a.tension_uv is not None:
            check(f"{at} tension", a.tension_uv, RULES.tension_uv)
        rows = motion[(ts >= a.start) & (ts < a.end)]
        if rows.shape[0] >= RULES.motion_min_n:
            gyro = float(np.sqrt(np.mean(np.sum(rows[:, 3:6] ** 2, axis=1))))
            check(f"{at} gyro", gyro, RULES.gyro_dps)
            for axis in range(3):
                check(f"{at} acc {axis}", float(np.std(rows[:, axis])), RULES.acc_std_g)
    return near


def main() -> int:
    with tempfile.TemporaryDirectory() as scratch:
        folder = record(Path(scratch))
        session = load_session(folder)
        quality = judge(session)
        near = too_close(session, quality)
        if near:
            print("Not written: these values lie within 5% of their limit:")
            print("\n".join(f"  {line}" for line in near))
            return 1
        target = REFERENCE / "session"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(folder, target)
        answers = json.dumps(to_json(quality), indent=1)
        (REFERENCE / "answers.json").write_text(answers + "\n", encoding="utf-8", newline="\n")
    counts = f"{len(quality.answers)} answers, {len(quality.blinks)} blinks"
    print(f"Wrote {target} and answers.json: {counts}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
