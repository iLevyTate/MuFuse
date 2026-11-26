# Contract: CLI

| Command | Behavior | Exit codes |
|---|---|---|
| `mufuse devices [--timeout 8]` | BLE scan, list Muse devices (name, address, RSSI), mark saved device | 0 found / 3 none |
| `mufuse stream [--source athena\|sim\|play PATH] [--device NAME] [--preset p1041]` | live view until `q`/Ctrl+C | 0 / 2 bad args / 4 connect fail |
| `mufuse record [same opts] [--notes TEXT] [--out DIR] [--duration SEC] [--no-firmware]` | reads firmware over BLE (unless `--no-firmware`), then live view + recording + key markers | 0 / 2 / 4 / 5 write error |
| `mufuse inspect PATH` | print manifest summary, per-stream rows/rate/completeness, markers, gaps | 0 / 6 unreadable |
| `mufuse hardware-test [--dry-run] [--quick] [--only CHECKS] [--preset p1041] [--out DIR]` | guided acceptance run: on-screen directions, automatic grading, `report.md` + `report.json` + test sessions under `DIR/<run id>/` | 0 all passed / 2 bad args / 7 a check failed / 130 stopped with Ctrl+C |
