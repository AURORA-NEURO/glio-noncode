"""Deep contracts for strict and release gates over module-577 diffs."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_578_aud as audit_model
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
    added = _snapshot("added")
    items = tuple((_item(1, "entry-added", empty, added, "added"), _item(2, "entry-changed", changed_left, changed_right, "changed"), _item(3, "entry-removed", _snapshot("removed"), empty, "removed"), _item(4, "entry-same", same, same, "unchanged")))
    body = {"diff_id": "module578-diff", "version": diff_model.VERSION, "boundary": diff_model.BOUNDARY, "catalog_id": "module578-catalog", "left_catalog_address": CATALOG_PREFIX + ":" + "a" * 64, "right_catalog_address": CATALOG_PREFIX + ":" + "b" * 64, "left_posture": "ready", "right_posture": "ready", "state_transition": "same-ready", "direction": "changed", "added_count": 1, "removed_count": 1, "changed_count": 1, "unchanged_count": 1, "items": items, "content_address": diff_model.DIFF_PREFIX + ":pending"}
    provisional = Diff(**body)
    return Diff(**(body | {"content_address": address_diff(provisional)}))


class FixedTransportCatalogDiffPolicy578Test(unittest.TestCase):
    def setUp(self) -> None:
        self.diff = _build_diff()
        self.release = policy_model.release_policy(self.diff, policy_id="module578-release")
        self.strict = policy_model.strict_policy(self.diff, policy_id="module578-strict")

    def test_release_and_strict_decisions_have_independent_audits(self) -> None:
        self.assertEqual((self.release.accepted, self.release.state, self.release.passed_count, self.release.failed_count), (True, "ready", 16, 0))
        self.assertEqual((self.strict.accepted, self.strict.state, self.strict.passed_count, self.strict.failed_count), (False, "blocked", 10, 6))
        release_audit = audit_model.audit_policy(self.release, diff=self.diff)
        strict_audit = audit_model.audit_policy(self.strict, diff=self.diff)
        self.assertEqual((release_audit.check_count, release_audit.passed_count, release_audit.failed_count, release_audit.accepted), (16, 16, 0, True))
        self.assertEqual((strict_audit.check_count, strict_audit.passed_count, strict_audit.failed_count, strict_audit.accepted), (16, 16, 0, True))
        self.assertEqual(policy_model.query_policy(self.strict, passed=False)["returned"], 6)

    def test_persistence_tamper_and_public_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            diff_model.write_diff(self.diff, diff_path)
            policy_model.write_policy(self.release, policy_path)
            receipt = audit_model.audit_policy(policy_path, diff=diff_path)
            audit_model.write_audit(receipt, audit_path)
            self.assertEqual(policy_model.load_policy(policy_path).content_address, self.release.content_address)
            self.assertEqual(audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                policy_model.verify_policy(self.release.to_dict() | {"accepted": False})
            with self.assertRaises(ValidationError):
                policy_model.verify_policy(self.release.to_dict() | {"agent": "forbidden"})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path = root / "diff.json", root / "policy.json", root / "audit.json"
            diff_model.write_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_578_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), "--profile", "release", "--policy-id", "cli-module578", "--destination", str(policy_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(policy_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(policy_path), "--failed"]), 0)
            self.assertEqual(invoke([command + "-audit", str(policy_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("policy_id", "http-module578")])
                self.assertEqual((built["state"], built["accepted"], built["check_count"]), ("ready", True, 16))
                queried = get(base + "/query", [("input", policy_path), ("passed", "false")])
                self.assertEqual(queried["returned"], 0)
                audited = get(base + "/audit", [("input", policy_path), ("diff", diff_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertIn("checks", schema.get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", {}))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
