"""Workbench boundary tests. Mock runners test the API contract, not SysML validity."""
import io
import json
from pathlib import Path
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import zipfile

from mvp.app import server


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "mvp"
        self.root.mkdir()
        self.patches = [patch.object(server, "PROJECT_ROOT", self.root),
                        patch.object(server, "HISTORY_ROOT", self.root / "app/data/history")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_input_validation_and_explicit_approval(self):
        self.assertFalse(server.validate_request({"case_name": "baseline"})["preview_approved"])
        self.assertTrue(server.validate_request({"case_name": "candidate_a", "preview_approved": True})["preview_approved"])
        for payload in ({"case_name": "arbitrary"}, {"case_name": "baseline", "link_mbps": float("nan")},
                        {"case_name": "baseline", "link_mbps": float("inf")},
                        {"case_name": "baseline", "link_mbps": 10 ** 400},
                        {"case_name": "baseline", "data_rate_mbps": -2},
                        {"case_name": "baseline", "link_mbps": True},
                        {"case_name": "baseline", "preview_approved": "true"},
                        {"case_name": "baseline", "command": "echo test"}):
            with self.subTest(payload=payload), self.assertRaises(server.APIError):
                server.validate_request(payload)

    def test_missing_engine_is_error_and_persists(self):
        with patch.object(server.importlib, "import_module", side_effect=ImportError("missing engine")):
            status, record = server.execute({"case_name": "baseline"})
        self.assertEqual(status, 503)
        self.assertEqual(record["status"], "ERROR")
        self.assertNotIn("result", record)
        self.assertEqual(server.read_record(record["record_id"]), record)
        self.assertFalse(server.RUN_LOCK.locked())

    def test_fail_is_not_rewritten_and_model_survives_reopen(self):
        model = self.root / "runs/test/model.sysml"
        model.parent.mkdir(parents=True)
        model.write_text("package BoundaryTest {}", encoding="utf-8")
        received = {}
        def runner(**kwargs):
            received.update(kwargs)
            return {"run_id": "test", "run_dir": str(model.parent), "model_path": str(model),
                    "sysml": {"status": "FAIL", "diagnostics": ["unit-test fixture"]},
                    "checks": [{"id": "X", "status": "UNKNOWN"}]}
        with patch.object(server.importlib, "import_module", return_value=types.SimpleNamespace(run_case=runner)):
            status, record = server.execute({"case_name": "candidate_a", "data_rate_mbps": 20, "preview_approved": True})
        self.assertEqual(status, 200)
        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(record["result"]["sysml"]["status"], "FAIL")
        self.assertEqual(received["data_rate_mbps"], 20)
        self.assertTrue(received["preview_approved"])
        persisted = server.read_record(record["record_id"])
        self.assertEqual(persisted["result"]["model_text"], "package BoundaryTest {}")
        self.assertEqual(server.list_history()[0]["record_id"], record["record_id"])
        with zipfile.ZipFile(io.BytesIO(server.export_run(record["record_id"]))) as archive:
            self.assertEqual(set(archive.namelist()), {"workbench-record.json", "run/model.sysml"})

    def test_runner_exception_releases_lock(self):
        def runner(**kwargs):
            raise RuntimeError("tool stopped")
        with patch.object(server.importlib, "import_module", return_value=types.SimpleNamespace(run_case=runner)):
            status, record = server.execute({"case_name": "baseline"})
        self.assertEqual(status, 500)
        self.assertEqual(record["status"], "ERROR")
        self.assertFalse(server.RUN_LOCK.locked())
        self.assertIsNone(server.ACTIVE_RUN)

    def test_concurrent_run_rejected(self):
        server.RUN_LOCK.acquire()
        try:
            with self.assertRaises(server.APIError) as caught:
                server.execute({"case_name": "baseline"})
            self.assertEqual(caught.exception.status, 409)
        finally:
            server.RUN_LOCK.release()

    def test_reference_dispatch_is_whitelisted_and_preserves_verdict(self):
        with self.assertRaises(server.APIError):
            server.execute({"reference_name": "arbitrary-project"}, reference=True)
        received = []
        def reference_runner(reference_name):
            received.append(reference_name)
            return {"status": "UNKNOWN", "sysml": {"status": "FAIL"}, "checks": []}
        with patch.object(server.importlib, "import_module", return_value=types.SimpleNamespace(run_reference=reference_runner)):
            status, record = server.execute({"reference_name": "nasa-cfe"}, reference=True)
        self.assertEqual(status, 200)
        self.assertEqual(received, ["nasa-cfe"])
        self.assertEqual(record["result"]["sysml"]["status"], "FAIL")
        self.assertEqual(record["request"], {"reference_name": "nasa-cfe"})

    def test_source_and_record_traversal_and_symlink_escape(self):
        outside = Path(self.temp.name) / "private.txt"
        outside.write_text("private", encoding="utf-8")
        fixtures = self.root / "fixtures"
        fixtures.mkdir()
        (fixtures / "source.txt").write_text("public fixture", encoding="utf-8")
        (fixtures / "escape.txt").symlink_to(outside)
        self.assertEqual([item["path"] for item in server.source_files()], ["fixtures/source.txt"])
        self.assertEqual(server.read_source("fixtures/source.txt")["text"], "public fixture")
        for value in ("../private.txt", str(outside), "fixtures/escape.txt"):
            with self.assertRaises(server.APIError):
                server.read_source(value)
        with self.assertRaises(server.APIError):
            server.read_record("../private")

    def test_export_rejects_outside_and_symlink(self):
        run = self.root / "runs/x"
        run.mkdir(parents=True)
        (run / "escape.txt").symlink_to(Path(self.temp.name) / "outside.txt")
        record = {"record_id": "export-test", "created_at": "2026", "status": "COMPLETED",
                  "request": {}, "result": {"run_dir": str(run)}}
        server.save_record(record)
        with self.assertRaises(server.APIError):
            server.export_run("export-test")
        record["result"]["run_dir"] = str(self.root / "app")
        server.save_record(record)
        with self.assertRaises(server.APIError):
            server.export_run("export-test")

    def test_http_security_and_unconfigured_agent(self):
        httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            with urlopen(base + "/") as response:
                self.assertIn("Engineering Change Workbench", response.read().decode())
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            blocked = Request(base + "/api/status", headers={"Host": "evil.example"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(blocked)
            self.assertEqual(caught.exception.code, 403)
            cross_site = Request(base + "/api/run", data=b'{"case_name":"baseline"}',
                                 headers={"Content-Type": "application/json", "Origin": "https://evil.example"})
            with self.assertRaises(HTTPError) as caught:
                urlopen(cross_site)
            self.assertEqual(caught.exception.code, 403)
            agent_request = Request(base + "/api/agent", data=json.dumps({"message": "Check the model", "case_name": "baseline"}).encode(),
                                    headers={"Content-Type": "application/json"})
            with patch.object(server.importlib, "import_module", return_value=types.SimpleNamespace()):
                with self.assertRaises(HTTPError) as caught:
                    urlopen(agent_request)
            self.assertEqual(caught.exception.code, 503)
            self.assertIn("Agent not connected", caught.exception.read().decode())
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
