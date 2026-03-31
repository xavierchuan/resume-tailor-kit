---
name: resume-tailor-kit
description: Use this when a user wants to tailor a resume from a reusable evidence bank with Codex. It is best for AI, data, software, and quant-adjacent roles, uses archetype-aware routing on top of the core families, supports a local markdown-first bank or a legacy YAML bank, and stops at a truthful draft plus QA instead of inventing final claims.
---

# Resume Tailor Kit

Use this skill inside a checkout of the `resume-tailor-kit` repository. The repo provides the deterministic pipeline; Codex provides the AI help and review loop. It is best suited to AI, data, software, and quant-adjacent resume-tailoring tasks rather than general-purpose CV generation for every profession. The routing layer now uses both coarse families and finer archetypes such as `data_analyst`, `data_scientist`, `data_engineer`, `applied_ai`, `backend_platform`, `software_general`, and `quant_dev`.

## Before you run anything

1. Confirm the current workspace contains `scripts/`, `bank-template/`, `examples/`, and either:
   - a local working `bank/`, or
   - `examples/sample_bank/` for a demo run.
2. Default to `bank/` as the user bank.
3. If `bank/` is missing, initialize it:
   - `python3 scripts/init_bank.py --target bank`
4. If the bank still contains `REPLACE_ME` placeholders, or only underscore-prefixed template files in `stories/` and `evidence/`, stop and tell the user which minimum fields to fill:
   - `profile.md`
   - at least one story in `stories/`
   - at least one evidence bullet in `evidence/`
   - `skills.md`
5. Use `examples/sample_bank/` only for demos. Do not treat it as the user's real data.

## Accepted inputs

- A pasted JD, which should be passed as `--jd-text`
- A plain-text JD file, which should be passed as `--jd-file`

The bank may be:
- a markdown bank created from `bank-template/`
- a legacy YAML bank such as `examples/sample_bank/`

The scripts handle the runtime conversion automatically.

## Workflow

### Starter mode

Use starter mode for demos, public examples, or a fast first draft.

1. Prepare the artifacts:
   - `python3 scripts/pipeline_fast.py --bank-dir <bank-dir> --jd-file <jd.txt> --cache-dir tmp/cache --artifacts-dir tmp/run`
   - or swap `--jd-file` for `--jd-text`
2. Render the deterministic rules fallback:
   - `python3 scripts/render_resume.py --bank-dir <bank-dir> --rewrite-pack tmp/run/rewrite_pack.used.json --output out/<base>.tex --compile`
   - fallback: `--selected tmp/run/selected.json` still works if needed
3. Run QA on the compiled PDF:
   - `python3 scripts/quick_qa.py --pdf out/<base>.pdf --output-dir out --base-name <base> --job-card tmp/run/job_card.json --unsupported-count 0`

### Quality mode

Use quality mode when the user has private historical `.tex` CVs outside the repo and wants output closer to their real workflow.

1. Prepare artifacts only:
   - `python3 scripts/pipeline_fast.py --bank-dir <bank-dir> --cv-root <private-cv-root> --jd-file <jd.txt> --cache-dir tmp/cache --artifacts-dir tmp/quality --prepare-only --rewrite-mode agent`
2. Read:
   - `tmp/quality/rewrite_seed.json`
   - `tmp/quality/rewrite_pack.rules.json`
   - `docs/rewrite-pack-schema.md`
3. Write a grounded final `rewrite_pack.json` yourself from those artifacts.
   - Keep all wording anchored to provenance.
   - Do not invent claims, tools, metrics, titles, or timelines.
4. Validate the final pack:
   - `python3 scripts/validate_rewrite_pack.py --rewrite-pack path/to/rewrite_pack.json --output tmp/quality/rewrite_pack.validation.json`
5. Finalize the run with fixed quality presets:
   - `python3 scripts/finalize_quality_run.py --bank-dir <bank-dir> --artifacts-dir tmp/quality --rewrite-pack path/to/rewrite_pack.json --output-dir out --base-name <base>`
6. Review:
   - `tmp/quality/rewrite_pack.validation.json`
   - `tmp/quality/finalize_quality_run.json`
   - selected `out/<base>.tex` and optional PDF

## Output contract

- `tmp/.../job_card.json`
- `tmp/.../selected.json`
- `tmp/.../variant_bank.json` in quality mode
- `tmp/.../rewrite_seed.json`
- `tmp/.../rewrite_pack.rules.json`
- optional final `rewrite_pack.json`
- optional `tmp/.../rewrite_pack.validation.json`
- optional `tmp/.../rewrite_pack.used.json`
- optional `tmp/.../finalize_quality_run.json`
- `out/<base>.tex`
- optional `out/<base>.pdf`
- QA JSON from `quick_qa.py`

## Constraints

- Keep all claims grounded in the bank and selected evidence.
- Treat starter mode as a portable shell, not the highest-quality final wording path.
- In quality mode, follow the full sequence: prepare artifacts, author grounded `rewrite_pack.json`, validate it, then run the quality finalizer.
- Treat the rendered CV as a draft for human review, not final truth.
- Do not invent metrics, titles, dates, employers, or unsupported tooling.
- Stop after draft + QA and ask the user to review wording before any final submission.
