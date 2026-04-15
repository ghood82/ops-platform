# Ops Platform

Shared AI infrastructure for all projects. Provides:

- **Triple AI Code Review** — 3 parallel Claude passes on every PR
- **Six-Phase CI/CD Pipeline** — Verify → Build Dev → Test Dev → Deploy Prod → Test Prod → Release
- **Self-Healing Monitoring** — Daily health checks, error triage, auto-ticketing
- **Auto-Rollback** — Circuit breaker reverts bad deploys within 5 minutes
- **AI Ops** — Release notes, deploy notifications, weekly digest

## Quick Start

1. Add a config file to `configs/<your-project>.yml`
2. Add required secrets to your GitHub repo
3. Copy the workflow template to your repo's `.github/workflows/ops.yml`
4. Run `scripts/setup-project.sh <your-project>` to verify

See `docs/superpowers/specs/2026-04-15-ops-platform-design.md` for the full design spec.
