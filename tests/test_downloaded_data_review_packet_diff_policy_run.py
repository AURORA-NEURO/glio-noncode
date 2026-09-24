"""End-to-end source-to-decision run coverage for downloaded data."""

# ruff: noqa: E501

from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet_diff_policy_run import (
    build_run,
    capabilities,
    load_run,
    query_run,
    render_run_markdown,
    run_json,
    run_schema,
    verify_run,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_run_audit import (
    audit_run,
    audit_schema,
    query_audit,
    verify_audit,
)
from glio_noncode.errors import ValidationError


def _source_bytes(payload: str) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("data.csv", payload)
    return output.getvalue()


class DownloadedDataReviewPacketDiffPolicyRunTest(unittest.TestCase):
    def setUp(self) -> None:
        self.left = _source_bytes("record_id,score\nA,1\nB,2\n")
        self.right = _source_bytes("record_id,score,group\nA,1,x\nB,3,y\nC,4,z\n")

    def test_end_to_end_ready_and_blocked_runs_are_source_free(self) -> None:
        ready = build_run(self.left, self.right, run_id="ready-run", profile="release", maximum_added=1, maximum_field_changed=256)
        blocked = build_run(self.left, self.right, run_id="blocked-run", profile="strict")
        ready_audit = audit_run(ready.receipt, package=ready.package)
        blocked_audit = audit_run(blocked.receipt, package=blocked.package)
        self.assertEqual((ready.receipt.policy_state, ready.receipt.policy_accepted), ("ready", True))
        self.assertEqual((blocked.receipt.policy_state, blocked.receipt.policy_accepted), ("blocked", False))
        self.assertEqual((ready_audit.check_count, ready_audit.passed_count, ready_audit.failed_count, ready_audit.accepted), (13, 13, 0, True))
        self.assertEqual((blocked_audit.check_count, blocked_audit.passed_count, blocked_audit.failed_count, blocked_audit.accepted), (13, 13, 0, True))
        self.assertEqual(verify_run(run_json(ready).encode("utf-8")).content_address, ready.receipt.content_address)
        self.assertEqual(load_run(run_json(ready).encode("utf-8")).package_address, ready.receipt.package_address)
        self.assertEqual(query_run(ready, resource="policy")["value"]["state"], "ready")
        self.assertIn("Downloaded Data Review Run", render_run_markdown(ready))
        self.assertTrue(run_schema()["properties"]["package_address"])
        self.assertTrue(capabilities()["builds_packets_diff_policy_and_package"])
        self.assertTrue(audit_schema()["properties"]["checks"])
        self.assertEqual(query_audit(ready_audit, passed=False)["matched"], 0)

    def test_tampering_and_missing_package_fail_closed(self) -> None:
        run = build_run(self.left, self.right, run_id="tampered-run", profile="release", maximum_added=1, maximum_field_changed=256)
        altered = run.receipt.to_dict() | {"diff_item_count": run.receipt.diff_item_count + 1}
        with self.assertRaises(ValidationError):
            verify_run(altered)
        rejected = audit_run(altered)
        self.assertFalse(rejected.accepted)
        self.assertEqual(rejected.failed_count, 13)
        missing_package = audit_run(run.receipt)
        self.assertFalse(missing_package.accepted)
        self.assertEqual(missing_package.failed_count, 3)

    def test_atomic_cli_and_http_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path = root / "left.zip"
            right_path = root / "right.zip"
            run_path = root / "run.json"
            package_path = root / "package.zip"
            audit_path = root / "audit.json"
            left_path.write_bytes(self.left)
            right_path.write_bytes(self.right)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run", str(left_path), str(right_path), "--run-id", "cli-run", "--profile", "release", "--maximum-added", "1", "--maximum-field-changed", "256", "--package-destination", str(package_path), "--run-destination", str(run_path), "--audit-destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run-verify", str(run_path), "--package", str(package_path)]), 0)
            self.assertEqual(main(["downloaded-data-review-packet-diff-policy-run-audit", str(run_path), "--package", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(verify_audit(audit_path).accepted, True)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, values: dict[str, object]) -> dict[str, object]:
                    query = urlencode({key: str(value) for key, value in values.items()})
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get("/v1/downloaded-data/review-packet/diff/policy/run", {"left": left_path, "right": right_path, "run_id": "http-run", "profile": "release", "maximum_added": 1, "maximum_field_changed": 256, "package_destination": root / "http-package.zip", "run_destination": root / "http-run.json", "audit_destination": root / "http-audit.json"})
                self.assertEqual(built["policy_state"], "ready")
                queried = get("/v1/downloaded-data/review-packet/diff/policy/run/query", {"input": root / "http-run.json", "resource": "lineage"})
                self.assertEqual(queried["value"]["package_address"], json.loads((root / "http-run.json").read_text(encoding="utf-8"))["package_address"])
                audited = get("/v1/downloaded-data/review-packet/diff/policy/run/audit", {"input": run_path, "package": package_path})
                self.assertTrue(audited["accepted"])
                with urlopen(f"http://127.0.0.1:{server.server_port}/v1/downloaded-data/review-packet/diff/policy/run/schema", timeout=20) as response:
                    self.assertEqual(json.loads(response.read())["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
