# jobhunt installer for Windows.
# Usage:
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  jobhunt installer" -ForegroundColor Blue
Write-Host ""

function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [System.Environment]::GetEnvironmentVariable('Path', 'Machine')
}

# -- Step 1: uv --

Refresh-Path
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  Installing uv..." -ForegroundColor Cyan
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" 2>$null
    Refresh-Path
    $uvBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path (Join-Path $uvBin 'uv.exe')) { $env:Path = "$uvBin;$env:Path" }
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "  Failed to install uv." -ForegroundColor Red
        Read-Host "  Press Enter"
        exit 1
    }
}
Write-Host "  uv ready" -ForegroundColor Green

# -- Step 2: jobhunt --

Write-Host "  Installing jobhunt..." -ForegroundColor Cyan
& uv tool uninstall jobhunt-app 2>$null | Out-Null
& uv tool uninstall jobhunt 2>$null | Out-Null
& uv cache clean 2>$null | Out-Null
# Floor version bumped every release so a cached older wheel can't satisfy
# the constraint — uv has to re-fetch the latest. --refresh forces metadata
# + wheel re-download even if locally cached.
& uv tool install --refresh "jobhunt-app>=0.11.0"

Refresh-Path
$toolBin = & uv tool dir --bin 2>$null
if ($toolBin -and (Test-Path $toolBin)) { $env:Path = "$toolBin;$env:Path" }

$jobhuntExe = (Get-Command jobhunt -ErrorAction SilentlyContinue).Source
if (-not $jobhuntExe) {
    Write-Host "  Install failed." -ForegroundColor Red
    Read-Host "  Press Enter"
    exit 1
}

$ver = & jobhunt --version 2>$null
Write-Host "  $ver installed" -ForegroundColor Green

# -- Step 3: create proper Windows shortcut (.lnk) on Desktop --

$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell

$lnk = $shell.CreateShortcut((Join-Path $desktop 'jobhunt.lnk'))
$lnk.TargetPath = $jobhuntExe
$lnk.Description = 'Search thousands of software jobs locally'
$lnk.WindowStyle = 7
$lnk.Save()

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$lnk2 = $shell.CreateShortcut((Join-Path $startMenu 'jobhunt.lnk'))
$lnk2.TargetPath = $jobhuntExe
$lnk2.Description = 'Search thousands of software jobs locally'
$lnk2.WindowStyle = 7
$lnk2.Save()

$oldBat = Join-Path $desktop 'jobhunt.bat'
if (Test-Path $oldBat) { Remove-Item $oldBat -Force }

Write-Host "  Shortcut added to Desktop and Start Menu" -ForegroundColor Green

Write-Host ""
Write-Host "  All done!" -ForegroundColor Green
Write-Host ""
Write-Host "  To start: click 'jobhunt' on Desktop or search it in Start Menu" -ForegroundColor White
Write-Host "  To update: run this install command again" -ForegroundColor Gray
Write-Host ""
