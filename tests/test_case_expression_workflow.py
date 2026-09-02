from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from glio_noncode.case_workflow import (
    MAX_CASE_RNA_CONSEQUENCES,
    CaseRunResult,
    RegulatoryTrackSource,
    VariantSource,
    capabilities,
    case_workflow_schema,
    prepare_case,
    run_case,
)
from glio_noncode.expression_claims import RNA_CONSEQUENCE_CHANNEL
from glio_noncode.expression_evidence import (
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.models import EdgeType, ReferenceContext
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

VCF = "\n".join(
    (
        "##fileformat=VCFv4.3",
        "##source=case-expression-workflow-fixture",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1",
        "7\t100\tvar-1\tA\tT\t99\tPASS\tDP=42\tGT\t0/1",
    )
)


def context() -> ReferenceContext:
    return ReferenceContext(
        genome_build="GRCh38",
        disease_class="diffuse_glioma",
        age_group="adult",
        cell_state="stem_like",
        territory="tumor_core",
        treatment_phase="pre_treatment",
        source_version="case-expression-workflow-v1",
    )


def track(source_id: str, gene_id: str) -> RegulatoryTrackSource:
    return RegulatoryTrackSource(
        source_id=source_id,
        input_format="bed",
        genome_build="GRCh38",
        context=context(),
        payload=f"7\t90\t130\t{gene_id}\t800\t+\n",
        target_gene_keys=("Name",),
    )


def prepared(*, two_genes: bool = False):
    tracks = (track("track-egfr", "EGFR"),)
    if two_genes:
        tracks += (track("track-sox2", "SOX2"),)
    return prepare_case(
        case_id="case-expression-workflow",
        subject_id="subject-expression-workflow",
        context=context(),
        variant_source=VariantSource(
            source_id="variants-expression-workflow",
            input_format="vcf",
            genome_build="GRCh38",
            payload=VCF,
        ),
        regulatory_tracks=tracks,
        requested_by="researcher-local",
    )


def consequence(value, gene_id: str, prediction_id: str) -> RNAConsequenceEvidence:
    assert value.manifest is not None
    return RNAConsequenceEvidence(
        prediction_id=prediction_id,
        prediction_address=content_hash(
            {"prediction_id": prediction_id},
            prefix="regulatory-effect-prediction",
        ),
        variant_id=value.manifest.variants[0].variant_id,
        feature_id=gene_id,
        context_key=value.manifest.context.key,
        predicted_direction=RegulatoryDirection.GAIN,
        state=RNAEvidenceState.SUPPORTED,
        expression_state=RNAEvidenceState.SUPPORTED,
        expression_direction=ExpressionDirection.UP,
        expression_robust_z=7.0,
        expression_result_address=content_hash(
            {"prediction_id": prediction_id, "component": "expression"},
            prefix="expression-outlier",
        ),
        allelic_state=None,
        allelic_direction=None,
        allelic_log2_ratio=None,
        allelic_q_value=None,
        allelic_result_address=None,
        reason_codes=("workflow_directional_support",),
    )


class CaseExpressionWorkflowTests(unittest.TestCase):
    def test_mapping_reason_codes_and_optional_address_are_schema_strict(self) -> None:
        value = prepared()
        canonical = consequence(value, "EGFR", "prediction:workflow:strict-rna").to_dict()
        invalid_values = (
            ("string reason codes", "reason_codes", "workflow_directional_support"),
            (
                "duplicate reason codes",
                "reason_codes",
                ["workflow_directional_support", "workflow_directional_support"],
            ),
            ("empty reason code", "reason_codes", [""]),
            ("null optional address", "content_address", None),
        )
        for label, field_name, replacement in invalid_values:
            mapping = json.loads(json.dumps(canonical))
            mapping[field_name] = replacement
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                result = run_case(
                    value,
                    data_root=directory,
                    rna_consequences=(mapping,),
                )
                self.assertTrue(result.blocked)
                self.assertIn("invalid_rna_consequence", {item.code for item in result.issues})

    def test_mapping_input_reaches_exact_edge_and_causal_path(self) -> None:
        value = prepared()
        rna = consequence(value, "EGFR", "prediction:workflow:egfr")
        with tempfile.TemporaryDirectory() as directory:
            result = run_case(
                value,
                data_root=directory,
                rna_consequences=(rna.to_dict(),),
            )

            self.assertTrue(result.accepted, result.to_dict())
            assert result.dossier is not None
            assert result.run_record is not None
            self.assertNotEqual(result.dossier.run_id, value.run_id)
            self.assertEqual(
                result.dossier.run_id,
                CaseRuntime._run_id(value.manifest, (rna,)),
            )
            rna_claim = next(
                claim
                for claim in result.dossier.evidence
                if claim.channel == RNA_CONSEQUENCE_CHANNEL
            )
            hypothesis = next(
                item for item in result.dossier.hypotheses if item.gene_id == "EGFR"
            )
            gene_edge = next(
                edge
                for edge in hypothesis.edges
                if edge.edge_type is EdgeType.ELEMENT_TO_GENE and edge.target_id == "EGFR"
            )
            path_edge = next(
                edge for edge in hypothesis.edges if edge.edge_type is EdgeType.CAUSAL_PATH
            )
            path_claim = next(
                claim
                for claim in result.dossier.evidence
                if claim.edge_id == path_edge.edge_id
            )
            self.assertEqual(rna_claim.edge_id, gene_edge.edge_id)
            self.assertIn(rna_claim.evidence_id, gene_edge.claim_ids)
            self.assertIn(rna_claim.evidence_id, path_claim.depends_on)
            self.assertEqual(
                result.run_record["input_address"],
                value.manifest_address,
            )

            receipt = result.stage_receipts[-1]
            self.assertEqual(receipt.source_id, result.dossier.run_id)
            self.assertEqual(receipt.metadata["prepared_run_id"], value.run_id)
            self.assertEqual(receipt.metadata["evaluation_run_id"], result.dossier.run_id)
            self.assertEqual(receipt.metadata["rna_consequence_count"], 1)
            self.assertEqual(receipt.metadata["rna_consequence_addresses"], [rna.content_address])
            self.assertTrue(receipt.metadata["rna_input_address"].startswith("sha256:"))
            self.assertTrue(
                CaseRuntime(directory).store.store.exists(receipt.metadata["rna_input_address"])
            )
            rendered_metadata = json.dumps(receipt.metadata, sort_keys=True)
            self.assertNotIn("expression_robust_z", rendered_metadata)
            self.assertNotIn(rna.prediction_id, rendered_metadata)
            self.assertEqual(CaseRunResult.from_mapping(result.to_dict()), result)

    def test_typed_inputs_are_canonical_and_evaluation_id_is_order_independent(self) -> None:
        value = prepared(two_genes=True)
        egfr = consequence(value, "EGFR", "prediction:workflow:egfr-order")
        sox2 = consequence(value, "SOX2", "prediction:workflow:sox2-order")
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            forward = run_case(
                value,
                data_root=first_directory,
                rna_consequences=(sox2, egfr),
            )
            reverse = run_case(
                value,
                data_root=second_directory,
                rna_consequences=(egfr, sox2),
            )

        self.assertTrue(forward.accepted, forward.to_dict())
        self.assertTrue(reverse.accepted, reverse.to_dict())
        self.assertEqual(forward.run_id, reverse.run_id)
        self.assertNotEqual(forward.run_id, value.run_id)
        expected_addresses = sorted((egfr.content_address, sox2.content_address))
        self.assertEqual(
            forward.stage_receipts[-1].metadata["rna_consequence_addresses"],
            expected_addresses,
        )
        self.assertEqual(
            forward.stage_receipts[-1].metadata["rna_input_address"],
            reverse.stage_receipts[-1].metadata["rna_input_address"],
        )

    def test_invalid_or_tampered_mapping_returns_typed_blocked_result(self) -> None:
        value = prepared()
        original = consequence(value, "EGFR", "prediction:workflow:invalid").to_dict()
        bad_inputs = []
        tampered_address = dict(original)
        tampered_address["content_address"] = "rna-consequence-evidence:" + "0" * 64
        bad_inputs.append(tampered_address)
        unknown_field = dict(original)
        unknown_field["raw_sample_value"] = 99
        bad_inputs.append(unknown_field)
        wrong_version = dict(original)
        wrong_version["schema_version"] = "999.0.0"
        bad_inputs.append(wrong_version)
        overflowing_number = dict(original)
        overflowing_number.pop("content_address")
        overflowing_number["expression_robust_z"] = 10**10_000
        bad_inputs.append(overflowing_number)

        for mapping in bad_inputs:
            with self.subTest(keys=sorted(mapping)):
                with tempfile.TemporaryDirectory() as directory:
                    result = run_case(
                        value,
                        data_root=directory,
                        rna_consequences=(mapping,),
                    )
                    self.assertTrue(result.blocked)
                    self.assertIsNone(result.dossier)
                    self.assertIn(
                        "invalid_rna_consequence",
                        {issue.code for issue in result.issues},
                    )
                    self.assertEqual(
                        result.stage_receipts[-1].metadata["reason"],
                        "invalid_rna_consequence",
                    )
                    self.assertFalse(any((Path(directory) / "runs").glob("run-*.json")))

    def test_no_rna_argument_and_explicit_empty_input_are_exactly_equal(self) -> None:
        value = prepared()
        fixed = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
            patch("glio_noncode.models.utc_now", return_value=fixed),
            patch("glio_noncode.events.utc_now", return_value=fixed),
            patch("glio_noncode.runtime.utc_now", return_value=fixed),
            patch("glio_noncode.case_workflow.utc_now", return_value=fixed),
        ):
            implicit = run_case(value, data_root=first_directory)
            explicit = run_case(
                value,
                data_root=second_directory,
                rna_consequences=(),
            )
        self.assertEqual(implicit, explicit)
        self.assertEqual(implicit.run_id, value.run_id)

    def test_schema_and_capabilities_advertise_rna_execution_identity(self) -> None:
        schema = case_workflow_schema()
        advertised = capabilities()
        rna_schema = schema["$defs"]["rna_consequence_execution_input"]
        self.assertEqual(rna_schema["type"], "array")
        self.assertEqual(rna_schema["maxItems"], MAX_CASE_RNA_CONSEQUENCES)
        self.assertFalse(rna_schema["items"]["additionalProperties"])
        self.assertIn("content_address", rna_schema["items"]["properties"])
        invalid_reason = consequence(
            prepared(),
            "EGFR",
            "prediction:workflow:empty-schema-reason",
        ).to_dict()
        invalid_reason["reason_codes"] = [""]
        self.assertFalse(Draft202012Validator(rna_schema).is_valid([invalid_reason]))
        self.assertIn("rna_consequences", advertised["optional_execution_inputs"])
        self.assertEqual(
            advertised["optional_execution_inputs"]["rna_consequences"]["max_items"],
            MAX_CASE_RNA_CONSEQUENCES,
        )
        self.assertEqual(
            advertised["canonical_rna_order"],
            "RNAConsequenceEvidence.content_address",
        )
        self.assertTrue(advertised["identity_semantics"]["empty_rna_preserves_prepared_run_id"])
        self.assertFalse(
            advertised["optional_execution_inputs"]["rna_consequences"][
                "raw_values_in_receipts"
            ]
        )

    def test_rna_execution_rejects_duplicate_and_over_limit_inputs(self) -> None:
        from itertools import repeat

        value = prepared()
        evidence = consequence(value, "SOX2", "pred-duplicate")
        for rows in (
            (evidence, evidence),
            repeat(evidence, MAX_CASE_RNA_CONSEQUENCES + 1),
        ):
            with self.subTest(rows=type(rows).__name__), tempfile.TemporaryDirectory() as directory:
                result = run_case(value, data_root=directory, rna_consequences=rows)
                self.assertTrue(result.blocked)
                self.assertIsNone(result.dossier)
                self.assertIn(
                    "invalid_rna_consequence",
                    {issue.code for issue in result.issues},
                )
                self.assertFalse(any((Path(directory) / "runs").glob("run-*.json")))


if __name__ == "__main__":
    unittest.main()
