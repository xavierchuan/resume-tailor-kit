#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path | None = None) -> str:
    process = subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)
    if process.returncode != 0:
        raise RuntimeError(process.stderr or process.stdout)
    return process.stdout.strip()


def load_structured(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8').strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import yaml  # type: ignore
        data = yaml.safe_load(text)
        return data or {}


def latex_escape(text: str) -> str:
    replacements = {
        '\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
        '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'
    }
    return ''.join(replacements.get(ch, ch) for ch in text)


def slugify(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_')


def build_header(candidate: dict[str, Any]) -> str:
    h = candidate['header']
    return (
        "\\begin{center}\n"
        f"{{\\Large \\textbf{{{latex_escape(candidate['candidate_name'])}}}}} \\\\\n"
        f"{latex_escape(h['location'])} \\quad | \\quad {latex_escape(h['availability'])} \\quad | \\quad {latex_escape(h['email'])} \\quad | \\quad {latex_escape(h['phone'])} \\\\\n"
        f"\\href{{{h['github']}}}{{GitHub}} \\quad \\href{{{h['linkedin']}}}{{LinkedIn}}\n"
        "\\end{center}\n"
    )


def build_profile(lines: list[str]) -> str:
    return " \\\\\n".join(latex_escape(line) for line in lines)


def build_skills_block(skills_bank: dict[str, Any], block_id: str) -> str:
    block = next((b for b in skills_bank['blocks'] if b['id'] == block_id), None)
    if not block:
        block = next(b for b in skills_bank['blocks'] if b['id'] == skills_bank['fallback_block_id'])
    out = []
    for raw in block['items']:
        if ':' in raw:
            key, value = raw.split(':', 1)
            out.append(f"\\textbf{{{latex_escape(key)}}}: {latex_escape(value.strip())} \\\\")
        else:
            out.append(f"{latex_escape(raw)} \\\\")
    return '\n'.join(out)


def build_projects(selected: dict[str, Any], project_bank: dict[str, Any], bullets_bank: dict[str, Any]) -> str:
    bullet_by_id = {b['id']: b for b in bullets_bank['bullets']}
    parts = []
    for section in selected['project_sections']:
        project = project_bank['projects'][section['project_id']]
        title = f"\\subsection*{{\\textbf{{{latex_escape(project['name'])}}}}}"
        stack = f"\\textit{{{latex_escape(project.get('stack', ''))}}}"
        bullets = [f"    \\item {latex_escape(bullet_by_id[bid]['text'])}" for bid in section['bullet_ids'] if bid in bullet_by_id]
        parts.append(title + "\n" + stack + "\n\\begin{itemize}\n" + "\n".join(bullets) + "\n\\end{itemize}\n")
    return '\n'.join(parts)


def build_education(candidate: dict[str, Any]) -> str:
    rows = []
    for edu in candidate['education']:
        rows.append(
            f"\\textbf{{{latex_escape(edu['institution'])}}} --- {latex_escape(edu['degree'])} \\hfill {latex_escape(edu['start'])} -- {latex_escape(edu['end'])} \\\\"
        )
    return '\n'.join(rows)


def build_tex(candidate: dict[str, Any], skills_bank: dict[str, Any], project_bank: dict[str, Any], selected: dict[str, Any], bullets_bank: dict[str, Any]) -> str:
    return f'''\\documentclass[a4paper,8.8pt]{{article}}
\\usepackage[margin=0.5in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{titlesec}}
\\usepackage{{multicol}}
\\usepackage[hidelinks]{{hyperref}}
\\pagestyle{{empty}}
\\titlespacing{{\\section}}{{0pt}}{{0.03em}}{{0.03em}}
\\titlespacing{{\\subsection}}{{0pt}}{{0.03em}}{{0.03em}}
\\renewcommand{{\\labelitemi}}{{--}}
\\setlist[itemize]{{leftmargin=1.0em, itemsep=-0.16em, topsep=-0.12em}}
\\setlength{{\\parskip}}{{0em}}
\\begin{{document}}
{build_header(candidate)}
\\section*{{PROFILE}}
{build_profile(selected['profile_lines'])}
\\section*{{TECHNICAL SKILLS}}
\\small
\\begin{{multicols}}{{2}}
\\setlength{{\\parindent}}{{0pt}}
{build_skills_block(skills_bank, selected['skills_block_id'])}
\\end{{multicols}}
\\normalsize
\\section*{{PROJECT EXPERIENCE}}
{build_projects(selected, project_bank, bullets_bank)}
\\section*{{EDUCATION}}
{build_education(candidate)}
\\end{{document}}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description='Render a generic LaTeX resume draft from selected content.')
    parser.add_argument('--selected', type=Path, required=True)
    parser.add_argument('--bank-dir', type=Path, default=Path('bank'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compile', action='store_true')
    args = parser.parse_args()
    selected = load_structured(args.selected)
    candidate = load_structured(args.bank_dir / 'candidate_profile.yaml')
    project_bank = load_structured(args.bank_dir / 'project_evidence.yaml')
    skills_bank = load_structured(args.bank_dir / 'skills_blocks.yaml')
    bullets_bank = load_structured(args.bank_dir / 'bullet_library.yaml')
    tex = build_tex(candidate, skills_bank, project_bank, selected, bullets_bank)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(tex, encoding='utf-8')
    if args.compile:
        run(['tectonic', str(args.output), '--outdir', str(args.output.parent)])
    print(json.dumps({'tex': str(args.output), 'pdf': str(args.output.with_suffix('.pdf')) if args.compile else None}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
