# resume-tailor-kit

`resume-tailor-kit` is a local-agent, BYO-AI starter kit for grounded resume tailoring.

Use it when you want Codex or Claude Code to help you tailor resumes from a reusable evidence bank, while the repository scripts keep routing, selection, rendering, and QA deterministic.

Best for AI, data, software, and quant-adjacent roles. Built for local-agent users who want grounded, repeatable tailoring from their own evidence bank. This is not a consumer no-code tool yet.

This repo does **not** ship its own chat provider or hosted UI:

- AI comes from your local agent environment such as Codex or Claude Code
- the repo provides script-backed workflow and file formats
- it is not a website product or a consumer GUI

This public repo includes both:

- a Codex skill wrapper in `codex-skill/resume-tailor-kit/`
- a Claude Code agent wrapper in `.claude/agents/`

## Current fit

| Status | Role families / workflows |
| --- | --- |
| Best fit | Software Engineer; Backend / Full-stack / Platform; Data Analyst / Data Engineer / Data Scientist; AI Engineer / Applied AI / LLM tooling; quant-adjacent technical roles |
| Can extend with custom routing/templates | Product; Operations; Consulting; General business analyst; Finance non-quant; Marketing / Growth |
| Not a fit right now | Design / UX portfolio workflows; legal / medical / academic CVs; Sales / BD resume styles; 2+ page CV or portfolio-driven workflows |

## Contribute

Contributors are the primary audience for this repo.

Start here:

- [Contribution guide](./CONTRIBUTING.md)
- [Bug report template](./.github/ISSUE_TEMPLATE/bug_report.md)
- [Feature / role-family request template](./.github/ISSUE_TEMPLATE/feature_request.md)

## Where contributions help

- more role families and archetypes beyond the current technical-first scope
- better starter-mode sample banks and demo outputs
- richer template mapping and renderer presets
- stronger selection, rewrite, and QA heuristics
- better skill / agent UX and docs

## What this repo does

- turns a full JD into a structured `job_card.json` with both coarse `family` and finer `archetype` routing
- selects grounded profile lines, skills, and project bullets from a reusable bank
- can optionally extract `variant_bank.json` from your external historical `.tex` CV corpus
- can optionally prepare `rewrite_seed.json` and `rewrite_pack.rules.json` for higher-quality rewrites
- validates a grounded final `rewrite_pack.json` against a documented schema and provenance contract
- renders a one-page LaTeX CV draft from either `selected.json` or `rewrite_pack.json`
- can run a multi-preset quality finalizer that renders multiple candidates and chooses the best QA result
- runs output-contract, page-count, layout, keyword-coverage, and scoring QA

## What this repo does not do

- it does not replace human review
- it does not invent unsupported claims
- it does not manage your provider API keys
- it does not store candidate data remotely
- it is not for everyone yet, and it does not work for every profession out of the box
- it assumes you can use Codex or Claude Code, local CLI commands, and a maintained Markdown evidence bank

## Two modes

### Starter mode

Use starter mode when you want a public, portable, easy-to-demo flow:

- no external historical CV corpus required
- runs on `bank/` or `examples/sample_bank/`
- good for demos, repo distribution, and quick drafts
- quality is intentionally more generic

Starter mode still produces rewrite artifacts, but they are built from the public bank only.

### Quality mode

Use quality mode when you want something closer to your private production workflow:

- takes an external historical CV root via `--cv-root`, or a prebuilt `--variant-bank`
- prepares `variant_bank.json`, `rewrite_seed.json`, and `rewrite_pack.rules.json`
- classifies the JD with both `family` and `archetype`, then uses that routing to shape selection and rewrite guidance
- expects a local agent or human to produce the final `rewrite_pack.json`
- keeps private CVs, historical variants, and strong role-specific data outside the repo

The repo stays public; your higher-quality assets stay private.

## Why the scope is narrow for now

The built-in routing currently centers on `quant`, `ai`, `data`, and `software`. Supporting more role families is possible, but it requires extending:

- job-family routing
- template mapping
- skills blocks
- evidence tags and selection logic

PRs and community extensions are welcome. The narrow scope is intentional for now so the public repo stays truthful and predictable.

Current built-in archetypes:

- `data_analyst`
- `data_scientist`
- `data_engineer`
- `applied_ai`
- `backend_platform`
- `software_general`
- `quant_dev`

## Repo shape

- `bank-template/` - blank markdown-first bank template for your own local data
- `bank/` - your local working bank, intentionally blank and gitignored
- `examples/sample_bank/` - demo-only legacy YAML bank
- `examples/jd_data_analyst.txt` - example JD input
- `scripts/compile_markdown_bank.py` - compile a markdown bank to runtime bank files
- `scripts/pipeline_fast.py` - starter/quality pipeline that writes job-card, selection, variant-bank, and rewrite artifacts
- `scripts/build_variant_bank.py` - extract reusable profile/skills/project variants from external historical CVs
- `scripts/build_rewrite_artifacts.py` - prepare rewrite seed + rules fallback pack
- `scripts/validate_rewrite_pack.py` - validate the final grounded rewrite pack before rendering
- `scripts/finalize_quality_run.py` - render multiple quality-mode presets, score them, and select the best output
- `scripts/render_resume.py` - render a deterministic LaTeX draft from `selected.json` or `rewrite_pack.json`
- `scripts/quick_qa.py` - validate one-page output, file contract, layout, keyword coverage, and candidate score
- `docs/rewrite-pack-schema.md` - schema and provenance contract for the final grounded `rewrite_pack.json`
- `codex-skill/resume-tailor-kit/SKILL.md` - Codex skill wrapper
- `.claude/agents/resume-tailor-kit.md` - Claude Code agent wrapper

## Quick start

### 0. Install the Python dependency

```bash
python3 -m pip install -r requirements.txt
```

### 1. Demo starter mode with the public sample bank

```bash
python3 scripts/pipeline_fast.py \
  --jd-file examples/jd_data_analyst.txt \
  --bank-dir examples/sample_bank \
  --cache-dir tmp/cache \
  --artifacts-dir tmp/starter

python3 scripts/render_resume.py \
  --bank-dir examples/sample_bank \
  --rewrite-pack tmp/starter/rewrite_pack.used.json \
  --output out/Sample_Candidate_Data_Analyst.tex \
  --compile
```

If you want the old minimal path, `render_resume.py --selected ...` still works.

The public sample bank is intentionally lightweight. Treat the starter quick start as a **preview draft path**, not as the strongest QA benchmark.

Optional diagnostic check:

```bash
python3 scripts/quick_qa.py \
  --pdf out/Sample_Candidate_Data_Analyst.pdf \
  --output-dir out \
  --base-name Sample_Candidate_Data_Analyst \
  --job-card tmp/starter/job_card.json \
  --unsupported-count 0
```

### 2. Initialize your own markdown bank

```bash
python3 scripts/init_bank.py --target bank
```

Then fill the minimum required files:

- `bank/profile.md`
- at least one story in `bank/stories/`
- at least one evidence bullet in `bank/evidence/`
- `bank/skills.md`

The pipeline auto-compiles markdown banks to runtime files under `.build/`.

### 3. Install the Codex skill

```bash
python3 scripts/install_codex_skill.py --force
```

Then open this repo in Codex and use the installed `resume-tailor-kit` skill against `bank/` or `examples/sample_bank/`.

### 4. Install the Claude Code agent

```bash
python3 scripts/install_claude_agent.py --force
```

Then open this repo in Claude Code and invoke the `resume-tailor-kit` agent from the same workspace.

## FAQ

### Can anyone use this?

Not really, at least not yet. This repo is best for power users who are comfortable with Codex or Claude Code, local command-line workflows, and maintaining a Markdown evidence bank. It is not a no-code consumer product.

### Which roles does it support best right now?

The best fit is AI, data, software, and quant-adjacent technical roles. You can extend it to adjacent business or operations workflows, but that requires custom routing, template mapping, skills blocks, and evidence-tag work.

## Bank format

The public default is markdown-first.

Your local bank should look like:

- `profile.md`
- `stories/`
- `evidence/`
- `skills.md`
- `templates.md`

Each story and evidence file is a standalone Markdown document with YAML frontmatter plus body content, so it stays editable by hand and parseable by scripts.

The repo still supports legacy YAML banks for compatibility, which is why `examples/sample_bank/` works without conversion. That public sample is a technical-role demo only, not evidence that the repo already covers every profession.

## Minimal CLI workflow for your own bank

Once your bank is filled, run either:

```bash
python3 scripts/pipeline_fast.py \
  --bank-dir bank \
  --jd-file path/to/jd.txt \
  --cache-dir tmp/cache \
  --artifacts-dir tmp/run
```

or:

```bash
python3 scripts/pipeline_fast.py \
  --bank-dir bank \
  --jd-text "full JD pasted here" \
  --cache-dir tmp/cache \
  --artifacts-dir tmp/run
```

Then render and QA, either from selected content:

```bash
python3 scripts/render_resume.py \
  --bank-dir bank \
  --selected tmp/run/selected.json \
  --output out/My_Target_Role.tex \
  --compile

python3 scripts/quick_qa.py \
  --pdf out/My_Target_Role.pdf \
  --output-dir out \
  --base-name My_Target_Role \
  --job-card tmp/run/job_card.json
```

or from the rules fallback pack:

```bash
python3 scripts/render_resume.py \
  --bank-dir bank \
  --rewrite-pack tmp/run/rewrite_pack.used.json \
  --output out/My_Target_Role.tex \
  --compile
```

## Quality mode with private historical CVs

This is the intended path when you want output quality closer to your private workflow without committing private assets.

### 1. Prepare artifacts from your public bank + private historical `.tex` files

```bash
python3 scripts/pipeline_fast.py \
  --bank-dir bank \
  --cv-root /absolute/path/to/private/cv-root \
  --jd-file path/to/jd.txt \
  --cache-dir tmp/cache \
  --artifacts-dir tmp/quality \
  --prepare-only \
  --rewrite-mode agent
```

This writes:

- `tmp/quality/job_card.json`
- `tmp/quality/selected.json`
- `tmp/quality/variant_bank.json`
- `tmp/quality/rewrite_seed.json`
- `tmp/quality/rewrite_pack.rules.json`

### 2. Ask your local agent to write the final rewrite pack

Use `rewrite_seed.json` and `rewrite_pack.rules.json` as grounded inputs, then save a final `rewrite_pack.json` somewhere local. The repo does not auto-generate the highest-quality final wording for you.

Read [`docs/rewrite-pack-schema.md`](./docs/rewrite-pack-schema.md) first so the final pack follows the expected structure, provenance contract, and `unsupported_count` rules.

### 3. Validate the final rewrite pack

```bash
python3 scripts/validate_rewrite_pack.py \
  --rewrite-pack path/to/rewrite_pack.json \
  --output tmp/quality/rewrite_pack.validation.json
```

### 4. Finalize the quality run

```bash
python3 scripts/finalize_quality_run.py \
  --bank-dir bank \
  --artifacts-dir tmp/quality \
  --rewrite-pack path/to/rewrite_pack.json \
  --output-dir out \
  --base-name My_Target_Role
```

This writes:

- `tmp/quality/rewrite_pack.validation.json`
- `tmp/quality/rewrite_pack.used.json`
- `tmp/quality/finalize_quality_run.json`
- `out/My_Target_Role.tex`
- optional `out/My_Target_Role.pdf`

The finalizer renders the fixed `balanced`, `dense`, and `expand_dense` presets, runs QA on each candidate, then keeps the best passing output.

### Optional fast fallback inside quality mode

If you want a deterministic draft before doing agent rewrite:

```bash
python3 scripts/pipeline_fast.py \
  --bank-dir bank \
  --cv-root /absolute/path/to/private/cv-root \
  --jd-file path/to/jd.txt \
  --cache-dir tmp/cache \
  --artifacts-dir tmp/quality-fast \
  --rewrite-mode rules

python3 scripts/render_resume.py \
  --bank-dir bank \
  --rewrite-pack tmp/quality-fast/rewrite_pack.used.json \
  --output out/My_Target_Role.tex \
  --compile
```

## Truthfulness boundary

This repo is designed to help with routing and evidence selection, not to replace review. Treat every generated resume as a draft that still needs human checks for:

- truthfulness
- unsupported claims
- role voice consistency
- page density and readability

## Requirements

- Python 3.10+
- `python3 -m pip install -r requirements.txt`
- `tectonic` for LaTeX compile when using `--compile`
- `pdfinfo` for page-count QA
- `pdftoppm` for layout preview and whitespace QA
- `pdftotext` for keyword-coverage QA

## License

MIT
