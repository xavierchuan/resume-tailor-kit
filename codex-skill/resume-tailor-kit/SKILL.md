---
name: resume-tailor-kit
description: Turn a plain-text job description plus a structured candidate evidence bank into a truthful one-page LaTeX resume draft with basic QA. Use when tailoring resumes from repeatable evidence rather than writing from scratch.
---

# Resume Tailor Kit

## Workflow

1. Convert the JD to plain text.
2. Run `scripts/pipeline_fast.py` to create `job_card.json` and `selected.json`.
3. Render a draft with `scripts/render_resume.py`.
4. Review the wording manually.
5. Compile and validate with `scripts/quick_qa.py`.

## Commands

Prepare:
`python3 scripts/pipeline_fast.py --jd-file <jd.txt> --cache-dir tmp/cache --output-job-card tmp/job_card.json --output-selected tmp/selected.json`

Render:
`python3 scripts/render_resume.py --selected tmp/selected.json --output out/<name>.tex --compile`

QA:
`python3 scripts/quick_qa.py --pdf out/<name>.pdf --output-dir out --base-name <name>`

## Constraints

- Keep all final claims grounded in the evidence bank.
- Treat generated wording as a draft, not final truth.
- Do not include personal candidate data in public examples.
