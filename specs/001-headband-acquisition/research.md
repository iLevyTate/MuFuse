# Research: Headband Acquisition & Recording

## R1 Driver
- **Decision**: BrainFlow 5.24, `BoardIds.MUSE_S_ATHENA_BOARD` (id 67), native BLE, one `BoardShim` with three presets.
- **Rationale**: Maintained, Windows native BLE, preset-aware API, verified enum + descriptors locally:
  DEFAULT 11 rows (EEG 1–4 = TP9,AF7,AF8,TP10; other 5–8; ts 9; marker 10) @256 Hz;
  AUXILIARY 9 rows (accel 1–3, gyro 4–6, ts 7, marker 8) @52 Hz;
  ANCILLARY 20 rows (optics 1–16, battery 17, ts 18, marker 19) @64 Hz.
- **Alternatives**: OpenMuse (no stated license, Windows unverified, LSL dependency), muse-rs (Rust; later reference).
  Driver hidden behind `HeadbandSource` so it can be swapped.

## R2 Device selection
- **Decision**: BrainFlow `serial_number` = device name (e.g., "MuseS-XXXX") for targeted connect; `bleak` scan for
  `mufuse devices`; last device persisted in platformdirs user config.
- **Rationale**: avoids OS pairing; deterministic when multiple headbands are nearby.

## R3 Simulated source
- **Decision**: custom deterministic generator with exact Athena layout (not BrainFlow SYNTHETIC_BOARD, whose
  channel layout differs). EEG = 10 Hz alpha + 1/f-ish noise (µV), IMU = gravity + small noise, optics = DC + 1.2 Hz
  pulse, battery slowly decreasing. Seeded RNG; can inject dropouts for supervisor tests.

## R4 Recording format
- **Decision**: folder per session: `manifest.json`, `<stream>.f64` (row-major little-endian float64, columns =
  timestamp + channels), `markers.jsonl`, `gaps.jsonl`. Row count derived from file size on read.
- **Rationale**: append-only + flush per chunk ⇒ crash-safe (truncated trailing partial row is dropped); trivially
  readable by numpy (`fromfile`) and Dart (`ByteData`); no extra dependencies.
- **Alternatives**: Parquet (needs pyarrow, not append-friendly mid-file), XDF (LSL-centric, weak Dart support),
  EDF+ (fixed record structure, awkward with gaps and float optics), HDF5 (corruption on crash).

## R5 Clock
- **Decision**: BrainFlow timestamp rows (host-side UNIX seconds) are the session clock; markers stamped with
  `time.time()` (same clock). Simulated/playback sources produce timestamps on the same scale.
- **Gap detection**: per stream, a gap is recorded when consecutive timestamps differ by > 5 nominal periods or when
  the supervisor declares a stall.

## R6 Stall & reconnect
- **Decision**: supervisor polls every 50 ms; stall if no new EEG samples for 3 s; reconnect with exponential backoff
  1, 2, 4, 8, 8… s; gap opened at last-sample time and closed at first new sample. Pure logic with injectable clock.

## R7 CLI/UI
- **Decision**: typer + rich Live (4 Hz). Keys during `record`: `space` = moment marker, `1–9` = block markers,
  `q` = stop (msvcrt on Windows; stdin fallback elsewhere).
