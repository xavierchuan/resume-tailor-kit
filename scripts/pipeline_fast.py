#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from extract_job_card import build_job_card
from select_content import select_content_payload


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(jd_file: Path | None, jd_text: str | None) -> str:
    if jd_file and jd_text:
        raise ValueError("Use only one of --jd-file or --jd-text.")
    if jd_file:
        return jd_file.read_text(encoding="utf-8")
    if jd_text:
        return jd_text
    raise ValueError("Provide --jd-file or --jd-text.")


def bank_signature(bank_dir: Path) -> str:
    tracked = [
        bank_dir / "candidate_profile.yaml",
        bank_dir / "project_evidence.yaml",
        bank_dir / "bullet_library.yaml",
        bank_dir / "skills_blocks.yaml",
        bank_dir / "template_registry.yaml",
    ]
    hasher = hashlib.sha256()
    for file in tracked:
        if not file.exists():
            continue
        hasher.update(file.name.encode("utf-8"))
        hasher.update(file.read_bytes())
    return hasher.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast cached pipeline: full JD -> job card -> selected content.")
    parser.add_argument("--jd-file", type=Path, help="Path to JD text file.")
    parser.add_argument("--jd-text", type=str, help="Raw JD text.")
    parser.add_argument("--bank-dir", type=Path, default=Path("bank"), help="Evidence bank directory.")
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/resume-tailor-cache"), help="Cache directory.")
    parser.add_argument("--output-job-card", type=Path, help="Write job card JSON to output path.")
    parser.add_argument("--output-selected", type=Path, help="Write selected content JSON to output path.")
    parser.add_argument("--print-summary", action="store_true", help="Print concise summary in addition to JSON.")
    args = parser.parse_args()

    try:
        jd = read_text(args.jd_file, args.jd_text)
    except ValueError as exc:
        parser.error(str(exc))

    jd_hash = sha256_text(jd)
    bank_hash = bank_signature(args.bank_dir)
    combo_hash = sha256_text(f"{jd_hash}:{bank_hash}")

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    job_card_cache_path = args.cache_dir / f"{jd_hash}.job_card.json"
    selected_cache_path = args.cache_dir / f"{combo_hash}.selected.json"

    if job_card_cache_path.exists():
        job_card = json.loads(job_card_cache_path.read_text(encoding="utf-8"))
        job_card_cache_hit = True
    else:
        job_card = build_job_card(jd)
        write_json(job_card_cache_path, job_card)
        job_card_cache_hit = False

    if selected_cache_path.exists():
        selected = json.loads(selected_cache_path.read_text(encoding="utf-8"))
        selected_cache_hit = True
    else:
        selected = select_content_payload(job_card=job_card, bank_dir=args.bank_dir)
        write_json(selected_cache_path, selected)
        selected_cache_hit = False

    if args.output_job_card:
        write_json(args.output_job_card, job_card)
    if args.output_selected:
        write_json(args.output_selected, selected)

    payload = {
        "job_card": job_card,
        "selected_content": selected,
        "cache": {
            "job_card_cache_hit": job_card_cache_hit,
            "selected_cache_hit": selected_cache_hit,
            "job_card_cache_path": str(job_card_cache_path),
            "selected_cache_path": str(selected_cache_path),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.print_summary:
        sections = selected.get("project_sections", [])
        counts = ", ".join(f"{s['project_id']}:{len(s['bullet_ids'])}" for s in sections)
        print(
            "\nsummary:"
            f" family={job_card.get('family')}"
            f", template={selected.get('base_template')}"
            f", skills_block={selected.get('skills_block_id')}"
            f", projects=[{counts}]"
            f", cache(job_card={job_card_cache_hit},selected={selected_cache_hit})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
