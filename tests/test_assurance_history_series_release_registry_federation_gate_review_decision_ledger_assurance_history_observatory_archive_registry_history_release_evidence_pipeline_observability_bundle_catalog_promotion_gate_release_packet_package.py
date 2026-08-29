"""Deep contracts for durable catalog promotion packages and package diffs."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as catalog_diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report as catalog_report
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as promotion_gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as promotion_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as release_packet
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package as package_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_audit as package_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_diff as package_diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_diff_audit as package_diff_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_diff_query as package_diff_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_query as package_query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report import RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture


class DurableCatalogPromotionPackageFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture):
    """Build package inputs from the same verified bundle-directory fixture as the catalog product."""

    def setUp(self) -> None:
        super().setUp()
        self.package_command = self.RELEASE_PACKET_COMMAND + "-package"

    def package_for(self, root: Path, *, held: bool = False, package_id: str = "package-test"):
        left, right, _, _ = self.documents_for(root)
        change = catalog_diff.build_diff(left, right, diff_id="catalog-diff:package")
        report = catalog_report.build_report(right, report_id="catalog-report:package")
        policy = promotion_gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=0) if held else None
        gate = promotion_gate.build_promotion_gate(change, report, policy=policy, gate_id="gate:package-held" if held else "gate:package-ready")
        gate_assurance = promotion_audit.audit_gate(gate)
        packet = release_packet.build_release_packet(gate, gate_assurance, packet_id="packet-package-held" if held else "packet-package-ready")
        return package_model.build_package(gate, gate_assurance, packet, package_id=package_id.replace(":", "-"))

    def assert_public_projection(self, value) -> None:
        forbidden_keys = {"agent", "agent_id", "assistant", "language"}

        def public_strings(current, *, key=None):
            if isinstance(current, dict):
                for child_key, child_value in current.items():
                    if child_key == "$schema":
                        continue
                    yield from public_strings(child_value, key=child_key)
            elif isinstance(current, (list, tuple)):
                for child_value in current:
                    yield from public_strings(child_value, key=key)
            elif isinstance(current, str) and key not in forbidden_keys:
                yield current.lower()

        if isinstance(value, dict):
            self.assertTrue(forbidden_keys.isdisjoint(value))
        document = "\n".join(public_strings(value))
        self.assertNotIn("/", document)
        self.assertNotIn("\\", document)


class CatalogPromotionPackageBuildTests(DurableCatalogPromotionPackageFixture):
    def test_build_conserves_gate_audit_packet_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            self.assertEqual(value.package_id, "package-test")
            self.assertEqual(value.packet.state, "ready")
            self.assertEqual(value.packet.decision, "promote")
            self.assertTrue(value.packet.accepted)
            self.assertTrue(value.packet.release_ready)
            self.assertEqual((value.artifact_count, value.file_count), (4, 5))
            self.assertEqual(value.files, package_model.FILES)
            self.assertEqual(value.manifest["files"], package_model.ARTIFACT_FILES)
            self.assertEqual(value.manifest["artifact_count"], package_model.MAX_ARTIFACTS)
            self.assertEqual(value.manifest_address, value.manifest["manifest_address"])
            self.assertEqual(value.actions_address, value.actions_document["content_address"])
            self.assertEqual(value.action_count, 0)
            self.assertEqual(value.check_count, 27)
            self.assertEqual((value.passed_count, value.failed_count), (27, 0))
            self.assertEqual(package_model.address_package(value), value.content_address)
            self.assertEqual(package_model.package_from_mapping(json.loads(package_model.package_json(value))).to_dict(), value.to_dict())
            self.assertIn("Catalog Promotion Package", package_model.render_package_markdown(value))
            self.assertIn("name,bytes,byte_address", package_model.package_csv(value))
            self.assert_public_projection(value.to_dict())
            for projection in (package_model.manifest_schema(), package_model.actions_schema(), package_model.package_schema(), package_model.capabilities()):
                self.assert_public_projection({key: item for key, item in projection.items() if key != "$schema"})

    def test_canonical_package_bytes_are_stable_and_members_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            payload = package_model.package_bytes(value)
            self.assertEqual(tuple(sorted(payload)), tuple(sorted(package_model.FILES)))
            self.assertEqual(payload["manifest.json"].decode("utf-8"), package_model.package_manifest_json(value))
            self.assertTrue(all(raw == package_model.canonical_bytes(json.loads(raw.decode("utf-8"))) for raw in payload.values()))
            self.assertEqual(payload, package_model.package_bytes(package_model.package_from_mapping(json.loads(package_model.package_json(value)))))
            self.assertEqual(len(value.manifest["artifacts"]), package_model.MAX_ARTIFACTS)
            self.assertEqual(tuple(item["name"] for item in value.manifest["artifacts"]), package_model.ARTIFACT_FILES)
            self.assertEqual(tuple(item["name"] for item in value.manifest["artifacts"]), tuple(sorted(item["name"] for item in value.manifest["artifacts"])))
            self.assertTrue(all(item["bytes"] == len(payload[item["name"]]) for item in value.manifest["artifacts"]))
            self.assertTrue(all(item["byte_address"].startswith(package_model.PACKAGE_PREFIX + "-artifact:") for item in value.manifest["artifacts"]))

    def test_write_load_verify_and_overwrite_have_safe_directory_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            destination = Path(temporary) / "persisted-package"
            self.assertEqual(package_model.write_package(value, destination), destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))
            loaded = package_model.load_package(destination)
            self.assertEqual(loaded.to_dict(), value.to_dict())
            self.assertEqual(package_model.verify_package(destination).content_address, value.content_address)
            self.assertRaises(ValidationError, package_model.write_package, value, destination)
            self.assertEqual(package_model.write_package(value, destination, overwrite=True), destination)
            self.assertEqual(package_model.load_package(destination).to_dict(), value.to_dict())
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            self.assertRaises(ValidationError, package_model.load_package, destination)

    def test_package_reload_rejects_missing_members_and_byte_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            destination = Path(temporary) / "persisted-package"
            package_model.write_package(value, destination)
            (destination / "actions.json").unlink()
            self.assertRaises(ValidationError, package_model.load_package, destination)
            destination = Path(temporary) / "tampered-package"
            package_model.write_package(value, destination)
            actions = destination / "actions.json"
            actions.write_bytes(actions.read_bytes().replace(b"{", b"{ ", 1))
            self.assertRaises(ValidationError, package_model.load_package, destination)
            package_model.write_package(value, destination, overwrite=True)
            manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
            manifest["package_id"] = "tampered"
            manifest["manifest_address"] = value.manifest_address
            (destination / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertRaises(ValidationError, package_model.load_package, destination)


class CatalogPromotionPackageQueryTests(DurableCatalogPromotionPackageFixture):
    def test_every_package_query_resource_is_bounded_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            for resource in package_query.RESOURCES:
                result = package_query.query_package(value, resource=resource, limit=package_query.MAX_LIMIT)
                self.assertEqual(result.package_address, value.content_address)
                self.assertLessEqual(result.returned_count, result.total_count)
                self.assertLessEqual(result.returned_count, package_query.MAX_QUERY_ITEMS)
                self.assertEqual(package_query.query_result_from_mapping(json.loads(package_query.query_json(result))).to_dict(), result.to_dict())
                self.assertIn("Resource", package_query.render_query_markdown(result))
                self.assertTrue(package_query.query_csv(result).splitlines()[0])
            files = package_query.query_package(value, resource="files")
            self.assertEqual((files.total_count, files.returned_count), (4, 4))
            self.assertEqual(tuple(item["name"] for item in files.records), package_model.ARTIFACT_FILES)
            actions = package_query.query_package(value, resource="actions")
            self.assertEqual((actions.total_count, actions.returned_count), (0, 0))

    def test_package_query_filters_source_severity_check_and_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary), held=True)
            all_actions = package_query.query_package(value, resource="actions", limit=package_query.MAX_LIMIT)
            self.assertEqual((all_actions.total_count, all_actions.returned_count), (1, 1))
            self.assertEqual(all_actions.records[0]["source"], "gate")
            self.assertEqual(package_query.query_package(value, resource="actions", source="audit").total_count, 0)
            self.assertEqual(package_query.query_package(value, resource="actions", severity="hold").total_count, 1)
            check_id = all_actions.records[0]["check_id"]
            self.assertEqual(package_query.query_package(value, resource="actions", check_id=check_id).total_count, 1)
            self.assertEqual(package_query.query_package(value, resource="actions", check_id="missing").total_count, 0)
            self.assertEqual(package_query.query_package(value, resource="actions", text="hold").total_count, 1)
            first = package_query.query_package(value, resource="actions", offset=0, limit=1)
            second = package_query.query_package(value, resource="actions", offset=1, limit=1)
            self.assertEqual(first.returned_count, 1)
            self.assertEqual(second.returned_count, 0)
            self.assertRaises(ValidationError, package_query.query_package, value, resource="unknown")
            self.assertRaises(ValidationError, package_query.query_package, value, offset=-1)
            self.assert_public_projection(package_query.capabilities())

    def test_query_from_raw_mapping_has_the_same_content_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            query_mapping = {"resource": "summary", "source": None, "severity": None, "check_id": None, "text": None, "offset": 0, "limit": 1}
            result = package_query.query_from_mapping(value.to_dict(), package_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionGateReleasePacketPackageQuery.from_mapping(query_mapping))
            self.assertEqual(result.total_count, 1)
            self.assertEqual(package_query.address_query(result), result.content_address)
            self.assertEqual(package_query.verify_query(result).to_dict(), result.to_dict())
            self.assertEqual(package_query.query_from_mapping(value.to_dict(), resource="files", limit=1).returned_count, 1)


class CatalogPromotionPackageAuditTests(DurableCatalogPromotionPackageFixture):
    def test_package_audit_has_twelve_independent_replay_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            assurance = package_audit.audit_package(value)
            self.assertEqual((assurance.state, assurance.complete, assurance.accepted), ("complete", True, True))
            self.assertEqual((assurance.check_count, assurance.passed_count, assurance.failed_count), (package_audit.MAX_CHECKS, package_audit.MAX_CHECKS, 0))
            self.assertEqual(tuple(check.check_id for check in assurance.checks), package_audit.CHECK_IDS)
            self.assertEqual(package_audit.address_audit(assurance), assurance.content_address)
            self.assertEqual(package_audit.verify_audit(assurance).to_dict(), assurance.to_dict())
            self.assertIn("Package Audit", package_audit.render_audit_markdown(assurance))
            self.assert_public_projection(assurance.to_dict())

    def test_package_audit_surfaces_malformed_documents_as_incomplete(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            tampered = value.to_dict()
            tampered["failed_count"] = 1
            diagnostics = package_audit.audit_from_mapping(tampered)
            self.assertEqual(diagnostics.state, "incomplete")
            self.assertFalse(diagnostics.accepted)
            self.assertEqual(diagnostics.failed_count, package_audit.MAX_CHECKS)
            self.assertEqual(package_audit.verify_audit(diagnostics).state, "incomplete")
            self.assert_public_projection(package_audit.capabilities())


class CatalogPromotionPackageDiffTests(DurableCatalogPromotionPackageFixture):
    def test_same_package_diff_is_unchanged_and_fully_assured(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self.package_for(Path(temporary))
            result = package_diff.build_diff(value, value, diff_id="package-diff-same")
            self.assertEqual(result.state, "unchanged")
            self.assertEqual(result.changed_fields, ())
            self.assertEqual(result.items, ())
            self.assertEqual(result.action_count_delta, 0)
            self.assertEqual(package_diff.address_diff(result), result.content_address)
            assurance = package_diff_audit.audit_diff(result)
            self.assertEqual((assurance.state, assurance.passed_count, assurance.failed_count), ("complete", package_diff_audit.MAX_CHECKS, 0))
            self.assertEqual(package_diff_audit.verify_audit(assurance).to_dict(), assurance.to_dict())
            self.assertIn("Package Diff", package_diff.render_diff_markdown(result))
            self.assertIn("field,before,after", package_diff.diff_csv(result).splitlines()[0])

    def test_ready_to_held_diff_detects_actions_and_changed_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready = self.package_for(Path(temporary) / "ready")
            held = self.package_for(Path(temporary) / "held", held=True, package_id="package-held")
            result = package_diff.build_diff(ready, held, diff_id="package-diff-ready-to-held")
            self.assertEqual(result.state, "changed")
            self.assertIn("packet.state", result.changed_fields)
            self.assertIn("packet.decision", result.changed_fields)
            self.assertEqual((result.left_decision, result.right_decision), ("promote", "hold"))
            self.assertEqual((result.left_action_count, result.right_action_count, result.action_count_delta), (0, 1, 1))
            self.assertEqual(len(result.action_added_ids), 1)
            self.assertEqual((len(result.action_removed_ids), len(result.action_changed_ids)), (0, 0))
            self.assertEqual(tuple(item.field for item in result.items), result.changed_fields)
            self.assertTrue(all(package_diff.address_item(item) == item.content_address for item in result.items))
            self.assertEqual(package_diff.verify_diff(result).to_dict(), result.to_dict())
            assurance = package_diff_audit.audit_diff(result)
            self.assertEqual((assurance.complete, assurance.accepted, assurance.failed_count), (True, True, 0))
            self.assertEqual(package_diff_query.query_diff(result, resource="fields").total_count, len(result.changed_fields))
            self.assertEqual(package_diff_query.query_diff(result, resource="added-actions").total_count, 1)
            self.assertEqual(package_diff_query.query_diff(result, resource="removed-actions").total_count, 0)
            self.assertEqual(package_diff_query.query_diff(result, resource="decisions").records[0]["before"], "promote")

    def test_package_diff_query_resources_filters_and_pagination_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = package_diff.build_diff(self.package_for(Path(temporary) / "ready"), self.package_for(Path(temporary) / "held", held=True, package_id="package-held"))
            for resource in package_diff_query.RESOURCES:
                page = package_diff_query.query_diff(result, resource=resource, limit=package_diff_query.MAX_LIMIT)
                self.assertEqual(package_diff_query.query_result_from_mapping(json.loads(package_diff_query.query_json(page))).to_dict(), page.to_dict())
                self.assertLessEqual(page.returned_count, package_diff_query.MAX_QUERY_ITEMS)
            self.assertEqual(package_diff_query.query_diff(result, resource="fields", field="packet.state").total_count, 1)
            self.assertEqual(package_diff_query.query_diff(result, resource="fields", field="missing").total_count, 0)
            self.assertEqual(package_diff_query.query_diff(result, resource="fields", text="hold").total_count, 1)
            self.assertEqual(package_diff_query.query_diff(result, resource="items", offset=1, limit=1).returned_count, 1)
            self.assertEqual(package_diff_query.query_diff(result, resource="items", offset=package_diff_query.MAX_QUERY_ITEMS, limit=1).returned_count, 0)
            self.assertRaises(ValidationError, package_diff_query.query_diff, result, resource="unknown")
            self.assert_public_projection(package_diff.capabilities())
            self.assert_public_projection(package_diff_query.capabilities())
            self.assert_public_projection(package_diff_audit.capabilities())


class CatalogPromotionPackageSurfaceTests(DurableCatalogPromotionPackageFixture):
    def test_cli_builds_persists_queries_audits_and_diffs_packages(self):
        from glio_noncode.cli import build_parser, main

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, baseline, candidate = self.documents_for(root / "inputs")
            destination = root / "package"
            summary_file = root / "package.json"
            sources = ["--left-label", "baseline", "--left-directory", str(baseline), "--right-label", "baseline", "--right-directory", str(baseline), "--right-label", "candidate", "--right-directory", str(candidate)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([self.package_command, *sources, "--destination", str(destination), "--format", "summary", "--output", str(summary_file)]), 0)
            self.assertEqual(json.loads(summary_file.read_text(encoding="utf-8"))["decision"], "promote")
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))
            query_file = root / "query.json"
            self.assertEqual(main([self.package_command + "-query", str(destination), "--resource", "files", "--format", "json", "--output", str(query_file)]), 0)
            self.assertEqual(json.loads(query_file.read_text(encoding="utf-8"))["total_count"], 4)
            audit_file = root / "audit.json"
            self.assertEqual(main([self.package_command + "-audit", str(destination), "--format", "json", "--output", str(audit_file)]), 0)
            self.assertEqual(json.loads(audit_file.read_text(encoding="utf-8"))["passed_count"], 12)
            diff_file = root / "diff.json"
            self.assertEqual(main([self.package_command + "-diff", str(destination), str(destination), "--format", "json", "--output", str(diff_file)]), 0)
            self.assertEqual(json.loads(diff_file.read_text(encoding="utf-8"))["state"], "unchanged")
            diff_query_file = root / "diff-query.json"
            self.assertEqual(main([self.package_command + "-diff-query", str(diff_file), "--resource", "summary", "--output", str(diff_query_file)]), 0)
            self.assertEqual(json.loads(diff_query_file.read_text(encoding="utf-8"))["total_count"], 1)
            diff_audit_file = root / "diff-audit.json"
            self.assertEqual(main([self.package_command + "-diff-audit", str(diff_file), "--format", "json", "--output", str(diff_audit_file)]), 0)
            self.assertEqual(json.loads(diff_audit_file.read_text(encoding="utf-8"))["passed_count"], 12)
            choices = build_parser()._subparsers._group_actions[0].choices
            self.assertIn(self.package_command + "-manifest-schema", choices)
            self.assertIn(self.package_command + "-diff-audit-capabilities", choices)

    def test_http_build_query_audit_and_package_diff_routes_are_public(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, baseline, candidate = self.documents_for(root / "inputs")
            ready = self.package_for(root / "ready")
            ready_path = root / "ready-package"
            package_model.write_package(ready, ready_path)
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/catalog/promotion-gate/release-packet"
                params = [("left_label", "baseline"), ("left_directory", str(baseline)), ("right_label", "baseline"), ("right_directory", str(baseline)), ("right_label", "candidate"), ("right_directory", str(candidate))]
                package_query_url = prefix + "/package/query?" + urlencode({"input": str(ready_path), "resource": "files", "format": "json"})
                with urlopen(package_query_url) as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 4)
                with urlopen(prefix + "/package/audit?" + urlencode({"input": str(ready_path), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["passed_count"], 12)
                with urlopen(prefix + "/package?" + urlencode(params + [("destination", str(root / "http-package")), ("format", "json")])) as response:
                    self.assertEqual(json.loads(response.read())["packet"]["decision"], "promote")
                runtime_params = params + [("runtime_id", "runtime-http"), ("package_id", "package-http"), ("resource", "files"), ("destination", str(root / "http-runtime-package")), ("format", "json")]
                with urlopen(prefix + "/package/runtime?" + urlencode(runtime_params)) as response:
                    runtime_payload = json.loads(response.read())
                    self.assertEqual(runtime_payload["package"]["packet"]["decision"], "promote")
                    self.assertEqual(runtime_payload["query"]["returned_count"], 4)
                with urlopen(prefix + "/package/registry?" + urlencode([( "package_directory", str(root / "http-runtime-package")), ("registry_id", "registry-http"), ("destination", str(root / "http-registry")), ("format", "json")])) as response:
                    registry_payload = json.loads(response.read())
                    self.assertEqual(registry_payload["entry_count"], 1)
                    self.assertEqual(registry_payload["release_ready_count"], 1)
                with urlopen(prefix + "/package/registry/query?" + urlencode({"input": str(root / "http-registry"), "resource": "ready", "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(prefix + "/package/registry/audit?" + urlencode({"input": str(root / "http-registry"), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["passed_count"], 9)
                with urlopen(prefix + "/package/registry/diff?" + urlencode({"left": str(root / "http-registry"), "right": str(root / "http-registry"), "format": "json"})) as response:
                    self.assertEqual(json.loads(response.read())["state"], "unchanged")
                with urlopen(prefix + "/package/manifest-schema") as response:
                    self.assertIn("package_id", json.loads(response.read())["properties"])
                with urlopen(prefix + "/package/query/query-result-schema") as response:
                    self.assertIn("records", json.loads(response.read())["properties"])
                with urlopen(prefix + "/package/runtime/capabilities") as response:
                    self.assertIn("runtime", json.loads(response.read())["schemas"])
                with urlopen(prefix + "/package/registry/diff/schema") as response:
                    self.assertIn("changed_fields", json.loads(response.read())["properties"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
