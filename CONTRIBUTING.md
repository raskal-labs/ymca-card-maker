# Contributing

Thanks for helping improve YMCA Card Maker! This document covers development setup and contribution basics.

## Code of conduct
Be respectful and collaborative. When in doubt, prefer clear communication and small, reviewable changes.

## Development environment
The project targets Python 3.10+. A typical local setup:

1. Create and activate a virtual environment:
   - **macOS/Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
   - **Windows (PowerShell):**
     ```powershell
     py -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
2. Install dependencies (pinned):
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```
3. Provide non-Python assets:
   - Install **Zint** and ensure `zint`/`zint.exe` is on PATH or placed under `./zint-2.12.0/`.
   - Add an OCR-B font at `assets/fonts/OCR-B.ttf` (or `.otf`).

## Running the tools
- **CLI (direct):**
  ```bash
  python src/ymca_card_maker.py -r ymca_letter_6up -d YXXXX0123456 --timestamp
  ```
- **CLI (config-driven wrapper):**
  ```bash
  ./scripts/ymca-card-cli --profile profiles/sample.json --out ./output/test
  ```
- **GUI:**
  ```bash
  python src/ymca_card_maker_gui.py
  ```

## Linting and checks
- Syntax check:
  ```bash
  python -m compileall src
  ```
- Dependency sanity check (optional, requires Zint/font):
  ```bash
  python src/check_deps.py --repo-root .
  ```

## Pull requests
- Keep changes focused and documented.
- Update README/docs when behavior or setup changes.
- Ensure CI passes before requesting review.
