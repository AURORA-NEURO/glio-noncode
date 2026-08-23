"""Deep focused tests for the D01 variant identity and intake architecture."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.capability_registry import CapabilityState, default_capability_registry
from glio_noncode.intake_architecture_access import build_intake_architecture_access_manifest
from glio_noncode.intake_architecture_bundle import (
    build_intake_architecture_artifacts,
    build_intake_architecture_release,
    verify_intake_architecture_release,
)
from glio_noncode.intake_architecture_completeness import score_intake_completeness
from glio_noncode.intake_architecture_contracts import (
    INTAKE_ARCHITECTURE_BOUNDARY,
    INTAKE_ARCHITECTURE_CASE_COUNT,
    INTAKE_ARCHITECTURE_CONTEXT,
    INTAKE_ARCHITECTURE_OPERATION_COUNT,
    IntakeArchitectureOperation,
    IntakeArchitectureScenario,
    IntakeArchitectureState,
)
from glio_noncode.intake_architecture_depth import audit_intake_architecture_depth
from glio_noncode.intake_architecture_exports import intake_architecture_report_markdown, intake_architecture_runtime_json
from glio_noncode.intake_architecture_failures import run_intake_architecture_failure_injections
from glio_noncode.intake_architecture_identity import (
    check_batch_identity,
    reconcile_aliases,
    resolve_intake_architecture_identity,
    resolve_public_identity,
)
from glio_noncode.intake_architecture_invariants import intake_architecture_invariants
from glio_noncode.intake_architecture_lineage import build_intake_architecture_lineage, verify_intake_architecture_lineage
from glio_noncode.intake_architecture_metrics import measure_intake_architecture
from glio_noncode.intake_architecture_normalization import (
    normalize_cat_vrs,
    normalize_intake_architecture_case,
    normalize_repeat,
    normalize_vrs,
)
from glio_noncode.intake_architecture_operations import evaluate_intake_architecture_fixture
from glio_noncode.intake_architecture_parsing import (
    parse_intake_architecture_case,
    parse_multiallelic,
    parse_regulatory_track,
    parse_variant_text,
)
from glio_noncode.intake_architecture_plan import audit_intake_architecture_plan, compile_intake_architecture_plan
from glio_noncode.intake_architecture_policy import evaluate_intake_policy
from glio_noncode.intake_architecture_provenance import build_intake_architecture_ledger, verify_intake_architecture_ledger
from glio_noncode.intake_architecture_public_data import (
    audit_intake_architecture_data,
    default_intake_architecture_fixture,
    intake_architecture_fixture_json,
)
from glio_noncode.intake_architecture_query import query_intake_architecture
from glio_noncode.intake_architecture_quarantine import build_intake_quarantine
from glio_noncode.intake_architecture_replay import replay_intake_architecture
from glio_noncode.intake_architecture_review import build_intake_architecture_review_queue, intake_review_csv
from glio_noncode.intake_architecture_runbook import build_intake_architecture_runbook
from glio_noncode.intake_architecture_runtime import run_intake_architecture
from glio_noncode.intake_architecture_schema import default_intake_architecture_schema, validate_intake_architecture_schema
from glio_noncode.intake_architecture_observability import audit_intake_architecture_trace, build_intake_architecture_trace
from glio_noncode.intake_architecture_validation import build_intake_architecture_validation_matrix
from glio_noncode.intake_architecture_quality import run_intake_architecture_quality_gate


class IntakeArchitectureFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_intake_architecture_fixture()
        cls.runtime = run_intake_architecture(cls.fixture)
        cls.evaluation = cls.runtime.evaluation
        cls.quality = run_intake_architecture_quality_gate(cls.runtime)

    def test_closed_boundary(self) -> None:
        self.assertEqual(self.fixture.boundary, INTAKE_ARCHITECTURE_BOUNDARY)
        self.assertEqual(self.fixture.context_key, INTAKE_ARCHITECTURE_CONTEXT)
        self.assertEqual(len(self.fixture.operations), INTAKE_ARCHITECTURE_OPERATION_COUNT)
        self.assertEqual(len(self.fixture.cases), INTAKE_ARCHITECTURE_CASE_COUNT)

    def test_public_sources(self) -> None:
        self.assertEqual(len(self.fixture.sources), 6)
        self.assertTrue(all(item.uri.startswith("https://") for item in self.fixture.sources))
        self.assertTrue(all(item.scope == "public_aggregate" for item in self.fixture.sources))
        self.assertEqual(len({item.source_id for item in self.fixture.sources}), 6)

    def test_operation_order_and_joins(self) -> None:
        self.assertEqual([item.ordinal for item in self.fixture.operations], list(range(1, 17)))
        self.assertEqual(self.fixture.operations[0].dependencies, ())
        self.assertEqual(self.fixture.operations[-1].dependencies, ("INTAKE-D01-C15",))
        source_ids = {item.source_id for item in self.fixture.sources}
        self.assertTrue(all(set(item.source_ids) <= source_ids for item in self.fixture.cases))

    def test_case_cardinality_and_scenarios(self) -> None:
        for spec in self.fixture.operations:
            rows = tuple(item for item in self.fixture.cases if item.operation_id == spec.operation_id)
            self.assertEqual(len(rows), 4)
            self.assertEqual({item.scenario for item in rows}, set(IntakeArchitectureScenario))
        self.assertEqual(len(self.fixture.positive_cases), 16)
        self.assertEqual(len(self.fixture.control_cases), 48)

    def test_data_audit(self) -> None:
        report = audit_intake_architecture_data(self.fixture)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.checks), 12)
        self.assertTrue(all(check.passed for check in report.checks))

    def test_fixture_json_is_stable(self) -> None:
        first = intake_architecture_fixture_json(self.fixture)
        second = intake_architecture_fixture_json(self.fixture)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["content_address"], self.fixture.content_address)
        self.assertEqual(len(payload["cases"]), 64)

    def test_source_receipt_addresses(self) -> None:
        self.assertTrue(all(":" in item.content_address for item in self.fixture.sources))
        self.assertTrue(all(":" in item.content_address for item in self.fixture.operations))
        self.assertTrue(all(":" in item.content_address for item in self.fixture.cases))

    def test_payloads_are_aggregate_only(self) -> None:
        serialized = json.dumps(self.fixture.to_dict(), sort_keys=True).lower()
        for token in ("patient_id", "participant_id", "medical_record_number", "email", "phone"):
            self.assertNotIn(token, serialized)

    def test_public_identifiers_are_present(self) -> None:
        self.assertTrue(all(item.public_identifier.startswith("public:") for item in self.fixture.cases))
        self.assertIn("dbsnp:rs429358", self.fixture.cases[0].payload["public_identifiers"])


class IntakeArchitectureExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_intake_architecture_fixture()
        cls.runtime = run_intake_architecture(cls.fixture)
        cls.evaluation = cls.runtime.evaluation

    def test_evaluation_is_accepted(self) -> None:
        self.assertTrue(self.evaluation.accepted)
        self.assertEqual(self.evaluation.passed_cases, 64)
        self.assertEqual(self.evaluation.failed_cases, 0)

    def test_positive_cases_are_accepted(self) -> None:
        positive = tuple(item for item in self.evaluation.results if item.scenario is IntakeArchitectureScenario.POSITIVE)
        self.assertEqual(len(positive), 16)
        self.assertTrue(all(item.observed_state is IntakeArchitectureState.ACCEPTED for item in positive))
        self.assertTrue(all(not item.issue_codes for item in positive))

    def test_controls_are_held(self) -> None:
        controls = tuple(item for item in self.evaluation.results if item.scenario is not IntakeArchitectureScenario.POSITIVE)
        self.assertEqual(len(controls), 48)
        self.assertTrue(all(item.observed_state is IntakeArchitectureState.REVIEW for item in controls))
        self.assertEqual({item.issue_codes for item in controls}, {("foreign_context",), ("malformed_input",), ("duplicate_identity",)})

    def test_each_operation_has_a_positive_receipt(self) -> None:
        positive = tuple(item for item in self.evaluation.results if item.scenario is IntakeArchitectureScenario.POSITIVE)
        self.assertTrue(all(item.receipt_addresses for item in positive))
        self.assertEqual(sum(len(item.receipt_addresses) for item in positive), 16)

    def test_runtime_has_twenty_stages(self) -> None:
        self.assertEqual(len(self.runtime.stages), 20)
        self.assertEqual([item.ordinal for item in self.runtime.stages], list(range(1, 21)))
        self.assertEqual(self.runtime.state, IntakeArchitectureState.ACCEPTED)

    def test_runtime_stage_addresses(self) -> None:
        self.assertTrue(all(":" in item.input_address for item in self.runtime.stages))
        self.assertTrue(all(":" in item.output_address for item in self.runtime.stages))
        self.assertEqual(len({item.content_address for item in self.runtime.stages}), 20)

    def test_quality_has_eighteen_passing_checks(self) -> None:
        quality = run_intake_architecture_quality_gate(self.runtime)
        self.assertTrue(quality.accepted)
        self.assertEqual(quality.passed_checks, 18)
        self.assertEqual(quality.failed_checks, 0)
        self.assertTrue(all(item.passed for item in quality.checks))

    def test_review_queue_is_complete(self) -> None:
        queue = self.runtime.review_queue
        self.assertTrue(queue.accepted)
        self.assertEqual(len(queue.items), 48)
        self.assertEqual(len({item.case_id for item in queue.items}), 48)
        self.assertTrue(all(item.state is IntakeArchitectureState.REVIEW for item in queue.items))

    def test_review_csv_is_sanitized(self) -> None:
        csv_text = intake_review_csv(self.runtime.review_queue)
        self.assertTrue(csv_text.startswith("review_id,case_id,operation_id"))
        self.assertEqual(len(csv_text.splitlines()), 49)
        self.assertNotIn("raw_text", csv_text)

    def test_ledger_cardinality_and_links(self) -> None:
        self.assertEqual(len(self.runtime.ledger.events), 64)
        self.assertEqual(verify_intake_architecture_ledger(self.runtime.ledger), ())
        self.assertTrue(self.runtime.ledger.accepted)
        self.assertEqual(self.runtime.ledger.events[0].previous_address, "genesis:intake-d01")
        self.assertEqual(self.runtime.ledger.events[-1].ordinal, 64)

    def test_bundle_and_release(self) -> None:
        self.assertEqual(len(self.runtime.artifacts), 5)
        self.assertTrue(all(item.offline_capable for item in self.runtime.artifacts))
        self.assertEqual(self.runtime.release.state, IntakeArchitectureState.ACCEPTED)
        self.assertEqual(verify_intake_architecture_release(self.runtime.release), ())
        self.assertEqual(len(self.runtime.release.artifact_addresses), 5)

    def test_validation_matrix(self) -> None:
        matrix = build_intake_architecture_validation_matrix(self.fixture)
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.cells), 112)
        self.assertTrue(all(cell.passed for cell in matrix.cells))

    def test_replay(self) -> None:
        replay = replay_intake_architecture(self.fixture)
        self.assertTrue(replay["accepted"])
        self.assertTrue(replay["deterministic"])
        self.assertEqual(replay["first_address"], replay["second_address"])

    def test_depth(self) -> None:
        report = audit_intake_architecture_depth(self.runtime)
        self.assertTrue(report.accepted)
        self.assertEqual(report.operation_count, 16)
        self.assertEqual(report.case_count, 64)
        self.assertEqual(report.stage_count, 20)
        self.assertEqual(report.receipt_count, 16)

    def test_metrics(self) -> None:
        metrics = measure_intake_architecture(self.runtime)
        self.assertEqual(metrics.total_cases, 64)
        self.assertEqual(metrics.positive_cases, 16)
        self.assertEqual(metrics.control_cases, 48)
        self.assertEqual(metrics.accepted_cases, 16)
        self.assertEqual(metrics.held_cases, 48)
        self.assertEqual(len(metrics.operation_metrics), 16)
        self.assertTrue(all(item.total_cases == 4 for item in metrics.operation_metrics))

    def test_lineage(self) -> None:
        lineage = build_intake_architecture_lineage(self.runtime)
        self.assertTrue(lineage.accepted)
        self.assertEqual(verify_intake_architecture_lineage(lineage), ())
        self.assertGreaterEqual(len(lineage.nodes), 16)

    def test_trace(self) -> None:
        trace = build_intake_architecture_trace(self.runtime)
        self.assertTrue(trace.accepted)
        self.assertEqual(len(trace.events), 20)
        self.assertEqual(audit_intake_architecture_trace(trace), ())
        self.assertTrue(all("subject_id" not in event.to_dict() for event in trace.events))

    def test_access_manifest(self) -> None:
        manifest = build_intake_architecture_access_manifest(self.runtime)
        self.assertTrue(manifest.accepted)
        self.assertEqual(len(manifest.entries), 5)
        self.assertTrue(all(item.scope == "public_aggregate" for item in manifest.entries))
        self.assertTrue(all(not item.write_allowed and not item.network_allowed for item in manifest.entries))

    def test_query(self) -> None:
        result = query_intake_architecture(self.runtime, "review")
        self.assertEqual(result["matched"], 48)
        self.assertTrue(all(item["state"] == "review" for item in result["results"]))
        empty = query_intake_architecture(self.runtime, "does-not-exist")
        self.assertEqual(empty["matched"], 0)

    def test_report_projections(self) -> None:
        runtime_json = intake_architecture_runtime_json(self.runtime)
        self.assertEqual(json.loads(runtime_json)["state"], "accepted")
        markdown = intake_architecture_report_markdown(self.runtime)
        self.assertIn("D01 Variant Identity", markdown)
        self.assertIn("64", markdown)

    def test_runbook(self) -> None:
        runbook = build_intake_architecture_runbook(self.runtime)
        self.assertTrue(runbook["accepted"])
        self.assertEqual(runbook["rollback"], "d01.2026.07.1")
        self.assertIn("verify HTTPS receipts", runbook["preflight"])

    def test_invariants(self) -> None:
        self.assertEqual(intake_architecture_invariants(self.runtime), ())

    def test_failure_injections(self) -> None:
        report = run_intake_architecture_failure_injections()
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.probes), 3)
        self.assertTrue(all(probe.passed for probe in report.probes))


class IntakeArchitecturePrimitiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = default_intake_architecture_fixture()
        cls.by_operation = {case.operation_id: case for case in fixture.positive_cases}

    def test_vcf_parser(self) -> None:
        case = self.by_operation["INTAKE-D01-C02"]
        receipt = parse_intake_architecture_case(case)
        self.assertEqual(receipt.input_format, "vcf")
        self.assertEqual(receipt.record_count, 1)
        self.assertEqual(receipt.accepted_count, 1)
        self.assertEqual(receipt.issue_codes, ())

    def test_vcf_malformed_control(self) -> None:
        case = next(
            item
            for item in default_intake_architecture_fixture().cases
            if item.operation_id == "INTAKE-D01-C02" and item.scenario is IntakeArchitectureScenario.MALFORMED_INPUT
        )
        receipt = parse_intake_architecture_case(case)
        self.assertIn("malformed_input", receipt.issue_codes)
        self.assertEqual(receipt.state, IntakeArchitectureState.REVIEW)

    def test_raw_variant_parser(self) -> None:
        text = "##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n7\t55249063\trs429358\tT\tC\t.\tPASS\t.\n"
        counts = parse_variant_text(text, source_id="public-test", input_format="vcf")
        self.assertEqual(counts[:4], (1, 1, 0, ()))
        self.assertIn(":", counts[4])

    def test_regulatory_track_parser(self) -> None:
        text = "chrom\tstart\tend\tname\tscore\nchr7\t1\t3\tpublic-window\t1\n"
        self.assertEqual(parse_regulatory_track(text)[:3], (1, 1, ()))
        bad = "chrom\tstart\tend\tname\nchr7\t3\t1\tbad\n"
        self.assertEqual(parse_regulatory_track(bad)[:3], (1, 0, ("malformed_input",)))

    def test_multiallelic_decomposition(self) -> None:
        count = parse_multiallelic({"variant_id": "public-multi", "chromosome": "7", "position": 55249063, "reference": "T", "alternates": ["C", "G"], "genotype": "1/2"})
        self.assertEqual(count[:3], (2, 2, ()))

    def test_vrs_normalization(self) -> None:
        case = self.by_operation["INTAKE-D01-C04"]
        result = normalize_vrs(case.payload)
        self.assertEqual(result[0], 1)
        self.assertEqual(result[2], IntakeArchitectureState.ACCEPTED)
        self.assertIsNotNone(result[1])

    def test_cat_vrs_normalization(self) -> None:
        case = self.by_operation["INTAKE-D01-C05"]
        result = normalize_cat_vrs(case.payload)
        self.assertEqual(result[0], 1)
        self.assertEqual(result[2], IntakeArchitectureState.ACCEPTED)
        self.assertIsNotNone(result[1])

    def test_repeat_normalization(self) -> None:
        case = self.by_operation["INTAKE-D01-C08"]
        result = normalize_repeat(case.payload)
        self.assertGreaterEqual(result[0], 1)
        self.assertEqual(result[2], IntakeArchitectureState.ACCEPTED)

    def test_normalization_receipt_dispatch(self) -> None:
        for operation_id in ("INTAKE-D01-C04", "INTAKE-D01-C05", "INTAKE-D01-C08"):
            receipt = normalize_intake_architecture_case(self.by_operation[operation_id])
            self.assertEqual(receipt.state, IntakeArchitectureState.ACCEPTED)
            self.assertIn(":", receipt.content_address)

    def test_equivalence_resolution(self) -> None:
        case = self.by_operation["INTAKE-D01-C09"]
        result = resolve_public_identity(case.payload, case.source_ids[0])
        self.assertEqual(result[0], 1)
        self.assertEqual(result[1], 1)
        self.assertEqual(result[4], IntakeArchitectureState.ACCEPTED)

    def test_alias_reconciliation(self) -> None:
        case = self.by_operation["INTAKE-D01-C10"]
        result = reconcile_aliases(case.payload, case.source_ids[0])
        self.assertEqual(result[0], 2)
        self.assertEqual(result[2], IntakeArchitectureState.ACCEPTED)
        self.assertIn("duplicate_identity", result[1])

    def test_batch_identity(self) -> None:
        case = self.by_operation["INTAKE-D01-C11"]
        result = check_batch_identity(case.payload)
        self.assertEqual(result[0], IntakeArchitectureState.ACCEPTED)
        self.assertEqual(result[1], ())

    def test_identity_receipt_dispatch(self) -> None:
        fixture = default_intake_architecture_fixture()
        for operation_id in ("INTAKE-D01-C09", "INTAKE-D01-C10", "INTAKE-D01-C11"):
            case = next(item for item in fixture.positive_cases if item.operation_id == operation_id)
            receipt = resolve_intake_architecture_identity(case)
            self.assertEqual(receipt.state, IntakeArchitectureState.ACCEPTED)

    def test_policy_positive(self) -> None:
        fixture = default_intake_architecture_fixture()
        decision = evaluate_intake_policy(next(item for item in fixture.positive_cases if item.operation_id == "INTAKE-D01-C13"))
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.state, IntakeArchitectureState.ACCEPTED)

    def test_policy_foreign_control(self) -> None:
        fixture = default_intake_architecture_fixture()
        case = next(item for item in fixture.cases if item.operation_id == "INTAKE-D01-C13" and item.scenario is IntakeArchitectureScenario.FOREIGN_CONTEXT)
        decision = evaluate_intake_policy(case)
        self.assertFalse(decision.allowed)
        self.assertIn("context_mismatch", decision.reasons)

    def test_completeness_positive(self) -> None:
        fixture = default_intake_architecture_fixture()
        score = score_intake_completeness(next(item for item in fixture.positive_cases if item.operation_id == "INTAKE-D01-C15"))
        self.assertEqual(score.score, 1.0)
        self.assertEqual(score.missing_fields, ())

    def test_quarantine_controls(self) -> None:
        fixture = default_intake_architecture_fixture()
        report = build_intake_quarantine(fixture.cases)
        self.assertTrue(report.accepted)
        self.assertEqual(len(report.items), 48)
        self.assertTrue(all(item.disposition == "held_for_review" for item in report.items))

    def test_plan_audit(self) -> None:
        plan = compile_intake_architecture_plan(default_intake_architecture_fixture())
        self.assertTrue(plan.accepted)
        self.assertEqual(audit_intake_architecture_plan(plan), ())

    def test_schema(self) -> None:
        schema = default_intake_architecture_schema()
        self.assertTrue(schema.accepted)
        self.assertEqual(len(schema.fields), 11)
        self.assertEqual(validate_intake_architecture_schema(schema), ())

    def test_capability_registry_d01_is_wired(self) -> None:
        registry = default_capability_registry()
        records = {item.spec.capability_id: item for item in registry.records()}
        for number in range(1, 17):
            record = records[f"GNC-D01-C{number:02d}"]
            self.assertEqual(record.state, CapabilityState.VERIFIED)
            self.assertIn("tests.test_intake_architecture", record.test_modules)
            self.assertTrue(any("intake_architecture" in value for value in record.implementation_modules))

    def test_no_new_metadata_attribution_fields(self) -> None:
        root = Path(__file__).parents[1] / "src" / "glio_noncode"
        files = tuple(root.glob("intake_architecture_*.py"))
        combined = "\n".join(path.read_text(encoding="utf-8") for path in files).lower()
        forbidden = ("agent" + "_id", "generated" + "_by", "model" + "_name", "author" + "_name", "programming" + "_language")
        for token in forbidden:
            self.assertNotIn(token, combined)


if __name__ == "__main__":
    unittest.main()
