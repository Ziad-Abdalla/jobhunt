#!/usr/bin/env bash
# Release a new version of jobhunt-app, atomically, without forgetting a step.
#
# Usage:
#   ./scripts/release.sh 0.10.0
#
# What it does (in order):
#   1. Validates the version string and that the working tree is clean.
#   2. Bumps the version in __init__.py, pyproject.toml, install.sh, install.ps1
#      — all four spots that have to agree, or future users get stuck on a
#      stale wheel (the "works one day, broken the next" bug).
#   3. Runs the full test suite. Aborts on any failure.
#   4. Rebuilds the wheel + sdist into dist/.
#   5. Verifies the wheel contains templates, static, and sources.yaml.
#   6. Smoke-installs the wheel into a throwaway venv and hits the routes.
#   7. Commits + tags + pushes (asks first).
#   8. Prints the exact PyPI + GitHub release commands for the human to run.
#
# This script never uploads to PyPI itself — that requires your token, which
# stays on your machine. It just makes the rest of the release deterministic.

set -euo pipefail

NEW_VERSION="${1:-}"
if [ -z "$NEW_VERSION" ]; then
    echo "usage: $0 <new-version>   e.g. $0 0.10.0" >&2
    exit 1
fi
if ! echo "$NEW_VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+(rc[0-9]+|b[0-9]+|a[0-9]+)?$'; then
    echo "ERROR: '$NEW_VERSION' doesn't look like a PEP 440 version" >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: working tree is dirty. Commit or stash first." >&2
    git status --short >&2
    exit 1
fi
if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
    echo "WARNING: you're not on 'main'. Continue anyway? [y/N]"
    read -r answer
    [ "$answer" = "y" ] || exit 1
fi

PY="${REPO_ROOT}/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

echo "→ bumping version to $NEW_VERSION across __init__.py, pyproject.toml, install.sh, install.ps1"

"$PY" - "$NEW_VERSION" <<'PYEOF'
import sys, re, pathlib
v = sys.argv[1]
p = pathlib.Path("src/jobhunt/__init__.py")
text = p.read_text()
new = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', text)
if new == text:
    raise SystemExit("ERROR: __version__ line not found in __init__.py")
p.write_text(new)
PYEOF

"$PY" - "$NEW_VERSION" <<'PYEOF'
import sys, re, pathlib
v = sys.argv[1]
p = pathlib.Path("pyproject.toml")
text = p.read_text()
new = re.sub(r'^version = "[^"]+"', f'version = "{v}"', text, count=1, flags=re.M)
if new == text:
    raise SystemExit("ERROR: version line not found in pyproject.toml")
p.write_text(new)
PYEOF

"$PY" - "$NEW_VERSION" <<'PYEOF'
import sys, re, pathlib
v = sys.argv[1]
p = pathlib.Path("scripts/install.sh")
text = p.read_text()
new = re.sub(r'PKG_SPEC="jobhunt-app>=[^"]+"', f'PKG_SPEC="jobhunt-app>={v}"', text)
if new == text:
    raise SystemExit("ERROR: PKG_SPEC line not found in install.sh")
p.write_text(new)
PYEOF

"$PY" - "$NEW_VERSION" <<'PYEOF'
import sys, re, pathlib
v = sys.argv[1]
p = pathlib.Path("scripts/install.ps1")
text = p.read_text()
new = re.sub(r'"jobhunt-app>=[^"]+"', f'"jobhunt-app>={v}"', text)
if new == text:
    raise SystemExit("ERROR: jobhunt-app>= pin not found in install.ps1")
p.write_text(new)
PYEOF

echo "→ running tests"
"$PY" -m pytest -q

echo "→ building dist/"
rm -rf dist build
"$PY" -m build

WHL="$(ls dist/jobhunt_app-${NEW_VERSION}-py3-none-any.whl 2>/dev/null || true)"
if [ -z "$WHL" ]; then
    echo "ERROR: expected wheel dist/jobhunt_app-${NEW_VERSION}-py3-none-any.whl not found" >&2
    exit 1
fi
"$PY" - "$WHL" <<'PYEOF'
import sys, zipfile
must_have = [
    "jobhunt/sources.yaml",
    "jobhunt/static/app.js",
    "jobhunt/static/style.css",
    "jobhunt/templates/index.html",
    "jobhunt/templates/local.html",
    "jobhunt/templates/bounties.html",
    "jobhunt/templates/settings.html",
    "jobhunt/templates/cv.html",
    "jobhunt/templates/sources.html",
]
z = zipfile.ZipFile(sys.argv[1])
missing = [m for m in must_have if m not in z.namelist()]
if missing:
    raise SystemExit(f"ERROR: wheel is missing: {missing}")
print(f"→ wheel-content check passed ({len(must_have)} files present)")
PYEOF

echo "→ smoke-installing into /tmp/jobhunt-release-test-venv"
rm -rf /tmp/jobhunt-release-test-venv
python3 -m venv /tmp/jobhunt-release-test-venv
/tmp/jobhunt-release-test-venv/bin/pip install -q "$WHL"
/tmp/jobhunt-release-test-venv/bin/python - <<'PYEOF'
from jobhunt.main import app
from jobhunt import __version__
from fastapi.testclient import TestClient
print("→ installed jobhunt version:", __version__)
with TestClient(app) as c:
    for p in ["/", "/local", "/bounties", "/sources", "/cv", "/settings", "/freelance"]:
        r = c.get(p)
        if r.status_code != 200:
            raise SystemExit(f"ERROR: {p} -> {r.status_code}")
        print(f"  200  {p}")
print("→ smoke install passed")
PYEOF
rm -rf /tmp/jobhunt-release-test-venv

echo ""
echo "→ ready to commit + tag + push v${NEW_VERSION}"
echo "  files changed:"
git diff --stat
echo ""
echo "Proceed? [y/N]"
read -r answer
[ "$answer" = "y" ] || { echo "aborted — your edits are still in the working tree"; exit 1; }

git add src/jobhunt/__init__.py pyproject.toml scripts/install.sh scripts/install.ps1
git commit -m "release v${NEW_VERSION}"
git tag -a "v${NEW_VERSION}" -m "v${NEW_VERSION}"
git push origin main
git push origin "v${NEW_VERSION}"

cat <<EOF

✅ Local release prepared for v${NEW_VERSION}.

Two manual steps remain (one each):

  1. Upload to PyPI (needs your token):

       cd $(pwd)
       twine upload dist/jobhunt_app-${NEW_VERSION}*

     ...or with uv:

       uv publish

  2. Create the GitHub release so the in-app "Check for updates" finds it:

       gh release create v${NEW_VERSION} --notes-from-tag

     ...or via the UI at:

       https://github.com/Ziad-Abdalla/jobhunt/releases/new?tag=v${NEW_VERSION}

After PyPI accepts the upload, anyone (including you on a new machine) can:

    irm https://raw.githubusercontent.com/Ziad-Abdalla/jobhunt/main/scripts/install.ps1 | iex   # Windows
    curl -fsSL https://raw.githubusercontent.com/Ziad-Abdalla/jobhunt/main/scripts/install.sh | bash   # macOS / Linux

...and the install script's --refresh + cache-clean + bumped version-floor
guarantees they get the new wheel, never a cached old one.
EOF
