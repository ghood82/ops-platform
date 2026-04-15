"""Tests for config loading and validation."""
import os
import tempfile
from pathlib import Path

import pytest
import yaml

from triage_engine.config import (
    ProjectConfig,
    MonitoringConfig,
    CIConfig,
    ReviewConfig,
    CircuitBreakerConfig,
    NotificationsConfig,
    TriageConfig,
    load_project_config,
    load_defaults,
)


@pytest.fixture
def defaults_dir(tmp_path):
    """Create a temp configs dir with defaults.yml."""
    defaults = {
        "project": {
            "name": "default",
            "repo": "user/repo",
            "deploy_target": "vercel",
            "prod_url": "https://example.com",
        },
        "monitoring": {
            "log_source": "cloudwatch",
            "cloudwatch_log_group": "",
            "cloudwatch_region": "us-east-1",
        },
        "ci": {
            "has_staging": False,
            "test_command": "pytest",
            "e2e_command": "",
            "lint_command": "npm run lint",
            "build_command": "npm run build",
            "coverage_minimum": 50,
        },
        "review": {
            "hipaa_checks": False,
            "org_id_scoping": False,
            "custom_rules": [],
        },
        "circuit_breaker": {
            "monitoring_window": 300,
            "poll_interval": 60,
            "mode": "enforce",
            "thresholds": {
                "error_rate_increase": 50,
                "p95_latency_increase": 100,
                "critical_endpoints": ["/health"],
                "min_success_rate": 95,
            },
            "rollback_method": "vercel",
        },
        "notifications": {
            "telegram_chat_id": "",
            "jira_project_key": "",
        },
        "triage": {
            "schedule": "0 */4 * * *",
            "severity_dimensions": [
                "frequency",
                "recency",
                "user_impact",
                "blast_radius",
                "recurrence",
            ],
        },
        "models": {
            "code_quality": "claude-sonnet-4-6-20250514",
            "security": "claude-opus-4-6-20250514",
            "dependencies": "claude-haiku-4-5-20251001",
            "health_analysis": "claude-sonnet-4-6-20250514",
            "release_notes": "claude-haiku-4-5-20251001",
        },
    }
    (tmp_path / "defaults.yml").write_text(yaml.dump(defaults))
    return tmp_path


@pytest.fixture
def rdc_config_dir(defaults_dir):
    """Create an RDC project config on top of defaults."""
    rdc = {
        "project": {
            "name": "RDC Platform",
            "repo": "ghood82/rdc-scaled",
            "deploy_target": "lightsail",
            "prod_url": "https://app.scaledservicesgroup.com",
        },
        "monitoring": {
            "cloudwatch_log_group": "/rdc/backend",
            "cloudwatch_region": "us-west-2",
        },
        "ci": {
            "has_staging": True,
            "coverage_minimum": 50,
        },
        "review": {
            "hipaa_checks": True,
            "org_id_scoping": True,
            "custom_rules": [
                "Never log PHI/PII",
                "AI calls must run in background",
                "All queries must scope to organization_id",
            ],
        },
        "circuit_breaker": {
            "rollback_method": "ssh",
            "thresholds": {
                "critical_endpoints": ["/api/v1/health", "/api/v1/auth/me"],
            },
        },
        "notifications": {
            "telegram_chat_id": "${TELEGRAM_CHAT_ID}",
            "jira_project_key": "RDC",
        },
    }
    (defaults_dir / "rdc.yml").write_text(yaml.dump(rdc))
    return defaults_dir


class TestLoadDefaults:
    def test_loads_defaults_yml(self, defaults_dir):
        config = load_defaults(defaults_dir)
        assert config.project.name == "default"
        assert config.ci.coverage_minimum == 50

    def test_missing_defaults_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_defaults(tmp_path)


class TestLoadProjectConfig:
    def test_merges_project_over_defaults(self, rdc_config_dir):
        config = load_project_config("rdc", rdc_config_dir)
        assert config.project.name == "RDC Platform"
        assert config.project.deploy_target == "lightsail"
        # Inherited from defaults
        assert config.ci.lint_command == "npm run lint"

    def test_project_overrides_nested(self, rdc_config_dir):
        config = load_project_config("rdc", rdc_config_dir)
        assert config.review.hipaa_checks is True
        assert config.circuit_breaker.rollback_method == "ssh"

    def test_critical_endpoints_overridden(self, rdc_config_dir):
        config = load_project_config("rdc", rdc_config_dir)
        assert "/api/v1/health" in config.circuit_breaker.thresholds.critical_endpoints

    def test_missing_project_config_uses_defaults(self, defaults_dir):
        config = load_project_config("nonexistent", defaults_dir)
        assert config.project.name == "default"

    def test_env_var_interpolation(self, rdc_config_dir, monkeypatch):
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
        config = load_project_config("rdc", rdc_config_dir)
        assert config.notifications.telegram_chat_id == "12345"


class TestConfigValidation:
    def test_invalid_deploy_target_raises(self, defaults_dir):
        bad = {"project": {"deploy_target": "heroku"}}
        (defaults_dir / "bad.yml").write_text(yaml.dump(bad))
        with pytest.raises(ValueError):
            load_project_config("bad", defaults_dir)

    def test_poll_interval_minimum(self, defaults_dir):
        bad = {"circuit_breaker": {"poll_interval": 5}}
        (defaults_dir / "bad.yml").write_text(yaml.dump(bad))
        with pytest.raises(ValueError):
            load_project_config("bad", defaults_dir)


class TestModelConfig:
    def test_model_ids_loaded(self, defaults_dir):
        config = load_defaults(defaults_dir)
        assert config.models.security == "claude-opus-4-6-20250514"
        assert config.models.release_notes == "claude-haiku-4-5-20251001"
