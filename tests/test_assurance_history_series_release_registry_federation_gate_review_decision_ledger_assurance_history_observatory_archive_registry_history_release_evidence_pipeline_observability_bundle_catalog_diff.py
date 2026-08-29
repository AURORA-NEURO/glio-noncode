"""Deep contracts for verified observability-bundle catalog revisions."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_audit_query as audit_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_query as diff_query
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    CATALOG_COMMAND = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture.DIFF_COMMAND.removesuffix("-diff") + "-catalog"
    CATALOG_DIFF_COMMAND = CATALOG_COMMAND + "-diff"

    def catalogs_for(self, root: Path):
        baseline = self.bundle_for(root / "baseline", "baseline")
        candidate = self.bundle_for(root / "candidate", "candidate")
        left = catalog.build_catalog_from_directories((("baseline", baseline),), catalog_id="catalog:left")
        right = catalog.build_catalog_from_directories((("baseline", baseline), ("candidate", candidate)), catalog_id="catalog:right")
        return left, right, baseline, candidate


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffFixture):
    def test_label_union_classification_deltas_and_mapping_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right, _, _ = self.catalogs_for(Path(temporary))
            value = diff.build_diff(left, right, diff_id="catalog-diff:test")
            self.assertEqual(value.state, "added")
            self.assertEqual(value.added_labels, ("candidate",))
            self.assertEqual(value.unchanged_labels, ("baseline",))
            self.assertEqual(value.item_count, 2)
            self.assertEqual(value.added_count, 1)
            self.assertEqual(value.unchanged_count, 1)
            self.assertEqual(value.entry_count_delta, 1)
            self.assertEqual(value.accepted_count_delta, 1)
            self.assertEqual(value.ready_count_delta, 1)
            self.assertEqual(value.artifact_count_delta, len(catalog.bundle_model.ARTIFACT_FILES))
            self.assertEqual(diff.address_diff(value), value.content_address)
            replayed = diff.diff_from_mapping(json.loads(diff.diff_json(value)))
            self.assertEqual(replayed.to_dict(), value.to_dict())
            self.assert_public(value)

    def test_same_label_revision_is_changed_and_audit_is_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, _, _, candidate = self.catalogs_for(Path(temporary))
            revised = catalog.build_catalog_from_directories((("baseline", candidate),), catalog_id="catalog:revised")
            value = diff.diff_catalogs(left, revised)
            self.assertEqual(value.state, "changed")
            self.assertEqual(value.changed_labels, ("baseline",))
            self.assertGreater(value.items[0].changed_fields.__len__(), 0)
            report = audit.audit_diff(value)
            self.assertEqual(report.state, "complete")
            self.assertEqual(report.check_count, len(audit.CHECK_IDS))
            self.assertEqual(report.failed_count, 0)
            self.assertTrue(report.accepted)
            self.assert_public(report)
            self.assert_public(audit.audit_schema())
            self.assert_public(audit.check_schema())
            self.assert_public(audit.capabilities())

    def test_audit_preserves_diagnostics_for_tampered_public_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right, _, _ = self.catalogs_for(Path(temporary))
            value = diff.build_diff(left, right)
            document = value.to_dict()
            document["added_count"] = 0
            report = audit.audit_from_mapping(document)
            self.assertEqual(report.state, "incomplete")
            self.assertFalse(report.accepted)
            self.assertGreater(report.failed_count, 0)
            self.assertEqual(len(report.checks), len(audit.CHECK_IDS))

    def test_bounded_diff_and_audit_queries_are_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right, _, _ = self.catalogs_for(Path(temporary))
            value = diff.build_diff(left, right)
            page = diff_query.query_diff(value, resource="transitions", status="added", limit=1)
            self.assertEqual(page.total_count, 1)
            self.assertEqual(page.returned_count, 1)
            self.assertEqual(page.records[0]["label"], "candidate")
            self.assertEqual(diff_query.address_query(page), page.content_address)
            self.assertEqual(diff_query.query_result_from_mapping(json.loads(diff_query.query_json(page))).to_dict(), page.to_dict())
            self.assertIn("candidate", diff_query.render_query_markdown(page))
            self.assertIn("label", diff_query.query_csv(page).splitlines()[0])
            audit_page = audit_query.query_diff(value, resource="passed", limit=3)
            self.assertEqual(audit_page.total_count, len(audit.CHECK_IDS))
            self.assertEqual(audit_page.returned_count, 3)
            self.assertEqual(audit_query.address_query(audit_page), audit_page.content_address)
            self.assertEqual(audit_query.query_result_from_mapping(json.loads(audit_query.query_json(audit_page))).to_dict(), audit_page.to_dict())
            self.assert_public(diff_query.query_schema())
            self.assert_public(diff_query.query_result_schema())
            self.assert_public(diff_query.capabilities())
            self.assert_public(audit_query.query_schema())
            self.assert_public(audit_query.query_result_schema())
            self.assert_public(audit_query.capabilities())
            with self.assertRaises(ValidationError):
                diff_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffQuery(resource="unknown")
            with self.assertRaises(ValidationError):
                audit_query.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffAuditQuery(limit=0)


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffCliApiTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogDiffFixture):
    def test_cli_diff_audit_query_and_contract_commands(self):
        from glio_noncode.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            left, right, baseline, candidate = self.catalogs_for(Path(temporary))
            output = Path(temporary) / "catalog-diff.json"
            sources = ["--left-label", "baseline", "--left-directory", str(baseline), "--right-label", "baseline", "--right-directory", str(baseline), "--right-label", "candidate", "--right-directory", str(candidate)]
            self.assertEqual(main([self.CATALOG_DIFF_COMMAND, *sources, "--format", "json", "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["added_count"], 1)
            audit_output = Path(temporary) / "catalog-diff-audit.json"
            self.assertEqual(main([self.CATALOG_DIFF_COMMAND + "-audit", *sources, "--format", "json", "--output", str(audit_output)]), 0)
            self.assertEqual(json.loads(audit_output.read_text(encoding="utf-8"))["failed_count"], 0)
            query_output = Path(temporary) / "catalog-diff-query.json"
            self.assertEqual(main([self.CATALOG_DIFF_COMMAND + "-query", *sources, "--resource", "added", "--limit", "1", "--output", str(query_output)]), 0)
            self.assertEqual(json.loads(query_output.read_text(encoding="utf-8"))["returned_count"], 1)
            audit_query_output = Path(temporary) / "catalog-diff-audit-query.json"
            self.assertEqual(main([self.CATALOG_DIFF_COMMAND + "-audit-query", *sources, "--resource", "passed", "--limit", "2", "--output", str(audit_query_output)]), 0)
            self.assertEqual(json.loads(audit_query_output.read_text(encoding="utf-8"))["returned_count"], 2)
            for suffix in ("-schema", "-entry-schema", "-capabilities", "-audit-schema", "-audit-check-schema", "-audit-capabilities", "-query-query-schema", "-query-query-result-schema", "-query-query-capabilities", "-audit-query-query-schema", "-audit-query-query-result-schema", "-audit-query-query-capabilities"):
                self.assertEqual(main([self.CATALOG_DIFF_COMMAND + suffix]), 0)
            self.assertEqual(left.entry_count, 1)
            self.assertEqual(right.entry_count, 2)

    def test_http_catalog_diff_audit_and_query_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, _, baseline, candidate = self.catalogs_for(Path(temporary))
            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/catalog/diff"
                params = [("left_label", "baseline"), ("left_directory", str(baseline)), ("right_label", "baseline"), ("right_directory", str(baseline)), ("right_label", "candidate"), ("right_directory", str(candidate)), ("format", "summary")]
                with urlopen(prefix + "?" + urlencode(params)) as response:
                    self.assertEqual(json.loads(response.read())["added_count"], 1)
                with urlopen(prefix + "/audit?" + urlencode(params)) as response:
                    self.assertEqual(json.loads(response.read())["failed_count"], 0)
                query_params = params + [("resource", "passed"), ("limit", "1")]
                with urlopen(prefix + "/audit/query?" + urlencode(query_params)) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                for suffix, field in (("/schema", "items"), ("/entry-schema", "label"), ("/audit/schema", "checks"), ("/audit/check-schema", "check_id"), ("/audit/query-schema", "resource"), ("/audit/query-result-schema", "records")):
                    with urlopen(prefix + suffix) as response:
                        self.assertIn(field, json.loads(response.read())["properties"])
                with urlopen(prefix + "/audit/query-capabilities") as response:
                    self.assertIn("check identity filtering", json.loads(response.read())["features"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
