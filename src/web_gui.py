#!/usr/bin/env python3
"""Local web frontend for the existing card-maker CLI."""
from __future__ import annotations

import argparse
import hmac
import html
import json
import re
import secrets
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "src" / "ymca_card_maker.py"
PAGE = ROOT / "web" / "index.html"
ASSOCIATIONS = ROOT / "profiles" / "associations.json"
REPORTS = {
    "ymca_letter_6up": ("Letter · 6 cards", "pdf"),
    "ymca_letter_1up": ("Letter · 1 card", "pdf"),
    "ymca_cr80_1up": ("CR80 · 1 card", "pdf"),
    "ymca_letter_6up_mixed": ("Letter · mixed checksum", "pdf"),
    "avery5164_6up": ("Avery 5164 / 8164 · 6 cards", "pdf"),
    "barcode_png": ("Barcode · PNG", "png"),
    "barcode_svg": ("Barcode · SVG", "svg"),
}
MIME = {"pdf": "application/pdf", "png": "image/png", "svg": "image/svg+xml"}
MAX_BODY = 4096
MAX_OUTPUT = 8 * 1024 * 1024


def validated_command(payload: dict, directory: Path) -> tuple[list[str], str]:
    """Accept only supported reports and bounded, explicit inputs."""
    if not isinstance(payload, dict):
        raise ValueError("Expected an object.")
    allowed = {"report", "data", "header_url", "header_title", "checksum",
               "text", "no_holes", "plus"}
    if set(payload) - allowed:
        raise ValueError("Unsupported setting.")
    report = payload.get("report")
    if not isinstance(report, str) or report not in REPORTS:
        raise ValueError("Select a supported layout.")
    data = payload.get("data")
    if not isinstance(data, str):
        raise ValueError("Enter your existing membership code.")
    data = data.strip().upper()
    if not re.fullmatch(r"[0-9A-Z. $/+%\-]{1,64}", data):
        raise ValueError("Use 1–64 Code 39 characters; no asterisks.")
    fields = {}
    for key in ("header_url", "header_title"):
        value = payload.get(key)
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 64:
            raise ValueError("Enter a header URL and title (1–64 characters).")
        if not value.isprintable():
            raise ValueError("Header fields cannot contain control characters.")
        fields[key] = value.strip()
    for key in ("checksum", "text", "no_holes", "plus"):
        if type(payload.get(key, False)) is not bool:
            raise ValueError("Options must be true or false.")
    cmd = [sys.executable, str(CLI), "--report=" + report, "--data=" + data,
           "--header-url=" + fields["header_url"], "--header-title=" + fields["header_title"],
           "--out-dir", str(directory / "out"), "--gen-dir", str(directory / "cache")]
    if payload.get("checksum") and report != "ymca_letter_6up_mixed":
        cmd.append("--checksum")
    if payload.get("text") and report.startswith("barcode_"):
        cmd.append("--text")
    if payload.get("no_holes") and not report.startswith("barcode_"):
        cmd.append("--no-holes")
    if payload.get("plus"):
        cmd.append("--plus")
    return cmd, REPORTS[report][1]


def render(payload: dict) -> tuple[bytes, str]:
    # No membership data or generated files are retained by this frontend.
    with tempfile.TemporaryDirectory(prefix="ymca-web-") as tmp:
        directory = Path(tmp)
        cmd, extension = validated_command(payload, directory)
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=30)
        if proc.returncode:
            # CLI output can include private membership data. Do not return or log it.
            raise RuntimeError("Rendering failed. Check the local Zint and OCR-B setup.")
        files = list((directory / "out").glob("*." + extension))
        if len(files) != 1 or files[0].stat().st_size > MAX_OUTPUT:
            raise RuntimeError("Unexpected renderer output.")
        return files[0].read_bytes(), extension


def page(token: str) -> bytes:
    reports = "".join(f'<option value="{html.escape(key)}">{html.escape(label)}</option>'
                      for key, (label, _) in REPORTS.items())
    associations = json.loads(ASSOCIATIONS.read_text(encoding="utf-8"))["associations"]
    options = "".join(
        '<option data-url="{}" data-title="{}">{}</option>'.format(
            html.escape(item["url"], quote=True), html.escape(item["title"], quote=True),
            html.escape(item["name"])) for item in associations)
    return (PAGE.read_text(encoding="utf-8")
            .replace("__REPORTS__", reports)
            .replace("__ASSOCIATIONS__", options)
            .replace("__TOKEN__", token)).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        # Avoid recording sensitive request metadata.
        pass

    def respond(self, status, body, content_type, **headers):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'unsafe-inline'; "
                         "style-src 'unsafe-inline'; img-src blob:; frame-src blob:; "
                         "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
                         "form-action 'none'")
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def error(self, status, message):
        self.respond(status, json.dumps({"error": message}).encode(), "application/json")

    def trusted_host(self):
        return self.headers.get("Host") in self.server.hosts

    def do_GET(self):
        if not self.trusted_host():
            return self.error(403, "Untrusted host.")
        if self.path != "/":
            return self.error(404, "Not found.")
        self.respond(200, page(self.server.token), "text/html; charset=utf-8")

    def do_POST(self):
        if not self.trusted_host() or self.headers.get("Origin") not in self.server.origins:
            return self.error(403, "Untrusted origin.")
        token = self.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(token.encode(), self.server.token.encode()):
            return self.error(403, "Reload the page and try again.")
        if self.path != "/render":
            return self.error(404, "Not found.")
        if self.headers.get_content_type() != "application/json":
            return self.error(415, "Expected JSON.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.error(400, "Invalid request length.")
        if not 0 < length <= MAX_BODY:
            return self.error(413, "Request too large or empty.")
        try:
            payload = json.loads(self.rfile.read(length))
            result, extension = render(payload)
        except (ValueError, UnicodeError) as exc:
            # JSON decoding errors can contain user data; use a generic message.
            return self.error(400, "Invalid input." if isinstance(exc, (json.JSONDecodeError, UnicodeError)) else str(exc))
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            return self.error(503, "Rendering unavailable. Check Zint, OCR-B and server configuration.")
        self.respond(200, result, MIME[extension],
                     **{"Content-Disposition": f'attachment; filename="card-output.{extension}"'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--origin", help="Exact external HTTPS origin of an authenticated reverse proxy")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    hosts = {f"127.0.0.1:{args.port}", f"localhost:{args.port}"}
    origins = {"http://" + host for host in hosts}
    if args.origin:
        origin = urlsplit(args.origin)
        if (origin.scheme != "https" or not origin.hostname or origin.path or origin.query
                or origin.fragment or origin.username or origin.password):
            parser.error("--origin must be an exact HTTPS origin, without a path")
        # External origin is allowed only for the explicitly configured proxy.
        hosts.add(origin.netloc)
        origins.add(args.origin)
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.hosts = hosts
    server.origins = origins
    server.token = secrets.token_urlsafe(32)
    print(f"Card Maker: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
