#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the resume-tailor-kit Codex skill into ~/.codex/skills.")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path.home() / ".codex" / "skills",
        help="Codex skills directory.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing installed skill.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source = repo_root / "codex-skill" / "resume-tailor-kit"
    target = args.target_dir.expanduser().resolve() / "resume-tailor-kit"

    if not source.exists():
        raise RuntimeError(f"Missing source skill directory: {source}")
    if target.exists():
        if not args.force:
            raise RuntimeError(f"{target} already exists. Use --force to overwrite it.")
        shutil.rmtree(target)

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    print(json.dumps({"status": "ok", "source": str(source), "target": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

