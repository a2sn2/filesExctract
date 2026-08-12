from __future__ import annotations

import hashlib
import mimetypes
import re
import zipfile
from pathlib import Path

from .models import AssetReference, CanonicalDocument, SourceReference

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    cleaned = _SAFE.sub("_", Path(name).name).strip("._")
    return cleaned or "asset.bin"


def collect_ooxml_assets(path: Path, family: str) -> list[AssetReference]:
    prefix = {
        "docx": "word/media/", "docm": "word/media/",
        "pptx": "ppt/media/", "pptm": "ppt/media/",
        "xlsx": "xl/media/", "xlsm": "xl/media/",
    }.get(family)
    if not prefix or not zipfile.is_zipfile(path):
        return []
    assets: list[AssetReference] = []
    with zipfile.ZipFile(path) as archive:
        members = sorted(name for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/"))
        used: set[str] = set()
        for index, member in enumerate(members, start=1):
            payload = archive.read(member)
            base = _safe_name(member)
            out_name = base if base not in used else f"{index:03d}_{base}"
            used.add(out_name)
            media_type, _ = mimetypes.guess_type(base)
            assets.append(AssetReference(
                asset_id=f"{family}-asset-{index}",
                asset_type="embedded_media",
                original_name=base,
                output_path=f"assets/{out_name}",
                media_type=media_type,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                source=SourceReference(archive_part=member),
                metadata={"archive_member": member},
            ))
    return assets


def materialize_assets(source: Path, document: CanonicalDocument, output_dir: Path) -> list[Path]:
    written: list[Path] = []

    archive_assets = [a for a in document.assets if a.metadata.get("archive_member") and a.output_path]

    def materialize_archive(archive_source: Path, assets: list[AssetReference]) -> None:
        if not assets or not zipfile.is_zipfile(archive_source):
            return
        with zipfile.ZipFile(archive_source) as archive:
            for asset in assets:
                member = str(asset.metadata["archive_member"])
                try:
                    payload = archive.read(member)
                except KeyError:
                    continue
                # Re-check the digest before writing so a changed/re-converted source
                # cannot silently produce bytes different from the canonical manifest.
                if asset.sha256 and hashlib.sha256(payload).hexdigest() != asset.sha256:
                    continue
                target = output_dir / str(asset.output_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                written.append(target)

    if archive_assets and zipfile.is_zipfile(source):
        materialize_archive(source, archive_assets)
    elif archive_assets:
        # Legacy DOC/XLS/PPT extraction runs against a temporary OOXML conversion.
        # Re-convert only while writing assets, avoiding persistent temp files and
        # keeping the CanonicalDocument independent from transient paths.
        groups: dict[str, list[AssetReference]] = {}
        for asset in archive_assets:
            target_family = asset.metadata.get("legacy_conversion_target")
            if target_family:
                groups.setdefault(str(target_family), []).append(asset)
        if groups:
            from .libreoffice import converted_temp

            for target_family, assets in groups.items():
                try:
                    with converted_temp(source, target_family) as converted:
                        materialize_archive(converted, assets)
                except Exception:
                    # Extraction has already surfaced the asset metadata; failure to
                    # materialize is reflected by the output manifest's written count.
                    continue

    pdf_assets = [a for a in document.assets if a.asset_type in {"pdf_image", "pdf_attachment"} and a.output_path]
    if pdf_assets and source.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(source, strict=False)
            if reader.is_encrypted:
                reader.decrypt("")
            attachments = None
            for asset in pdf_assets:
                payload: bytes | None = None
                if asset.asset_type == "pdf_image":
                    page_no = int(asset.metadata["pdf_page"])
                    image_index = int(asset.metadata["pdf_image_index"])
                    try:
                        payload = reader.pages[page_no - 1].images[image_index].data
                    except Exception:
                        payload = None
                elif asset.asset_type == "pdf_attachment":
                    if attachments is None:
                        attachments = reader.attachments
                    name = str(asset.metadata["pdf_attachment_name"])
                    index = int(asset.metadata["pdf_attachment_index"])
                    try:
                        payload = attachments[name][index]
                    except Exception:
                        payload = None
                if payload is None:
                    continue
                target = output_dir / str(asset.output_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                written.append(target)
        except Exception:
            pass

    return written
