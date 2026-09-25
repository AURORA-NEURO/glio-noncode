"""Deep contracts for module-580 transport catalogs and rollup audits."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580_aud as catalog_audit_model
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
    left, right = _snapshot("left"), _snapshot("right")
    items = tuple((_item(1, "entry-added", empty, _snapshot("added"), "added"), _item(2, "entry-changed", left, right, "changed"), _item(3, "entry-removed", _snapshot("removed"), empty, "removed"), _item(4, "entry-same", same, same, "unchanged")))
    body = {"diff_id": "module580-diff", "version": diff_model.VERSION, "boundary": diff_model.BOUNDARY, "catalog_id": "module580-catalog", "left_catalog_address": CATALOG_PREFIX + ":" + "a" * 64, "right_catalog_address": CATALOG_PREFIX + ":" + "b" * 64, "left_posture": "ready", "right_posture": "ready", "state_transition": "same-ready", "direction": "changed", "added_count": 1, "removed_count": 1, "changed_count": 1, "unchanged_count": 1, "items": items, "content_address": diff_model.DIFF_PREFIX + ":pending"}
    provisional = Diff(**body)
    return Diff(**(body | {"content_address": address_diff(provisional)}))


class FixedTransportCatalogDiffPolicyTransportCatalog580Test(unittest.TestCase):
    def setUp(self) -> None:
        diff = _build_diff()
        release = policy_model.release_policy(diff, policy_id="module580-release")
        strict = policy_model.strict_policy(diff, policy_id="module580-strict")
        release_audit = policy_audit_model.audit_policy(release, diff=diff)
        strict_audit = policy_audit_model.audit_policy(strict, diff=diff)
        self.release = transport_model.build_package(diff, release, release_audit, package_id="module580-release-transport")
        self.strict = transport_model.build_package(diff, strict, strict_audit, package_id="module580-strict-transport")
        self.catalog = catalog_model.build_catalog((self.strict, self.release), entry_ids=("strict", "release"), catalog_id="module580-catalog")

    def test_deterministic_mixed_rollup_and_independent_recompute(self) -> None:
        repeated = catalog_model.build_catalog((self.release, self.strict), entry_ids=("release", "strict"), catalog_id="module580-catalog")
        receipt = catalog_audit_model.audit_catalog(self.catalog, packages=(self.release, self.strict))
        self.assertEqual(self.catalog.content_address, repeated.content_address)
        self.assertEqual((self.catalog.state, self.catalog.entry_count, self.catalog.accepted_count, self.catalog.ready_count, self.catalog.blocked_count), ("mixed", 2, 2, 1, 1))
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(catalog_model.query_catalog(self.catalog, resource="entries", state="blocked")["returned"], 1)

    def test_duplicate_and_tamper_rejection_persistence(self) -> None:
        with self.assertRaises(ValidationError):
            catalog_model.build_catalog((self.release, self.release), entry_ids=("one", "two"), catalog_id="duplicate")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            audit_path = Path(directory) / "audit.json"
            catalog_model.write_catalog(self.catalog, path)
            receipt = catalog_audit_model.audit_catalog(path)
            catalog_audit_model.write_audit(receipt, audit_path)
            self.assertEqual(catalog_model.load_catalog(path).content_address, self.catalog.content_address)
            self.assertEqual(catalog_audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                catalog_model.verify_catalog(self.catalog.to_dict() | {"state": "ready"})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release_path, strict_path = root / "release.zip", root / "strict.zip"
            catalog_path, audit_path = root / "catalog.json", root / "audit.json"
            transport_model.write_package(self.release, release_path)
            transport_model.write_package(self.strict, strict_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_580_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, "--package", str(release_path), "--package", str(strict_path), "--entry-id", "release", "--entry-id", "strict", "--catalog-id", "cli-module580", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--resource", "entries", "--state", "blocked"]), 0)
            self.assertEqual(invoke([command + "-audit", str(catalog_path), "--package", str(release_path), "--package", str(strict_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport" + "/catalog"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("package", release_path), ("package", strict_path), ("entry_id", "release"), ("entry_id", "strict"), ("catalog_id", "http-module580"), ("destination", catalog_path), ("overwrite", "true")])
                self.assertEqual((built["state"], built["entry_count"], built["blocked_count"]), ("mixed", 2, 1))
                queried = get(base + "/query", [("input", catalog_path), ("resource", "entries"), ("state", "blocked")])
                self.assertEqual(queried["returned"], 1)
                audited = get(base + "/audit", [("input", catalog_path), ("package", release_path), ("package", strict_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                schema = get(base + "/schema", [])
                self.assertIn("entries", schema.get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", {}))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
