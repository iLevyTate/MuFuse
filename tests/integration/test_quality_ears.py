"""Nothing on the forehead depends on the ear sensors (SC-006, FR-006; issue #12)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.types import DeviceInfo, StreamKind
from mufuse.quality.engine import judge
from mufuse.recording.reader import load_session
from mufuse.recording.writer import SessionWriter
from tests.conftest import QUICK, FakeClock, rehearse


def test_ears_without_contact_change_nothing_on_the_forehead(
    tmp_path: Path, clock: FakeClock
) -> None:
    wearer = replace(QUICK, blinks=((8.0, 12.0),), clench=((13.0, 15.0),), turns=((16.0, 18.0),))
    writer = SessionWriter.create(
        tmp_path, DeviceInfo("SimulatedAthena", "p1041", "simulated"), ATHENA_STREAMS, clock=clock
    )
    for read in rehearse(wearer, clock, 25.0):
        writer.write(read)
    writer.finalize()
    worn = load_session(writer.session_dir)
    ts, eeg = worn.streams[StreamKind.EEG]
    off = eeg.copy()
    rng = np.random.default_rng(12)
    t = ts - ts[0]
    for ear in (0, 3):  # TP9, TP10: mostly mains hum, as on the 2026-11-26 sitting
        off[:, ear] = 300.0 * np.sin(2 * np.pi * 60 * t) + 5.0 * rng.standard_normal(t.size)
    lifted = replace(worn, streams={**worn.streams, StreamKind.EEG: (ts, off)})

    a, b = judge(worn), judge(lifted)
    assert len(a.answers) == len(b.answers)
    for x, y in zip(a.answers, b.answers, strict=True):
        for sensor in ("AF7", "AF8"):
            assert x.state(sensor) == y.state(sensor)
        assert (x.eye, x.tension, x.tension_uv, x.movement) == (
            y.eye,
            y.tension,
            y.tension_uv,
            y.movement,
        )
        assert y.state("TP9").state == y.state("TP10").state == "none"
    assert (a.blinks, a.tension_spans, a.movement_spans) == (
        b.blinks,
        b.tension_spans,
        b.movement_spans,
    )
    assert len(a.blinks) == 4
    assert {x.coverage.level for x in b.answers[3:]} == {"reduced"}
    assert any(x.coverage != y.coverage for x, y in zip(a.answers, b.answers, strict=True))
