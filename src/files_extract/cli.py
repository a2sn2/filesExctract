from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import ExtractionEngine
from .errors import FilesExtractError
from .renderers import render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="files-extract",
        description="Extract document content into structured JSON and Markdown.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Detect a file type without extracting it.")
    inspect_parser.add_argument("input", type=Path)

    extract_parser = subparsers.add_parser("extract", help="Extract a supported document.")
    extract_parser.add_argument("input", type=Path)
    extract_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output directory. Defaults to <input-stem>_extracted next to the source file.",
    )
    extract_parser.add_argument(
        "--format",
        choices=("both", "json", "markdown"),
        default="both",
        help="Output format to write.",
    )
    extract_parser.add_argument("--json-indent", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = ExtractionEngine()

    try:
        if args.command == "inspect":
            detected = engine.inspect(args.input)
            print(f"type={detected.document_type}")
            print(f"extension={detected.extension}")
            print(f"media_type={detected.media_type or ''}")
            print(f"legacy_office={str(detected.is_legacy_office).lower()}")
            print(f"macro_enabled={str(detected.is_macro_enabled).lower()}")
            return 0

        document = engine.extract(args.input)
        output_dir = args.output or args.input.resolve().parent / f"{args.input.stem}_extracted"
        output_dir.mkdir(parents=True, exist_ok=True)

        if args.format in {"both", "json"}:
            (output_dir / "document.json").write_text(
                render_json(document, indent=args.json_indent),
                encoding="utf-8",
            )
        if args.format in {"both", "markdown"}:
            (output_dir / "document.md").write_text(
                render_markdown(document),
                encoding="utf-8",
            )

        print(f"Extracted: {args.input}")
        print(f"Type: {document.metadata.document_type}")
        print(f"Units: {document.unit_count}")
        print(f"Warnings: {len(document.warnings)}")
        print(f"Unsupported/partial objects: {len(document.unsupported_objects)}")
        print(f"Output: {output_dir}")
        return 0
    except FilesExtractError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"I/O error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
