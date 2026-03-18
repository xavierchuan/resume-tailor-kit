#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_expected_files(base_name: str, include_cover: bool) -> list[str]:
    expected = [
        f"{base_name}.tex",
        f"{base_name}.pdf",
    ]
    if include_cover:
        prefix = base_name
        expected.extend(
            [
                f"{prefix}_Cover_Letter.tex",
                f"{prefix}_Cover_Letter.pdf",
            ]
        )
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate resume output file contract.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory containing generated files.")
    parser.add_argument("--base-name", required=True, help="Base output name (without extension).")
    parser.add_argument(
        "--cover-base-name",
        help="Base name for cover files when include-cover is enabled.",
    )
    parser.add_argument(
        "--include-cover",
        action="store_true",
        help="Expect cover letter files in addition to CV files.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    if args.include_cover and not args.cover_base_name:
        parser.error("--include-cover requires --cover-base-name.")

    expected_cv = [
        f"{args.base_name}.tex",
        f"{args.base_name}.pdf",
    ]
    expected_cover = []
    if args.include_cover:
        expected_cover = [
            f"{args.cover_base_name}_Cover_Letter.tex",
            f"{args.cover_base_name}_Cover_Letter.pdf",
        ]
    expected = expected_cv + expected_cover
    expected_set = set(expected)
    existing = {p.name for p in output_dir.iterdir() if p.is_file()}

    matched = sorted(name for name in existing if name in expected_set)
    missing = sorted(name for name in expected_set if name not in existing)

    related_prefixes = {args.base_name}
    if args.cover_base_name:
        related_prefixes.add(args.cover_base_name)
    related = sorted(
        name
        for name in existing
        if any(name.startswith(prefix) for prefix in related_prefixes)
    )
    extras = sorted(name for name in related if name not in expected_set)

    result = {
        "status": "pass" if not missing and not extras and len(matched) == len(expected) else "fail",
        "include_cover": args.include_cover,
        "expected_count": len(expected),
        "matched_count": len(matched),
        "expected_files": expected,
        "missing_files": missing,
        "extra_related_files": extras,
    }

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
