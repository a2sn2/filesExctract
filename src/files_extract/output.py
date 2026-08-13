from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .assets import materialize_assets
from .models import CanonicalDocument
from .renderers import render_json, render_markdown


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _is_existing_files_extract_package(output_dir: Path) -> bool:
    """Return True only when the directory contains our previous manifest.

    This prevents FilesExtract from deleting arbitrary user content merely
    because a caller chose a non-empty output directory. Cleanup is limited to
    directories that can be positively identified as a prior FilesExtract
    package.
    """

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("schema_version")
        and isinstance(payload.get("source"), dict)
        and payload["source"].get("filename")
        and isinstance(payload.get("summary"), dict)
        and isinstance(payload.get("files"), list)
    )


def _remove_generated_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    is_junction = getattr(path, "is_junction", None)
    if path.is_symlink() or (callable(is_junction) and is_junction()):
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def _prepare_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not _is_existing_files_extract_package(output_dir):
        return

    # These names are reserved by the FilesExtract package contract. Removing
    # them before a repeated extraction prevents stale Markdown or stale assets
    # from a previous run from masquerading as part of the new package.
    for name in ("document.json", "document.md", "manifest.json", "assets"):
        _remove_generated_path(output_dir / name)


def write_output_package(
    source: Path,
    document: CanonicalDocument,
    output_dir: Path,
    *,
    output_format: str = "both",
    json_indent: int = 2,
    extract_assets: bool = True,
    pdf_password: str | None = None,
) -> dict[str, object]:
    _prepare_output_dir(output_dir)
    written: list[Path] = []
    if output_format in {"both", "json"}:
        p = output_dir / "document.json"
        p.write_text(render_json(document, indent=json_indent), encoding="utf-8")
        written.append(p)
    if output_format in {"both", "markdown"}:
        p = output_dir / "document.md"
        p.write_text(render_markdown(document), encoding="utf-8")
        written.append(p)
    asset_paths = materialize_assets(
        source, document, output_dir, pdf_password=pdf_password
    ) if extract_assets else []
    written.extend(asset_paths)
    manifest = {
        "schema_version": document.schema_version,
        "source": {
            "filename": document.metadata.filename,
            "sha256": document.metadata.sha256,
            "type": document.metadata.document_type,
        },
        "summary": {
            "units": document.unit_count,
            "elements": document.element_count,
            "warnings": len(document.warnings),
            "unsupported_objects": len(document.unsupported_objects),
            "assets_declared": len(document.assets),
            "assets_requested": bool(extract_assets),
            "assets_written": len(asset_paths),
            "assets_failed": max(0, len(document.assets) - len(asset_paths)) if extract_assets else 0,
            "potentially_active_assets": sum(
                1 for asset in document.assets if asset.metadata.get("potentially_active_content")
            ),
        },
        "files": [],
    }
    for path in written:
        if not path.exists():
            continue
        manifest["files"].append({
            "path": path.relative_to(output_dir).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        })
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
