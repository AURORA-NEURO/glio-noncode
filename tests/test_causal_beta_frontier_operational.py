from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.causal_beta_frontier_assurance import build_causal_beta_frontier_assurance
from glio_noncode.causal_beta_frontier_exports import build_causal_beta_frontier_exports, export_causal_beta_frontier_json, export_causal_beta_frontier_review_csv, export_causal_beta_frontier_review_markdown
from glio_noncode.causal_beta_frontier_query import CausalBetaFrontierQuery, build_causal_beta_frontier_query_index, query_causal_beta_frontier
from glio_noncode.causal_beta_frontier_report import build_causal_beta_frontier_report
from glio_noncode.causal_beta_frontier_runbook import build_causal_beta_frontier_runbook, runbook_is_executable
from glio_noncode.causal_beta_frontier_runtime import run_causal_beta_frontier_runtime


class CausalBetaFrontierOperationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_causal_beta_frontier_runtime(run_id="operational-test")
        cls.fixture = cls.runtime.fixture
        cls.evaluation = cls.runtime.evaluation
        cls.review = cls.runtime.review
        cls.metrics = cls.runtime.metrics
        cls.bundle = cls.runtime.bundle
        cls.release = cls.runtime.release
        cls.artifacts = cls.runtime.artifacts
        cls.view = cls.runtime.review_view
        cls.exports = cls.runtime.exports
        cls.operational = cls.runtime.operational
        cls.boundary = cls.runtime.boundary
        cls.assurance = cls.runtime.assurance
        cls.runbook = cls.runtime.runbook

    def test_runtime_and_all_operational_planes_are_accepted(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertTrue(self.operational.accepted)
        self.assertTrue(self.boundary.accepted)
        self.assertTrue(self.exports.accepted)
        self.assertTrue(self.assurance.accepted)
        self.assertTrue(self.runbook.accepted)

    def test_operation_matrix_is_balanced(self) -> None:
        self.assertEqual(len(self.operational.cells), 16)
        for operation in {item.operation for item in self.operational.cells}:
            cells = self.operational.for_operation(operation)
            self.assertEqual(len(cells), 4)
            self.assertEqual(sum(item.release_allowed for item in cells), 1)
            self.assertEqual(sum(item.decision == "quarantine" for item in cells), 2 if operation != "counterfactual_allele_state" else 1)

    def test_operation_matrix_scenario_totals_are_balanced(self) -> None:
        expected = {
            "positive": 4,
            "minimum_or_missing": 4,
            "conflict_or_ambiguity": 4,
            "foreign_context": 4,
        }
        for scenario, count in expected.items():
            self.assertEqual(len(self.operational.for_scenario(scenario)), count)

    def test_positive_cells_are_retainable(self) -> None:
        for cell in self.operational.for_scenario("positive"):
            self.assertEqual(cell.state, "supported")
            self.assertEqual(cell.decision, "retain")
            self.assertEqual(cell.action, "retain_for_bounded_analysis")
            self.assertEqual(cell.expected_effect, "retain positive receipt")
            self.assertTrue(cell.release_allowed)
            self.assertFalse(cell.review_required)

    def test_minimum_cells_are_reviewable(self) -> None:
        for cell in self.operational.for_scenario("minimum_or_missing"):
            self.assertEqual(cell.state, "partial")
            self.assertIn(cell.decision, {"review", "abstain"})
            self.assertFalse(cell.release_allowed)
            self.assertTrue(cell.review_required)
            self.assertIn(cell.action, {"route_to_review", "abstain_from_claim"})

    def test_conflict_cells_are_quarantined_or_reviewed(self) -> None:
        for cell in self.operational.for_scenario("conflict_or_ambiguity"):
            self.assertIn(cell.state, {"contradictory", "ambiguous"})
            self.assertIn(cell.decision, {"quarantine", "review"})
            self.assertFalse(cell.release_allowed)
            self.assertTrue(cell.review_required)

    def test_foreign_context_cells_are_blocked(self) -> None:
        for cell in self.operational.for_scenario("foreign_context"):
            self.assertEqual(cell.state, "out_of_domain")
            self.assertEqual(cell.decision, "quarantine")
            self.assertEqual(cell.action, "quarantine")
            self.assertFalse(cell.release_allowed)
            self.assertTrue(cell.review_required)

    def test_all_operational_cells_have_receipts(self) -> None:
        self.assertEqual(len({item.content_address for item in self.operational.cells}), 16)
        for cell in self.operational.cells:
            self.assertTrue(cell.cell_id.startswith("cell:"))
            self.assertTrue(cell.operation)
            self.assertTrue(cell.scenario)
            self.assertTrue(cell.action)
            self.assertTrue(cell.content_address.startswith("sha256:"))

    def test_boundary_has_three_allowed_statements(self) -> None:
        self.assertEqual(len(self.boundary.allowed), 3)
        self.assertEqual([item.boundary_kind for item in self.boundary.allowed], ["allowed", "allowed", "allowed"])
        self.assertEqual(len({item.boundary_id for item in self.boundary.allowed}), 3)
        self.assertTrue(all(item.enforced for item in self.boundary.allowed))

    def test_boundary_has_four_excluded_statements(self) -> None:
        self.assertEqual(len(self.boundary.excluded), 4)
        self.assertEqual([item.boundary_kind for item in self.boundary.excluded], ["excluded"] * 4)
        excluded_ids = {item.boundary_id for item in self.boundary.excluded}
        self.assertEqual(excluded_ids, {"excluded:patient", "excluded:diagnosis", "excluded:foreign-context", "excluded:unresolved"})
        self.assertTrue(all(item.enforced for item in self.boundary.excluded))

    def test_boundary_receipts_are_unique(self) -> None:
        receipts = [item.content_address for item in self.boundary.all_boundaries]
        self.assertEqual(len(receipts), len(set(receipts)))
        self.assertTrue(all(item.startswith("sha256:") for item in receipts))

    def test_export_inventory_has_expected_media_types(self) -> None:
        media_types = {item.export_kind: item.content_type for item in self.exports.envelopes}
        self.assertEqual(media_types["fixture-json"], "application/json")
        self.assertEqual(media_types["evaluation-json"], "application/json")
        self.assertEqual(media_types["summary-json"], "application/json")
        self.assertEqual(media_types["release-manifest-json"], "application/json")
        self.assertEqual(media_types["review-csv"], "text/csv")
        self.assertEqual(media_types["review-markdown"], "text/markdown")

    def test_export_inventory_has_nonnegative_row_counts(self) -> None:
        self.assertTrue(all(item.row_count >= 0 for item in self.exports.envelopes))
        self.assertEqual(self.exports.by_kind("fixture-json").row_count, 16)
        self.assertEqual(self.exports.by_kind("evaluation-json").row_count, 16)
        self.assertEqual(self.exports.by_kind("review-csv").row_count, 16)
        self.assertEqual(self.exports.by_kind("review-markdown").row_count, 16)
        self.assertEqual(self.exports.by_kind("release-manifest-json").row_count, 16)

    def test_export_json_is_parseable(self) -> None:
        decoded = json.loads(export_causal_beta_frontier_json(self.exports))
        self.assertEqual(decoded["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(decoded["export_count"], 6)
        self.assertTrue(decoded["accepted"])
        for envelope in decoded["envelopes"]:
            self.assertTrue(envelope["export_id"])
            self.assertTrue(envelope["content_address"].startswith("sha256:"))

    def test_csv_export_has_header_and_all_records(self) -> None:
        lines = export_causal_beta_frontier_review_csv(self.view).splitlines()
        self.assertEqual(len(lines), 17)
        self.assertEqual(lines[0].split(",")[:4], ["record_id", "operation", "role", "expected_state"])
        self.assertTrue(any("D11-C05-P" in line for line in lines))
        self.assertTrue(any("D11-C08-C3" in line for line in lines))

    def test_markdown_export_has_stable_columns(self) -> None:
        markdown = export_causal_beta_frontier_review_markdown(self.view)
        lines = markdown.splitlines()
        self.assertEqual(lines[0], "| record_id | operation | role | expected_state | observed_state | issue_codes | decision | priority | state_match | issue_match | accepted | source_count |")
        self.assertEqual(lines[1].count("---"), 12)
        self.assertEqual(len(lines), 18)
        self.assertIn("D11-C07-C2", markdown)

    def test_review_view_has_one_row_per_fixture_record(self) -> None:
        self.assertEqual(len(self.view.rows), len(self.fixture.records))
        self.assertEqual({item.record_id for item in self.view.rows}, set(self.fixture.record_map()))
        self.assertTrue(all(item.state_match for item in self.view.rows))
        self.assertTrue(all(item.issue_match for item in self.view.rows))

    def test_review_view_source_counts_match_fixture(self) -> None:
        source_counts = {item.record_id: len(self.fixture.record_map()[item.record_id].source_ids) for item in self.view.rows}
        for row in self.view.rows:
            self.assertEqual(row.source_count, source_counts[row.record_id])

    def test_review_view_acceptance_tracks_reconciliation(self) -> None:
        accepted_ids = {item.record_id for item in self.view.rows if item.accepted}
        expected_ids = {item.record_id for item in self.runtime.reconciliation.items if item.accepted}
        self.assertEqual(accepted_ids, expected_ids)

    def test_query_index_exposes_all_dimension_values(self) -> None:
        index = build_causal_beta_frontier_query_index(self.fixture, self.evaluation)
        self.assertEqual(index.fixture_id, self.fixture.fixture_id)
        self.assertEqual(index.record_ids, tuple(item.record_id for item in self.evaluation.rows))
        self.assertEqual(index.operations, tuple(sorted({item.operation for item in self.evaluation.rows})))
        self.assertEqual(index.states, ("ambiguous", "contradictory", "out_of_domain", "partial", "supported"))
        self.assertEqual(index.issue_codes, ("context_mismatch", "contradictory_direction", "minimum_independent_sources", "missing_alternate_allele", "negative_control_conflict", "replicate_ambiguity"))

    def test_query_by_operation_returns_four_rows(self) -> None:
        for operation in self.runtime.adapters.specs:
            result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(operation=operation.operation.value), self.review)
            self.assertEqual(len(result.rows), 4)
            self.assertEqual(result.query.operation, operation.operation.value)
            self.assertFalse(result.empty)

    def test_query_by_role_returns_positive_and_controls(self) -> None:
        positives = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(role="positive"), self.review)
        controls = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(role="control"), self.review)
        self.assertEqual(len(positives.rows), 4)
        self.assertEqual(len(controls.rows), 12)
        self.assertTrue(all(item.role == "positive" for item in positives.rows))
        self.assertTrue(all(item.role == "control" for item in controls.rows))

    def test_query_by_state_and_issue_can_be_intersected(self) -> None:
        result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(state="out_of_domain", issue_code="context_mismatch"), self.review)
        self.assertEqual(len(result.rows), 4)
        self.assertTrue(all(item.observed_state == "out_of_domain" for item in result.rows))
        self.assertTrue(all("context_mismatch" in item.observed_issue_codes for item in result.rows))

    def test_query_by_record_id_has_single_row(self) -> None:
        result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(record_id="D11-C07-C2"), self.review)
        self.assertEqual(result.record_ids, ("D11-C07-C2",))
        self.assertEqual(result.total_matches, 1)
        self.assertEqual(result.rows[0].observed_issue_codes, ("negative_control_conflict",))

    def test_query_with_no_match_is_explicitly_empty(self) -> None:
        result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(record_id="missing"), self.review)
        self.assertTrue(result.empty)
        self.assertEqual(result.total_matches, 0)
        self.assertEqual(result.record_ids, ())
        self.assertEqual(result.rows, ())

    def test_query_accepted_only_excludes_blocked_rows(self) -> None:
        result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(accepted_only=True), self.review)
        self.assertEqual(len(result.rows), 8)
        self.assertTrue(all(item.observed_state not in {"contradictory", "out_of_domain"} for item in result.rows))

    def test_report_has_five_sections(self) -> None:
        report = build_causal_beta_frontier_report(self.fixture, self.metrics, self.review, self.operational, self.assurance)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.sections), 5)
        self.assertEqual([item[0] for item in report.sections], ["Scope", "Observed states", "Issue coverage", "Disposition", "Boundary"])
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_report_mentions_state_and_issue_counts(self) -> None:
        report = build_causal_beta_frontier_report(self.fixture, self.metrics, self.review, self.operational, self.assurance)
        markdown = report.to_markdown()
        self.assertIn("supported=4", markdown)
        self.assertIn("context_mismatch=4", markdown)
        self.assertIn("retained=4", markdown)
        self.assertIn("blocked=8", markdown)

    def test_report_markdown_is_stable_across_runtime_replays(self) -> None:
        first = build_causal_beta_frontier_report(self.fixture, self.metrics, self.review, self.operational, self.assurance)
        other = run_causal_beta_frontier_runtime(run_id="operational-other")
        second = build_causal_beta_frontier_report(other.fixture, other.metrics, other.review, other.operational, other.assurance)
        self.assertEqual(first.to_markdown(), second.to_markdown())
        self.assertEqual(first.content_address, second.content_address)

    def test_runbook_has_twelve_ordered_steps(self) -> None:
        self.assertTrue(runbook_is_executable(self.runbook))
        self.assertEqual(len(self.runbook.steps), 12)
        self.assertEqual(tuple(item.sequence for item in self.runbook.steps), tuple(range(1, 13)))
        self.assertEqual(len({item.step_id for item in self.runbook.steps}), 12)
        self.assertEqual(len({item.command for item in self.runbook.steps}), 12)

    def test_runbook_commands_are_public_beta_commands(self) -> None:
        for command in self.runbook.commands:
            self.assertTrue(command.startswith(("causal-beta-frontier-", "export-causal-beta-frontier-")))
        self.assertIn("causal-beta-frontier-runtime", self.runbook.commands)
        self.assertIn("causal-beta-frontier-assurance", self.runbook.commands)
        self.assertIn("export-causal-beta-frontier-json", self.runbook.commands)

    def test_runbook_blocking_steps_are_explicit(self) -> None:
        self.assertEqual(len(self.runbook.blocking_steps), 9)
        self.assertTrue(all(item.blocking for item in self.runbook.blocking_steps))
        self.assertFalse(self.runbook.step("review-csv").blocking)
        self.assertTrue(self.runbook.step("quality").blocking)
        self.assertEqual(self.runbook.step("runtime").sequence, 4)

    def test_runbook_references_release_addresses(self) -> None:
        self.assertEqual(self.runbook.required_addresses, (self.release.content_address, self.bundle.content_address, self.boundary.content_address, self.assurance.content_address))
        self.assertEqual(len(set(self.runbook.required_addresses)), 4)
        self.assertTrue(all(item.startswith("sha256:") for item in self.runbook.required_addresses))

    def test_runbook_markdown_contains_all_commands(self) -> None:
        markdown = self.runbook.to_markdown()
        self.assertIn("# operational-test:runbook", markdown)
        self.assertIn("| Step | Command | Required output | Blocking |", markdown)
        for command in self.runbook.commands:
            self.assertIn(command, markdown)

    def test_rebuilt_runbook_is_equal_except_run_id(self) -> None:
        rebuilt = build_causal_beta_frontier_runbook("operational-rebuilt", self.fixture.fixture_id, self.runtime.stage_count, self.release, self.bundle, self.boundary, self.assurance)
        self.assertTrue(rebuilt.accepted)
        self.assertEqual(rebuilt.fixture_id, self.runbook.fixture_id)
        self.assertEqual(rebuilt.release_id, self.runbook.release_id)
        self.assertEqual(rebuilt.steps, self.runbook.steps)
        self.assertNotEqual(rebuilt.runbook_id, self.runbook.runbook_id)

    def test_assurance_headline_is_consistent_with_all_flags(self) -> None:
        flags = (self.assurance.runtime_accepted, self.assurance.replay_deterministic, self.assurance.integrity_accepted, self.assurance.operational_accepted, self.assurance.boundary_accepted, self.assurance.exports_accepted)
        self.assertTrue(all(flags))
        self.assertIn("ready", self.assurance.headline)
        self.assertTrue(self.assurance.limitations)

    def test_assurance_limitations_are_deduplicated(self) -> None:
        self.assertEqual(len(self.assurance.limitations), len(set(self.assurance.limitations)))
        self.assertTrue(any("patient" in item.lower() for item in self.assurance.limitations))
        self.assertTrue(any("diagnostic" in item.lower() for item in self.assurance.limitations))

    def test_release_and_bundle_use_boundaries_match(self) -> None:
        self.assertEqual(self.bundle.allowed_uses, self.release.allowed_uses)
        self.assertEqual(self.bundle.excluded_uses, self.release.excluded_uses)
        self.assertEqual(self.boundary.boundary, "public_aggregate_non_patient")
        self.assertEqual(self.bundle.state.value, "ready")
        self.assertEqual(self.release.state.value, "ready")

    def test_artifact_paths_are_unique_and_json(self) -> None:
        paths = [item.relative_path for item in self.artifacts.artifacts]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(all(path.endswith(".json") for path in paths))
        self.assertEqual(paths[0], "fixture.json")
        self.assertEqual(paths[-1], "release.json")

    def test_artifact_descriptions_are_present(self) -> None:
        self.assertTrue(all(item.description for item in self.artifacts.artifacts))
        self.assertEqual(self.artifacts.for_kind("quality")[0].description, "quality gate")
        self.assertEqual(self.artifacts.for_kind("release")[0].description, "release manifest")

    def test_runtime_stage_outputs_have_addresses(self) -> None:
        self.assertEqual(len(self.runtime.stages), 27)
        self.assertEqual(len({item.output_address for item in self.runtime.stages}), 27)
        for stage in self.runtime.stages:
            self.assertTrue(stage.output_address.startswith("sha256:"))
            self.assertTrue(stage.detail)
            self.assertEqual(stage.state, "completed")

    def test_runtime_observability_matches_stage_order(self) -> None:
        self.assertEqual(self.runtime.observability.stage_ids, self.runtime.stage_ids)
        self.assertEqual(self.runtime.observability.completed_count, self.runtime.stage_count)
        self.assertEqual(self.runtime.observability.failed_count, 0)
        self.assertGreaterEqual(self.runtime.observability.total_duration_ms, 0.0)

    def test_runtime_serialization_contains_every_operational_key(self) -> None:
        value = self.runtime.to_dict()
        for key in ("integrity", "operational", "boundary", "replay", "review_view", "exports", "assurance", "runbook"):
            self.assertIn(key, value)
            self.assertIsInstance(value[key], dict)
        self.assertEqual(value["stage_count"], 27)
        self.assertEqual(value["runbook"]["stage_count"], 27)

    def test_runtime_serialization_round_trips_as_json(self) -> None:
        value = json.loads(json.dumps(self.runtime.to_dict(), default=str))
        self.assertEqual(value["run_id"], "operational-test")
        self.assertTrue(value["accepted"])
        self.assertEqual(value["operational"]["cell_count"], 16)
        self.assertEqual(value["exports"]["export_count"], 6)

    def test_export_envelopes_have_unique_addresses(self) -> None:
        addresses = [item.content_address for item in self.exports.envelopes]
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))

    def test_query_result_addresses_change_with_query(self) -> None:
        first = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(state="supported"), self.review)
        second = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(state="partial"), self.review)
        self.assertNotEqual(first.content_address, second.content_address)
        self.assertNotEqual(first.record_ids, second.record_ids)

    def test_query_result_serialization_has_query_payload(self) -> None:
        result = query_causal_beta_frontier(self.fixture, self.evaluation, CausalBetaFrontierQuery(operation="gene_to_state", role="control"), self.review)
        value = result.to_dict()
        self.assertEqual(value["query"]["operation"], "gene_to_state")
        self.assertEqual(value["query"]["role"], "control")
        self.assertEqual(value["total_matches"], 3)
        self.assertEqual(len(value["rows"]), 3)

    def test_retain_and_control_counts_conserve_rows(self) -> None:
        self.assertEqual(self.review.retained_count + self.review.review_count + self.review.blocked_count, 17)
        self.assertEqual(self.review.retained_count + 12, 16)
        self.assertEqual(len(self.review.blocking_record_ids), 8)

    def test_release_checks_are_all_passed(self) -> None:
        self.assertEqual(self.release.passed_count, len(self.release.checks))
        self.assertEqual(self.release.failed_check_ids, ())
        for check in self.release.checks:
            self.assertTrue(check.passed)
            self.assertTrue(check.evidence_address.startswith("sha256:"))

    def test_quality_and_release_addresses_are_distinct(self) -> None:
        self.assertNotEqual(self.runtime.gate.content_address, self.runtime.release.content_address)
        self.assertNotEqual(self.runtime.bundle.content_address, self.runtime.release.content_address)
        self.assertTrue(self.runtime.gate.content_address.startswith("sha256:"))

    def test_all_review_priorities_have_expected_rows(self) -> None:
        expected = {"critical": 7, "high": 1, "normal": 4, "informational": 4}
        for priority, count in expected.items():
            self.assertEqual(len(self.review.for_priority(priority)), count)

    def test_review_queue_ids_are_prefixed(self) -> None:
        self.assertTrue(all(item.queue_id.startswith("causal-beta-frontier-review:") for item in self.review.items))
        self.assertEqual(len({item.queue_id for item in self.review.items}), 16)

    def test_metrics_state_and_issue_maps_are_sorted(self) -> None:
        self.assertEqual(tuple(self.metrics.state_counts), ("ambiguous", "contradictory", "out_of_domain", "partial", "supported"))
        self.assertEqual(tuple(self.metrics.issue_counts), ("context_mismatch", "contradictory_direction", "minimum_independent_sources", "missing_alternate_allele", "negative_control_conflict", "replicate_ambiguity"))
        self.assertEqual(sum(self.metrics.state_counts.values()), 16)
        self.assertEqual(sum(self.metrics.issue_counts.values()), 12)

    def test_each_operation_metric_has_one_positive(self) -> None:
        for metric in self.metrics.operations:
            self.assertEqual(metric.positive_count, 1)
            self.assertEqual(metric.control_count, 3)
            self.assertEqual(metric.record_count, 4)
            self.assertTrue(metric.accepted)

    def test_content_hashes_are_stable_for_rebuilt_runtime(self) -> None:
        other = run_causal_beta_frontier_runtime(run_id="operational-test")
        self.assertEqual(self.runtime.fixture.content_address, other.fixture.content_address)
        self.assertEqual(self.runtime.evaluation.content_address, other.evaluation.content_address)
        self.assertEqual(self.runtime.metrics.content_address, other.metrics.content_address)
        self.assertEqual(self.runtime.release.content_address, other.release.content_address)
        self.assertEqual(self.runtime.runbook.steps, other.runbook.steps)

    def test_release_bundle_contains_fourteen_core_addresses(self) -> None:
        fields = ("fixture_address", "evaluation_address", "metrics_address", "contracts_address", "schema_address", "lineage_address", "provenance_address", "depth_address", "reconciliation_address", "policy_address", "review_address", "quality_gate_address", "scenario_address", "validation_address")
        addresses = tuple(getattr(self.bundle, name) for name in fields)
        self.assertEqual(len(addresses), 14)
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))

    def test_runbook_required_outputs_are_nonempty(self) -> None:
        for step in self.runbook.steps:
            self.assertTrue(step.purpose)
            self.assertTrue(step.required_output)
            self.assertTrue(step.content_address.startswith("sha256:"))

    def test_runbook_step_lookup_is_exact(self) -> None:
        self.assertEqual(self.runbook.step("audit").command, "causal-beta-frontier-data-audit")
        self.assertEqual(self.runbook.step("exports").command, "export-causal-beta-frontier-json")
        with self.assertRaises(StopIteration):
            self.runbook.step("missing")

    def test_export_summary_payload_contains_release_ids(self) -> None:
        summary = self.exports.by_kind("summary-json").payload
        self.assertEqual(summary["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(summary["bundle_id"], self.bundle.bundle_id)
        self.assertEqual(summary["release_id"], self.release.release_id)
        self.assertEqual(summary["artifact_count"], 16)

    def test_boundary_and_assurance_use_same_fixture(self) -> None:
        self.assertEqual(self.boundary.fixture_id, self.fixture.fixture_id)
        self.assertEqual(self.assurance.fixture_id, self.fixture.fixture_id)
        self.assertEqual(self.exports.fixture_id, self.fixture.fixture_id)
        self.assertEqual(self.runbook.fixture_id, self.fixture.fixture_id)


if __name__ == "__main__":
    unittest.main()
