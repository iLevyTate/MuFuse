# Data Model: Headband Acquisition & Recording

| Entity | Fields | Rules |
|---|---|---|
| **StreamKind** | `EEG`, `MOTION`, `OPTICS` | Battery travels in OPTICS stream metadata (ancillary preset) as its own column |
| **StreamSpec** | kind, channel_names: tuple[str], sampling_rate: float, units: tuple[str] | channel_names excludes timestamp; rate > 0 |
| **Chunk** | kind, timestamps: float64[n], data: float64[n, c] | n ≥ 0; timestamps strictly increasing within a chunk; c == len(spec.channel_names) |
| **DeviceInfo** | name, address \| None, preset, driver ("brainflow-5.24" / "simulated" / "playback"), firmware \| None | preset ∈ ATHENA_PRESETS |
| **Marker** | t: float, kind: `moment` \| `block_start` \| `block_end` \| `system`, label: str, source: `keyboard` \| `system` \| `ring` | t on session clock |
| **Gap** | stream kind, start: float, end: float \| None, reason: `stall` \| `disconnect` \| `timestamp_jump` | end ≥ start once closed |
| **Session** | id (UTC `YYYYMMDDTHHMMSSZ-<4hex>`), started_at, ended_at, notes, device, streams{kind→spec}, format_version, software_version, completeness{kind→{expected, received}} | written at start, finalized at stop |

Supervisor state machine: `DISCONNECTED → CONNECTING → STREAMING → STALLED → RECONNECTING → STREAMING | FAILED`.
