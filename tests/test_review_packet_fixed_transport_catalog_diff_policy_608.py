"""Deep contracts for module608 policy-decision transport catalogs."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_604 as catalog_seed_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_605 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_606 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_606_aud as policy_audit_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_607 as transport_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_608 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_608_aud as audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_603_ct import PACKAGE_PREFIX
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_604_ct import CATALOG_PREFIX, ENTRY_PREFIX, Catalog, Entry, address_catalog, address_entry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _entry(entry_id: str, *, state: str = "ready", package_byte_count: int = 100) -> Entry:
    seed = ord(entry_id[0]) - 96
    body = {"entry_id": entry_id, "package_id": "package-" + entry_id, "package_address": PACKAGE_PREFIX + ":" + f"{seed:064x}", "manifest_address": "manifest:" + f"{seed + 10:064x}", "diff_address": "diff:" + f"{seed + 20:064x}", "policy_address": "policy:" + f"{seed + 30:064x}", "audit_address": "audit:" + f"{seed + 40:064x}", "policy_state": state, "policy_accepted": state == "ready", "audit_accepted": True, "package_byte_count": package_byte_count, "member_count": 4, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = Entry(**body)
    return Entry(**(body | {"content_address": address_entry(provisional)}))


def _catalog(entries: tuple[Entry, ...], catalog_id: str = "module608-seed") -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_seed_model.VERSION, "boundary": catalog_seed_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyCatalog608Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200), _entry("delta", state="blocked")))
        right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("epsilon")))
        diff = diff_model.build_diff(left, right, diff_id="module608-diff")
        release = policy_model.release_policy(diff, policy_id="module608-release")
        strict = policy_model.strict_policy(diff, policy_id="module608-strict")
        release_audit = policy_audit_model.audit_policy(release, diff=diff)
        strict_audit = policy_audit_model.audit_policy(strict, diff=diff)
        self.release_package = transport_model.build_package(diff, release, release_audit, package_id="module608-release")
        self.strict_package = transport_model.build_package(diff, strict, strict_audit, package_id="module608-strict")
        self.value = catalog_model.build_catalog((self.release_package, self.strict_package), entry_ids=("release", "strict"), catalog_id="module608-catalog")

    def test_mixed_fold_lineage_and_independent_audit(self) -> None:
        repeated = catalog_model.build_catalog((self.release_package, self.strict_package), entry_ids=("release", "strict"), catalog_id="module608-catalog")
        receipt = audit_model.audit_catalog(self.value)
        self.assertEqual(self.value.content_address, repeated.content_address)
        self.assertEqual((self.value.entry_count, self.value.accepted_count, self.value.ready_count, self.value.blocked_count, self.value.state), (2, 2, 1, 1, "mixed"))
        self.assertEqual((receipt.check_count, receipt.passed_count, receipt.failed_count, receipt.accepted), (16, 16, 0, True))
        self.assertEqual(catalog_model.query_catalog(self.value, resource="entries", state="blocked")["returned"], 1)
        self.assertEqual(catalog_model.query_catalog(self.value, resource="entries", text="strict")["returned"], 1)

    def test_duplicate_persistence_and_tamper_rejection(self) -> None:
        with self.assertRaises(ValidationError):
            catalog_model.build_catalog((self.release_package, self.release_package), entry_ids=("a", "b"), catalog_id="duplicate")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            audit_path = Path(directory) / "audit.json"
            catalog_model.write_catalog(self.value, path)
            receipt = audit_model.audit_catalog(self.value)
            audit_model.write_audit(receipt, audit_path)
            self.assertEqual(catalog_model.load_catalog(path).content_address, self.value.content_address)
            self.assertEqual(audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                catalog_model.verify_catalog(self.value.to_dict() | {"state": "ready"})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release_path, strict_path, catalog_path, audit_path = (root / name for name in ("release.zip", "strict.zip", "catalog.json", "audit.json"))
            transport_model.write_package(self.release_package, release_path)
            transport_model.write_package(self.strict_package, strict_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_608_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(release_path), str(strict_path), "--entry-id", "release", "--entry-id", "strict", "--catalog-id", "cli-module608", "--destination", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--state", "blocked"]), 0)
            self.assertEqual(invoke([command + "-audit", str(catalog_path), "--destination", str(audit_path)]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)
            for suffix in ("-schema", "-entry-schema", "-capabilities", "-audit-check-schema", "-audit-schema", "-audit-capabilities"):
                self.assertEqual(invoke([command + suffix]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog"

                def get(path: str, pairs: list[tuple[str, object]] | None = None) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in (pairs or [])])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("package", release_path), ("package", strict_path), ("entry_id", "release"), ("entry_id", "strict"), ("catalog_id", "http-module608"), ("destination", catalog_path), ("overwrite", "true")])
                self.assertEqual((built["state"], built["entry_count"], built["accepted_count"]), ("mixed", 2, 2))
                queried = get(base + "/query", [("input", catalog_path), ("resource", "entries"), ("state", "blocked")])
                self.assertEqual(queried["returned"], 1)
                audited = get(base + "/audit", [("input", catalog_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("entries", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
