"""Append-only, crash-safe session writer.

Every chunk is appended as little-endian float64 rows (t, channels...) and flushed, so a crash
at any instant leaves a readable session; the manifest is replaced atomically on finalize.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import IO, Any

import numpy as np

from mufuse.acquisition.types import Chunk, DeviceInfo, StreamKind, StreamSpec
from mufuse.recording.format import FORMAT_VERSION, Gap, Marker, new_session_id, stream_filename

_LE_F64 = np.dtype("<f8")


class SessionWriter:
    def __init__(
        self,
        session_dir: Path,
        manifest: dict[str, Any],
        streams: Mapping[StreamKind, StreamSpec],
        clock: Callable[[], float],
    ) -> None:
        self.session_dir = session_dir
        self._manifest = manifest
        self._streams = streams
        self._clock = clock
        self._files: dict[StreamKind, IO[bytes]] = {
            k: (session_dir / stream_filename(k.value)).open("ab") for k in streams
        }
        self._jsonl = {
            name: (session_dir / f"{name}.jsonl").open("a", encoding="utf-8")
            for name in ("markers", "gaps")
        }
        self._received = dict.fromkeys(streams, 0)
        self._first_t: dict[StreamKind, float] = {}
        self._last_t: dict[StreamKind, float] = {}
        self._finalized = False

    @classmethod
    def create(
        cls,
        root: Path,
        device: DeviceInfo,
        streams: Mapping[StreamKind, StreamSpec],
        *,
        notes: str = "",
        clock: Callable[[], float] = time.time,
    ) -> SessionWriter:
        started_at = clock()
        session_id = new_session_id(started_at)
        session_dir = root / session_id
        session_dir.mkdir(parents=True, exist_ok=False)
        manifest: dict[str, Any] = {
            "format_version": FORMAT_VERSION,
            "session_id": session_id,
            "started_at": started_at,
            "ended_at": None,
            "notes": notes,
            "software_version": version("mufuse"),
            "device": asdict(device),
            "streams": {
                k.value: {
                    "file": stream_filename(k.value),
                    "columns": ["t", *spec.channel_names],
                    "sampling_rate": spec.sampling_rate,
                    "units": ["s", *spec.units],
                }
                for k, spec in streams.items()
            },
            "completeness": None,
        }
        _write_json_atomic(session_dir / "manifest.json", manifest)
        return cls(session_dir, manifest, streams, clock)

    def write(self, chunks: Iterable[Chunk]) -> None:
        for chunk in chunks:
            if chunk.n_samples == 0:
                continue
            rows = np.column_stack([chunk.timestamps, chunk.data]).astype(_LE_F64, copy=False)
            fh = self._files[chunk.kind]
            fh.write(rows.tobytes())
            fh.flush()
            self._received[chunk.kind] += chunk.n_samples
            self._first_t.setdefault(chunk.kind, float(chunk.timestamps[0]))
            self._last_t[chunk.kind] = float(chunk.timestamps[-1])

    def add_marker(self, marker: Marker) -> None:
        self._append_jsonl("markers", asdict(marker))

    def add_gap(self, gap: Gap) -> None:
        self._append_jsonl("gaps", asdict(gap))

    def finalize(self, lost_subpackets: Mapping[StreamKind, int] | None = None) -> None:
        if self._finalized:
            return
        self.close_files()
        self._manifest["ended_at"] = self._clock()
        self._manifest["completeness"] = {
            k.value: {"expected": self._expected(k), "received": self._received[k]}
            for k in self._streams
        }
        if lost_subpackets is not None:
            # Lost on the headset link, by the device's own counter. An optional key of
            # format 1: sessions written before it existed do not have it.
            self._manifest["lost_subpackets"] = {
                k.value: int(n) for k, n in lost_subpackets.items()
            }
        _write_json_atomic(self.session_dir / "manifest.json", self._manifest)
        self._finalized = True

    def close_files(self) -> None:
        for fh in (*self._files.values(), *self._jsonl.values()):
            if not fh.closed:
                fh.close()

    def _expected(self, kind: StreamKind) -> int:
        if kind not in self._first_t:
            return 0
        span = self._last_t[kind] - self._first_t[kind]
        return round(span * self._streams[kind].sampling_rate) + 1

    def _append_jsonl(self, name: str, record: dict[str, Any]) -> None:
        fh = self._jsonl[name]
        fh.write(json.dumps(record) + "\n")
        fh.flush()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
