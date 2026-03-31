# Rewrite Pack Schema

A `rewrite_pack.json` is the grounded final input for quality-mode rendering.

## Required top-level fields

- `role`
  - `company`
  - `role`
  - `family`
  - `archetype`
- `coverage_terms`
- `profile`
  - `short`
  - `normal`
  - `dense`
- `skills`
  - `normal`
  - `dense`
- `projects`
- `extra_projects`
- `density_hints`
- `provenance_check`
- `unsupported_count`

## Line-item contract

Every final text line should be an object with:

- `text`
- `provenance`
- `source_type`

Optional metadata:

- `source_tokens`
- `source_role_tokens`

`provenance` must be non-empty for every final line that appears in the rendered CV.

## Project contract

Each project in `projects` or `extra_projects` should include:

- `project_id`
- `title`
- `stack`
- optional `link`
- `bullets`
- `extra_bullets`

`title`, `stack`, `bullets[*]`, and `extra_bullets[*]` use the line-item contract.

If `link` is present, it must include:

- `label`
- `url`
- `provenance`
- `source_type`

## Validation rules

- `profile.short|normal|dense` must be non-empty lists.
- `skills.normal|dense` must be non-empty lists.
- `projects` must be a non-empty list.
- `unsupported_count` must be `0` for a pack to pass validation.
- `rewrite_pack.rules.json` is a speed-first fallback, not the highest-quality final pack.
