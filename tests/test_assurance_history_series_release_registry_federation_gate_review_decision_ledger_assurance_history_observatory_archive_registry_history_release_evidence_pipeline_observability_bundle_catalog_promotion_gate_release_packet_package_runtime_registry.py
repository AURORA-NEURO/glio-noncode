"""Deep contracts for package runtime execution and package registries."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_runtime as runtime
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class PublicBoundaryMixin:
    def assert_public(self, value) -> None:
        document = json.dumps(value, default=str).lower()
        self.assertNotIn('"agent"', document)
        self.assertNotIn('"agent_id"', document)
        self.assertNotIn('"assistant"', document)
        self.assertNotIn('"language"', document)


class CatalogPromotionPackageRuntimeTests(PublicBoundaryMixin, DurableCatalogPromotionPackageFixture):
    def test_ready_runtime_composes_persisted_package_and_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left, _, baseline, _ = self.documents_for(root / "inputs")
            value = runtime.run_package_runtime(
                (("baseline", str(baseline)),),
                (("baseline", str(baseline)),),
                runtime_id="runtime-ready",
                package_id="package-ready",
                resource="files",
                limit=10,
                destination=root / "package",
            )
            self.assertEqual(left.catalog_id, "catalog:left")
            self.assertEqual(value.runtime_id, "runtime-ready")
            self.assertEqual(value.package.package_id, "package-ready")
            self.assertEqual((value.package.packet.state, value.package.packet.decision), ("ready", "promote"))
            self.assertTrue(value.package.packet.release_ready)
            self.assertTrue(value.persisted)
            self.assertTrue(value.reload_verified)
            self.assertEqual(value.files, registry_model_files())
            self.assertEqual((value.audit.state, value.audit.passed_count, value.audit.failed_count), ("complete", 12, 0))
            self.assertEqual((value.query.query.resource, value.query.total_count, value.query.returned_count), ("files", 4, 4))
            self.assertEqual(runtime.verify_runtime(value).content_address, value.content_address)
            self.assertEqual(runtime.runtime_from_mapping(json.loads(runtime.runtime_json(value))).to_dict(), value.to_dict())
            self.assertIn("Catalog Promotion Package Runtime", runtime.render_runtime_markdown(value))
            self.assertIn("runtime_id,package_id,state,decision", runtime.runtime_csv(value))
            self.assert_public(value.to_dict())

    def test_held_runtime_preserves_actions_and_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, baseline, candidate = self.documents_for(root / "inputs")
            value = runtime.run_package_runtime(
                (("baseline", str(baseline)),),
                (("candidate", str(candidate)),),
                runtime_id="runtime-held",
                package_id="package-held",
                resource="actions",
                text="hold",
                limit=10,
                max_added=0,
            )
            self.assertEqual((value.package.packet.state, value.package.packet.decision), ("held", "hold"))
            self.assertTrue(value.package.packet.accepted)
            self.assertFalse(value.package.packet.release_ready)
            self.assertEqual(value.query.query.text, "hold")
            self.assertGreaterEqual(value.query.total_count, 1)
            self.assertEqual(value.query.returned_count, value.query.total_count)
            self.assertFalse(value.persisted)
            self.assertFalse(value.reload_verified)
            self.assertEqual(value.files, ())
            self.assert_public(value.summary())

    def test_runtime_request_is_strict_bounded_and_path_free(self):
        request = runtime.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest(
            runtime_id="request-test",
            left_labels=("baseline", "secondary"),
            right_labels=("candidate",),
            package_id="package-test",
            resource="summary",
            limit=25,
        )
        self.assertEqual(runtime.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest.from_mapping(request.to_dict()).to_dict(), request.to_dict())
        self.assert_public(request.to_dict())
        with self.assertRaises(ValidationError):
            runtime.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest(runtime_id="bad label")
        with self.assertRaises(ValidationError):
            runtime.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest(left_labels=("same", "same"))
        with self.assertRaises(ValidationError):
            runtime.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageRuntimeRequest(limit=0)
        with self.assertRaises(ValidationError):
            runtime.run_package_runtime((("bad/label", "C:\\private\\input"),), (("candidate", "C:\\private\\input"),))

    def test_runtime_schema_capabilities_and_formats_are_public(self):
        self.assertIn("request", runtime.runtime_schema()["properties"])
        self.assertIn("runtime", runtime.capabilities()["schemas"])
        self.assertEqual(tuple(runtime.capabilities()["files"]), registry_model_files())
        self.assert_public(runtime.request_schema())
        self.assert_public(runtime.runtime_schema())
        self.assert_public(runtime.capabilities())

    def test_runtime_cli_persists_and_emits_path_free_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, baseline, _ = self.documents_for(root / "inputs")
            output = root / "runtime.json"
            command = self.RELEASE_PACKET_COMMAND + "-package-runtime"
            self.assertEqual(main([command, "--left-label", "baseline", "--left-directory", str(baseline), "--right-label", "baseline", "--right-directory", str(baseline), "--resource", "files", "--destination", str(root / "package"), "--format", "summary", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual((payload["decision"], payload["package_audit_passed_count"], payload["query_returned_count"]), ("promote", 12, 4))
            self.assert_public(payload)

    def test_registry_cli_indexes_queries_audits_and_diffs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready = self.package_for(root / "ready-input", package_id="package-ready")
            held = self.package_for(root / "held-input", held=True, package_id="package")
            package_model().write_package(ready, root / "ready-package")
            package_model().write_package(held, root / "held-package")
            base_command = self.RELEASE_PACKET_COMMAND + "-package"
            registry_command = base_command + "-registry"
            ready_registry = root / "ready-registry"
            held_registry = root / "held-registry"
            self.assertEqual(main([registry_command, "--package-directory", str(root / "ready-package"), "--registry-id", "registry-ready", "--destination", str(ready_registry), "--format", "summary"]), 0)
            self.assertEqual(main([registry_command, "--package-directory", str(root / "held-package"), "--registry-id", "registry-held", "--destination", str(held_registry), "--format", "summary"]), 0)
            query_output = root / "query.json"
            self.assertEqual(main([registry_command + "-query", str(ready_registry), "--resource", "entries", "--format", "json", "--output", str(query_output)]), 0)
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["returned_count"], 1)
            audit_output = root / "audit.json"
            self.assertEqual(main([registry_command + "-audit", str(ready_registry), "--format", "json", "--output", str(audit_output)]), 0)
            self.assertEqual(json.loads(audit_output.read_text(encoding="utf-8"))["passed_count"], 9)
            diff_output = root / "diff.json"
            diff_command = registry_command + "-diff"
            self.assertEqual(main([diff_command, str(ready_registry), str(held_registry), "--format", "json", "--output", str(diff_output)]), 0)
            diff_payload = json.loads(diff_output.read_text(encoding="utf-8"))
            self.assertEqual(diff_payload["state"], "changed")
            diff_audit_output = root / "diff-audit.json"
            self.assertEqual(main([diff_command + "-audit", str(diff_output), "--format", "json", "--output", str(diff_audit_output)]), 0)
            self.assertEqual(json.loads(diff_audit_output.read_text(encoding="utf-8"))["passed_count"], 11)


class CatalogPromotionPackageRegistryTests(PublicBoundaryMixin, DurableCatalogPromotionPackageFixture):
    def _packages(self, root: Path):
        ready = self.package_for(root / "ready-input", package_id="package-ready")
        held = self.package_for(root / "held-input", held=True, package_id="package-held")
        ready_directory = root / "ready-package"
        held_directory = root / "held-package"
        package_model().write_package(ready, ready_directory)
        package_model().write_package(held, held_directory)
        return ready, held, ready_directory, held_directory

    def test_registry_indexes_ready_and_held_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, held, ready_directory, held_directory = self._packages(root)
            value = registry.build_registry_from_directories((ready_directory, held_directory), registry_id="registry-test")
            self.assertEqual(value.registry_id, "registry-test")
            self.assertEqual(value.entry_count, 2)
            self.assertEqual((value.accepted_count, value.release_ready_count), (2, 1))
            self.assertEqual((value.held_count, value.blocked_count), (1, 0))
            self.assertEqual((value.artifact_count, value.file_count), (8, 10))
            self.assertEqual(tuple(entry.package_id for entry in value.entries), (ready.package_id, held.package_id))
            self.assertEqual(tuple(entry.package_address for entry in value.entries), (ready.content_address, held.content_address))
            self.assertEqual(registry.address_registry(value), value.content_address)
            self.assertEqual(registry.registry_from_mapping(json.loads(registry.registry_json(value))).to_dict(), value.to_dict())
            self.assertEqual(registry.load_registry(registry.write_registry(value, root / "registry")).to_dict(), value.to_dict())
            self.assertEqual(tuple(item.name for item in (root / "registry").iterdir()), registry.FILES)
            self.assert_public(value.to_dict())

    def test_registry_query_resources_filter_and_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._packages(root)
            value = registry.build_registry_from_directories((root / "ready-package", root / "held-package"))
            expected_counts = {"summary": 1, "entries": 2, "accepted": 2, "ready": 1, "held": 1, "addresses": 2}
            for resource, expected in expected_counts.items():
                result = registry.query_registry(value, resource=resource, limit=registry.MAX_LIMIT)
                self.assertEqual(result.total_count, expected)
                self.assertEqual(result.returned_count, expected)
                self.assertEqual(registry.query_result_from_mapping(json.loads(registry.query_json(result))).to_dict(), result.to_dict())
                self.assertIn("Catalog Promotion Package Registry Query", registry.render_query_markdown(result))
                self.assertTrue(registry.query_csv(result).splitlines()[0])
            held = registry.query_registry(value, resource="entries", state="held")
            self.assertEqual(tuple(record["package_id"] for record in held.records), ("package-held",))
            promote = registry.query_registry(value, resource="entries", decision="promote")
            self.assertEqual(tuple(record["package_id"] for record in promote.records), ("package-ready",))
            text = registry.query_registry(value, resource="entries", text="package-held")
            self.assertEqual(text.returned_count, 1)
            page = registry.query_registry(value, resource="entries", offset=1, limit=1)
            self.assertEqual((page.total_count, page.returned_count), (2, 1))
            self.assert_public(page.to_dict())

    def test_registry_audit_has_independent_nine_check_assurance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._packages(root)
            value = registry.build_registry_from_directories((root / "ready-package", root / "held-package"))
            assurance = registry.audit_registry(value)
            self.assertEqual((assurance.state, assurance.accepted), ("complete", True))
            self.assertEqual((assurance.check_count, assurance.passed_count, assurance.failed_count), (9, 9, 0))
            self.assertEqual(tuple(check.check_id for check in assurance.checks), registry.CHECK_IDS)
            self.assertEqual(registry.verify_audit(registry.audit_from_mapping(json.loads(registry.audit_json(assurance)))).to_dict(), assurance.to_dict())
            self.assertIn("Catalog Promotion Package Registry Audit", registry.render_audit_markdown(assurance))
            self.assert_public(assurance.to_dict())

    def test_registry_write_contract_rejects_tampering_and_extra_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._packages(root)
            value = registry.build_registry_from_directories((root / "ready-package", root / "held-package"))
            destination = root / "registry"
            registry.write_registry(value, destination)
            with self.assertRaises(ValidationError):
                registry.write_registry(value, destination)
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                registry.load_registry(destination)
            (destination / "extra.json").unlink()
            registry.write_registry(value, destination, overwrite=True)
            registry_raw = destination / registry.REGISTRY_NAME
            registry_raw.write_bytes(registry_raw.read_bytes().replace(b"package-ready", b"package-altered", 1))
            with self.assertRaises(ValidationError):
                registry.load_registry(destination)

    def test_registry_rejects_duplicate_identity_and_schema_is_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, _, ready_directory, _ = self._packages(root)
            with self.assertRaises(ValidationError):
                registry.build_registry((ready, ready), registry_id="duplicate")
            for schema in (registry.manifest_schema(), registry.entry_schema(), registry.registry_schema(), registry.query_schema(), registry.query_result_schema(), registry.audit_check_schema(), registry.audit_schema(), registry.capabilities()):
                self.assert_public(schema)
            self.assertIn("entries", registry.registry_schema()["properties"])
            self.assertIn("release_ready", registry.entry_schema()["properties"])
            self.assertIn("audit", registry.capabilities()["schemas"])


def package_model():
    from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as model

    return model


def registry_model_files():
    return package_model().FILES


if __name__ == "__main__":
    unittest.main()
