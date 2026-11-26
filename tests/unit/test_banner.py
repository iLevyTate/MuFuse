from __future__ import annotations

import io

from rich.console import Console

from mufuse.banner import _PIXELS, HEIGHT_LINES, MAX_WIDTH, MU_COLUMN, print_banner, render_banner


def _console(*, terminal: bool) -> tuple[Console, io.StringIO]:
    buf = io.StringIO()
    return Console(file=buf, force_terminal=terminal, width=MAX_WIDTH, color_system=None), buf


def test_pixel_art_is_rectangular_with_even_rows() -> None:
    assert len(_PIXELS) % 2 == 0
    assert {len(row) for row in _PIXELS} == {len(_PIXELS[0])}
    assert set("".join(_PIXELS)) <= {".", "#"}
    assert 0 < MU_COLUMN < len(_PIXELS[0])


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


def test_banner_colours_impulse_amber_and_mu_paper() -> None:
    text = render_banner()
    styles = {str(span.style) for span in text.spans}
    assert {"#F59E0B", "#F3F1EC"} <= styles


def test_banner_is_suppressed_when_output_is_not_a_terminal() -> None:
    console, buf = _console(terminal=False)
    assert not print_banner(console, "anything")
    assert buf.getvalue() == ""
