from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path

from .errors import InvalidInputFileError


@dataclass(frozen=True, slots=True)
class ArchiveSafetyLimits:
    max_members: int = 100_000
    max_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024
    max_single_member_bytes: int = 1024 * 1024 * 1024


def validate_zip_archive(path: Path, limits: ArchiveSafetyLimits) -> dict[str, int]:
    """Validate OOXML/ZIP expansion limits before handing the package to parsers.

    This does not attempt to prove a ZIP is benign. It establishes deterministic
    resource ceilings so a tiny compressed input cannot expand without bound.
    """
    if not zipfile.is_zipfile(path):
        return {"members": 0, "uncompressed_bytes": 0, "compressed_bytes": 0}

    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise InvalidInputFileError(f"Unable to inspect ZIP/OOXML archive safely: {path.name}") from exc

    if len(infos) > limits.max_members:
        raise InvalidInputFileError(
            f"Archive contains {len(infos)} members, exceeding the configured limit of {limits.max_members}."
        )

    total_uncompressed = 0
    total_compressed = 0
    for info in infos:
        if info.file_size < 0 or info.compress_size < 0:
            raise InvalidInputFileError(f"Archive contains an invalid member size: {info.filename}")
        if info.file_size > limits.max_single_member_bytes:
            raise InvalidInputFileError(
                f"Archive member '{info.filename}' expands to {info.file_size} bytes, exceeding the configured "
                f"single-member limit of {limits.max_single_member_bytes}."
            )
        total_uncompressed += info.file_size
        total_compressed += info.compress_size
        if total_uncompressed > limits.max_uncompressed_bytes:
            raise InvalidInputFileError(
                f"Archive expands to more than {limits.max_uncompressed_bytes} bytes, exceeding the configured limit."
            )

    return {
        "members": len(infos),
        "uncompressed_bytes": total_uncompressed,
        "compressed_bytes": total_compressed,
    }
