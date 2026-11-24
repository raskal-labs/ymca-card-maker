import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import web_gui


class WebGUITests(TestCase):
    def payload(self, **changes):
        return dict(report="ymca_letter_6up", data="DEMO", header_url="example.invalid",
                    header_title="Demo", **changes)

    def test_all_existing_reports(self):
        for report, (_, expected) in web_gui.REPORTS.items():
            payload = self.payload()
            payload["report"] = report
            cmd, extension = web_gui.validated_command(payload, Path("/tmp/example"))
            self.assertIn("--report=" + report, cmd)
            self.assertEqual(extension, expected)

    def test_options_follow_layout(self):
        payload = self.payload(checksum=True, text=True, no_holes=True)
        payload["report"] = "ymca_letter_6up_mixed"
        cmd, _ = web_gui.validated_command(payload, Path("/tmp/example"))
        self.assertNotIn("--checksum", cmd)
        self.assertNotIn("--text", cmd)
        self.assertIn("--no-holes", cmd)

    def test_rejects_invalid_inputs(self):
        for key, value in [("data", ""), ("data", "*"), ("report", "../bad"),
                           ("header_title", "bad\nheader"), ("checksum", "true"),
                           ("out_dir", "/etc")]:
            payload = self.payload()
            payload[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                web_gui.validated_command(payload, Path("/tmp/example"))

    def test_generated_data_is_ephemeral(self):
        paths = []
        def fake_run(cmd, **kwargs):
            out = Path(cmd[cmd.index("--out-dir") + 1])
            out.mkdir()
            paths.append(out)
            (out / "demo.pdf").write_bytes(b"%PDF-demo")
            return type("Result", (), {"returncode": 0})()
        with patch.object(web_gui.subprocess, "run", side_effect=fake_run):
            data, ext = web_gui.render(self.payload())
        self.assertEqual((data, ext), (b"%PDF-demo", "pdf"))
        self.assertFalse(paths[0].exists())

    def test_page_has_all_layouts_and_token(self):
        page = web_gui.page("demo-token")
        self.assertIn(b"demo-token", page)
        for report in web_gui.REPORTS:
            self.assertIn(report.encode(), page)
        self.assertNotIn(b"__ASSOCIATIONS__", page)
