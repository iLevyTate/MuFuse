"""CLI header: the Concept 7J-3 impulse-to-mu trace as half-block pixel art (docs/BRAND.md)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from rich.console import Console
from rich.text import Text

PHOSPHOR_AMBER = "#F59E0B"
BENCH_PAPER = "#F3F1EC"

# One character per column, two pixel rows per terminal line. Columns before MU_COLUMN are the
# amber impulse; from MU_COLUMN on, the mu and its resting baseline.
_PIXELS = (
    "...........#............................",
    "..........#.#...........................",
    "..........#.#...........................",
    "..........#.#.........##....##..........",
    ".........#...#........##....##..........",
    ".....#...#...#........##....##..........",
    "....#.#..#...#........##....##..........",
    "####...##.....#...######################",
    "..............#..#....##................",
    "..............#..#....##................",
    "...............##.....##................",
    "......................##................",
)
MU_COLUMN = 22
HEIGHT_LINES = len(_PIXELS) // 2
MAX_WIDTH = 80
_GAP = "   "
_HALF = {(True, True): "█", (True, False): "▀", (False, True): "▄", (False, False): " "}


def _version() -> str:
    try:
        return version("mufuse")
    except PackageNotFoundError:
        return "dev"


def render_banner(status: str = "") -> Text:
    """The mark on the left; name, version, tagline and `status` beside it."""
    info = [f"MuFuse v{_version()}", "Punk EEG.", "", status]
    out = Text()
    for line in range(HEIGHT_LINES):
        top, bottom = _PIXELS[2 * line], _PIXELS[2 * line + 1]
        for col, (a, b) in enumerate(zip(top, bottom, strict=True)):
            glyph = _HALF[(a == "#", b == "#")]
            out.append(glyph, style=PHOSPHOR_AMBER if col < MU_COLUMN else BENCH_PAPER)
        label = info[line - 1] if 0 < line <= len(info) else ""
        if label:
            room = MAX_WIDTH - len(top) - len(_GAP)
            label = label if len(label) <= room else label[: room - 1] + "…"
            out.append(_GAP)
            out.append(label, style="bold" if line == 1 else ("dim" if line == 2 else ""))
        out.append("\n")
    out.rstrip()
    return out


def print_banner(console: Console, status: str = "") -> bool:
    """Print the header for people, not pipes: skipped unless output is an interactive terminal.

    Returns whether it was printed.
    """
    if not console.is_terminal:
        return False
    console.print(render_banner(status))
    return True
