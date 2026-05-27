# jobhunt installer for Windows (PowerShell).
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

$GitPackage = "git+https://github.com/Abdalla2004-collab/Jobhunt.git"

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
            Write-Host "  FAIL Could not install uv. Install from: https://docs.astral.sh/uv/" -ForegroundColor Red
            exit 1
        }
    }
    Ok "uv installed"
}

# -- jobhunt --

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) {
    $env:Path = "$toolBin;$env:Path"
}

if (Get-Command jobhunt -ErrorAction SilentlyContinue) {
    Info "jobhunt is already installed. Updating..."
    & uv tool install --reinstall --upgrade jobhunt-app 2>$null
    Ok "jobhunt updated"
} else {
    Info "Installing jobhunt..."
    & uv tool install jobhunt-app 2>$null
    if ($LASTEXITCODE -ne 0) {
        Info "Trying from GitHub..."
        & uv tool install $GitPackage 2>$null
    }
    Ok "jobhunt installed"
}

# -- verify --

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
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
Write-Host "  To launch:      jobhunt"
Write-Host "  To update:      jobhunt update"
Write-Host "  To uninstall:   uv tool uninstall jobhunt-app"
Write-Host ""
