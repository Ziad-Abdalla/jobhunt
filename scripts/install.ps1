# jobhunt installer for Windows.
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  jobhunt installer" -ForegroundColor Blue
Write-Host "  -----------------" -ForegroundColor Blue
Write-Host ""

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

# -- Step 1: uv --

Refresh-Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  [1/2] Installing uv..." -ForegroundColor Cyan
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    Refresh-Path
    $uvBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path (Join-Path $uvBin 'uv.exe')) {
        $env:Path = "$uvBin;$env:Path"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "  ERROR: uv install failed." -ForegroundColor Red
        Read-Host "  Press Enter to close"
        exit 1
    }
}
Write-Host "  [1/2] uv ready" -ForegroundColor Green

# -- Step 2: jobhunt --

Write-Host "  [2/2] Installing jobhunt..." -ForegroundColor Cyan

# Force clean install of latest version
& uv tool uninstall jobhunt-app 2>$null | Out-Null
& uv tool uninstall jobhunt 2>$null | Out-Null
& uv cache clean jobhunt-app 2>$null | Out-Null
& uv cache clean 2>$null | Out-Null
& uv tool install "jobhunt-app>=0.7.3" --refresh

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) {
    $env:Path = "$toolBin;$env:Path"
}

$ver = & jobhunt --version 2>$null
if (-not $ver) {
    Write-Host ""
    Write-Host "  ERROR: jobhunt not found after install." -ForegroundColor Red
    Write-Host "  Close ALL terminals, open a new PowerShell, type: jobhunt" -ForegroundColor Yellow
    Read-Host "  Press Enter to close"
    exit 1
}

Write-Host "  [2/2] $ver installed" -ForegroundColor Green
Write-Host ""
Write-Host "  Done! To start jobhunt:" -ForegroundColor Green
Write-Host ""
Write-Host "    jobhunt" -ForegroundColor White
Write-Host ""
Write-Host "  Type that in any terminal. Your browser opens automatically." -ForegroundColor Gray
Write-Host "  To update later: run this same install command again." -ForegroundColor Gray
Write-Host ""
