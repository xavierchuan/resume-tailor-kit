# Sample Bank

This directory is a demo-only legacy YAML bank for `resume-tailor-kit`.

Use it to:

- test the CLI pipeline end to end
- inspect the expected structured output format
- compare the older YAML shape against the markdown-first `bank-template/`
- exercise starter mode without any private historical CV assets

The sample content is intentionally shaped around technical-role workflows. It does not mean the repo already supports every profession out of the box.
It also does not represent the highest-quality output path; quality mode is meant to layer in your own external historical CV variants.

Do not use it as your default working bank. Your own local bank should be created with:

```bash
python3 scripts/init_bank.py --target bank
```

The public `bank/` directory in this repo stays blank and gitignored on purpose.
