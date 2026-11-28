"""The modified Beer-Lambert law for the Athena's forehead optics (004 decision 2). EXPERIMENTAL.

ΔOD(λ) = -log10(I / I0) = (ε_HbO(λ)·ΔHbO + ε_HbR(λ)·ΔHbR) · d · DPF(λ)

One log base throughout: base 10, matching Prahl's extinction coefficients. The distances are
estimates from the FCC photos, so every concentration is relative: a wrong distance or DPF scales
all of them alike.
"""

from __future__ import annotations

import numpy as np

from mufuse.acquisition.types import FloatArray

FNIRS_VERSION = "1"
EXPERIMENTAL = "EXPERIMENTAL"
WAVELENGTHS = (730.0, 850.0)
# Prahl, OMLC hemoglobin table, cm^-1 M^-1, base 10: (HbO, HbR)
EPSILON: dict[float, tuple[float, float]] = {730.0: (390.0, 1102.2), 850.0: (1058.0, 691.32)}
AGE = 30.0
DETECTORS = ("LI", "RI", "LO", "RO")  # the order of each group of four OPT rows (optics.py)
OUTER = ("LO", "RO")
DISTANCE_CM = {"LI": 1.0, "RI": 1.0, "LO": 3.0, "RO": 3.0}  # estimates, from the FCC photos
_ROW_730, _ROW_850 = 8, 12  # OPT9 and OPT13, 0-based: the first row of each wavelength's group
UM = 1e6  # M -> µM


def dpf(wavelength: float, age: float = AGE) -> float:
    """Differential pathlength factor (Scholkmann & Wolf 2013, from ~3 cm frontal data)."""
    lam = wavelength
    return 223.3 + 0.05624 * age**0.8493 - 5.723e-7 * lam**3 + 0.001245 * lam**2 - 0.9025 * lam


def rows_of(detector: str) -> tuple[int, int]:
    """The detector's 730 nm and 850 nm OPT rows, 0-based."""
    k = DETECTORS.index(detector)
    return _ROW_730 + k, _ROW_850 + k


def optical_density(intensity: FloatArray, i0: float) -> FloatArray:
    return -np.log10(np.asarray(intensity, dtype=np.float64) / i0)


def _matrix(distance_cm: float, age: float) -> FloatArray:
    """ΔOD (730, 850) = M · (ΔHbO, ΔHbR) in mol/L."""
    return np.array(
        [[e * distance_cm * dpf(lam, age) for e in EPSILON[lam]] for lam in WAVELENGTHS]
    )


def concentrations(
    od730: FloatArray, od850: FloatArray, distance_cm: float, age: float = AGE
) -> tuple[FloatArray, FloatArray]:
    """ΔHbO and ΔHbR in µM from the two ΔODs of one detector."""
    inverse = np.linalg.inv(_matrix(distance_cm, age))
    od = np.vstack([np.asarray(od730, dtype=np.float64), np.asarray(od850, dtype=np.float64)])
    hbo, hbr = (inverse @ od) * UM
    return hbo, hbr


def intensities(
    hbo_um: FloatArray,
    hbr_um: FloatArray,
    i0_730: float,
    i0_850: float,
    distance_cm: float,
    age: float = AGE,
) -> tuple[FloatArray, FloatArray]:
    """The forward model: the 730 and 850 nm intensities that the given changes would give."""
    c = np.vstack([np.asarray(hbo_um, dtype=np.float64), np.asarray(hbr_um, dtype=np.float64)])
    od730, od850 = _matrix(distance_cm, age) @ (c / UM)
    return i0_730 * 10.0 ** (-od730), i0_850 * 10.0 ** (-od850)
