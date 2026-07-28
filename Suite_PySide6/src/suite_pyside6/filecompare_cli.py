from __future__ import annotations

import argparse
from pathlib import Path

from suite_pyside6.core.file_compare.models import CompareMode, ComparisonOptions
from suite_pyside6.core.file_compare.reports import as_html, as_json, as_text, write_report
from suite_pyside6.core.file_compare.service import compare_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="filecompare", description="Compara archivos o carpetas de forma exacta y segura.")
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--mode", choices=[item.value for item in CompareMode], default="strict")
    parser.add_argument("--format", choices=["text", "json", "html"], default="text", dest="output_format")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-differences", type=int, default=100)
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--ignore-whitespace", action="store_true")
    parser.add_argument("--ignore-line-endings", action="store_true")
    parser.add_argument("--recursive", action="store_true", help="Aceptado para compatibilidad; las carpetas siempre se recorren recursivamente.")
    parser.add_argument("--generate-visual-diff", action="store_true")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_differences < 1:
        raise SystemExit("--max-differences debe ser mayor que cero")
    options = ComparisonOptions(CompareMode(args.mode), args.max_differences, ignore_case=args.ignore_case, ignore_whitespace=args.ignore_whitespace, ignore_line_endings=args.ignore_line_endings, generate_visual_diff=args.generate_visual_diff, exclusions=tuple(args.exclude))
    result = compare_paths(args.left, args.right, options)
    renderer = {"text": as_text, "json": as_json, "html": as_html}[args.output_format]
    if args.output:
        write_report(result, args.output, args.output_format)
    else:
        print(renderer(result))
    if result.errors:
        return 2
    return 0 if result.strict_equal else 1


if __name__ == "__main__":
    raise SystemExit(main())
