#!/bin/bash
# jobhunt installer for Linux — run with: bash install-linux.sh
clear
echo ""
echo "  Installing jobhunt..."
echo "  ---------------------"
echo ""

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "  Installing uv (package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

echo "  Installing jobhunt from PyPI..."
uv tool install jobhunt-app 2>/dev/null || uv tool install --reinstall --upgrade jobhunt-app 2>/dev/null

export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "  Done! Starting jobhunt — your browser will open."
echo "  Press Ctrl+C to stop."
echo ""
jobhunt
