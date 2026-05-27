# jobhunt installer for Windows (PowerShell).
#
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
#
# To uninstall:
#   uv tool uninstall jobhunt
$ErrorActionPreference = 'Stop'

$Repo       = 'Abdalla2004-collab/Jobhunt'
$GitPackage = "git+https://github.com/$Repo.git"

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

# ── Step 1: uv ──────────────────────────────────────────────────────────────

Refresh-Path

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = & uv --version 2>$null
    Ok "uv is already installed ($uvVer)"
} else {
    Info "Installing uv (package manager by Astral)..."
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    } catch {
        Fail "Could not install uv. Install from: https://docs.astral.sh/uv/"
    }
    Refresh-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $uvBin = Join-Path $env:USERPROFILE '.local\bin'
        if (Test-Path (Join-Path $uvBin 'uv.exe')) {
            $env:Path = "$uvBin;$env:Path"
        } else {
            Fail "Could not find uv. Close this window, reopen PowerShell, and try again."
        }
    }
    Ok "uv installed"
}

# ── Step 2: jobhunt ─────────────────────────────────────────────────────────

Info "Installing jobhunt..."

# Try PyPI first (fast, no git needed), fall back to git
$prev = $ErrorActionPreference
$ErrorActionPreference = 'SilentlyContinue'
$output = & uv tool install jobhunt 2>&1 | Out-String
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $prev

if ($exitCode -ne 0) {
    if ($output -match 'already installed') {
        Info "Already installed -- upgrading..."
        $ErrorActionPreference = 'SilentlyContinue'
        & uv tool install --reinstall --upgrade jobhunt 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            & uv tool install --reinstall --upgrade $GitPackage 2>&1 | Out-Null
        }
        $ErrorActionPreference = $prev
    } else {
        # PyPI failed, try git
        $ErrorActionPreference = 'SilentlyContinue'
        & uv tool install $GitPackage 2>&1 | Out-Null
        $ErrorActionPreference = $prev
    }
}

Ok "jobhunt installed"

# ── Step 3: verify ──────────────────────────────────────────────────────────

Refresh-Path

$toolBin = (& uv tool dir --bin 2>$null)
if ($toolBin -and (Test-Path $toolBin)) {
    if ($env:Path -notlike "*$toolBin*") {
        $env:Path = "$toolBin;$env:Path"
    }
}

if (Get-Command jobhunt -ErrorAction SilentlyContinue) {
    Ok "Ready -- run 'jobhunt' to start"
} else {
    Write-Host ""
    Info "Close this window, open a new PowerShell, and run: jobhunt"
}

Write-Host ""
Write-Host "  +----------------------------------------------+"
Write-Host "  |                                              |"
Write-Host "  |   To launch:      jobhunt                   |"
Write-Host "  |   To update:      jobhunt update             |"
Write-Host "  |   To uninstall:   uv tool uninstall jobhunt  |"
Write-Host "  |                                              |"
Write-Host "  +----------------------------------------------+"
Write-Host ""
