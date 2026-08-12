from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .errors import ExternalToolError


def find_libreoffice() -> str | None:
    return shutil.which("libreoffice") or shutil.which("soffice")


def libreoffice_version() -> str | None:
    executable = find_libreoffice()
    if not executable:
        return None
    try:
        proc = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=15, check=False)
        text = (proc.stdout or proc.stderr).strip()
        return text or None
    except Exception:
        return None


def convert_office(source: Path, target_extension: str, output_dir: Path, *, timeout: int = 180) -> Path:
    executable = find_libreoffice()
    if not executable:
        raise ExternalToolError(
            "LibreOffice/soffice was not found. Install LibreOffice or use the Docker image for legacy Office conversion and Word pagination."
        )
    target_extension = target_extension.lower().lstrip(".")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="files-extract-lo-profile-") as profile:
        profile_uri = Path(profile).resolve().as_uri()
        cmd = [
            executable,
            "--headless",
            f"-env:UserInstallation={profile_uri}",
            "--convert-to",
            target_extension,
            "--outdir",
            str(output_dir),
            str(source),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ExternalToolError(f"LibreOffice conversion timed out after {timeout} seconds: {source.name}") from exc
    candidates = sorted(output_dir.glob(f"*.{target_extension}"), key=lambda p: p.stat().st_mtime, reverse=True)
    expected = output_dir / f"{source.stem}.{target_extension}"
    if expected.exists():
        return expected
    if proc.returncode != 0 or not candidates:
        message = (proc.stderr or proc.stdout or "unknown LibreOffice error").strip()
        raise ExternalToolError(f"LibreOffice failed converting {source.name} to {target_extension}: {message}")
    return candidates[0]


@contextmanager
def converted_temp(source: Path, target_extension: str, *, timeout: int = 180) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix="files-extract-convert-") as tmp:
        yield convert_office(source, target_extension, Path(tmp), timeout=timeout)
