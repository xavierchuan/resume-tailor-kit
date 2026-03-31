#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from bank_runtime import compute_bank_signature, resolve_runtime_bank
from build_rewrite_artifacts import build_rewrite_artifacts
from build_variant_bank import build_variant_bank
from extract_job_card import build_job_card
from select_content import select_content_payload


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def read_text(jd_file: Path | None, jd_text: str | None) -> str:
    if jd_file and jd_text:
        raise ValueError("Use only one of --jd-file or --jd-text.")
    if jd_file:
        return jd_file.read_text(encoding="utf-8")
    if jd_text:
        return jd_text
    raise ValueError("Provide --jd-file or --jd-text.")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cv_signature(cv_root: Path) -> str:
    hasher = hashlib.sha256()
    for file in sorted(path for path in cv_root.rglob("*.tex") if path.is_file()):
        if any(part.startswith(".") for part in file.parts):
            continue
        stat = file.stat()
        hasher.update(str(file.relative_to(cv_root)).encode("utf-8"))
        hasher.update(str(stat.st_size).encode("utf-8"))
        hasher.update(str(int(stat.st_mtime)).encode("utf-8"))
    return hasher.hexdigest()


def empty_variant_bank() -> dict[str, Any]:
    return {
        "cv_root": None,
        "bank_dir": None,
        "stats": {"tex_files_scanned": 0, "projects_seen": 0},
        "profiles": [],
        "skills_lines": [],
        "project_variants": {},
    }


def build_default_artifact_paths(artifacts_dir: Path) -> dict[str, Path]:
    return {
        "job_card": artifacts_dir / "job_card.json",
        "selected": artifacts_dir / "selected.json",
        "variant_bank": artifacts_dir / "variant_bank.json",
        "rewrite_seed": artifacts_dir / "rewrite_seed.json",
        "rewrite_rules": artifacts_dir / "rewrite_pack.rules.json",
        "rewrite_used": artifacts_dir / "rewrite_pack.used.json",
    }


def ensure_variant_bank(
    *,
    cache_dir: Path,
    bank_dir: Path,
    cv_root: Path | None,
    variant_bank_path: Path | None,
) -> tuple[dict[str, Any], str, bool]:
    if variant_bank_path:
        return load_json(variant_bank_path), "external", False
    if cv_root:
        signature = sha256_text(f"{cv_signature(cv_root)}:{compute_bank_signature(bank_dir)}")
        cached_path = cache_dir / f"{signature}.variant_bank.json"
        if cached_path.exists():
            return load_json(cached_path), "cache", True
        payload = build_variant_bank(cv_root=cv_root, bank_dir=bank_dir)
        write_json(cached_path, payload)
        return payload, "cache", False
    return empty_variant_bank(), "starter", False


def maybe_write_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Starter/quality resume tailoring pipeline: JD -> job card -> selected evidence -> rewrite artifacts."
    )
    parser.add_argument("--jd-file", type=Path, help="Path to JD text file.")
    parser.add_argument("--jd-text", type=str, help="Raw JD text.")
    parser.add_argument("--bank-dir", type=Path, default=Path("bank"), help="Evidence bank directory.")
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp/resume-tailor-cache"), help="Cache directory.")
    parser.add_argument("--cv-root", type=Path, help="External root containing historical CV .tex files.")
    parser.add_argument("--variant-bank", type=Path, help="Prebuilt external variant_bank.json path.")
    parser.add_argument("--artifacts-dir", type=Path, help="Directory for pipeline artifacts.")
    parser.add_argument("--output-job-card", type=Path, help="Write job card JSON to output path.")
    parser.add_argument("--output-selected", type=Path, help="Write selected content JSON to output path.")
    parser.add_argument("--prepare-only", action="store_true", help="Prepare artifacts and stop without choosing a final rewrite pack.")
    parser.add_argument("--rewrite-mode", choices=["rules", "agent"], default="rules", help="Rules writes rewrite_pack.used.json; agent expects a later injected rewrite pack.")
    parser.add_argument("--rewrite-pack", type=Path, help="Agent-authored rewrite pack to materialize as rewrite_pack.used.json.")
    parser.add_argument("--print-summary", action="store_true", help="Print concise summary in addition to JSON.")
    args = parser.parse_args()

    try:
        jd = read_text(args.jd_file, args.jd_text)
    except ValueError as exc:
        parser.error(str(exc))

    runtime_bank_dir = resolve_runtime_bank(args.bank_dir)
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    jd_hash = sha256_text(jd)
    bank_hash = compute_bank_signature(args.bank_dir)
    combo_hash_parts = [jd_hash, bank_hash]
    if args.cv_root:
        combo_hash_parts.append(cv_signature(args.cv_root))
    if args.variant_bank:
        combo_hash_parts.append(sha256_file(args.variant_bank))
    artifacts_dir = args.artifacts_dir or (args.cache_dir / sha256_text(":".join(combo_hash_parts)))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    paths = build_default_artifact_paths(artifacts_dir)

    job_card_cache_path = args.cache_dir / f"{jd_hash}.job_card.json"
    selected_cache_path = args.cache_dir / f"{sha256_text(f'{jd_hash}:{bank_hash}')}.selected.json"

    if job_card_cache_path.exists():
        job_card = load_json(job_card_cache_path)
        job_card_cache_hit = True
    else:
        job_card = build_job_card(jd)
        write_json(job_card_cache_path, job_card)
        job_card_cache_hit = False

    if selected_cache_path.exists():
        selected = load_json(selected_cache_path)
        selected_cache_hit = True
    else:
        selected = select_content_payload(job_card=job_card, bank_dir=runtime_bank_dir)
        write_json(selected_cache_path, selected)
        selected_cache_hit = False

    variant_bank, variant_source, variant_cache_hit = ensure_variant_bank(
        cache_dir=args.cache_dir,
        bank_dir=args.bank_dir,
        cv_root=args.cv_root,
        variant_bank_path=args.variant_bank,
    )
    seed, rules_pack = build_rewrite_artifacts(job_card, selected, runtime_bank_dir, variant_bank)

    write_json(paths["job_card"], job_card)
    write_json(paths["selected"], selected)
    write_json(paths["variant_bank"], variant_bank)
    write_json(paths["rewrite_seed"], seed)
    write_json(paths["rewrite_rules"], rules_pack)

    if args.output_job_card:
        write_json(args.output_job_card, job_card)
    if args.output_selected:
        write_json(args.output_selected, selected)

    rewrite_origin = None
    if args.rewrite_pack:
        maybe_write_copy(args.rewrite_pack, paths["rewrite_used"])
        rewrite_origin = "agent"
    elif args.rewrite_mode == "rules" and not args.prepare_only:
        write_json(paths["rewrite_used"], rules_pack)
        rewrite_origin = "rules"

    mode = "quality" if any([args.cv_root, args.variant_bank, args.rewrite_pack]) else "starter"
    payload: dict[str, Any] = {
        "mode": mode,
        "job_card": job_card,
        "selected_content": selected,
        "cache": {
            "job_card_cache_hit": job_card_cache_hit,
            "selected_cache_hit": selected_cache_hit,
            "job_card_cache_path": str(job_card_cache_path),
            "selected_cache_path": str(selected_cache_path),
            "variant_source": variant_source,
            "variant_cache_hit": variant_cache_hit,
        },
        "bank": {
            "source_bank_dir": str(args.bank_dir.resolve()),
            "runtime_bank_dir": str(runtime_bank_dir),
            "bank_signature": bank_hash,
        },
        "artifacts": {
            "artifacts_dir": str(artifacts_dir),
            "job_card": str(paths["job_card"]),
            "selected": str(paths["selected"]),
            "variant_bank": str(paths["variant_bank"]),
            "rewrite_seed": str(paths["rewrite_seed"]),
            "rewrite_pack_rules": str(paths["rewrite_rules"]),
            "rewrite_pack_used": str(paths["rewrite_used"]) if paths["rewrite_used"].exists() else None,
        },
        "rewrite": {
            "mode": args.rewrite_mode,
            "prepare_only": args.prepare_only,
            "rewrite_origin": rewrite_origin,
            "unsupported_count": rules_pack.get("provenance_check", {}).get("unsupported_count", 0),
        },
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.print_summary:
        sections = selected.get("project_sections", [])
        counts = ", ".join(f"{section['project_id']}:{len(section['bullet_ids'])}" for section in sections)
        print(
            "\nsummary:"
            f" mode={mode}"
            f", family={job_card.get('family')}"
            f", template={selected.get('base_template')}"
            f", rewrite_mode={args.rewrite_mode}"
            f", rewrite_origin={rewrite_origin or 'prepare_only'}"
            f", projects=[{counts}]"
            f", unsupported={rules_pack.get('provenance_check', {}).get('unsupported_count', 0)}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
