"""The pinned speech models (007b): fetched only when asked, checked before they are used."""

from __future__ import annotations

import hashlib
import io
import tarfile
from dataclasses import replace
from pathlib import Path

import pytest

from mufuse.voice.models import HEAR, SPEAK, VAD, ChecksumError, fetch, missing, needed


def _tar(folder: str) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:bz2") as tar:
        data = b"model"
        info = tarfile.TarInfo(f"{folder}/model.onnx")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return out.getvalue()


def _served(payload: bytes, seen: list[str]):
    def download(url: str, to: Path) -> None:
        seen.append(url)
        to.write_bytes(payload)

    return download


def test_every_model_is_pinned_to_a_sherpa_release_with_a_checksum_and_a_licence() -> None:
    for m in (VAD, SPEAK, *HEAR.values()):
        assert m.url.startswith("https://github.com/k2-fsa/sherpa-onnx/releases/download/")
        assert len(m.sha256) == 64
        assert m.licence
        assert "GPL" not in m.licence  # sherpa-onnx 2.0 or later; no espeak-ng voices
    assert [m.name for m in needed()][1] == HEAR["base"].name
    assert [m.name for m in needed(small=True)][1] == HEAR["small"].name


def test_a_file_is_downloaded_checked_and_kept(tmp_path: Path) -> None:
    payload = b"vad weights"
    model = replace(VAD, sha256=hashlib.sha256(payload).hexdigest())
    seen: list[str] = []
    path = fetch(model, tmp_path, _served(payload, seen))
    assert path.read_bytes() == payload
    assert seen == [VAD.url]
    assert fetch(model, tmp_path, _served(b"", seen)) == path  # there already: no download
    assert len(seen) == 1


def test_an_archive_is_unpacked_to_its_folder(tmp_path: Path) -> None:
    payload = _tar(SPEAK.folder or "")
    model = replace(SPEAK, sha256=hashlib.sha256(payload).hexdigest())
    path = fetch(model, tmp_path, _served(payload, []))
    assert (path / "model.onnx").read_bytes() == b"model"
    assert not list(tmp_path.glob("*.part"))


def test_a_wrong_checksum_deletes_the_download(tmp_path: Path) -> None:
    with pytest.raises(ChecksumError, match="sha256"):
        fetch(VAD, tmp_path, _served(b"not the pinned file", []))
    assert list(tmp_path.iterdir()) == []


def test_missing_names_only_what_is_not_there(tmp_path: Path) -> None:
    assert missing(tmp_path) == list(needed())
    (tmp_path / VAD.name).write_bytes(b"x")
    assert VAD not in missing(tmp_path)
