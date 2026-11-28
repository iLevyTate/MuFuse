"""The frozen fNIRS reference (004 decision 9): a failure means the pipeline changed."""

from __future__ import annotations

import json
import math

from mufuse.fnirs.mbll import FNIRS_VERSION
from tests.fnirs_reference import REFERENCE, reference_hemo, to_json


def _close(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is b
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6)


def test_the_output_matches_the_frozen_reference() -> None:
    """If meant: rerun scripts/make_fnirs_reference.py and raise FNIRS_VERSION."""
    stored = json.loads(REFERENCE.read_text(encoding="utf-8"))
    now = to_json(reference_hemo())
    assert stored["fnirs"] == FNIRS_VERSION
    assert now["moving"] == stored["moving"]
    assert now["t"] == stored["t"]
    for part in ("hbo", "hbr"):
        got, want = now[part], stored[part]
        assert isinstance(got, list)
        assert len(got) == len(want)
        for i, (g_row, w_row) in enumerate(zip(got, want, strict=True)):
            for g, w in zip(g_row, w_row, strict=True):
                assert _close(g, w), (part, i, g, w)


def test_the_reference_holds_left_out_and_used_samples() -> None:
    stored = json.loads(REFERENCE.read_text(encoding="utf-8"))
    cells = [v for row in stored["hbo"] for v in row]
    assert any(v is None for v in cells)  # the head turn
    assert sum(v is not None for v in cells) > 0.9 * len(cells)
