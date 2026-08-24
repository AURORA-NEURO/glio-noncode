"""Deep unit coverage for the repository-wide module fabric."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from glio_noncode.module_fabric_catalog import (
    default_module_fabric_catalog,
    validate_module_fabric_catalog,
)
from glio_noncode.module_fabric_contracts import FabricReferenceKind, FabricRole, FabricState
from glio_noncode.module_fabric_data_dictionary import default_module_fabric_data_dictionary
from glio_noncode.module_fabric_depth import audit_module_fabric_depth
from glio_noncode.module_fabric_exports import (
    export_module_fabric_review_csv,
    module_fabric_json,
    module_fabric_summary,
    render_module_fabric_review_markdown,
)
from glio_noncode.module_fabric_failures import run_module_fabric_failure_injections
from glio_noncode.module_fabric_fixture_eval import (
    evaluate_module_fabric_fixture,
    execute_module_fabric_record,
)
from glio_noncode.module_fabric_governance import (
    build_module_fabric_review_queue,
    default_module_fabric_claim_boundary,
)
from glio_noncode.module_fabric_lineage import (
    build_module_fabric_lineage,
    verify_module_fabric_lineage,
)
from glio_noncode.module_fabric_metrics import measure_module_fabric, module_fabric_reference_rate
from glio_noncode.module_fabric_observability import (
    build_module_fabric_trace,
    verify_module_fabric_trace,
)
from glio_noncode.module_fabric_operations import evaluate_module_fabric_record
from glio_noncode.module_fabric_public_data import (
    audit_module_fabric_data,
    default_module_fabric_fixture,
    load_module_fabric_fixture,
    module_fabric_fixture_json,
)
from glio_noncode.module_fabric_quality_gate import run_module_fabric_quality_gate
from glio_noncode.module_fabric_release import (
    build_module_fabric_release,
    verify_module_fabric_release,
)
from glio_noncode.module_fabric_replay import replay_module_fabric
from glio_noncode.module_fabric_reports import (
    module_fabric_report,
    render_module_fabric_runtime_markdown,
)
from glio_noncode.module_fabric_runtime import run_module_fabric_runtime
from glio_noncode.module_fabric_scenario_matrix import evaluate_module_fabric_scenarios
from glio_noncode.module_fabric_schema import (
    default_module_fabric_schema,
    validate_module_fabric_schema,
)
from glio_noncode.module_fabric_source_registry import (
    build_module_fabric_source_registry,
    source_registry_for,
)
from glio_noncode.module_fabric_support import (
    all_resolved,
    contains_private_key,
    parse_reference,
    reference_set_receipts,
    resolve_reference,
)


class ModuleFabricTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_module_fabric_fixture()
        cls.evaluation = evaluate_module_fabric_fixture(cls.fixture)

    def test_public_fixture_has_exact_denominator(self) -> None:
        self.assertEqual(len(self.fixture.sources), 5)
        self.assertEqual(len(self.fixture.records), 32)
        self.assertEqual(len(self.fixture.positive_records), 16)
        self.assertEqual(len(self.fixture.control_records), 16)
        self.assertEqual(set(self.fixture.domain_ids), {f"D{i:02d}" for i in range(1, 17)})

    def test_public_data_audit_accepts(self) -> None:
        report = audit_module_fabric_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertTrue(all(item.passed for item in report.checks))

    def test_checked_in_fixture_round_trips(self) -> None:
        path = Path(__file__).parents[1] / "examples" / "module-fabric-public-aggregate.json"
        loaded = load_module_fabric_fixture(path)
        self.assertEqual(loaded.content_address, self.fixture.content_address)
        self.assertEqual(module_fabric_fixture_json(loaded), module_fabric_fixture_json(self.fixture))

    def test_sources_are_public_and_addressed(self) -> None:
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.scope == "public_aggregate" for item in self.fixture.sources))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.fixture.sources))

    def test_reference_parser_distinguishes_module_and_symbol(self) -> None:
        self.assertEqual(parse_reference("tests.test_module_fabric").symbol_name, "test_module_fabric")
        self.assertEqual(parse_reference("glio_noncode.module_fabric_operations.evaluate_module_fabric_record").symbol_name, "evaluate_module_fabric_record")
        self.assertIsNone(resolve_reference("tests.test_module_fabric").parsed.symbol_name)
        self.assertEqual(resolve_reference("glio_noncode.module_fabric_operations.evaluate_module_fabric_record").state.value, "resolved")

    def test_all_declared_references_resolve(self) -> None:
        receipts = []
        from glio_noncode.capability_registry import default_capability_registry

        for record in default_capability_registry().records():
            receipts.extend(reference_set_receipts(record.implementation_modules, FabricReferenceKind.IMPLEMENTATION))
            receipts.extend(reference_set_receipts(record.test_modules, FabricReferenceKind.TEST))
        self.assertTrue(receipts)
        self.assertTrue(all_resolved(receipts))

    def test_evaluation_is_accepted_with_eight_checks_per_record(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(len(self.evaluation.executions), 32)
        self.assertEqual(len(self.evaluation.checks), 394)
        self.assertEqual(self.evaluation.failed_checks, 0)

    def test_positive_and_control_states_remain_separate(self) -> None:
        positives = [item for item in self.evaluation.executions if item.role is FabricRole.POSITIVE]
        controls = [item for item in self.evaluation.executions if item.role is FabricRole.CONTROL]
        self.assertEqual({item.observed_state for item in positives}, {FabricState.ACCEPTED})
        self.assertEqual({item.observed_state for item in controls}, {FabricState.REVIEW})
        self.assertTrue(all("context_mismatch" in item.issue_codes for item in controls))
        self.assertTrue(all("foreign_domain" in item.issue_codes for item in controls))

    def test_execution_receipts_are_sanitized_and_addressed(self) -> None:
        for item in self.evaluation.executions:
            self.assertFalse(contains_private_key(item.output))
            self.assertTrue(item.content_address.startswith("sha256:"))
            self.assertTrue(all(receipt.content_address.startswith("sha256:") for receipt in (*item.implementation_receipts, *item.test_receipts)))

    def test_metrics_conserve_records_and_references(self) -> None:
        metrics = measure_module_fabric(self.fixture, self.evaluation)
        self.assertEqual(metrics.record_count, 32)
        self.assertEqual(metrics.positive_count + metrics.control_count, 32)
        self.assertEqual(metrics.domain_count, 16)
        self.assertEqual(metrics.failed_reference_count, 0)
        self.assertEqual(module_fabric_reference_rate(metrics), 1.0)
        self.assertEqual(sum(item["records"] for item in metrics.by_domain.values()), 32)

    def test_depth_audit_is_complete(self) -> None:
        report = audit_module_fabric_depth(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 30)
        self.assertEqual(report.failed_checks, 0)

    def test_lineage_is_closed_without_orphans(self) -> None:
        lineage = build_module_fabric_lineage(self.fixture, self.evaluation)
        self.assertTrue(lineage.accepted)
        self.assertEqual(verify_module_fabric_lineage(lineage), ())
        self.assertGreater(len(lineage.nodes), 300)
        self.assertGreater(len(lineage.edges), len(lineage.nodes))

    def test_replay_is_deterministic(self) -> None:
        first = replay_module_fabric(self.fixture)
        second = replay_module_fabric(self.fixture)
        self.assertTrue(first.accepted)
        self.assertEqual(first.content_address, second.content_address)
        self.assertTrue(all(item.passed for item in first.checks))

    def test_quality_gate_and_release_are_accepted(self) -> None:
        quality = run_module_fabric_quality_gate(self.fixture)
        release = build_module_fabric_release(self.fixture)
        self.assertTrue(quality.accepted)
        self.assertEqual(release.state, FabricState.ACCEPTED)
        self.assertEqual(verify_module_fabric_release(release), ())
        self.assertGreaterEqual(len(release.artifacts), 8)

    def test_scenario_matrix_has_every_record(self) -> None:
        matrix = evaluate_module_fabric_scenarios(self.fixture, self.evaluation)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 32)
        self.assertTrue(all(item.passed for item in matrix.cells))

    def test_schema_and_dictionary_are_closed(self) -> None:
        schema = default_module_fabric_schema()
        dictionary = default_module_fabric_data_dictionary()
        self.assertEqual(validate_module_fabric_schema(schema), ())
        self.assertGreaterEqual(len(schema.fields), 15)
        self.assertGreaterEqual(len(dictionary.entries), 12)
        self.assertTrue(any(not item.public_projection for item in dictionary.entries))

    def test_contract_catalog_has_sixteen_domains(self) -> None:
        catalog = default_module_fabric_catalog()
        self.assertEqual(validate_module_fabric_catalog(catalog), ())
        self.assertEqual(len(catalog.domains), 16)
        self.assertTrue(all(item.capability_count == 16 for item in catalog.domains))

    def test_source_registry_closes_receipts(self) -> None:
        registry = build_module_fabric_source_registry(self.fixture)
        self.assertTrue(registry.accepted)
        self.assertEqual(len(registry.entries), 5)
        self.assertIsNotNone(source_registry_for("blueprint-receipt", registry))
        self.assertIsNone(source_registry_for("missing", registry))

    def test_governance_boundary_and_review_queue(self) -> None:
        boundary = default_module_fabric_claim_boundary()
        queue = build_module_fabric_review_queue(self.fixture, self.evaluation)
        self.assertEqual(boundary.boundary, "public_aggregate_module_integration")
        self.assertEqual(len(queue.items), 16)
        self.assertTrue(all(item.priority >= 1 for item in queue.items))

    def test_exports_are_public_and_stable(self) -> None:
        csv_text = export_module_fabric_review_csv(self.fixture, self.evaluation)
        markdown = render_module_fabric_review_markdown(self.fixture, self.evaluation)
        payload = json.loads(module_fabric_json(self.fixture, self.evaluation))
        summary = module_fabric_summary(self.fixture, self.evaluation)
        self.assertEqual(len(csv_text.splitlines()), 33)
        self.assertIn("# Module Fabric Review", markdown)
        self.assertEqual(payload["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(summary["failed_checks"], 0)
        self.assertNotIn("payload", csv_text)

    def test_runtime_is_ordered_and_accepted(self) -> None:
        report = run_module_fabric_runtime(self.fixture)
        self.assertEqual(report.state, FabricState.ACCEPTED)
        self.assertEqual(len(report.stages), 24)
        self.assertEqual(tuple(item.ordinal for item in report.stages), tuple(range(1, 25)))
        trace = build_module_fabric_trace(report)
        self.assertTrue(trace.accepted)
        self.assertEqual(verify_module_fabric_trace(trace), ())
        self.assertEqual(module_fabric_report(report)["stage_count"], 24)
        self.assertIn("# Module Fabric Runtime Report", render_module_fabric_runtime_markdown(report))

    def test_compliance_closes_the_runtime_boundary(self) -> None:
        report = run_module_fabric_runtime(self.fixture)
        self.assertTrue(report.compliance.accepted)
        self.assertEqual(len(report.compliance.checks), 12)
        self.assertEqual(report.compliance.forbidden_paths, ())

    def test_runtime_evaluation_and_trace_denominators_are_closed(self) -> None:
        report = run_module_fabric_runtime(self.fixture)
        self.assertEqual(len(report.evaluation.checks), 394)
        trace = build_module_fabric_trace(report)
        self.assertEqual(len(trace.observations), 24)

    def test_failure_probes_are_conservative(self) -> None:
        report = run_module_fabric_failure_injections()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.probes), 4)
        self.assertTrue(all(item.passed for item in report.probes))

    def test_mutated_positive_context_is_reviewed(self) -> None:
        record = self.fixture.positive_records[0]
        mutated = replace(record, payload={**record.payload, "declared_context_key": "foreign-context"})
        result = evaluate_module_fabric_record(mutated)
        self.assertEqual(result.state, FabricState.REVIEW)
        self.assertIn("context_mismatch", result.issue_codes)

    def test_record_execution_is_stable(self) -> None:
        record = self.fixture.positive_records[0]
        first = execute_module_fabric_record(record)
        second = execute_module_fabric_record(record)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.output, second.output)


if __name__ == "__main__":
    unittest.main()
