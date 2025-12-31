#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON:-python3}"

echo "=== YMCA Card Maker CLI helper ==="
echo "Using Python: ${PYTHON_BIN}"

echo "--- Checking Python dependencies (reportlab, svglib) ---"
if ! "${PYTHON_BIN}" - <<'PY'
import importlib
missing = []
for mod in ("reportlab", "svglib"):
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError:
        missing.append(mod)

if missing:
    raise SystemExit("MISSING:" + ",".join(missing))
PY
then
  echo "Installing missing Python packages..."
  "${PYTHON_BIN}" -m pip install --upgrade pip >/dev/null
  "${PYTHON_BIN}" -m pip install reportlab svglib
fi

echo "--- Verifying Zint ---"
if command -v zint >/dev/null 2>&1; then
  echo "Found zint on PATH: $(command -v zint)"
elif [ -x "${REPO_ROOT}/zint-2.12.0/zint.exe" ]; then
  echo "Using bundled Windows Zint at ./zint-2.12.0/zint.exe"
elif [ -x "${REPO_ROOT}/vendor/zint/zint-2.12.0/zint.exe" ]; then
  echo "Using bundled Windows Zint at ./vendor/zint/zint-2.12.0/zint.exe"
else
  echo "Warning: Zint not found on PATH or in ./zint-2.12.0/zint.exe"
fi

echo "--- Verifying OCR-B font ---"
if [ -f "${REPO_ROOT}/assets/fonts/OCR-B.ttf" ] || [ -f "${REPO_ROOT}/assets/fonts/OCR-B.otf" ]; then
  echo "Found OCR-B font in assets/fonts/"
elif [ -f "${REPO_ROOT}/font/OCR-B.ttf" ] || [ -f "${REPO_ROOT}/font/OCR-B.otf" ]; then
  echo "Found OCR-B font in legacy ./font directory"
else
  echo "Warning: OCR-B font not found in assets/fonts/ (expected OCR-B.ttf or OCR-B.otf)"
fi

echo "--- Running CLI ---"
exec "${PYTHON_BIN}" "${REPO_ROOT}/src/ymca_card_maker.py" "$@"
