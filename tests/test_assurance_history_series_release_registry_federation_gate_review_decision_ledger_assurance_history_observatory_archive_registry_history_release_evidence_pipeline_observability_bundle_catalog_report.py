"""Deep contracts for catalog reports and promotion decisions."""

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

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog as catalog
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report as report
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit as report_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit_query as report_audit_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_query as report_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate as promotion_gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit as promotion_audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit_query as promotion_audit_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_query as promotion_query
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet as release_packet
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_query as release_packet_query
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff import RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture(RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture):
    CATALOG_COMMAND = RegistryHistoryReleaseEvidencePipelineObservabilityBundleDiffFixture.DIFF_COMMAND.removesuffix("-diff") + "-catalog"
    REPORT_COMMAND = CATALOG_COMMAND + "-report"
    GATE_COMMAND = CATALOG_COMMAND + "-promotion-gate"
    RELEASE_PACKET_COMMAND = GATE_COMMAND + "-release-packet"

    def documents_for(self, root: Path):
        baseline_bundle = self.bundle_for(root / "baseline", "baseline")
        candidate_bundle = self.bundle_for(root / "candidate", "candidate")
        left = catalog.build_catalog_from_directories((("baseline", baseline_bundle),), catalog_id="catalog:left")
        right = catalog.build_catalog_from_directories((("baseline", baseline_bundle), ("candidate", candidate_bundle)), catalog_id="catalog:right")
        return left, right, baseline_bundle, candidate_bundle


class RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportBuildTests(RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogReportFixture):
    def test_report_conserves_catalog_rows_and_exposes_path_free_ratios(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, value, _, _ = self.documents_for(Path(temporary))
            result = report.build_report(value, report_id="report:test")
            self.assertEqual(result.entry_count, 2)
            self.assertEqual(result.accepted_count, 2)
            self.assertEqual(result.ready_count, 2)
            self.assertEqual(result.rejected_count, 0)
            self.assertEqual(result.acceptance_basis_points, 10000)
            self.assertEqual(result.readiness_basis_points, 10000)
            self.assertEqual(result.accepted_labels, ("baseline", "candidate"))
            self.assertEqual(result.ready_labels, ("baseline", "candidate"))
            self.assertEqual(result.rejected_labels, ())
            self.assertEqual(tuple(row.ordinal for row in result.rows), (1, 2))
            self.assertEqual(tuple(row.state for row in result.rows), ("ready", "ready"))
            self.assertEqual(report.address_report(result), result.content_address)
            document = report.report_json(result)
            self.assertNotIn(str(Path(temporary)), document)
            self.assertEqual(report.report_from_mapping(json.loads(document)).to_dict(), result.to_dict())
            self.assertIn("ordinal", report.report_csv(result).splitlines()[0])
            self.assertIn("Catalog Report", report.render_report_markdown(result))
            self.assert_public(result)
            self.assert_public(report.report_schema())
            self.assert_public(report.row_schema())
            self.assert_public(report.capabilities())

    def test_report_audit_and_queries_are_independent_and_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, value, _, _ = self.documents_for(Path(temporary))
            result = report.build_report(value)
            assurance = report_audit.audit_report(result)
            self.assertEqual(assurance.state, "complete")
            self.assertTrue(assurance.accepted)
            self.assertEqual(assurance.passed_count, len(report_audit.CHECK_IDS))
            self.assertEqual(assurance.failed_count, 0)
            page = report_query.query_report(result, resource="ready", limit=1)
            self.assertEqual((page.total_count, page.returned_count), (2, 1))
            self.assertEqual(page.records[0]["label"], "baseline")
            self.assertEqual(report_query.query_result_from_mapping(json.loads(report_query.query_json(page))).to_dict(), page.to_dict())
            audit_page = report_audit_query.query_report(result, resource="passed", limit=3)
            self.assertEqual((audit_page.total_count, audit_page.returned_count), (12, 3))
            self.assertEqual(report_audit_query.query_result_from_mapping(json.loads(report_audit_query.query_json(audit_page))).to_dict(), audit_page.to_dict())
            self.assertIn("check_id", report_audit_query.query_csv(audit_page).splitlines()[0])
            self.assertIn("Resource", report_query.render_query_markdown(page))
            for value_to_check in (assurance, report_audit_query.query_schema(), report_audit_query.query_result_schema(), report_audit_query.capabilities()):
                self.assert_public(value_to_check)
            tampered = result.to_dict()
            tampered["accepted_count"] = 1
            diagnostics = report_audit.audit_from_mapping(tampered)
            self.assertEqual(diagnostics.state, "incomplete")
            self.assertFalse(diagnostics.accepted)
            self.assertGreater(diagnostics.failed_count, 0)

    def test_promotion_gate_models_policy_outcomes_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right, _, _ = self.documents_for(Path(temporary))
            change = diff.build_diff(left, right, diff_id="catalog-diff:test")
            candidate_report = report.build_report(right, report_id="report:test")
            ready = promotion_gate.build_promotion_gate(change, candidate_report, gate_id="gate:ready")
            self.assertEqual((ready.state, ready.accepted, ready.release_ready), ("ready", True, True))
            self.assertEqual((ready.passed_count, ready.failed_count), (15, 0))
            ready_assurance = promotion_audit.audit_gate(ready)
            self.assertTrue(ready_assurance.complete)
            self.assertEqual(ready_assurance.passed_count, len(promotion_audit.CHECK_IDS))
            self.assertEqual(promotion_audit.audit_from_mapping(ready.to_dict()).to_dict(), ready_assurance.to_dict())
            page = promotion_query.query_gate(ready, resource="passed", limit=2)
            self.assertEqual((page.total_count, page.returned_count), (15, 2))
            audit_page = promotion_audit_query.query_gate(ready, resource="passed", limit=2)
            self.assertEqual((audit_page.total_count, audit_page.returned_count), (12, 2))
            self.assertEqual(promotion_audit_query.query_result_from_mapping(json.loads(promotion_audit_query.query_json(audit_page))).to_dict(), audit_page.to_dict())
            packet = release_packet.build_release_packet(ready, ready_assurance, packet_id="packet-ready")
            self.assertEqual((packet.state, packet.decision, packet.release_ready), ("ready", "promote", True))
            self.assertEqual((packet.passed_count, packet.check_count, packet.action_count), (27, 27, 0))
            self.assertEqual(release_packet.packet_from_mapping(json.loads(release_packet.packet_json(packet))).to_dict(), packet.to_dict())
            packet_page = release_packet_query.query_packet(packet, resource="actions", limit=27)
            self.assertEqual((packet_page.total_count, packet_page.returned_count), (0, 0))
            held_policy = promotion_gate.RegistryHistoryReleaseEvidencePipelineObservabilityBundleCatalogPromotionPolicy(max_added=0)
            held = promotion_gate.build_promotion_gate(change, candidate_report, policy=held_policy, gate_id="gate:held")
            self.assertEqual((held.state, held.accepted, held.release_ready), ("held", True, False))
            self.assertEqual(held.hold_failure_count, 1)
            held_assurance = promotion_audit.audit_gate(held)
            held_packet = release_packet.build_release_packet(held, held_assurance, packet_id="packet-held")
            self.assertEqual((held_packet.state, held_packet.decision, held_packet.action_count), ("held", "hold", 1))
            self.assertEqual(release_packet_query.query_packet(held_packet, resource="holds").total_count, 1)
            empty = catalog.build_catalog_from_directories((), catalog_id="catalog:empty")
            blocked_change = diff.build_diff(empty, right, diff_id="catalog-diff:blocked")
            blocked = promotion_gate.build_promotion_gate(blocked_change, candidate_report, gate_id="gate:blocked")
            self.assertEqual((blocked.state, blocked.accepted, blocked.release_ready), ("blocked", False, False))
            self.assertGreater(blocked.blocking_failure_count, 0)
            blocked_audit = promotion_audit.audit_gate(blocked)
            self.assertTrue(blocked_audit.complete)
            failed_page = promotion_query.query_gate(blocked, resource="failed", limit=15)
            self.assertGreater(failed_page.total_count, 0)
            self.assert_public(promotion_gate.capabilities())
            self.assert_public(promotion_audit.capabilities())
            self.assert_public(release_packet.capabilities())
            self.assert_public(release_packet_query.capabilities())

    def test_contract_commands_and_http_promotion_audit_routes(self):
        from glio_noncode.cli import build_parser, main

        with tempfile.TemporaryDirectory() as temporary:
            left, right, baseline, candidate = self.documents_for(Path(temporary))
            sources = ["--left-label", "baseline", "--left-directory", str(baseline), "--right-label", "baseline", "--right-directory", str(baseline), "--right-label", "candidate", "--right-directory", str(candidate)]
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([self.REPORT_COMMAND, "--label", "baseline", "--directory", str(baseline), "--label", "candidate", "--directory", str(candidate), "--format", "summary"]), 0)
            self.assertEqual(json.loads(output.getvalue())["entry_count"], 2)
            gate_output = Path(temporary) / "gate.json"
            self.assertEqual(main([self.GATE_COMMAND, *sources, "--format", "json", "--output", str(gate_output)]), 0)
            self.assertEqual(json.loads(gate_output.read_text(encoding="utf-8"))["state"], "ready")
            audit_output = Path(temporary) / "audit.json"
            self.assertEqual(main([self.GATE_COMMAND + "-audit", *sources, "--format", "json", "--output", str(audit_output)]), 0)
            self.assertEqual(json.loads(audit_output.read_text(encoding="utf-8"))["failed_count"], 0)
            packet_output = Path(temporary) / "packet.json"
            self.assertEqual(main([self.RELEASE_PACKET_COMMAND, *sources, "--format", "json", "--output", str(packet_output)]), 0)
            self.assertEqual(json.loads(packet_output.read_text(encoding="utf-8"))["decision"], "promote")
            for suffix in ("-audit-schema", "-audit-check-schema", "-audit-capabilities", "-audit-query-query-schema", "-audit-query-query-result-schema", "-audit-query-query-capabilities"):
                self.assertEqual(main([self.GATE_COMMAND + suffix]), 0)
            for suffix in ("-action-schema", "-schema", "-capabilities", "-query-query-schema", "-query-query-result-schema", "-query-query-capabilities"):
                self.assertEqual(main([self.RELEASE_PACKET_COMMAND + suffix]), 0)
            choices = build_parser()._subparsers._group_actions[0].choices
            self.assertIn(self.GATE_COMMAND + "-audit", choices)
            self.assertEqual(left.entry_count, 1)
            self.assertEqual(right.entry_count, 2)

            server, thread = self.server()
            try:
                prefix = f"http://127.0.0.1:{server.server_port}/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory/packet/registry/federation/assurance-gate/review/decision-ledger/assurance-history-series/release-registry/federation/gate/review/decision-ledger/assurance-history/observatory/archive/registry/history/release-gate/release-evidence-pipeline/observability/bundle/catalog/promotion-gate"
                params = [("left_label", "baseline"), ("left_directory", str(baseline)), ("right_label", "baseline"), ("right_directory", str(baseline)), ("right_label", "candidate"), ("right_directory", str(candidate)), ("format", "json")]
                try:
                    with urlopen(prefix + "/audit?" + urlencode(params)) as response:
                        self.assertEqual(json.loads(response.read())["failed_count"], 0)
                except Exception as error:
                    if hasattr(error, "read"):
                        raise AssertionError(error.read().decode()) from error
                    raise
                with urlopen(prefix + "/audit/query?" + urlencode(params + [("resource", "passed"), ("limit", "1")])) as response:
                    self.assertEqual(json.loads(response.read())["returned_count"], 1)
                with urlopen(prefix + "/release-packet?" + urlencode(params)) as response:
                    self.assertEqual(json.loads(response.read())["decision"], "promote")
                with urlopen(prefix + "/release-packet/query?" + urlencode(params + [("resource", "actions")])) as response:
                    self.assertEqual(json.loads(response.read())["total_count"], 0)
                for suffix, field in (("/audit/schema", "gate_address"), ("/audit/check-schema", "check_id"), ("/audit/query/query-schema", "resource"), ("/audit/query/query-result-schema", "records")):
                    with urlopen(prefix + suffix) as response:
                        self.assertIn(field, json.loads(response.read())["properties"])
                for suffix, field in (("/release-packet/action-schema", "ordinal"), ("/release-packet/schema", "packet_id"), ("/release-packet/query/query-schema", "resource"), ("/release-packet/query/query-result-schema", "records")):
                    with urlopen(prefix + suffix) as response:
                        self.assertIn(field, json.loads(response.read())["properties"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


if __name__ == "__main__":
    unittest.main()
