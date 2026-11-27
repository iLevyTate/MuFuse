from __future__ import annotations

import signal
from dataclasses import replace

import numpy as np
import pytest

from mufuse.acquisition import simulated
from mufuse.acquisition.athena import ATHENA_STREAMS
from mufuse.acquisition.simulated import CTRL_C, Rehearsal, SimulatedAthena, Wearer
from mufuse.acquisition.types import Chunk, SourceError, StreamKind
from tests.conftest import FakeClock


def _collect(src: SimulatedAthena, clock: FakeClock, seconds: float) -> dict[StreamKind, Chunk]:
    clock.advance(seconds)
    return {c.kind: c for c in src.read()}


def test_streams_match_athena_layout(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    assert dict(src.streams) == dict(ATHENA_STREAMS)
    assert src.device.driver == "simulated"


def test_read_before_start_raises(clock: FakeClock) -> None:
    with pytest.raises(SourceError):
        SimulatedAthena(clock=clock).read()


@pytest.mark.parametrize(("kind", "rate"), [("eeg", 256), ("motion", 52), ("optics", 64)])
def test_sample_counts_follow_nominal_rates(clock: FakeClock, kind: str, rate: int) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    chunk = _collect(src, clock, 2.0)[StreamKind(kind)]
    assert chunk.n_samples == 2 * rate
    assert chunk.data.shape[1] == len(ATHENA_STREAMS[StreamKind(kind)].channel_names)


def test_consecutive_reads_are_contiguous(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    first = _collect(src, clock, 0.5)[StreamKind.EEG]
    second = _collect(src, clock, 0.5)[StreamKind.EEG]
    gap = second.timestamps[0] - first.timestamps[-1]
    assert gap == pytest.approx(1 / 256)


def test_same_seed_is_deterministic(clock: FakeClock) -> None:
    a, b = SimulatedAthena(clock=clock, seed=7), SimulatedAthena(clock=FakeClock(), seed=7)
    a.start()
    b.start()
    clock.advance(1.0)
    b_clock = b._clock  # pyright: ignore[reportPrivateUsage]
    assert isinstance(b_clock, FakeClock)
    b_clock.advance(1.0)
    ea = next(c for c in a.read() if c.kind is StreamKind.EEG)
    eb = next(c for c in b.read() if c.kind is StreamKind.EEG)
    np.testing.assert_array_equal(ea.data, eb.data)


def test_eeg_has_alpha_peak(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    eeg = _collect(src, clock, 8.0)[StreamKind.EEG].data[:, 1]  # AF7
    freqs = np.fft.rfftfreq(eeg.size, 1 / 256)
    power = np.abs(np.fft.rfft(eeg - eeg.mean())) ** 2
    band = (freqs > 2) & (freqs < 40)
    assert 9.0 <= freqs[band][np.argmax(power[band])] <= 11.0


def test_dropout_window_produces_no_samples(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock, dropouts=[(1.0, 2.0)])
    src.start()
    eeg = _collect(src, clock, 3.0)[StreamKind.EEG]
    rel = eeg.timestamps - clock.now + 3.0
    assert not np.any((rel >= 1.0) & (rel < 2.0))
    assert eeg.n_samples == 2 * 256


def test_stop_is_idempotent(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    src.start()
    src.stop()
    src.stop()


# A scripted wearer ----------------------------------------------------------------------------

QUICK = Wearer(connect_s=0.0, first_data_s=0.0, scan_s=0.0, stop_s=0.0)  # no link delays
TP9, AF7, AF8, TP10 = 0, 1, 2, 3
AMBIENT = slice(4, 8)  # OPT5-8 in BrainFlow wire order
LEDS = np.r_[0:4, 8:16]


def _worn(clock: FakeClock, wearer: Wearer) -> Rehearsal:
    return Rehearsal(wearer, clock=clock, sleep=clock.advance)


def _script_time(rehearsal: Rehearsal, chunk: Chunk) -> np.ndarray:
    assert rehearsal.t0 is not None
    return chunk.timestamps - rehearsal.t0


def _eeg(clock: FakeClock, wearer: Wearer, seconds: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """The EEG of the first `seconds` and each sample's time on the wearer's timeline."""
    rehearsal = _worn(clock, wearer)
    src = rehearsal.source()
    src.start()
    eeg = _collect(src, clock, seconds)[StreamKind.EEG]
    return eeg.data, _script_time(rehearsal, eeg)


def test_a_plain_simulated_headband_is_not_a_worn_one(clock: FakeClock) -> None:
    src = SimulatedAthena(clock=clock)
    assert src.device.firmware is None
    src.start()
    chunks = _collect(src, clock, 1.0)
    assert chunks[StreamKind.EEG].data[:, :4].mean() == pytest.approx(0, abs=2)  # centred
    assert chunks[StreamKind.OPTICS].data[0, 0] == pytest.approx(20_000, abs=200)
    assert chunks[StreamKind.OPTICS].data[0, -1] == pytest.approx(100.0)


def test_a_worn_headband_reports_firmware_and_a_battery_that_reads_zero_at_first(
    clock: FakeClock,
) -> None:
    src = _worn(clock, replace(QUICK, firmware="3.1.29", battery=64.0)).source()
    assert src.device.firmware == "3.1.29"
    assert dict(src.streams) == dict(ATHENA_STREAMS)
    src.start()
    battery = _collect(src, clock, 12.0)[StreamKind.OPTICS].data[:, -1]
    assert not battery[:640].any()  # the first 10 s
    assert (battery[640:] == 64.0).all()


def test_a_worn_headband_at_rest_sits_on_a_steady_offset(clock: FakeClock) -> None:
    data, _ = _eeg(clock, QUICK)
    assert data[:, AF7].mean() == pytest.approx(-54, abs=3)  # real data is not centred
    assert 8 < data[:, TP9].std() < 20


def test_a_lifted_sensor_floats_with_a_dip_every_12_samples(clock: FakeClock) -> None:
    data, t = _eeg(clock, replace(QUICK, lifted=((2.0, 6.0, "TP10"),)))
    up = (t >= 2.0) & (t < 6.0)
    lifted = data[up, TP10]
    assert 170 < lifted.std() < 230  # what the unconnected inputs of a real Athena show
    assert set(np.diff(np.flatnonzero(lifted < -450))) == {12}
    assert np.median(lifted) == pytest.approx(110, abs=15)
    assert data[~up, TP10].std() < 20
    assert data[up, TP9].std() < 20  # only the lifted one


def test_a_clench_adds_broadband_activity_at_both_ears_only(clock: FakeClock) -> None:
    data, t = _eeg(clock, replace(QUICK, clench=((2.0, 6.0),)))
    jaw = (t >= 2.0) & (t < 6.0)
    for ear in (TP9, TP10):
        assert data[jaw, ear].std() > 4 * data[~jaw, ear].std()
    assert data[jaw, AF7].std() == pytest.approx(data[~jaw, AF7].std(), rel=0.2)


def test_blinks_show_on_the_forehead_about_once_a_second(clock: FakeClock) -> None:
    data, t = _eeg(clock, replace(QUICK, blinks=((1.0, 7.0),)))
    for forehead in (AF7, AF8):
        high = np.flatnonzero(data[:, forehead] - np.median(data[:, forehead]) > 100)
        assert np.count_nonzero(np.diff(high) > 64) + 1 == 6  # one bump a second for 6 s
        assert t[high].min() >= 1.0
        assert t[high].max() < 7.0
    assert np.ptp(data[:, TP9]) < 150


def test_the_signal_ends_at_the_amplifier_range(
    clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(simulated, "CLENCH_UV", 900.0)
    data, _ = _eeg(clock, replace(QUICK, clench=((0.0, 8.0),)))
    assert data.max() == pytest.approx(724.96)
    assert data.min() == pytest.approx(-725.04)


def test_optics_follow_the_light_on_top_of_the_ambient_pedestal(clock: FakeClock) -> None:
    script = replace(QUICK, optics=((10.0, "light"), (20.0, "covered"), (30.0, "head")))
    rehearsal = _worn(clock, script)
    src = rehearsal.source()
    src.start()
    optics = _collect(src, clock, 40.0)[StreamKind.OPTICS]
    t = _script_time(rehearsal, optics)
    head, light, covered, again = (
        np.median(optics.data[(t >= a) & (t < a + 10), :16], axis=0) for a in (0, 10, 20, 30)
    )
    assert head[AMBIENT] == pytest.approx([339_776, 335_887, 339_644, 335_806], abs=30)
    assert head[0] == pytest.approx(100_800, abs=100)  # red, lit by its own LED on the skin
    assert (light[AMBIENT] - head[AMBIENT] >= 1000).all()  # room light adds to the pedestal
    assert covered[AMBIENT] == pytest.approx(head[AMBIENT], abs=30)  # dark is dark
    assert (np.abs(covered[LEDS] - head[LEDS]) > 0.1 * head[LEDS]).all()  # no skin to light up
    assert (np.abs(light[LEDS] - head[LEDS]) > 0.1 * head[LEDS]).all()
    assert again == pytest.approx(head, rel=0.02)


def test_a_switched_off_headband_sends_nothing_and_cannot_be_found(clock: FakeClock) -> None:
    script = Wearer(off=((10.0, 25.0),), connect_s=4.0, first_data_s=0.5, scan_s=16.0, stop_s=7.3)
    rehearsal = _worn(clock, script)
    first = rehearsal.source()
    began = clock.now
    first.start()
    assert clock.now - began == pytest.approx(4.0)  # connecting takes its time
    t0 = clock.now
    assert rehearsal.t0 == t0  # the script starts when the first connection is up
    eeg = _collect(first, clock, 12.0)[StreamKind.EEG]
    assert eeg.timestamps[0] - t0 == pytest.approx(0.5)  # nothing arrives right away
    assert eeg.timestamps[-1] - t0 < 10.0
    assert not _collect(first, clock, 1.0)  # reads go empty

    first.stop()
    assert clock.now - t0 == pytest.approx(13.0)  # no link left to release

    second = rehearsal.source()
    with pytest.raises(SourceError, match="switched off"):
        second.start()
    assert clock.now - t0 == pytest.approx(13.0 + 16.0)  # a whole scan, in vain

    third = rehearsal.source()
    third.start()  # the headband is back on by now
    assert clock.now - t0 == pytest.approx(29.0 + 4.0)
    back = _collect(third, clock, 2.0)[StreamKind.EEG]
    assert back.timestamps[0] - t0 == pytest.approx(33.5)
    third.stop()
    assert clock.now - t0 == pytest.approx(35.0 + 7.3)  # the real release takes this long
    third.stop()
    assert clock.now - t0 == pytest.approx(35.0 + 7.3)


def test_a_lost_link_stays_lost_when_the_headband_is_back_on(clock: FakeClock) -> None:
    src = _worn(clock, replace(QUICK, off=((1.0, 2.0),))).source()
    src.start()
    assert _collect(src, clock, 1.0)[StreamKind.EEG].n_samples == 256
    assert not _collect(src, clock, 5.0)  # only a new connection brings the data back


def test_every_connection_of_a_rehearsal_shares_one_timeline(clock: FakeClock) -> None:
    rehearsal = _worn(clock, replace(QUICK, lifted=((3.0, 5.0, "TP9"),)))
    first = rehearsal.source()
    first.start()
    clock.advance(2.0)
    first.stop()
    second = rehearsal.source()
    second.start()  # 2 s into the script
    eeg = _collect(second, clock, 4.0)[StreamKind.EEG]
    t = _script_time(rehearsal, eeg)
    lifted = eeg.data[:, TP9] < -450
    assert lifted.any()
    assert t[lifted].min() >= 3.0
    assert t[lifted].max() < 5.0


def test_scripted_keys_arrive_once_each_when_they_are_due(clock: FakeClock) -> None:
    rehearsal = _worn(clock, replace(QUICK, keys=((2.0, " "), (-1.0, "x"), (2.0, "1"))))
    assert rehearsal.read_key() is None  # the script has not begun
    rehearsal.source().start()
    assert rehearsal.read_key() == "x"  # typed while it was still connecting
    assert rehearsal.read_key() is None
    clock.advance(2.0)
    assert rehearsal.read_key() == " "
    assert rehearsal.read_key() == "1"
    assert rehearsal.read_key() is None


def test_a_scripted_ctrl_c_arrives_as_the_signal_a_console_sends(clock: FakeClock) -> None:
    rehearsal = _worn(clock, replace(QUICK, keys=((1.0, CTRL_C),)))
    rehearsal.source().start()
    seen: list[int] = []
    previous = signal.signal(signal.SIGINT, lambda signum, frame: seen.append(signum))
    try:
        assert rehearsal.read_key() is None
        assert not seen
        clock.advance(1.0)
        assert rehearsal.read_key() is None  # not a key: a signal
    finally:
        signal.signal(signal.SIGINT, previous)
    assert seen == [signal.SIGINT]
