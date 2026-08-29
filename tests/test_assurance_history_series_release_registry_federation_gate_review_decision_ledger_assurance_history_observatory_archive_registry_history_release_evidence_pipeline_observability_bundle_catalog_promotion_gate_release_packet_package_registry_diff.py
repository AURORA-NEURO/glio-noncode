"""Deep contracts for package-registry revision diffs and assurance."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_diff as registry_diff
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class PackageRegistryDiffTests(DurableCatalogPromotionPackageFixture):
    """Exercise registry evolution as a deterministic public contract."""

    def _registries(self, root: Path):
        ready = self.package_for(root / "ready-input", package_id="package-ready")
        held = self.package_for(root / "held-input", held=True, package_id="package-held")
        held_same = self.package_for(root / "held-same-input", held=True, package_id="package-ready")
        ready_directory = root / "ready-package"
        held_directory = root / "held-package"
        package_model.write_package(ready, ready_directory)
        package_model.write_package(held, held_directory)
        left = registry.build_registry((ready,), registry_id="registry-left")
        right = registry.build_registry((held,), registry_id="registry-right")
        changed = registry.build_registry((held_same,), registry_id="registry-changed")
        expanded = registry.build_registry((ready, held), registry_id="registry-expanded")
        return ready, held, changed, left, right, expanded

    def _assert_public(self, value) -> None:
        forbidden = {"agent", "agent_id", "assistant", "language"}

        def walk(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    self.assertNotIn(key, forbidden)
                    walk(child)
            elif isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)

        walk(value)

    def test_changed_receipts_report_semantic_field_delta(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, changed, left, _, _ = self._registries(Path(temporary))
            value = registry_diff.build_diff(left, changed, diff_id="registry-diff-changed")
            self.assertEqual(value.state, "changed")
            self.assertEqual((value.left_entry_count, value.right_entry_count, value.entry_count_delta), (1, 1, 0))
            self.assertEqual((value.added_count, value.removed_count, value.changed_count), (0, 0, 1))
            self.assertEqual(value.changed_package_ids, ("package-ready",))
            self.assertEqual(value.changed_fields, ("action_count", "decision", "failed_count", "passed_count", "release_ready", "state"))
            self.assertEqual(tuple(item.change for item in value.items), ("changed",))
            self.assertTrue(all(item.content_address.startswith(registry_diff.ITEM_PREFIX + ":") for item in value.items))
            self.assertEqual(registry_diff.address_diff(value), value.content_address)
            self._assert_public(value.to_dict())

    def test_expanded_and_contracted_registry_revisions_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, left, _, expanded = self._registries(Path(temporary))
            grown = registry_diff.build_diff(left, expanded, diff_id="registry-diff-expanded")
            shrunk = registry_diff.build_diff(expanded, left, diff_id="registry-diff-contracted")
            self.assertEqual((grown.state, grown.entry_count_delta, grown.added_package_ids, grown.removed_package_ids), ("expanded", 1, ("package-held",), ()))
            self.assertEqual((shrunk.state, shrunk.entry_count_delta, shrunk.added_package_ids, shrunk.removed_package_ids), ("contracted", -1, (), ("package-held",)))
            self.assertEqual((grown.changed_count, shrunk.changed_count), (0, 0))
            self.assertEqual(tuple(item.change for item in grown.items), ("added",))
            self.assertEqual(tuple(item.change for item in shrunk.items), ("removed",))

    def test_unchanged_revision_has_no_items_and_replays_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, left, _, _ = self._registries(Path(temporary))
            value = registry_diff.build_diff(left, left, diff_id="registry-diff-unchanged")
            self.assertEqual(value.state, "unchanged")
            self.assertEqual(value.items, ())
            self.assertEqual(value.changed_fields, ())
            self.assertEqual(registry_diff.diff_from_mapping(json.loads(registry_diff.diff_json(value))).to_dict(), value.to_dict())
            self.assertIn("No package receipt changed", registry_diff.render_diff_markdown(value))
            self.assertIn("package_id", registry_diff.diff_csv(value).splitlines()[0])

    def test_diff_serialization_is_canonical_and_path_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, changed, left, _, _ = self._registries(Path(temporary))
            value = registry_diff.build_diff(left, changed, diff_id="registry-diff-serialized")
            raw = registry_diff.diff_json(value)
            self.assertEqual(raw, registry_diff.diff_json(registry_diff.diff_from_mapping(json.loads(raw))))
            self.assertEqual(raw, json.dumps(json.loads(raw), separators=(",", ":"), sort_keys=True))
            self.assertEqual(registry_diff.diff_from_mapping(json.loads(raw)).content_address, value.content_address)
            self.assertEqual(registry_diff.diff_csv(value).splitlines()[0], "ordinal,package_id,change,left_entry_address,right_entry_address,changed_fields,detail,content_address")
            self.assertIn("Catalog Promotion Package Registry Diff", registry_diff.render_diff_markdown(value))
            self._assert_public(json.loads(raw))

    def test_independent_audit_has_eleven_conservation_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, _, left, right, _ = self._registries(Path(temporary))
            value = registry_diff.build_diff(left, right, diff_id="registry-diff-audited")
            assurance = registry_diff.audit_diff(value)
            self.assertEqual((assurance.state, assurance.accepted), ("complete", True))
            self.assertEqual((assurance.check_count, assurance.passed_count, assurance.failed_count), (11, 11, 0))
            self.assertEqual(tuple(check.check_id for check in assurance.checks), registry_diff.CHECK_IDS)
            self.assertEqual(registry_diff.address_audit(assurance), assurance.content_address)
            self.assertEqual(registry_diff.verify_audit(assurance).to_dict(), assurance.to_dict())
            self.assertEqual(registry_diff.audit_from_mapping(json.loads(registry_diff.audit_json(assurance))).to_dict(), assurance.to_dict())
            self.assertIn("11/11", registry_diff.render_audit_markdown(assurance))
            self._assert_public(assurance.to_dict())

    def test_diff_mapping_rejects_unknown_fields_and_inconsistent_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, changed, left, _, _ = self._registries(Path(temporary))
            value = registry_diff.build_diff(left, changed, diff_id="registry-diff-invalid")
            unknown = value.to_dict()
            unknown["unexpected"] = True
            with self.assertRaises(ValidationError):
                registry_diff.diff_from_mapping(unknown)
            inconsistent = value.to_dict()
            inconsistent["entry_count_delta"] = 99
            with self.assertRaises(ValidationError):
                registry_diff.diff_from_mapping(inconsistent)
            audit_mapping = registry_diff.audit_diff(value).to_dict()
            audit_mapping["checks"][0]["passed"] = not audit_mapping["checks"][0]["passed"]
            with self.assertRaises(ValidationError):
                registry_diff.audit_from_mapping(audit_mapping)

    def test_schema_capabilities_describe_every_registry_diff_surface(self):
        schemas = (registry_diff.item_schema(), registry_diff.diff_schema(), registry_diff.audit_check_schema(), registry_diff.audit_schema(), registry_diff.capabilities())
        for value in schemas:
            self._assert_public(value)
        self.assertEqual(tuple(registry_diff.capabilities()["schemas"]), ("item", "diff", "audit-check", "audit"))
        self.assertEqual(tuple(registry_diff.capabilities()["changes"]), registry_diff.CHANGES)
        self.assertEqual(tuple(registry_diff.capabilities()["compare_fields"]), registry_diff.COMPARE_FIELDS)
        self.assertEqual(tuple(registry_diff.capabilities()["check_ids"]), registry_diff.CHECK_IDS)
        self.assertEqual(registry_diff.diff_schema()["properties"]["items"]["maxItems"], registry_diff.MAX_ITEMS)
        self.assertEqual(registry_diff.audit_schema()["properties"]["check_count"]["const"], len(registry_diff.CHECK_IDS))


if __name__ == "__main__":
    unittest.main()
