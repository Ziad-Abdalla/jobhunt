# jobhunt installer for Windows.
#
# What this does (nothing hidden):
#   1. Installs "uv" if you don't have it - a trusted, open-source Python
#      package manager made by Astral (the company behind ruff). It's a
#      single small file, installs to your user directory, and doesn't
#      touch anything else on your machine.
#   2. Installs jobhunt in its own isolated environment via uv.
#   3. Adds the "jobhunt" command to your PATH.
#
# Usage (in PowerShell):
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
#
# To uninstall:
#   uv tool uninstall jobhunt
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Repo    = 'Abdalla2004-collab/Jobhunt'
$Package = "git+https://github.com/$Repo.git"

function Info($msg)  { Write-Host "  → $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Fail($msg)  { Write-Host "  ✗ $msg" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "  Installing jobhunt"
Write-Host "  ──────────────────"
Write-Host ""

# ── Step 1: uv ──────────────────────────────────────────────────────────────

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = & uv --version 2>$null
    Ok "uv is already installed ($uvVer)"
} else {
    Info "Installing uv (open-source Python package manager by Astral)..."
    Info "Source: https://astral.sh/uv — widely trusted, MIT-licensed."
    Write-Host ""
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    } catch {
        Fail "Could not install uv automatically."
        Fail "Install it yourself: https://docs.astral.sh/uv/getting-started/installation/"
    }
    # Refresh PATH so we can find uv.
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Fail "Could not find uv after installation. Close this window, open a new PowerShell, and re-run the script."
    }
    Ok "uv installed"
}

# ── Step 2: jobhunt ─────────────────────────────────────────────────────────

Info "Installing jobhunt into its own isolated environment..."
$output = & uv tool install $Package 2>&1 | Out-String
if ($output -match 'already installed') {
    Info "jobhunt is already installed — upgrading to latest..."
    & uv tool upgrade jobhunt 2>$null
}
Ok "jobhunt installed"

# ── Step 3: verify ──────────────────────────────────────────────────────────

# Refresh PATH one more time.
$env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')

if (-not (Get-Command jobhunt -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Info "Almost done — close this window and open a new PowerShell so the"
    Info "PATH update takes effect, then run: jobhunt"
} else {
    Ok "Ready"
}

Write-Host ""
Write-Host "  ┌──────────────────────────────────────────────┐"
Write-Host "  │                                              │"
Write-Host "  │   All done. To launch jobhunt, just run:     │"
Write-Host "  │                                              │"
Write-Host "  │       jobhunt                                │"
Write-Host "  │                                              │"
Write-Host "  │   It starts a local server and opens your    │"
Write-Host "  │   browser. Nothing leaves your machine.      │"
Write-Host "  │                                              │"
Write-Host "  │   To update later:                           │"
Write-Host "  │                                              │"
Write-Host "  │       uv tool upgrade jobhunt                │"
Write-Host "  │                                              │"
Write-Host "  │   To uninstall:                              │"
Write-Host "  │                                              │"
Write-Host "  │       uv tool uninstall jobhunt              │"
Write-Host "  │                                              │"
Write-Host "  └──────────────────────────────────────────────┘"
Write-Host ""
