#!/usr/bin/env python3
"""
YMCA Card Maker CLI v1.5

This keeps the locked YMCA geometry you validated, but adds:
- Header fields as runtime variables (URL + title)
- A small association picker database (profiles/associations.json) used by the GUI (optional)
- Cleaner template generation support (scripts/make_templates.ps1)

Config precedence (highest -> lowest):
1) CLI flags
2) .user_config.json (created by GUI, gitignored)
3) profiles/ymca.json (repo default)
4) auto-detect relative to this script

Reports:
- barcode_svg
- barcode_png
- ymca_letter_1up
- ymca_cr80_1up
- ymca_letter_6up
- ymca_letter_6up_mixed (left column plain, right column checksum)

Note: this CLI uses Zint to generate Code 39 barcodes (SVG/PNG).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF


VERSION = "1.5"

def get_app_dir() -> Path:
    """Directory where the app should read/write *user* files."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent  # repo root (src/..)

def get_resource_dir() -> Path:
    """Directory where bundled resources live (PyInstaller uses sys._MEIPASS)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(getattr(sys, '_MEIPASS')).resolve()
    return get_app_dir()

APP_DIR = get_app_dir()
RES_DIR = get_resource_dir()

# Prefer an external profiles/ folder next to the exe for "portable" builds,
# but fall back to bundled resources when running onefile.
PROFILE_DEFAULT = (APP_DIR / 'profiles' / 'ymca.json')
if not PROFILE_DEFAULT.exists():
    PROFILE_DEFAULT = (RES_DIR / 'profiles' / 'ymca.json')

# User config should live next to the exe (portable) or repo root (dev).
USER_CONFIG_DEFAULT = (APP_DIR / '.user_config.json')


PAGE_SIZE_LETTER = letter

# --- Locked geometry (from your validated v0.9/v1.x) ---
# Card size: CR80
CARD_W = 85.60 * mm
CARD_H = 53.98 * mm
CARD_RADIUS = 3.0 * mm

# Baselines from top (user-provided)
URL_BASELINE_FROM_TOP = 11.5 * mm  # ~11-12mm
TITLE_BASELINE_FROM_TOP = 18.5 * mm  # ~18-19mm

# Header fonts (kept locked)
HEADER_FONT_NAME = "Helvetica"
HEADER_TITLE_FONT_NAME = "Helvetica-Bold"
URL_FONT_SIZE_PT = 12
TITLE_FONT_SIZE_PT = 12

# Barcode placement from bottom
BARCODE_BOTTOM_FROM_BOTTOM = 5.5 * mm  # bottom of bars
BARCODE_HEIGHT = 13.0 * mm
BARCODE_WIDTH = 59.2 * mm

# Barcode text baseline from bottom
BOTTOM_TEXT_BASELINE_FROM_BOTTOM = 3.0 * mm
BOTTOM_TEXT_SIZE_PT = 6  # OCR-B 6pt

# Holes
HOLE_DIAMETER = 6.0 * mm
HOLE_Y_FROM_TOP = 24.0 * mm
HOLE_X1_FROM_LEFT = 17.0 * mm
HOLE_X2_FROM_LEFT = 30.0 * mm

# Layout for 2x3 on letter
COLS = 2
ROWS = 3

# General defaults (repo-safe)
DEFAULT_HEADER_URL = "ymca.org"
DEFAULT_HEADER_TITLE = "YMCA"
DEFAULT_DATA = "YXXXX0123456"

C39_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-. $/+%"


def mod43_check_digit(data: str) -> str:
    clean = data.upper().replace("*", "")
    s = 0
    for ch in clean:
        s += C39_CHARS.index(ch)
    return C39_CHARS[s % 43]


def safe_filename(s: str) -> str:
    s2 = re.sub(r"[^A-Za-z0-9._-]+", "_", s.strip())
    return s2[:120] if len(s2) > 120 else s2


@dataclass
class Paths:
    zint_exe: Path
    ocrb_ttf: Path
    out_dir: Path
    gen_dir: Path


def load_json_if_exists(p: Path) -> dict:
    if p and p.exists():
        # utf-8-sig tolerates Windows BOM
        return json.loads(p.read_text(encoding="utf-8-sig"))
    return {}


def detect_zint_exe(repo_root: Path) -> Optional[Path]:
    candidates = [
        repo_root / "vendor" / "zint" / "zint-2.12.0" / "zint.exe",
        repo_root / "zint-2.12.0" / "zint.exe",
        repo_root / "zint.exe",
        repo_root / "zint-2.12.0" / "zint",
        repo_root / "zint",
    ]
    for c in candidates:
        if c.exists():
            return c
    for c in repo_root.rglob("zint*"):
        if c.name.lower() in {"zint.exe", "zint"} and c.is_file():
            return c
    which = shutil.which("zint")
    if which:
        return Path(which)
    return None


def detect_ocrb_font(repo_root: Path) -> Optional[Path]:
    candidates = [
        repo_root / "assets" / "fonts" / "OCR-B.ttf",
        repo_root / "font" / "OCR-B.ttf",  # legacy
        repo_root / "assets" / "fonts" / "OCR-B.otf",
        repo_root / "font" / "OCR-B.otf",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def merge_paths(cli_args: argparse.Namespace) -> Paths:
    profile = load_json_if_exists(PROFILE_DEFAULT)
    user_cfg = load_json_if_exists(USER_CONFIG_DEFAULT)

    def pick(key: str, default: str = "") -> str:
        v = getattr(cli_args, key, None)
        if v:
            return str(v)
        if key in user_cfg and user_cfg[key]:
            return str(user_cfg[key])
        paths = profile.get("paths", {})
        if key in paths and paths[key]:
            return str(paths[key])
        return default

    zint_str = pick("zint_exe", "")
    zint = Path(zint_str) if zint_str else None
    if zint and not zint.is_absolute():
        zint = (APP_DIR / zint).resolve() if (APP_DIR / zint).exists() else (RES_DIR / zint).resolve()
    if not zint or not zint.exists():
        zint = detect_zint_exe(APP_DIR) or detect_zint_exe(RES_DIR)
    if not zint or not zint.exists():
        raise FileNotFoundError("Cannot find Zint. Set --zint-exe or put the binary under ./zint-2.12.0/zint or ensure it is on PATH.")

    font_str = pick("ocrb_ttf", "")
    font = Path(font_str) if font_str else None
    if font and not font.is_absolute():
        font = (APP_DIR / font).resolve() if (APP_DIR / font).exists() else (RES_DIR / font).resolve()
    if not font or not font.exists():
        font = detect_ocrb_font(APP_DIR) or detect_ocrb_font(RES_DIR)
    if not font or not font.exists():
        raise FileNotFoundError("Cannot find OCR-B font. Put OCR-B.ttf in assets/fonts/ or set --ocrb-ttf")

    out_dir = Path(pick("out_dir", "out"))
    gen_dir = Path(pick("gen_dir", ".gen_barcodes"))
    if not out_dir.is_absolute():
        out_dir = (APP_DIR / out_dir).resolve()
    if not gen_dir.is_absolute():
        gen_dir = (APP_DIR / gen_dir).resolve()

    return Paths(zint_exe=zint, ocrb_ttf=font, out_dir=out_dir, gen_dir=gen_dir)


def merge_header_defaults(cli_args: argparse.Namespace) -> Tuple[str, str, str]:
    """
    Returns (header_url, header_title, default_data) where each value can be overridden by:
    CLI -> .user_config.json -> profiles/ymca.json -> hardcoded defaults
    """
    profile = load_json_if_exists(PROFILE_DEFAULT)
    user_cfg = load_json_if_exists(USER_CONFIG_DEFAULT)

    def pick(key: str, fallback: str) -> str:
        v = getattr(cli_args, key, None)
        if v:
            return str(v)
        if key in user_cfg and user_cfg[key]:
            return str(user_cfg[key])
        if key in profile and profile[key]:
            return str(profile[key])
        return fallback

    header_url = pick("header_url", DEFAULT_HEADER_URL)
    header_title = pick("header_title", DEFAULT_HEADER_TITLE)
    default_data = pick("default_data", DEFAULT_DATA)
    return header_url, header_title, default_data


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def choose_output_path(out_dir: Path, stem: str, ext: str, timestamp: bool) -> Path:
    ensure_dir(out_dir)
    if timestamp:
        import datetime as _dt
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        return out_dir / f"{stem}__{ts}.{ext}"
    return out_dir / f"{stem}.{ext}"


def zint_make_svg(zint_exe: Path, data: str, out_svg: Path, include_text: bool) -> None:
    ensure_dir(out_svg.parent)
    args = [str(zint_exe), "-b", "8", "-d", data, "--output", str(out_svg), "--filetype", "SVG"]
    if not include_text:
        args += ["--notext"]
    subprocess.run(args, check=True, capture_output=True)


def zint_make_png(zint_exe: Path, data: str, out_png: Path, include_text: bool, png_scale: float, scalexdimdp: str) -> None:
    ensure_dir(out_png.parent)
    args = [str(zint_exe), "-b", "8", "-d", data, "--output", str(out_png), "--filetype", "PNG"]
    if not include_text:
        args += ["--notext"]
    if png_scale:
        args += ["--scale", str(png_scale)]
    if scalexdimdp:
        args += ["--scalexdimdp", scalexdimdp]
    subprocess.run(args, check=True, capture_output=True)


def build_data(raw: str, checksum: bool, plus: bool) -> Tuple[str, str]:
    data = raw.strip().upper()
    if plus:
        data = "+" + data
    bottom = data
    if checksum:
        cd = mod43_check_digit(data)
        data = data + cd
        bottom = bottom + cd
    return data, bottom


def register_ocrb(font_path: Path) -> str:
    name = "OCRB"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(font_path)))
    return name


def draw_rounded_card(c: canvas.Canvas, x: float, y: float) -> None:
    c.setLineWidth(0.5)
    c.roundRect(x, y, CARD_W, CARD_H, CARD_RADIUS, stroke=1, fill=0)


def draw_holes(c: canvas.Canvas, x: float, y: float) -> None:
    c.setLineWidth(0.8)
    cx1 = x + HOLE_X1_FROM_LEFT
    cx2 = x + HOLE_X2_FROM_LEFT
    cy = y + CARD_H - HOLE_Y_FROM_TOP
    r = HOLE_DIAMETER / 2.0
    c.circle(cx1, cy, r, stroke=1, fill=0)
    c.circle(cx2, cy, r, stroke=1, fill=0)


def draw_header(c: canvas.Canvas, x: float, y: float, header_url: str, header_title: str) -> None:
    c.setFont(HEADER_FONT_NAME, URL_FONT_SIZE_PT)
    url_y = y + CARD_H - URL_BASELINE_FROM_TOP
    c.drawCentredString(x + CARD_W / 2.0, url_y, header_url)

    c.setFont(HEADER_TITLE_FONT_NAME, TITLE_FONT_SIZE_PT)
    title_y = y + CARD_H - TITLE_BASELINE_FROM_TOP
    c.drawCentredString(x + CARD_W / 2.0, title_y, header_title)


def draw_barcode_svg(c: canvas.Canvas, x: float, y: float, svg_path: Path) -> None:
    drawing = svg2rlg(str(svg_path))
    sx = BARCODE_WIDTH / drawing.width
    sy = BARCODE_HEIGHT / drawing.height
    drawing.scale(sx, sy)

    bx = x + (CARD_W - BARCODE_WIDTH) / 2.0
    by = y + BARCODE_BOTTOM_FROM_BOTTOM
    renderPDF.draw(drawing, c, bx, by)


def draw_bottom_text(c: canvas.Canvas, x: float, y: float, font_name: str, bottom_text: str) -> None:
    c.setFont(font_name, BOTTOM_TEXT_SIZE_PT)
    tx = x + CARD_W / 2.0
    ty = y + BOTTOM_TEXT_BASELINE_FROM_BOTTOM
    c.drawCentredString(tx, ty, bottom_text)


def draw_ymca_card(
    c: canvas.Canvas,
    x: float,
    y: float,
    svg_path: Path,
    bottom_text: str,
    ocrb_font: str,
    holes_enabled: bool,
    header_url: str,
    header_title: str,
) -> None:
    draw_rounded_card(c, x, y)
    draw_header(c, x, y, header_url=header_url, header_title=header_title)
    if holes_enabled:
        draw_holes(c, x, y)
    draw_barcode_svg(c, x, y, svg_path)
    draw_bottom_text(c, x, y, ocrb_font, bottom_text)


def letter_layout_positions() -> Tuple[float, float, float, float]:
    margin_x = 12 * mm
    margin_top = 12 * mm
    gap_x = 12 * mm
    gap_y = 18 * mm

    page_w, page_h = PAGE_SIZE_LETTER
    start_x = margin_x
    start_y_top = page_h - margin_top - CARD_H
    return start_x, start_y_top, gap_x, gap_y


def report_barcode_svg(paths: Paths, raw: str, checksum: bool, plus: bool, include_text: bool, timestamp: bool) -> Path:
    data, _bottom = build_data(raw, checksum=checksum, plus=plus)
    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__barcode_svg_{'chk' if checksum else 'plain'}", "svg", timestamp)
    zint_make_svg(paths.zint_exe, data, out, include_text=include_text)
    print(f"Created: {out}")
    return out


def report_barcode_png(paths: Paths, raw: str, checksum: bool, plus: bool, include_text: bool, png_scale: float, scalexdimdp: str, timestamp: bool) -> Path:
    data, _bottom = build_data(raw, checksum=checksum, plus=plus)
    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__barcode_png_{'chk' if checksum else 'plain'}", "png", timestamp)
    zint_make_png(paths.zint_exe, data, out, include_text=include_text, png_scale=png_scale, scalexdimdp=scalexdimdp)
    print(f"Created: {out}")
    return out


def report_ymca_letter_1up(paths: Paths, raw: str, checksum: bool, plus: bool, holes: bool, header_url: str, header_title: str, timestamp: bool) -> Path:
    data, bottom = build_data(raw, checksum=checksum, plus=plus)

    ensure_dir(paths.gen_dir)
    svg = paths.gen_dir / f"{safe_filename(data)}.svg"
    if not svg.exists():
        zint_make_svg(paths.zint_exe, data, svg, include_text=False)

    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__ymca_letter_1up_{'chk' if checksum else 'plain'}", "pdf", timestamp)
    c = canvas.Canvas(str(out), pagesize=PAGE_SIZE_LETTER)
    ocrb = register_ocrb(paths.ocrb_ttf)

    start_x, start_y_top, _, _ = letter_layout_positions()
    draw_ymca_card(c, start_x, start_y_top, svg, bottom, ocrb_font=ocrb, holes_enabled=holes, header_url=header_url, header_title=header_title)

    c.showPage()
    c.save()
    print(f"Created: {out}")
    return out


def report_ymca_cr80_1up(paths: Paths, raw: str, checksum: bool, plus: bool, holes: bool, header_url: str, header_title: str, timestamp: bool) -> Path:
    data, bottom = build_data(raw, checksum=checksum, plus=plus)

    ensure_dir(paths.gen_dir)
    svg = paths.gen_dir / f"{safe_filename(data)}.svg"
    if not svg.exists():
        zint_make_svg(paths.zint_exe, data, svg, include_text=False)

    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__ymca_cr80_1up_{'chk' if checksum else 'plain'}", "pdf", timestamp)
    c = canvas.Canvas(str(out), pagesize=(CARD_W, CARD_H))
    ocrb = register_ocrb(paths.ocrb_ttf)

    draw_ymca_card(c, 0, 0, svg, bottom, ocrb_font=ocrb, holes_enabled=holes, header_url=header_url, header_title=header_title)

    c.showPage()
    c.save()
    print(f"Created: {out}")
    return out


def report_ymca_letter_6up(paths: Paths, raw: str, checksum: bool, plus: bool, holes: bool, header_url: str, header_title: str, timestamp: bool) -> Path:
    data, bottom = build_data(raw, checksum=checksum, plus=plus)

    ensure_dir(paths.gen_dir)
    svg = paths.gen_dir / f"{safe_filename(data)}.svg"
    if not svg.exists():
        zint_make_svg(paths.zint_exe, data, svg, include_text=False)

    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__ymca_letter_6up_{'chk' if checksum else 'plain'}", "pdf", timestamp)
    c = canvas.Canvas(str(out), pagesize=PAGE_SIZE_LETTER)
    ocrb = register_ocrb(paths.ocrb_ttf)

    start_x, start_y_top, gap_x, gap_y = letter_layout_positions()
    for i in range(ROWS * COLS):
        row = i // COLS
        col = i % COLS
        x = start_x + col * (CARD_W + gap_x)
        y = start_y_top - row * (CARD_H + gap_y)
        draw_ymca_card(c, x, y, svg, bottom, ocrb_font=ocrb, holes_enabled=holes, header_url=header_url, header_title=header_title)

    c.showPage()
    c.save()
    print(f"Created: {out}")
    return out


def report_ymca_letter_6up_mixed(paths: Paths, raw: str, plus: bool, holes: bool, header_url: str, header_title: str, timestamp: bool) -> Path:
    plain_data, plain_bottom = build_data(raw, checksum=False, plus=plus)
    chk_data, chk_bottom = build_data(raw, checksum=True, plus=plus)

    ensure_dir(paths.gen_dir)
    plain_svg = paths.gen_dir / f"{safe_filename(plain_data)}.svg"
    chk_svg = paths.gen_dir / f"{safe_filename(chk_data)}.svg"
    if not plain_svg.exists():
        zint_make_svg(paths.zint_exe, plain_data, plain_svg, include_text=False)
    if not chk_svg.exists():
        zint_make_svg(paths.zint_exe, chk_data, chk_svg, include_text=False)

    out = choose_output_path(paths.out_dir, f"{safe_filename(raw)}__ymca_letter_6up_mixed", "pdf", timestamp)
    c = canvas.Canvas(str(out), pagesize=PAGE_SIZE_LETTER)
    ocrb = register_ocrb(paths.ocrb_ttf)

    start_x, start_y_top, gap_x, gap_y = letter_layout_positions()
    for i in range(ROWS * COLS):
        row = i // COLS
        col = i % COLS
        x = start_x + col * (CARD_W + gap_x)
        y = start_y_top - row * (CARD_H + gap_y)
        if col == 0:
            draw_ymca_card(c, x, y, plain_svg, plain_bottom, ocrb_font=ocrb, holes_enabled=holes, header_url=header_url, header_title=header_title)
        else:
            draw_ymca_card(c, x, y, chk_svg, chk_bottom, ocrb_font=ocrb, holes_enabled=holes, header_url=header_url, header_title=header_title)

    c.showPage()
    c.save()
    print(f"Created: {out}")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("-d", "--data", default="", help="Raw code, e.g. YXXXX0123456 (defaults can come from config)")
    p.add_argument("-r", "--report", required=True, help="Report name")
    p.add_argument("--checksum", action="store_true", help="Append Mod43 check digit (not used for mixed report)")
    p.add_argument("--text", action="store_true", help="Include human-readable text in barcode-only outputs")
    p.add_argument("--plus", action="store_true", help="Prefix raw code with '+' before encoding/checksum")
    p.add_argument("--timestamp", action="store_true", help="Timestamp output filename to avoid overwrite/locks")
    p.add_argument("--no-holes", action="store_true", help="Disable holes on YMCA cards")

    # Header overrides
    p.add_argument("--header-url", dest="header_url", default="", help="Header URL string (e.g. ymca.org)")
    p.add_argument("--header-title", dest="header_title", default="", help="Header title string (e.g. YMCA)")
    p.add_argument("--default-data", dest="default_data", default="", help="Default data value (used only if --data omitted)")

    # path overrides
    p.add_argument("--zint-exe", dest="zint_exe", default="", help="Path to zint.exe")
    p.add_argument("--ocrb-ttf", dest="ocrb_ttf", default="", help="Path to OCR-B.ttf")
    p.add_argument("--out-dir", dest="out_dir", default="", help="Output directory")
    p.add_argument("--gen-dir", dest="gen_dir", default="", help="Barcode cache directory")

    # png options
    p.add_argument("--png-scale", dest="png_scale", default="5.0", help="Zint --scale for PNG output")
    p.add_argument("--png-scalexdimdp", dest="png_scalexdimdp", default="", help="Zint --scalexdimdp for PNG output")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    paths = merge_paths(args)
    header_url, header_title, default_data = merge_header_defaults(args)

    holes = not args.no_holes
    report = args.report.strip()
    raw = (args.data or "").strip() or default_data

    plus = bool(args.plus)
    checksum = bool(args.checksum)
    include_text = bool(args.text)
    timestamp = bool(args.timestamp)

    if report == "barcode_svg":
        report_barcode_svg(paths, raw, checksum=checksum, plus=plus, include_text=include_text, timestamp=timestamp)
    elif report == "barcode_png":
        report_barcode_png(paths, raw, checksum=checksum, plus=plus, include_text=include_text, png_scale=float(args.png_scale), scalexdimdp=args.png_scalexdimdp, timestamp=timestamp)
    elif report == "ymca_letter_1up":
        report_ymca_letter_1up(paths, raw, checksum=checksum, plus=plus, holes=holes, header_url=header_url, header_title=header_title, timestamp=timestamp)
    elif report == "ymca_cr80_1up":
        report_ymca_cr80_1up(paths, raw, checksum=checksum, plus=plus, holes=holes, header_url=header_url, header_title=header_title, timestamp=timestamp)
    elif report == "ymca_letter_6up":
        report_ymca_letter_6up(paths, raw, checksum=checksum, plus=plus, holes=holes, header_url=header_url, header_title=header_title, timestamp=timestamp)
    elif report == "ymca_letter_6up_mixed":
        report_ymca_letter_6up_mixed(paths, raw, plus=plus, holes=holes, header_url=header_url, header_title=header_title, timestamp=timestamp)
    else:
        raise SystemExit(f"Unknown report: {report}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or b"").decode(errors="ignore") if isinstance(e.stderr, (bytes, bytearray)) else str(e.stderr)
        print("Zint failed.")
        if msg:
            print(msg)
        raise
