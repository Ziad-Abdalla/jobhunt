#!/usr/bin/env bash
# jobhunt installer for Linux and macOS.
#
# What this does (nothing hidden):
#   1. Installs "uv" if you don't have it — a trusted, open-source Python
#      package manager made by Astral (the company behind ruff). It's a
#      single small binary, installs to ~/.local/bin, and doesn't touch
#      your system Python or anything else on your machine.
#   2. Installs jobhunt in its own isolated environment via uv.
#   3. Adds the "jobhunt" command to your PATH.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
#
# To uninstall:
#   uv tool uninstall jobhunt
set -euo pipefail

REPO="Abdalla2004-collab/Jobhunt"
PACKAGE="git+https://github.com/$REPO.git"

info()  { printf '  \033[1;36m→\033[0m %s\n' "$*"; }
ok()    { printf '  \033[1;32m✓\033[0m %s\n' "$*"; }
fail()  { printf '  \033[1;31m✗\033[0m %s\n' "$*" >&2; exit 1; }

echo ""
echo "  Installing jobhunt"
echo "  ──────────────────"
echo ""

# ── Step 0: check git ───────────────────────────────────────────────────────

if ! command -v git >/dev/null 2>&1; then
    fail "Git is required but not found. Install it first:"
    echo "  Linux (Debian/Ubuntu): sudo apt install git"
    echo "  Linux (Fedora):        sudo dnf install git"
    echo "  macOS:                 xcode-select --install"
    echo ""
    echo "  Or download the standalone binary instead:"
    echo "  https://github.com/$REPO/releases/latest"
    exit 1
fi

# ── Step 1: uv ───────────────────────────────────────────────────────────────

if command -v uv >/dev/null 2>&1; then
    ok "uv is already installed ($(uv --version 2>/dev/null || echo 'unknown version'))"
else
    info "Installing uv (open-source Python package manager by Astral)..."
    info "Source: https://astral.sh/uv — widely trusted, MIT-licensed."
    echo ""
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    # Make uv available for the rest of this script.
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        fail "Could not install uv automatically."
        fail "Install it yourself: https://docs.astral.sh/uv/getting-started/installation/"
    fi
    ok "uv installed"
fi

# ── Step 2: jobhunt ──────────────────────────────────────────────────────────

info "Installing jobhunt into its own isolated environment..."
output=$(uv tool install "$PACKAGE" 2>&1) || true
if echo "$output" | grep -q "already installed"; then
    info "jobhunt is already installed — upgrading to latest..."
    uv tool install --reinstall --upgrade "$PACKAGE" >/dev/null 2>&1 || true
fi
ok "jobhunt installed"

# ── Step 3: verify ───────────────────────────────────────────────────────────

# uv tool installs put binaries in ~/.local/bin — make sure it's on PATH.
export PATH="$HOME/.local/bin:$PATH"

if command -v jobhunt >/dev/null 2>&1; then
    ok "Ready"
else
    echo ""
    info "Almost done — add this line to your shell config (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "      export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
    info "Then reopen your terminal."
fi

echo ""
echo "  ┌──────────────────────────────────────────────┐"
echo "  │                                              │"
echo "  │   All done. To launch jobhunt, just run:     │"
echo "  │                                              │"
echo "  │       jobhunt                                │"
echo "  │                                              │"
echo "  │   It starts a local server and opens your    │"
echo "  │   browser. Nothing leaves your machine.      │"
echo "  │                                              │"
echo "  │   To update later:                           │"
echo "  │                                              │"
echo "  │       uv tool upgrade jobhunt                │"
echo "  │                                              │"
echo "  │   To uninstall:                              │"
echo "  │                                              │"
echo "  │       uv tool uninstall jobhunt              │"
echo "  │                                              │"
echo "  └──────────────────────────────────────────────┘"
echo ""
