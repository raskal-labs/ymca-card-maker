[CmdletBinding()]
param(
  [string]$Data = "YXXXX0123456",
  [string]$HeaderUrl = "ymca.org",
  [string]$HeaderTitle = "YMCA",
  [string]$OutDir = ".\templates",
  [switch]$Timestamp
)

$ErrorActionPreference = "Stop"

# Ensure OutDir exists
New-Item -ItemType Directory -Force $OutDir | Out-Null

# Default: timestamp ON unless explicitly disabled
$useTimestamp = $true
if ($PSBoundParameters.ContainsKey("Timestamp")) {
  $useTimestamp = [bool]$Timestamp
}

function Run-Report {
  param(
    [Parameter(Mandatory=$true)][string]$Label,
    [Parameter(Mandatory=$true)][string]$Report,
    [switch]$Checksum
  )

  Write-Host "==> $Label"

  $args = @(
    ".\src\ymca_card_maker.py",
    "-d", $Data,
    "-r", $Report,
    "--out-dir", $OutDir,
    "--header-url", $HeaderUrl,
    "--header-title", $HeaderTitle
  )

  if ($Checksum) { $args += "--checksum" }
  if ($useTimestamp) { $args += "--timestamp" }

  # Call py with argument array (this is the key fix)
  & py @args
  if ($LASTEXITCODE -ne 0) { throw "Report failed: $Label" }
}

# Barcode-only
Run-Report -Label "barcode_svg_plain"     -Report "barcode_svg"
Run-Report -Label "barcode_svg_checksum"  -Report "barcode_svg" -Checksum
Run-Report -Label "barcode_png_plain"     -Report "barcode_png"
Run-Report -Label "barcode_png_checksum"  -Report "barcode_png" -Checksum

# YMCA card PDFs
Run-Report -Label "ymca_letter_1up_plain"    -Report "ymca_letter_1up"
Run-Report -Label "ymca_letter_1up_checksum" -Report "ymca_letter_1up" -Checksum
Run-Report -Label "ymca_cr80_1up_plain"      -Report "ymca_cr80_1up"
Run-Report -Label "ymca_cr80_1up_checksum"   -Report "ymca_cr80_1up" -Checksum

# Sheets
Run-Report -Label "ymca_letter_6up_plain"    -Report "ymca_letter_6up"
Run-Report -Label "ymca_letter_6up_checksum" -Report "ymca_letter_6up" -Checksum

Write-Host ""
Write-Host "Templates written to: $OutDir"
