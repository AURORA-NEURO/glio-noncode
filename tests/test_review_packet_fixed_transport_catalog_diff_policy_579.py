"""Deep contracts for deterministic module-579 policy decision transports."""

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

from glio_noncode import _legacy_cli
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_577 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_578 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_578_aud as policy_audit_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_579 as transport_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_579_aud as transport_audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_577_ct import CATALOG_PREFIX, ITEM_PREFIX, SNAPSHOT_FIELDS, Diff, DiffItem, address_diff, address_item
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _snapshot(name: str) -> dict[str, object]:
    return {"package_id": name, "package_address": "package:" + "1" * 64, "manifest_address": "manifest:" + "2" * 64, "diff_address": "diff:" + "3" * 64, "policy_address": "policy:" + "4" * 64, "audit_address": "audit:" + "5" * 64, "policy_state": "ready", "policy_accepted": True, "audit_accepted": True, "member_count": 4, "member_byte_count": 1000, "package_byte_count": 1200}


def _item(ordinal: int, entry_id: str, left: dict[str, object], right: dict[str, object], change: str) -> DiffItem:
    changed = tuple(sorted(field for field in SNAPSHOT_FIELDS if left.get(field) != right.get(field)))
    body = {"ordinal": ordinal, "entry_id": entry_id, "change": change, "changed_fields": changed, "left_address": "entry:" + str(ordinal) * 64 if left else "", "right_address": "entry:" + str(ordinal + 4) * 64 if right else "", "left_snapshot": left, "right_snapshot": right, "content_address": ITEM_PREFIX + ":pending"}
    provisional = DiffItem(**body)
    return DiffItem(**(body | {"content_address": address_item(provisional)}))


def _build_diff() -> Diff:
    empty: dict[str, object] = {}
    same = _snapshot("same")
    changed_left, changed_right = _snapshot("changed-left"), _snapshot("changed-right")
    items = tuple((_item(1, "entry-added", empty, _snapshot("added"), "added"), _item(2, "entry-changed", changed_left, changed_right, "changed"), _item(3, "entry-removed", _snapshot("removed"), empty, "removed"), _item(4, "entry-same", same, same, "unchanged")))
    body = {"diff_id": "module579-diff", "version": diff_model.VERSION, "boundary": diff_model.BOUNDARY, "catalog_id": "module579-catalog", "left_catalog_address": CATALOG_PREFIX + ":" + "a" * 64, "right_catalog_address": CATALOG_PREFIX + ":" + "b" * 64, "left_posture": "ready", "right_posture": "ready", "state_transition": "same-ready", "direction": "changed", "added_count": 1, "removed_count": 1, "changed_count": 1, "unchanged_count": 1, "items": items, "content_address": diff_model.DIFF_PREFIX + ":pending"}
    provisional = Diff(**body)
    return Diff(**(body | {"content_address": address_diff(provisional)}))


class FixedTransportCatalogDiffPolicyTransport579Test(unittest.TestCase):
    def setUp(self) -> None:
        self.diff = _build_diff()
        self.policy = policy_model.release_policy(self.diff, policy_id="module579-release")
        self.policy_audit = policy_audit_model.audit_policy(self.policy, diff=self.diff)
        self.transport = transport_model.build_package(self.diff, self.policy, self.policy_audit, package_id="module579-release-transport")

    def test_determinism_lineage_and_independent_audit(self) -> None:
        repeated = transport_model.build_package(self.diff, self.policy, self.policy_audit, package_id="module579-release-transport")
        self.assertEqual(self.transport.package_bytes, repeated.package_bytes)
        diff, policy, audit, review = transport_model.load_package(self.transport)
        receipt = transport_audit_model.audit_package(self.transport)
        self.assertEqual((diff.content_address, policy.content_address, audit.content_address), (self.diff.content_address, self.policy.content_address, self.policy_audit.content_address))
        self.assertIn("Module579", review)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))

    def test_blocked_policy_preserves_failed_controls_and_tamper_rejects(self) -> None:
        strict = policy_model.strict_policy(self.diff, policy_id="module579-strict")
        strict_audit = policy_audit_model.audit_policy(strict, diff=self.diff)
        blocked = transport_model.build_package(self.diff, strict, strict_audit, package_id="module579-strict-transport")
        self.assertFalse(blocked.manifest.policy_accepted)
        self.assertEqual(blocked.manifest.policy_state, "blocked")
        self.assertTrue(transport_audit_model.audit_package(blocked).accepted)
        with self.assertRaises(ValidationError):
            transport_model.verify_package(blocked.package_bytes[:-1] + bytes((blocked.package_bytes[-1] ^ 1,)))

    def test_persistence_cli_http_query_and_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            transport_path, transport_audit_path = root / "transport.zip", root / "transport-audit.json"
            diff_model.write_diff(self.diff, diff_path)
            policy_model.write_policy(self.policy, policy_path)
            policy_audit_model.write_audit(self.policy_audit, audit_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_579_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), str(policy_path), "--audit", str(audit_path), "--package-id", "cli-module579", "--destination", str(transport_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(transport_path)]), 0)
            self.assertEqual(invoke([command + "-load", str(transport_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(transport_path), "--resource", "members"]), 0)
            self.assertEqual(invoke([command + "-audit", str(transport_path), "--destination", str(transport_audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(transport_audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("diff", diff_path), ("policy", policy_path), ("audit", audit_path), ("package_id", "http-module579"), ("destination", transport_path), ("overwrite", "true")])
                self.assertEqual((built["policy_state"], built["audit_accepted"], built["member_count"]), ("ready", True, 4))
                verified = get(base + "/verify", [("input", transport_path)])
                self.assertEqual(verified["package_id"], "http-module579")
                queried = get(base + "/query", [("input", transport_path), ("resource", "members")])
                self.assertEqual(queried["returned"], 4)
                audited = get(base + "/audit", [("input", transport_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertIn("manifest", schema.get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", {}))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
