#!/usr/bin/env bash
set -euo pipefail

# Usage:
# ./scripts/publish_github.sh <repo-name> [public|private]
# Requires: git, gh (GitHub CLI) installed and authenticated (`gh auth login`) OR a logged-in git remote.

REPO_NAME=${1:-AgenteScalping_V2}
VISIBILITY=${2:-private}

if ! command -v git >/dev/null 2>&1; then
  echo "git not found; install git and retry" >&2
  exit 1
fi

if [ ! -d .git ]; then
  echo "Initializing local git repository..."
  git init
fi

git add -A
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  git commit -m "Prepare repository for publishing" || true
else
  git commit -m "Initial commit" || true
fi

if command -v gh >/dev/null 2>&1; then
  echo "Creating remote repo via gh: $REPO_NAME ($VISIBILITY)"
  gh repo create "$REPO_NAME" --$VISIBILITY --source=. --remote=origin --push || true
else
  echo "gh (GitHub CLI) not found. Please create a repository on GitHub named '$REPO_NAME' and add it as remote 'origin'."
  echo "Example: git remote add origin git@github.com:<youruser>/$REPO_NAME.git && git push -u origin main"
fi

echo "Done. Repository should be available on GitHub (check your account)."
