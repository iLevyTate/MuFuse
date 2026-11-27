"""The public Muse 2 set, on a tiny folder in its layout (research R12)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from mufuse.cli import app
from mufuse.quality.public_set import (
    BEEP,
    TASKS,
    NotTheSetError,
    public_lines,
    read_edf,
    score_public,
)

FS = 256
RNG = np.random.default_rng(4)


def _field(values: list[str], width: int) -> bytes:
    return b"".join(v.encode("ascii").ljust(width)[:width] for v in values)


def write_edf(
    path: Path, signals: dict[str, np.ndarray], annotations: list[tuple[float, str]]
) -> None:
    """A continuous EDF+ file with 1 s records, as the set's Muse 2 files are."""
    seconds = len(next(iter(signals.values()))) // FS
    labels = [*signals, "EDF Annotations"]
    per = [FS] * len(signals) + [60]
    n = len(labels)
    head = b"0".ljust(8) + b" " * 80 + b" " * 80 + b"01.01.25" + b"00.00.00"
    head += str(256 * (n + 1)).encode().ljust(8) + b"EDF+C".ljust(44)
    head += str(seconds).encode().ljust(8) + b"1".ljust(8) + str(n).encode().ljust(4)
    head += _field(labels, 16) + _field([""] * n, 80) + _field(["uV"] * n, 8)
    head += _field(["-1000"] * len(signals) + ["-1"], 8) + _field(
        ["1000"] * len(signals) + ["1"], 8
    )
    head += _field(["-32768"] * n, 8) + _field(["32767"] * n, 8) + _field([""] * n, 80)
    head += _field([str(p) for p in per], 8) + _field([""] * n, 32)
    body = bytearray()
    for r in range(seconds):
        for x in signals.values():
            digital = np.round((x[r * FS : (r + 1) * FS] + 1000) * 65535 / 2000 - 32768)
            body += digital.astype("<i2").tobytes()
        tal = f"+{r}\x14\x14\x00".encode()
        tal += b"".join(
            f"+{t}\x14{text}\x14\x00".encode() for t, text in annotations if r <= t < r + 1
        )
        body += tal.ljust(120, b"\x00")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(head + bytes(body))


def _muse2(seconds: int, beeps: list[float], blinks: list[float]) -> dict[str, np.ndarray]:
    t = np.arange(seconds * FS) / FS
    x = {
        name: 20 * np.sin(2 * np.pi * 10 * t) + 8 * RNG.standard_normal(t.size)
        for name in ("TP9", "AF7", "AF8", "TP10")
    }
    n = round(0.3 * FS)
    for b in blinks:
        first = round(b * FS)
        for name in ("AF7", "AF8"):
            x[name][first : first + n] += 150 * np.sin(np.pi * np.arange(n) / n)
    return {**x, "Right AUX": np.zeros(t.size)}


def _set(root: Path, *, with_beeps: bool = True) -> Path:
    beeps = [20.0 + 3 * k for k in range(5)]
    for sub in (1, 2):
        for task in TASKS.values():
            blinks = [b + 0.3 for b in beeps] if task == TASKS["blink"] else []
            notes = [(1.0, "OVTK_StimulationId_Number_00")]
            notes += [(b, BEEP) for b in beeps] if with_beeps else []
            path = root / "sourcedata" / f"sub-0{sub}" / f"sub-0{sub}_task-{task}_acq-Muse2_eeg.edf"
            write_edf(path, _muse2(40, beeps, blinks), notes)
    return root


def test_an_edf_file_is_read_with_its_annotations(tmp_path: Path) -> None:
    signals = _muse2(3, [], [])
    write_edf(tmp_path / "x.edf", signals, [(1.0, "OVTK_StimulationId_Number_00"), (2.5, BEEP)])
    edf = read_edf(tmp_path / "x.edf")
    assert edf.labels[:4] == ("TP9", "AF7", "AF8", "TP10")
    assert edf.rates[1] == FS
    np.testing.assert_allclose(edf.signal("AF7"), signals["AF7"], atol=2000 / 65535)
    assert (2.5, BEEP) in edf.annotations


def test_blinks_at_the_cue_beeps_are_found(tmp_path: Path) -> None:
    s = score_public(_set(tmp_path))
    assert (s.blinks.found, s.blinks.total, s.blinks.passed) == (10, 10, True)
    assert s.clenches.total == 10  # nobody clenched in this folder: not found
    assert s.clenches.passed is False
    assert s.recordings == 4
    assert not s.passed


def test_cues_that_cannot_be_read_are_not_scored_never_passed(tmp_path: Path) -> None:
    s = score_public(_set(tmp_path, with_beeps=False))
    assert s.blinks.passed is None
    assert len(s.skipped) == 4
    text = "\n".join(public_lines(s))
    assert "not scored" in text
    assert "no cue beeps" in text
    assert "head turns    not scored" in text
    assert text.endswith("RESULT        fail")


def test_a_folder_that_is_not_the_set(tmp_path: Path) -> None:
    with pytest.raises(NotTheSetError):
        score_public(tmp_path)
    shown = CliRunner().invoke(app, ["quality", "score", "--public", str(tmp_path)])
    assert shown.exit_code == 2, shown.output


def test_quality_score_public_prints_the_score(tmp_path: Path) -> None:
    shown = CliRunner().invoke(app, ["quality", "score", "--public", str(_set(tmp_path))])
    assert shown.exit_code == 1, shown.output  # the clenches are missing: the gate is not met
    assert "Public Muse 2 set score (rules 1" in shown.output
    assert "blinks        10 of 10 (100.0%)   pass" in shown.output
