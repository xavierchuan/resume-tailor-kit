#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


LEGACY_BANK_FILES = (
    "candidate_profile.yaml",
    "project_evidence.yaml",
    "bullet_library.yaml",
    "skills_blocks.yaml",
    "template_registry.yaml",
)

MARKDOWN_BANK_ROOT_FILES = (
    "profile.md",
    "skills.md",
    "templates.md",
)

MARKDOWN_BANK_DIRS = ("stories", "evidence")
PLACEHOLDER_MARKER = "REPLACE_ME"


def require_yaml():
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "PyYAML is required for markdown-bank compilation. Install it with `python3 -m pip install pyyaml`."
        ) from exc
    return yaml


def load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        yaml = require_yaml()
        data = yaml.safe_load(text)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RuntimeError(f"{path} must contain a top-level mapping/dictionary.")
    return data


def is_legacy_bank_dir(bank_dir: Path) -> bool:
    return all((bank_dir / name).exists() for name in LEGACY_BANK_FILES)


def is_markdown_bank_dir(bank_dir: Path) -> bool:
    return all((bank_dir / name).exists() for name in MARKDOWN_BANK_ROOT_FILES) and all(
        (bank_dir / name).is_dir() for name in MARKDOWN_BANK_DIRS
    )


def iter_bank_files(bank_dir: Path) -> list[Path]:
    if is_legacy_bank_dir(bank_dir):
        return [bank_dir / name for name in LEGACY_BANK_FILES]
    if is_markdown_bank_dir(bank_dir):
        files = [bank_dir / name for name in MARKDOWN_BANK_ROOT_FILES]
        for folder in MARKDOWN_BANK_DIRS:
            files.extend(sorted((bank_dir / folder).glob("*.md")))
        return files
    return []


def compute_bank_signature(bank_dir: Path) -> str:
    hasher = hashlib.sha256()
    files = iter_bank_files(bank_dir)
    if not files:
        raise RuntimeError(
            f"{bank_dir} is not a supported bank directory. Expected legacy YAML files or markdown-bank files."
        )
    for file in files:
        hasher.update(str(file.relative_to(bank_dir)).encode("utf-8"))
        hasher.update(file.read_bytes())
    return hasher.hexdigest()


def parse_markdown_document(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise RuntimeError(f"{path} must start with YAML frontmatter.")
    rest = text[4:]
    frontmatter_text, sep, body = rest.partition("\n---\n")
    if not sep:
        raise RuntimeError(f"{path} is missing the closing YAML frontmatter delimiter.")
    yaml = require_yaml()
    frontmatter = yaml.safe_load(frontmatter_text) or {}
    if not isinstance(frontmatter, dict):
        raise RuntimeError(f"{path} frontmatter must be a top-level mapping/dictionary.")
    return frontmatter, body.strip()


def normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [normalize_line(str(item)) for item in value if normalize_line(str(item))]
    return []


def parse_profile_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = slugify(line[3:])
            sections.setdefault(current, [])
            continue
        if line.startswith("- ") and current:
            bullet = normalize_line(line[2:])
            if bullet:
                sections[current].append(bullet)
    return sections


def parse_fact_bullets(body: str) -> dict[str, str]:
    facts: dict[str, str] = {}
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("- "):
            continue
        payload = line[2:].strip()
        fact_id, sep, fact_text = payload.partition(":")
        fact_id = normalize_line(fact_id)
        fact_text = normalize_line(fact_text)
        if sep and fact_id and fact_text:
            facts[fact_id] = fact_text
    return facts


def parse_bullet_text(body: str) -> str:
    lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        lines.append(line)
    return normalize_line(" ".join(lines))


def compile_profile(bank_dir: Path) -> dict[str, Any]:
    frontmatter, body = parse_markdown_document(bank_dir / "profile.md")
    sections = parse_profile_sections(body)
    profile_snippets = {
        family: sections.get(family, as_string_list(frontmatter.get("profile_snippets", {}).get(family, [])))
        for family in ("quant", "ai", "data", "software")
    }
    return {
        "candidate_name": normalize_line(str(frontmatter.get("candidate_name", PLACEHOLDER_MARKER))),
        "header": {
            "location": normalize_line(str(frontmatter.get("location", PLACEHOLDER_MARKER))),
            "availability": normalize_line(str(frontmatter.get("availability", PLACEHOLDER_MARKER))),
            "email": normalize_line(str(frontmatter.get("email", "you@example.com"))),
            "phone": normalize_line(str(frontmatter.get("phone", PLACEHOLDER_MARKER))),
            "github": normalize_line(str(frontmatter.get("github", ""))),
            "linkedin": normalize_line(str(frontmatter.get("linkedin", ""))),
        },
        "education": frontmatter.get("education", []),
        "project_bullet_targets": frontmatter.get("project_bullet_targets", [4, 3, 2]),
        "project_orders": frontmatter.get("project_orders", {}),
        "profile_snippets": profile_snippets,
    }


def compile_stories(bank_dir: Path) -> dict[str, Any]:
    projects: dict[str, Any] = {}
    for path in sorted((bank_dir / "stories").glob("*.md")):
        if path.name.startswith("_"):
            continue
        frontmatter, body = parse_markdown_document(path)
        project_id = normalize_line(str(frontmatter.get("id", ""))) or slugify(path.stem)
        facts = parse_fact_bullets(body)
        raw_aliases = as_string_list(frontmatter.get("aliases", []))
        display_title = normalize_line(str(frontmatter.get("display_title", "")))
        link = frontmatter.get("link", {})
        link_url = normalize_line(str(frontmatter.get("link_url", "")))
        link_label = normalize_line(str(frontmatter.get("link_label", "")))
        if isinstance(link, dict):
            link_url = link_url or normalize_line(str(link.get("url", "")))
            link_label = link_label or normalize_line(str(link.get("label", "")))
        projects[project_id] = {
            "name": normalize_line(str(frontmatter.get("name", project_id))),
            "stack": normalize_line(str(frontmatter.get("stack", ""))),
            "display_title": display_title,
            "aliases": raw_aliases,
            "link": {
                "label": link_label,
                "url": link_url,
            },
            "facts": facts,
        }
    return {"projects": projects}


def compile_evidence(bank_dir: Path) -> dict[str, Any]:
    bullets: list[dict[str, Any]] = []
    for path in sorted((bank_dir / "evidence").glob("*.md")):
        if path.name.startswith("_"):
            continue
        frontmatter, body = parse_markdown_document(path)
        bullets.append(
            {
                "id": normalize_line(str(frontmatter.get("id", ""))) or slugify(path.stem),
                "project_id": normalize_line(str(frontmatter.get("project_id", ""))),
                "text": parse_bullet_text(body),
                "families": as_string_list(frontmatter.get("families", [])),
                "tags": as_string_list(frontmatter.get("tags", [])),
                "priority": int(frontmatter.get("priority", 3)),
                "evidence_refs": as_string_list(frontmatter.get("evidence_refs", [])),
            }
        )
    return {"bullets": bullets}


def compile_skills(bank_dir: Path) -> dict[str, Any]:
    frontmatter, _ = parse_markdown_document(bank_dir / "skills.md")
    return {
        "fallback_block_id": normalize_line(str(frontmatter.get("fallback_block_id", "software_core_v1"))),
        "blocks": frontmatter.get("blocks", []),
    }


def compile_templates(bank_dir: Path) -> dict[str, Any]:
    frontmatter, _ = parse_markdown_document(bank_dir / "templates.md")
    return {
        "templates": frontmatter.get("templates", {}),
        "routing_defaults": frontmatter.get("routing_defaults", {}),
        "routing_rules": frontmatter.get("routing_rules", []),
    }


def write_structured(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def compile_markdown_bank(bank_dir: Path, output_dir: Path) -> Path:
    if not is_markdown_bank_dir(bank_dir):
        raise RuntimeError(f"{bank_dir} does not look like a markdown bank.")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_structured(output_dir / "candidate_profile.yaml", compile_profile(bank_dir))
    write_structured(output_dir / "project_evidence.yaml", compile_stories(bank_dir))
    write_structured(output_dir / "bullet_library.yaml", compile_evidence(bank_dir))
    write_structured(output_dir / "skills_blocks.yaml", compile_skills(bank_dir))
    write_structured(output_dir / "template_registry.yaml", compile_templates(bank_dir))
    return output_dir


def resolve_runtime_bank(bank_dir: Path, compiled_root: Path | None = None) -> Path:
    bank_dir = bank_dir.resolve()
    if is_legacy_bank_dir(bank_dir):
        return bank_dir
    if not is_markdown_bank_dir(bank_dir):
        raise RuntimeError(
            f"{bank_dir} is not a supported bank directory. Expected either legacy YAML files or markdown-bank files."
        )
    compiled_root = (compiled_root or Path(".build/compiled_bank")).resolve()
    compiled_dir = compiled_root / compute_bank_signature(bank_dir)
    if not is_legacy_bank_dir(compiled_dir):
        compile_markdown_bank(bank_dir, compiled_dir)
    return compiled_dir
