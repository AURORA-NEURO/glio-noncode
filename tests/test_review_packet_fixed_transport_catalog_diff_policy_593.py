"""Deep contracts for module593 longitudinal module592 catalog diffs."""

# ruff: noqa: E501, I001

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_592 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_593 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_593_aud as audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_591_ct import PACKAGE_PREFIX
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_592_ct import CATALOG_PREFIX, ENTRY_PREFIX, Catalog, Entry, address_catalog, address_entry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _entry(entry_id: str, *, state: str = "ready", package_byte_count: int = 100) -> Entry:
    seed = sum(ord(char) for char in entry_id)
    body = {"entry_id": entry_id, "package_id": "package-" + entry_id, "package_address": PACKAGE_PREFIX + ":" + f"{seed:064x}", "manifest_address": "manifest:" + f"{seed + 10:064x}", "diff_address": "diff:" + f"{seed + 20:064x}", "policy_address": "policy:" + f"{seed + 30:064x}", "audit_address": "audit:" + f"{seed + 40:064x}", "policy_state": state, "policy_accepted": state == "ready", "audit_accepted": True, "package_byte_count": package_byte_count, "member_count": 4, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = Entry(**body)
    return Entry(**(body | {"content_address": address_entry(provisional)}))


def _catalog(entries: tuple[Entry, ...], catalog_id: str = "module593-catalog") -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyTransportCatalogDiff593Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        self.left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200), _entry("delta", state="blocked")))
        self.right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("epsilon")))
        self.value = diff_model.build_diff(self.left, self.right, diff_id="module593-diff")

    def test_deterministic_classification_transition_and_direction(self) -> None:
        repeated = diff_model.build_diff(self.left, self.right, diff_id="module593-diff")
        self.assertEqual(self.value.content_address, repeated.content_address)
        self.assertEqual((self.value.added_count, self.value.removed_count, self.value.changed_count, self.value.unchanged_count), (1, 1, 1, 1))
        self.assertEqual((self.value.state_transition, self.value.direction), ("mixed-to-ready", "improved"))
        self.assertEqual(tuple(item.change for item in self.value.items), ("unchanged", "changed", "removed", "added"))
        self.assertEqual(diff_model.query_diff(self.value, change="removed")["returned"], 1)
        self.assertEqual(diff_model.query_diff(self.value, text="policy_state")["returned"], 3)

    def test_independent_audit_persistence_and_tamper_rejection(self) -> None:
        receipt = audit_model.audit_diff(self.value, left=self.left, right=self.right)
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        with tempfile.TemporaryDirectory() as directory:
            diff_path, audit_path = Path(directory) / "diff.json", Path(directory) / "audit.json"
            diff_model.write_diff(self.value, diff_path)
            audit_model.write_audit(receipt, audit_path)
            self.assertEqual(diff_model.load_diff(diff_path).content_address, self.value.content_address)
            self.assertEqual(audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                diff_model.verify_diff(self.value.to_dict() | {"direction": "regressed"})
            with self.assertRaises(ValidationError):
                diff_model.build_diff(self.left, _catalog((_entry("zeta"),), catalog_id="other"), diff_id="mismatch")

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path, diff_path, audit_path = (root / name for name in ("left.json", "right.json", "diff.json", "audit.json"))
            catalog_model.write_catalog(self.left, left_path)
            catalog_model.write_catalog(self.right, right_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_DIFF_593_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(left_path), str(right_path), "--diff-id", "cli-module593", "--destination", str(diff_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(diff_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(diff_path), "--change", "removed"]), 0)
            self.assertEqual(invoke([command + "-audit", str(diff_path), "--left", str(left_path), "--right", str(right_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)
            self.assertEqual(invoke([command + "-audit-query", str(audit_path), "--passed"]), 0)
            for suffix in ("-schema", "-item-schema", "-capabilities", "-audit-check-schema", "-audit-schema", "-audit-capabilities"):
                self.assertEqual(invoke([command + suffix]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff"

                def get(path: str, pairs: list[tuple[str, object]] | None = None) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in (pairs or [])])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("left", left_path), ("right", right_path), ("diff_id", "http-module593"), ("destination", diff_path), ("overwrite", "true")])
                self.assertEqual((built["state_transition"], built["direction"], built["changed_count"]), ("mixed-to-ready", "improved", 1))
                queried = get(base + "/query", [("input", diff_path), ("change", "removed")])
                self.assertEqual(queried["returned"], 1)
                audited = get(base + "/audit", [("input", diff_path), ("left", left_path), ("right", right_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("items", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()


