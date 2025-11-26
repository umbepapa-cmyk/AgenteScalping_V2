#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/create_github_repo.sh <repo-name> [private|public]
# This script reads GITHUB_TOKEN from the environment (or from .env),
# creates a GitHub repository in the authenticated user's account via REST API,
# then configures the remote and pushes the current repo to GitHub.
#
# SECURITY: keep your GITHUB_TOKEN secret. Prefer using gh CLI and gh auth login.

REPO_NAME=${1:-AgenteScalping_V2}
VISIBILITY=${2:-private}

# load .env if present
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a
  . .env
  set +a
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN not set in environment or .env" >&2
  echo "Set GITHUB_TOKEN in your environment or in .env and retry." >&2
  exit 2
fi

API_URL="https://api.github.com"

echo "Retrieving authenticated user..."
OWNER=$(curl -s -H "Authorization: token ${GITHUB_TOKEN}" ${API_URL}/user | jq -r .login)
if [ -z "$OWNER" ] || [ "$OWNER" = "null" ]; then
  echo "Failed to determine authenticated GitHub user. Check token scope." >&2
  exit 3
fi
echo "Authenticated as $OWNER"

echo "Creating repository $OWNER/$REPO_NAME (visibility=$VISIBILITY)"
CREATE_RESP=$(curl -s -o /dev/stderr -w "%{http_code}" -X POST -H "Authorization: token ${GITHUB_TOKEN}" -H "Accept: application/vnd.github+json" ${API_URL}/user/repos -d "{\"name\": \"${REPO_NAME}\", \"private\": $( [ "$VISIBILITY" = "private" ] && echo true || echo false ) }")
if [ "$CREATE_RESP" -ge 400 ]; then
  echo "Repository creation may have failed (HTTP $CREATE_RESP). Check server output above." >&2
fi

REMOTE_URL="https://github.com/${OWNER}/${REPO_NAME}.git"

if [ ! -d .git ]; then
  echo "Initializing local git repository..."
  git init
fi
git add -A || true
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git commit -m "Prepare repository for publishing" || true
else
  git commit -m "Initial commit" || true
fi

echo "Pushing to remote $REMOTE_URL"
echo "NOTE: this will use the token to authenticate during the push."
GIT_REMOTE_AUTH_URL="https://${GITHUB_TOKEN}@github.com/${OWNER}/${REPO_NAME}.git"
git remote remove origin >/dev/null 2>&1 || true
git remote add origin "$REMOTE_URL"
# push using token in URL to authenticate
git push -u "$GIT_REMOTE_AUTH_URL" main || git push -u "$GIT_REMOTE_AUTH_URL" master

echo "Repository created and pushed: https://github.com/${OWNER}/${REPO_NAME}"
