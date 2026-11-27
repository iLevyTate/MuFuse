"""Load a MuFuse session folder into aligned numpy arrays."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from mufuse.acquisition.types import FloatArray, StreamKind
from mufuse.recording.format import Gap, Marker, ReconnectStep


@dataclass(frozen=True)
class LoadedSession:
    path: Path
    manifest: dict[str, Any]
    streams: dict[StreamKind, tuple[FloatArray, FloatArray]]  # kind -> (timestamps, data)
    markers: list[Marker]
    gaps: list[Gap]
    reconnects: list[ReconnectStep] = field(default_factory=list[ReconnectStep])

    @property
    def finalized(self) -> bool:
        return self.manifest["ended_at"] is not None


def load_session(path: Path) -> LoadedSession:
    manifest: dict[str, Any] = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    streams: dict[StreamKind, tuple[FloatArray, FloatArray]] = {}
    for kind_name, meta in manifest["streams"].items():
        n_cols = len(meta["columns"])
        raw = np.fromfile(path / meta["file"], dtype="<f8")
        rows = raw[: (raw.size // n_cols) * n_cols].reshape(-1, n_cols)  # drop a torn row
        streams[StreamKind(kind_name)] = (
            rows[:, 0].astype(np.float64),
            rows[:, 1:].astype(np.float64),
        )
    return LoadedSession(
        path=path,
        manifest=manifest,
        streams=streams,
        markers=[Marker(**r) for r in _read_jsonl(path / "markers.jsonl")],
        gaps=[Gap(**r) for r in _read_jsonl(path / "gaps.jsonl")],
        reconnects=[ReconnectStep(**r) for r in _read_jsonl(path / "reconnects.jsonl")],
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            break  # torn final line after a crash
    return records
