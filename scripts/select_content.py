#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bank_runtime import load_structured, resolve_runtime_bank
from routing import get_archetype_config, project_bullet_targets_for_archetype


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9+]+", "-", text.lower()).strip("-")


def family_to_profile_keys(family: str, archetype: str) -> list[str]:
    keys = []
    for candidate in [archetype, family, "software"]:
        if candidate and candidate not in keys:
            keys.append(candidate)
    return keys


def choose_template(job_card: dict[str, Any], registry: dict[str, Any]) -> str:
    archetype = job_card.get("archetype", "")
    family = job_card["family"]
    domain = set(job_card.get("domain_keywords", []))
    templates = registry.get("templates", {})
    defaults = registry.get("routing_defaults", {})
    templates_by_archetype = registry.get("templates_by_archetype", {})

    if archetype in templates_by_archetype:
        return templates_by_archetype[archetype]
    if family == "quant" and {"etf", "leveraged-etf"} & domain:
        return templates.get("quant_etf", "CV/quant_etf_leveraged.tex")
    if family == "quant":
        return templates.get("quant", "CV/quant.tex")
    if family == "ai":
        return templates.get("ai", "CV/AI Engineering.tex")
    if family in {"data", "software"}:
        return templates.get("software", "CV/software developer.tex")
    return defaults.get("fallback", "CV/software developer.tex")


def choose_skills_block(job_card: dict[str, Any], skills_blocks: dict[str, Any]) -> str:
    family = job_card["family"]
    archetype = job_card.get("archetype", "")
    domain = set(job_card.get("domain_keywords", []))
    blocks = skills_blocks.get("blocks", [])

    for block in blocks:
        archetypes = set(block.get("archetypes", []))
        required_tags = set(block.get("required_domain_tags", []))
        if archetypes and archetype not in archetypes:
            continue
        if required_tags and not required_tags.issubset(domain):
            continue
        if archetypes:
            return block["id"]

    for block in blocks:
        families = set(block.get("families", []))
        required_tags = set(block.get("required_domain_tags", []))
        if family not in families:
            continue
        if required_tags and not required_tags.issubset(domain):
            continue
        return block["id"]

    return skills_blocks.get("fallback_block_id", "software_core_v1")


def gather_evidence_ids(project_evidence: dict[str, Any]) -> dict[str, set[str]]:
    projects = project_evidence.get("projects", {})
    out: dict[str, set[str]] = {}
    for project_id, payload in projects.items():
        facts = payload.get("facts", {})
        out[project_id] = set(facts.keys())
    return out


def extract_tokens(items: list[str]) -> set[str]:
    tokens: set[str] = set()
    for item in items:
        for token in re.split(r"[^a-zA-Z0-9+]+", item.lower()):
            if len(token) >= 3:
                tokens.add(token)
    return tokens


def score_bullet(
    bullet: dict[str, Any],
    family: str,
    domain_keywords: set[str],
    must_tokens: set[str],
    preferred_tags: set[str],
) -> int:
    score = 0
    families = set(bullet.get("families", []))
    tags = {normalize_token(tag) for tag in bullet.get("tags", [])}
    text = bullet.get("text", "").lower()

    if family in families or "all" in families:
        score += 5
    overlap = tags & domain_keywords
    score += 2 * len(overlap)
    score += 2 * len(tags & preferred_tags)
    score += sum(1 for token in must_tokens if token and token in text)
    score += sum(1 for token in preferred_tags if token and token in text)
    score += int(bullet.get("priority", 0))
    return score


def score_project(
    project_id: str,
    bullets: list[dict[str, Any]],
    family: str,
    domain_keywords: set[str],
    must_tokens: set[str],
    preferred_tags: set[str],
) -> int:
    candidates = [bullet for bullet in bullets if bullet.get("project_id") == project_id]
    if not candidates:
        return -1
    ranked = sorted(
        (
            score_bullet(
                bullet,
                family=family,
                domain_keywords=domain_keywords,
                must_tokens=must_tokens,
                preferred_tags=preferred_tags,
            )
            for bullet in candidates
        ),
        reverse=True,
    )
    return sum(ranked[:3])


def choose_project_order(
    base_template: str,
    profile: dict[str, Any],
    project_ids: list[str],
    bullets: list[dict[str, Any]],
    family: str,
    archetype: str,
    domain_keywords: set[str],
    must_tokens: set[str],
    preferred_tags: set[str],
) -> list[str]:
    mapping = profile.get("project_orders", {})
    archetype_mapping = profile.get("project_orders_by_archetype", {})
    key = Path(base_template).name
    stem_key = Path(base_template).stem
    preferred = (
        archetype_mapping.get(archetype)
        or mapping.get(archetype)
        or mapping.get(key)
        or mapping.get(stem_key)
        or mapping.get("default", [])
    )
    order_index = {project_id: index for index, project_id in enumerate(preferred)}
    full_project_ids = []
    for project_id in preferred + project_ids:
        if project_id not in full_project_ids:
            full_project_ids.append(project_id)
    return sorted(
        full_project_ids,
        key=lambda project_id: (
            score_project(
                project_id,
                bullets=bullets,
                family=family,
                domain_keywords=domain_keywords,
                must_tokens=must_tokens,
                preferred_tags=preferred_tags,
            ),
            -order_index.get(project_id, 999),
        ),
        reverse=True,
    )


def choose_profile_lines(candidate_profile: dict[str, Any], family: str, archetype: str) -> tuple[list[str], str]:
    profile_snippets = candidate_profile.get("profile_snippets", {})
    profile_snippets_by_archetype = candidate_profile.get("profile_snippets_by_archetype", {})
    for key in family_to_profile_keys(family, archetype):
        lines = profile_snippets_by_archetype.get(key) or profile_snippets.get(key)
        if lines:
            return list(lines), key
    return list(profile_snippets.get("software", [])), "software"


def select_bullets_for_project(
    project_id: str,
    bullets: list[dict[str, Any]],
    family: str,
    domain_keywords: set[str],
    must_tokens: set[str],
    preferred_tags: set[str],
    target_count: int,
) -> list[str]:
    candidates = [bullet for bullet in bullets if bullet.get("project_id") == project_id]
    ranked = sorted(
        candidates,
        key=lambda bullet: score_bullet(
            bullet,
            family=family,
            domain_keywords=domain_keywords,
            must_tokens=must_tokens,
            preferred_tags=preferred_tags,
        ),
        reverse=True,
    )
    return [bullet["id"] for bullet in ranked[:target_count]]


def select_content_payload(job_card: dict[str, Any], bank_dir: Path) -> dict[str, Any]:
    bank_dir = resolve_runtime_bank(bank_dir)
    candidate_profile = load_structured(bank_dir / "candidate_profile.yaml")
    project_evidence = load_structured(bank_dir / "project_evidence.yaml")
    bullet_library = load_structured(bank_dir / "bullet_library.yaml")
    skills_blocks = load_structured(bank_dir / "skills_blocks.yaml")
    template_registry = load_structured(bank_dir / "template_registry.yaml")

    family = job_card.get("family", "software")
    archetype = job_card.get("archetype") or family
    archetype_config = get_archetype_config(archetype, family=family)
    domain_keywords = {normalize_token(token) for token in job_card.get("domain_keywords", [])}
    must_tokens = extract_tokens(job_card.get("must_have", []))
    preferred_tags = {normalize_token(tag) for tag in archetype_config.get("preferred_tags", [])}

    base_template = choose_template(job_card, template_registry)
    skills_block_id = choose_skills_block(job_card, skills_blocks)
    profile_lines, profile_key = choose_profile_lines(candidate_profile, family=family, archetype=archetype)

    bullets = bullet_library.get("bullets", [])
    bullet_by_id = {bullet["id"]: bullet for bullet in bullets if "id" in bullet}
    project_ids = list(project_evidence.get("projects", {}).keys())
    ranked_project_ids = choose_project_order(
        base_template=base_template,
        profile=candidate_profile,
        project_ids=project_ids,
        bullets=bullets,
        family=family,
        archetype=archetype,
        domain_keywords=domain_keywords,
        must_tokens=must_tokens,
        preferred_tags=preferred_tags,
    )
    count_targets = project_bullet_targets_for_archetype(
        archetype,
        fallback=list(candidate_profile.get("project_bullet_targets", [8, 4, 3])),
    )

    evidence_ids_by_project = gather_evidence_ids(project_evidence)
    selected_sections: list[dict[str, Any]] = []
    unsupported_count = 0
    selected_project_ids = set()

    for index, project_id in enumerate(ranked_project_ids):
        if len(selected_sections) >= 3:
            break
        target_count = count_targets[index] if index < len(count_targets) else count_targets[-1]
        bullet_ids = select_bullets_for_project(
            project_id=project_id,
            bullets=bullets,
            family=family,
            domain_keywords=domain_keywords,
            must_tokens=must_tokens,
            preferred_tags=preferred_tags,
            target_count=target_count,
        )
        if not bullet_ids:
            continue

        verified_ids: list[str] = []
        project_fact_ids = evidence_ids_by_project.get(project_id, set())
        for bullet_id in bullet_ids:
            bullet = bullet_by_id.get(bullet_id)
            if not bullet:
                unsupported_count += 1
                continue
            refs = bullet.get("evidence_refs", [])
            if not refs or any(ref not in project_fact_ids for ref in refs):
                unsupported_count += 1
                continue
            verified_ids.append(bullet_id)

        if verified_ids:
            selected_sections.append({"project_id": project_id, "bullet_ids": verified_ids})
            selected_project_ids.add(project_id)

    fallback_projects = [project_id for project_id in ranked_project_ids if project_id not in selected_project_ids]
    for project_id in fallback_projects:
        if len(selected_sections) >= 3:
            break
        bullet_ids = select_bullets_for_project(
            project_id=project_id,
            bullets=bullets,
            family=family,
            domain_keywords=domain_keywords,
            must_tokens=must_tokens,
            preferred_tags=preferred_tags,
            target_count=2,
        )
        if bullet_ids:
            selected_sections.append({"project_id": project_id, "bullet_ids": bullet_ids[:2]})

    return {
        "base_template": base_template,
        "profile_lines": profile_lines,
        "skills_block_id": skills_block_id,
        "project_sections": selected_sections,
        "routing": {
            "family": family,
            "archetype": archetype,
            "profile_key": profile_key,
            "project_bullet_targets": count_targets,
        },
        "claims_check": {"unsupported_count": unsupported_count},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Select template/profile/project bullets from central evidence bank.")
    parser.add_argument("--job-card", type=Path, required=True, help="Path to job card JSON.")
    parser.add_argument("--bank-dir", type=Path, default=Path("bank"), help="Path to evidence bank directory.")
    parser.add_argument("--output", type=Path, help="Write selected content JSON.")
    args = parser.parse_args()

    job_card = load_structured(args.job_card)
    selected = select_content_payload(job_card=job_card, bank_dir=args.bank_dir)

    payload = json.dumps(selected, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
