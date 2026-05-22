# jobhunt — one-line binary installer for Windows.
#
# Detects your CPU, downloads the matching pre-built binary from the latest
# GitHub release, drops it at $env:USERPROFILE\jobhunt\, and prints the next
# step. No Python required.
#
# Usage (in PowerShell):
#   irm https://raw.githubusercontent.com/Abdalla2004-collab/Jobhunt/main/scripts/install.ps1 | iex
#
# Or, after cloning:
#   .\scripts\install.ps1
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$Repo       = 'Abdalla2004-collab/Jobhunt'
$InstallDir = if ($env:JOBHUNT_INSTALL_DIR) { $env:JOBHUNT_INSTALL_DIR } else { Join-Path $env:USERPROFILE 'jobhunt' }
$BinName    = 'jobhunt.exe'

function Say($msg)  { Write-Host "▸ $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "▸ $msg" -ForegroundColor Yellow }
function Fail($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

# 1. Find latest release.
Say "looking up latest release of $Repo"
try {
  $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -ErrorAction Stop
} catch {
  Fail "Could not reach GitHub. Either no release exists yet, or check your connection."
}
$tag = $rel.tag_name
Say "latest release: $tag"

# 2. Pick the right asset (Windows x86_64 only for now).
$asset = 'jobhunt-windows-x86_64.exe'
$url = "https://github.com/$Repo/releases/download/$tag/$asset"

# 3. Download.
if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir | Out-Null }
$destination = Join-Path $InstallDir $BinName
Say "downloading $asset"
try {
  Invoke-WebRequest -Uri $url -OutFile $destination -UseBasicParsing
} catch {
  Fail "Download failed: $url"
}
Say "installed at $destination"

# 4. PATH check.
$paths = ($env:Path -split ';')
if ($paths -notcontains $InstallDir) {
  Warn "$InstallDir is not on your PATH."
  Warn "To add it for your user, run:"
  Write-Host ""
  Write-Host "    [Environment]::SetEnvironmentVariable('Path', `"`$env:Path;$InstallDir`", 'User')"
  Write-Host ""
  Warn "Then open a new PowerShell window."
}

Write-Host ""
Write-Host "Done. Run jobhunt with:" -ForegroundColor Green
Write-Host ""
Write-Host "    jobhunt app"
Write-Host ""
Write-Host "That starts the server and opens it in your browser."
Write-Host "Source code & docs: https://github.com/$Repo"
Write-Host ""
