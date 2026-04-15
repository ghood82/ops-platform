# Ops Platform

Shared AI infrastructure providing reusable CI/CD workflows, AI code review, self-healing monitoring, auto-rollback, and operational automation.

## Architecture
- `configs/` — Per-project YAML config files. `defaults.yml` is the base; project files override.
- `triage-engine/` — Python package for health checks, error triage, ticket management.
- `rollback/` — Circuit breaker and deploy verification.
- `notifications/` — Telegram alert formatting and routing.
- `.github/workflows/` — Reusable GitHub Actions workflows consumed by other repos.
- `scripts/` — Onboarding and setup scripts.

## Conventions
- All secrets come from GitHub Actions secrets in consuming repos. Never hardcode secrets.
- Config files must not contain sensitive values — use `${ENV_VAR}` syntax for secrets.
- Python code uses pydantic for validation, pytest for testing.
- Reusable workflows use tagged releases (@v1, @v2). Never reference @main from consuming repos.

## Model IDs
- Opus 4.6: `claude-opus-4-6-20250514`
- Sonnet 4.6: `claude-sonnet-4-6-20250514`
- Haiku 4.5: `claude-haiku-4-5-20251001`
