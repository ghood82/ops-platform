"""Config loader for ops-platform.

Loads per-project YAML configs with defaults merging, env var interpolation,
and pydantic validation.
"""
import os
import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator


ENV_VAR_PATTERN = re.compile(r"\$\{(\w+)\}")


def _interpolate_env_vars(value: str) -> str:
    """Replace ${VAR} patterns with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    if isinstance(value, str):
        return ENV_VAR_PATTERN.sub(replacer, value)
    return value


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override wins for leaf values."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _interpolate_dict(d: dict) -> dict:
    """Recursively interpolate env vars in all string values."""
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = _interpolate_dict(value)
        elif isinstance(value, list):
            result[key] = [
                _interpolate_env_vars(item) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, str):
            result[key] = _interpolate_env_vars(value)
        else:
            result[key] = value
    return result


class ThresholdsConfig(BaseModel):
    error_rate_increase: int = 50
    p95_latency_increase: int = 100
    critical_endpoints: list[str] = ["/health"]
    min_success_rate: int = 95


class CircuitBreakerConfig(BaseModel):
    monitoring_window: int = 300
    poll_interval: int = 60
    mode: Literal["enforce", "monitor"] = "enforce"
    thresholds: ThresholdsConfig = ThresholdsConfig()
    rollback_method: Literal["ssh", "vercel", "cloudflare"] = "vercel"

    @field_validator("poll_interval")
    @classmethod
    def poll_interval_minimum(cls, v):
        if v < 10:
            raise ValueError("poll_interval must be at least 10 seconds")
        return v


class ProjectConfig(BaseModel):
    name: str = "default"
    repo: str = "user/repo"
    deploy_target: Literal["lightsail", "vercel", "cloudflare"] = "vercel"
    prod_url: str = "https://example.com"


class MonitoringConfig(BaseModel):
    log_source: Literal["cloudwatch", "vercel", "file"] = "cloudwatch"
    cloudwatch_log_group: str = ""
    cloudwatch_region: str = "us-east-1"
    vercel_team_id: str = ""
    vercel_project_id: str = ""


class CIConfig(BaseModel):
    has_staging: bool = False
    test_command: str = "pytest"
    e2e_command: str = ""
    lint_command: str = "npm run lint"
    build_command: str = "npm run build"
    coverage_minimum: int = 50


class ReviewConfig(BaseModel):
    hipaa_checks: bool = False
    org_id_scoping: bool = False
    custom_rules: list[str] = []


class NotificationsConfig(BaseModel):
    telegram_chat_id: str = ""
    jira_project_key: str = ""


class TriageConfig(BaseModel):
    schedule: str = "0 */4 * * *"
    severity_dimensions: list[str] = [
        "frequency", "recency", "user_impact", "blast_radius", "recurrence"
    ]


class ModelsConfig(BaseModel):
    code_quality: str = "claude-sonnet-4-6-20250514"
    security: str = "claude-opus-4-6-20250514"
    dependencies: str = "claude-haiku-4-5-20251001"
    health_analysis: str = "claude-sonnet-4-6-20250514"
    release_notes: str = "claude-haiku-4-5-20251001"


class OpsConfig(BaseModel):
    project: ProjectConfig = ProjectConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    ci: CIConfig = CIConfig()
    review: ReviewConfig = ReviewConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    notifications: NotificationsConfig = NotificationsConfig()
    triage: TriageConfig = TriageConfig()
    models: ModelsConfig = ModelsConfig()


def load_defaults(configs_dir: Path) -> OpsConfig:
    """Load defaults.yml from the configs directory."""
    defaults_path = configs_dir / "defaults.yml"
    if not defaults_path.exists():
        raise FileNotFoundError(f"defaults.yml not found in {configs_dir}")
    with open(defaults_path) as f:
        raw = yaml.safe_load(f)
    raw = _interpolate_dict(raw)
    return OpsConfig(**raw)


def load_project_config(project_name: str, configs_dir: Path) -> OpsConfig:
    """Load a project config, merging over defaults."""
    defaults_path = configs_dir / "defaults.yml"
    if not defaults_path.exists():
        raise FileNotFoundError(f"defaults.yml not found in {configs_dir}")
    with open(defaults_path) as f:
        base = yaml.safe_load(f)

    project_path = configs_dir / f"{project_name}.yml"
    if project_path.exists():
        with open(project_path) as f:
            override = yaml.safe_load(f) or {}
        merged = _deep_merge(base, override)
    else:
        merged = base

    merged = _interpolate_dict(merged)
    return OpsConfig(**merged)
