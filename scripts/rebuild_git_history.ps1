param(
  [string]$RepoRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent),
  [string]$LegacyHistoryDir = ""
)

$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

if (-not (Test-Path ".git")) {
  git init
}

# Where legacy versions live (you already have these)
if ($LegacyHistoryDir -eq "") {
  $LegacyHistoryDir = Join-Path $RepoRoot "history"
}

if (-not (Test-Path $LegacyHistoryDir)) {
  throw "Cannot find legacy history dir: $LegacyHistoryDir"
}

# Map legacy versions -> commit order
$versions = @(
  "make_sheet_v0.1.py",
  "make_sheet_v0.2.py",
  "make_sheet_v0.3.py",
  "make_sheet_v0.4.py",
  "make_sheet_v0.9.py"
)

# Commit each legacy version as src/legacy/make_sheet.py
New-Item -ItemType Directory -Force -Path "src\legacy" | Out-Null

foreach ($v in $versions) {
  $src = Join-Path $LegacyHistoryDir $v
  if (-not (Test-Path $src)) {
    Write-Host "Skipping missing: $src"
    continue
  }

  Copy-Item $src "src\legacy\make_sheet.py" -Force
  git add "src\legacy\make_sheet.py"
  git commit -m "history: import $v"
}

# Finally commit current v1.4 code + repo files
git add .
git commit -m "v1.4: repo layout, CLI+GUI with configurable paths"

Write-Host "Done. Review with: git log --oneline --decorate"
