#!/usr/bin/env bash
#
# Rebuild the profile card and push it, from this machine.
#
# There is no stored credential anywhere in this setup. The GitHub token is read
# out of the macOS keyring at the moment it is needed, via the `gh` CLI you are
# already signed in to, and lives only in this process's environment for the few
# seconds the fetch takes. Nothing is written to disk, committed, or held by
# GitHub.
#
# Safe to run by hand at any time:  ./scripts/nightly.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
BRANCH="main"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }
die() { log "ERROR: $*"; exit 1; }

cd "$REPO_DIR"

# ── Preflight ───────────────────────────────────────────────────────────────
[ -x "$PYTHON" ] || die "no virtualenv at $PYTHON -- run: make venv"
command -v gh >/dev/null || die "the gh CLI is not installed"
gh auth status >/dev/null 2>&1 || die "gh is not signed in -- run: gh auth login"

# Never build on top of someone else's changes.
git fetch --quiet origin "$BRANCH" || die "could not reach origin"
if [ -n "$(git status --porcelain -- ':!dist' ':!cache')" ]; then
    die "working tree has uncommitted changes outside dist/ -- refusing to run"
fi
git merge --quiet --ff-only "origin/$BRANCH" 2>/dev/null || true

# ── Build ───────────────────────────────────────────────────────────────────
log "fetching stats and rendering"

# The token is scoped to this one command. It is never echoed, never persisted,
# and `gh` re-reads it from the keyring on every run, so rotating your gh login
# is all it takes to rotate this.
if ! GITHUB_TOKEN="$(gh auth token)" "$PYTHON" -m profilecard; then
    die "build failed -- card left untouched"
fi

# ── Publish ─────────────────────────────────────────────────────────────────
if git diff --quiet -- dist cache; then
    log "no change; nothing to push"
    exit 0
fi

git add dist cache
# GitHub's noreply address, so a real email is not stamped into every commit
# this job makes. Change it if you fork; yours is on github.com/settings/emails.
git -c user.name="Scott Davis" \
    -c user.email="355212+the-scott-davis@users.noreply.github.com" \
    commit --quiet -m "chore: rebuild profile card ($(date '+%Y-%m-%d'))"

if git push --quiet origin "$BRANCH"; then
    log "pushed $(git rev-parse --short HEAD)"
else
    die "push failed -- commit is local, will retry tomorrow"
fi
