"""Loss on the headset link, counted from the Athena's per-sensor subpacket counter.

BrainFlow's package number is `(packet index << 8) | subpacket counter`; only the low byte is a
clean counter. It goes up by one per subpacket of a sensor and wraps at 256.
"""

from __future__ import annotations

from collections.abc import Iterable


def skipped_subpackets(counters: Iterable[int], previous: int | None = None) -> int:
    """How many subpackets are missing from a run of subpacket counters (0-255).

    Every sample of one subpacket carries the same counter, so equal neighbours are one
    subpacket. `previous` is the last counter of the read before, None on a new connection.
    A hole of 255 subpackets or more cannot be told from a shorter one; holes that long are
    stalls, which the supervisor records as gaps.
    """
    lost = 0
    for counter in counters:
        if previous is not None and counter != previous:
            lost += (counter - previous - 1) % 256
        previous = counter
    return lost
