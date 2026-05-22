#!/usr/bin/env sh
# jobhunt installer (Linux / macOS / WSL).
#
# Usage:
#   ./scripts/install.sh            # assumes `uv` is already installed
#   ./scripts/install.sh --with-uv  # also install `uv` into ~/.local/bin
#
# This script does NOT pipe curl to sh. If you pass --with-uv we use the
# official uv installer command directly; otherwise we just print the
# instruction so you can install uv yourself.

set -eu
# `set -o pipefail` isn't in POSIX, but most modern /bin/sh implementations
# (bash, dash, ash on Alpine, zsh) support it. Guard the call so we don't
# crash on a shell that doesn't.
# shellcheck disable=SC3040
(set -o pipefail 2>/dev/null) && set -o pipefail

WITH_UV=0
for arg in "$@"; do
    case "$arg" in
        --with-uv) WITH_UV=1 ;;
        -h|--help)
            sed -n '2,11p' "$0"
            exit 0
            ;;
        *)
            echo "unknown arg: $arg" >&2
            exit 2
            ;;
    esac
done

# --- 1. Python >= 3.11 check ---------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 is not on PATH." >&2
    echo "install Python 3.11+ from https://www.python.org/downloads/ or your OS package manager." >&2
    exit 1
fi

PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_OK="$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)')"
if [ "$PY_OK" != "1" ]; then
    echo "error: jobhunt requires Python >= 3.11; found $PY_VER." >&2
    echo "install a newer Python from https://www.python.org/downloads/ and re-run." >&2
    exit 1
fi
echo "[ok] python $PY_VER detected"

# --- 2. uv availability --------------------------------------------------------

if ! command -v uv >/dev/null 2>&1; then
    if [ "$WITH_UV" = "1" ]; then
        echo "[..] installing uv into ~/.local/bin via pip"
        python3 -m pip install --user --upgrade uv
        # Make sure ~/.local/bin is on PATH for the rest of this script.
        case ":$PATH:" in
            *":$HOME/.local/bin:"*) : ;;
            *) PATH="$HOME/.local/bin:$PATH" ; export PATH ;;
        esac
    else
        echo "error: uv is not installed." >&2
        echo "install it with one of:" >&2
        echo "    pip install --user uv" >&2
        echo "    pipx install uv" >&2
        echo "or re-run this script with --with-uv to install it via pip --user." >&2
        echo "we do not pipe curl to sh." >&2
        exit 1
    fi
fi
echo "[ok] uv available: $(command -v uv)"

# --- 3. project install --------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -d ".venv" ]; then
    echo "[..] creating virtualenv at .venv"
    uv venv
else
    echo "[ok] .venv already exists"
fi

echo "[..] installing project + dev extras"
uv pip install -e ".[dev]"

# --- 4. next steps -------------------------------------------------------------

cat <<'EOF'

[done] jobhunt installed.

next steps:
    source .venv/bin/activate
    jobhunt scrape           # first scrape (a few minutes)
    jobhunt serve            # open http://127.0.0.1:8765

optional extras:
    uv pip install -e ".[match]"       # local CV matching (~500MB of deps)
    uv pip install -e ".[linkedin]"    # opt-in only; violates LinkedIn ToS

EOF
