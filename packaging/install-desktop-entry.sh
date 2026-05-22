#!/usr/bin/env bash
# Install jobhunt as a Linux desktop application (XDG-compliant).
# Idempotent — safe to re-run.
set -eu

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$APPS_DIR" "$ICONS_DIR"

if ! command -v jobhunt >/dev/null 2>&1; then
  echo "warning: 'jobhunt' is not on your PATH yet."
  echo "         install it first (pipx, pip, or copy the binary somewhere on PATH)."
  echo "         the desktop entry will be installed but may not launch."
fi

install -m 0644 "$SOURCE_DIR/jobhunt.desktop" "$APPS_DIR/jobhunt.desktop"
if [ -f "$SOURCE_DIR/jobhunt.svg" ]; then
  install -m 0644 "$SOURCE_DIR/jobhunt.svg" "$ICONS_DIR/jobhunt.svg"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "installed:"
echo "  $APPS_DIR/jobhunt.desktop"
echo
echo "you can now launch jobhunt from your application launcher."
