"""The fNIRS protocol: cues, guide and scorer on synthetic signals (004 decisions 6-7)."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.fnirs.mbll import EXPERIMENTAL
from mufuse.fnirs.pipeline import Hemo
from mufuse.fnirs.protocol import (
    ARITHS,
    END_S,
    HOLDS,
    FCue,
    cues_from_markers,
    protocol_guide,
    schedule,
    score,
    score_lines,
)
from mufuse.recording.format import Marker

FS = 64.0


def _hemo(outer: np.ndarray, t: np.ndarray) -> Hemo:
    hbo = np.column_stack([outer * 0.2, outer * 0.2, outer, outer])
    return Hemo(t=t, hbo=hbo, hbr=-0.3 * hbo, glare=0, moving=0, short_pieces=0)


def _blocks(sign_hold: float, sign_arith: float) -> Hemo:
    t = np.arange(0.0, END_S + 5.0, 1 / FS)
    x = np.zeros_like(t)
    for onset in HOLDS:
        x[(t >= onset + 10.0) & (t < onset + 40.0)] = sign_hold
    for onset in ARITHS:
        x[(t >= onset + 3.0) & (t < onset + 30.0)] = sign_arith
    return _hemo(x, t)


def test_the_schedule_has_rest_five_holds_five_counts_and_an_end() -> None:
    kinds = [c.kind for c in schedule()]
    assert kinds == ["rest", *["hold"] * 5, *["arith"] * 5, "end"]
    assert [c.label for c in schedule()][:2] == ["f:rest", "f:hold"]


def test_the_guide_writes_every_cue_marker_and_never_asks_for_closed_eyes() -> None:
    guide = protocol_guide()
    markers = [c.marker for c in guide.cues if c.marker]
    assert markers == [c.label for c in schedule()]
    assert not any("eyes closed" in c.text.lower() for c in guide.cues)


def test_only_f_system_markers_are_cues() -> None:
    markers = [
        Marker(t=5.0, kind="system", label="f:hold", source="system"),
        Marker(t=1.0, kind="system", label="f:rest", source="system"),
        Marker(t=2.0, kind="system", label="q:blink", source="system"),
        Marker(t=3.0, kind="moment", label="f:hold", source="keyboard"),
        Marker(t=4.0, kind="system", label="f:dance", source="system"),
    ]
    assert cues_from_markers(markers) == (FCue(1.0, "rest"), FCue(5.0, "hold"))


def test_every_block_up_passes() -> None:
    result = score(_blocks(1.0, 0.5), schedule())
    assert result.share == 1.0
    assert result.passed
    assert len(result.scored) == 10


def test_holds_up_and_arithmetic_down_is_half() -> None:
    result = score(_blocks(1.0, -0.5), schedule())
    assert result.share == pytest.approx(0.5)
    assert not result.passed


def test_the_hold_window_skips_the_early_dip() -> None:
    t = np.arange(0.0, END_S + 5.0, 1 / FS)
    x = np.zeros_like(t)
    for onset in HOLDS:  # a dip in the first 10 s, then the late rise
        x[(t >= onset) & (t < onset + 10.0)] = -1.0
        x[(t >= onset + 15.0) & (t < onset + 35.0)] = 1.0
    result = score(_hemo(x, t), schedule())
    assert all(b.expected for b in result.blocks if b.kind == "hold")


def test_a_block_without_signal_is_not_scored() -> None:
    hemo = _blocks(1.0, 1.0)
    hemo.hbo[(hemo.t >= HOLDS[0] - 10.0) & (hemo.t < HOLDS[0] + 40.0)] = np.nan
    result = score(hemo, schedule())
    assert result.blocks[0].change_um is None
    assert len(result.scored) == 9


def test_the_report_is_labelled_experimental_and_names_the_gate() -> None:
    text = "\n".join(score_lines(score(_blocks(1.0, 0.5), schedule())))
    assert EXPERIMENTAL in text
    assert "10 of 10 blocks (100%)" in text
    assert "70% across 5 sessions" in text
    empty = score(_hemo(np.full(10, np.nan), np.arange(10.0)), schedule())
    assert "not scored" in "\n".join(score_lines(empty))
