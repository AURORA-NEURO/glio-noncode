from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode import (
    SEQUENCE_REGULATION_CONTEXT_KEY,
    SequenceRegulationOperation,
    SequenceRegulationState,
    audit_sequence_regulation_boundary,
    audit_sequence_regulation_data,
    build_sequence_regulation_adapters,
    build_sequence_regulation_catalog,
    build_sequence_regulation_contracts,
    build_sequence_regulation_receipt_rows,
    build_sequence_regulation_source_registry,
    build_sequence_regulation_summary,
    default_sequence_regulation_fixture,
    evaluate_sequence_regulation_fixture,
    render_sequence_regulation_metrics_csv,
    render_sequence_regulation_receipts_csv,
    render_sequence_regulation_summary_markdown,
    run_sequence_regulation_frontier_pipeline,
    verify_sequence_regulation_source_registry,
    verify_sequence_regulation_summary,
)
from glio_noncode.cli import main


class SequenceRegulationFrontierTests(unittest.TestCase):
    def test_fixture_is_public_closed_and_complete(self) -> None:
        fixture = default_sequence_regulation_fixture()
        self.assertEqual(fixture.context_key, SEQUENCE_REGULATION_CONTEXT_KEY)
        self.assertEqual(len(fixture.sources), 4)
        self.assertEqual(len(fixture.records), 16)
        self.assertEqual(len(fixture.positive_records), 4)
        self.assertEqual(len(fixture.control_records), 12)
        self.assertTrue(audit_sequence_regulation_data(fixture).accepted)
        self.assertTrue(audit_sequence_regulation_boundary(fixture).accepted)
        self.assertTrue(fixture.content_address.startswith("sha256:"))

    def test_each_operation_has_positive_and_controls(self) -> None:
        fixture = default_sequence_regulation_fixture()
        for operation in SequenceRegulationOperation:
            records = fixture.operation_records(operation)
            self.assertEqual(len(records), 4)
            self.assertEqual(sum(record.role.value == "positive" for record in records), 1)
            self.assertEqual(sum(record.role.value == "control" for record in records), 3)

    def test_evaluation_matches_all_expected_paths(self) -> None:
        evaluation = evaluate_sequence_regulation_fixture(default_sequence_regulation_fixture())
        self.assertTrue(evaluation.accepted)
        self.assertEqual(evaluation.state_match_count, 16)
        self.assertEqual(evaluation.issue_match_count, 16)
        self.assertEqual(evaluation.failed_record_ids, ())
        self.assertEqual(
            {item.observed_state for item in evaluation.records},
            {
                SequenceRegulationState.SUPPORTED,
                SequenceRegulationState.PARTIAL,
                SequenceRegulationState.INVALID,
                SequenceRegulationState.ABSTAINED,
                SequenceRegulationState.OUT_OF_DOMAIN,
            },
        )

    def test_registry_contracts_and_adapters_cover_all_operations(self) -> None:
        contracts = build_sequence_regulation_contracts()
        adapters = build_sequence_regulation_adapters()
        self.assertTrue(contracts.accepted)
        self.assertTrue(adapters.accepted)
        self.assertEqual(contracts.unique_operations, 4)
        self.assertEqual(len(adapters.specs), 4)
        self.assertEqual(
            {spec.operation for spec in adapters.specs}, set(SequenceRegulationOperation)
        )

    def test_catalog_contains_all_receipts_and_issue_paths(self) -> None:
        fixture = default_sequence_regulation_fixture()
        catalog = build_sequence_regulation_catalog(fixture)
        self.assertEqual(
            set(catalog.operations), {operation.value for operation in SequenceRegulationOperation}
        )
        self.assertEqual(len(catalog.record_ids), 16)
        self.assertEqual(len(catalog.source_ids), 4)
        self.assertIn("context_mismatch", catalog.issue_codes)
        self.assertTrue(catalog.content_address.startswith("sha256:"))

    def test_source_registry_matches_all_declared_receipts(self) -> None:
        registry = build_sequence_regulation_source_registry()
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.profiles), 4)
        self.assertEqual(len(registry.matches), 4)
        self.assertEqual(verify_sequence_regulation_source_registry(registry), ())
        self.assertTrue(
            all(profile.expected_checksum.startswith("sha256:") for profile in registry.profiles)
        )

    def test_summary_reports_include_operation_and_state_breakdowns(self) -> None:
        fixture = default_sequence_regulation_fixture()
        evaluation = evaluate_sequence_regulation_fixture(fixture)
        summary = build_sequence_regulation_summary(fixture, evaluation)
        self.assertTrue(summary.accepted)
        self.assertEqual(summary.record_count, 16)
        self.assertEqual(summary.review_count, 0)
        self.assertEqual(
            summary.operation_ids,
            tuple(operation.value for operation in SequenceRegulationOperation),
        )
        self.assertEqual(verify_sequence_regulation_summary(summary), ())
        self.assertEqual(len(build_sequence_regulation_receipt_rows(evaluation)), 16)

    def test_summary_csv_and_markdown_are_stable(self) -> None:
        fixture = default_sequence_regulation_fixture()
        evaluation = evaluate_sequence_regulation_fixture(fixture)
        summary = build_sequence_regulation_summary(fixture, evaluation)
        rows = build_sequence_regulation_receipt_rows(evaluation)
        metrics_csv = render_sequence_regulation_metrics_csv(summary)
        receipts_csv = render_sequence_regulation_receipts_csv(rows)
        markdown = render_sequence_regulation_summary_markdown(summary)
        self.assertTrue(metrics_csv.startswith("metric_id,label,value,detail\n"))
        self.assertTrue(
            receipts_csv.startswith(
                "record_id,operation,role,state,issue_codes,result_address,release_allowed\n"
            )
        )
        self.assertIn("# Sequence regulation frontier summary", markdown)
        self.assertIn("nucleosome_propensity", markdown)
        self.assertEqual(metrics_csv, render_sequence_regulation_metrics_csv(summary))

    def test_pipeline_exposes_deep_release_surfaces(self) -> None:
        report = run_sequence_regulation_frontier_pipeline()
        self.assertTrue(report.accepted)
        self.assertTrue(report.runtime.accepted)
        self.assertTrue(report.quality.accepted)
        self.assertTrue(report.release.accepted)
        self.assertTrue(report.bundle.accepted)
        self.assertTrue(report.artifacts.accepted)
        self.assertTrue(report.view.accepted)
        self.assertTrue(report.trace.accepted)
        self.assertTrue(report.accessibility.accepted)
        self.assertTrue(report.boundary.accepted)
        self.assertTrue(report.invariants.accepted)
        self.assertTrue(report.scenarios.accepted)
        self.assertTrue(report.thresholds.accepted)
        self.assertTrue(report.validation.accepted)
        self.assertTrue(report.replay.accepted)
        self.assertEqual(len(report.runtime.stages), 10)
        self.assertEqual(len(report.addresses()), 19)
        self.assertEqual(len(report.evaluation.records), 16)

    def test_pipeline_serializes_without_subject_fields(self) -> None:
        report = run_sequence_regulation_frontier_pipeline()
        payload = report.to_dict()
        serialized = json.dumps(payload, sort_keys=True)
        self.assertTrue(all("patient" not in record.payload for record in report.fixture.records))
        self.assertTrue(all("subject" not in record.payload for record in report.fixture.records))
        self.assertIn("sequence-regulation-frontier-public-aggregate", serialized)
        self.assertIn("sha256:", serialized)

    def test_cli_emits_fixture_and_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture_path = root / "fixture.json"
            pipeline_path = root / "pipeline.json"
            self.assertEqual(
                main(["sequence-regulation-fixture", "--output", str(fixture_path)]), 0
            )
            self.assertEqual(
                main(["run-sequence-regulation-pipeline", "--output", str(pipeline_path)]), 0
            )
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
            self.assertEqual(len(fixture["records"]), 16)
            self.assertTrue(pipeline["accepted"])
            self.assertEqual(len(pipeline["runtime"]["stages"]), 10)


if __name__ == "__main__":
    unittest.main()
