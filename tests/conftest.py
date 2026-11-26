from __future__ import annotations

import pytest


class FakeClock:
    """Manually advanced clock so time-dependent code is deterministic in tests."""

    def __init__(self, start: float = 1_700_000_000.0) -> None:
        self._start = start
        self._offset = 0.0  # kept separately so repeated small steps don't compound rounding

    @property
    def now(self) -> float:
        return self._start + self._offset

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self._offset += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
