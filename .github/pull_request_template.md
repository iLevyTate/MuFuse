## Summary
<!-- What changed and why. Link the spec: specs/NNN-name/ -->

## Constitution check
- [ ] No raw or inferred neural data leaves the device (I)
- [ ] User-facing text describes signals, never labels the person (II)
- [ ] Signal-processing changes are versioned and regression-tested (IV)

## Test plan
- [ ] `uv run ruff format --check && uv run ruff check && uv run pyright`
- [ ] `uv run pytest -m "not hardware"`
- [ ] Hardware checks (if acquisition/signal code changed): `uv run pytest -m hardware -s`
