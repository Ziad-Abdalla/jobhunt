#!/usr/bin/env bash
# jobhunt installer for macOS and Linux.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
set -euo pipefail

echo ""
echo "  ============================="
echo "       jobhunt installer"
echo "  ============================="
echo ""

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

# -- Step 1: uv --

if command -v uv >/dev/null 2>&1; then
    echo "  [1/2] uv found"
else
    echo "  [1/2] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "  ERROR: uv install failed. Visit https://docs.astral.sh/uv/"
        exit 1
    fi
    echo "  [1/2] uv installed"
fi

# -- Step 2: jobhunt --

echo "  [2/2] Installing jobhunt..."

uv tool uninstall jobhunt-app 2>/dev/null || true
uv tool uninstall jobhunt 2>/dev/null || true
uv tool install jobhunt-app

export PATH="$HOME/.local/bin:$PATH"

ver=$(jobhunt --version 2>/dev/null || echo "")
if [ -z "$ver" ]; then
    echo "  ERROR: jobhunt not found after install."
    echo "  Add this to ~/.bashrc or ~/.zshrc:"
    echo '    export PATH="$HOME/.local/bin:$PATH"'
    exit 1
fi

echo "  [2/2] $ver installed"

echo ""
echo "  ============================="
echo "         All done!"
echo "  ============================="
echo ""
echo "  Type 'jobhunt' to start."
echo "  To update later: run this same command again."
echo ""
