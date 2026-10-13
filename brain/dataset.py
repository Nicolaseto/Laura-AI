from __future__ import annotations

import base64
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from PIL import Image

from .vision import MAX_IMAGE_BYTES, decode_image_bytes


MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024
MAX_MEMBERS = 2_000
MAX_PACKAGE_IMAGES = 1000
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


@dataclass
class ImagePackage:
    images: list[tuple[str, bytes]]
    skipped: int
    limited: int
    categories: dict[str, int]

    def iter_images(self):
        # Keep compressed previews in the package, decoding only one at a time.
        for label, raw in self.images:
            yield label, decode_image_bytes(raw)


def _clean_label(value: str) -> str:
    value = re.sub(r"[_-]+", " ", value)
    return " ".join(value.strip().lower().split())[:60]


def read_image_package(data_url: str, limit_per_category: int = 30) -> ImagePackage:
    """Lê um ZIP em memória. O nome da pasta pai vira a categoria."""
    limit_per_category = min(250, max(3, int(limit_per_category)))
    encoded = data_url.split(",", 1)[-1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("pacote ZIP inválido") from exc
    if not raw or len(raw) > MAX_ARCHIVE_BYTES:
        raise ValueError("o pacote deve ter no máximo 100 MB")

    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ValueError("arquivo ZIP inválido") from exc

    members = archive.infolist()
    if len(members) > MAX_MEMBERS:
        raise ValueError("o pacote possui arquivos demais")
    if sum(item.file_size for item in members) > MAX_UNCOMPRESSED_BYTES:
        raise ValueError("o conteúdo descompactado é muito grande")

    images: list[tuple[str, bytes]] = []
    counts: dict[str, int] = {}
    skipped = limited = 0
    for item in members:
        name = item.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if item.is_dir() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2 or item.flag_bits & 0x1:
            skipped += 1
            continue
        label = _clean_label(path.parent.name)
        if not label or label.startswith(".") or path.name.startswith("."):
            skipped += 1
            continue
        if counts.get(label, 0) >= limit_per_category or len(images) >= MAX_PACKAGE_IMAGES:
            limited += 1
            continue
        try:
            if item.file_size > MAX_IMAGE_BYTES:
                skipped += 1
                continue
            image = decode_image_bytes(archive.read(item))
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            image.save(output, "JPEG", quality=85)
        except (ValueError, RuntimeError, OSError, zipfile.BadZipFile):
            skipped += 1
            continue
        images.append((label, output.getvalue()))
        counts[label] = counts.get(label, 0) + 1
    archive.close()
    if not images:
        raise ValueError("nenhuma imagem organizada em pastas foi encontrada")
    return ImagePackage(images, skipped, limited, counts)
