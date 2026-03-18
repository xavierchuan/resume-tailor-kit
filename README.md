# resume-tailor-kit

A small open-source toolkit for turning a job description plus a personal evidence bank into a draft one-page LaTeX resume.

This project is extracted from a private workflow and intentionally keeps the useful generic parts only:
- job-description routing (`family`, `seniority`, `keywords`)
- evidence-bank selection
- deterministic draft rendering to LaTeX
- output contract checks and simple PDF QA

## What it is for

Use this when you already have a structured evidence bank about a candidate and want a fast, truthful draft that mirrors a target JD.

The workflow is:
1. Convert the JD to plain text.
2. Extract a job card.
3. Select matching profile lines, skill blocks, and project bullets from the bank.
4. Render a draft LaTeX resume.
5. Review and edit the draft manually.
6. Compile and run QA.

## Why the manual review step still matters

This toolkit helps with routing and evidence selection. It does **not** remove the need for human review. Final wording should be checked for:
- truthfulness
- role voice consistency
- unsupported claims
- page density and readability

## Project layout

- `bank/` - sample candidate evidence bank you can replace with your own
- `scripts/extract_job_card.py` - derive company, role, family, keywords from a JD
- `scripts/select_content.py` - select content from the evidence bank
- `scripts/pipeline_fast.py` - cached prepare pipeline
- `scripts/render_resume.py` - render a generic LaTeX resume draft
- `scripts/check_output_contract.py` - validate expected files exist
- `scripts/quick_qa.py` - validate one-page output and file contract
- `examples/` - example JD input

## Quick start

```bash
cd resume-tailor-kit
python3 scripts/pipeline_fast.py \
  --jd-file examples/jd_data_analyst.txt \
  --cache-dir tmp/cache \
  --output-job-card tmp/job_card.json \
  --output-selected tmp/selected.json

python3 scripts/render_resume.py \
  --selected tmp/selected.json \
  --output out/Sample_Candidate_Data_Analyst.tex \
  --compile

python3 scripts/quick_qa.py \
  --pdf out/Sample_Candidate_Data_Analyst.pdf \
  --output-dir out \
  --base-name Sample_Candidate_Data_Analyst
```

## Requirements

- Python 3.10+
- `tectonic` for LaTeX compile (optional unless using `--compile`)
- `pdfinfo` for page-count QA

## Bank format

All files in `bank/` are JSON-compatible YAML. You can edit them with either JSON or YAML syntax.

Core files:
- `candidate_profile.yaml`
- `project_evidence.yaml`
- `bullet_library.yaml`
- `skills_blocks.yaml`
- `template_registry.yaml`

## License

MIT
