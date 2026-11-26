"""MuFuse session recording format v1 (see specs/001-headband-acquisition/contracts)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

FORMAT_VERSION = 1

MarkerKind = Literal["moment", "block_start", "block_end", "system"]
MarkerSource = Literal["keyboard", "system", "ring"]
GapReason = Literal["stall", "disconnect", "timestamp_jump"]


@dataclass(frozen=True)
class Marker:
    t: float
    kind: MarkerKind
    label: str
    source: MarkerSource


@dataclass(frozen=True)
class Gap:
    stream: str
    start: float
    end: float | None
    reason: GapReason


def new_session_id(started_at: float) -> str:
    stamp = datetime.fromtimestamp(started_at, tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"


def stream_filename(kind: str) -> str:
    return f"{kind}.f64"
