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
    root = {
        "docx": "word", "docm": "word",
        "pptx": "ppt", "pptm": "ppt",
        "xlsx": "xl", "xlsm": "xl",
    }.get(family)
    if not root or not zipfile.is_zipfile(path):
        return []

    specs = [
        (f"{root}/media/", "embedded_media", "media"),
        (f"{root}/embeddings/", "embedded_object", "embeddings"),
        (f"{root}/activeX/", "activex_part", "activex"),
        (f"{root}/charts/", "raw_package_part", "package-parts/charts"),
        (f"{root}/diagrams/", "raw_package_part", "package-parts/diagrams"),
    ]
    if root == "xl":
        specs.extend([
            ("xl/pivotTables/", "raw_package_part", "package-parts/pivot-tables"),
            ("xl/slicers/", "raw_package_part", "package-parts/slicers"),
            ("xl/queryTables/", "raw_package_part", "package-parts/query-tables"),
        ])
    vba_member = f"{root}/vbaProject.bin"

    assets: list[AssetReference] = []
    used_paths: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        candidates: list[tuple[str, str, str]] = []
        for prefix, asset_type, directory in specs:
            candidates.extend(
                (member, asset_type, directory)
                for member in sorted(names)
                if member.startswith(prefix) and not member.endswith("/")
            )
        candidates.extend(
            (member, "raw_package_part", "package-parts/custom-xml")
            for member in sorted(names)
            if member.startswith("customXml/") and not member.endswith("/")
        )
        if root == "xl" and "xl/connections.xml" in names:
            candidates.append(("xl/connections.xml", "raw_package_part", "package-parts/connections"))
        if vba_member in names:
            candidates.append((vba_member, "vba_project", "macros"))

        for index, (member, asset_type, directory) in enumerate(candidates, start=1):
            payload = archive.read(member)
            base = _safe_name(member)
            out_name = base
            candidate_path = f"assets/{directory}/{out_name}"
            if candidate_path in used_paths:
                out_name = f"{index:03d}_{base}"
                candidate_path = f"assets/{directory}/{out_name}"
            used_paths.add(candidate_path)
            media_type, _ = mimetypes.guess_type(base)
            assets.append(AssetReference(
                asset_id=f"{family}-asset-{index}",
                asset_type=asset_type,
                original_name=base,
                output_path=candidate_path,
                media_type=media_type or ("application/vnd.ms-office.vbaProject" if asset_type == "vba_project" else None),
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                source=SourceReference(archive_part=member),
                metadata={
                    "archive_member": member,
                    "potentially_active_content": asset_type in {"embedded_object", "activex_part", "vba_project"},
                },
            ))
    return assets


def materialize_assets(
    source: Path,
    document: CanonicalDocument,
    output_dir: Path,
    *,
    pdf_password: str | None = None,
) -> list[Path]:
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
                if asset.sha256 and hashlib.sha256(payload).hexdigest() != asset.sha256:
                    continue
                target = output_dir / str(asset.output_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                written.append(target)

    if archive_assets and zipfile.is_zipfile(source):
        materialize_archive(source, archive_assets)
    elif archive_assets:
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
                    continue

    pdf_assets = [a for a in document.assets if a.asset_type in {"pdf_image", "pdf_attachment"} and a.output_path]
    if pdf_assets and source.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(source, strict=False)
            if reader.is_encrypted:
                result = reader.decrypt(pdf_password or "")
                if not result:
                    return written
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
