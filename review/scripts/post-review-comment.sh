#!/usr/bin/env bash
set -euo pipefail

# post-review-comment.sh — Post a review comment on a GitHub PR
# Usage: ./post-review-comment.sh <repo> <pr-number> <comment-body>
#
# Env vars required: GITHUB_TOKEN

REPO="${1:?Repo required (owner/name)}"
PR_NUMBER="${2:?PR number required}"
COMMENT_BODY="${3:?Comment body required}"

# Check if comment contains "Critical (blocks merge)"
if echo "$COMMENT_BODY" | grep -q "Critical (blocks merge)"; then
    EVENT="REQUEST_CHANGES"
else
    EVENT="COMMENT"
fi

# Post review via GitHub API
gh api \
    --method POST \
    "repos/$REPO/pulls/$PR_NUMBER/reviews" \
    -f body="$COMMENT_BODY" \
    -f event="$EVENT" \
    || echo "::warning::Failed to post review comment on PR #$PR_NUMBER"
