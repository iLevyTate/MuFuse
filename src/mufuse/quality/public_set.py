"""The second score on the public Muse 2 set (SC-003, research R12).

Lee and Ahn, https://doi.org/10.6084/m9.figshare.30162868.v1, CC BY 4.0, fetched by
`scripts/fetch_muse2_set.py` into a folder outside the repository. Each subject has one EDF+ file
per task and device; the Muse 2 files (`sub-XX_task-<task>_acq-Muse2_eeg.edf`) carry TP9, AF7, AF8
and TP10 at 256 Hz and the cue beeps as annotations, on the file's own clock. The blink and
jaw-clench rules of the labelled session are applied with those beeps as cues. Head turns are not
scored: the Muse 2 files hold no motion data. The files are read, never run.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from mufuse.acquisition.types import Chunk, FloatArray, StreamKind
from mufuse.quality.answer import SENSORS, Blink, QualityAnswer, SessionQuality
from mufuse.quality.engine import QualityEngine
from mufuse.quality.labelled import (
    ALLOWED_S,
    KindScore,
    blinks_found,
    kind_score,
    span_found,
)
from mufuse.quality.rules import RULES, Rules

TASKS = {"blink": "EB", "clench": "BT"}  # task codes; BT is inferred from the data (research R12)
BEEP = "OVTK_StimulationId_Number_02"  # "task performing beep": the cue
EEG_HZ = 256
_TAL = re.compile(rb"([+-][0-9.]+)(?:\x15([0-9.]+))?\x14([^\x00]*)")


class NotTheSetError(ValueError):
    """The folder does not hold the public Muse 2 set."""


@dataclass(frozen=True)
class Edf:
    labels: tuple[str, ...]
    rates: tuple[float, ...]
    signals: tuple[FloatArray, ...]  # physical values, one per label (empty for annotations)
    annotations: tuple[tuple[float, str], ...]  # onset (s from the file start), text

    def signal(self, label: str) -> FloatArray:
        return self.signals[self.labels.index(label)]


def _fields(raw: bytes, n: int, width: int) -> list[str]:
    return [raw[i * width : (i + 1) * width].decode("ascii", "replace").strip() for i in range(n)]


def read_edf(path: Path) -> Edf:
    """A plain EDF or EDF+ (continuous) file: its signals in physical units and its annotations."""
    data = path.read_bytes()
    if len(data) < 256:
        raise ValueError(f"{path.name}: too short for an EDF file")
    header_bytes, records = int(data[184:192]), int(data[236:244])
    duration, n = float(data[244:252]), int(data[252:256])
    raw = data[256 : 256 + 256 * n]
    widths = (16, 80, 8, 8, 8, 8, 8, 80, 8, 32)
    columns: list[list[str]] = []
    off = 0
    for width in widths:
        columns.append(_fields(raw[off:], n, width))
        off += width * n
    labels, phys_min, phys_max = columns[0], columns[3], columns[4]
    dig_min, dig_max, per = columns[5], columns[6], [int(x) for x in columns[8]]
    record = sum(per)
    body = np.frombuffer(data, dtype="<i2", offset=header_bytes, count=records * record)
    body = body.reshape(records, record)
    signals: list[FloatArray] = []
    annotations: list[tuple[float, str]] = []
    first = 0
    for i, label in enumerate(labels):
        block = body[:, first : first + per[i]]
        first += per[i]
        if label == "EDF Annotations":
            signals.append(np.empty(0))
            for tal in block:
                for m in _TAL.finditer(tal.tobytes()):
                    for text in m.group(3).split(b"\x14"):
                        if text:
                            annotations.append((float(m.group(1)), text.decode("latin-1")))
            continue
        d0, d1 = float(dig_min[i]), float(dig_max[i])
        p0, p1 = float(phys_min[i]), float(phys_max[i])
        digital = block.reshape(-1).astype(np.float64)
        signals.append((digital - d0) * (p1 - p0) / (d1 - d0) + p0)
    rates = tuple(p / duration for p in per)
    return Edf(tuple(labels), rates, tuple(signals), tuple(annotations))


@dataclass(frozen=True)
class PublicScore:
    rules: str
    blinks: KindScore
    clenches: KindScore
    recordings: int
    skipped: tuple[str, ...]  # one reason per recording that could not be scored

    @property
    def passed(self) -> bool:
        return self.blinks.passed is True and self.clenches.passed is True


def _files(folder: Path, task: str) -> list[Path]:
    return sorted((folder / "sourcedata").glob(f"sub-*/sub-*_task-{task}_acq-Muse2_eeg.edf"))


def _judge(edf: Edf, rules: Rules) -> SessionQuality:
    columns = [edf.signal(name) for name in SENSORS]
    n = min(c.size for c in columns)
    eeg = np.zeros((n, 8))
    eeg[:, :4] = np.column_stack([c[:n] for c in columns])
    t = np.arange(n) / EEG_HZ
    engine = QualityEngine(rules)
    answers: list[QualityAnswer] = []
    blinks: list[Blink] = []
    for first in range(0, n, 10 * EEG_HZ):  # fed in 10 s pieces, as a recording is judged
        piece = slice(first, first + 10 * EEG_HZ)
        judged = engine.feed([Chunk(StreamKind.EEG, t[piece], eeg[piece])])
        answers += judged.answers
        blinks += judged.blinks
    judged = engine.finish()
    return SessionQuality.of((*answers, *judged.answers), (*blinks, *judged.blinks), rules.version)


def _beeps(edf: Edf) -> list[float]:
    return [onset for onset, text in edf.annotations if text == BEEP]


def _score_task(files: Sequence[Path], kind: str, rules: Rules) -> tuple[int, int, list[str]]:
    found = total = 0
    skipped: list[str] = []
    for path in files:
        try:
            edf = read_edf(path)
            if any(name not in edf.labels for name in SENSORS):
                raise ValueError("not the four Muse sensors")
            if any(abs(edf.rates[edf.labels.index(n)] - EEG_HZ) > 1e-6 for n in SENSORS):
                raise ValueError("not 256 Hz")
        except (OSError, ValueError) as exc:
            skipped.append(f"{path.name}: {exc}")
            continue
        cues = _beeps(edf)
        if not cues:
            skipped.append(f"{path.name}: no cue beeps in its annotations")
            continue
        quality = _judge(edf, rules)
        answers = [a for a in quality.answers if not a.no_data]
        if kind == "blink":
            found += blinks_found(quality, cues)
        else:
            found += sum(span_found(answers, quality.tension_spans, c) for c in cues)
        total += len(cues)
    return found, total, skipped


def score_public(folder: Path, rules: Rules = RULES) -> PublicScore:
    """Blinks on the eye-blink task and clenches on the jaw-clench task, all subjects."""
    blink_files, clench_files = _files(folder, TASKS["blink"]), _files(folder, TASKS["clench"])
    if not blink_files and not clench_files:
        raise NotTheSetError(f"{folder} holds no sourcedata/sub-*/…_acq-Muse2_eeg.edf files")
    b_found, b_total, b_skipped = _score_task(blink_files, "blink", rules)
    c_found, c_total, c_skipped = _score_task(clench_files, "clench", rules)
    return PublicScore(
        rules=rules.version,
        blinks=kind_score(b_found, b_total),
        clenches=kind_score(c_found, c_total),
        recordings=len(blink_files) + len(clench_files),
        skipped=(*b_skipped, *c_skipped),
    )


def public_lines(s: PublicScore) -> list[str]:
    def kind(name: str, k: KindScore) -> str:
        if k.passed is None:
            return f"  {name:<12}  not scored (no cue could be read)"
        share = 100 * k.found / k.total
        verdict = "pass" if k.passed else "fail"
        return f"  {name:<12}  {k.found} of {k.total} ({share:.1f}%)   {verdict}"

    lines = [
        f"Public Muse 2 set score (rules {s.rules}, a mark counts within {ALLOWED_S:.1f} s of its "
        "cue beep)",
        kind("blinks", s.blinks),
        kind("jaw clenches", s.clenches),
        f"  {'head turns':<12}  not scored (the Muse 2 files hold no motion data)",
        f"  {'recordings':<12}  {s.recordings - len(s.skipped)} scored, {len(s.skipped)} skipped",
    ]
    lines += [f"    skipped {reason}" for reason in s.skipped[:10]]
    lines.append(f"  {'RESULT':<12}  {'pass' if s.passed else 'fail'}")
    return lines
