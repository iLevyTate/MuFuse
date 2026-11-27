"""Head movement in a stretch, from the accelerometer and the gyroscope (rules section 6)."""

from __future__ import annotations

import numpy as np

from mufuse.acquisition.types import FloatArray
from mufuse.quality.answer import Movement
from mufuse.quality.rules import RULES, Rules

_ACC, _GYRO = slice(0, 3), slice(3, 6)  # MOTION columns: ACC_X/Y/Z in g, GYRO_X/Y/Z in deg/s


def movement(motion: FloatArray, rules: Rules = RULES) -> Movement:
    """`motion` holds the MOTION samples of one stretch, (n, 6)."""
    if motion.shape[0] < rules.motion_min_n:
        return "unknown"
    gyro_dps = float(np.sqrt(np.mean(np.sum(motion[:, _GYRO] ** 2, axis=1))))
    acc_std_g = float(np.max(np.std(motion[:, _ACC], axis=0)))
    return "moving" if gyro_dps > rules.gyro_dps or acc_std_g > rules.acc_std_g else "still"
