#!/usr/bin/env bash
set -euo pipefail

# --- Config (edit if you rename repo/remote) ---
EXPECTED_REPO_NAME="_MonacoVIEWER"
EXPECTED_REMOTE_URL="git@github.com:jacobmentalconstruct/_MonacoVIEWER.git"  # or https URL
EXPECTED_BRANCH="main"

# --- Args ---
REPO_DIR="${1:-.}"             # optional: path to repo; default = current folder
shift || true
COMMIT_MSG="${*:-chore: quick update}"  # optional: commit message after repo path

# --- Resolve repo & sanity checks ---
cd "$REPO_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[x] Not a git repo: $(pwd)"; exit 1
fi

ROOT="$(git rev-parse --show-toplevel)"
BASENAME="$(basename "$ROOT")"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
ORIGIN_URL="$(git config --get remote.origin.url || true)"

echo "=== GIT CONTEXT ==="
echo "Repo   : $ROOT"
echo "Branch : $BRANCH"
echo "Remote : ${ORIGIN_URL:-<none>}"

if [[ "$BASENAME" != "$EXPECTED_REPO_NAME" ]]; then
  echo "[x] Repo name mismatch. Expected '$EXPECTED_REPO_NAME' but got '$BASENAME'"; exit 1
fi

# Allow https OR ssh forms; only check that it contains the expected path tail.
if [[ "${ORIGIN_URL}" != *"jacobmentalconstruct/_MonacoVIEWER"* ]]; then
  echo "[x] Origin remote doesn't look like jacobmentalconstruct/_MonacoVIEWER"; exit 1
fi

if [[ "$BRANCH" != "$EXPECTED_BRANCH" ]]; then
  echo "[x] On '$BRANCH', expected '$EXPECTED_BRANCH'."; exit 1
fi

# --- Work ---
# Show short status; bail early if nothing to do
git status -sb

# Stage everything (tracked + new)
git add -A

# Only commit if there are staged changes
if ! git diff --cached --quiet; then
  TS="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  git commit -m "${COMMIT_MSG} [${TS}]"
else
  echo "[i] No changes staged; skipping commit."
fi

# Make sure we’re up to date, then push
git fetch origin
git pull --rebase origin "$EXPECTED_BRANCH"
git push origin "$EXPECTED_BRANCH"

echo "[✓] Update complete."

