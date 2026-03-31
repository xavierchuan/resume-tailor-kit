#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from bank_runtime import load_structured


def _is_nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_line_item(item: Any, path: str, errors: list[str], warnings: list[str]) -> int:
    unsupported = 0
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object with text and provenance.")
        return 1
    text = item.get("text")
    provenance = item.get("provenance")
    if not _is_nonempty_text(text):
        errors.append(f"{path}.text must be a non-empty string.")
    if not isinstance(provenance, list):
        errors.append(f"{path}.provenance must be a list.")
        unsupported += 1
    elif not provenance:
        errors.append(f"{path}.provenance must be non-empty.")
        unsupported += 1
    if "source_type" not in item:
        warnings.append(f"{path}.source_type is missing.")
    return unsupported


def validate_link_item(item: Any, path: str, errors: list[str], warnings: list[str]) -> int:
    unsupported = 0
    if item is None:
        return 0
    if not isinstance(item, dict):
        errors.append(f"{path} must be an object when present.")
        return 1
    if not _is_nonempty_text(item.get("label")):
        errors.append(f"{path}.label must be a non-empty string.")
    if not _is_nonempty_text(item.get("url")):
        errors.append(f"{path}.url must be a non-empty string.")
    provenance = item.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        errors.append(f"{path}.provenance must be a non-empty list.")
        unsupported += 1
    if "source_type" not in item:
        warnings.append(f"{path}.source_type is missing.")
    return unsupported


def validate_project(project: Any, path: str, errors: list[str], warnings: list[str]) -> int:
    unsupported = 0
    if not isinstance(project, dict):
        errors.append(f"{path} must be an object.")
        return 1
    if not _is_nonempty_text(project.get("project_id")):
        errors.append(f"{path}.project_id must be a non-empty string.")
    unsupported += validate_line_item(project.get("title"), f"{path}.title", errors, warnings)
    stack = project.get("stack")
    if isinstance(stack, dict) and stack.get("text"):
        unsupported += validate_line_item(stack, f"{path}.stack", errors, warnings)
    elif stack not in (None, {}, ""):
        errors.append(f"{path}.stack must be omitted or be a line-item object.")
    unsupported += validate_link_item(project.get("link"), f"{path}.link", errors, warnings)

    bullets = project.get("bullets")
    if not isinstance(bullets, list) or not bullets:
        errors.append(f"{path}.bullets must be a non-empty list.")
    else:
        for index, item in enumerate(bullets):
            unsupported += validate_line_item(item, f"{path}.bullets[{index}]", errors, warnings)

    extra_bullets = project.get("extra_bullets", [])
    if not isinstance(extra_bullets, list):
        errors.append(f"{path}.extra_bullets must be a list when present.")
    else:
        for index, item in enumerate(extra_bullets):
            unsupported += validate_line_item(item, f"{path}.extra_bullets[{index}]", errors, warnings)
    return unsupported


def validate_rewrite_pack_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    unsupported_count = 0

    role = payload.get("role")
    if not isinstance(role, dict):
        errors.append("role must be an object.")
    else:
        for key in ["company", "role", "family"]:
            if not _is_nonempty_text(role.get(key)):
                errors.append(f"role.{key} must be a non-empty string.")
        if not _is_nonempty_text(role.get("archetype")):
            warnings.append("role.archetype is missing.")

    coverage_terms = payload.get("coverage_terms")
    if not isinstance(coverage_terms, list) or not all(_is_nonempty_text(term) for term in coverage_terms):
        errors.append("coverage_terms must be a non-empty list of strings.")

    profile = payload.get("profile")
    if not isinstance(profile, dict):
        errors.append("profile must be an object.")
    else:
        for key in ["short", "normal", "dense"]:
            bucket = profile.get(key)
            if not isinstance(bucket, list) or not bucket:
                errors.append(f"profile.{key} must be a non-empty list.")
                continue
            for index, item in enumerate(bucket):
                unsupported_count += validate_line_item(item, f"profile.{key}[{index}]", errors, warnings)

    skills = payload.get("skills")
    if not isinstance(skills, dict):
        errors.append("skills must be an object.")
    else:
        for key in ["normal", "dense"]:
            bucket = skills.get(key)
            if not isinstance(bucket, list) or not bucket:
                errors.append(f"skills.{key} must be a non-empty list.")
                continue
            for index, item in enumerate(bucket):
                unsupported_count += validate_line_item(item, f"skills.{key}[{index}]", errors, warnings)

    projects = payload.get("projects")
    if not isinstance(projects, list) or not projects:
        errors.append("projects must be a non-empty list.")
    else:
        for index, project in enumerate(projects):
            unsupported_count += validate_project(project, f"projects[{index}]", errors, warnings)

    extra_projects = payload.get("extra_projects", [])
    if not isinstance(extra_projects, list):
        errors.append("extra_projects must be a list when present.")
    else:
        for index, project in enumerate(extra_projects):
            unsupported_count += validate_project(project, f"extra_projects[{index}]", errors, warnings)

    declared_unsupported = payload.get("unsupported_count")
    if declared_unsupported is not None and declared_unsupported != unsupported_count:
        warnings.append(
            f"unsupported_count mismatch: declared {declared_unsupported}, computed {unsupported_count}."
        )

    provenance_check = payload.get("provenance_check", {})
    if isinstance(provenance_check, dict):
        declared = provenance_check.get("unsupported_count")
        if declared is not None and declared != unsupported_count:
            warnings.append(
                f"provenance_check.unsupported_count mismatch: declared {declared}, computed {unsupported_count}."
            )

    return {
        "status": "pass" if not errors and unsupported_count == 0 else "fail",
        "errors": errors,
        "warnings": warnings,
        "unsupported_count": unsupported_count,
        "project_count": len(projects) if isinstance(projects, list) else 0,
        "extra_project_count": len(extra_projects) if isinstance(extra_projects, list) else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rewrite_pack.json structure and provenance contract.")
    parser.add_argument("--rewrite-pack", type=Path, required=True, help="Path to rewrite_pack.json.")
    parser.add_argument("--output", type=Path, help="Optional path to write validation result JSON.")
    args = parser.parse_args()

    payload = load_structured(args.rewrite_pack)
    result = validate_rewrite_pack_payload(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
