#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bank_runtime import load_structured, resolve_runtime_bank
from routing import get_archetype_config, tokenize_loose


STOPWORDS = {
    "and", "the", "with", "for", "from", "into", "that", "this", "your", "will", "have", "you",
    "our", "are", "using", "work", "role", "data", "engineer", "engineering", "software", "junior",
    "experience", "strong", "workflows", "working", "build", "built", "deliver", "delivery", "team",
    "teams", "systems", "system", "application", "applications", "skills", "knowledge", "good", "great",
    "required", "requirements", "preferred", "plus", "related", "degree", "ability", "support", "would",
    "what", "bring", "need", "must", "based", "across", "through", "more", "than", "under", "into",
    "their", "them", "they", "within", "also", "such", "new", "real", "world", "production", "grade",
}
KEEP_SHORT = {"sql", "api", "llm", "rag", "etl", "c++", "ml", "ai", "bi"}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def tokens(text: str) -> list[str]:
    found = re.findall(r"[a-z0-9][a-z0-9+_-]*", text.lower())
    out = []
    for token in found:
        if token in STOPWORDS:
            continue
        if len(token) < 4 and token not in KEEP_SHORT:
            continue
        out.append(token)
    return out


def unique_by_text(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = normalize_text(item.get("text", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def text_overlap_score(
    text: str,
    terms: list[str],
    source_tokens: list[str] | None = None,
    source_role_tokens: list[str] | None = None,
    role_focus_tokens: set[str] | None = None,
) -> float:
    text_tokens = set(tokens(text))
    term_set = set(terms)
    overlap = len(text_tokens & term_set)
    score = overlap * 3.0
    if source_tokens:
        score += len(set(source_tokens) & term_set)
    if source_role_tokens and role_focus_tokens:
        score += 1.5 * len(set(source_role_tokens) & role_focus_tokens)
    lower = text.lower()
    if any(term in lower for term in ["validate", "validation", "schema", "monitor", "pipeline", "sql", "python", "agent", "automation"]):
        score += 1.0
    if len(text) > 180:
        score -= 0.5
    return score


def derive_terms(job_card: dict[str, Any]) -> list[str]:
    raw_parts = []
    raw_parts.extend(job_card.get("must_have", []))
    raw_parts.extend(job_card.get("nice_to_have", []))
    raw_parts.extend(job_card.get("domain_keywords", []))
    raw_parts.append(job_card.get("role", ""))
    raw_parts.append(job_card.get("company", ""))
    found: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        for token in tokens(str(part)):
            if token in seen:
                continue
            seen.add(token)
            found.append(token)
    return found[:24]


def derive_must_preserve_terms(job_card: dict[str, Any], archetype_config: dict[str, Any], coverage_terms: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for source in [archetype_config.get("must_preserve_terms", []), coverage_terms, job_card.get("domain_keywords", [])]:
        for part in source:
            for token in tokenize_loose(str(part)):
                key = token.lower()
                if key in seen:
                    continue
                seen.add(key)
                found.append(key)
    return found[:12]


def item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text", "")).strip()
    return str(item).strip()


def annotate_item(
    *,
    text: str,
    provenance: list[str],
    source_type: str,
    source_tokens: list[str] | None = None,
    source_role_tokens: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "text": text.strip(),
        "provenance": provenance,
        "source_type": source_type,
        "source_tokens": source_tokens or [],
        "source_role_tokens": source_role_tokens or [],
    }
    if extra:
        item.update(extra)
    return item


def candidate_profile_lines(selected: dict[str, Any], variant_bank: dict[str, Any]) -> list[dict[str, Any]]:
    lines = []
    for idx, text in enumerate(selected.get("profile_lines", [])):
        lines.append(
            annotate_item(
                text=text,
                provenance=[f"selected:profile:{idx}"],
                source_type="selected",
            )
        )
    for item in variant_bank.get("profiles", []):
        text = item.get("text", "")
        if any(bad in text.lower() for bad in ["founding", "senior", "lead", "manager", "director", "5+ years", "3+ years"]):
            continue
        lines.append(
            annotate_item(
                text=text,
                provenance=[f"variant:{item.get('source')}"],
                source_type=item.get("source_type", "variant"),
                source_tokens=item.get("source_tokens", []),
                source_role_tokens=item.get("source_role_tokens", []),
            )
        )
    return unique_by_text(lines)


def candidate_skill_lines(selected: dict[str, Any], bank_dir: Path, variant_bank: dict[str, Any]) -> list[dict[str, Any]]:
    skills_blocks = load_structured(bank_dir / "skills_blocks.yaml")
    selected_block = selected.get("skills_block_id")
    lines = []
    for block in skills_blocks.get("blocks", []):
        if block.get("id") != selected_block:
            continue
        for idx, item in enumerate(block.get("items", [])):
            lines.append(
                annotate_item(
                    text=item,
                    provenance=[f"skills_block:{selected_block}:{idx}"],
                    source_type="selected",
                )
            )
    for item in variant_bank.get("skills_lines", []):
        text = item.get("text", "")
        if len(text) > 140:
            continue
        lines.append(
            annotate_item(
                text=text,
                provenance=[f"variant:{item.get('source')}"],
                source_type=item.get("source_type", "variant"),
                source_tokens=item.get("source_tokens", []),
                source_role_tokens=item.get("source_role_tokens", []),
            )
        )
    return unique_by_text(lines)


def load_bullet_map(bank_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    bullet_library = load_structured(bank_dir / "bullet_library.yaml")
    bullets = bullet_library.get("bullets", [])
    by_id = {bullet["id"]: bullet for bullet in bullets if "id" in bullet}
    text_to_id = {
        normalize_text(bullet["text"]): bullet["id"]
        for bullet in bullets
        if "text" in bullet and "id" in bullet
    }
    return by_id, text_to_id


def project_defaults(project_id: str, project_bank: dict[str, Any]) -> dict[str, Any]:
    project = project_bank.get("projects", {}).get(project_id, {})
    link = project.get("link", {})
    if not isinstance(link, dict):
        link = {}
    title = project.get("display_title") or project.get("name") or project_id.replace("_", " ").title()
    stack = project.get("stack", "")
    link_label = link.get("label", "")
    link_url = link.get("url", "")
    return {
        "title": annotate_item(text=title, provenance=[f"default_title:{project_id}"], source_type="bank"),
        "stack": annotate_item(text=stack, provenance=[f"default_stack:{project_id}"], source_type="bank") if stack else {"text": "", "provenance": [], "source_type": "bank"},
        "link": {
            "label": link_label,
            "url": link_url,
            "provenance": [f"default_link:{project_id}"],
            "source_type": "bank",
        }
        if link_label and link_url
        else None,
    }


def project_candidates(project_id: str, selected_ids: list[str], bank_dir: Path, variant_bank: dict[str, Any]) -> dict[str, Any]:
    project_evidence = load_structured(bank_dir / "project_evidence.yaml")
    bullet_by_id, text_to_id = load_bullet_map(bank_dir)
    defaults = project_defaults(project_id, project_evidence)
    title_candidates = [defaults["title"]]
    stack_candidates = [defaults["stack"]] if defaults["stack"]["text"] else []
    link_candidates = [defaults["link"]] if defaults["link"] else []
    bullet_candidates: list[dict[str, Any]] = []

    project_bucket = variant_bank.get("project_variants", {}).get(project_id, {})
    for item in project_bucket.get("title_variants", []):
        title_candidates.append(
            annotate_item(
                text=item["text"],
                provenance=[f"variant:{item['source']}"],
                source_type=item.get("source_type", "variant"),
                source_tokens=item.get("source_tokens", []),
                source_role_tokens=item.get("source_role_tokens", []),
            )
        )
    for item in project_bucket.get("stack_variants", []):
        stack_candidates.append(
            annotate_item(
                text=item["text"],
                provenance=[f"variant:{item['source']}"],
                source_type=item.get("source_type", "variant"),
                source_tokens=item.get("source_tokens", []),
                source_role_tokens=item.get("source_role_tokens", []),
            )
        )
    for item in project_bucket.get("link_variants", []):
        link_candidates.append(
            {
                "label": item.get("label", ""),
                "url": item.get("url", ""),
                "provenance": [f"variant:{item['source']}"],
                "source_type": item.get("source_type", "variant"),
                "source_tokens": item.get("source_tokens", []),
                "source_role_tokens": item.get("source_role_tokens", []),
            }
        )
    for bullet_id in selected_ids:
        bullet = bullet_by_id.get(bullet_id)
        if not bullet:
            continue
        bullet_candidates.append(
            annotate_item(
                text=bullet["text"],
                provenance=[f"bullet:{bullet_id}"] + [f"evidence:{ref}" for ref in bullet.get("evidence_refs", [])],
                source_type="selected",
                source_tokens=bullet.get("tags", []),
            )
        )
    for bullet in bullet_by_id.values():
        if bullet.get("project_id") != project_id or bullet["id"] in selected_ids:
            continue
        bullet_candidates.append(
            annotate_item(
                text=bullet["text"],
                provenance=[f"bullet:{bullet['id']}"] + [f"evidence:{ref}" for ref in bullet.get("evidence_refs", [])],
                source_type="bank",
                source_tokens=bullet.get("tags", []),
            )
        )
    for item in project_bucket.get("bullet_variants", []):
        normalized = normalize_text(item["text"])
        provenance = [f"variant:{item['source']}"]
        if normalized in text_to_id:
            provenance.insert(0, f"bullet:{text_to_id[normalized]}")
        bullet_candidates.append(
            annotate_item(
                text=item["text"],
                provenance=provenance,
                source_type=item.get("source_type", "variant"),
                source_tokens=item.get("source_tokens", []),
                source_role_tokens=item.get("source_role_tokens", []),
            )
        )

    return {
        "title_candidates": unique_by_text(title_candidates),
        "stack_candidates": unique_by_text(stack_candidates),
        "link_candidates": [candidate for candidate in link_candidates if candidate.get("label") and candidate.get("url")],
        "bullet_candidates": unique_by_text(bullet_candidates),
        "default_link": defaults["link"],
    }


def choose_top(items: list[dict[str, Any]], terms: list[str], limit: int, role_focus_tokens: set[str]) -> list[dict[str, Any]]:
    ranked = sorted(
        items,
        key=lambda item: (
            text_overlap_score(
                item["text"],
                terms,
                item.get("source_tokens"),
                item.get("source_role_tokens"),
                role_focus_tokens,
            ),
            len(item.get("text", "")),
        ),
        reverse=True,
    )
    return ranked[:limit]


def choose_with_default_bias(items: list[dict[str, Any]], terms: list[str], role_focus_tokens: set[str], bias: float = 2.0) -> dict[str, Any]:
    if not items:
        return {"text": "", "provenance": [], "source_type": "bank"}
    default = items[0]
    best = max(
        items,
        key=lambda item: text_overlap_score(
            item["text"],
            terms,
            item.get("source_tokens"),
            item.get("source_role_tokens"),
            role_focus_tokens,
        ),
    )
    default_score = text_overlap_score(
        default["text"],
        terms,
        default.get("source_tokens"),
        default.get("source_role_tokens"),
        role_focus_tokens,
    ) + bias
    best_score = text_overlap_score(
        best["text"],
        terms,
        best.get("source_tokens"),
        best.get("source_role_tokens"),
        role_focus_tokens,
    )
    return default if default_score >= best_score else best


def choose_link_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for candidate in candidates:
        if candidate.get("label") and candidate.get("url"):
            return candidate
    return None


def provenance_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    with_provenance = 0
    for item in items:
        source_type = item.get("source_type", "unknown")
        counts[source_type] = counts.get(source_type, 0) + 1
        if item.get("provenance"):
            with_provenance += 1
    return {
        "source_type_counts": counts,
        "with_provenance": with_provenance,
        "total_items": len(items),
    }


def build_rewrite_artifacts(
    job_card: dict[str, Any],
    selected: dict[str, Any],
    bank_dir: Path,
    variant_bank: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime_bank_dir = resolve_runtime_bank(bank_dir)
    project_bank = load_structured(runtime_bank_dir / "project_evidence.yaml")
    archetype = job_card.get("archetype") or job_card.get("family", "software")
    archetype_config = get_archetype_config(archetype, family=job_card.get("family", "software"))
    coverage_terms = derive_terms(job_card)
    must_preserve_terms = derive_must_preserve_terms(job_card, archetype_config, coverage_terms)
    avoid_terms = list(archetype_config.get("avoid_terms", []))
    target_tone = archetype_config.get("target_tone", "grounded, concise, role-specific")
    target_density = archetype_config.get("target_density", "balanced")
    role_focus_tokens = set(tokens(" ".join(archetype_config.get("terms", []))))

    profile_candidates = candidate_profile_lines(selected, variant_bank)
    skills_candidates = candidate_skill_lines(selected, runtime_bank_dir, variant_bank)

    ranked_profiles = choose_top(profile_candidates, coverage_terms, 12, role_focus_tokens)
    ranked_skills = choose_top(skills_candidates, coverage_terms, 12, role_focus_tokens)

    selected_project_ids = []
    seed_projects = []
    rules_projects = []
    for section in selected.get("project_sections", []):
        project_id = section["project_id"]
        selected_project_ids.append(project_id)
        candidates = project_candidates(project_id, section.get("bullet_ids", []), runtime_bank_dir, variant_bank)
        preferred_title = choose_with_default_bias(candidates["title_candidates"], coverage_terms, role_focus_tokens, bias=2.5)
        preferred_stack = (
            choose_with_default_bias(candidates["stack_candidates"], coverage_terms, role_focus_tokens, bias=1.0)
            if candidates["stack_candidates"]
            else {"text": "", "provenance": [], "source_type": "bank"}
        )
        preferred_link = choose_link_candidate(candidates["link_candidates"]) or candidates["default_link"]
        ranked_bullets = choose_top(candidates["bullet_candidates"], coverage_terms, 10, role_focus_tokens)
        primary_bullets = ranked_bullets[:4]
        reserve_bullets = ranked_bullets[4:8]
        seed_projects.append(
            {
                "project_id": project_id,
                "preferred_title_candidate": preferred_title,
                "preferred_stack_candidate": preferred_stack,
                "preferred_link_candidate": preferred_link,
                "title_candidates": candidates["title_candidates"][:6],
                "stack_candidates": candidates["stack_candidates"][:4],
                "link_candidates": candidates["link_candidates"][:3],
                "primary_bullets": primary_bullets,
                "reserve_bullets": reserve_bullets,
                "bullet_candidates": ranked_bullets,
                "provenance_summary": provenance_summary(primary_bullets + reserve_bullets),
            }
        )
        rules_projects.append(
            {
                "project_id": project_id,
                "title": preferred_title,
                "stack": preferred_stack,
                "link": preferred_link,
                "bullets": primary_bullets,
                "extra_bullets": reserve_bullets,
                "provenance_summary": provenance_summary(primary_bullets + reserve_bullets),
            }
        )

    extra_projects = []
    for project_id in project_bank.get("projects", {}).keys():
        if project_id in selected_project_ids:
            continue
        candidates = project_candidates(project_id, [], runtime_bank_dir, variant_bank)
        ranked_bullets = choose_top(candidates["bullet_candidates"], coverage_terms, 6, role_focus_tokens)
        if len(ranked_bullets) < 2:
            continue
        title = choose_with_default_bias(candidates["title_candidates"], coverage_terms, role_focus_tokens, bias=2.5)
        stack = (
            choose_with_default_bias(candidates["stack_candidates"], coverage_terms, role_focus_tokens, bias=1.0)
            if candidates["stack_candidates"]
            else {"text": "", "provenance": [], "source_type": "bank"}
        )
        link = choose_link_candidate(candidates["link_candidates"]) or candidates["default_link"]
        primary_bullets = ranked_bullets[:3]
        reserve_bullets = ranked_bullets[3:6]
        extra_projects.append(
            {
                "project_id": project_id,
                "title": title,
                "stack": stack,
                "link": link,
                "bullets": primary_bullets,
                "extra_bullets": reserve_bullets,
                "provenance_summary": provenance_summary(primary_bullets + reserve_bullets),
            }
        )
    extra_projects = sorted(
        extra_projects,
        key=lambda project: text_overlap_score(
            project["title"]["text"],
            coverage_terms,
            project["title"].get("source_tokens"),
            project["title"].get("source_role_tokens"),
            role_focus_tokens,
        ),
        reverse=True,
    )[:2]

    seed = {
        "job_card": job_card,
        "coverage_terms": coverage_terms,
        "must_preserve_terms": must_preserve_terms,
        "avoid_terms": avoid_terms,
        "target_tone": target_tone,
        "target_density": target_density,
        "profile_candidates": ranked_profiles,
        "skills_candidates": ranked_skills,
        "projects": seed_projects,
        "extra_projects": extra_projects,
        "instructions": {
            "constraints": [
                "Only use evidenced facts already present in the candidate bank or external historical CV corpus.",
                "Do not add tools, metrics, ownership, or experience not supported by provenance.",
                "Rewrite for this JD using specific wording, not generic summaries.",
                "Aim for a one-page CV with balanced density and minimal bottom whitespace.",
            ],
            "process": [
                "Prefer the preferred title/stack/link candidates unless another candidate is clearly better supported and more role-specific.",
                "Use primary bullets first; draw from reserve bullets only when you need more density or better keyword coverage.",
                "Preserve must_preserve_terms where they are truthful and relevant.",
                "Avoid drifting into the avoid_terms framing.",
            ],
        },
    }

    profile_short = ranked_profiles[:2]
    profile_normal = ranked_profiles[:3]
    profile_dense = ranked_profiles[:4]
    skills_normal = ranked_skills[:4]
    skills_dense = ranked_skills[:6]

    rules_pack = {
        "role": {
            "company": job_card.get("company"),
            "role": job_card.get("role"),
            "family": job_card.get("family"),
            "archetype": archetype,
        },
        "coverage_terms": coverage_terms,
        "must_preserve_terms": must_preserve_terms,
        "avoid_terms": avoid_terms,
        "target_tone": target_tone,
        "target_density": target_density,
        "profile": {
            "short": profile_short,
            "normal": profile_normal,
            "dense": profile_dense,
        },
        "skills": {
            "normal": skills_normal,
            "dense": skills_dense,
        },
        "projects": rules_projects,
        "extra_projects": extra_projects,
        "density_hints": {
            "preferred_layout_mode": "dense" if target_density == "dense" else "balanced",
            "preferred_typography": "tight" if target_density == "dense" else "normal",
            "candidate_extra_bullets": [0, 2, 4],
            "target_density": target_density,
        },
    }

    unsupported = 0
    for bucket in [profile_dense, skills_dense]:
        unsupported += sum(1 for item in bucket if not item.get("provenance"))
    for project in rules_projects + extra_projects:
        if not project.get("title", {}).get("provenance"):
            unsupported += 1
        if project.get("stack", {}).get("text") and not project.get("stack", {}).get("provenance"):
            unsupported += 1
        link = project.get("link")
        if link and not link.get("provenance"):
            unsupported += 1
        unsupported += sum(1 for item in project.get("bullets", []) if not item.get("provenance"))
        unsupported += sum(1 for item in project.get("extra_bullets", []) if not item.get("provenance"))
    rules_pack["provenance_check"] = {"unsupported_count": unsupported}
    rules_pack["unsupported_count"] = unsupported
    return seed, rules_pack


def main() -> int:
    parser = argparse.ArgumentParser(description="Build rewrite seed and rules-based rewrite pack from selected evidence.")
    parser.add_argument("--job-card", type=Path, required=True, help="Path to job_card.json")
    parser.add_argument("--selected", type=Path, required=True, help="Path to selected.json")
    parser.add_argument("--bank-dir", type=Path, default=Path("bank"), help="Candidate bank directory")
    parser.add_argument("--variant-bank", type=Path, required=True, help="Path to variant_bank.json")
    parser.add_argument("--seed-output", type=Path, required=True, help="Output path for rewrite_seed.json")
    parser.add_argument("--rules-output", type=Path, required=True, help="Output path for rewrite_pack.rules.json")
    args = parser.parse_args()

    job_card = json.loads(args.job_card.read_text(encoding="utf-8"))
    selected = json.loads(args.selected.read_text(encoding="utf-8"))
    variant_bank = json.loads(args.variant_bank.read_text(encoding="utf-8"))

    seed, rules_pack = build_rewrite_artifacts(job_card, selected, args.bank_dir, variant_bank)
    args.seed_output.parent.mkdir(parents=True, exist_ok=True)
    args.rules_output.parent.mkdir(parents=True, exist_ok=True)
    args.seed_output.write_text(json.dumps(seed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.rules_output.write_text(json.dumps(rules_pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "pass",
                "seed_output": str(args.seed_output),
                "rules_output": str(args.rules_output),
                "coverage_terms": seed["coverage_terms"],
                "archetype": job_card.get("archetype"),
                "unsupported_count": rules_pack["unsupported_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
