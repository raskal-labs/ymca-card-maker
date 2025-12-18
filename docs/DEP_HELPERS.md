# Dependency helpers

Adds:

- `src/check_deps.py` (sanity checker)
- `scripts/setup_windows.ps1` (bootstrap + optional migration)

Zint is expected at repo root: `./zint-2.12.0/zint.exe`.

## Typical usage (Windows)

From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -CopyFromLegacy
py .\src\check_deps.py --repo-root .
py .\src\ymca_card_maker.py -d YXXXX0123456 -r ymca_letter_6up_mixed --timestamp
```

## Auto-download (optional)

If you supply a URL to a Zint zip, the setup script can download + expand it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -ZintUrl "<ZIP_URL>"
```

(You supply the URL because download URLs can change.)
