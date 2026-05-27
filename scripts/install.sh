#!/usr/bin/env bash
# jobhunt installer for Linux and macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
#
# To uninstall:
#   uv tool uninstall jobhunt
set -euo pipefail

REPO="Abdalla2004-collab/Jobhunt"
GIT_PACKAGE="git+https://github.com/$REPO.git"

info()  { printf '  \033[1;36m→\033[0m %s\n' "$*"; }
ok()    { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
fail()  { printf '  \033[1;31m✗\033[0m %s\n' "$*" >&2; }

echo ""
echo "  Installing jobhunt"
echo "  ──────────────────"
echo ""

# ── Step 1: uv ───────────────────────────────────────────────────────────────

if command -v uv >/dev/null 2>&1; then
    ok "uv is already installed ($(uv --version 2>/dev/null || echo '?'))"
else
    info "Installing uv (package manager by Astral)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        fail "Could not install uv. Install it yourself: https://docs.astral.sh/uv/"
        exit 1
    fi
    ok "uv installed"
fi

# ── Step 2: jobhunt ──────────────────────────────────────────────────────────

info "Installing jobhunt..."

# Try PyPI first (fast, no git needed), fall back to git
installed=false
if uv tool install jobhunt-app >/dev/null 2>&1; then
    installed=true
elif uv tool install "$GIT_PACKAGE" >/dev/null 2>&1; then
    installed=true
fi

if [ "$installed" = false ]; then
    # Already installed — upgrade
    uv tool install --reinstall --upgrade jobhunt >/dev/null 2>&1 \
        || uv tool install --reinstall --upgrade "$GIT_PACKAGE" >/dev/null 2>&1 \
        || true
fi

ok "jobhunt installed"

# ── Step 3: verify ───────────────────────────────────────────────────────────

export PATH="$HOME/.local/bin:$PATH"

if command -v jobhunt >/dev/null 2>&1; then
    ok "Ready — run 'jobhunt' to start"
else
    echo ""
    info "Add this to your ~/.bashrc or ~/.zshrc, then reopen your terminal:"
    echo ""
    echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │                                              │"
echo "  │   To launch:      jobhunt                    │"
echo "  │   To update:      jobhunt update             │"
echo "  │   To uninstall:   uv tool uninstall jobhunt  │"
echo "  │                                              │"
echo "  └──────────────────────────────────────────────┘"
echo ""
