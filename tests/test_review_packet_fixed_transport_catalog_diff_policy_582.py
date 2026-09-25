"""Deep contracts for module-582 catalog-diff policy gates."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_580 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_581 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_582_aud as audit_model
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


def _catalog(entries: tuple[Entry, ...], catalog_id: str = "module582-catalog") -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicyTransportCatalogDiffPolicy582Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200)))
        right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("gamma")))
        self.diff = diff_model.build_diff(left, right, diff_id="module582-diff")

    def test_release_and_strict_profiles_replay_and_audit(self) -> None:
        release = policy_model.release_policy(self.diff, policy_id="module582-release")
        strict = policy_model.strict_policy(self.diff, policy_id="module582-strict")
        self.assertTrue(release.accepted)
        self.assertEqual((release.state, strict.state), ("ready", "blocked"))
        self.assertEqual((release.check_count, release.passed_count), (16, 16))
        self.assertEqual((strict.check_count, strict.failed_count), (16, 7))
        self.assertEqual((audit_model.audit_policy(release, diff=self.diff).passed_count, audit_model.audit_policy(strict, diff=self.diff).passed_count), (16, 16))
        self.assertEqual(policy_model.query_policy(strict, passed=False)["returned"], 7)

    def test_persistence_tamper_and_custom_controls(self) -> None:
        policy = policy_model.build_policy(self.diff, policy_id="module582-custom", maximum_total_changes=0, require_ready=True, allow_unchanged=False)
        self.assertFalse(policy.accepted)
        with tempfile.TemporaryDirectory() as directory:
            policy_path, audit_path = Path(directory) / "policy.json", Path(directory) / "audit.json"
            receipt = audit_model.audit_policy(policy, diff=self.diff)
            policy_model.write_policy(policy, policy_path)
            audit_model.write_audit(receipt, audit_path)
            self.assertEqual(policy_model.load_policy(policy_path).content_address, policy.content_address)
            self.assertEqual(audit_model.load_audit(audit_path).content_address, receipt.content_address)
            with self.assertRaises(ValidationError):
                policy_model.verify_policy(policy.to_dict() | {"state": "ready"})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            diff_path, release_path, audit_path = root / "diff.json", root / "release.json", root / "audit.json"
            diff_model.write_diff(self.diff, diff_path)
            command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_582_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([command, str(diff_path), "--profile", "release", "--policy-id", "cli-module582", "--destination", str(release_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-verify", str(release_path)]), 0)
            self.assertEqual(invoke([command + "-query", str(release_path), "--passed"]), 0)
            self.assertEqual(invoke([command + "-audit", str(release_path), "--diff", str(diff_path), "--destination", str(audit_path), "--format", "summary"]), 0)
            self.assertEqual(invoke([command + "-audit-verify", str(audit_path)]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]]) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in pairs])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("policy_id", "http-module582"), ("destination", release_path), ("overwrite", "true")])
                self.assertEqual((built["state"], built["passed_count"]), ("ready", 16))
                queried = get(base + "/query", [("input", release_path), ("passed", "true")])
                self.assertEqual(queried["returned"], 16)
                audited = get(base + "/audit", [("input", release_path), ("diff", diff_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("checks", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
