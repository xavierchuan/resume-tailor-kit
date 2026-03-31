#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable

from bank_runtime import load_structured, resolve_runtime_bank
from routing import infer_source_role_tokens


SECTION_RE = re.compile(r"\\section\*\{(?P<name>[^}]+)\}(?P<body>.*?)(?=(?:\\section\*\{|\\end\{document\}))", re.S)
SUBSECTION_RE = re.compile(r"\\subsection\*\{(?P<title>.*?)\}(?P<body>.*?)(?=(?:\\subsection\*\{|\\section\*\{|\\end\{document\}))", re.S)
ITEM_RE = re.compile(r"\\item\s+(.*?)(?=(?:\\item|\\end\{itemize\}))", re.S)
HREF_RE = re.compile(r"\\href\{[^}]*\}\{([^}]*)\}")
HREF_PAIR_RE = re.compile(r"\\href\{([^}]*)\}\{([^}]*)\}")
CMD_ARG_RE = re.compile(r"\\(?:textbf|textit|emph)\{([^{}]*)\}")
LINEBREAK_RE = re.compile(r"\\\\")
COMMAND_RE = re.compile(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?")
BRACE_RE = re.compile(r"[{}]")
MULTISPACE_RE = re.compile(r"\s+")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

STOP_TEX_FILES = {
    "software.tex",
    "ai.tex",
    "quant.tex",
    "quant_etf_leveraged.tex",
    "AI Engineering.tex",
    "software developer.tex",
}


def tex_to_text(text: str) -> str:
    text = HREF_RE.sub(r"\1", text)
    previous = None
    while previous != text:
        previous = text
        text = CMD_ARG_RE.sub(r"\1", text)
    text = text.replace("~", " ")
    text = LINEBREAK_RE.sub("\n", text)
    text = COMMAND_RE.sub("", text)
    text = BRACE_RE.sub("", text)
    text = text.replace(r"\&", "&").replace(r"\%", "%").replace(r"\_", "_")
    text = MULTISPACE_RE.sub(" ", text)
    return text.strip()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9+_-]*", text.lower())


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def iter_tex_files(cv_root: Path) -> Iterable[Path]:
    for path in cv_root.rglob("*.tex"):
        if any(part.startswith(".") for part in path.parts):
            continue
        if path.name in STOP_TEX_FILES:
            continue
        if "cover" in path.name.lower():
            continue
        if "_bank" in path.parts:
            continue
        yield path


def extract_section(text: str, section_name: str) -> str:
    for match in SECTION_RE.finditer(text):
        if match.group("name").strip().lower() == section_name.lower():
            return match.group("body")
    return ""


def split_profile_lines(profile_body: str) -> list[str]:
    text = tex_to_text(profile_body)
    if not text:
        return []
    lines = []
    for part in SENTENCE_SPLIT_RE.split(text):
        part = part.strip()
        if len(part) < 30:
            continue
        lines.append(part)
    return lines


def split_skills_lines(skills_body: str) -> list[str]:
    raw = skills_body.replace("\\begin{multicols}{2}", "").replace("\\end{multicols}", "")
    segments = [tex_to_text(part) for part in LINEBREAK_RE.split(raw)]
    out = []
    for seg in segments:
        seg = seg.strip(" ")
        seg = re.sub(r"^(?:0pt\s+)+", "", seg)
        if ":" not in seg:
            continue
        if len(seg) < 8:
            continue
        out.append(seg)
    return out


def extract_projects(text: str, source_path: Path) -> list[dict]:
    out = []
    for match in SUBSECTION_RE.finditer(text):
        title_raw = match.group("title")
        body_raw = match.group("body")
        title = tex_to_text(title_raw)
        title = re.sub(r"\bRepository\b", "", title).strip(" -—")
        if not title:
            continue
        stack_match = re.search(r"\\textit\{(.*?)\}", body_raw, re.S)
        stack = tex_to_text(stack_match.group(1)) if stack_match else ""
        href_matches = HREF_PAIR_RE.findall(body_raw)
        links = [{"url": url.strip(), "label": tex_to_text(label).strip()} for url, label in href_matches if url.strip() and tex_to_text(label).strip()]
        source_role_tokens = infer_source_role_tokens(source_path.stem, title, body_raw)
        bullets = [tex_to_text(item) for item in ITEM_RE.findall(body_raw)]
        bullets = [b for b in bullets if len(b) >= 20]
        out.append(
            {
                "title": title,
                "stack": stack,
                "links": links,
                "bullets": bullets,
                "body": tex_to_text(body_raw),
                "source": str(source_path),
                "source_tokens": tokenize(source_path.stem),
                "source_role_tokens": source_role_tokens,
            }
        )
    return out


def add_unique(items: list[dict], seen: set[str], entry: dict, dedupe_key: str = "text") -> None:
    key = normalize_text(entry.get(dedupe_key, ""))
    if not key or key in seen:
        return
    seen.add(key)
    items.append(entry)


def load_project_aliases(bank_dir: Path | None) -> dict[str, list[str]]:
    if not bank_dir:
        return {}
    runtime_bank_dir = resolve_runtime_bank(bank_dir)
    project_evidence = load_structured(runtime_bank_dir / "project_evidence.yaml")
    alias_map: dict[str, list[str]] = {}
    for project_id, payload in project_evidence.get("projects", {}).items():
        aliases = [project_id, payload.get("name", ""), payload.get("display_title", "")]
        aliases.extend(payload.get("aliases", []) or [])
        alias_map[project_id] = [alias for alias in aliases if normalize_text(str(alias))]
    return alias_map


def resolve_project_alias(title: str, body: str, alias_map: dict[str, list[str]]) -> str | None:
    if not alias_map:
        return None
    corpus = normalize_text(f"{title} {body}")
    corpus_tokens = set(tokenize(corpus))
    best_id = None
    best_score = 0
    for project_id, aliases in alias_map.items():
        score = 0
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if not alias_norm:
                continue
            if alias_norm in corpus:
                score += 4
            score += len(corpus_tokens & set(tokenize(alias_norm)))
        if score > best_score:
            best_score = score
            best_id = project_id
    if best_score < 2:
        return None
    return best_id


def build_variant_bank(cv_root: Path, bank_dir: Path | None = None) -> dict:
    profiles: list[dict] = []
    skills_lines: list[dict] = []
    profiles_seen: set[str] = set()
    skills_seen: set[str] = set()
    project_variants: dict[str, dict[str, list[dict]]] = {}
    project_seen: dict[str, dict[str, set[str]]] = {}
    stats = {"tex_files_scanned": 0, "projects_seen": 0}
    alias_map = load_project_aliases(bank_dir)

    for path in iter_tex_files(cv_root):
        stats["tex_files_scanned"] += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        source_tokens = tokenize(path.stem)

        profile_body = extract_section(text, "PROFILE")
        for line in split_profile_lines(profile_body):
            add_unique(
                profiles,
                profiles_seen,
                {
                    "text": line,
                    "source": str(path),
                    "source_tokens": source_tokens,
                    "source_role_tokens": infer_source_role_tokens(path.stem, line),
                    "source_type": "variant",
                },
            )

        skills_body = extract_section(text, "TECHNICAL SKILLS")
        for line in split_skills_lines(skills_body):
            add_unique(
                skills_lines,
                skills_seen,
                {
                    "text": line,
                    "source": str(path),
                    "source_tokens": source_tokens,
                    "source_role_tokens": infer_source_role_tokens(path.stem, line),
                    "source_type": "variant",
                },
            )

        for project in extract_projects(text, path):
            stats["projects_seen"] += 1
            project_id = resolve_project_alias(project["title"], project["body"], alias_map) or slugify(project["title"])
            bucket = project_variants.setdefault(
                project_id,
                {"title_variants": [], "stack_variants": [], "link_variants": [], "bullet_variants": []},
            )
            seen_bucket = project_seen.setdefault(
                project_id,
                {"title_variants": set(), "stack_variants": set(), "link_variants": set(), "bullet_variants": set()},
            )
            add_unique(
                bucket["title_variants"],
                seen_bucket["title_variants"],
                {
                    "text": project["title"],
                    "source": project["source"],
                    "source_tokens": project["source_tokens"],
                    "source_role_tokens": project["source_role_tokens"],
                    "source_type": "variant",
                },
            )
            if project["stack"]:
                add_unique(
                    bucket["stack_variants"],
                    seen_bucket["stack_variants"],
                    {
                        "text": project["stack"],
                        "source": project["source"],
                        "source_tokens": project["source_tokens"],
                        "source_role_tokens": project["source_role_tokens"],
                        "source_type": "variant",
                    },
                )
            for link in project["links"]:
                add_unique(
                    bucket["link_variants"],
                    seen_bucket["link_variants"],
                    {
                        "text": f"{link['label']}|{link['url']}",
                        "label": link["label"],
                        "url": link["url"],
                        "source": project["source"],
                        "source_tokens": project["source_tokens"],
                        "source_role_tokens": project["source_role_tokens"],
                        "source_type": "variant",
                    },
                )
            for bullet in project["bullets"]:
                add_unique(
                    bucket["bullet_variants"],
                    seen_bucket["bullet_variants"],
                    {
                        "text": bullet,
                        "source": project["source"],
                        "source_tokens": project["source_tokens"],
                        "source_role_tokens": project["source_role_tokens"],
                        "source_type": "variant",
                    },
                )

    return {
        "cv_root": str(cv_root),
        "bank_dir": str(bank_dir.resolve()) if bank_dir else None,
        "stats": stats,
        "profiles": profiles,
        "skills_lines": skills_lines,
        "project_variants": project_variants,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract reusable profile, skills, and project variants from historical CV TeX files.")
    parser.add_argument("--cv-root", type=Path, required=True, help="Root directory containing historical CV .tex files.")
    parser.add_argument("--bank-dir", type=Path, help="Optional bank directory used to map project aliases.")
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path.")
    args = parser.parse_args()

    bank = build_variant_bank(args.cv_root, args.bank_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(args.output), "stats": bank["stats"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
