from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .doctor import environment_report
from .engine import ExtractionEngine, ExtractionOptions
from .errors import FilesExtractError
from .output import write_output_package

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".docm", ".xlsx", ".xlsm", ".pptx", ".pptm", ".doc", ".xls", ".ppt"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="files-extract", description="Local-first structured document extraction engine.")
    parser.add_argument("--version", action="version", version=f"files-extract {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_p = sub.add_parser("inspect", help="Detect a file type without extracting it.")
    inspect_p.add_argument("input", type=Path)

    extract_p = sub.add_parser("extract", help="Extract one supported document.")
    extract_p.add_argument("input", type=Path)
    extract_p.add_argument("-o", "--output", type=Path)
    extract_p.add_argument("--format", choices=("both", "json", "markdown"), default="both")
    extract_p.add_argument("--json-indent", type=int, default=2)
    extract_p.add_argument("--no-assets", action="store_true", help="Do not write embedded media/attachments to the assets directory.")
    extract_p.add_argument("--no-render-word-pages", action="store_true", help="Skip LibreOffice Word page-count verification.")
    extract_p.add_argument("--max-file-size-mb", type=int, default=512)

    batch_p = sub.add_parser("batch", help="Extract all supported files in a directory.")
    batch_p.add_argument("input", type=Path)
    batch_p.add_argument("-o", "--output", type=Path, required=True)
    batch_p.add_argument("--recursive", action="store_true")
    batch_p.add_argument("--no-assets", action="store_true")
    batch_p.add_argument("--no-render-word-pages", action="store_true")
    batch_p.add_argument("--max-file-size-mb", type=int, default=512)

    doctor_p = sub.add_parser("doctor", help="Report dependency/backend availability.")
    doctor_p.add_argument("--json", action="store_true")
    return parser


def _engine(args: argparse.Namespace) -> ExtractionEngine:
    return ExtractionEngine(options=ExtractionOptions(
        render_word_pages=not bool(getattr(args, "no_render_word_pages", False)),
        max_file_size_bytes=int(getattr(args, "max_file_size_mb", 512)) * 1024 * 1024,
    ))


def _extract_one(engine: ExtractionEngine, source: Path, output: Path, args: argparse.Namespace) -> dict[str, object]:
    document = engine.extract(source)
    manifest = write_output_package(
        source.resolve(), document, output,
        output_format=getattr(args, "format", "both"),
        json_indent=getattr(args, "json_indent", 2),
        extract_assets=not bool(getattr(args, "no_assets", False)),
    )
    print(f"Extracted: {source}")
    print(f"Type: {document.metadata.document_type}")
    print(f"Units: {document.unit_count} | Elements: {document.element_count} | Assets: {len(document.assets)}")
    print(f"Warnings: {len(document.warnings)} | Unsupported/partial: {len(document.unsupported_objects)}")
    print(f"Output: {output}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            report = environment_report()
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"Python: {report['python']['version']}")
                for name, info in report["dependencies"].items():
                    status = "OK" if info["available"] else "MISSING"
                    print(f"{name}: {status} {info.get('version') or ''}".rstrip())
                lo = report["external_tools"]["libreoffice"]
                print(f"LibreOffice: {'OK' if lo['available'] else 'MISSING'} {lo.get('version') or ''}".rstrip())
            return 0

        engine = _engine(args)
        if args.command == "inspect":
            d = engine.inspect(args.input)
            print(f"type={d.document_type}")
            print(f"extension={d.extension}")
            print(f"media_type={d.media_type or ''}")
            print(f"legacy_office={str(d.is_legacy_office).lower()}")
            print(f"macro_enabled={str(d.is_macro_enabled).lower()}")
            return 0

        if args.command == "extract":
            out = args.output or args.input.resolve().parent / f"{args.input.stem}_extracted"
            _extract_one(engine, args.input, out, args)
            return 0

        root = args.input.resolve()
        if not root.is_dir():
            raise FilesExtractError(f"Batch input is not a directory: {root}")
        iterator = root.rglob("*") if args.recursive else root.glob("*")
        files = sorted(p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES)
        summary: list[dict[str, object]] = []
        failures = 0
        for source in files:
            relative = source.relative_to(root)
            out = args.output.resolve() / relative.parent / f"{source.stem}_extracted"
            try:
                manifest = _extract_one(engine, source, out, args)
                summary.append({"source": relative.as_posix(), "status": "ok", "summary": manifest["summary"]})
            except Exception as exc:
                failures += 1
                summary.append({"source": relative.as_posix(), "status": "error", "error": str(exc)})
                print(f"Failed: {source}: {exc}", file=sys.stderr)
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "batch-summary.json").write_text(json.dumps({"files": summary, "failures": failures}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Batch complete: {len(files) - failures} succeeded, {failures} failed.")
        return 1 if failures else 0
    except FilesExtractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
