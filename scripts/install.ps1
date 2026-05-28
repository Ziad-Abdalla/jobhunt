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
& uv tool install "jobhunt-app>=0.8.0" --refresh

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

# Find the custom icon from the installed package
$pkgDir = & python3 -c "import jobhunt; print(jobhunt.__file__.replace('__init__.py',''))" 2>$null
$customIcon = Join-Path $pkgDir 'static\jobhunt.ico'
if (Test-Path $customIcon) {
    $iconPath = $customIcon
} else {
    $iconPath = "$env:SystemRoot\System32\imageres.dll,14"
}

# Desktop shortcut
$lnk = $shell.CreateShortcut((Join-Path $desktop 'jobhunt.lnk'))
$lnk.TargetPath = $jobhuntExe
$lnk.Description = 'Search thousands of software jobs locally'
$lnk.IconLocation = $iconPath
$lnk.WindowStyle = 7
$lnk.Save()

# Also add to Start Menu
$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$lnk2 = $shell.CreateShortcut((Join-Path $startMenu 'jobhunt.lnk'))
$lnk2.TargetPath = $jobhuntExe
$lnk2.Description = 'Search thousands of software jobs locally'
$lnk2.IconLocation = $iconPath
$lnk2.WindowStyle = 7
$lnk2.Save()

# Remove old .bat if it exists
$oldBat = Join-Path $desktop 'jobhunt.bat'
if (Test-Path $oldBat) { Remove-Item $oldBat -Force }

Write-Host "  Shortcut added to Desktop and Start Menu" -ForegroundColor Green

Write-Host ""
Write-Host "  All done!" -ForegroundColor Green
Write-Host ""
Write-Host "  To start: click 'jobhunt' on Desktop or search it in Start Menu" -ForegroundColor White
Write-Host "  To update: run this install command again" -ForegroundColor Gray
Write-Host ""
