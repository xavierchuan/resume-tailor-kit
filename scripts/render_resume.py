#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

from bank_runtime import load_structured, resolve_runtime_bank


TYPOGRAPHY_PRESETS = {
    "normal": {
        "font_size": "8.85pt",
        "margin": "0.47in",
        "section_spacing": ("0.04em", "0.04em"),
        "subsection_spacing": ("0.03em", "0.03em"),
        "itemize": "leftmargin=1.0em, itemsep=-0.12em, topsep=-0.08em",
        "tabcolsep": "2pt",
    },
    "tight": {
        "font_size": "8.55pt",
        "margin": "0.44in",
        "section_spacing": ("0.03em", "0.03em"),
        "subsection_spacing": ("0.02em", "0.02em"),
        "itemize": "leftmargin=0.95em, itemsep=-0.18em, topsep=-0.12em",
        "tabcolsep": "1.5pt",
    },
}


LAYOUT_OVERRIDES = {
    "balanced": {
        "font_bump": 0.3,
        "margin_bump": 0.08,
        "section_spacing": ("0.10em", "0.08em"),
        "subsection_spacing": ("0.05em", "0.04em"),
        "itemize": "leftmargin=1.0em, itemsep=-0.06em, topsep=-0.02em",
        "tabcolsep": "2.4pt",
    },
    "dense": {
        "font_bump": 0.0,
        "margin_bump": 0.0,
        "section_spacing": None,
        "subsection_spacing": None,
        "itemize": None,
        "tabcolsep": None,
    },
}


def run(cmd: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr or process.stdout)
    return process.stdout.strip()


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def normalize_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text", "")).strip()
    return str(item).strip()


def dedupe_texts(items: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = item_text(item)
        key = normalize_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def split_columns(items: list[str]) -> tuple[list[str], list[str]]:
    midpoint = math.ceil(len(items) / 2)
    left = items[:midpoint]
    right = items[midpoint:]
    while len(left) < len(right):
        left.append("")
    while len(right) < len(left):
        right.append("")
    return left, right


def parse_pt(value: str) -> float:
    return float(value.removesuffix("pt"))


def parse_in(value: str) -> float:
    return float(value.removesuffix("in"))


def format_pt(value: float) -> str:
    return f"{value:.2f}pt"


def format_in(value: float) -> str:
    return f"{value:.2f}in"


def preset_for_layout(typography_preset: str, layout_mode: str) -> dict[str, str | tuple[str, str]]:
    base = dict(TYPOGRAPHY_PRESETS.get(typography_preset, TYPOGRAPHY_PRESETS["normal"]))
    overrides = LAYOUT_OVERRIDES.get(layout_mode, LAYOUT_OVERRIDES["balanced"])
    font_size = parse_pt(str(base["font_size"])) + float(overrides["font_bump"])
    margin = parse_in(str(base["margin"])) + float(overrides["margin_bump"])
    base["font_size"] = format_pt(font_size)
    base["margin"] = format_in(margin)
    if overrides["section_spacing"]:
        base["section_spacing"] = overrides["section_spacing"]
    if overrides["subsection_spacing"]:
        base["subsection_spacing"] = overrides["subsection_spacing"]
    if overrides["itemize"]:
        base["itemize"] = overrides["itemize"]
    if overrides["tabcolsep"]:
        base["tabcolsep"] = overrides["tabcolsep"]
    return base


def skills_block_items(skills_blocks: dict[str, Any], block_id: str) -> list[str]:
    for block in skills_blocks.get("blocks", []):
        if block.get("id") == block_id:
            return list(block.get("items", []))
    fallback_id = skills_blocks.get("fallback_block_id")
    for block in skills_blocks.get("blocks", []):
        if block.get("id") == fallback_id:
            return list(block.get("items", []))
    return []


def bullet_text_map(bullet_library: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        bullet["id"]: bullet
        for bullet in bullet_library.get("bullets", [])
        if "id" in bullet and "text" in bullet
    }


def project_defaults(project_bank: dict[str, Any], project_id: str) -> dict[str, Any]:
    project = project_bank.get("projects", {}).get(project_id, {})
    link = project.get("link", {})
    if not isinstance(link, dict):
        link = {}
    return {
        "title": project.get("display_title") or project.get("name") or project_id.replace("_", " ").title(),
        "stack": project.get("stack", ""),
        "link": {
            "label": link.get("label", ""),
            "url": link.get("url", ""),
        },
    }


def load_bank(bank_dir: Path) -> tuple[dict[str, Any], Path]:
    runtime_bank_dir = resolve_runtime_bank(bank_dir)
    bank = {
        "candidate_profile": load_structured(runtime_bank_dir / "candidate_profile.yaml"),
        "project_evidence": load_structured(runtime_bank_dir / "project_evidence.yaml"),
        "bullet_library": load_structured(runtime_bank_dir / "bullet_library.yaml"),
        "skills_blocks": load_structured(runtime_bank_dir / "skills_blocks.yaml"),
    }
    return bank, runtime_bank_dir


def distribute_extra(projects: list[dict[str, Any]], extra_bullets: int) -> list[dict[str, Any]]:
    if extra_bullets <= 0:
        return projects
    remaining = extra_bullets
    expanded = []
    for project in projects:
        bullets = list(project.get("bullets", []))
        extras = list(project.get("extra_bullets", []))
        while remaining > 0 and extras:
            bullets.append(extras.pop(0))
            remaining -= 1
        cloned = dict(project)
        cloned["bullets"] = bullets
        cloned["extra_bullets"] = extras
        expanded.append(cloned)
    return expanded


def build_model_from_selected(selected: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    candidate = bank["candidate_profile"]
    project_bank = bank["project_evidence"]
    bullet_map = bullet_text_map(bank["bullet_library"])
    skills_items = skills_block_items(bank["skills_blocks"], selected.get("skills_block_id", "software_core_v1"))
    projects = []
    for section in selected.get("project_sections", []):
        project_id = section["project_id"]
        defaults = project_defaults(project_bank, project_id)
        bullets = []
        for bullet_id in section.get("bullet_ids", []):
            bullet = bullet_map.get(bullet_id)
            if bullet:
                bullets.append(bullet["text"])
        projects.append(
            {
                "project_id": project_id,
                "title": defaults["title"],
                "stack": defaults["stack"],
                "link": defaults["link"] if defaults["link"].get("label") and defaults["link"].get("url") else None,
                "bullets": dedupe_texts(bullets),
                "extra_bullets": [],
            }
        )
    return {
        "header": candidate["header"],
        "candidate_name": candidate["candidate_name"],
        "profile_lines": [line.strip() for line in selected.get("profile_lines", []) if line.strip()],
        "skills_items": dedupe_texts(skills_items),
        "projects": projects,
        "education": candidate.get("education", []),
    }


def build_model_from_rewrite_pack(
    rewrite_pack: dict[str, Any],
    bank: dict[str, Any],
    profile_variant: str,
    skills_variant: str,
    extra_bullets: int,
    include_extra_project: bool,
) -> dict[str, Any]:
    candidate = bank["candidate_profile"]
    project_bank = bank["project_evidence"]

    profile_lines = dedupe_texts(rewrite_pack.get("profile", {}).get(profile_variant, []))
    if not profile_lines:
        profile_lines = dedupe_texts(rewrite_pack.get("profile", {}).get("normal", []))
    skills_items = dedupe_texts(rewrite_pack.get("skills", {}).get(skills_variant, []))
    if not skills_items:
        skills_items = dedupe_texts(rewrite_pack.get("skills", {}).get("normal", []))

    def rewrite_project_to_model(project: dict[str, Any]) -> dict[str, Any]:
        project_id = project.get("project_id", "")
        defaults = project_defaults(project_bank, project_id) if project_id else {"title": "Project", "stack": "", "link": {"label": "", "url": ""}}
        link = project.get("link")
        if not isinstance(link, dict):
            link = defaults["link"]
        return {
            "project_id": project_id,
            "title": item_text(project.get("title")) or defaults["title"],
            "stack": item_text(project.get("stack")) or defaults["stack"],
            "link": link if link.get("label") and link.get("url") else (defaults["link"] if defaults["link"].get("label") and defaults["link"].get("url") else None),
            "bullets": dedupe_texts(project.get("bullets", [])),
            "extra_bullets": dedupe_texts(project.get("extra_bullets", [])),
        }

    projects = [rewrite_project_to_model(project) for project in rewrite_pack.get("projects", [])]
    projects = distribute_extra(projects, extra_bullets)
    if include_extra_project:
        extra_projects = [rewrite_project_to_model(project) for project in rewrite_pack.get("extra_projects", [])[:1]]
        projects.extend(extra_projects)

    return {
        "header": candidate["header"],
        "candidate_name": candidate["candidate_name"],
        "profile_lines": profile_lines,
        "skills_items": skills_items,
        "projects": projects,
        "education": candidate.get("education", []),
    }


def render_header(model: dict[str, Any]) -> str:
    header = model["header"]
    github_url = header.get("github", "")
    linkedin_url = header.get("linkedin", "")
    social_parts = []
    if github_url:
        social_parts.append(rf"\href{{{github_url}}}{{GitHub}}")
    if linkedin_url:
        social_parts.append(rf"\href{{{linkedin_url}}}{{LinkedIn}}")
    social_row = r" \quad ".join(social_parts)
    if social_row:
        social_row = social_row + "\n"
    return (
        "\\begin{center}\n"
        f"{{\\large \\textbf{{{latex_escape(model['candidate_name'])}}}}} \\\\\n"
        f"{latex_escape(header['location'])} \\quad | \\quad {latex_escape(header['availability'])} \\quad | \\quad {latex_escape(header['email'])} \\quad | \\quad {latex_escape(header['phone'])} \\\\\n"
        f"{social_row}"
        "\\end{center}\n"
    )


def render_project_section(project: dict[str, Any]) -> str:
    title = latex_escape(project["title"])
    lines = [rf"\subsection*{{\textbf{{{title}}}}}"]
    if project.get("stack"):
        lines.append(rf"\textit{{{latex_escape(project['stack'])}}}")
    if project.get("link"):
        lines.append(rf"\href{{{project['link']['url']}}}{{{latex_escape(project['link']['label'])}}}")
    lines.append(r"\begin{itemize}")
    for bullet in project.get("bullets", []):
        lines.append(rf"\item {latex_escape(bullet)}")
    lines.append(r"\end{itemize}")
    return "\n".join(lines)


def build_tex(model: dict[str, Any], typography_preset: str, layout_mode: str) -> str:
    preset = preset_for_layout(typography_preset, layout_mode)
    profile_text = " ".join(latex_escape(line) for line in model.get("profile_lines", []))
    left, right = split_columns(model.get("skills_items", []))
    skill_rows = []
    for left_item, right_item in zip(left, right):
        skill_rows.append(rf"{latex_escape(left_item)} & {latex_escape(right_item)} \\")
    projects = "\n\n".join(render_project_section(project) for project in model.get("projects", []))
    education_rows = [
        rf"\textbf{{{latex_escape(item['institution'])}}} --- {latex_escape(item['degree'])} \hfill {latex_escape(item['start'])} -- {latex_escape(item['end'])} \\"
        for item in model.get("education", [])
    ]
    sec_before, sec_after = preset["section_spacing"]
    sub_before, sub_after = preset["subsection_spacing"]
    return rf"""\documentclass[a4paper,{preset['font_size']}]{{article}}
\usepackage[margin={preset['margin']}]{{geometry}}
\usepackage{{enumitem}}
\usepackage{{titlesec}}
\usepackage[hidelinks]{{hyperref}}
\pagestyle{{empty}}

\titlespacing{{\section}}{{0pt}}{{{sec_before}}}{{{sec_after}}}
\titlespacing{{\subsection}}{{0pt}}{{{sub_before}}}{{{sub_after}}}
\renewcommand{{\labelitemi}}{{--}}
\setlist[itemize]{{{preset['itemize']}}}
\setlength{{\parskip}}{{0em}}
\setlength{{\tabcolsep}}{{{preset['tabcolsep']}}}

\begin{{document}}

{render_header(model)}
\section*{{PROFILE}}
{profile_text}

\section*{{TECHNICAL SKILLS}}
\footnotesize
\begin{{tabular}}{{p{{0.47\textwidth}}p{{0.47\textwidth}}}}
{chr(10).join(skill_rows)}
\end{{tabular}}
\normalsize

\section*{{PROJECT EXPERIENCE}}
{projects}

\section*{{EDUCATION}}
{chr(10).join(education_rows)}

\end{{document}}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a one-page LaTeX CV from selected content or rewrite packs.")
    parser.add_argument("--selected", type=Path, help="Fallback selected.json path.")
    parser.add_argument("--rewrite-pack", type=Path, help="Preferred rewrite_pack.json path.")
    parser.add_argument("--bank-dir", type=Path, default=Path("bank"), help="Evidence bank directory.")
    parser.add_argument("--output", type=Path, required=True, help="Output TeX path.")
    parser.add_argument("--compile", action="store_true", help="Compile TeX to PDF via tectonic.")
    parser.add_argument("--profile-variant", choices=["short", "normal", "dense"], default="normal")
    parser.add_argument("--skills-variant", choices=["normal", "dense"], default="normal")
    parser.add_argument("--extra-bullets", type=int, default=0)
    parser.add_argument("--include-extra-project", action="store_true")
    parser.add_argument("--layout-mode", choices=["balanced", "dense"], default="balanced")
    parser.add_argument("--typography-preset", choices=["normal", "tight"], default="normal")
    args = parser.parse_args()

    if not args.rewrite_pack and not args.selected:
        parser.error("Provide --rewrite-pack or --selected.")

    bank, runtime_bank_dir = load_bank(args.bank_dir)
    if args.rewrite_pack:
        rewrite_pack = load_structured(args.rewrite_pack)
        model = build_model_from_rewrite_pack(
            rewrite_pack,
            bank,
            profile_variant=args.profile_variant,
            skills_variant=args.skills_variant,
            extra_bullets=args.extra_bullets,
            include_extra_project=args.include_extra_project,
        )
        source = "rewrite_pack"
    else:
        selected = load_structured(args.selected)
        model = build_model_from_selected(selected, bank)
        source = "selected"

    tex = build_tex(model, typography_preset=args.typography_preset, layout_mode=args.layout_mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(tex, encoding="utf-8")
    pdf_path = None
    if args.compile:
        run(["tectonic", str(args.output), "--outdir", str(args.output.parent)])
        pdf_path = args.output.with_suffix(".pdf")
    print(
        json.dumps(
            {
                "status": "pass",
                "source": source,
                "output_tex": str(args.output),
                "pdf": str(pdf_path) if pdf_path else None,
                "bank_dir": str(args.bank_dir.resolve()),
                "runtime_bank_dir": str(runtime_bank_dir),
                "profile_variant": args.profile_variant,
                "skills_variant": args.skills_variant,
                "extra_bullets": args.extra_bullets,
                "include_extra_project": args.include_extra_project,
                "layout_mode": args.layout_mode,
                "typography_preset": args.typography_preset,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
