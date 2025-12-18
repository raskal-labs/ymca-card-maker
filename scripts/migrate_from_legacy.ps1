param(
  [string]$LegacyRoot = "C:\Barcode",
  [string]$NewRootName = "ymca_card_maker"
)

$ErrorActionPreference = "Stop"

$legacy = Resolve-Path $LegacyRoot
$newRoot = Join-Path $legacy $NewRootName

Write-Host "Legacy: $legacy"
Write-Host "New:    $newRoot"

if (-not (Test-Path $newRoot)) {
  New-Item -ItemType Directory -Path $newRoot | Out-Null
}

# Create structure
$dirs = @(
  "src","profiles","assets\fonts","scripts","tools","docs","examples","history","out",".gen_barcodes",".trash"
)
foreach ($d in $dirs) {
  New-Item -ItemType Directory -Force -Path (Join-Path $newRoot $d) | Out-Null
}

# Move legacy history files if present
$legacyHistory = Join-Path $legacy "history"
if (Test-Path $legacyHistory) {
  Write-Host "Moving legacy history -> $newRoot\history"
  robocopy $legacyHistory (Join-Path $newRoot "history") /E /MOVE | Out-Null
}

# Move fonts
$legacyFont = Join-Path $legacy "font"
if (Test-Path $legacyFont) {
  Write-Host "Moving legacy font -> $newRoot\assets\fonts (keeps filenames)"
  robocopy $legacyFont (Join-Path $newRoot "assets\fonts") /E | Out-Null
}

# Move zint folder (kept as vendor-ish, not committed by default)
$legacyZint = Join-Path $legacy "zint-2.12.0-win32"
if (Test-Path $legacyZint) {
  Write-Host "Moving legacy zint -> $newRoot\vendor\zint"
  New-Item -ItemType Directory -Force -Path (Join-Path $newRoot "vendor\zint") | Out-Null
  robocopy $legacyZint (Join-Path $newRoot "vendor\zint") /E | Out-Null
}

# Move old scripts into history/ (optional)
Get-ChildItem $legacy -Filter "make_sheet*.py" -File -ErrorAction SilentlyContinue | ForEach-Object {
  Write-Host "Archiving legacy script: $($_.Name)"
  Move-Item $_.FullName (Join-Path $newRoot "history\$($_.Name)") -Force
}

Write-Host "Done. New repo root: $newRoot"
Write-Host "Next: copy in the new v1.4 src files (from the bundle), then init git."
