from __future__ import annotations

from mufuse.calibration import suggestions, tables

CHANNELS = ("TP9", "AF7", "AF8", "TP10")


def phase_numbers(
    name: str, spread: tuple[float, float, float], **other: float
) -> dict[str, float]:
    """One phase's saved numbers, the same on all four channels: spread p05, median, p95."""
    numbers = {
        "spread_p05_uv": spread[0],
        "spread_uv": spread[1],
        "spread_p95_uv": spread[2],
        "std_uv": spread[1],
        "ptp_uv": 4 * spread[1],
        "rail_share": 0.0,
        "mains_50hz_share": 0.02,
        "mains_60hz_share": 0.0,
        "ok_share": 1.0,
        "noisy_share": 0.0,
        "flat_share": 0.0,
        "railed_share": 0.0,
    } | other
    return {f"{name}.{ch}.{key}": value for ch in CHANNELS for key, value in numbers.items()}


def h8_numbers(
    rest: tuple[float, float, float] = (10.0, 15.0, 20.0),
    clench: tuple[float, float, float] = (80.0, 90.0, 120.0),
) -> dict[str, float]:
    return (
        phase_numbers("rest", rest)
        | phase_numbers("lift", (30.0, 39.0, 50.0), std_uv=215.0, rail_share=0.3)
        | phase_numbers("clench", clench, ok_share=0.0, noisy_share=1.0)
        | phase_numbers("blink", (15.0, 25.0, 35.0))
    )


def _noisy(lines: list[str]) -> str:
    (line,) = [text for text in lines if text.startswith("Noisy")]
    return line


def test_the_noisy_suggestion_is_the_geometric_midpoint_between_rest_and_clench() -> None:
    h8 = h8_numbers() | {"rest.AF7.spread_p95_uv": 20.0, "clench.TP10.spread_p05_uv": 80.0}

    line = _noisy(suggestions({"H8": h8}))

    assert "about 40 µV" in line  # sqrt(20 * 80)
    assert "20 µV" in line
    assert "80 µV" in line
    assert "now 75 µV" in line
    assert "inside that gap" in line


def test_the_noisiest_rest_channel_and_the_weaker_ear_set_the_gap() -> None:
    h8 = h8_numbers() | {"rest.AF8.spread_p95_uv": 32.0, "clench.TP9.spread_p05_uv": 50.0}

    line = _noisy(suggestions({"H8": h8}))

    assert "32 µV (AF8)" in line
    assert "50 µV (TP9)" in line
    assert "about 40 µV" in line
    assert "a clench this weak would still read ok" in line  # 75 µV is above 50 µV


def test_overlapping_rest_and_clench_are_called_not_separable() -> None:
    line = _noisy(
        suggestions({"H8": h8_numbers(rest=(20.0, 40.0, 60.0), clench=(50.0, 70.0, 90.0))})
    )

    assert line.startswith("Noisy threshold (NOISY_UV, now 75 µV): not separable")
    assert "about" not in line


def test_blinks_above_the_suggestion_are_pointed_out() -> None:
    h8 = h8_numbers() | {"blink.AF7.spread_p95_uv": 55.0}

    lines = suggestions({"H8": h8})

    assert "a blink would read noisy" in _noisy(lines)
    assert "a blink would read noisy" not in _noisy(suggestions({"H8": h8_numbers()}))


def test_a_still_phase_noisier_than_the_suggestion_is_pointed_out() -> None:
    lines = suggestions({"H8": h8_numbers(), "P0": phase_numbers("still", (20.0, 40.0, 60.0))})

    assert "P0" in _noisy(lines)
    assert "60 µV" in _noisy(lines)
    assert "P0" not in _noisy(
        suggestions({"H8": h8_numbers(), "P0": phase_numbers("still", (9.0, 14.0, 19.0))})
    )


def test_the_rail_note_gives_the_threshold_at_full_scale() -> None:
    (line,) = [t for t in suggestions({"H8": h8_numbers()}) if t.startswith("Rail")]

    assert "now 710 µV, within 2% of the ±725 µV full scale" in line
    assert "it was 1000 µV, which cannot be reached" in line
    assert "about 690 µV" in line
    assert "30% of the lifted TP9 samples" in line


def test_a_lift_the_channel_check_did_not_see_is_pointed_out() -> None:
    (line,) = [t for t in suggestions({"H8": h8_numbers()}) if t.startswith("Lifted")]

    assert "ok in 100%" in line
    assert "215 µV" in line  # the plain std did see it
    assert "15 µV" in line


def test_nothing_is_suggested_without_the_numbers_ofh8_numbers() -> None:
    (line,) = suggestions({"P0": phase_numbers("still", (9.0, 14.0, 19.0))})

    assert "H8" in line
    assert "nothing to suggest" in line


def test_a_partly_saved_h8_gives_the_suggestions_it_has_numbers_for() -> None:
    h8 = {k: v for k, v in h8_numbers().items() if not k.startswith("clench.")}

    lines = suggestions({"H8": h8})

    assert not [t for t in lines if t.startswith("Noisy")]
    assert [t for t in lines if t.startswith("Rail")]


def test_the_eeg_tables_have_a_row_for_each_phase_that_saved_numbers() -> None:
    made = tables(
        {"H8": h8_numbers(), "P0": phase_numbers("still", (9.0, 14.0, 19.0)), "H5": {"gaps": 1.0}}
    )

    spread = made[0]
    assert "spread" in spread.title
    assert spread.header == ("Phase", *CHANNELS)
    assert [row[0] for row in spread.rows] == [
        "P0 sitting still",
        "H8 at rest",
        "H8 left ear sensor lifted",
        "H8 jaw clenched",
        "H8 blinking",
    ]
    assert spread.rows[0][1:] == ("9 / 14 / 19",) * 4
    labels = made[1]
    assert labels.rows[3][1] == "0 / 100 / 0 / 0"  # clenched: every window read noisy
    assert len(made) == 4
    assert all(table.header[0] == "Phase" and len(table.rows) == 5 for table in made)


def test_a_phase_with_a_number_missing_shows_a_dash_there() -> None:
    h4 = phase_numbers("whole", (9.0, 14.0, 19.0))
    del h4["whole.AF7.spread_p05_uv"]

    (row,) = tables({"H4": h4})[0].rows

    assert row == ("H4 whole recording (worn or on the desk)", "9 / 14 / 19", "-", *row[3:])


def test_the_optics_table_lists_all_16_rows_with_their_role_and_what_light_adds() -> None:
    f1: dict[str, float] = {}
    for n in range(1, 17):
        ambient = 5 <= n <= 8
        f1[f"on_head.OPT{n}.median"] = 338000.0 if ambient else 100000.0
        f1[f"room_light.OPT{n}.median"] = 341200.0 if ambient else 300.0
        f1[f"dark.OPT{n}.median"] = 338000.0 if ambient else 60000.0
        f1[f"light_again.OPT{n}.median"] = 341000.0 if ambient else 310.0
        f1[f"on_head.OPT{n}.pulse_share"] = 0.01 if ambient else 0.4

    (optics,) = tables({"F1": f1})

    assert [row[0] for row in optics.rows] == [f"OPT{n}" for n in range(1, 17)]
    assert [row[1] for row in optics.rows][3:5] == ["red", "ambient"]
    assert [row[1] for row in optics.rows][8::4] == ["730 nm", "850 nm"]
    # the smaller of the two room-light phases over covered, as the judge takes it
    assert optics.rows[4] == (
        "OPT5", "ambient", "338000", "341200", "338000", "341000", "+3000", "1%"
    )  # fmt: skip
    assert optics.rows[0][6] == "-59700"
    # the same level in the units OpenMuse and Mind Monitor show: 338000 / 32768
    assert "÷ 32768" in optics.note
    assert "about 338000 counts here, reads about 10.3 there" in optics.note
    assert "Pulse share: the part of a row's 0.1 to 10 Hz power between 0.7 and 3 Hz" in optics.note


def test_a_rest_louder_than_the_threshold_in_force_is_pointed_out() -> None:
    h8 = h8_numbers(rest=(40.0, 60.0, 90.0), clench=(300.0, 350.0, 400.0))

    assert "windows at rest would read noisy" in _noisy(suggestions({"H8": h8}))


def test_the_flat_note_says_whether_rest_came_near_the_threshold() -> None:
    (clear,) = [t for t in suggestions({"H8": h8_numbers()}) if t.startswith("Flat")]
    assert "now 1 µV" in clear
    assert "10 µV (TP9), clear of it" in clear

    dead = h8_numbers() | {"rest.AF8.spread_p05_uv": 0.4}
    (flat,) = [t for t in suggestions({"H8": dead}) if t.startswith("Flat")]
    assert "0.4 µV (AF8): rest windows on that channel read flat" in flat


def test_a_lift_the_channel_check_saw_is_reported_as_seen() -> None:
    h8 = h8_numbers() | {"lift.TP9.ok_share": 0.1, "lift.TP9.flat_share": 0.9}

    (line,) = [t for t in suggestions({"H8": h8}) if t.startswith("Lifted")]

    assert "ok in 10% of windows (noisy 0%, flat 90%, railed 0%)" in line
    assert "needs a measure other" not in line


def test_no_numbers_no_tables() -> None:
    assert tables({}) == []
    assert tables({"H6": {"presses": 3.0}}) == []
