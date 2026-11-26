from __future__ import annotations

import io

from rich.console import Console

from mufuse.banner import _TRACE, HEIGHT_LINES, MAX_WIDTH, MU_COLUMN, print_banner, render_banner


def _console(*, terminal: bool) -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, force_terminal=terminal, width=MAX_WIDTH, color_system=None), buf


def test_trace_is_rectangular_plain_ascii() -> None:
    assert {len(row) for row in _TRACE} == {len(_TRACE[0])}
    assert set("".join(_TRACE)) <= set(" _/\\|")


def test_colour_changes_at_the_mu_left_stem() -> None:
    assert 0 < MU_COLUMN < len(_TRACE[0])
    assert all(row[MU_COLUMN] == "|" for row in _TRACE[1:])
    assert all(row[MU_COLUMN] == " " for row in _TRACE[:1])


def test_banner_is_ascii_so_any_terminal_font_renders_it() -> None:
    width = len(_TRACE[0])
    assert all(line[:width].isascii() for line in render_banner().plain.split("\n"))


def test_banner_fits_an_80_column_terminal_in_under_8_lines() -> None:
    console, buf = _console(terminal=True)
    status = "MuseS-C27F · preset p1041 · " + "x" * 200
    assert print_banner(console, status)
    lines = buf.getvalue().rstrip("\n").split("\n")
    assert len(lines) == HEIGHT_LINES < 8
    assert max(len(line) for line in lines) <= MAX_WIDTH
    assert "MuFuse v" in buf.getvalue()
    assert "Punk EEG." in buf.getvalue()
    assert "MuseS-C27F" in buf.getvalue()


def test_banner_colours_impulse_orange_and_mu_white() -> None:
    text = render_banner()
    styles = {str(span.style) for span in text.spans}
    assert {"#F97316", "#FFFFFF"} <= styles


def test_banner_is_suppressed_when_output_is_not_a_terminal() -> None:
    console, buf = _console(terminal=False)
    assert not print_banner(console, "anything")
    assert buf.getvalue() == ""
