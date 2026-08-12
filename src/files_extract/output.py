from __future__ import annotations

import hashlib
import json
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


def write_output_package(
    source: Path,
    document: CanonicalDocument,
    output_dir: Path,
    *,
    output_format: str = "both",
    json_indent: int = 2,
    extract_assets: bool = True,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    if output_format in {"both", "json"}:
        p = output_dir / "document.json"
        p.write_text(render_json(document, indent=json_indent), encoding="utf-8")
        written.append(p)
    if output_format in {"both", "markdown"}:
        p = output_dir / "document.md"
        p.write_text(render_markdown(document), encoding="utf-8")
        written.append(p)
    asset_paths = materialize_assets(source, document, output_dir) if extract_assets else []
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
            "assets_written": len(asset_paths),
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
