#!/usr/bin/env bash
# jobhunt — one-line binary installer for Linux & macOS.
#
# Detects your OS + CPU, downloads the matching pre-built binary from the
# latest GitHub release, drops it at ~/.local/bin/jobhunt, and prints the
# next step. No Python required.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.sh | bash
#
# Or, after cloning:
#   bash scripts/install.sh
set -euo pipefail

REPO="Abdalla2004-collab/Jobhunt"
INSTALL_DIR="${JOBHUNT_INSTALL_DIR:-$HOME/.local/bin}"
BIN_NAME="jobhunt"

say()  { printf "\033[1;36m▸\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m▸\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m✗\033[0m %s\n" "$*" >&2; exit 1; }

# 1. detect OS / arch
uname_s="$(uname -s)"
uname_m="$(uname -m)"
case "$uname_s" in
  Linux)  os="linux" ;;
  Darwin) os="macos" ;;
  *) die "Unsupported OS: $uname_s. Try the source install — see README." ;;
esac
case "$uname_m" in
  x86_64|amd64)  arch="x86_64" ;;
  arm64|aarch64) arch="arm64" ;;
  *) die "Unsupported CPU: $uname_m." ;;
esac

case "$os-$arch" in
  linux-x86_64) asset="jobhunt-linux-x86_64" ;;
  macos-arm64)  asset="jobhunt-macos-arm64" ;;
  macos-x86_64) asset="jobhunt-macos-arm64" ;;
  *) die "No prebuilt binary for $os-$arch yet. Install from source — see README." ;;
esac

# 2. find latest release tag
say "looking up latest release of $REPO"
api_url="https://api.github.com/repos/$REPO/releases/latest"
tag="$(curl -fsSL "$api_url" 2>/dev/null | grep -E '"tag_name"' | head -1 | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/' || true)"
if [ -z "${tag:-}" ]; then
  die "Could not find a release. Either none exist yet, or GitHub is unreachable.
   Try the source install — see https://github.com/$REPO#install"
fi
say "latest release: $tag"

download_url="https://github.com/$REPO/releases/download/$tag/$asset"

# 3. download
mkdir -p "$INSTALL_DIR"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
say "downloading $asset"
curl -fL --progress-bar -o "$tmp" "$download_url" \
  || die "Download failed. URL: $download_url"

# 4. install
chmod +x "$tmp"
install_path="$INSTALL_DIR/$BIN_NAME"
mv "$tmp" "$install_path"
trap - EXIT
say "installed at $install_path"

# 5. PATH check
case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *)
    warn "$INSTALL_DIR is not on your PATH. Add this to your shell config:"
    printf "\n    export PATH=\"%s:\$PATH\"\n\n" "$INSTALL_DIR"
    ;;
esac

cat <<EOF

Done. Run jobhunt with:

    jobhunt app

That starts the server and opens it in your browser.

Source code & docs: https://github.com/$REPO
EOF
