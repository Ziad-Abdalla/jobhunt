#!/usr/bin/env bash
# jobhunt installer for Linux and macOS.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
set -euo pipefail

GIT_PACKAGE="git+https://github.com/Abdalla2004-collab/Jobhunt.git"

info()  { printf '  \033[1;36m>\033[0m %s\n' "$*"; }
ok()    { printf '  \033[1;32mOK\033[0m %s\n' "$*"; }
fail()  { printf '  \033[1;31mFAIL\033[0m %s\n' "$*" >&2; }

echo ""
echo "  Installing jobhunt"
echo "  -------------------"
echo ""

# ── uv ──

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
    ok "uv is already installed"
else
    info "Installing uv (package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        fail "Could not install uv. Install from: https://docs.astral.sh/uv/"
        exit 1
    fi
    ok "uv installed"
fi

# ── jobhunt ──

if command -v jobhunt >/dev/null 2>&1; then
    info "jobhunt is already installed. Updating..."
    uv tool install --reinstall --upgrade jobhunt-app 2>&1 || true
    ok "jobhunt updated"
else
    info "Installing jobhunt..."
    if ! uv tool install jobhunt-app 2>&1; then
        info "PyPI failed. Trying from GitHub..."
        uv tool install "$GIT_PACKAGE" 2>&1
    fi
    ok "jobhunt installed"
fi

# ── verify ──

export PATH="$HOME/.local/bin:$PATH"

if command -v jobhunt >/dev/null 2>&1; then
    ok "Ready"
else
    echo ""
    info "Add this to your ~/.bashrc or ~/.zshrc, then reopen your terminal:"
    echo '      export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "  To launch:      jobhunt"
echo "  To update:      jobhunt update"
echo "  To uninstall:   uv tool uninstall jobhunt-app"
echo ""
