# YMCA Card Maker CLI on Debian / Proxmox LXC

This guide documents the CLI-first workflow and the bits you need for Debian hosts and Proxmox LXC containers.

## Entrypoints and scope audit
- **CLI renderer (core):** `src/ymca_card_maker.py` hosts all rendering functions (PDF/SVG/PNG). It runs headless.
- **Dedicated CLI wrapper:** `src/cli_runner.py` and `scripts/ymca-card-cli` provide config discovery, profile loading, and Proxmox/LXC-aware logging.
- **Dependency checker:** `src/check_deps.py` verifies Python libs, Tk availability (GUI), Zint, and the OCR-B font.
- **GUI-only module:** `src/ymca_card_maker_gui.py` is Tkinter-based and Windows-centric; omit it on minimal Debian hosts.
- **Scripts folder:** only PowerShell utilities for Windows builds live here aside from the new `ymca-card-cli` wrapper.

## Runtime requirements
- **Python:** 3.10+ (3.11 works). Install via `apt install python3 python3-venv python3-pip`.
- **Python libs:** `reportlab`, `svglib`, and (optionally) `pyyaml` for YAML configs. Install with `python3 -m pip install --user reportlab svglib pyyaml`.
- **Zint barcode CLI:** install `zint` from APT (`apt install zint libzint-dev`) or place a 2.12.x build on PATH (the CLI auto-detects `/usr/bin/zint` or bundled copies).
- **GUI bits (optional):** `python3-tk` for Tkinter if you need the GUI.
- **Fonts:** provide `assets/fonts/OCR-B.ttf` (or `.otf`). Package fonts via APT if available, or copy the file into the repo.

## Config discovery (non-root friendly)
The wrapper looks for a config file in this order:
1. `--config /custom/path.yml` (explicit flag)
2. `/etc/ymca-card-maker/config.yml`
3. `$HOME/.config/ymca-card-maker/config.yml`
4. No file found → rely on profile/defaults

Example minimal config (works for unprivileged users when paths are writable):

```yaml
header_url: ymca.org
header_title: YMCA
paths:
  out_dir: output
  gen_dir: .gen_barcodes
  zint_exe: /usr/bin/zint
  ocrb_ttf: assets/fonts/OCR-B.ttf
```

## Proxmox LXC considerations
- The CLI emits an `[env]` line describing container detection, systemd availability, and `/sys` writability.
- LXC containers often lack systemd; favor cron or direct execution rather than systemd units.
- Unprivileged containers usually expose read-only `/sys`; avoid tools that expect hardware access. Rendering works fine without it.
- Keep Zint/font/output paths inside writable volumes for non-root users.

## Non-interactive rendering workflow
- Profiles live under `profiles/` and can be JSON or YAML. A sample is provided at `profiles/sample.json`.
- Invoke the wrapper script (no GUI required):

```bash
./scripts/ymca-card-cli \
  --profile profiles/sample.json \
  --out ./output/test
```

The command reads the profile, merges it with config defaults, prints environment hints, and writes artifacts under `./output/test` (e.g., a `*_ymca_letter_6up_chk.pdf`).

### Smoke test
Run a quick end-to-end render and check for the output PDF:

```bash
./scripts/ymca-card-cli --profile profiles/sample.json --out ./output/test
```

Expected artifact: a PDF named like `YXXXX0123456__ymca_letter_6up_chk.pdf` in `./output/test/`. The CLI logs to stdout/stderr only.

## Service/automation (systemd-less)
Use cron or a simple wrapper when systemd is unavailable:

```bash
#!/bin/sh
cd /opt/ymca-card-maker || exit 1
./scripts/ymca-card-cli --profile profiles/sample.json --out /var/tmp/ymca-output
```

Add it to root or user crontab (adjust paths for writable locations). Include the font/Zint binaries where the config can find them.
