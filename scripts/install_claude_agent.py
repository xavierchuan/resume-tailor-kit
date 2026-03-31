#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the resume-tailor-kit Claude Code subagent into ~/.claude/agents.")
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path.home() / ".claude" / "agents",
        help="Claude Code agents directory.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite an existing installed agent.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    source = repo_root / ".claude" / "agents" / "resume-tailor-kit.md"
    target = args.target_dir.expanduser().resolve() / "resume-tailor-kit.md"

    if not source.exists():
        raise RuntimeError(f"Missing source agent file: {source}")
    if target.exists() and not args.force:
        raise RuntimeError(f"{target} already exists. Use --force to overwrite it.")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    print(json.dumps({"status": "ok", "source": str(source), "target": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
