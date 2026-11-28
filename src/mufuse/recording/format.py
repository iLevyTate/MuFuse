"""MuFuse session recording format v1 (see specs/001-headband-acquisition/contracts)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

FORMAT_VERSION = 1

MarkerKind = Literal["moment", "block_start", "block_end", "system"]
MarkerSource = Literal["keyboard", "system", "ring", "app"]  # app: the desk strip (005)
GapReason = Literal["stall", "disconnect", "timestamp_jump"]
ReconnectWhat = Literal["lost", "released", "attempt", "failed", "connected", "first_sample"]


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


@dataclass(frozen=True)
class ReconnectStep:
    """One step of losing the headband and getting it back, at the recorder's clock time `t`:
    the signal counted as lost (detail: the gap's reason), the old connection released, an
    attempt begun, failed (detail: the error) or connected, and the first sample after it."""

    t: float
    what: ReconnectWhat
    detail: str | None = None


def new_session_id(started_at: float) -> str:
    stamp = datetime.fromtimestamp(started_at, tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(2)}"


def stream_filename(kind: str) -> str:
    return f"{kind}.f64"
