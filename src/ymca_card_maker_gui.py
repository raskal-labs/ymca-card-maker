#!/usr/bin/env python3
"""
YMCA Card Maker GUI v1.5 (tkinter)

Adds:
- Association dropdown (loaded from profiles/associations.json)
- Editable Header URL + Header Title fields
- Defaults support:
  - "General" repo defaults: ymca.org / YMCA / YXXXX0123456
  - Your local defaults can live in .user_config.json (gitignored)

The GUI writes .user_config.json (UTF-8 no BOM) so the CLI can pick it up.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

APP_VERSION = "1.5"

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = REPO_ROOT / "src" / "ymca_card_maker.py"
USER_CFG = REPO_ROOT / ".user_config.json"
PROFILE_DB = REPO_ROOT / "profiles" / "associations.json"

GENERAL_DEFAULTS = {
    "header_url": "ymca.org",
    "header_title": "YMCA",
    "default_data": "YXXXX0123456",
}

REPORTS = [
    ("barcode_svg", "Barcode SVG (single)"),
    ("barcode_png", "Barcode PNG (single)"),
    ("ymca_letter_1up", "YMCA Letter 1-up (A1 top-left)"),
    ("ymca_cr80_1up", "YMCA CR80 1-up (card-sized page)"),
    ("ymca_letter_6up", "YMCA Letter 6-up"),
    ("ymca_letter_6up_mixed", "YMCA Letter 6-up Mixed (col A plain, col B checksum)"),
]


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json_no_bom(path: Path, obj: dict) -> None:
    # Ensure no BOM: use utf-8 and write_text (Python doesn't add BOM)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def load_associations() -> list[dict]:
    try:
        db = read_json(PROFILE_DB)
        items = db.get("associations", [])
        if isinstance(items, list):
            return items
    except Exception:
        pass
    return []


@dataclass
class PathsCfg:
    zint_exe: str = ""
    ocrb_ttf: str = ""
    out_dir: str = ""
    gen_dir: str = ""


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"YMCA Card Maker {APP_VERSION}")
        self.resizable(False, False)

        self.associations = load_associations()

        self.user_cfg = read_json(USER_CFG)
        self.paths = PathsCfg(
            zint_exe=self.user_cfg.get("zint_exe", ""),
            ocrb_ttf=self.user_cfg.get("ocrb_ttf", ""),
            out_dir=self.user_cfg.get("out_dir", ""),
            gen_dir=self.user_cfg.get("gen_dir", ""),
        )

        self.var_data = tk.StringVar(value=self.user_cfg.get("default_data", GENERAL_DEFAULTS["default_data"]))
        self.var_report = tk.StringVar(value=REPORTS[0][0])

        self.var_checksum = tk.BooleanVar(value=False)
        self.var_text = tk.BooleanVar(value=False)
        self.var_plus = tk.BooleanVar(value=False)
        self.var_timestamp = tk.BooleanVar(value=True)
        self.var_no_holes = tk.BooleanVar(value=False)

        self.var_header_url = tk.StringVar(value=self.user_cfg.get("header_url", GENERAL_DEFAULTS["header_url"]))
        self.var_header_title = tk.StringVar(value=self.user_cfg.get("header_title", GENERAL_DEFAULTS["header_title"]))

        self.var_png_scale = tk.StringVar(value=str(self.user_cfg.get("png_scale", "5.0")))
        self.var_png_scalexdimdp = tk.StringVar(value=str(self.user_cfg.get("png_scalexdimdp", "")))

        self._build_ui()
        self._apply_report_rules()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # Association picker
        frm_assoc = ttk.LabelFrame(self, text="Association (optional)")
        frm_assoc.grid(row=0, column=0, sticky="ew", **pad)

        assoc_names = ["(Custom / manual)"] + [a["name"] for a in self.associations]
        self.var_assoc = tk.StringVar(value=assoc_names[0])
        cmb = ttk.Combobox(frm_assoc, textvariable=self.var_assoc, values=assoc_names, state="readonly", width=52)
        cmb.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._on_assoc_selected())

        btn_reset = ttk.Button(frm_assoc, text="Reset to general defaults", command=self._reset_to_general_defaults)
        btn_reset.grid(row=0, column=1, padx=8, pady=6, sticky="e")

        # Header fields
        frm_header = ttk.LabelFrame(self, text="Header")
        frm_header.grid(row=1, column=0, sticky="ew", **pad)

        ttk.Label(frm_header, text="URL").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frm_header, textvariable=self.var_header_url, width=40).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(frm_header, text="Title").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frm_header, textvariable=self.var_header_title, width=40).grid(row=1, column=1, sticky="w", padx=8, pady=4)

        # Data + report
        frm_main = ttk.LabelFrame(self, text="Report")
        frm_main.grid(row=2, column=0, sticky="ew", **pad)

        ttk.Label(frm_main, text="Barcode data").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frm_main, textvariable=self.var_data, width=40).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(frm_main, text="Report type").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        cmb_report = ttk.Combobox(frm_main, textvariable=self.var_report, values=[r[0] for r in REPORTS], state="readonly", width=38)
        cmb_report.grid(row=1, column=1, sticky="w", padx=8, pady=4)
        cmb_report.bind("<<ComboboxSelected>>", lambda _e: self._apply_report_rules())

        # Options
        frm_opt = ttk.LabelFrame(self, text="Options")
        frm_opt.grid(row=3, column=0, sticky="ew", **pad)

        self.chk_checksum = ttk.Checkbutton(frm_opt, text="Checksum (Mod43)", variable=self.var_checksum)
        self.chk_checksum.grid(row=0, column=0, sticky="w", padx=8, pady=2)

        self.chk_text = ttk.Checkbutton(frm_opt, text="Include barcode text (barcode-only)", variable=self.var_text)
        self.chk_text.grid(row=0, column=1, sticky="w", padx=8, pady=2)

        ttk.Checkbutton(frm_opt, text="Prefix '+'", variable=self.var_plus).grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(frm_opt, text="Timestamp outputs", variable=self.var_timestamp).grid(row=1, column=1, sticky="w", padx=8, pady=2)
        ttk.Checkbutton(frm_opt, text="No holes (YMCA cards)", variable=self.var_no_holes).grid(row=2, column=0, sticky="w", padx=8, pady=2)

        # PNG extras
        frm_png = ttk.LabelFrame(self, text="PNG options (barcode_png)")
        frm_png.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(frm_png, text="scale").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(frm_png, textvariable=self.var_png_scale, width=10).grid(row=0, column=1, sticky="w", padx=8, pady=4)
        ttk.Label(frm_png, text="scalexdimdp").grid(row=0, column=2, sticky="w", padx=8, pady=4)
        ttk.Entry(frm_png, textvariable=self.var_png_scalexdimdp, width=18).grid(row=0, column=3, sticky="w", padx=8, pady=4)

        # Paths
        frm_paths = ttk.LabelFrame(self, text="Paths (optional overrides)")
        frm_paths.grid(row=5, column=0, sticky="ew", **pad)

        self._path_row(frm_paths, 0, "zint.exe", "zint_exe")
        self._path_row(frm_paths, 1, "OCR-B.ttf", "ocrb_ttf")
        self._path_row(frm_paths, 2, "Output dir", "out_dir", is_dir=True)
        self._path_row(frm_paths, 3, "Barcode cache dir", "gen_dir", is_dir=True)

        # Buttons
        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=6, column=0, sticky="ew", padx=10, pady=10)

        ttk.Button(frm_btn, text="Save config", command=self._save_config).grid(row=0, column=0, padx=6)
        ttk.Button(frm_btn, text="Run", command=self._run).grid(row=0, column=1, padx=6)
        ttk.Button(frm_btn, text="Open output folder", command=self._open_output).grid(row=0, column=2, padx=6)

    def _path_row(self, parent, row: int, label: str, key: str, is_dir: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=8, pady=4)
        var = tk.StringVar(value=getattr(self.paths, key))
        setattr(self, f"var_{key}", var)
        ttk.Entry(parent, textvariable=var, width=46).grid(row=row, column=1, sticky="w", padx=8, pady=4)

        def browse():
            if is_dir:
                p = filedialog.askdirectory()
            else:
                p = filedialog.askopenfilename()
            if p:
                var.set(p)

        ttk.Button(parent, text="Browse", command=browse).grid(row=row, column=2, padx=6, pady=4)

    def _reset_to_general_defaults(self) -> None:
        self.var_header_url.set(GENERAL_DEFAULTS["header_url"])
        self.var_header_title.set(GENERAL_DEFAULTS["header_title"])
        self.var_data.set(GENERAL_DEFAULTS["default_data"])
        self.var_assoc.set("(Custom / manual)")

    def _on_assoc_selected(self) -> None:
        name = self.var_assoc.get()
        if name == "(Custom / manual)":
            return
        for a in self.associations:
            if a["name"] == name:
                self.var_header_url.set(a.get("url", GENERAL_DEFAULTS["header_url"]))
                self.var_header_title.set(a.get("title", GENERAL_DEFAULTS["header_title"]))
                break

    def _apply_report_rules(self) -> None:
        rpt = self.var_report.get()

        # checksum checkbox is irrelevant for mixed
        if rpt == "ymca_letter_6up_mixed":
            self.chk_checksum.state(["disabled"])
        else:
            self.chk_checksum.state(["!disabled"])

        # include_text only applies to barcode_* outputs
        if rpt in ("barcode_svg", "barcode_png"):
            self.chk_text.state(["!disabled"])
        else:
            self.chk_text.state(["disabled"])

    def _save_config(self) -> None:
        cfg = read_json(USER_CFG)

        # paths
        cfg["zint_exe"] = self.var_zint_exe.get().strip()
        cfg["ocrb_ttf"] = self.var_ocrb_ttf.get().strip()
        cfg["out_dir"] = self.var_out_dir.get().strip()
        cfg["gen_dir"] = self.var_gen_dir.get().strip()

        # defaults
        cfg["header_url"] = self.var_header_url.get().strip()
        cfg["header_title"] = self.var_header_title.get().strip()
        cfg["default_data"] = self.var_data.get().strip()

        # png defaults
        cfg["png_scale"] = self.var_png_scale.get().strip()
        cfg["png_scalexdimdp"] = self.var_png_scalexdimdp.get().strip()

        write_json_no_bom(USER_CFG, cfg)
        messagebox.showinfo("Saved", f"Saved {USER_CFG.name}")

    def _run(self) -> None:
        rpt = self.var_report.get().strip()
        data = self.var_data.get().strip()
        if not rpt:
            messagebox.showerror("Missing report", "Choose a report.")
            return

        cmd = [sys.executable, str(CLI_PATH), "-r", rpt]
        if data:
            cmd += ["-d", data]

        # header fields
        if self.var_header_url.get().strip():
            cmd += ["--header-url", self.var_header_url.get().strip()]
        if self.var_header_title.get().strip():
            cmd += ["--header-title", self.var_header_title.get().strip()]

        # options
        if self.var_checksum.get() and rpt != "ymca_letter_6up_mixed":
            cmd += ["--checksum"]
        if self.var_text.get() and rpt in ("barcode_svg", "barcode_png"):
            cmd += ["--text"]
        if self.var_plus.get():
            cmd += ["--plus"]
        if self.var_timestamp.get():
            cmd += ["--timestamp"]
        if self.var_no_holes.get():
            cmd += ["--no-holes"]

        # png options
        if rpt == "barcode_png":
            cmd += ["--png-scale", self.var_png_scale.get().strip()]
            if self.var_png_scalexdimdp.get().strip():
                cmd += ["--png-scalexdimdp", self.var_png_scalexdimdp.get().strip()]

        # paths
        if self.var_zint_exe.get().strip():
            cmd += ["--zint-exe", self.var_zint_exe.get().strip()]
        if self.var_ocrb_ttf.get().strip():
            cmd += ["--ocrb-ttf", self.var_ocrb_ttf.get().strip()]
        if self.var_out_dir.get().strip():
            cmd += ["--out-dir", self.var_out_dir.get().strip()]
        if self.var_gen_dir.get().strip():
            cmd += ["--gen-dir", self.var_gen_dir.get().strip()]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            messagebox.showerror("Run failed", str(e))
            return

        if proc.returncode != 0:
            messagebox.showerror("Error", (proc.stdout + "\n" + proc.stderr).strip())
            return

        out = (proc.stdout or "").strip()
        messagebox.showinfo("Done", out if out else "Done")

    def _open_output(self) -> None:
        # Use configured out_dir if set, else default ./out
        out_dir = self.var_out_dir.get().strip() or "out"
        p = (REPO_ROOT / out_dir).resolve() if not Path(out_dir).is_absolute() else Path(out_dir)
        p.mkdir(parents=True, exist_ok=True)

        if sys.platform.startswith("win"):
            subprocess.run(["explorer", str(p)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)])
        else:
            subprocess.run(["xdg-open", str(p)])


def main() -> int:
    if not CLI_PATH.exists():
        print(f"Missing CLI at {CLI_PATH}")
        return 2
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
