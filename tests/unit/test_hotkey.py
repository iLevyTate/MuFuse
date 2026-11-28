"""The global hotkey (005c): what the person writes, and what serve does with a press."""

from __future__ import annotations

import sys

import pytest

from mufuse.companion.hotkey import DEFAULT, Hotkey, parse


def test_the_default_is_ctrl_alt_m() -> None:
    combo = parse(DEFAULT)
    assert combo.text == "ctrl+alt+m"
    assert combo.modifiers == 0x0002 | 0x0001
    assert combo.key == ord("M")


@pytest.mark.parametrize(
    ("spec", "text", "key"),
    [
        ("Alt + Ctrl + M", "ctrl+alt+m", ord("M")),
        ("ctrl+shift+f9", "ctrl+shift+f9", 0x78),
        ("win+space", "win+space", 0x20),
        ("ctrl+alt+7", "ctrl+alt+7", ord("7")),
    ],
)
def test_combinations_are_read_in_any_order_and_case(spec: str, text: str, key: int) -> None:
    combo = parse(spec)
    assert (combo.text, combo.key) == (text, key)


@pytest.mark.parametrize("spec", ["m", "ctrl+alt", "ctrl+m+n", "ctrl+ctrl+m", "ctrl+é", "ctrl+tab"])
def test_a_combination_without_a_modifier_or_one_key_is_refused(spec: str) -> None:
    with pytest.raises(ValueError, match="--hotkey"):
        parse(spec)


@pytest.mark.skipif(sys.platform == "win32", reason="the other systems' answer")
def test_elsewhere_it_says_windows_only_and_serve_goes_on() -> None:
    hotkey = Hotkey(parse(DEFAULT), lambda: None)
    assert hotkey.start() == "the global hotkey works on Windows only for now"
    hotkey.stop()  # nothing to stop: no error


@pytest.mark.skipif(sys.platform != "win32", reason="RegisterHotKey is Windows only")
def test_on_windows_it_registers_and_stops_cleanly() -> None:
    hotkey = Hotkey(parse("ctrl+alt+shift+f12"), lambda: None)
    why = hotkey.start()
    if why is not None:  # a runner without a desktop, or the combination is taken
        pytest.skip(why)
    hotkey.stop()
    again = Hotkey(parse("ctrl+alt+shift+f12"), lambda: None)
    assert again.start() is None  # released on stop, so it can be taken again
    again.stop()
