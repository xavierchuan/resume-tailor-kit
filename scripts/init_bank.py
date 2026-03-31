#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a local markdown bank from bank-template/.")
    parser.add_argument("--target", type=Path, default=Path("bank"), help="Target bank directory.")
    parser.add_argument("--force", action="store_true", help="Overwrite the target directory if it already exists.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source = repo_root / "bank-template"
    target = args.target.resolve()

    if not source.exists():
        raise RuntimeError(f"Missing bank-template directory at {source}.")

    if target.exists():
        if any(target.iterdir()) and not args.force:
            raise RuntimeError(f"{target} already exists and is not empty. Use --force to overwrite it.")
        if args.force:
            shutil.rmtree(target)

    shutil.copytree(source, target)
    print(json.dumps({"status": "ok", "source": str(source), "target": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

