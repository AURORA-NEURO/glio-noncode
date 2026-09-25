"""Deep contracts for module-584 fixed policy transport catalogs."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580 as catalog_seed_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_581 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582_aud as policy_audit_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_583 as package_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_584 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_584_aud as audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_579_ct import PACKAGE_PREFIX
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580_ct import CATALOG_PREFIX, ENTRY_PREFIX, Catalog as SeedCatalog, Entry as SeedEntry, address_catalog, address_entry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _entry(entry_id: str, *, state: str = "ready", package_byte_count: int = 100) -> SeedEntry:
    seed = ord(entry_id[0]) - 96
    body = {"entry_id": entry_id, "package_id": "package-" + entry_id, "package_address": PACKAGE_PREFIX + ":" + f"{seed:064x}", "manifest_address": "manifest:" + f"{seed + 10:064x}", "diff_address": "diff:" + f"{seed + 20:064x}", "policy_address": "policy:" + f"{seed + 30:064x}", "audit_address": "audit:" + f"{seed + 40:064x}", "policy_state": state, "policy_accepted": state == "ready", "audit_accepted": True, "package_byte_count": package_byte_count, "member_count": 4, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = SeedEntry(**body)
    return SeedEntry(**(body | {"content_address": address_entry(provisional)}))


def _catalog(entries: tuple[SeedEntry, ...], catalog_id: str = "module584-seed") -> SeedCatalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_seed_model.VERSION, "boundary": catalog_seed_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = SeedCatalog(**body)
    return SeedCatalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyTransportCatalog584Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200)))
        right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("gamma")))
        diff = diff_model.build_diff(left, right, diff_id="module584-diff")
        release = policy_model.release_policy(diff, policy_id="module584-release")
        strict = policy_model.strict_policy(diff, policy_id="module584-strict")
        self.release = package_model.build_package(diff, release, policy_audit_model.audit_policy(release, diff=diff), package_id="module584-release")
        self.strict = package_model.build_package(diff, strict, policy_audit_model.audit_policy(strict, diff=diff), package_id="module584-strict")

    def test_mixed_catalog_determinism_lineage_and_independent_audit(self) -> None:
        catalog = catalog_model.build_catalog((self.release, self.strict), entry_ids=("release", "strict"), catalog_id="module584-catalog")
        repeated = catalog_model.build_catalog((self.release, self.strict), entry_ids=("release", "strict"), catalog_id="module584-catalog")
        receipt = audit_model.audit_catalog(catalog, packages=(self.release, self.strict))
        self.assertEqual(catalog.content_address, repeated.content_address)
        self.assertEqual(catalog_model.catalog_json(catalog), catalog_model.catalog_json(repeated))
        self.assertEqual((catalog.entry_count, catalog.accepted_count, catalog.ready_count, catalog.blocked_count, catalog.state), (2, 2, 1, 1, "mixed"))
        self.assertEqual(tuple(item.entry_id for item in catalog.entries), ("release", "strict"))
        self.assertEqual(catalog_model.query_catalog(catalog, resource="entries", state="blocked")["returned"], 1)
        self.assertEqual((receipt.passed_count, receipt.check_count, receipt.failed_count), (16, 16, 0))
        public = catalog_model.catalog_json(catalog).lower()
        self.assertNotIn('"agent"', public)
        self.assertNotIn('"model"', public)
        self.assertNotIn('"language"', public)

    def test_persistence_duplicate_identity_and_tamper_rejection(self) -> None:
        catalog = catalog_model.build_catalog((self.release, self.strict), entry_ids=("release", "strict"), catalog_id="module584-persist")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            audit_path = Path(directory) / "audit.json"
            catalog_model.write_catalog(catalog, path)
            receipt = audit_model.audit_catalog(path)
            audit_model.write_audit(receipt, audit_path)
            self.assertEqual(catalog_model.load_catalog(path).content_address, catalog.content_address)
            self.assertEqual(audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                catalog_model.verify_catalog(catalog.to_dict() | {"state": "ready"})
            with self.assertRaises(ValidationError):
                catalog_model.build_catalog((self.release, self.release), entry_ids=("one", "two"))
            with self.assertRaises(ValidationError):
                catalog_model.build_catalog((self.release, self.strict), entry_ids=("same", "same"))

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release_path, strict_path = root / "release.zip", root / "strict.zip"
            catalog_path, audit_path = root / "catalog.json", root / "audit.json"
            package_model.write_package(self.release, release_path)
            package_model.write_package(self.strict, strict_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_584_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(release_path), str(strict_path), "--entry-id", "release", "--entry-id", "strict", "--catalog-id", "cli-module584", "--destination", str(catalog_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(catalog_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(catalog_path), "--resource", "entries", "--state", "blocked"]), 0)
            self.assertEqual(invoke([command + "-audit", str(catalog_path), "--package", str(release_path), "--package", str(strict_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)
            self.assertEqual(invoke([command + "-audit-query", str(audit_path), "--passed"]), 0)
            self.assertEqual(invoke([command + "-schema"]), 0)
            self.assertEqual(invoke([command + "-entry-schema"]), 0)
            self.assertEqual(invoke([command + "-capabilities"]), 0)
            self.assertEqual(invoke([command + "-audit-check-schema"]), 0)
            self.assertEqual(invoke([command + "-audit-schema"]), 0)
            self.assertEqual(invoke([command + "-audit-capabilities"]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport/catalog"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("package", release_path), ("package", strict_path), ("entry_id", "release"), ("entry_id", "strict"), ("catalog_id", "http-module584"), ("destination", catalog_path), ("overwrite", "true")])
                self.assertEqual((built["state"], built["entry_count"], built["accepted_count"]), ("mixed", 2, 2))
                verified = get(base + "/verify", [("input", catalog_path)])
                self.assertEqual(verified["content_address"], built["content_address"])
                queried = get(base + "/query", [("input", catalog_path), ("resource", "entries"), ("state", "blocked")])
                self.assertEqual(queried["returned"], 1)
                audited = get(base + "/audit", [("input", catalog_path), ("package", release_path), ("package", strict_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("entries", get(base + "/schema", [] ).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("required", get(base + "/entry-schema", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
