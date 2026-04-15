#!/usr/bin/env bash
set -euo pipefail

# setup-project.sh — Verify ops-platform connectivity for a project
# Usage: ./scripts/setup-project.sh <project-name>

PROJECT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIGS_DIR="$SCRIPT_DIR/../configs"
PASS="✅"
FAIL="❌"
WARN="⚠️"
ERRORS=0

if [[ -z "$PROJECT" ]]; then
    echo "Usage: ./scripts/setup-project.sh <project-name>"
    echo "Available configs:"
    ls "$CONFIGS_DIR"/*.yml 2>/dev/null | xargs -I{} basename {} .yml | grep -v defaults
    exit 1
fi

echo "🔍 Verifying ops-platform setup for: $PROJECT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Config exists
CONFIG_FILE="$CONFIGS_DIR/$PROJECT.yml"
if [[ -f "$CONFIG_FILE" ]]; then
    if python3 -c "import yaml; yaml.safe_load(open('$CONFIG_FILE'))" 2>/dev/null; then
        echo "$PASS Config: $CONFIG_FILE (valid YAML)"
    else
        echo "$FAIL Config: $CONFIG_FILE (invalid YAML)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "$FAIL Config: $CONFIG_FILE not found"
    echo "   Create it by copying defaults.yml: cp $CONFIGS_DIR/defaults.yml $CONFIG_FILE"
    ERRORS=$((ERRORS + 1))
fi

# 2. CloudWatch connectivity
if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
    REGION=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('monitoring',{}).get('cloudwatch_region','us-east-1'))" 2>/dev/null || echo "us-east-1")
    if aws cloudwatch list-metrics --region "$REGION" --max-items 1 &>/dev/null; then
        echo "$PASS CloudWatch: Connected (region: $REGION)"
    else
        echo "$FAIL CloudWatch: Cannot connect to region $REGION"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "$WARN CloudWatch: AWS_ACCESS_KEY_ID not set (skip if not using CloudWatch)"
fi

# 3. Jira connectivity
if [[ -n "${JIRA_API_TOKEN:-}" && -n "${JIRA_EMAIL:-}" && -n "${JIRA_URL:-}" ]]; then
    JIRA_KEY=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('notifications',{}).get('jira_project_key',''))" 2>/dev/null || echo "")
    if [[ -n "$JIRA_KEY" ]]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
            "$JIRA_URL/rest/api/3/project/$JIRA_KEY" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            echo "$PASS Jira: Project $JIRA_KEY accessible"
        else
            echo "$FAIL Jira: Cannot access project $JIRA_KEY (HTTP $HTTP_CODE)"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo "$WARN Jira: No jira_project_key in config"
    fi
else
    echo "$WARN Jira: JIRA_API_TOKEN/JIRA_EMAIL/JIRA_URL not set"
fi

# 4. Telegram bot
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=🔗 Ops platform connected to $PROJECT" 2>/dev/null || echo '{"ok":false}')
    if echo "$RESPONSE" | python3 -c "import sys,json; assert json.load(sys.stdin)['ok']" 2>/dev/null; then
        echo "$PASS Telegram: Test message sent"
    else
        echo "$FAIL Telegram: Cannot send message (check bot token and chat ID)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "$WARN Telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set"
fi

# 5. Anthropic API
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "x-api-key: $ANTHROPIC_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d '{"model":"claude-haiku-4-5-20251001","max_tokens":10,"messages":[{"role":"user","content":"ping"}]}' \
        "https://api.anthropic.com/v1/messages" 2>/dev/null || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo "$PASS Anthropic API: Key valid"
    else
        echo "$FAIL Anthropic API: Invalid key or API error (HTTP $HTTP_CODE)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "$WARN Anthropic API: ANTHROPIC_API_KEY not set"
fi

# 6. GitHub repo
REPO=$(python3 -c "import yaml; c=yaml.safe_load(open('$CONFIG_FILE')); print(c.get('project',{}).get('repo',''))" 2>/dev/null || echo "")
if [[ -n "$REPO" ]] && command -v gh &>/dev/null; then
    if gh repo view "$REPO" &>/dev/null; then
        echo "$PASS GitHub: Repo $REPO accessible"
    else
        echo "$FAIL GitHub: Cannot access $REPO (check gh auth)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo "$WARN GitHub: gh CLI not available or no repo configured"
fi

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ $ERRORS -eq 0 ]]; then
    echo "$PASS All checks passed! $PROJECT is ready for ops-platform."
else
    echo "$FAIL $ERRORS check(s) failed. Fix the issues above and re-run."
    exit 1
fi
