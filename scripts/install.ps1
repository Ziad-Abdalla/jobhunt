# jobhunt installer for Windows (PowerShell).
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

function Info($msg)  { Write-Host "  > $msg" -ForegroundColor Cyan }
function Ok($msg)    { Write-Host "  OK $msg" -ForegroundColor Green }

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

Write-Host ""
Write-Host "  Installing jobhunt"
Write-Host "  -------------------"
Write-Host ""

# -- uv --

Refresh-Path

if (Get-Command uv -ErrorAction SilentlyContinue) {
    Ok "uv is already installed"
} else {
    Info "Installing uv (package manager)..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    Refresh-Path
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $uvBin = Join-Path $env:USERPROFILE '.local\bin'
        if (Test-Path (Join-Path $uvBin 'uv.exe')) {
            $env:Path = "$uvBin;$env:Path"
        } else {
            Write-Host "  FAIL Could not install uv." -ForegroundColor Red
            exit 1
        }
    }
    Ok "uv installed"
}

# -- uninstall old version if present (fixes broken update command) --

& uv tool uninstall jobhunt-app 2>$null
& uv tool uninstall jobhunt 2>$null

# -- install latest from PyPI --

Info "Installing latest jobhunt from PyPI..."
& uv tool install jobhunt-app 2>$null

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) {
    $env:Path = "$toolBin;$env:Path"
}

# -- show version --

$ver = & jobhunt --version 2>$null
if ($ver) {
    Ok "Installed: $ver"
} else {
    Write-Host "  FAIL jobhunt not found after install" -ForegroundColor Red
    exit 1
}

# -- create desktop shortcut --

$desktop = [Environment]::GetFolderPath('Desktop')
$batPath = Join-Path $desktop 'jobhunt.bat'
$batContent = "@echo off`ntitle jobhunt`njobhunt`npause"
Set-Content -Path $batPath -Value $batContent -Encoding ASCII
Ok "Desktop shortcut created: jobhunt.bat"

Write-Host ""
Write-Host "  All done!" -ForegroundColor Green
Write-Host ""
Write-Host "  To start: double-click 'jobhunt' on your Desktop"
Write-Host "            or type 'jobhunt' in any terminal"
Write-Host ""
Write-Host "  To update later: run this same command again"
Write-Host ""
