# Changelog

## v1.5 — 2025-12-18

### Added
- Header fields as runtime variables (URL + title) in CLI + GUI
- Optional association presets (`profiles/associations.json`) for quick picking common YMCA-style headers
- Dependency helper / sanity-check tooling for local setup

### Changed
- Repository defaults are generic and safe:
  - Barcode: `YXXXX0123456`
  - URL: `ymca.org`
  - Title: `YMCA`
- Personal defaults (real codes, local URLs, local paths) should live only in `.user_config.json` (gitignored)
- Locked geometry, spacing, and typography preserved (print-validated)

### Fixed
- More robust JSON config loading (handles UTF-8 BOM safely)
- More consistent Zint invocation and error surfacing
- Mixed 6-up layout explicitly split by column (left = plain, right = checksum)

---

## v1.4 — 2025-12-18

- Path configurability for Zint, fonts, output, and cache
- Standardized report naming
- CLI/GUI parity improvements

---

## v0.9 — 2025-12-17

- Initial locked geometry based on physical card validation
- YMCA card layouts established
- Code 39 + Mod43 support finalized
