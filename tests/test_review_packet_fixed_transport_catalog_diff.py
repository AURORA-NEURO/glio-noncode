"""Deep contracts for longitudinal comparison of fixed policy transport catalogs."""

# ruff: noqa: E501

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode import _legacy_cli
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff,
    catalog_model,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import (
    release_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_transport import (
    build_transport,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_transport_catalog import (
    build_transport_catalog,
    verify_transport_catalog,
    write_transport_catalog,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_tr_cat_diff import (
    build_transport_catalog_diff,
    query_transport_catalog_diff,
    verify_transport_catalog_diff,
    write_transport_catalog_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_tr_cat_diff_aud import (
    audit_transport_catalog_diff,
    query_audit,
    verify_audit,
    write_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_gate_aud import (
    audit_policy,
)
from glio_noncode.errors import ValidationError


class FixedTransportCatalogDiffTest(unittest.TestCase):
    def setUp(self) -> None:
        source = catalog_model.build_catalog((), catalog_id="fixed-transport-diff-source")
        source_diff = build_diff(source, source, diff_id="fixed-transport-diff-source-diff")
        policy = release_policy(source_diff, policy_id="fixed-transport-diff-policy", require_ready=False)
        policy_audit = audit_policy(policy, diff=source_diff)
        packet_a = build_transport(source_diff, policy, policy_audit, package_id="fixed-transport-diff-a")
        packet_b = build_transport(source_diff, policy, policy_audit, package_id="fixed-transport-diff-b")
        blocked_policy = release_policy(source_diff, policy_id="fixed-transport-diff-blocked-policy", require_ready=False, require_change=True)
        blocked_audit = audit_policy(blocked_policy, diff=source_diff)
        blocked = build_transport(source_diff, blocked_policy, blocked_audit, package_id="fixed-transport-diff-blocked")
        self.left = build_transport_catalog((packet_a.package_bytes, packet_b.package_bytes, blocked.package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-removed"), catalog_id="fixed-transport-diff-catalog")
        self.right = build_transport_catalog((packet_a.package_bytes, blocked.package_bytes, packet_b.package_bytes), entry_ids=("entry-unchanged", "entry-changed", "entry-added"), catalog_id="fixed-transport-diff-catalog")
        self.diff = build_transport_catalog_diff(self.left, self.right, diff_id="fixed-transport-catalog-diff")

    def test_four_way_classification_and_direction(self) -> None:
        self.assertEqual((self.diff.added_count, self.diff.removed_count, self.diff.changed_count, self.diff.unchanged_count), (1, 1, 1, 1))
        self.assertEqual(self.diff.direction, "changed")
        self.assertEqual(self.diff.state_transition, "same-mixed")
        self.assertEqual(tuple(item.entry_id for item in self.diff.items), ("entry-added", "entry-changed", "entry-removed", "entry-unchanged"))
        self.assertEqual(verify_transport_catalog_diff(self.diff.to_dict()).content_address, self.diff.content_address)
        self.assertEqual(query_transport_catalog_diff(self.diff, change="changed")["matched"], 1)
        self.assertEqual(query_transport_catalog_diff(self.diff, change="added")["matched"], 1)
        self.assertEqual(query_transport_catalog_diff(self.diff, change="removed")["matched"], 1)

    def test_independent_audit_and_fail_closed_tamper(self) -> None:
        receipt = audit_transport_catalog_diff(self.diff, left=self.left, right=self.right)
        self.assertTrue(receipt.accepted)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count), (13, 13, 0))
        self.assertEqual(verify_audit(receipt.to_dict()).content_address, receipt.content_address)
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)
        tampered = self.diff.to_dict() | {"changed_count": 0}
        with self.assertRaises(ValidationError):
            verify_transport_catalog_diff(tampered)
        self.assertNotIn("agent", json.dumps(self.diff.to_dict()).lower())
        self.assertNotIn("model", json.dumps(self.diff.to_dict()).lower())

    def test_persistence_cli_http_schema_and_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path = root / "left.json", root / "right.json"
            diff_path, audit_path = root / "diff.json", root / "audit.json"
            write_transport_catalog(self.left, left_path)
            write_transport_catalog(self.right, right_path)
            write_transport_catalog_diff(self.diff, diff_path)
            write_audit(audit_transport_catalog_diff(self.diff, left=self.left, right=self.right), audit_path)
            self.assertEqual(verify_transport_catalog(left_path).content_address, self.left.content_address)
            self.assertEqual(verify_transport_catalog_diff(diff_path).content_address, self.diff.content_address)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_DIFF_565_COMMAND

            def invoke(arguments: list[str]) -> tuple[int, str]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    code = main(arguments)
                return code, output.getvalue()

            self.assertEqual(invoke([command, str(left_path), str(right_path), "--destination", str(diff_path), "--allow-existing", "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)])[0], 0)
            self.assertEqual(invoke([command + "-audit", str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--allow-existing", "--format", "summary"])[0], 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)])[0], 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "changed"])[0], 0)
            self.assertEqual(invoke([command + "-schema"])[0], 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-fixed-transport-diff")])
                self.assertEqual((built["changed_count"], built["added_count"], built["removed_count"]), (1, 1, 1))
                queried = get(base + "/query", [("input", diff_path), ("change", "changed")])
                self.assertEqual((queried["matched"], queried["returned"]), (1, 1))
                audited = get(base + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertEqual((audited["accepted"], audited["passed_count"], audited["check_count"]), (True, 13, 13))
                schema = get(base + "/schema", [])
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
