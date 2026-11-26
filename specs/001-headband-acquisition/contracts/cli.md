# Contract: CLI

| Command | Behavior | Exit codes |
|---|---|---|
| `mufuse devices [--timeout 8]` | BLE scan, list Muse devices (name, address, RSSI), mark saved device | 0 found / 3 none |
| `mufuse stream [--source athena\|sim\|play PATH] [--device NAME] [--preset p1041]` | live view until `q`/Ctrl+C | 0 / 2 bad args / 4 connect fail |
| `mufuse record [same opts] [--notes TEXT] [--out DIR] [--duration SEC]` | live view + recording + key markers | 0 / 2 / 4 / 5 write error |
| `mufuse inspect PATH` | print manifest summary, per-stream rows/rate/completeness, markers, gaps | 0 / 6 unreadable |
