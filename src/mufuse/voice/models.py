"""The speech models (007b): pinned files, their checksums, and `mufuse voice fetch`.

Fetching is the only step of voice that touches the network, and it runs only when asked. Every
file is checked against its sha256 before it is unpacked; a mismatch deletes the download. The
models live in the user data folder, beside the other caches, never in the repository.
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_data_path

RELEASES = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
CHUNK = 1 << 20


@dataclass(frozen=True)
class ModelFile:
    name: str  # what is downloaded (an .onnx file, or a .tar.bz2 that unpacks to `folder`)
    tag: str  # the sherpa-onnx release that holds it
    sha256: str
    mb: int
    licence: str
    folder: str | None = None  # the folder a .tar.bz2 unpacks to

    @property
    def url(self) -> str:
        return f"{RELEASES}/{self.tag}/{self.name}"

    def path(self, root: Path) -> Path:
        return root / (self.folder or self.name)


VAD = ModelFile(
    "silero_vad.onnx",
    "asr-models",
    "9e2449e1087496d8d4caba907f23e0bd3f78d91fa552479bb9c23ac09cbb1fd6",
    1,
    "MIT (Silero VAD)",
)
HEAR = {
    "base": ModelFile(
        "sherpa-onnx-moonshine-base-en-quantized-2026-02-27.tar.bz2",
        "asr-models",
        "43232c1d13013d37317163baec3135bd771a186a4356f28c889bab453bb0e891",
        111,
        "MIT (Moonshine, English)",
        "sherpa-onnx-moonshine-base-en-quantized-2026-02-27",
    ),
    "small": ModelFile(
        "sherpa-onnx-moonshine-tiny-en-quantized-2026-02-27.tar.bz2",
        "asr-models",
        "9ec31b342d8fa3240c3b81b8f82e1cf7e3ac467c93ca5a999b741d5887164f8d",
        29,
        "MIT (Moonshine, English)",
        "sherpa-onnx-moonshine-tiny-en-quantized-2026-02-27",
    ),
}
SPEAK = ModelFile(
    "sherpa-onnx-pocket-tts-int8-2026-01-26.tar.bz2",
    "tts-models",
    "f4da7c7bd465f7b91e89191487fe90504396a51d6f0bcf94d0787633e2657293",
    98,
    "CC-BY-4.0 (Pocket TTS, Kyutai)",
    "sherpa-onnx-pocket-tts-int8-2026-01-26",
)


def models_dir() -> Path:
    """`<user data>/Models`, beside the companion's store (%LOCALAPPDATA%\\mufuse on Windows)."""
    return user_data_path("mufuse", appauthor=False) / "Models"


def needed(small: bool = False) -> tuple[ModelFile, ...]:
    return (VAD, HEAR["small" if small else "base"], SPEAK)


def missing(root: Path, small: bool = False) -> list[ModelFile]:
    return [m for m in needed(small) if not m.path(root).exists()]


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


Download = Callable[[str, Path], None]


def _download(url: str, to: Path) -> None:  # pragma: no cover - network
    with urllib.request.urlopen(url, timeout=60) as r, to.open("wb") as f:
        shutil.copyfileobj(r, f, CHUNK)


class ChecksumError(Exception):
    pass


def fetch(
    model: ModelFile,
    root: Path,
    download: Download = _download,
    say: Callable[[str], None] = lambda _: None,
) -> Path:
    """Download, check and unpack one model; returns where it is. Nothing to do if it is there."""
    target = model.path(root)
    if target.exists():
        return target
    root.mkdir(parents=True, exist_ok=True)
    part = root / (model.name + ".part")
    say(f"Fetching {model.name} ({model.mb} MB, {model.licence})")
    download(model.url, part)
    got = sha256_of(part)
    if got != model.sha256:
        part.unlink()
        raise ChecksumError(f"{model.name}: sha256 {got} is not the pinned {model.sha256}")
    if model.folder is None:
        part.replace(target)
        return target
    with tarfile.open(part, "r:bz2") as tar:
        tar.extractall(root, filter="data")  # no paths outside root, no links out
    part.unlink()
    if not target.exists():
        raise ChecksumError(f"{model.name} did not unpack to {model.folder}")
    return target
