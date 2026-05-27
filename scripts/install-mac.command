#!/bin/bash
# jobhunt installer for macOS — double-click this file.
clear
echo ""
echo "  Installing jobhunt..."
echo ""

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "  Installing uv (package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

if command -v jobhunt >/dev/null 2>&1; then
    echo "  Updating jobhunt..."
    uv tool install --reinstall --upgrade jobhunt-app 2>/dev/null
else
    echo "  Installing jobhunt from PyPI..."
    uv tool install jobhunt-app 2>/dev/null || uv tool install "git+https://github.com/Abdalla2004-collab/Jobhunt.git" 2>/dev/null
fi

export PATH="$HOME/.local/bin:$PATH"

echo ""
echo "  Done! Starting jobhunt..."
echo "  Close this window to stop."
echo ""
jobhunt
