"""Modified Beer-Lambert law (004 decision 2): constants, one log base, round trip."""

from __future__ import annotations

import numpy as np
import pytest

from mufuse.fnirs.mbll import (
    DETECTORS,
    DISTANCE_CM,
    EPSILON,
    concentrations,
    dpf,
    intensities,
    optical_density,
    rows_of,
)


def test_dpf_follows_scholkmann_and_wolf_at_age_30() -> None:
    assert dpf(730.0) == pytest.approx(6.31, abs=0.01)
    assert dpf(850.0) == pytest.approx(5.23, abs=0.01)
    assert dpf(850.0, age=60.0) > dpf(850.0, age=30.0)


def test_prahl_coefficients_are_the_base_10_values() -> None:
    assert EPSILON[730.0] == (390.0, 1102.2)
    assert EPSILON[850.0] == (1058.0, 691.32)


def test_rows_are_wire_order_groups_of_li_ri_lo_ro() -> None:
    assert DETECTORS == ("LI", "RI", "LO", "RO")
    assert rows_of("LI") == (8, 12)  # OPT9 (730 nm), OPT13 (850 nm), 0-based
    assert rows_of("RO") == (11, 15)
    assert DISTANCE_CM == {"LI": 1.0, "RI": 1.0, "LO": 3.0, "RO": 3.0}


def test_optical_density_is_base_10() -> None:
    assert optical_density(np.array([10.0, 1.0]), 10.0) == pytest.approx([0.0, 1.0])


@pytest.mark.parametrize("distance", [1.0, 3.0])
def test_concentrations_survive_the_round_trip(distance: float) -> None:
    hbo = np.array([0.0, 0.5, 1.0, -0.4])
    hbr = np.array([0.0, -0.15, -0.3, 0.2])
    i730, i850 = intensities(hbo, hbr, 60_000.0, 25_000.0, distance)
    back_hbo, back_hbr = concentrations(
        optical_density(i730, 60_000.0), optical_density(i850, 25_000.0), distance
    )
    assert back_hbo == pytest.approx(hbo, abs=1e-9)
    assert back_hbr == pytest.approx(hbr, abs=1e-9)


def test_natural_log_od_would_read_ln10_times_too_high() -> None:
    """The OpenMuse unit bug: -ln(I/I0) with base-10 epsilon inflates by ln 10."""
    i730, i850 = intensities(np.array([1.0]), np.array([-0.3]), 60_000.0, 25_000.0, 3.0)
    right, _ = concentrations(optical_density(i730, 60_000.0), optical_density(i850, 25_000.0), 3.0)
    wrong, _ = concentrations(-np.log(i730 / 60_000.0), -np.log(i850 / 25_000.0), 3.0)
    assert right[0] == pytest.approx(1.0)
    assert wrong[0] == pytest.approx(np.log(10.0))


def test_one_micromolar_at_3_cm_moves_850_nm_by_the_expected_od() -> None:
    i730, i850 = intensities(np.array([1.0]), np.array([0.0]), 1.0, 1.0, 3.0)
    assert optical_density(i850, 1.0)[0] == pytest.approx(1058e-6 * 3.0 * dpf(850.0))
    assert optical_density(i730, 1.0)[0] == pytest.approx(390e-6 * 3.0 * dpf(730.0))
