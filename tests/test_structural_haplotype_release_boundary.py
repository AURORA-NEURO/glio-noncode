"""Release-boundary invariants for Domain 02 C09-C12."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.structural_haplotype_bundle import (
    StructuralHaplotypeBundleFormat,
    StructuralHaplotypeEvidenceBundleBuilder,
)
from glio_noncode.structural_haplotype_fixture_eval import evaluate_structural_haplotype_fixture
from glio_noncode.structural_haplotype_lineage import build_structural_haplotype_lineage
from glio_noncode.structural_haplotype_public_data import (
    StructuralHaplotypeFixtureCatalog,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
    audit_structural_haplotype_fixture,
)
from glio_noncode.structural_haplotype_quality_gate import (
    evaluate_structural_haplotype_quality_gate,
)
from glio_noncode.structural_haplotype_replay import (
    StructuralHaplotypeReplayExpectation,
    replay_structural_haplotype_fixtures,
)
from glio_noncode.structural_haplotype_runtime import (
    StructuralHaplotypePipelineState,
    run_structural_haplotype_pipeline,
)
from glio_noncode.structural_haplotype_scenario_matrix import (
    evaluate_structural_haplotype_scenarios,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "structural-haplotype-public-aggregate.json"
PIPELINE = ROOT / "examples" / "structural-haplotype-pipeline-accepted.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCE_IDS = (
    "ncbi-dbvar-haplotype",
    "gnomad-sv-v4",
    "ncbi-dbvar-study-browser",
    "ncbi-dbvar-ftp-manifest",
)
SORTED_SOURCE_IDS = tuple(sorted(SOURCE_IDS))


def _raw_fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class StructuralHaplotypeReleaseBoundaryTests(unittest.TestCase):
    def test_catalog_audit_is_the_narrow_public_boundary(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        report = audit_structural_haplotype_fixture(catalog)
        self.assertEqual(report.state, StructuralHaplotypeFixtureState.ACCEPTED)
        self.assertTrue(report.accepted)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.source_ids, SORTED_SOURCE_IDS)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertEqual(report.issue_codes, ())
        self.assertRegex(report.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_catalog_operations_have_one_positive_and_two_controls_each(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        for operation in StructuralHaplotypeOperation:
            positives = [record for record in catalog.positives if record.operation == operation]
            controls = [record for record in catalog.controls if record.operation == operation]
            self.assertEqual(len(positives), 1, operation)
            self.assertEqual(len(controls), 2, operation)
            self.assertTrue(all(record.source_id in SOURCE_IDS for record in positives + controls))
            self.assertTrue(all(record.context_key == CONTEXT for record in positives + controls))

    def test_source_receipts_are_http_public_aggregate_records(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        self.assertEqual(tuple(source.source_id for source in catalog.sources), SOURCE_IDS)
        self.assertTrue(all(source.url.startswith("https://") for source in catalog.sources))
        self.assertTrue(all(not source.patient_level for source in catalog.sources))
        self.assertTrue(all(source.license for source in catalog.sources))
        self.assertTrue(all(source.data_scope for source in catalog.sources))

    def test_evaluation_has_one_addressed_receipt_for_every_catalog_record(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        report = evaluate_structural_haplotype_fixture(catalog)
        self.assertEqual({receipt.record_id for receipt in report.receipts}, {
            record.record_id for record in catalog.positives + catalog.controls
        })
        self.assertTrue(all(receipt.output_address.startswith("sha256:") for receipt in report.receipts))
        self.assertTrue(all(receipt.detail for receipt in report.receipts))
        self.assertTrue(all(receipt.counts for receipt in report.receipts))

    def test_evaluation_exposes_every_required_control_reason(self) -> None:
        report = evaluate_structural_haplotype_fixture(FIXTURE.as_posix())
        by_id = {receipt.record_id: receipt for receipt in report.receipts}
        expected_states = {
            "control-phased-unphased": "ambiguous",
            "control-phased-context-drift": "out_of_domain",
            "control-allele-conflict": "contradictory",
            "control-allele-missing-dosage": "partial",
            "control-pangenome-ambiguous-paths": "ambiguous",
            "control-pangenome-unmapped": "partial",
            "control-repeat-mixed-classes": "ambiguous",
            "control-repeat-context-drift": "partial",
        }
        for record_id, result_state in expected_states.items():
            self.assertEqual(by_id[record_id].observed_result_state, result_state)
            self.assertEqual(by_id[record_id].expected_state, StructuralHaplotypeFixtureState.REVIEW)
        self.assertIn("context_mismatch", by_id["control-phased-context-drift"].issue_codes)
        self.assertIn("conflicting_allele_observation", by_id["control-allele-conflict"].issue_codes)
        self.assertIn("annotation_context_mismatch", by_id["control-repeat-context-drift"].issue_codes)

    def test_scenario_matrix_keeps_positive_and_review_sets_separate(self) -> None:
        matrix = evaluate_structural_haplotype_scenarios(FIXTURE.as_posix())
        self.assertTrue(matrix.passed)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.review_count, 8)
        self.assertEqual(len(matrix.scenarios), 12)
        self.assertEqual(
            {scenario.expected_state for scenario in matrix.scenarios},
            {StructuralHaplotypeFixtureState.ACCEPTED, StructuralHaplotypeFixtureState.REVIEW},
        )
        self.assertTrue(all(scenario.passed for scenario in matrix.scenarios))

    def test_quality_gate_reconciles_all_component_addresses(self) -> None:
        quality = evaluate_structural_haplotype_quality_gate(FIXTURE.as_posix())
        self.assertTrue(quality.passed)
        self.assertEqual(quality.state, StructuralHaplotypeFixtureState.ACCEPTED)
        self.assertEqual(len(quality.checks), 20)
        self.assertTrue(all(check.passed for check in quality.checks))
        self.assertRegex(quality.content_address, r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(quality.lineage_address, r"^sha256:[0-9a-f]{64}$")

    def test_lineage_records_operation_and_capability_pairing(self) -> None:
        graph = build_structural_haplotype_lineage(FIXTURE.as_posix())
        result_nodes = [node for node in graph.nodes if node.kind.value == "result"]
        self.assertEqual(len(result_nodes), 12)
        self.assertEqual(
            {node.label for node in result_nodes},
            {operation.value for operation in StructuralHaplotypeOperation},
        )
        self.assertEqual({node.context_key for node in graph.nodes}, {CONTEXT})
        self.assertTrue(all(node.content_address.startswith("sha256:") for node in result_nodes))

    def test_bundle_contains_only_expected_entry_classes_and_operations(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="release-boundary")
        self.assertTrue(bundle.accepted)
        self.assertEqual(len(bundle.entries), 12)
        self.assertEqual(sum(entry.entry_class == "positive" for entry in bundle.entries), 4)
        self.assertEqual(sum(entry.entry_class == "review" for entry in bundle.entries), 8)
        self.assertEqual({entry.operation for entry in bundle.entries}, {
            operation.value for operation in StructuralHaplotypeOperation
        })
        self.assertEqual({entry.capability_id for entry in bundle.entries}, {
            "GNC-D02-C09", "GNC-D02-C10", "GNC-D02-C11", "GNC-D02-C12"
        })

    def test_bundle_renderers_preserve_entry_count(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="renderer-boundary")
        json_payload = json.loads(bundle.render(StructuralHaplotypeBundleFormat.JSON))
        csv_text = bundle.render(StructuralHaplotypeBundleFormat.CSV)
        markdown_text = bundle.render(StructuralHaplotypeBundleFormat.MARKDOWN)
        self.assertEqual(json_payload["entry_count"], 12)
        self.assertEqual(len(csv_text.splitlines()), 13)
        self.assertEqual(markdown_text.count("| positive |"), 4)
        entry_rows = [line for line in markdown_text.splitlines() if line.startswith("| review:")]
        self.assertEqual(len(entry_rows), 8)

    def test_bundle_verification_rejects_tampered_entry_address(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="tamper-boundary")
        payload = copy.deepcopy(bundle.to_dict())
        payload["entries"][0]["evidence_address"] = "sha256:" + "0" * 64
        self.assertFalse(StructuralHaplotypeEvidenceBundleBuilder.verify(payload))

    def test_bundle_verification_ignores_convenience_count_drift(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="count-boundary")
        payload = copy.deepcopy(bundle.to_dict())
        payload["entry_count"] = 99
        self.assertTrue(StructuralHaplotypeEvidenceBundleBuilder.verify(payload))

    def test_bundle_verification_accepts_canonical_serialization(self) -> None:
        bundle = StructuralHaplotypeEvidenceBundleBuilder().build(FIXTURE, bundle_id="verify-boundary")
        payload = json.loads(bundle.render(StructuralHaplotypeBundleFormat.JSON))
        self.assertTrue(StructuralHaplotypeEvidenceBundleBuilder.verify(payload))

    def test_replay_expectation_matches_canonical_floor(self) -> None:
        catalog = StructuralHaplotypeFixtureCatalog.from_file(FIXTURE)
        expectation = StructuralHaplotypeReplayExpectation(
            fixture_id=catalog.fixture_id,
            context_key=CONTEXT,
            source_ids=catalog.source_ids,
            minimum_checks=40,
            minimum_positive_records=4,
            minimum_control_records=8,
        )
        report = replay_structural_haplotype_fixtures(
            (FIXTURE.as_posix(),),
            expectation=expectation,
            required_context_key=CONTEXT,
        )
        self.assertTrue(report.passed)
        self.assertEqual(len(report.cases), 1)
        self.assertTrue(report.cases[0].passed)

    def test_runtime_acceptance_manifest_matches_stage_receipts(self) -> None:
        report = run_structural_haplotype_pipeline(json.loads(PIPELINE.read_text(encoding="utf-8")))
        self.assertEqual(report.state, StructuralHaplotypePipelineState.ACCEPTED)
        assert report.manifest is not None
        self.assertEqual(report.manifest["stage_ids"], [receipt.stage_id for receipt in report.stage_receipts])
        self.assertEqual(
            report.manifest["stage_addresses"],
            [receipt.output_address for receipt in report.stage_receipts],
        )
        self.assertEqual(report.manifest["context_key"], CONTEXT)
        self.assertEqual(report.manifest["source_ids"], list(SOURCE_IDS))

    def test_runtime_stage_outputs_are_sanitized_and_addressed(self) -> None:
        report = run_structural_haplotype_pipeline(json.loads(PIPELINE.read_text(encoding="utf-8")))
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("aggregate-pipeline-phase", serialized)
        self.assertTrue(all(receipt.output_address.startswith("sha256:") for receipt in report.stage_receipts))
        self.assertTrue(all(receipt.detail for receipt in report.stage_receipts))

    def test_operation_floor_is_stable(self) -> None:
        self.assertEqual(tuple(StructuralHaplotypeOperation), (
            StructuralHaplotypeOperation.PHASED_HAPLOTYPE,
            StructuralHaplotypeOperation.ALLELE_AWARE_SV,
            StructuralHaplotypeOperation.PANGENOME_PROJECTION,
            StructuralHaplotypeOperation.REPEAT_MOBILE_ANNOTATION,
        ))


if __name__ == "__main__":
    unittest.main()
