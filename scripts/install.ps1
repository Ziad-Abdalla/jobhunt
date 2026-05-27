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
$ErrorActionPreference = 'Stop'

$Repo    = 'Abdalla2004-collab/Jobhunt'
$Package = "git+https://github.com/$Repo.git"

function Info($msg)  { Write-Host "  -> $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "  OK $msg" -ForegroundColor Green }
function Fail($msg)  { Write-Host "  FAIL $msg" -ForegroundColor Red; exit 1 }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

Write-Host ""
Write-Host "  Installing jobhunt"
Write-Host "  ------------------"
Write-Host ""

# ── Step 0: check git ───────────────────────────────────────────────────────

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  Git is required but not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "  Install Git for Windows from: https://git-scm.com/download/win"
    Write-Host "  Then re-run this script."
    Write-Host ""
    Write-Host "  Alternatively, download the standalone binary:"
    Write-Host "  https://github.com/$Repo/releases/latest/download/jobhunt-windows-x86_64.exe"
    Write-Host ""
    exit 1
}

# ── Step 1: uv ──────────────────────────────────────────────────────────────

Refresh-Path

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = & uv --version 2>$null
    Ok "uv is already installed ($uvVer)"
} else {
    Info "Installing uv (open-source Python package manager by Astral)..."
    Info "Source: https://astral.sh/uv -- widely trusted, MIT-licensed."
    Write-Host ""
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    } catch {
        Fail "Could not install uv automatically. Install it yourself: https://docs.astral.sh/uv/getting-started/installation/"
    }
    Refresh-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $uvBin = Join-Path $env:USERPROFILE '.local\bin'
        if (Test-Path (Join-Path $uvBin 'uv.exe')) {
            $env:Path = "$uvBin;$env:Path"
        } else {
            Fail "Could not find uv after installation. Close this window, open a new PowerShell, and re-run the script."
        }
    }
    Ok "uv installed"
}

# ── Step 2: jobhunt ─────────────────────────────────────────────────────────

Info "Installing jobhunt into its own isolated environment..."

$prev = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$output = & uv tool install $Package 2>&1 | Out-String
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prev

if ($output -match 'already installed') {
    Info "jobhunt is already installed -- upgrading to latest..."
    $ErrorActionPreference = 'SilentlyContinue'
    & uv tool install --reinstall --upgrade $Package 2>&1 | Out-Null
    $ErrorActionPreference = $prev
} elseif ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "  Installation failed. Output:" -ForegroundColor Red
    Write-Host $output
    Write-Host ""
    Write-Host "  Try downloading the standalone binary instead:"
    Write-Host "  https://github.com/$Repo/releases/latest/download/jobhunt-windows-x86_64.exe"
    exit 1
}
Ok "jobhunt installed"

# ── Step 3: add tool bin to PATH for this session ───────────────────────────

Refresh-Path

$toolBin = (& uv tool dir --bin 2>$null)
if ($toolBin -and (Test-Path $toolBin)) {
    if ($env:Path -notlike "*$toolBin*") {
        $env:Path = "$toolBin;$env:Path"
    }
}

if (Get-Command jobhunt -ErrorAction SilentlyContinue) {
    Ok "Ready -- you can run 'jobhunt' right now in this window"
} else {
    Write-Host ""
    Info "Almost done -- close this window and open a new PowerShell,"
    Info "then run: jobhunt"
}

Write-Host ""
Write-Host "  +----------------------------------------------+"
Write-Host "  |                                              |"
Write-Host "  |   All done. To launch jobhunt, just run:     |"
Write-Host "  |                                              |"
Write-Host "  |       jobhunt                                |"
Write-Host "  |                                              |"
Write-Host "  |   It starts a local server and opens your    |"
Write-Host "  |   browser. Nothing leaves your machine.      |"
Write-Host "  |                                              |"
Write-Host "  |   To update later:                           |"
Write-Host "  |                                              |"
Write-Host "  |       jobhunt update                         |"
Write-Host "  |                                              |"
Write-Host "  |   To uninstall:                              |"
Write-Host "  |                                              |"
Write-Host "  |       uv tool uninstall jobhunt              |"
Write-Host "  |                                              |"
Write-Host "  +----------------------------------------------+"
Write-Host ""
