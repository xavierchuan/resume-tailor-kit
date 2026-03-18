#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()


def read_pdf_pages(pdf_path: Path) -> int:
    output = run_cmd(["pdfinfo", str(pdf_path)])
    match = re.search(r"^Pages:\s+(\d+)$", output, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("Failed to parse page count from pdfinfo output.")
    return int(match.group(1))


def run_contract_check(
    output_dir: Path,
    base_name: str,
    include_cover: bool,
    cover_base_name: str | None,
) -> dict:
    script = Path(__file__).with_name("check_output_contract.py")
    cmd = [
        "python3",
        str(script),
        "--output-dir",
        str(output_dir),
        "--base-name",
        base_name,
    ]
    if include_cover:
        if not cover_base_name:
            raise RuntimeError("--include-cover requires --cover-base-name.")
        cmd.extend(["--include-cover", "--cover-base-name", cover_base_name])
    output = run_cmd(cmd)
    return json.loads(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast QA for tailored resume outputs.")
    parser.add_argument("--pdf", type=Path, required=True, help="CV PDF path.")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum allowed pages for CV.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory to contract-check.")
    parser.add_argument("--base-name", required=True, help="CV base name without extension.")
    parser.add_argument("--include-cover", action="store_true", help="Validate CV+cover contract.")
    parser.add_argument("--cover-base-name", help="Cover base name (required when include-cover is enabled).")
    args = parser.parse_args()

    pages = read_pdf_pages(args.pdf)
    contract = run_contract_check(
        output_dir=args.output_dir,
        base_name=args.base_name,
        include_cover=args.include_cover,
        cover_base_name=args.cover_base_name,
    )

    result = {
        "status": "pass",
        "pdf": str(args.pdf),
        "pages": pages,
        "max_pages": args.max_pages,
        "page_check_pass": pages <= args.max_pages,
        "contract_check_pass": contract.get("status") == "pass",
        "contract": contract,
    }

    if not result["page_check_pass"] or not result["contract_check_pass"]:
        result["status"] = "fail"

    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
