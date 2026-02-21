<#
.SYNOPSIS
  PROJECT AEGIS — ShobNG Plugin Installer (Windows)

.DESCRIPTION
  Copies the gesture-control plugin files into an existing ShobNG installation.
  Does NOT modify the ShobNG git history — just drops files in place.

.PARAMETER ShobNGPath
  Path to the root of your ShobNG repo/installation.
  Defaults to ..\ShobNG relative to this script.

.EXAMPLE
  .\install.ps1
  .\install.ps1 -ShobNGPath "C:\Projects\ShobNG"
#>

param(
    [string]$ShobNGPath = (Resolve-Path (Join-Path $PSScriptRoot "..\ShobNG") -ErrorAction SilentlyContinue)
)

$ErrorActionPreference = "Stop"

# ── Resolve ShobNG path ───────────────────────────────────────────────────────
if (-not $ShobNGPath -or -not (Test-Path $ShobNGPath)) {
    Write-Host ""
    Write-Host "Could not auto-detect ShobNG path." -ForegroundColor Yellow
    $ShobNGPath = Read-Host "Enter the full path to your ShobNG directory"
}

$ShobNGPath = $ShobNGPath.TrimEnd('\', '/')

if (-not (Test-Path "$ShobNGPath\frontend\src\plugins")) {
    Write-Error "ShobNG plugin directory not found at: $ShobNGPath\frontend\src\plugins`nMake sure the path points to the ShobNG repo root."
}

# ── Copy plugin files ─────────────────────────────────────────────────────────
$src  = Join-Path $PSScriptRoot "shobng-plugin\frontend\src\plugins\gesture-control"
$dest = Join-Path $ShobNGPath  "frontend\src\plugins\gesture-control"

Write-Host ""
Write-Host "PROJECT AEGIS — ShobNG Plugin Installer" -ForegroundColor Cyan
Write-Host "  Source : $src"
Write-Host "  Target : $dest"
Write-Host ""

if (Test-Path $dest) {
    Write-Host "Existing plugin directory found — overwriting." -ForegroundColor Yellow
}

New-Item -ItemType Directory -Path $dest -Force | Out-Null
Copy-Item "$src\*" $dest -Recurse -Force

Write-Host "Plugin files installed successfully." -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start the AEGIS backend:  cd backend && python main.py --source 1"
Write-Host "  2. Start ShobNG:             cd $ShobNGPath && .\start.ps1"
Write-Host "  3. Open the Plugins panel in ShobNG and enable 'Gesture Control'."
Write-Host ""
