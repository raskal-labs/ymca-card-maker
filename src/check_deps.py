#!/usr/bin/env python3
"""check_deps.py

Sanity-check runtime dependencies for YMCA Card Maker.

Checks:
- Python version
- reportlab import
- svglib import
- Tkinter import (for GUI)
- Zint executable existence + runs "zint --version"
- OCR-B font file existence (if provided)

Usage:
  py .\src\check_deps.py --repo-root .
  py .\src\check_deps.py --zint .\zint-2.12.0\zint.exe --ocrb .\assets\fonts\OCR-B.ttf
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

MIN_PY = (3, 10)

def ok(msg: str) -> None:
    print(f"[OK] {msg}")

def warn(msg: str) -> None:
    print(f"[WARN] {msg}")

def err(msg: str) -> None:
    print(f"[ERR] {msg}")

def find_zint(repo_root: Path) -> Path | None:
    candidates = [
        repo_root / "zint-2.12.0" / "zint.exe",
        repo_root / "zint-2.12.0" / "zint-2.12.0" / "zint.exe",
        repo_root / "zint-2.12.0-win32" / "zint-2.12.0" / "zint.exe",
        repo_root / "_deps" / "zint" / "zint.exe",
        repo_root / "zint-2.12.0" / "zint",
        repo_root / "zint",
    ]
    for c in candidates:
        if c.exists():
            return c
    for c in repo_root.rglob("zint*"):
        if c.name.lower() in {"zint", "zint.exe"}:
            return c
    from_path = shutil.which("zint")
    if from_path:
        return Path(from_path)
    for c in repo_root.rglob("zint.exe"):
        parts = {p.lower() for p in c.parts}
        if "build" in parts or "dist" in parts:
            continue
        return c
    return None

def find_ocrb(repo_root: Path) -> Path | None:
    candidates = [
        repo_root / "assets" / "fonts" / "OCR-B.ttf",
        repo_root / "assets" / "fonts" / "OCR-B.otf",
        repo_root / "font" / "OCR-B.ttf",
        repo_root / "font" / "OCR-B.otf",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--zint", default="", help="Explicit path to zint.exe")
    ap.add_argument("--ocrb", default="", help="Explicit path to OCR-B font")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()

    if sys.version_info < MIN_PY:
        err(f"Python {MIN_PY[0]}.{MIN_PY[1]}+ required, found {sys.version.split()[0]}")
        return 2
    ok(f"Python {sys.version.split()[0]}")

    try:
        import reportlab  # noqa: F401
        ok("reportlab import")
    except Exception as e:
        err(f"reportlab import failed: {e}")
        return 3

    try:
        import svglib  # noqa: F401
        ok("svglib import")
    except Exception as e:
        err(f"svglib import failed: {e}")
        return 4

    try:
        import tkinter  # noqa: F401
        ok("tkinter import (GUI capable)")
    except Exception as e:
        warn(f"tkinter import failed (CLI still works): {e}")

    zint = Path(args.zint).resolve() if args.zint else (find_zint(repo) or Path())
    if not zint or not zint.exists():
        err("Zint binary not found. Put it under ./zint-2.12.0/zint(.exe), ensure it is on PATH, or pass --zint <path>")
        return 5
    ok(f"zint binary found: {zint}")

    try:
        proc = subprocess.run([str(zint), "--version"], capture_output=True, text=True, check=False)
        out = ((proc.stdout or '') + ' ' + (proc.stderr or '')).strip()
        if proc.returncode == 0:
            ok(f"zint --version: {out}")
        else:
            warn(f"zint --version returned code {proc.returncode}: {out}")
    except Exception as e:
        warn(f"Could not run zint --version: {e}")

    ocrb = Path(args.ocrb).resolve() if args.ocrb else (find_ocrb(repo) or Path())
    if ocrb and ocrb.exists():
        ok(f"OCR-B font found: {ocrb}")
    else:
        warn("OCR-B font not found (required for YMCA PDF bottom text). Place at assets/fonts/OCR-B.ttf or pass --ocrb")

    print("\nNext steps:")
    print("  - If reportlab/svglib missing: py -m pip install reportlab svglib")
    print("  - If zint missing: install it via your package manager or place zint(.exe) at ./zint-2.12.0/zint")
    print("  - If OCR-B missing: copy OCR-B.ttf to ./assets/fonts/OCR-B.ttf")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
