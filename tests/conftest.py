from __future__ import annotations

import pytest

from mufuse.hwtest.checks import Timings


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


# The guided hardware test runs real threads against the simulated headband, so CI shrinks every
# duration instead of faking the clock. Pass thresholds stay the real ones.
FAST_TIMINGS = Timings(
    scan_s=0.0,
    info_timeout_s=0.1,
    settle_s=0.05,
    stream_s=0.5,
    connect_attempts=2,
    connect_pause_s=0.0,
    connect_timeout_s=2.0,
    countdown_s=0,
    rest_s=0.6,
    blink_s=0.6,
    clench_s=0.6,
    lift_s=0.6,
    contact_window_s=0.25,
    recover_s=0.05,
    record_s=1.0,
    marker_at_s=(0.2, 0.45, 0.7),
    marker_wait_s=2.0,
    progress_every_s=0.5,
    power_lead_s=0.3,
    power_off_s=0.4,
    power_detect_s=2.0,
    resume_wait_s=3.0,
    power_tail_s=0.3,
    interrupt_lead_s=0.2,
    interrupt_wait_s=0.5,
    drain_s=0.1,
    poll_s=0.01,
    pause_threshold_s=0.15,
    stall_after_s=0.2,
    backoff_s=(0.05,),
)
