# Contributing to `resume-tailor-kit`

Thanks for contributing.

This repository is an open-source, local-agent starter kit for grounded resume tailoring. It is contributor-oriented and currently optimized for `AI / data / software / quant-adjacent` roles rather than for every profession.

## What good contributions look like

Good contributions usually improve one of these areas:

- role routing and archetype coverage
- starter-mode sample quality and demo clarity
- template mapping and renderer behavior
- rewrite artifact quality and QA checks
- Codex / Claude Code skill and agent UX
- docs that make the repo easier to understand or contribute to

## Before you open an issue or PR

- Keep the public scope truthful. Do not market the repo as a universal CV tool.
- Do not commit private candidate data, private CVs, employer names, or personal snippets you would not want public.
- Keep `bank/` local-only. Public examples belong under `examples/`.
- Prefer grounded, deterministic improvements over “AI magic” wording.

## Local setup

```bash
python3 -m pip install -r requirements.txt
```

Starter-mode sanity check:

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

Optional diagnostics:

```bash
python3 scripts/quick_qa.py \
  --pdf out/Sample_Candidate_Data_Analyst.pdf \
  --output-dir out \
  --base-name Sample_Candidate_Data_Analyst \
  --job-card tmp/starter/job_card.json \
  --unsupported-count 0
```

## If you extend role coverage

When adding a new role family or archetype, update the full chain rather than only one file:

- routing logic and archetype config
- selection heuristics
- template mapping
- docs describing current fit
- sample/demo assets when needed

If your contribution changes public scope, update the README wording to keep the repo honest about what works best right now.

## Pull request expectations

Please include:

- a short explanation of the problem and the chosen fix
- any README or skill/agent doc updates needed
- the commands you ran locally
- confirmation that no private candidate data was added

The PR should stay reviewable. Prefer focused changes over bundling unrelated improvements.
