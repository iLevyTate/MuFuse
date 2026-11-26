from __future__ import annotations

import sys

import pytest

from mufuse.keys import KeyPoller


def test_poller_without_a_terminal_reports_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    # pytest's stdin is not an interactive terminal, so nothing is ever pressed.
    monkeypatch.setattr(sys, "platform", "linux")
    with KeyPoller() as keys:
        assert keys.poll() is None


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX terminals only")
def test_a_posix_terminal_gets_cbreak_and_hands_keys_over() -> None:
    assert sys.platform != "win32"  # also tells the type checker which branch this is
    import os
    import pty
    import termios

    leader, follower = pty.openpty()
    saved = sys.stdin
    sys.stdin = os.fdopen(follower, "r")
    try:
        before = termios.tcgetattr(follower)
        with KeyPoller() as keys:
            assert termios.tcgetattr(follower)[3] & termios.ICANON == 0  # no Enter needed
            os.write(leader, b" ")
            assert keys.poll() == " "
            assert keys.poll() is None
        assert termios.tcgetattr(follower) == before  # the terminal is put back
    finally:
        sys.stdin.close()
        sys.stdin = saved
        os.close(leader)
