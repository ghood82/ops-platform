#!/usr/bin/env bash
set -euo pipefail

# run-review-pass.sh — Run a single AI review pass on a PR diff
# Usage: ./run-review-pass.sh <pass-name> <model-id> <prompt-file> <diff-file> [custom-rules]
#
# Env vars required: ANTHROPIC_API_KEY
# Outputs: review comment body to stdout

PASS_NAME="${1:?Pass name required (code-quality|security|dependencies)}"
MODEL_ID="${2:?Model ID required}"
PROMPT_FILE="${3:?Prompt file path required}"
DIFF_FILE="${4:?Diff file path required}"
CUSTOM_RULES="${5:-}"

TIMEOUT=60
MAX_RETRIES=1

# Read prompt template and inject custom rules
PROMPT=$(cat "$PROMPT_FILE")
if [[ -n "$CUSTOM_RULES" ]]; then
    PROMPT="${PROMPT//\{\{CUSTOM_RULES\}\}/Additional project-specific rules:
$CUSTOM_RULES}"
else
    PROMPT="${PROMPT//\{\{CUSTOM_RULES\}\}/}"
fi

# Read diff
DIFF=$(cat "$DIFF_FILE")
DIFF_SIZE=${#DIFF}

# Truncate if over 150KB (context limit safety)
if [[ $DIFF_SIZE -gt 153600 ]]; then
    echo "::warning::Diff is ${DIFF_SIZE} bytes, truncating to 150KB for $PASS_NAME pass"
    DIFF="${DIFF:0:153600}

... [diff truncated at 150KB — review covers partial changes]"
fi

# Build API request
REQUEST=$(jq -n \
    --arg model "$MODEL_ID" \
    --arg system "$PROMPT" \
    --arg diff "$DIFF" \
    '{
        model: $model,
        max_tokens: 4096,
        system: $system,
        messages: [{role: "user", content: ("Review this pull request diff:\n\n" + $diff)}]
    }')

# Call Anthropic API with retry
ATTEMPT=0
while [[ $ATTEMPT -le $MAX_RETRIES ]]; do
    RESPONSE=$(curl -s --max-time "$TIMEOUT" \
        -H "x-api-key: $ANTHROPIC_API_KEY" \
        -H "anthropic-version: 2023-06-01" \
        -H "content-type: application/json" \
        -d "$REQUEST" \
        "https://api.anthropic.com/v1/messages" 2>/dev/null) || true

    # Check for valid response
    if echo "$RESPONSE" | jq -e '.content[0].text' &>/dev/null; then
        echo "$RESPONSE" | jq -r '.content[0].text'
        exit 0
    fi

    ATTEMPT=$((ATTEMPT + 1))
    if [[ $ATTEMPT -le $MAX_RETRIES ]]; then
        echo "::warning::$PASS_NAME pass attempt $ATTEMPT failed, retrying in 4s..."
        sleep 4
    fi
done

# All retries exhausted — output fallback
echo "## AI Code Review — ${PASS_NAME}

⚠️ **Review unavailable** — Claude API did not respond after $((MAX_RETRIES + 1)) attempts. Merge at your own discretion.

Error details: $(echo "$RESPONSE" | jq -r '.error.message // "No response"' 2>/dev/null || echo "Connection timeout")"
