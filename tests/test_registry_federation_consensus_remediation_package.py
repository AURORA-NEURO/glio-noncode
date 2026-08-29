"""Persistence and adapter contracts for remediation handoff packages."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_remediation as remediation_model
from glio_noncode import registry_federation_consensus_remediation_package as package_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode.errors import ValidationError
from glio_noncode.cli import main
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusRemediationPackageTests(DurableCatalogPromotionPackageFixture):
    """Verify exact members, projection replay, and fail-closed loading."""

    def _remediation(self, root: Path):
        ready_package = self.package_for(root / "ready-input", package_id="package-remediation")
        held_package = self.package_for(root / "held-input", package_id="package-remediation", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="package-ready")
        held = registry_model.build_registry((held_package,), registry_id="package-held")
        ready_path, held_path = root / "ready", root / "held"
        registry_model.write_registry(ready, ready_path)
        registry_model.write_registry(held, held_path)
        federation = federation_model.build_federation_from_directories((("primary", ready_path), ("archive", held_path)), federation_id="package-federation")
        return remediation_model.build_remediation(consensus_model.build_consensus(federation, consensus_id="package-consensus"))

    def test_build_package_embeds_independent_audit_and_replays_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = package_model.build_package(self._remediation(Path(temporary)), package_id="handoff-package")
            self.assertEqual(value.package_id, "handoff-package")
            self.assertEqual(value.audit.remediation_address, value.remediation.content_address)
            self.assertEqual(package_model.package_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(package_model.package_json(value))["package_id"], "handoff-package")
            self.assertEqual(package_model.capabilities()["files"], package_model.FILES)

    def test_write_and_load_package_enforces_exact_four_file_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = package_model.build_package(self._remediation(Path(temporary)))
            destination = Path(temporary) / "package"
            package_model.write_package(value, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))
            self.assertEqual(package_model.load_package(destination).to_dict(), value.to_dict())
            with self.assertRaises(ValidationError):
                package_model.write_package(value, destination)

    def test_package_manifest_projection_and_audit_tampering_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = package_model.build_package(self._remediation(Path(temporary)))
            destination = Path(temporary) / "package"
            package_model.write_package(value, destination)
            for name, field, replacement in ((package_model.MANIFEST_NAME, "package_id", "tampered"), (package_model.REMEDIATION_NAME, "steps", []), (package_model.AUDIT_NAME, "accepted", False)):
                package_model.write_package(value, destination, overwrite=True)
                path = destination / name
                document = json.loads(path.read_text(encoding="utf-8"))
                document[field] = replacement
                path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
                with self.assertRaises(ValidationError):
                    package_model.load_package(destination)

    def test_package_schema_contract_covers_manifest_and_nested_receipt(self):
        self.assertEqual(package_model.package_schema()["required"], list(package_model.RegistryFederationConsensusRemediationPackage.FIELDS))
        self.assertEqual(package_model.manifest_schema()["required"][-1], "manifest_address")
        self.assertIn("four-file remediation handoff", package_model.capabilities()["features"])

    def test_cli_materializes_exact_handoff_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            remediation = self._remediation(root)
            remediation_path = root / "remediation.json"
            remediation_path.write_text(remediation_model.remediation_json(remediation), encoding="utf-8")
            destination = root / "handoff"
            output = root / "package.json"
            self.assertEqual(main(["registry-federation-consensus-remediation-package", "--input", str(remediation_path), "--destination", str(destination), "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(package_model.load_package(destination).content_address, json.loads(output.read_text(encoding="utf-8"))["content_address"])
            self.assertEqual(main(["registry-federation-consensus-remediation-package-capabilities"]), 0)


if __name__ == "__main__":
    unittest.main()
