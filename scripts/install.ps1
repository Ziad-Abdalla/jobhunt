# jobhunt installer for Windows.
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  =============================" -ForegroundColor Blue
Write-Host "       jobhunt installer" -ForegroundColor Blue
Write-Host "  =============================" -ForegroundColor Blue
Write-Host ""

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

# -- Step 1: uv --

Refresh-Path

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "  [1/3] uv found" -ForegroundColor Green
} else {
    Write-Host "  [1/3] Installing uv..." -ForegroundColor Cyan
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
    Write-Host "  [1/3] uv installed" -ForegroundColor Green
}

# -- Step 2: jobhunt --

Write-Host "  [2/3] Installing jobhunt..." -ForegroundColor Cyan

& uv tool uninstall jobhunt-app 2>$null | Out-Null
& uv tool uninstall jobhunt 2>$null | Out-Null
& uv tool install jobhunt-app

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) {
    $env:Path = "$toolBin;$env:Path"
}

$ver = & jobhunt --version 2>$null
if (-not $ver) {
    Write-Host "  ERROR: install failed." -ForegroundColor Red
    Read-Host "  Press Enter to close"
    exit 1
}
Write-Host "  [2/3] $ver installed" -ForegroundColor Green

# -- Step 3: desktop shortcut --

# Find the exact path to jobhunt.exe
$jobhuntExe = (Get-Command jobhunt -ErrorAction SilentlyContinue).Source
if (-not $jobhuntExe) {
    $jobhuntExe = Join-Path $toolBin 'jobhunt.exe'
}

$desktop = [Environment]::GetFolderPath('Desktop')
$batPath = Join-Path $desktop 'jobhunt.bat'

$batLines = @(
    '@echo off'
    'title jobhunt'
    "set ""PATH=$toolBin;%USERPROFILE%\.local\bin;%PATH%"""
    'echo.'
    'echo   Starting jobhunt...'
    'echo   Your browser will open shortly.'
    'echo   Close this window to stop the server.'
    'echo.'
    'jobhunt'
    'if %errorlevel% neq 0 ('
    '    echo.'
    '    echo   Something went wrong. See error above.'
    '    pause'
    ')'
)
Set-Content -Path $batPath -Value ($batLines -join "`r`n") -Encoding ASCII
Write-Host "  [3/3] Desktop shortcut created" -ForegroundColor Green

Write-Host ""
Write-Host "  =============================" -ForegroundColor Green
Write-Host "         All done!" -ForegroundColor Green
Write-Host "  =============================" -ForegroundColor Green
Write-Host ""
Write-Host "  Double-click 'jobhunt' on your Desktop to start." -ForegroundColor White
Write-Host "  To update later: run this same command again." -ForegroundColor Gray
Write-Host ""
