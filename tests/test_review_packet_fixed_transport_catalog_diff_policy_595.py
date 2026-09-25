"""Deep contracts for module595 policy-decision transports."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_592 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_593 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_594 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_594_aud as policy_audit_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_595 as package_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_595_aud as audit_model
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


def _catalog(entries: tuple[Entry, ...]) -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": "module595-catalog", "version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyTransport595Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200), _entry("delta", state="blocked")))
        right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("epsilon")))
        self.diff = diff_model.build_diff(left, right, diff_id="module595-diff")
        self.release = policy_model.release_policy(self.diff, policy_id="module595-release")
        self.strict = policy_model.strict_policy(self.diff, policy_id="module595-strict")
        self.release_audit = policy_audit_model.audit_policy(self.release, diff=self.diff)
        self.strict_audit = policy_audit_model.audit_policy(self.strict, diff=self.diff)

    def test_deterministic_nested_lineage_and_blocked_evidence(self) -> None:
        release = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module595-release")
        repeated = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module595-release")
        blocked = package_model.build_package(self.diff, self.strict, self.strict_audit, package_id="module595-strict")
        self.assertEqual(release.package_address, repeated.package_address)
        self.assertNotEqual(release.package_address, blocked.package_address)
        self.assertEqual(tuple(item.relative_path for item in release.manifest.members), package_model.PAYLOAD_NAMES)
        self.assertEqual(package_model.load_package(blocked)[1].failed_count, self.strict.failed_count)
        self.assertEqual((audit_model.audit_package(release).passed_count, audit_model.audit_package(release).check_count), (16, 16))
        self.assertEqual((audit_model.audit_package(blocked).passed_count, audit_model.audit_package(blocked).check_count), (16, 16))
        self.assertEqual(package_model.query_package(blocked, resource="policy")["returned"], 1)
        filtered = package_model.query_package(blocked, resource="policy", text="blocked")
        self.assertEqual((filtered["total"], filtered["matched"], filtered["returned"]), (1, 1, 1))

    def test_persistence_tamper_and_public_boundary(self) -> None:
        package = package_model.build_package(self.diff, self.release, self.release_audit, package_id="module595-persist")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.zip"
            package_model.write_package(package, path)
            self.assertEqual(package_model.verify_package(path).package_address, package.package_address)
            broken = bytearray(package.package_bytes)
            broken[-1] ^= 1
            with self.assertRaises(ValidationError):
                package_model.verify_package(bytes(broken))

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, policy_path, audit_path, package_path, package_audit_path = (root / name for name in ("diff.json", "policy.json", "audit.json", "package.zip", "package-audit.json"))
            diff_model.write_diff(self.diff, diff_path)
            policy_model.write_policy(self.release, policy_path)
            policy_audit_model.write_audit(self.release_audit, audit_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_595_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), str(policy_path), "--audit", str(audit_path), "--package-id", "cli-module595", "--destination", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-verify", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-load", str(package_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(package_path), "--resource", "policy"]), 0)
            self.assertEqual(invoke([command + "-audit", str(package_path), "--destination", str(package_audit_path)]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(package_audit_path)]), 0)
            for suffix in ("-schema", "-manifest-schema", "-check-schema", "-capabilities", "-audit-check-schema", "-audit-schema", "-audit-capabilities"):
                self.assertEqual(invoke([command + suffix]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport"

                def get(path: str, pairs: list[tuple[str, object]] | None = None) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in (pairs or [])])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("diff", diff_path), ("policy", policy_path), ("audit", audit_path), ("package_id", "http-module595"), ("destination", package_path), ("overwrite", "true")])
                self.assertEqual((built["policy_state"], built["audit_accepted"]), ("ready", True))
                loaded = get(base + "/load", [("input", package_path)])
                self.assertEqual(loaded["policy"]["policy_id"], "module595-release")
                queried = get(base + "/query", [("input", package_path), ("resource", "policy")])
                self.assertEqual(queried["returned"], 1)
                audited = get(base + "/audit", [("input", package_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("manifest", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
