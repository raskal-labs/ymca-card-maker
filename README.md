# YMCA Card Maker

A precise, locked-geometry toolchain for generating **YMCA-style barcode cards** and print sheets.

This project was built to reliably produce scannable, print-accurate barcode cards with strict physical dimensions, consistent typography, and predictable layout. Geometry and spacing are intentionally fixed to match a validated physical card.

The tool supports both **CLI** and **GUI** usage and is safe to publish: all defaults are generic, and personal data lives only in local, ignored config.

---

## Features

- Code 39 barcode generation (via Zint)
- Optional Mod43 checksum
- High-resolution barcode-only outputs (SVG / PNG)
- YMCA card layouts:
  - 1-up on Letter
  - 1-up CR80 (credit-card sized)
  - 6-up Letter sheets
  - 6-up mixed (plain + checksum split by column)
- Locked, print-validated geometry
- Configurable header URL and title
- CLI and Windows GUI
- Association presets (optional)
- Personal defaults stored locally and never committed

---

## Defaults (Repo-Safe)

These are the **generic defaults** used by the repository:

- **Barcode data:** `YXXXX0123456`
- **Header URL:** `ymca.org`
- **Header title:** `YMCA`

Your personal defaults (real codes, local URLs, paths) belong in:

```
.user_config.json   (gitignored)
```

---

## Requirements

### Python
- Python 3.10+

Install required packages:

```bash
py -m pip install reportlab svglib
```

### Zint
Download Zint 2.12.x and place it at:

```
zint-2.12.0/zint.exe
```

Zint is **not** committed to the repo.

### OCR-B Font
Provide an OCR-B font (TTF or OTF) at:

```
assets/fonts/OCR-B.ttf
```

(Font files are intentionally gitignored.)

---

## CLI Usage

Basic syntax:

```bash
py src/ymca_card_maker.py -r <report> -d <data>
```

### Reports

| Report name | Output |
|------------|--------|
| `barcode_svg` | Single barcode (SVG) |
| `barcode_png` | Single barcode (PNG) |
| `ymca_letter_1up` | One card on Letter (top-left) |
| `ymca_cr80_1up` | CR80-sized page |
| `ymca_letter_6up` | 6-up Letter sheet |
| `ymca_letter_6up_mixed` | 3 plain + 3 checksum (split by column) |

### Common Flags

```bash
--checksum        Append Mod43 check digit
--text            Include human-readable text (barcode-only)
--timestamp       Timestamp output filename to avoid overwrite/locks
--no-holes        Disable punch holes on card layouts
--header-url      Override header URL
--header-title    Override header title
--default-data    Override the default data used when --data is omitted
```

### Example (generic)

```bash
py src/ymca_card_maker.py \
  -d YXXXX0123456 \
  -r ymca_letter_6up_mixed \
  --header-url ymca.org \
  --header-title YMCA \
  --timestamp
```

### CLI on Debian/Proxmox

For Debian or Proxmox LXC hosts, use the non-interactive wrapper and follow the Debian notes in [docs/cli-setup-debian.md](docs/cli-setup-debian.md):

```bash
./scripts/ymca-card-cli --profile profiles/sample.json --out ./output/test
```

The wrapper auto-detects `/etc` or `~/.config` configs, warns about container limitations, and writes artifacts under the requested output directory.

---

## GUI Usage (Windows)

Launch:

```bash
py src/ymca_card_maker_gui.py
```

The GUI allows:
- entering barcode data
- selecting a report
- toggling checksum / text
- setting header URL and title
- managing paths via local config

All GUI settings persist in `.user_config.json`.

---

## Repo Hygiene

This repo intentionally does **not** include:
- real barcodes
- fonts
- Zint binaries
- generated PDFs / images
- personal configuration

All such artifacts should be ignored via `.gitignore`.

---

## License

This project is provided as-is.

Ensure you comply with licenses for Zint and any fonts you use.
