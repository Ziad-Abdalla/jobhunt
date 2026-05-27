# jobhunt installer for Windows.
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  =============================" -ForegroundColor Blue
Write-Host "       jobhunt installer" -ForegroundColor White
Write-Host "  =============================" -ForegroundColor Blue
Write-Host ""

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

# -- Step 1: uv --

Refresh-Path

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "  [1/3] uv already installed" -ForegroundColor Green
} else {
    Write-Host "  [1/3] Installing uv..." -ForegroundColor Cyan
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    Refresh-Path
    $uvBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path (Join-Path $uvBin 'uv.exe')) {
        $env:Path = "$uvBin;$env:Path"
    }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "  ERROR: Could not install uv." -ForegroundColor Red
        Write-Host "  Install manually from https://docs.astral.sh/uv/" -ForegroundColor Red
        Write-Host ""
        Read-Host "  Press Enter to close"
        exit 1
    }
    Write-Host "  [1/3] uv installed" -ForegroundColor Green
}

# -- Step 2: jobhunt --

Write-Host "  [2/3] Installing jobhunt..." -ForegroundColor Cyan

# Remove any old installation to avoid name conflicts
& uv tool uninstall jobhunt-app 2>$null | Out-Null
& uv tool uninstall jobhunt 2>$null | Out-Null

# Install fresh — show output so user sees progress
& uv tool install jobhunt-app

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) {
    $env:Path = "$toolBin;$env:Path"
}

$ver = & jobhunt --version 2>$null
if (-not $ver) {
    Write-Host ""
    Write-Host "  ERROR: jobhunt not found after install." -ForegroundColor Red
    Write-Host "  Close this window, open a new PowerShell, and type: jobhunt" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to close"
    exit 1
}
Write-Host "  [2/3] $ver installed" -ForegroundColor Green

# -- Step 3: desktop shortcut --

$desktop = [Environment]::GetFolderPath('Desktop')
$toolBinResolved = & uv tool dir --bin 2>$null

$batContent = @"
@echo off
title jobhunt
set "PATH=$toolBinResolved;%USERPROFILE%\.local\bin;%PATH%"
echo.
echo   Starting jobhunt... your browser will open.
echo   Close this window to stop.
echo.
jobhunt
"@

$batPath = Join-Path $desktop 'jobhunt.bat'
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Write-Host "  [3/3] Desktop shortcut created" -ForegroundColor Green

Write-Host ""
Write-Host "  =============================" -ForegroundColor Blue
Write-Host "         All done!" -ForegroundColor Green
Write-Host "  =============================" -ForegroundColor Blue
Write-Host ""
Write-Host "  Double-click 'jobhunt' on your Desktop to start." -ForegroundColor White
Write-Host "  Or type 'jobhunt' in any terminal." -ForegroundColor White
Write-Host ""
Write-Host "  To update: run this same command again." -ForegroundColor Gray
Write-Host ""
