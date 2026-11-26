import numpy as np
import pytest
from brainflow.board_shim import BoardShim, BrainFlowPresets

from mufuse.acquisition.athena import (
    ATHENA_BOARD_ID,
    ATHENA_PRESETS,
    ATHENA_STREAMS,
    DEFAULT_PRESET,
    preset_code,
    preset_from_code,
    preset_warning,
    validate_preset,
)
from mufuse.acquisition.types import Chunk, StreamKind


def test_chunk_accepts_matching_shapes() -> None:
    chunk = Chunk(StreamKind.EEG, np.array([1.0, 2.0]), np.zeros((2, 8)))
    assert chunk.n_samples == 2


def test_chunk_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="timestamps"):
        Chunk(StreamKind.EEG, np.array([1.0]), np.zeros((2, 8)))


def test_chunk_rejects_non_increasing_timestamps() -> None:
    with pytest.raises(ValueError, match="increasing"):
        Chunk(StreamKind.EEG, np.array([2.0, 1.0]), np.zeros((2, 8)))


def test_empty_chunk_is_valid() -> None:
    assert Chunk(StreamKind.MOTION, np.empty(0), np.empty((0, 6))).n_samples == 0


_PRESET_FOR = {
    StreamKind.EEG: BrainFlowPresets.DEFAULT_PRESET,
    StreamKind.MOTION: BrainFlowPresets.AUXILIARY_PRESET,
    StreamKind.OPTICS: BrainFlowPresets.ANCILLARY_PRESET,
}


@pytest.mark.parametrize("kind", list(StreamKind))
def test_layout_matches_installed_brainflow(kind: StreamKind) -> None:
    """Our hard-coded layout must track the driver; this fails loudly if BrainFlow changes."""
    descr = BoardShim.get_board_descr(ATHENA_BOARD_ID, _PRESET_FOR[kind])
    spec = ATHENA_STREAMS[kind]
    assert spec.sampling_rate == descr["sampling_rate"]
    data_rows = [r for r in range(descr["num_rows"]) if r not in _non_data_rows(descr)]
    assert len(spec.channel_names) == len(data_rows)


def _non_data_rows(descr: dict[str, object]) -> set[int]:
    keys = ("package_num_channel", "timestamp_channel", "marker_channel")
    return {int(descr[k]) for k in keys if k in descr}  # type: ignore[arg-type]


def test_eeg_channel_names_start_with_muse_sites() -> None:
    assert ATHENA_STREAMS[StreamKind.EEG].channel_names[:4] == ("TP9", "AF7", "AF8", "TP10")


def test_validate_preset() -> None:
    assert DEFAULT_PRESET in ATHENA_PRESETS
    assert validate_preset("p1035") == "p1035"
    with pytest.raises(ValueError, match="p1041"):
        validate_preset("p9999")


@pytest.mark.parametrize("preset", ["p20", "p21", "p50", "p51", "p60", "p61"])
def test_presets_without_optics_on_the_athena_are_refused(preset: str) -> None:
    assert preset not in ATHENA_PRESETS
    with pytest.raises(ValueError, match="no optics"):
        validate_preset(preset)


def test_preset_names_are_hex_codes() -> None:
    assert preset_code("p1041") == 0x1041 == 4161
    assert preset_code("p1021") == 4129
    assert preset_code("pzz") is None
    assert preset_from_code(4161) == "p1041"


def test_a_preset_the_headset_did_not_take_is_named() -> None:
    warning = preset_warning("p1041", "p1021")
    assert warning is not None
    assert "p1021" in warning
    assert "p1041" in warning
    assert preset_warning("p1041", "p1041") is None
    assert preset_warning("p1041", None) is None
