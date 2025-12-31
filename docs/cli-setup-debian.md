# Linux/Proxmox CLI setup

These steps were validated on Debian/Proxmox-style environments and focus on the CLI workflow.

## Install packages

```bash
sudo apt update
sudo apt install python3 python3-pip python3-reportlab python3-svglib zint
```

> If your distro package versions are old or missing, you can instead run:
>
> ```bash
> python3 -m pip install --upgrade pip
> python3 -m pip install reportlab svglib
> sudo apt install zint
> ```

## Provide the OCR-B font

Place an OCR-B TTF/OTF file at:

```
assets/fonts/OCR-B.ttf   (preferred)
```

Alternative locations the CLI will find:

- `assets/fonts/OCR-B.otf`
- `font/OCR-B.ttf` or `font/OCR-B.otf` (legacy folder)

If you install the font system-wide (e.g., `/usr/local/share/fonts`), also copy it into `assets/fonts/` so the CLI can load it without extra configuration.

## Smoke test

From the repo root:

```bash
./scripts/ymca_card_cli.sh -r barcode_svg -d TEST123 --text
```

Expected output:

- Dependency checks pass (or install automatically)
- Zint is detected on `$PATH`
- A barcode SVG is created in the `out/` folder
