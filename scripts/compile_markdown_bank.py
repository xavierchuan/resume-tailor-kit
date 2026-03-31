#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bank_runtime import compile_markdown_bank, compute_bank_signature


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile a markdown-first bank into the legacy YAML/JSON bank format.")
    parser.add_argument("--bank-dir", type=Path, required=True, help="Path to markdown bank directory.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for compiled legacy bank files.")
    args = parser.parse_args()

    compiled_dir = compile_markdown_bank(args.bank_dir, args.output_dir)
    print(
        json.dumps(
            {
                "status": "ok",
                "bank_dir": str(args.bank_dir),
                "output_dir": str(compiled_dir),
                "signature": compute_bank_signature(args.bank_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

