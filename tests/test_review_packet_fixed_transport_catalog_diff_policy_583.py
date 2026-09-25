"""Deep contracts for module-583 fixed policy decision transports."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import _legacy_cli
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_581 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582_aud as policy_audit_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_583 as package_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_583_aud as audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_579_ct import PACKAGE_PREFIX
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580_ct import CATALOG_PREFIX, ENTRY_PREFIX, Catalog, Entry, address_catalog, address_entry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _entry(entry_id: str, *, state: str = "ready", package_byte_count: int = 100) -> Entry:
    seed = ord(entry_id[0]) - 96
    body = {"entry_id": entry_id, "package_id": "package-" + entry_id, "package_address": PACKAGE_PREFIX + ":" + f"{seed:064x}", "manifest_address": "manifest:" + f"{seed + 10:064x}", "diff_address": "diff:" + f"{seed + 20:064x}", "policy_address": "policy:" + f"{seed + 30:064x}", "audit_address": "audit:" + f"{seed + 40:064x}", "policy_state": state, "policy_accepted": state == "ready", "audit_accepted": True, "package_byte_count": package_byte_count, "member_count": 4, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = Entry(**body)
    return Entry(**(body | {"content_address": address_entry(provisional)}))


def _catalog(entries: tuple[Entry, ...], catalog_id: str = "module583-catalog") -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyTransport583Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200)))
        right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("gamma")))
        self.diff = diff_model.build_diff(left, right, diff_id="module583-diff")
        self.release = policy_model.release_policy(self.diff, policy_id="module583-release")
        self.strict = policy_model.strict_policy(self.diff, policy_id="module583-strict")
        self.release_audit = policy_audit_model.audit_policy(self.release, diff=self.diff)
        self.strict_audit = policy_audit_model.audit_policy(self.strict, diff=self.diff)

    def test_deterministic_members_lineage_and_blocked_evidence(self) -> None:
        release = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module583-release")
        repeated = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module583-release")
        blocked = package_model.build_package(self.diff, self.strict, self.strict_audit, package_id="module583-strict")
        self.assertEqual(release.package_bytes, repeated.package_bytes)
        self.assertEqual(release.package_address, repeated.package_address)
        self.assertEqual(tuple(item.relative_path for item in release.manifest.members), ("catalog-diff.json", "policy.json", "policy-audit.json", "review.md"))
        self.assertEqual((release.manifest.policy_state, release.manifest.policy_accepted, release.manifest.audit_accepted), ("ready", True, True))
        self.assertEqual((blocked.manifest.policy_state, blocked.manifest.policy_accepted, blocked.manifest.audit_accepted), ("blocked", False, True))
        self.assertEqual((audit_model.audit_package(release).passed_count, audit_model.audit_package(release).check_count), (16, 16))
        self.assertEqual((audit_model.audit_package(blocked).passed_count, audit_model.audit_package(blocked).check_count), (16, 16))
        with zipfile.ZipFile(io.BytesIO(release.package_bytes)) as archive:
            self.assertEqual(tuple(archive.namelist()), package_model.FILE_NAMES)
            self.assertTrue(all(info.compress_type == zipfile.ZIP_STORED for info in archive.infolist()))
        self.assertNotIn("agent", package_model.package_json(release).lower())
        self.assertNotIn("model", package_model.package_json(release).lower())

    def test_persistence_roundtrip_and_zip_tamper_rejection(self) -> None:
        package = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module583-persist")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transport.zip"
            package_model.write_package(package, path)
            loaded = package_model.verify_package(path)
            diff, policy, audit, review = package_model.load_package(path)
            self.assertEqual(loaded.package_address, package.package_address)
            self.assertEqual((diff.content_address, policy.content_address, audit.content_address), (self.diff.content_address, self.release.content_address, self.release_audit.content_address))
            self.assertIn("Module583 Policy Decision Transport", review)
            with self.assertRaises(ValidationError):
                package_model.verify_package(package.package_bytes[:-1] + bytes([package.package_bytes[-1] ^ 1]))

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path, package_path, package_audit_path = (root / name for name in ("diff.json", "policy.json", "audit.json", "transport.zip", "transport-audit.json"))
            diff_model.write_diff(self.diff, diff_path)
            policy_model.write_policy(self.release, policy_path)
            policy_audit_model.write_audit(self.release_audit, audit_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_583_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), str(policy_path), "--audit", str(audit_path), "--package-id", "cli-module583", "--destination", str(package_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-load", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(package_path), "--resource", "members"]), 0)
            self.assertEqual(invoke([command + "-audit", str(package_path), "--destination", str(package_audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(package_audit_path)]), 0)
            self.assertEqual(invoke([command + "-audit-query", str(package_audit_path), "--passed"]), 0)
            self.assertEqual(invoke([command + "-schema"]), 0)
            self.assertEqual(invoke([command + "-manifest-schema"]), 0)
            self.assertEqual(invoke([command + "-capabilities"]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("diff", diff_path), ("policy", policy_path), ("audit", audit_path), ("package_id", "http-module583"), ("destination", package_path), ("overwrite", "true")])
                self.assertEqual((built["policy_state"], built["member_count"], built["audit_accepted"]), ("ready", 4, True))
                verified = get(base + "/verify", [("input", package_path)])
                self.assertEqual(verified["package_address"], built["package_address"])
                queried = get(base + "/query", [("input", package_path), ("resource", "members")])
                self.assertEqual(queried["returned"], 4)
                audited = get(base + "/audit", [("input", package_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("manifest", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("required", get(base + "/manifest-schema", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
