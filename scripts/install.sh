#!/usr/bin/env bash
# jobhunt installer for macOS and Linux.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
#
# This script is idempotent — running it again on a later day pulls the latest
# release. We force the uv tool cache to drop the old wheel so users never
# stay stuck on a stale install (the "worked yesterday, broken today" trap).
set -euo pipefail

# Floor version: re-running with an older floor would still let uv pick
# whatever is cached. Bumping this every release guarantees the user gets
# the new wheel even if their cache holds the previous one.
PKG_SPEC="jobhunt-app>=0.9.2"

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

# Drop the old install + cache so we always resolve to the latest PyPI wheel.
# Without these, uv happily reuses a wheel from yesterday and the user thinks
# their update did nothing.
uv tool uninstall jobhunt-app >/dev/null 2>&1 || true
uv tool uninstall jobhunt >/dev/null 2>&1 || true
uv cache clean >/dev/null 2>&1 || true

# `--refresh` forces uv to re-fetch metadata + wheel even if locally cached.
uv tool install --refresh "$PKG_SPEC"

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
echo "  To uninstall: open Settings inside the app and click Uninstall."
echo ""
