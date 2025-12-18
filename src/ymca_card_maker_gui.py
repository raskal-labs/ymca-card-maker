#!/usr/bin/env python3
"""
YMCA Card Maker GUI (wizard)

Front-end for: ymca_card_maker_v1_2.py

Flow:
Step 1:
- Enter raw code
- Select report (dropdown)

Step 2:
- Shows only the options that apply to the selected report:
  - checksum (disabled for ymca_letter_6up_mixed)
  - text (barcode-only reports only)
  - PNG sizing (barcode_png only)
  - holes (YMCA PDF reports only)
  - plus prefix, timestamp, out-dir, gen-dir

It runs the CLI script and shows output, plus buttons to open output file/folder.

Place this file next to ymca_card_maker_v1_2.py and run:
  python .\ymca_card_maker_gui.py
"""

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

def _app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def _res_dir() -> Path:
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(getattr(sys, '_MEIPASS')).resolve()
    return _app_dir()

APP_DIR = _app_dir()
RES_DIR = _res_dir()

# CLI lives in src/ inside the bundle (onefile) or repo (dev)
_cli_candidate = RES_DIR / "src" / "ymca_card_maker.py"
if not _cli_candidate.exists():
    _cli_candidate = APP_DIR / "src" / "ymca_card_maker.py"
CLI_SCRIPT_DEFAULT = str(_cli_candidate)

REPORTS = [
    ("barcode_svg", "Barcode SVG"),
    ("barcode_png", "Barcode PNG"),
    ("ymca_letter_1up", "YMCA Letter 1-up (top-left slot)"),
    ("ymca_cr80_1up", "YMCA CR80 1-up"),
    ("ymca_letter_6up", "YMCA Letter 6-up"),
    ("ymca_letter_6up_mixed", "YMCA Letter 6-up mixed (left plain, right checksum)"),
]

def _load_default_profile() -> dict:
    """Load repo/bundle defaults from profiles/default.json (fallback to profiles/ymca.json)."""
    candidates = [
        RES_DIR / "profiles" / "default.json",
        APP_DIR / "profiles" / "default.json",
        RES_DIR / "profiles" / "ymca.json",
        APP_DIR / "profiles" / "ymca.json",
    ]
    for p in candidates:
        try:
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            # keep trying other candidates
            pass
    return {}

def _profile_default(profile: dict, key: str, fallback: str) -> str:
    v = profile.get(key, fallback)
    return str(v) if v is not None else fallback

def _profile_path_default(profile: dict, key: str, fallback: str) -> str:
    paths = profile.get("paths", {}) if isinstance(profile.get("paths", {}), dict) else {}
    v = paths.get(key, fallback)
    return str(v) if v is not None else fallback


YMCA_PDF_REPORTS = {"ymca_letter_1up", "ymca_cr80_1up", "ymca_letter_6up", "ymca_letter_6up_mixed"}
BARCODE_ONLY_REPORTS = {"barcode_svg", "barcode_png"}


def open_path(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except Exception:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YMCA Card Maker")

        # Load defaults from profiles/default.json (fallback to profiles/ymca.json)
        self.profile = _load_default_profile()
        self.resizable(False, False)

        self.cli_path = tk.StringVar(value=CLI_SCRIPT_DEFAULT)

        self.raw_code = tk.StringVar(value=_profile_default(self.profile, "default_data", "YXXXX0123456"))
        self.report = tk.StringVar(value=REPORTS[0][0])

        self.opt_checksum = tk.BooleanVar(value=False)
        self.opt_text = tk.BooleanVar(value=False)
        self.opt_plus = tk.BooleanVar(value=False)
        self.opt_timestamp = tk.BooleanVar(value=True)

        self.opt_no_holes = tk.BooleanVar(value=False)

        self.out_dir = tk.StringVar(value=_profile_default(self.profile, "out_dir", "out"))
        self.gen_dir = tk.StringVar(value=_profile_default(self.profile, "gen_dir", ".gen_barcodes"))

        self.png_scale = tk.StringVar(value="5.0")
        self.png_scalexdimdp = tk.StringVar(value="")

        self.last_output_path = None

        self._build_ui()

    def _build_ui(self):
        outer = ttk.Frame(self, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")

        ttk.Label(outer, text="YMCA Card Maker (GUI)").grid(row=0, column=0, sticky="w")

        self.container = ttk.Frame(outer)
        self.container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        self.page1 = ttk.Frame(self.container)
        self.page2 = ttk.Frame(self.container)

        for p in (self.page1, self.page2):
            p.grid(row=0, column=0, sticky="nsew")

        self._build_page1()
        self._build_page2()

        self.show_page(1)

    def show_page(self, n: int):
        if n == 1:
            self.page1.tkraise()
        else:
            self.page2.tkraise()
            self._refresh_page2_visibility()

    def _build_page1(self):
        f = self.page1

        ttk.Label(f, text="Step 1: Enter code + choose report").grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(f, text="Raw code:").grid(row=1, column=0, sticky="w", pady=(10, 2))
        entry = ttk.Entry(f, textvariable=self.raw_code, width=34)
        entry.grid(row=2, column=0, columnspan=3, sticky="we")
        entry.focus_set()

        ttk.Label(f, text="Report:").grid(row=3, column=0, sticky="w", pady=(10, 2))
        report_box = ttk.Combobox(
            f,
            textvariable=self.report,
            values=[r[0] for r in REPORTS],
            state="readonly",
            width=32,
        )
        report_box.grid(row=4, column=0, columnspan=3, sticky="we")

        ttk.Label(f, text="CLI script (must be in this folder):").grid(row=5, column=0, sticky="w", pady=(10, 2))
        ttk.Entry(f, textvariable=self.cli_path, width=34).grid(row=6, column=0, columnspan=3, sticky="we")

        btns = ttk.Frame(f)
        btns.grid(row=7, column=0, columnspan=3, sticky="we", pady=(12, 0))
        ttk.Button(btns, text="Next", command=self._on_next).grid(row=0, column=2, sticky="e")

    def _build_page2(self):
        f = self.page2

        ttk.Label(f, text="Step 2: Options (changes based on report)").grid(row=0, column=0, columnspan=3, sticky="w")

        self.summary = ttk.Label(f, text="")
        self.summary.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 8))

        self.chk_plus = ttk.Checkbutton(f, text="Prefix with '+' (encode +DATA)", variable=self.opt_plus)
        self.chk_plus.grid(row=2, column=0, columnspan=3, sticky="w")

        self.chk_timestamp = ttk.Checkbutton(f, text="Timestamped output (avoid overwrite/file lock)", variable=self.opt_timestamp)
        self.chk_timestamp.grid(row=3, column=0, columnspan=3, sticky="w")

        self.chk_checksum = ttk.Checkbutton(f, text="Checksum (Mod43 appended)", variable=self.opt_checksum)
        self.chk_checksum.grid(row=4, column=0, columnspan=3, sticky="w")

        self.chk_text = ttk.Checkbutton(f, text="Include text in barcode image (Zint text)", variable=self.opt_text)
        self.chk_text.grid(row=5, column=0, columnspan=3, sticky="w")

        self.chk_no_holes = ttk.Checkbutton(f, text="Disable holes (YMCA PDFs)", variable=self.opt_no_holes)
        self.chk_no_holes.grid(row=6, column=0, columnspan=3, sticky="w")

        ttk.Label(f, text="Output folder:").grid(row=7, column=0, sticky="w", pady=(10, 2))
        ttk.Entry(f, textvariable=self.out_dir, width=18).grid(row=8, column=0, sticky="w")

        ttk.Label(f, text="Barcode cache folder:").grid(row=7, column=1, sticky="w", pady=(10, 2), padx=(12, 0))
        ttk.Entry(f, textvariable=self.gen_dir, width=18).grid(row=8, column=1, sticky="w", padx=(12, 0))

        self.png_frame = ttk.LabelFrame(f, text="PNG options (barcode_png only)")
        self.png_frame.grid(row=9, column=0, columnspan=3, sticky="we", pady=(10, 0))

        ttk.Label(self.png_frame, text="--png-scale:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(self.png_frame, textvariable=self.png_scale, width=8).grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(self.png_frame, text="--png-scalexdimdp (optional):").grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
        ttk.Entry(self.png_frame, textvariable=self.png_scalexdimdp, width=30).grid(row=1, column=1, sticky="w", pady=(0, 8))

        self.run_btn = ttk.Button(f, text="Generate", command=self._on_generate)
        self.run_btn.grid(row=10, column=0, sticky="w", pady=(12, 0))

        self.back_btn = ttk.Button(f, text="Back", command=lambda: self.show_page(1))
        self.back_btn.grid(row=10, column=1, sticky="w", pady=(12, 0), padx=(12, 0))

        self.open_file_btn = ttk.Button(f, text="Open output file", command=self._open_last_file, state="disabled")
        self.open_file_btn.grid(row=11, column=0, sticky="w", pady=(8, 0))

        self.open_folder_btn = ttk.Button(f, text="Open output folder", command=self._open_out_dir)
        self.open_folder_btn.grid(row=11, column=1, sticky="w", pady=(8, 0), padx=(12, 0))

        self.output_text = tk.Text(f, width=64, height=10, wrap="word")
        self.output_text.grid(row=12, column=0, columnspan=3, sticky="we", pady=(10, 0))
        self.output_text.configure(state="disabled")

    def _on_next(self):
        raw = self.raw_code.get().strip()
        if not raw:
            messagebox.showerror("Missing code", "Enter the raw code first.")
            return

        cli = Path(self.cli_path.get().strip())
        if not cli.exists():
            messagebox.showerror("Missing CLI script", f"Cannot find {cli}. Put the GUI next to your CLI script, or set the correct name.")
            return

        self.show_page(2)

    def _refresh_page2_visibility(self):
        r = self.report.get()
        raw = self.raw_code.get().strip()
        label = dict(REPORTS).get(r, r)
        self.summary.configure(text=f"Raw code: {raw}   |   Report: {r} ({label})")

        is_barcode = r in BARCODE_ONLY_REPORTS
        is_png = (r == "barcode_png")
        is_mixed = (r == "ymca_letter_6up_mixed")
        is_ymca_pdf = r in YMCA_PDF_REPORTS

        # Mixed report ignores checksum flag
        self.chk_checksum.configure(state=("disabled" if is_mixed else "normal"))
        if is_mixed:
            self.opt_checksum.set(False)

        # Text only for barcode-only reports
        self.chk_text.configure(state=("normal" if is_barcode else "disabled"))
        if not is_barcode:
            self.opt_text.set(False)

        # Holes only for YMCA PDFs
        self.chk_no_holes.configure(state=("normal" if is_ymca_pdf else "disabled"))
        if not is_ymca_pdf:
            self.opt_no_holes.set(False)

        # PNG frame only for barcode_png
        if is_png:
            for child in self.png_frame.winfo_children():
                child.configure(state="normal")
        else:
            for child in self.png_frame.winfo_children():
                child.configure(state="disabled")

    def _append_output(self, s: str):
        self.output_text.configure(state="normal")
        self.output_text.insert("end", s)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def _build_command(self):
        python = sys.executable
        cli = self.cli_path.get().strip()
        raw = self.raw_code.get().strip()
        report = self.report.get().strip()

        cmd = [python, cli, "-d", raw, "-r", report]

        if self.opt_plus.get():
            cmd.append("--plus")
        if self.opt_timestamp.get():
            cmd.append("--timestamp")

        out_dir = self.out_dir.get().strip() or "out"
        gen_dir = self.gen_dir.get().strip() or ".gen_barcodes"
        cmd += ["--out-dir", out_dir, "--gen-dir", gen_dir]

        if report != "ymca_letter_6up_mixed" and self.opt_checksum.get():
            cmd.append("--checksum")

        if report in BARCODE_ONLY_REPORTS and self.opt_text.get():
            cmd.append("--text")

        if report in YMCA_PDF_REPORTS and self.opt_no_holes.get():
            cmd.append("--no-holes")

        if report == "barcode_png":
            scale = self.png_scale.get().strip()
            if scale:
                cmd += ["--png-scale", scale]
            xdimdp = self.png_scalexdimdp.get().strip()
            if xdimdp:
                cmd += ["--png-scalexdimdp", xdimdp]

        return cmd

    def _on_generate(self):
        self._refresh_page2_visibility()

        cmd = self._build_command()

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")
        self._append_output("Running:\n" + " ".join(cmd) + "\n\n")

        self.last_output_path = None
        self.open_file_btn.configure(state="disabled")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            messagebox.showerror("Run failed", str(e))
            return

        out = (proc.stdout or "") + (proc.stderr or "")
        self._append_output(out if out else "(no output)\n")

        if proc.returncode != 0:
            messagebox.showerror("Error", "The CLI returned an error. See output box for details.")
            return

        # Try to find "Created: <path>"
        created_path = None
        for line in out.splitlines():
            if line.strip().startswith("Created:"):
                maybe = line.split("Created:", 1)[1].strip()
                if maybe:
                    created_path = maybe

        if created_path:
            p = Path(created_path)
            self.last_output_path = p
            self.open_file_btn.configure(state="normal")

    def _open_last_file(self):
        if self.last_output_path:
            open_path(self.last_output_path)

    def _open_out_dir(self):
        p = Path(self.out_dir.get().strip() or "out")
        p.mkdir(parents=True, exist_ok=True)
        open_path(p)


if __name__ == "__main__":
    app = App()
    app.mainloop()
