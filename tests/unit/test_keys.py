from __future__ import annotations

from mufuse.keys import KeyPoller


def test_poller_without_a_terminal_reports_no_keys() -> None:
    # pytest's stdin is not an interactive terminal, so nothing is ever pressed.
    with KeyPoller() as keys:
        assert keys.poll() is None
