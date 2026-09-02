#!/usr/bin/env python3
"""Run a synthetic case plus matched-RNA evidence through verified replay.

The inline observations are deliberately synthetic. The emitted JSON is a
sample-free operator summary and is not suitable for clinical use.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from glio_noncode.case_workflow import (
    RegulatoryTrackSource,
    VariantSource,
    prepare_case,
    run_case,
)
from glio_noncode.errors import GlioError
from glio_noncode.expression_claims import RNA_CONSEQUENCE_CHANNEL
from glio_noncode.expression_evidence import (
    AllelicCountObservation,
    AllelicImbalanceAnalyzer,
    ExpressionBatch,
    ExpressionObservation,
    ExpressionScale,
    PhaseStatus,
    PredictedRegulatoryEffect,
    RegulatoryDirection,
    RNAConsequenceIntegrator,
    RobustExpressionOutlierAnalyzer,
)
from glio_noncode.models import EdgeType, ReferenceContext

RESEARCH_WARNING = (
    "RESEARCH USE ONLY. This synthetic workflow does not provide a diagnosis, "
    "clinical probability, or treatment recommendation."
)
DEFAULT_DATA_ROOT = Path(".glio-case-expression-demo")

# Private inputs used only inside this process. None is copied into the summary.
_VCF = "\n".join(
    (
        "##fileformat=VCFv4.3",
        "##source=synthetic-research-only-demo",
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSYNTHETIC_PRIVATE",
        "7\t100\tdemo-var-1\tA\tT\t99\tPASS\tDP=100\tGT\t0/1",
    )
)
_BED = "7\t90\t130\tEGFR\t800\t+\n"
_TUMOUR_SAMPLE_KEY = "private:tumour-expression-key"
_REFERENCE_VALUES = (3.125, 3.375, 3.625, 3.875, 4.125, 4.375, 4.625, 4.875)


class DemoBlocked(RuntimeError):
    """Raised when a supposedly accepted synthetic stage fails closed."""


def _context() -> ReferenceContext:
    return ReferenceContext(
        genome_build="GRCh38",
        disease_class="diffuse_glioma",
        age_group="adult",
        cell_state="stem_like",
        territory="tumor_core",
        treatment_phase="pre_treatment",
        source_version="synthetic-demo-v1",
    )


def _expression(
    *, feature_id: str, sample_key: str, value: float, context_key: str
) -> ExpressionObservation:
    return ExpressionObservation(
        feature_id=feature_id,
        sample_key=sample_key,
        value=value,
        scale=ExpressionScale.LOG2_TPM,
        context_key=context_key,
        source_id="synthetic-matched-rna",
        source_version="synthetic-demo-v1",
    )


def run_demo(data_root: Path, *, persistence_mode: str) -> dict[str, object]:
    """Execute the synthetic workflow and return only a sample-free summary."""

    context = _context()
    prepared = prepare_case(
        case_id="synthetic-case-expression-demo",
        subject_id="synthetic-subject-private",
        context=context,
        variant_source=VariantSource(
            source_id="synthetic-variants",
            input_format="vcf",
            genome_build="GRCh38",
            payload=_VCF,
        ),
        regulatory_tracks=(
            RegulatoryTrackSource(
                source_id="synthetic-egfr-track",
                input_format="bed",
                genome_build="GRCh38",
                context=context,
                payload=_BED,
                target_gene_keys=("Name",),
            ),
        ),
        requested_by="synthetic-demo-operator",
        live_reference=False,
    )
    if not prepared.accepted or prepared.manifest is None or prepared.run_id is None:
        raise DemoBlocked("synthetic case preparation was blocked")

    manifest = prepared.manifest
    variant_id = manifest.variants[0].variant_id
    context_key = manifest.context.key
    expression_target = _expression(
        feature_id="EGFR",
        sample_key=_TUMOUR_SAMPLE_KEY,
        value=20.125,
        context_key=context_key,
    )
    references = ExpressionBatch(
        tuple(
            _expression(
                feature_id="EGFR",
                sample_key=f"private:reference-{index}",
                value=value,
                context_key=context_key,
            )
            for index, value in enumerate(_REFERENCE_VALUES, start=1)
        )
    )
    expression_result = RobustExpressionOutlierAnalyzer().analyze(
        expression_target,
        references,
        expected_direction=RegulatoryDirection.GAIN,
        expected_context_key=context_key,
    )

    allelic_result = AllelicImbalanceAnalyzer().analyze(
        AllelicCountObservation(
            feature_id="EGFR",
            variant_id=variant_id,
            sample_key=_TUMOUR_SAMPLE_KEY,
            ref_count=18,
            alt_count=82,
            other_count=0,
            phase=PhaseStatus.PHASED,
            context_key=context_key,
            source_id="synthetic-matched-rna",
            source_version="synthetic-demo-v1",
            expected_alt_fraction=0.5,
            mapping_bias=0.01,
            mapping_bias_flag=False,
        ),
        expected_direction=RegulatoryDirection.GAIN,
        expected_context_key=context_key,
    )

    prediction = PredictedRegulatoryEffect(
        prediction_id="prediction:synthetic:egfr",
        variant_id=variant_id,
        feature_id="EGFR",
        direction=RegulatoryDirection.GAIN,
        context_key=context_key,
        source_id="synthetic-regulatory-model",
        source_version="synthetic-demo-v1",
    )
    consequence = RNAConsequenceIntegrator().integrate(
        prediction,
        expression=expression_result,
        allelic=allelic_result,
    )
    result = run_case(
        prepared,
        data_root=data_root,
        rna_consequences=(consequence,),
    )
    if (
        not result.accepted
        or result.run_id is None
        or result.dossier is None
        or result.replay_report is None
    ):
        raise DemoBlocked("synthetic case evaluation or replay was blocked")

    matched_claim = next(
        (
            claim
            for claim in result.dossier.evidence
            if claim.channel == RNA_CONSEQUENCE_CHANNEL
        ),
        None,
    )
    hypothesis = next(
        (item for item in result.dossier.hypotheses if item.gene_id == "EGFR"),
        None,
    )
    if matched_claim is None or hypothesis is None:
        raise DemoBlocked("matched RNA claim did not reach the EGFR hypothesis")
    element_gene_edge = next(
        (
            edge
            for edge in hypothesis.edges
            if edge.edge_type is EdgeType.ELEMENT_TO_GENE
            and edge.edge_id == matched_claim.edge_id
        ),
        None,
    )
    causal_path_edge = next(
        (edge for edge in hypothesis.edges if edge.edge_type is EdgeType.CAUSAL_PATH),
        None,
    )
    if element_gene_edge is None or causal_path_edge is None:
        raise DemoBlocked("expected hypothesis edges were not constructed")
    causal_path_claim = next(
        (
            claim
            for claim in result.dossier.evidence
            if claim.edge_id == causal_path_edge.edge_id
        ),
        None,
    )
    if causal_path_claim is None:
        raise DemoBlocked("causal-path aggregate claim was not constructed")

    replay = result.replay_report
    replay_accepted = replay.event_chain_valid and replay.stored_dossier_matches_address
    runtime_receipt = result.stage_receipts[-1]
    return {
        "accepted": result.accepted and replay_accepted,
        "research_use_only": True,
        "warning": RESEARCH_WARNING,
        "persistence": {"mode": persistence_mode},
        "preparation": {
            "prepared_run_id": prepared.run_id,
            "manifest_address": prepared.manifest_address,
            "workflow_address": prepared.content_address,
        },
        "evaluation": {
            "evaluation_run_id": result.run_id,
            "dossier_address": result.dossier.content_address,
            "workflow_address": result.content_address,
            "rna_input_address": runtime_receipt.metadata.get("rna_input_address"),
        },
        "rna_evidence": {
            "state": consequence.state.value,
            "prediction_address": prediction.content_address,
            "expression_result_address": expression_result.content_address,
            "allelic_result_address": allelic_result.content_address,
            "consequence_address": consequence.content_address,
        },
        "matched_rna_claim": {
            "claim_address": matched_claim.evidence_id,
            "channel": matched_claim.channel,
            "edge_id": matched_claim.edge_id,
            "source_addresses": list(matched_claim.depends_on),
        },
        "element_to_gene_edge": {
            "edge_id": element_gene_edge.edge_id,
            "element_id": hypothesis.element_id,
            "gene_id": hypothesis.gene_id,
            "claim_addresses": list(element_gene_edge.claim_ids),
            "support_strength": element_gene_edge.support,
            "uncertainty": element_gene_edge.uncertainty,
            "support_level": element_gene_edge.support_level.value,
        },
        "causal_path_support": {
            "edge_id": causal_path_edge.edge_id,
            "aggregate_claim_address": causal_path_claim.evidence_id,
            "supporting_claim_addresses": list(causal_path_claim.depends_on),
            "matched_rna_claim_linked": matched_claim.evidence_id
            in causal_path_claim.depends_on,
            "support_strength": causal_path_edge.support,
            "support_level": causal_path_edge.support_level.value,
        },
        "replay": {
            "accepted": replay_accepted,
            "event_chain_valid": replay.event_chain_valid,
            "stored_dossier_matches_address": replay.stored_dossier_matches_address,
            "warnings": list(replay.warnings),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the synthetic case + matched-RNA research workflow."
    )
    roots = parser.add_mutually_exclusive_group()
    roots.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help=f"persistent local runtime directory (default: {DEFAULT_DATA_ROOT})",
    )
    roots.add_argument(
        "--temporary-data-root",
        action="store_true",
        help="use and remove an isolated temporary runtime directory",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.temporary_data_root:
            with tempfile.TemporaryDirectory(prefix="glio-case-expression-demo-") as directory:
                summary = run_demo(Path(directory), persistence_mode="temporary")
        else:
            summary = run_demo(args.data_root, persistence_mode="persistent")
    except (DemoBlocked, GlioError, OSError):
        print(
            json.dumps(
                {
                    "accepted": False,
                    "error": "demo_blocked",
                    "research_use_only": True,
                    "warning": RESEARCH_WARNING,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
