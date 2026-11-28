"""Fetch the public Muse 2 artifact set, the second score of feature 002 (research R12).

    uv run python scripts/fetch_muse2_set.py [--dest DIR] [--from FILE]

Lee and Ahn, figshare https://doi.org/10.6084/m9.figshare.30162868.v1 (CC BY 4.0). It downloads
`sourcedata.zip` (about 400 MB), or takes FILE when the download was made in a browser, checks the
published MD5, unpacks it into DIR (default: the user's cache folder, never this repository) and
prints the folder. This is the only network access of the feature; it sends nothing but the
download request. The files are third-party data: they are read, never run, and never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import platformdirs

PAGE = "https://doi.org/10.6084/m9.figshare.30162868.v1"
URL = "https://ndownloader.figshare.com/files/58088461"
ARCHIVE = "sourcedata.zip"
EXPECTED_MD5 = "cdc629a35f58b1faf7a9981a86783786"
REPO = Path(__file__).resolve().parents[1]


def default_dest() -> Path:
    return platformdirs.user_cache_path("mufuse", appauthor=False) / "muse2-artifacts"


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "mufuse-fetch/1"})
    partial = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(request, timeout=60) as response, partial.open("wb") as out:
        shutil.copyfileobj(response, out, length=1 << 20)
    partial.replace(target)


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def unpack(archive: Path, dest: Path) -> None:
    """Every entry must land inside `dest`; an archive that tries otherwise is refused whole."""
    root = dest.resolve()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if not (root / name).resolve().is_relative_to(root):
                raise ValueError(f"the archive entry {name!r} would land outside {dest}")
        z.extractall(root)


def _by_hand() -> str:
    return (
        "Download it in a browser instead:\n"
        f"  1. open {PAGE}\n"
        f"  2. download {ARCHIVE}\n"
        "  3. run: uv run python scripts/fetch_muse2_set.py --from <the downloaded file>"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", type=Path, default=default_dest(), help="where to unpack")
    parser.add_argument("--from", dest="source", type=Path, help="a sourcedata.zip already here")
    args = parser.parse_args(argv)
    dest: Path = args.dest
    if dest.resolve().is_relative_to(REPO):
        print(f"Refused: {dest} is inside the repository; third-party data stays outside it.")
        return 1
    dest.mkdir(parents=True, exist_ok=True)
    archive: Path = args.source or dest / ARCHIVE
    if args.source is None:
        print(f"Downloading {ARCHIVE} (about 400 MB) from figshare…")
        try:
            download(URL, archive)
        except (urllib.error.URLError, OSError) as exc:
            print(f"The download was refused or failed: {exc}")
            print(_by_hand())
            return 1
    if md5(archive) != EXPECTED_MD5:
        print(f"Refused: the checksum of {archive} is not the published one ({EXPECTED_MD5}).")
        return 1
    try:
        unpack(archive, dest)
    except (ValueError, zipfile.BadZipFile) as exc:
        print(f"Refused: {exc}")
        return 1
    print(dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
