#!/usr/bin/env python3
"""Command-line front-end for YMCA Card Maker with Debian/Proxmox defaults.

This wrapper keeps the rendering logic in ``ymca_card_maker`` but adds:
- Config discovery under /etc and ~/.config
- Profile-driven, non-interactive rendering
- Environment detection for Proxmox LXC quirks
- Simple stdout/stderr logging (no GUI)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable

from ymca_card_maker import (
    APP_DIR,
    DEFAULT_DATA,
    DEFAULT_HEADER_TITLE,
    DEFAULT_HEADER_URL,
    Paths,
    detect_ocrb_font,
    detect_zint_exe,
    report_barcode_png,
    report_barcode_svg,
    report_ymca_cr80_1up,
    report_ymca_letter_1up,
    report_ymca_letter_6up,
    report_ymca_letter_6up_mixed,
)

_yaml_spec = importlib.util.find_spec("yaml")
yaml = importlib.util.module_from_spec(_yaml_spec) if _yaml_spec else None
if yaml and _yaml_spec and _yaml_spec.loader:
    _yaml_spec.loader.exec_module(yaml)

DEFAULT_PROFILE = APP_DIR / "profiles" / "default.json"
USER_CONFIG = Path(os.environ.get("YMCA_CARD_CONFIG", "")) if os.environ.get("YMCA_CARD_CONFIG") else None
SYSTEM_CONFIG = Path("/etc/ymca-card-maker/config.yml")
HOME_CONFIG = Path.home() / ".config" / "ymca-card-maker" / "config.yml"
CONFIG_PROBE_ORDER = [SYSTEM_CONFIG, HOME_CONFIG]


class EnvironmentReport(SimpleNamespace):
    @property
    def messages(self) -> Iterable[str]:
        systemd = "systemd" if self.has_systemd else "no systemd"
        sys_ro = "read-only /sys" if self.sys_readonly else "writable /sys"
        yield f"container={self.container_type or 'none'}; {systemd}; {sys_ro}; user={self.user}"
        if self.container_type:
            yield "Detected containerized host (Proxmox/LXC-style cgroups). Expect limited namespaces."
        if not self.has_systemd:
            yield "systemd is absent; prefer cron or direct invocation instead of systemd services."
        if self.sys_readonly:
            yield "/sys appears read-only; avoid tooling that attempts hardware toggles."
        if self.unprivileged:
            yield "Running unprivileged; ensure output paths and Zint/font locations are user-writable."


def detect_environment() -> EnvironmentReport:
    cg_text = Path("/proc/1/cgroup").read_text(errors="ignore") if Path("/proc/1/cgroup").exists() else ""
    container = "lxc" if "lxc" in cg_text.lower() or "pve" in cg_text.lower() else ""
    has_systemd = Path("/run/systemd/system").exists()
    sys_readonly = Path("/sys").exists() and not os.access("/sys", os.W_OK)
    unprivileged = os.geteuid() != 0
    return EnvironmentReport(container_type=container, has_systemd=has_systemd, sys_readonly=sys_readonly, unprivileged=unprivileged, user=os.environ.get("USER", "unknown"))


def load_structured_file(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8")
    suffix = p.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        if not yaml:
            raise RuntimeError("PyYAML is required to read YAML profiles/config files")
        loaded = yaml.safe_load(text) or {}
        return dict(loaded)
    return json.loads(text)


def coerce_bool(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return bool(v)


def pick_value(*candidates: Any, fallback: Any = None) -> Any:
    for cand in candidates:
        if cand is None:
            continue
        if isinstance(cand, str) and cand.strip() == "":
            continue
        return cand
    return fallback


def build_paths(args: argparse.Namespace, config_paths: Dict[str, Any], profile_paths: Dict[str, Any]) -> Paths:
    def resolve_path(raw: Any) -> Path | None:
        if raw is None or (isinstance(raw, str) and raw.strip() == ""):
            return None
        pth = Path(str(raw))
        if not pth.is_absolute():
            pth = (APP_DIR / pth).resolve()
        return pth

    zint = resolve_path(pick_value(args.zint_exe, config_paths.get("zint_exe"), profile_paths.get("zint_exe")))
    ocrb = resolve_path(pick_value(args.ocrb_ttf, config_paths.get("ocrb_ttf"), profile_paths.get("ocrb_ttf")))

    zint = zint if zint and zint.exists() else detect_zint_exe(APP_DIR)
    if not zint or not zint.exists():
        raise FileNotFoundError("Cannot find zint executable; set --zint-exe or configure it under paths.zint_exe")

    ocrb = ocrb if ocrb and ocrb.exists() else detect_ocrb_font(APP_DIR)
    if not ocrb or not ocrb.exists():
        raise FileNotFoundError("Cannot find OCR-B font; set --ocrb-ttf or place it under assets/fonts")

    out_dir = resolve_path(pick_value(args.out_dir, config_paths.get("out_dir"), profile_paths.get("out_dir"), fallback="output"))
    gen_dir = resolve_path(pick_value(args.gen_dir, config_paths.get("gen_dir"), profile_paths.get("gen_dir"), fallback=".gen_barcodes"))

    return Paths(zint_exe=zint, ocrb_ttf=ocrb, out_dir=out_dir, gen_dir=gen_dir)


def select_config_file(cli_path: str | None) -> Path | None:
    if cli_path:
        p = Path(cli_path).expanduser().resolve()
        return p if p.exists() else None
    if USER_CONFIG and USER_CONFIG.exists():
        return USER_CONFIG
    for candidate in CONFIG_PROBE_ORDER:
        if candidate.exists():
            return candidate
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="YMCA Card Maker CLI wrapper")
    p.add_argument("--config", help="Path to YAML/JSON config (defaults: /etc/ymca-card-maker/config.yml then ~/.config/ymca-card-maker/config.yml)")
    p.add_argument("--profile", default=str(DEFAULT_PROFILE), help="Profile JSON/YAML containing defaults")
    p.add_argument("--report", help="Report to render (overrides profile)")
    p.add_argument("--data", help="Barcode data (overrides profile/defaults)")
    p.add_argument("--checksum", action="store_true", help="Append Mod43 check digit")
    p.add_argument("--plus", action="store_true", help="Prefix data with '+'")
    p.add_argument("--text", action="store_true", help="Include human-readable text for barcode-only reports")
    p.add_argument("--timestamp", action="store_true", help="Timestamp output filenames")
    p.add_argument("--no-holes", dest="no_holes", action="store_true", help="Disable punch holes on YMCA cards")
    p.add_argument("--header-url", dest="header_url", help="Header URL override")
    p.add_argument("--header-title", dest="header_title", help="Header title override")
    p.add_argument("--default-data", dest="default_data", help="Default barcode data when --data is omitted")
    p.add_argument("--zint-exe", dest="zint_exe", help="Path to zint executable")
    p.add_argument("--ocrb-ttf", dest="ocrb_ttf", help="Path to OCR-B font")
    p.add_argument("--out", dest="out_dir", help="Output directory")
    p.add_argument("--gen-dir", dest="gen_dir", help="Barcode cache directory")
    p.add_argument("--dry-run", action="store_true", help="Print merged config and exit")
    return p.parse_args(argv)


def run_report(paths: Paths, report: str, raw: str, *, checksum: bool, plus: bool, include_text: bool, holes: bool, timestamp: bool, header_url: str, header_title: str) -> None:
    if report == "barcode_svg":
        report_barcode_svg(paths, raw, checksum=checksum, plus=plus, include_text=include_text, timestamp=timestamp)
    elif report == "barcode_png":
        report_barcode_png(paths, raw, checksum=checksum, plus=plus, include_text=include_text, png_scale=5.0, scalexdimdp="", timestamp=timestamp)
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    env_report = detect_environment()
    for msg in env_report.messages:
        print(f"[env] {msg}", file=sys.stderr)

    config_file = select_config_file(args.config)
    config = load_structured_file(config_file) if config_file else {}
    profile = load_structured_file(Path(args.profile)) if args.profile else {}

    profile_paths = profile.get("paths", {}) if isinstance(profile, dict) else {}
    config_paths = config.get("paths", {}) if isinstance(config, dict) else {}

    header_url = pick_value(args.header_url, config.get("header_url") if isinstance(config, dict) else None, profile.get("header_url") if isinstance(profile, dict) else None, fallback=DEFAULT_HEADER_URL)
    header_title = pick_value(args.header_title, config.get("header_title") if isinstance(config, dict) else None, profile.get("header_title") if isinstance(profile, dict) else None, fallback=DEFAULT_HEADER_TITLE)
    default_data = pick_value(args.default_data, config.get("default_data") if isinstance(config, dict) else None, profile.get("default_data") if isinstance(profile, dict) else None, fallback=DEFAULT_DATA)

    report = pick_value(args.report, config.get("report") if isinstance(config, dict) else None, profile.get("report") if isinstance(profile, dict) else None, fallback="ymca_letter_6up")
    raw = pick_value(args.data, config.get("data") if isinstance(config, dict) else None, profile.get("data") if isinstance(profile, dict) else None, fallback=default_data)

    checksum = args.checksum or coerce_bool(config.get("checksum") if isinstance(config, dict) else None, default=coerce_bool(profile.get("checksum") if isinstance(profile, dict) else None, default=False))
    plus = args.plus or coerce_bool(config.get("plus") if isinstance(config, dict) else None, default=coerce_bool(profile.get("plus") if isinstance(profile, dict) else None, default=False))
    include_text = args.text or coerce_bool(config.get("text") if isinstance(config, dict) else None, default=coerce_bool(profile.get("text") if isinstance(profile, dict) else None, default=False))
    holes = not args.no_holes if args.no_holes else not coerce_bool(config.get("no_holes") if isinstance(config, dict) else None, default=coerce_bool(profile.get("no_holes") if isinstance(profile, dict) else None, default=False))
    timestamp = args.timestamp or coerce_bool(config.get("timestamp") if isinstance(config, dict) else None, default=coerce_bool(profile.get("timestamp") if isinstance(profile, dict) else None, default=False))

    paths = build_paths(args, config_paths if isinstance(config_paths, dict) else {}, profile_paths if isinstance(profile_paths, dict) else {})

    merged_view = {
        "report": report,
        "data": raw,
        "checksum": checksum,
        "plus": plus,
        "text": include_text,
        "holes": holes,
        "timestamp": timestamp,
        "header_url": header_url,
        "header_title": header_title,
        "paths": {
            "zint_exe": str(paths.zint_exe),
            "ocrb_ttf": str(paths.ocrb_ttf),
            "out_dir": str(paths.out_dir),
            "gen_dir": str(paths.gen_dir),
        },
    }

    if args.dry_run:
        print(json.dumps(merged_view, indent=2))
        return 0

    run_report(paths, report, raw, checksum=checksum, plus=plus, include_text=include_text, holes=holes, timestamp=timestamp, header_url=header_url, header_title=header_title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
