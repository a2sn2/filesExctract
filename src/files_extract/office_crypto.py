from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import ExtractionFailedError


@contextmanager
def decrypted_office_temp(
    source: Path,
    password: str,
    *,
    extension: str,
) -> Iterator[Path]:
    """Decrypt an encrypted modern Office container into an isolated temp file.

    The password is only passed to msoffcrypto in memory. The decrypted
    intermediate is deleted when the context exits and is never copied into the
    output package.
    """

    if not password:
        raise ExtractionFailedError(
            "The Office document is encrypted and no password was supplied. "
            "Use --password or enter the password in the desktop application."
        )

    try:
        import msoffcrypto
    except Exception as exc:  # pragma: no cover - packaging/runtime guard
        raise ExtractionFailedError(
            "Encrypted Office support is unavailable because msoffcrypto-tool "
            "is not installed in this runtime."
        ) from exc

    suffix = f".{extension.lstrip('.')}" if extension else ".ooxml"
    with tempfile.TemporaryDirectory(prefix="files-extract-office-decrypt-") as tmp:
        destination = Path(tmp) / f"decrypted{suffix}"
        try:
            with source.open("rb") as encrypted, destination.open("wb") as output:
                office = msoffcrypto.OfficeFile(encrypted)
                try:
                    office.load_key(password=password, verify_password=True)
                except TypeError:
                    # Some older encryption implementations do not support the
                    # verification flag. Decryption still validates naturally.
                    office.load_key(password=password)
                try:
                    office.decrypt(output, verify_integrity=True)
                except TypeError:
                    office.decrypt(output)
        except Exception as exc:
            raise ExtractionFailedError(
                "Unable to decrypt the Office document. The password may be "
                "incorrect or the encryption scheme may be unsupported."
            ) from exc

        if not destination.is_file() or destination.stat().st_size == 0:
            raise ExtractionFailedError(
                "Office decryption completed without producing a usable document."
            )
        yield destination
