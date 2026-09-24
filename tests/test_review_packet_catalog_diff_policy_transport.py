"""Coverage for deterministic review-packet catalog diff policy transports."""

# ruff: noqa: E501

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff import (
    build_diff,
    catalog_model,
    write_diff,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy import (
    release_policy,
    write_policy,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_transport import (
    build_transport,
    load_transport,
    package_json,
    query_transport,
    verify_transport,
    write_transport,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_tr_aud import (
    audit_transport,
    query_audit,
)
from glio_noncode.downloaded_data_review_packet_diff_policy_release_certificate_bundle_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_policy_package_catalog_diff_gate_aud import (
    audit_policy,
    write_audit,
)
from glio_noncode.errors import ValidationError


class DownloadedDataReviewPacketPolicyHandoffCatalogReviewPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = catalog_model.build_catalog((), catalog_id="policy-handoff-review-packet-empty")
        self.diff = build_diff(self.catalog, self.catalog, diff_id="policy-handoff-review-packet-empty-diff")
        self.policy = release_policy(self.diff, policy_id="policy-handoff-review-packet-release", require_ready=False)
        self.policy_audit = audit_policy(self.policy, diff=self.diff)

    def test_deterministic_transport_round_trip_and_independent_audit(self) -> None:
        first = build_transport(self.diff, self.policy, self.policy_audit, package_id="policy-handoff-review-packet")
        second = build_transport(self.diff, self.policy, self.policy_audit, package_id="policy-handoff-review-packet")
        self.assertEqual(first.package_bytes, second.package_bytes)
        self.assertEqual(first.package_address, second.package_address)
        self.assertEqual(len(first.manifest.members), 4)
        self.assertEqual(load_transport(first)[0].content_address, self.diff.content_address)
        self.assertEqual(query_transport(first, resource="members")["total"], 4)
        self.assertEqual(json.loads(package_json(first))["package_address"], first.package_address)
        receipt = audit_transport(first)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (15, 15, 0, True))
        self.assertEqual(query_audit(receipt, passed=False)["matched"], 0)

    def test_blocked_evidence_persistence_and_tamper_rejection(self) -> None:
        blocked = release_policy(self.diff, policy_id="policy-handoff-review-packet-blocked", require_ready=False, require_change=True)
        blocked_audit = audit_policy(blocked, diff=self.diff)
        packet = build_transport(self.diff, blocked, blocked_audit, package_id="policy-handoff-review-packet-blocked")
        self.assertEqual((packet.manifest.policy_state, packet.manifest.policy_accepted, packet.manifest.audit_accepted), ("blocked", False, True))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "review-packet.zip"
            write_transport(packet, destination)
            self.assertEqual(verify_transport(destination).package_address, packet.package_address)
        tampered = packet.package_bytes[:-1] + bytes((packet.package_bytes[-1] ^ 1,))
        with self.assertRaises(ValidationError):
            verify_transport(tampered)

    def test_cli_http_schema_and_query_surfaces(self) -> None:
        command = "downloaded-data-review-packet-diff-policy-release-certificate-bundle-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-policy-package-catalog-diff-transport"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, policy_audit_path = root / "diff.json", root / "policy.json", root / "policy-audit.json"
            packet_path, audit_path = root / "review-packet.zip", root / "review-packet-audit.json"
            write_diff(self.diff, diff_path)
            write_policy(self.policy, policy_path)
            write_audit(self.policy_audit, policy_audit_path)
            self.assertEqual(main([command, str(diff_path), str(policy_path), str(policy_audit_path), "--destination", str(packet_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-verify", str(packet_path)]), 0)
            self.assertEqual(main([command + "-audit", str(packet_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(main([command + "-audit-verify", str(audit_path)]), 0)
            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport"
                built = get(base, [("diff", diff_path), ("policy", policy_path), ("policy_audit", policy_audit_path)])
                queried = get(base + "/query", [("input", packet_path), ("resource", "members")])
                audited = get(base + "/audit", [("input", packet_path)])
                schema = get(base + "/schema", [])
                self.assertTrue(built["policy_accepted"])
                self.assertEqual(queried["total"], 4)
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (15, 0, True))
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
