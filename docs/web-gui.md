# Browser GUI

The browser GUI is a local frontend to the existing Python renderer. It does
not replace the CLI or Tkinter application.

## Run

Install the existing requirements and configure Zint and OCR-B as described
in [the main README](../README.md). Then run from the repository root:

```sh
python3 -m pip install -r requirements.txt
python3 src/web_gui.py --port 8765
```

Open http://127.0.0.1:8765. Select a layout, enter an existing membership code
you are authorized to use, and generate a preview. Download or open the
result to print at 100% scale. On mobile browsers without inline PDF support,
use Open / print or Download.

The GUI supports all seven existing report formats and reads the association
presets from the repository. It does not modify the renderer or its geometry.
Personal inputs are not saved by the web frontend; intermediate files are
isolated in temporary directories and removed after rendering. Downloaded
files remain on the device. The renderer's local dependency configuration
is reused. No personal defaults are sent to the browser.

## Remote use

By design the server only binds to IPv4 loopback. For a remote host, use an
SSH tunnel, for example:

```sh
ssh -L 8765:127.0.0.1:8765 user@server
```

For a private HTTPS reverse proxy, start with:

```sh
python3 src/web_gui.py --port 8765 --origin https://ymca.rsk.al
```

Configure the proxy to forward to 127.0.0.1:8765, preserve the original Host
and Origin headers, enforce authentication and HTTPS, limit request rates and
sizes, and disable response caching and request-body logging. Do not expose
the backend port or publish an unauthenticated route. The origin and CSRF
checks are not a substitute for authentication. This repository change does
not configure or deploy the reverse proxy.

## Tests

```sh
python3 -m unittest discover -s tests
```

Tests cover argument validation, layout-specific options, temporary file
cleanup and page generation. Actual rendering requires Zint and a local font.
