#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_rewrite_pack import validate_rewrite_pack_payload


PRESETS = [
    {
        "name": "balanced",
        "profile_variant": "normal",
        "skills_variant": "normal",
        "extra_bullets": 0,
        "include_extra_project": False,
        "typography_preset": "normal",
    },
    {
        "name": "dense",
        "profile_variant": "dense",
        "skills_variant": "dense",
        "extra_bullets": 2,
        "include_extra_project": False,
        "typography_preset": "tight",
    },
    {
        "name": "expand_dense",
        "profile_variant": "dense",
        "skills_variant": "dense",
        "extra_bullets": 4,
        "include_extra_project": True,
        "typography_preset": "tight",
    },
]


def run_json_cmd(cmd: list[str]) -> dict[str, Any]:
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as exc:
        output = exc.output
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"Command did not produce JSON output: {' '.join(cmd)}\n{output}")
    return json.loads(output[start:end + 1])


def choose_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    def rank(item: dict[str, Any]) -> tuple[int, int, float, float, float]:
        qa = item["qa"]
        layout = qa.get("layout", {})
        return (
            1 if qa.get("status") == "pass" else 0,
            1 if layout.get("classification") == "balanced" else 0,
            float(qa.get("keyword_coverage", {}).get("ratio", 0.0)),
            -float(layout.get("bottom_whitespace_ratio") if layout.get("bottom_whitespace_ratio") is not None else 1.0),
            float(qa.get("score", 0.0)),
        )

    return max(candidates, key=rank)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and score multiple quality-mode candidates, then select the best one.")
    parser.add_argument("--bank-dir", type=Path, required=True, help="Evidence bank directory.")
    parser.add_argument("--artifacts-dir", type=Path, required=True, help="Artifacts directory containing job_card.json and rewrite artifacts.")
    parser.add_argument("--rewrite-pack", type=Path, required=True, help="Final grounded rewrite_pack.json.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory for final selected outputs.")
    parser.add_argument("--base-name", required=True, help="Base output name without extension.")
    args = parser.parse_args()

    rewrite_pack = json.loads(args.rewrite_pack.read_text(encoding="utf-8"))
    validation = validate_rewrite_pack_payload(rewrite_pack)
    validation_path = args.artifacts_dir / "rewrite_pack.validation.json"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    validation_path.write_text(json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if validation["status"] != "pass":
        print(json.dumps({"status": "fail", "validation": validation, "validation_path": str(validation_path)}, indent=2))
        return 1

    job_card_path = args.artifacts_dir / "job_card.json"
    if not job_card_path.exists():
        raise RuntimeError(f"Missing job_card.json in {args.artifacts_dir}")

    rewrite_used_path = args.artifacts_dir / "rewrite_pack.used.json"
    if args.rewrite_pack.resolve() != rewrite_used_path.resolve():
        shutil.copyfile(args.rewrite_pack, rewrite_used_path)

    candidate_root = args.artifacts_dir / "finalizer_candidates"
    candidate_root.mkdir(parents=True, exist_ok=True)

    candidates: list[dict[str, Any]] = []
    for preset in PRESETS:
        candidate_base = f"{args.base_name}_{preset['name']}"
        tex_path = candidate_root / f"{candidate_base}.tex"
        render_cmd = [
            "python3",
            str(Path(__file__).with_name("render_resume.py")),
            "--bank-dir",
            str(args.bank_dir),
            "--rewrite-pack",
            str(rewrite_used_path),
            "--output",
            str(tex_path),
            "--compile",
            "--profile-variant",
            preset["profile_variant"],
            "--skills-variant",
            preset["skills_variant"],
            "--extra-bullets",
            str(preset["extra_bullets"]),
            "--layout-mode",
            "dense" if preset["extra_bullets"] >= 2 else "balanced",
            "--typography-preset",
            preset["typography_preset"],
        ]
        if preset["include_extra_project"]:
            render_cmd.append("--include-extra-project")
        render_result = run_json_cmd(render_cmd)
        pdf_path = Path(render_result["pdf"])
        qa_result = run_json_cmd(
            [
                "python3",
                str(Path(__file__).with_name("quick_qa.py")),
                "--pdf",
                str(pdf_path),
                "--output-dir",
                str(candidate_root),
                "--base-name",
                candidate_base,
                "--job-card",
                str(job_card_path),
                "--unsupported-count",
                str(validation["unsupported_count"]),
            ]
        )
        candidates.append(
            {
                "preset": preset,
                "render": render_result,
                "qa": qa_result,
                "tex": str(tex_path),
                "pdf": str(pdf_path),
            }
        )

    best = choose_best_candidate(candidates)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    final_tex = args.output_dir / f"{args.base_name}.tex"
    final_pdf = args.output_dir / f"{args.base_name}.pdf"
    shutil.copyfile(best["tex"], final_tex)
    shutil.copyfile(best["pdf"], final_pdf)

    summary = {
        "status": "pass" if best["qa"].get("status") == "pass" else "warn",
        "rewrite_pack": str(args.rewrite_pack),
        "rewrite_pack_used": str(rewrite_used_path),
        "validation": validation,
        "selected_preset": best["preset"],
        "final_output": {
            "output_dir": str(args.output_dir),
            "base_name": args.base_name,
            "tex": str(final_tex),
            "pdf": str(final_pdf),
        },
        "candidate_runs": [
            {
                "name": item["preset"]["name"],
                "status": item["qa"].get("status"),
                "score": item["qa"].get("score"),
                "layout": item["qa"].get("layout"),
                "keyword_coverage": item["qa"].get("keyword_coverage"),
                "tex": item["tex"],
                "pdf": item["pdf"],
            }
            for item in candidates
        ],
    }
    summary_path = args.artifacts_dir / "finalize_quality_run.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if best["qa"].get("status") == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
