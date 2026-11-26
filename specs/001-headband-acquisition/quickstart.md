# Quickstart: 001 Acquisition

```bash
uv sync
uv run mufuse stream --source sim            # no hardware
uv run mufuse devices                        # headband on, official Muse app closed
uv run mufuse record --notes "first test" --duration 120   # space = moment marker, 1-9 = block markers, q = stop
uv run mufuse inspect recordings/<session_id>
uv run pytest -m "not hardware"              # CI suite
uv run pytest -m hardware -s                 # quick automatic checks, headband on
uv run mufuse hardware-test --dry-run --quick  # preview the guided acceptance test
uv run mufuse hardware-test                    # guided acceptance test (tests/hardware/README.md)
```
