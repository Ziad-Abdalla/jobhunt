# jobhunt installer (Windows / PowerShell).
#
# Usage:
#   .\scripts\install.ps1
#
# Requires Python 3.11+ on PATH. We do NOT pipe-execute remote scripts; if you
# want `uv`, install it manually first (`pip install --user uv` or
# `winget install --id=astral-sh.uv`).

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Fail($msg) {
    Write-Host "error: $msg" -ForegroundColor Red
    exit 1
}

# --- 1. Python >= 3.11 check -------------------------------------------------

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Fail "python is not on PATH. install Python 3.11+ from https://www.python.org/downloads/"
}

$verRaw = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
$verOk  = & python -c "import sys; print(1 if sys.version_info >= (3, 11) else 0)"
if ($verOk.Trim() -ne '1') {
    Fail "jobhunt requires Python >= 3.11; found $verRaw."
}
Write-Host "[ok] python $($verRaw.Trim()) detected"

# --- 2. project root ---------------------------------------------------------

$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $scriptDir '..')
Set-Location $projectRoot

# --- 3. virtualenv -----------------------------------------------------------

if (-not (Test-Path '.venv')) {
    Write-Host "[..] creating virtualenv at .venv"
    & python -m venv .venv
} else {
    Write-Host "[ok] .venv already exists"
}

$activate = Join-Path '.venv' 'Scripts\Activate.ps1'
if (-not (Test-Path $activate)) {
    Fail "venv created but $activate is missing"
}
. $activate

# --- 4. install --------------------------------------------------------------

Write-Host "[..] upgrading pip"
& python -m pip install --upgrade pip

Write-Host "[..] installing project + dev extras"
& pip install -e ".[dev]"

# --- 5. next steps -----------------------------------------------------------

Write-Host ""
Write-Host "[done] jobhunt installed." -ForegroundColor Green
Write-Host ""
Write-Host "next steps:"
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "    jobhunt scrape           # first scrape (a few minutes)"
Write-Host "    jobhunt serve            # open http://127.0.0.1:8765"
Write-Host ""
Write-Host "optional extras:"
Write-Host "    pip install -e `".[match]`"       # local CV matching (~500MB of deps)"
Write-Host "    pip install -e `".[linkedin]`"    # opt-in only; violates LinkedIn ToS"
Write-Host ""
