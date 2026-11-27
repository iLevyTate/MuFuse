from __future__ import annotations

from mufuse.acquisition.loss import skipped_subpackets


def test_no_loss_when_the_counter_steps_by_one() -> None:
    assert skipped_subpackets([5, 6, 7, 8]) == 0
    assert skipped_subpackets([]) == 0
    assert skipped_subpackets([42]) == 0


def test_samples_of_one_subpacket_share_a_counter() -> None:
    assert skipped_subpackets([5, 5, 6, 6, 7, 7]) == 0  # EEG: two samples per subpacket
    assert skipped_subpackets([5, 5, 5, 6, 6, 6]) == 0  # motion: three


def test_counts_each_skipped_subpacket() -> None:
    assert skipped_subpackets([5, 5, 7, 7]) == 1
    assert skipped_subpackets([10, 14, 15, 18]) == 5


def test_the_counter_wraps_at_256() -> None:
    assert skipped_subpackets([254, 255, 0, 1]) == 0
    assert skipped_subpackets([254, 1]) == 2  # 255 and 0 never arrived


def test_previous_carries_the_count_over_from_the_read_before() -> None:
    assert skipped_subpackets([7, 8], previous=6) == 0
    assert skipped_subpackets([7, 8], previous=7) == 0  # second sample of the same subpacket
    assert skipped_subpackets([9], previous=6) == 2
    assert skipped_subpackets([9], previous=None) == 0  # a new connection has nothing to compare
