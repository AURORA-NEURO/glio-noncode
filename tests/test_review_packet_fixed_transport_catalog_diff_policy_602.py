"""Deep contracts for module602 strict and release gates over module601 diffs."""

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
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_600 as catalog_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_601 as diff_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_602 as policy_model
from glio_noncode import downloaded_data_review_packet_fixed_transport_catalog_diff_policy_602_aud as audit_model
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_599_ct import PACKAGE_PREFIX
from glio_noncode.downloaded_data_review_packet_fixed_transport_catalog_diff_policy_600_ct import CATALOG_PREFIX, ENTRY_PREFIX, Catalog, Entry, address_catalog, address_entry
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError


def _entry(entry_id: str, *, state: str = "ready", package_byte_count: int = 100) -> Entry:
    seed = sum(ord(char) for char in entry_id)
    body = {"entry_id": entry_id, "package_id": "package-" + entry_id, "package_address": PACKAGE_PREFIX + ":" + f"{seed:064x}", "manifest_address": "manifest:" + f"{seed + 10:064x}", "diff_address": "diff:" + f"{seed + 20:064x}", "policy_address": "policy:" + f"{seed + 30:064x}", "audit_address": "audit:" + f"{seed + 40:064x}", "policy_state": state, "policy_accepted": state == "ready", "audit_accepted": True, "package_byte_count": package_byte_count, "member_count": 4, "content_address": ENTRY_PREFIX + ":pending"}
    provisional = Entry(**body)
    return Entry(**(body | {"content_address": address_entry(provisional)}))


def _catalog(entries: tuple[Entry, ...], catalog_id: str = "module602-catalog") -> Catalog:
    entries = tuple(sorted(entries, key=lambda item: item.entry_id))
    ready_count = sum(item.policy_state == "ready" for item in entries)
    blocked_count = sum(item.policy_state == "blocked" for item in entries)
    body = {"catalog_id": catalog_id, "version": catalog_model.VERSION, "boundary": catalog_model.BOUNDARY, "entry_count": len(entries), "accepted_count": sum(item.audit_accepted for item in entries), "ready_count": ready_count, "blocked_count": blocked_count, "state": "empty" if not entries else "ready" if ready_count == len(entries) else "blocked" if blocked_count == len(entries) else "mixed", "entries": entries, "content_address": CATALOG_PREFIX + ":pending"}
    provisional = Catalog(**body)
    return Catalog(**(body | {"content_address": address_catalog(provisional)}))


class FixedTransportCatalogDiffPolicy602Test(unittest.TestCase):
    def setUp(self) -> None:
        alpha = _entry("alpha")
        self.left = _catalog((alpha, _entry("beta", state="blocked", package_byte_count=200), _entry("delta", state="blocked")))
        self.right = _catalog((alpha, _entry("beta", package_byte_count=240), _entry("epsilon")))
        self.diff = diff_model.build_diff(self.left, self.right, diff_id="module602-diff")

    def test_release_accepts_strict_retains_failures_and_audit_is_independent(self) -> None:
        release = policy_model.release_policy(self.diff, policy_id="release-module602")
        strict = policy_model.strict_policy(self.diff, policy_id="strict-module602")
        self.assertTrue(release.accepted)
        self.assertEqual((release.check_count, release.failed_count, release.state), (16, 0, "ready"))
        self.assertFalse(strict.accepted)
        self.assertEqual((strict.check_count, strict.failed_count, strict.state), (16, 8, "blocked"))
        self.assertEqual(policy_model.query_policy(strict, passed=False)["matched"], 8)
        self.assertEqual((audit_model.audit_policy(release, diff=self.diff).check_count, audit_model.audit_policy(release, diff=self.diff).failed_count), (16, 0))
        self.assertEqual((audit_model.audit_policy(strict, diff=self.diff).check_count, audit_model.audit_policy(strict, diff=self.diff).failed_count), (16, 0))

    def test_persistence_tamper_and_custom_budget(self) -> None:
        value = policy_model.build_policy(self.diff, policy_id="custom-module602", maximum_added=1, maximum_removed=1, maximum_changed=1, maximum_total_changes=3, require_change=True)
        self.assertTrue(value.accepted)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            policy_model.write_policy(value, path)
            self.assertEqual(policy_model.load_policy(path).content_address, value.content_address)
            with self.assertRaises(ValidationError):
                policy_model.verify_policy(value.to_dict() | {"content_address": policy_model.POLICY_PREFIX + ":" + "0" * 64})

    def test_cli_http_and_schema_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left_path, right_path, diff_path, release_path, strict_path, audit_path = (root / name for name in ("left.json", "right.json", "diff.json", "release.json", "strict.json", "audit.json"))
            catalog_model.write_catalog(self.left, left_path)
            catalog_model.write_catalog(self.right, right_path)
            diff_command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_DIFF_601_COMMAND
            policy_command = _legacy_cli._REVIEW_PACKET_TRANSPORT_CATALOG_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_TRANSPORT_CATALOG_DIFF_POLICY_602_COMMAND

            def invoke(arguments: list[str]) -> int:
                with contextlib.redirect_stdout(io.StringIO()):
                    return main(arguments)

            self.assertEqual(invoke([diff_command, str(left_path), str(right_path), "--diff-id", "cli-module602", "--destination", str(diff_path)]), 0)
            self.assertEqual(invoke([policy_command, str(diff_path), "--profile", "release", "--destination", str(release_path)]), 0)
            self.assertEqual(invoke([policy_command, str(diff_path), "--profile", "strict", "--destination", str(strict_path)]), 2)
            self.assertEqual(invoke([policy_command + "-verify", str(release_path)]), 0)
            self.assertEqual(invoke([policy_command + "-query", str(strict_path), "--failed"]), 0)
            self.assertEqual(invoke([policy_command + "-audit", str(release_path), "--diff", str(diff_path), "--destination", str(audit_path)]), 0)
            self.assertEqual(invoke([policy_command + "-audit-verify", str(audit_path)]), 0)
            for suffix in ("-schema", "-check-schema", "-capabilities", "-audit-check-schema", "-audit-schema", "-audit-capabilities"):
                self.assertEqual(invoke([policy_command + suffix]), 0)

            server = create_server("127.0.0.1", 0, root)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                policy_base = "/v1/downloaded-data/review-packet/diff/policy/release-certificate/bundle/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/package/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"
                base = policy_base + "/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy/transport/catalog/diff/policy"

                def get(path: str, pairs: list[tuple[str, object]] | None = None) -> dict[str, object]:
                    query = urlencode([(key, str(value)) for key, value in (pairs or [])])
                    with urlopen(f"http://127.0.0.1:{server.server_port}{path}?{query}", timeout=20) as response:
                        return json.loads(response.read())

                built = get(base, [("input", diff_path), ("profile", "release"), ("destination", release_path), ("overwrite", "true")])
                self.assertEqual((built["state"], built["failed_count"]), ("ready", 0))
                queried = get(base + "/query", [("input", strict_path), ("passed", "false")])
                self.assertEqual(queried["matched"], 8)
                audited = get(base + "/audit", [("input", release_path), ("diff", diff_path)])
                self.assertEqual((audited["check_count"], audited["failed_count"], audited["accepted"]), (16, 0, True))
                self.assertIn("checks", get(base + "/schema", []).get("properties", {}))
                self.assertIn("operations", get(base + "/capabilities", []))
                self.assertIn("check_ids", get(base + "/audit/capabilities", []))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
