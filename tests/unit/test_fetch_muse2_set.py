"""scripts/fetch_muse2_set.py, without the network (FR-022, research R12)."""

from __future__ import annotations

import hashlib
import importlib.util
import urllib.error
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[2]


def _fetch() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "fetch_muse2_set", REPO / "scripts" / "fetch_muse2_set.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _zip(folder: Path, entries: dict[str, bytes]) -> Path:
    archive = folder / "sourcedata.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return archive


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def test_a_file_with_the_wrong_checksum_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fetch = _fetch()
    archive = _zip(tmp_path, {"sourcedata/sub-01/eeg.csv": b"1,2,3\n"})
    assert fetch.main(["--from", str(archive), "--dest", str(tmp_path / "set")]) == 1
    assert "checksum" in capsys.readouterr().out
    assert not (tmp_path / "set" / "sourcedata").exists()


def test_the_right_file_is_unpacked_and_its_folder_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _fetch()
    archive = _zip(tmp_path, {"sourcedata/sub-01/eeg.csv": b"1,2,3\n"})
    monkeypatch.setattr(fetch, "EXPECTED_MD5", _md5(archive))
    dest = tmp_path / "set"
    assert fetch.main(["--from", str(archive), "--dest", str(dest)]) == 0
    assert (dest / "sourcedata" / "sub-01" / "eeg.csv").read_bytes() == b"1,2,3\n"
    assert str(dest) in capsys.readouterr().out


def test_an_entry_that_would_leave_the_destination_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _fetch()
    archive = _zip(tmp_path, {"sourcedata/ok.csv": b"1\n", "../escaped.txt": b"no\n"})
    monkeypatch.setattr(fetch, "EXPECTED_MD5", _md5(archive))
    dest = tmp_path / "set"
    assert fetch.main(["--from", str(archive), "--dest", str(dest)]) == 1
    assert not (tmp_path / "escaped.txt").exists()


def test_a_refused_download_exits_1_and_says_how_to_get_it_by_hand(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    fetch = _fetch()

    def refused(url: str, target: Path) -> None:
        raise urllib.error.HTTPError(url, 403, "Forbidden", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(fetch, "download", refused)
    assert fetch.main(["--dest", str(tmp_path / "set")]) == 1
    out = capsys.readouterr().out
    assert "https://doi.org/10.6084/m9.figshare.30162868.v1" in out
    assert "--from" in out


def test_the_set_never_lands_in_the_repository(tmp_path: Path) -> None:
    fetch = _fetch()
    archive = _zip(tmp_path, {"sourcedata/ok.csv": b"1\n"})
    assert fetch.main(["--from", str(archive), "--dest", str(REPO / "muse2-set")]) == 1
    assert not (REPO / "muse2-set").exists()


def test_by_default_the_set_goes_to_the_user_cache_outside_the_repository() -> None:
    dest = _fetch().default_dest()
    assert not dest.resolve().is_relative_to(REPO)
    assert "mufuse" in str(dest)
