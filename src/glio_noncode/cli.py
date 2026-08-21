"""Command-line entry point for local case evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .api import create_server
from .atlas_beta import (
    HistoneMarkTrackHarmonizer,
    MolecularAtlasState,
    MolecularStateAtlasAdapter,
)
from .atlas_extensions import CcreAtlasProfile, CcreTrackParser
from .capability_registry import default_capability_registry
from .causal_reasoning import FactorGraphConstructor, FactorObservation
from .cell_context import ContextObservationParser
from .chromatin_context import ChromatinTrackKind, ChromatinTrackParser
from .cohort_discovery import CohortQuery, CohortQueryBuilder, CohortVariantRecord
from .control_plane import ClaimCeiling, MissionContext, default_control_plane_registry
from .control_plane_app import ControlPlaneApplication
from .data_sources import PublicReferenceRetriever, default_source_catalog
from .errors import GlioError
from .evidence_lifecycle import (
    CitationResolver,
    EvidenceCitation,
    EvidenceDossierPublisher,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from .intake import IntakeFormat, VariantIntake
from .link_graph import GeneFeatureParser
from .methylation_beta import (
    CpGCreationLossAnalyzer,
    IdhHypermethylationContextModel,
    MethylationContextRetriever,
    MethylationRecordParser,
    MethylationSensitiveMotifAnalyzer,
    MethylationSensitiveMotifDefinition,
)
from .mission_runtime import MissionPlanBuilder, MissionRequest
from .models import CaseManifest, ReferenceContext, VariantIdentity
from .reference_beta import (
    DiseaseOntologyMapper,
    GencodeTranscriptAdapter,
    ManeTranscriptAdapter,
    RegulatoryOntologyAdapter,
)
from .reference_registry import default_reference_registry
from .regulatory_tracks import RegulatoryTrackFormat, RegulatoryTrackParser
from .runtime import CaseRuntime
from .schema import schema_document
from .sequence_adapters import (
    LongContextVariantEffectAdapter,
    SequenceContextEncoder,
    SequenceFoundationModelAdapter,
)
from .sequence_beta import (
    CooperativeTFGrammarModel,
    GrammarInteraction,
    MotifCreationScanner,
    MotifDefinition,
    MotifDisruptionScanner,
    MotifGrammarRule,
    MotifSpacingGrammarAnalyzer,
)
from .specimen_beta import (
    CancerCellFractionEstimator,
    MosaicismPosteriorEstimator,
    SomaticGermlineOriginClassifier,
    SubcloneAssigner,
)
from .specimen_context import PurityPloidyImporter
from .structural_beta import (
    ChromothripsisPatternDetector,
    EnhancerHijackingCandidateDetector,
    ExtrachromosomalDnaCandidateDetector,
    FocalAmplificationBoundaryMapper,
)
from .structural_extensions import CopyNumberSegmentHarmonizer, SVConsensusImporter
from .topology_context import (
    ContactMatrixParser,
    TadBoundaryParser,
    TopologyAssay,
)
from .variant_beta import (
    CategoricalCatalogParser,
    CatVRSNormalizer,
    MultiAllelicDecomposer,
    RepeatAwareNormalizer,
    VAAnnotationEnvelopeBuilder,
)
from .variant_normalization import VRSNormalizer
from .workspace import CaseWorkspaceBuilder, RegulatoryTrackBrowser


def _read_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object")
    return payload


def _write_json(payload: Any, output: str | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def _read_rows(path: str, *keys: str) -> tuple[Mapping[str, Any], ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        for key in keys:
            if key in payload:
                rows = payload[key]
                if not isinstance(rows, list):
                    raise ValueError(f"{path} JSON field {key!r} must be a list")
                return tuple(rows)
        return (payload,)
    if isinstance(payload, list):
        return tuple(payload)
    raise ValueError(f"{path} JSON must be an object or list")


def _context_from_key(context_key: str) -> ReferenceContext:
    parts = context_key.split("|")
    if len(parts) != 6:
        raise ValueError("context-key must contain six pipe-delimited fields")
    return ReferenceContext(
        genome_build=parts[0],
        disease_class=parts[1],
        age_group=parts[2],
        cell_state=parts[3],
        territory=parts[4],
        treatment_phase=parts[5],
    )


def _motif_definitions(rows: Any) -> tuple[MotifDefinition, ...]:
    if not isinstance(rows, list):
        raise ValueError("motifs must be a list")
    return tuple(
        MotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", row.get("motif_id", ""))),
            consensus=str(row.get("consensus", "")),
            source_id=str(row.get("source_id", "motif-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 1.0)),
            strand_aware=bool(row.get("strand_aware", True)),
            attributes=dict(row.get("attributes", {})),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _grammar_rules(rows: Any) -> tuple[MotifGrammarRule, ...]:
    if not isinstance(rows, list):
        raise ValueError("rules must be a list")
    return tuple(
        MotifGrammarRule(
            rule_id=str(row.get("rule_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            minimum_spacing=int(row.get("minimum_spacing", 0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            allowed_orientations=tuple(
                str(item) for item in row.get("allowed_orientations", ("same", "opposite", "any"))
            ),
            source_id=str(row.get("source_id", "grammar-input")),
            source_version=str(row.get("source_version", "unspecified")),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _grammar_interactions(rows: Any) -> tuple[GrammarInteraction, ...]:
    if not isinstance(rows, list):
        raise ValueError("interactions must be a list")
    return tuple(
        GrammarInteraction(
            interaction_id=str(row.get("interaction_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            weight=float(row.get("weight", 0.0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            required=bool(row.get("required", False)),
            source_id=str(row.get("source_id", "grammar-model")),
            source_version=str(row.get("source_version", "unspecified")),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _methylation_motifs(rows: Any) -> tuple[MethylationSensitiveMotifDefinition, ...]:
    if not isinstance(rows, list):
        raise ValueError("methylation-sensitive motifs must be a list")
    definitions: list[MethylationSensitiveMotifDefinition] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("methylation-sensitive motif rows must be objects")
        definitions.append(
            MethylationSensitiveMotifDefinition(
                motif_id=str(row.get("motif_id", "")),
                name=str(row.get("name", row.get("motif_id", ""))),
                consensus=str(row.get("consensus", "")),
                source_id=str(row.get("source_id", "motif-input")),
                source_version=str(row.get("source_version", "unspecified")),
                sensitive_positions=tuple(int(item) for item in row.get("sensitive_positions", ())),
                threshold=float(row.get("threshold", 1.0)),
                methylated_threshold=float(row.get("methylated_threshold", 0.50)),
                strand_aware=bool(row.get("strand_aware", True)),
                attributes=dict(row.get("attributes", {})),
            )
        )
    return tuple(definitions)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode", description="Inspectable research hypothesis runtime"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="evaluate a case manifest")
    evaluate.add_argument("manifest", type=str)
    evaluate.add_argument("--data-root", default=".glio")
    evaluate.add_argument("--output", default=None)
    evaluate.add_argument(
        "--live-reference",
        action="store_true",
        help="retrieve bounded sequence and annotation data from public APIs",
    )
    evaluate.add_argument(
        "--window-bp", default=2000, type=int, help="half-window for live reference retrieval"
    )

    fetch_public = subparsers.add_parser(
        "fetch-public", help="retrieve and emit live public reference data for a manifest"
    )
    fetch_public.add_argument("manifest", type=str)
    fetch_public.add_argument("--data-root", default=".glio")
    fetch_public.add_argument("--output", default=None)
    fetch_public.add_argument("--window-bp", default=2000, type=int)

    serve = subparsers.add_parser("serve", help="run the local JSON API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", default=8765, type=int)
    serve.add_argument("--data-root", default=".glio")

    schema = subparsers.add_parser("schema", help="print the public contract summary")
    schema.add_argument("--output", default=None)

    subparsers.add_parser("sources", help="print the live public source catalog")
    subparsers.add_parser("registry", help="print the bounded control-plane registry")
    subparsers.add_parser("bindings", help="print executable control-plane handler bindings")
    subparsers.add_parser("capabilities", help="print the 256-capability implementation ledger")
    subparsers.add_parser("references", help="print the reference assembly registry")

    gencode = subparsers.add_parser(
        "parse-gencode",
        help="parse a versioned GENCODE transcript GTF or JSON snapshot",
    )
    gencode.add_argument("input", type=str)
    gencode.add_argument("--source-id", default=None)
    gencode.add_argument("--source-version", default="unspecified")
    gencode.add_argument("--assembly", default="GRCh38")
    gencode.add_argument("--format", choices=("gtf", "gff3", "json"), default=None)
    gencode.add_argument("--output", default=None)

    mane = subparsers.add_parser(
        "parse-mane",
        help="parse a versioned MANE transcript TSV, CSV, or JSON snapshot",
    )
    mane.add_argument("input", type=str)
    mane.add_argument("--source-id", default=None)
    mane.add_argument("--source-version", default="unspecified")
    mane.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    mane.add_argument("--output", default=None)

    regulatory_term = subparsers.add_parser(
        "normalize-regulatory-term",
        help="normalize a regulatory term against a declared ontology catalog",
    )
    regulatory_term.add_argument("input", type=str)
    regulatory_term.add_argument("--catalog", required=True)
    regulatory_term.add_argument("--source-id", default=None)
    regulatory_term.add_argument("--source-version", default="unspecified")
    regulatory_term.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    regulatory_term.add_argument("--output", default=None)

    disease_term = subparsers.add_parser(
        "map-disease-term",
        help="map a disease term against a declared ontology mapping catalog",
    )
    disease_term.add_argument("input", type=str)
    disease_term.add_argument("--catalog", required=True)
    disease_term.add_argument("--source-id", default=None)
    disease_term.add_argument("--source-version", default="unspecified")
    disease_term.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    disease_term.add_argument("--output", default=None)

    citations = subparsers.add_parser(
        "parse-citations", help="parse a versioned citation manifest with quarantine accounting"
    )
    citations.add_argument("input", type=str)
    citations.add_argument("--source-id", default=None)
    citations.add_argument("--source-version", default="unspecified")
    citations.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    citations.add_argument("--output", default=None)

    evidence_graph = subparsers.add_parser(
        "evidence-graph", help="build and validate an immutable versioned evidence graph"
    )
    evidence_graph.add_argument("input", type=str)
    evidence_graph.add_argument("--context-key", required=True)
    evidence_graph.add_argument("--graph-id", default="evidence-graph")
    evidence_graph.add_argument("--output", default=None)

    workspace_case = subparsers.add_parser(
        "workspace-case", help="build a deterministic case research workspace"
    )
    workspace_case.add_argument("manifest", type=str)
    workspace_case.add_argument("--output", default=None)

    workspace_track = subparsers.add_parser(
        "workspace-track", help="build an exact-context regulatory track workspace"
    )
    workspace_track.add_argument("input", type=str)
    workspace_track.add_argument("--context-key", required=True)
    workspace_track.add_argument("--source-id", default=None)
    workspace_track.add_argument(
        "--format", choices=[item.value for item in RegulatoryTrackFormat], default=None
    )
    workspace_track.add_argument("--genome-build", default="GRCh38")
    workspace_track.add_argument("--output", default=None)

    mission_plan = subparsers.add_parser(
        "mission-plan", help="expand a mission request into a typed plan and compiled workflow"
    )
    mission_plan.add_argument("input", type=str)
    mission_plan.add_argument("--output", default=None)

    intake = subparsers.add_parser("intake", help="canonicalize a VCF, TSV, or JSON variant source")
    intake.add_argument("input", type=str)
    intake.add_argument("--source-id", default=None)
    intake.add_argument("--format", choices=[item.value for item in IntakeFormat], default=None)
    intake.add_argument("--genome-build", default="GRCh38")
    intake.add_argument("--sample-id", default=None)
    intake.add_argument("--include-no-call", action="store_true")
    intake.add_argument("--output", default=None)

    track = subparsers.add_parser(
        "parse-track", help="parse a BED, narrowPeak, GFF3, or JSON regulatory track"
    )
    track.add_argument("input", type=str)
    track.add_argument("--source-id", default=None)
    track.add_argument(
        "--format", choices=[item.value for item in RegulatoryTrackFormat], default=None
    )
    track.add_argument("--genome-build", default="GRCh38")
    track.add_argument("--output", default=None)

    normalize = subparsers.add_parser("normalize", help="emit a VRS-style normalization report")
    normalize.add_argument("notation", type=str)
    normalize.add_argument("--genome-build", default="GRCh38")
    normalize.add_argument("--sequence-digest", default=None)
    normalize.add_argument("--reference-sequence", default=None)
    normalize.add_argument("--reference-start", type=int, default=None)
    normalize.add_argument("--output", default=None)

    normalize_categorical = subparsers.add_parser(
        "normalize-categorical",
        help="normalize a declared categorical variation against a versioned catalog",
    )
    normalize_categorical.add_argument("input", type=str)
    normalize_categorical.add_argument("--catalog", default=None)
    normalize_categorical.add_argument("--source-id", default=None)
    normalize_categorical.add_argument("--source-version", default="unspecified")
    normalize_categorical.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    normalize_categorical.add_argument("--output", default=None)

    annotation = subparsers.add_parser(
        "build-annotation",
        help="build a provenance-complete VA-Spec-shaped annotation envelope",
    )
    annotation.add_argument("input", type=str)
    annotation.add_argument("--context-key", required=True)
    annotation.add_argument("--annotation-id", default=None)
    annotation.add_argument("--profile", default="glio-noncode.research.statement")
    annotation.add_argument("--specification-version", default="1.0-shaped")
    annotation.add_argument("--output", default=None)

    decompose = subparsers.add_parser(
        "decompose-multiallelic",
        help="split a multi-allelic record while retaining parent lineage and genotype projections",
    )
    decompose.add_argument("input", type=str)
    decompose.add_argument("--source-id", default="multiallelic-cli")
    decompose.add_argument("--source-version", default="unspecified")
    decompose.add_argument("--genome-build", default="GRCh38")
    decompose.add_argument("--output", default=None)

    repeat = subparsers.add_parser(
        "normalize-repeat",
        help="enumerate locally equivalent literal indel placements by sequence replay",
    )
    repeat.add_argument("input", type=str)
    repeat.add_argument("--reference-start", type=int, default=None)
    repeat.add_argument("--max-shift-bp", type=int, default=50)
    repeat.add_argument("--genome-build", default="GRCh38")
    repeat.add_argument("--output", default=None)

    sv_consensus = subparsers.add_parser(
        "sv-consensus", help="import and reconcile multi-caller structural observations"
    )
    sv_consensus.add_argument("input", type=str)
    sv_consensus.add_argument("--source-id", default=None)
    sv_consensus.add_argument("--format", choices=("tsv", "json"), default=None)
    sv_consensus.add_argument("--breakpoint-tolerance", type=int, default=10)
    sv_consensus.add_argument("--output", default=None)

    cn = subparsers.add_parser("harmonize-cn", help="harmonize multi-caller copy-number segments")
    cn.add_argument("input", type=str)
    cn.add_argument("--source-id", default=None)
    cn.add_argument("--output", default=None)

    focal_amp = subparsers.add_parser(
        "map-focal-amplification",
        help="map copy-number amplification boundaries with caller disagreement",
    )
    focal_amp.add_argument("input", type=str)
    focal_amp.add_argument("--context-key", default=None)
    focal_amp.add_argument("--baseline-copy-number", type=float, default=2.0)
    focal_amp.add_argument("--amplification-threshold", type=float, default=6.0)
    focal_amp.add_argument("--minimum-gain", type=float, default=2.0)
    focal_amp.add_argument("--merge-gap-bp", type=int, default=0)
    focal_amp.add_argument("--boundary-tolerance-bp", type=int, default=50)
    focal_amp.add_argument("--output", default=None)

    chromothripsis = subparsers.add_parser(
        "detect-chromothripsis",
        help="detect bounded breakpoint-cluster patterns with explicit evidence limits",
    )
    chromothripsis.add_argument("input", type=str)
    chromothripsis.add_argument("--context-key", default=None)
    chromothripsis.add_argument("--min-breakpoints", type=int, default=6)
    chromothripsis.add_argument("--max-cluster-span-bp", type=int, default=10_000_000)
    chromothripsis.add_argument("--max-gap-bp", type=int, default=2_000_000)
    chromothripsis.add_argument("--min-orientation-switches", type=int, default=3)
    chromothripsis.add_argument("--require-copy-number-oscillation", action="store_true")
    chromothripsis.add_argument("--output", default=None)

    ecdna = subparsers.add_parser(
        "detect-ecdna",
        help="detect extrachromosomal-DNA candidates from explicit circular evidence",
    )
    ecdna.add_argument("input", type=str)
    ecdna.add_argument("--context-key", default=None)
    ecdna.add_argument("--minimum-copy-number", type=float, default=6.0)
    ecdna.add_argument("--minimum-junctions", type=int, default=2)
    ecdna.add_argument("--output", default=None)

    hijack = subparsers.add_parser(
        "detect-enhancer-hijacking",
        help="detect context-qualified enhancer-to-gene structural bridge candidates",
    )
    hijack.add_argument("input", type=str)
    hijack.add_argument("--context-key", required=True)
    hijack.add_argument("--minimum-evidence-channels", type=int, default=2)
    hijack.add_argument("--output", default=None)

    purity = subparsers.add_parser(
        "purity-ploidy", help="import purity and ploidy measurements with source receipts"
    )
    purity.add_argument("input", type=str)
    purity.add_argument("--source-id", default=None)
    purity.add_argument("--format", choices=("tsv", "json"), default=None)
    purity.add_argument("--output", default=None)

    origin = subparsers.add_parser(
        "classify-origin",
        help="classify somatic/germline origin from declared tumor and normal observations",
    )
    origin.add_argument("input", type=str)
    origin.add_argument("--variant-id", default=None)
    origin.add_argument("--minimum-tumor-alt-fraction", type=float, default=0.05)
    origin.add_argument("--normal-presence-fraction", type=float, default=0.02)
    origin.add_argument("--output", default=None)

    mosaic = subparsers.add_parser(
        "estimate-mosaicism",
        help="estimate repeated low-fraction mosaicism evidence across tissues",
    )
    mosaic.add_argument("input", type=str)
    mosaic.add_argument("--prior", type=float, default=0.10)
    mosaic.add_argument("--calibration-id", default=None)
    mosaic.add_argument("--low-fraction-max", type=float, default=0.35)
    mosaic.add_argument("--minimum-tissues", type=int, default=2)
    mosaic.add_argument("--contamination-threshold", type=float, default=0.05)
    mosaic.add_argument("--output", default=None)

    ccf = subparsers.add_parser(
        "estimate-ccf",
        help="estimate cancer-cell fraction from purity, copy number, and VAF",
    )
    ccf.add_argument("input", type=str)
    ccf.add_argument("--normal-copy-number", type=float, default=2.0)
    ccf.add_argument("--output", default=None)

    subclones = subparsers.add_parser(
        "assign-subclones",
        help="assign relative CCF clusters within sample scope",
    )
    subclones.add_argument("input", type=str)
    subclones.add_argument("--max-ccf-distance", type=float, default=0.15)
    subclones.add_argument("--boundary-ambiguity", type=float, default=0.02)
    subclones.add_argument("--output", default=None)

    ccre = subparsers.add_parser("parse-ccre", help="parse an ENCODE SCREEN-style cCRE track")
    ccre.add_argument("input", type=str)
    ccre.add_argument("--source-id", default=None)
    ccre.add_argument(
        "--profile", choices=[item.value for item in CcreAtlasProfile], default="encode_screen_ccre"
    )
    ccre.add_argument("--format", choices=("tsv", "json"), default=None)
    ccre.add_argument("--output", default=None)

    chromatin = subparsers.add_parser(
        "parse-chromatin", help="parse a context-qualified ATAC, DNase, histone, or H3K27ac track"
    )
    chromatin.add_argument("input", type=str)
    chromatin.add_argument("--source-id", default=None)
    chromatin.add_argument(
        "--track-kind", choices=[item.value for item in ChromatinTrackKind], required=True
    )
    chromatin.add_argument("--format", choices=("tsv", "json"), default=None)
    chromatin.add_argument("--output", default=None)

    state_atlas = subparsers.add_parser(
        "query-state-atlas",
        help="query an exact molecular-state atlas record against a context-qualified interval",
    )
    state_atlas.add_argument("input", type=str)
    state_atlas.add_argument(
        "--molecular-state",
        choices=[item.value for item in MolecularAtlasState],
        required=True,
    )
    state_atlas.add_argument("--chromosome", required=True)
    state_atlas.add_argument("--start", type=int, required=True)
    state_atlas.add_argument("--end", type=int, required=True)
    state_atlas.add_argument("--context-key", required=True)
    state_atlas.add_argument("--source-id", default="state-atlas-cli")
    state_atlas.add_argument("--source-version", default="unspecified")
    state_atlas.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    state_atlas.add_argument("--coordinate-system", choices=("bed", "one_based"), default="bed")
    state_atlas.add_argument("--output", default=None)

    histone = subparsers.add_parser(
        "harmonize-histone",
        help="harmonize context-qualified histone-mark tracks into atomic intervals",
    )
    histone.add_argument("input", type=str)
    histone.add_argument("--source-id", default=None)
    histone.add_argument("--source-version", default="unspecified")
    histone.add_argument("--format", choices=("tsv", "csv", "json"), default=None)
    histone.add_argument("--coordinate-system", choices=("bed", "one_based"), default="bed")
    histone.add_argument("--spread-tolerance", type=float, default=0.25)
    histone.add_argument("--output", default=None)

    motif_disruption = subparsers.add_parser(
        "scan-motif-disruption",
        help="compare reference and alternate sequence windows for declared motif losses",
    )
    motif_disruption.add_argument("input", type=str)
    motif_disruption.add_argument("--variant-id", default=None)
    motif_disruption.add_argument("--window-start", type=int, default=None)
    motif_disruption.add_argument("--context-key", default=None)
    motif_disruption.add_argument("--output", default=None)

    motif_creation = subparsers.add_parser(
        "scan-motif-creation",
        help="compare reference and alternate sequence windows for declared motif gains",
    )
    motif_creation.add_argument("input", type=str)
    motif_creation.add_argument("--variant-id", default=None)
    motif_creation.add_argument("--window-start", type=int, default=None)
    motif_creation.add_argument("--context-key", default=None)
    motif_creation.add_argument("--output", default=None)

    motif_grammar = subparsers.add_parser(
        "analyze-motif-grammar",
        help="evaluate declared motif spacing and orientation grammar rules",
    )
    motif_grammar.add_argument("input", type=str)
    motif_grammar.add_argument("--context-key", default=None)
    motif_grammar.add_argument("--output", default=None)

    cooperative_grammar = subparsers.add_parser(
        "score-cooperative-grammar",
        help="score versioned cooperative motif interactions as a descriptive model output",
    )
    cooperative_grammar.add_argument("input", type=str)
    cooperative_grammar.add_argument("--model-id", required=True)
    cooperative_grammar.add_argument("--model-version", required=True)
    cooperative_grammar.add_argument("--context-key", default=None)
    cooperative_grammar.add_argument("--baseline", type=float, default=0.0)
    cooperative_grammar.add_argument("--output", default=None)

    methylation_parse = subparsers.add_parser(
        "parse-methylation",
        help="parse one-based or BED-like methylation records with source receipts",
    )
    methylation_parse.add_argument("input", type=str)
    methylation_parse.add_argument("--source-id", default=None)
    methylation_parse.add_argument("--source-version", default="unspecified")
    methylation_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    methylation_parse.add_argument(
        "--coordinate-system", choices=("one_based", "bed"), default="one_based"
    )
    methylation_parse.add_argument("--output", default=None)

    methylation_query = subparsers.add_parser(
        "query-methylation-context",
        help="retrieve methylation records for an exact context and interval",
    )
    methylation_query.add_argument("input", type=str)
    methylation_query.add_argument("--chromosome", required=True)
    methylation_query.add_argument("--start", type=int, required=True)
    methylation_query.add_argument("--end", type=int, required=True)
    methylation_query.add_argument("--context-key", required=True)
    methylation_query.add_argument("--source-id", default=None)
    methylation_query.add_argument("--source-version", default="unspecified")
    methylation_query.add_argument("--format", choices=("tsv", "json"), default=None)
    methylation_query.add_argument(
        "--coordinate-system", choices=("one_based", "bed"), default="one_based"
    )
    methylation_query.add_argument("--beta-spread-tolerance", type=float, default=0.20)
    methylation_query.add_argument("--output", default=None)

    cpg = subparsers.add_parser(
        "analyze-cpg-change",
        help="detect allele-specific CpG creation or loss with optional methylation context",
    )
    cpg.add_argument("input", type=str)
    cpg.add_argument("--variant-id", default=None)
    cpg.add_argument("--window-start", type=int, default=None)
    cpg.add_argument("--chromosome", default=None)
    cpg.add_argument("--context-key", default=None)
    cpg.add_argument("--methylated-threshold", type=float, default=0.50)
    cpg.add_argument("--output", default=None)

    methylation_motifs = subparsers.add_parser(
        "analyze-methylation-motifs",
        help="annotate declared motif hits with exact methylation-sensitive positions",
    )
    methylation_motifs.add_argument("input", type=str)
    methylation_motifs.add_argument("--sequence-id", default=None)
    methylation_motifs.add_argument("--window-start", type=int, default=None)
    methylation_motifs.add_argument("--chromosome", default=None)
    methylation_motifs.add_argument("--context-key", default=None)
    methylation_motifs.add_argument("--methylation-spread-tolerance", type=float, default=0.20)
    methylation_motifs.add_argument("--output", default=None)

    idh_methylation = subparsers.add_parser(
        "model-idh-hypermethylation",
        help="model a declared IDH-state methylation panel against a comparator",
    )
    idh_methylation.add_argument("input", type=str)
    idh_methylation.add_argument("--model-id", required=True)
    idh_methylation.add_argument("--model-version", required=True)
    idh_methylation.add_argument("--context-key", required=True)
    idh_methylation.add_argument("--molecular-state", default="IDH-mutant")
    idh_methylation.add_argument("--comparator-state", default="IDH-wildtype")
    idh_methylation.add_argument("--methylated-threshold", type=float, default=0.70)
    idh_methylation.add_argument("--minimum-sites", type=int, default=3)
    idh_methylation.add_argument("--output", default=None)

    context = subparsers.add_parser(
        "parse-context",
        help="parse context-qualified disease, age, molecular, or territory observations",
    )
    context.add_argument("input", type=str)
    context.add_argument("--source-id", default=None)
    context.add_argument("--format", choices=("tsv", "json"), default=None)
    context.add_argument("--output", default=None)

    contacts = subparsers.add_parser(
        "parse-contacts", help="parse a context-qualified Hi-C or Micro-C contact matrix"
    )
    contacts.add_argument("input", type=str)
    contacts.add_argument("--source-id", default=None)
    contacts.add_argument("--assay", choices=[item.value for item in TopologyAssay], required=True)
    contacts.add_argument("--format", choices=("tsv", "json"), default=None)
    contacts.add_argument("--output", default=None)

    boundaries = subparsers.add_parser(
        "parse-boundaries", help="parse context-qualified TAD boundary candidates"
    )
    boundaries.add_argument("input", type=str)
    boundaries.add_argument("--source-id", default=None)
    boundaries.add_argument(
        "--assay", choices=[item.value for item in TopologyAssay], required=True
    )
    boundaries.add_argument("--format", choices=("tsv", "json"), default=None)
    boundaries.add_argument("--output", default=None)

    genes = subparsers.add_parser(
        "parse-genes", help="parse context-qualified gene intervals for link baselines"
    )
    genes.add_argument("input", type=str)
    genes.add_argument("--source-id", default=None)
    genes.add_argument("--format", choices=("tsv", "json"), default=None)
    genes.add_argument("--genome-build", default="GRCh38")
    genes.add_argument("--output", default=None)

    factor_graph = subparsers.add_parser(
        "factor-graph", help="construct a replayable factor graph from JSON factors"
    )
    factor_graph.add_argument("input", type=str)
    factor_graph.add_argument("--context-key", required=True)
    factor_graph.add_argument("--graph-id", default="factor-graph")
    factor_graph.add_argument("--output", default=None)

    cohort_query = subparsers.add_parser(
        "cohort-query", help="apply an exact-context cohort query to a JSON record bundle"
    )
    cohort_query.add_argument("input", type=str)
    cohort_query.add_argument("--output", default=None)

    encode_sequence = subparsers.add_parser(
        "encode-sequence", help="emit deterministic sequence context features"
    )
    encode_sequence.add_argument("sequence", type=str)
    encode_sequence.add_argument("--sequence-id", required=True)
    encode_sequence.add_argument("--source-id", default="sequence-cli")
    encode_sequence.add_argument("--kmer-size", type=int, default=3)
    encode_sequence.add_argument("--output", default=None)

    effect = subparsers.add_parser(
        "parse-effect", help="parse a foundation or long-context model output table"
    )
    effect.add_argument("input", type=str)
    effect.add_argument("--source-id", default=None)
    effect.add_argument("--adapter", choices=("foundation", "long-context"), default="foundation")
    effect.add_argument("--output", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "schema":
            _write_json(schema_document(), args.output)
            return 0
        if args.command == "sources":
            _write_json(default_source_catalog().manifest(), None)
            return 0
        if args.command == "registry":
            _write_json(default_control_plane_registry().manifest(), None)
            return 0
        if args.command == "bindings":
            _write_json(ControlPlaneApplication().manifest(), None)
            return 0
        if args.command == "capabilities":
            _write_json(default_capability_registry().manifest(), None)
            return 0
        if args.command == "references":
            _write_json(default_reference_registry().manifest(), None)
            return 0
        if args.command == "parse-gencode":
            input_path = Path(args.input)
            result = GencodeTranscriptAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                assembly=args.assembly,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-mane":
            input_path = Path(args.input)
            result = ManeTranscriptAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "normalize-regulatory-term":
            catalog_path = Path(args.catalog)
            adapter = RegulatoryOntologyAdapter()
            catalog = adapter.parse_text(
                catalog_path.read_text(encoding="utf-8"),
                source_id=args.source_id or catalog_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            result = adapter.normalize(_read_json(args.input), catalog=catalog)
            _write_json(
                {"catalog": catalog.to_dict(), "normalization": result.to_dict()},
                args.output,
            )
            return 0
        if args.command == "map-disease-term":
            catalog_path = Path(args.catalog)
            mapper = DiseaseOntologyMapper()
            catalog = mapper.parse_text(
                catalog_path.read_text(encoding="utf-8"),
                source_id=args.source_id or catalog_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            result = mapper.map(_read_json(args.input), catalog=catalog)
            _write_json({"catalog": catalog.to_dict(), "mapping": result.to_dict()}, args.output)
            return 0
        if args.command == "parse-citations":
            input_path = Path(args.input)
            result = CitationResolver().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evidence-graph":
            payload = _read_json(args.input)
            citations = tuple(
                EvidenceCitation.from_mapping(
                    row,
                    fallback_source_id=str(row.get("source_id", "declared_source")),
                    fallback_version=str(row.get("version", "unspecified")),
                    fallback_row_number=index,
                )
                for index, row in enumerate(payload.get("citations", ()), start=1)
            )
            claims = tuple(
                VersionedEvidenceClaim.from_mapping(
                    row,
                    fallback_id=f"{Path(args.input).stem}:{index}",
                    context_key=args.context_key,
                )
                for index, row in enumerate(payload.get("claims", ()), start=1)
            )
            graph = VersionedEvidenceGraphConstructor().construct(
                claims,
                citations=citations,
                graph_id=args.graph_id,
                context_key=args.context_key,
            )
            _write_json(EvidenceDossierPublisher().publish(graph).to_dict(), args.output)
            return 0
        if args.command == "workspace-case":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            _write_json(CaseWorkspaceBuilder().build(manifest).to_dict(), args.output)
            return 0
        if args.command == "workspace-track":
            input_path = Path(args.input)
            batch = RegulatoryTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                genome_build=args.genome_build,
                input_format=args.format,
            )
            workspace = RegulatoryTrackBrowser().build(batch, context_key=args.context_key)
            _write_json(workspace.to_dict(), args.output)
            return 0
        if args.command == "mission-plan":
            payload = _read_json(args.input)
            raw = dict(payload.get("mission", payload))
            mission = MissionContext(
                mission_id=str(raw.get("mission_id", "mission-cli")),
                project_id=str(raw.get("project_id", "glio-noncode")),
                intended_use=str(raw.get("intended_use", "research hypothesis exploration")),
                requested_question=str(raw.get("requested_question", "bounded research question")),
                claim_ceiling=ClaimCeiling(
                    str(raw.get("claim_ceiling", ClaimCeiling.HYPOTHESIS.value))
                ),
                allowed_source_ids=tuple(str(item) for item in raw.get("allowed_source_ids", ())),
                allowed_data_scopes=tuple(
                    str(item)
                    for item in raw.get("allowed_data_scopes", ("synthetic", "public_reference"))
                ),
                allowed_mutations=tuple(
                    str(item)
                    for item in raw.get(
                        "allowed_mutations", ("none", "event_log", "content_addressed_store")
                    )
                ),
            )
            request = MissionRequest(
                mission=mission,
                requested_agent_ids=tuple(
                    str(item) for item in payload.get("requested_agent_ids", ())
                ),
                workflow_id=str(payload.get("workflow_id", "mission-cli-workflow")),
            )
            _write_json(MissionPlanBuilder().plan(request).to_dict(), args.output)
            return 0
        if args.command == "intake":
            input_path = Path(args.input)
            source_id = args.source_id or input_path.stem
            intake_engine = VariantIntake(default_build=args.genome_build)
            if args.format == IntakeFormat.BCF.value or input_path.suffix.lower() == ".bcf":
                batch = intake_engine.parse_bytes(
                    input_path.read_bytes(),
                    source_id=source_id,
                    genome_build=args.genome_build,
                    sample_id=args.sample_id,
                    include_no_call=args.include_no_call,
                )
            else:
                batch = intake_engine.parse_text(
                    input_path.read_text(encoding="utf-8"),
                    source_id=source_id,
                    input_format=args.format,
                    genome_build=args.genome_build,
                    sample_id=args.sample_id,
                    include_no_call=args.include_no_call,
                )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "parse-track":
            input_path = Path(args.input)
            batch = RegulatoryTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                genome_build=args.genome_build,
                input_format=args.format,
            )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "normalize":
            report = VRSNormalizer().normalize(
                args.notation,
                genome_build=args.genome_build,
                sequence_digest=args.sequence_digest,
                reference_sequence=args.reference_sequence,
                reference_start=args.reference_start,
            )
            _write_json(report.to_dict(), args.output)
            return 0
        if args.command == "normalize-categorical":
            payload = _read_json(args.input)
            if args.catalog:
                catalog_path = Path(args.catalog)
                batch = CategoricalCatalogParser().parse_text(
                    catalog_path.read_text(encoding="utf-8"),
                    source_id=args.source_id or catalog_path.stem,
                    source_version=args.source_version,
                    input_format=args.format,
                )
                report = CatVRSNormalizer(batch.definitions).normalize(payload)
                _write_json(
                    {"catalog": batch.to_dict(), "normalization": report.to_dict()},
                    args.output,
                )
            else:
                _write_json(CatVRSNormalizer().normalize(payload).to_dict(), args.output)
            return 0
        if args.command == "build-annotation":
            payload = _read_json(args.input)
            builder = VAAnnotationEnvelopeBuilder()
            envelope = builder.build_from_mappings(
                str(args.annotation_id or payload.get("annotation_id", "annotation-cli")),
                dict(payload.get("subject", {})),
                payload.get("statements", ()),
                payload.get("evidence_lines", payload.get("evidence", ())),
                context_key=args.context_key,
                profile=args.profile,
                specification_version=args.specification_version,
            )
            _write_json(envelope.to_dict(), args.output)
            return 0
        if args.command == "decompose-multiallelic":
            result = MultiAllelicDecomposer().decompose(
                _read_json(args.input),
                genome_build=args.genome_build,
                source_id=args.source_id,
                source_version=args.source_version,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "normalize-repeat":
            payload = _read_json(args.input)
            reference_start = args.reference_start
            if reference_start is None:
                reference_start = int(payload.get("reference_start", 0))
            if not reference_start:
                raise ValueError("normalize-repeat requires reference_start")
            if "reference_sequence" not in payload:
                raise ValueError("normalize-repeat requires reference_sequence")
            result = RepeatAwareNormalizer().normalize(
                payload.get("variant", payload),
                reference_sequence=str(payload["reference_sequence"]),
                reference_start=reference_start,
                max_shift_bp=args.max_shift_bp,
                genome_build=args.genome_build,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "sv-consensus":
            input_path = Path(args.input)
            batch = SVConsensusImporter(breakpoint_tolerance=args.breakpoint_tolerance).parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(batch.to_dict(), args.output)
            return 0
        if args.command == "harmonize-cn":
            input_path = Path(args.input)
            result = CopyNumberSegmentHarmonizer().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "map-focal-amplification":
            result = FocalAmplificationBoundaryMapper().map(
                _read_rows(args.input, "records", "segments"),
                context_key=args.context_key,
                baseline_copy_number=args.baseline_copy_number,
                amplification_threshold=args.amplification_threshold,
                minimum_gain=args.minimum_gain,
                merge_gap_bp=args.merge_gap_bp,
                boundary_tolerance_bp=args.boundary_tolerance_bp,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "detect-chromothripsis":
            result = ChromothripsisPatternDetector().detect(
                _read_rows(args.input, "records", "breakpoints"),
                context_key=args.context_key,
                min_breakpoints=args.min_breakpoints,
                max_cluster_span_bp=args.max_cluster_span_bp,
                max_gap_bp=args.max_gap_bp,
                min_orientation_switches=args.min_orientation_switches,
                require_copy_number_oscillation=args.require_copy_number_oscillation,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "detect-ecdna":
            result = ExtrachromosomalDnaCandidateDetector().detect(
                _read_rows(args.input, "records", "evidence"),
                context_key=args.context_key,
                minimum_copy_number=args.minimum_copy_number,
                minimum_junctions=args.minimum_junctions,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "detect-enhancer-hijacking":
            result = EnhancerHijackingCandidateDetector().detect(
                _read_rows(args.input, "records", "evidence", "links"),
                context_key=args.context_key,
                minimum_evidence_channels=args.minimum_evidence_channels,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "purity-ploidy":
            input_path = Path(args.input)
            result = PurityPloidyImporter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "classify-origin":
            result = SomaticGermlineOriginClassifier().classify(
                _read_rows(args.input, "records", "observations"),
                variant_id=args.variant_id,
                minimum_tumor_alt_fraction=args.minimum_tumor_alt_fraction,
                normal_presence_fraction=args.normal_presence_fraction,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-mosaicism":
            result = MosaicismPosteriorEstimator().estimate(
                _read_rows(args.input, "records", "observations"),
                prior=args.prior,
                calibration_id=args.calibration_id,
                low_fraction_max=args.low_fraction_max,
                minimum_tissues=args.minimum_tissues,
                contamination_threshold=args.contamination_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-ccf":
            result = CancerCellFractionEstimator().estimate(
                _read_rows(args.input, "records", "observations"),
                normal_copy_number=args.normal_copy_number,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "assign-subclones":
            result = SubcloneAssigner().assign(
                _read_rows(args.input, "records", "estimates"),
                max_ccf_distance=args.max_ccf_distance,
                boundary_ambiguity=args.boundary_ambiguity,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-ccre":
            input_path = Path(args.input)
            result = CcreTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                profile=args.profile,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-chromatin":
            input_path = Path(args.input)
            result = ChromatinTrackParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                track_kind=args.track_kind,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "query-state-atlas":
            payload = _read_json(args.input)
            rows = payload.get("records", payload.get("elements", ()))
            if not isinstance(rows, list):
                raise ValueError("state atlas JSON must contain a records list")
            context = _context_from_key(args.context_key)
            adapter = MolecularStateAtlasAdapter()
            batch = adapter.parse_text(
                json.dumps({"records": rows}),
                source_id=args.source_id,
                source_version=args.source_version,
                input_format="json",
                coordinate_system=args.coordinate_system,
            )
            query = adapter.query(
                batch.records,
                molecular_state=args.molecular_state,
                chromosome=args.chromosome,
                start=args.start,
                end=args.end,
                context=context,
            )
            _write_json({"catalog": batch.to_dict(), "query": query.to_dict()}, args.output)
            return 0
        if args.command == "harmonize-histone":
            input_path = Path(args.input)
            result = HistoneMarkTrackHarmonizer().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                coordinate_system=args.coordinate_system,
                spread_tolerance=args.spread_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-methylation":
            input_path = Path(args.input)
            result = MethylationRecordParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                coordinate_system=args.coordinate_system,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "query-methylation-context":
            input_path = Path(args.input)
            batch = MethylationRecordParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                coordinate_system=args.coordinate_system,
            )
            result = MethylationContextRetriever(batch.records).query(
                args.chromosome,
                args.start,
                args.end,
                context_key=args.context_key,
                beta_spread_tolerance=args.beta_spread_tolerance,
            )
            _write_json({"catalog": batch.to_dict(), "query": result.to_dict()}, args.output)
            return 0
        if args.command == "analyze-cpg-change":
            payload = _read_json(args.input)
            result = CpGCreationLossAnalyzer().analyze(
                str(payload.get("reference_sequence", "")),
                str(payload.get("alternate_sequence", "")),
                variant_id=args.variant_id or str(payload.get("variant_id", Path(args.input).stem)),
                window_start=(
                    args.window_start
                    if args.window_start is not None
                    else int(payload.get("window_start", 1))
                ),
                chromosome=args.chromosome or str(payload.get("chromosome", "unspecified")),
                context_key=args.context_key or payload.get("context_key"),
                methylation_records=payload.get("methylation_records", payload.get("records", ())),
                methylated_threshold=args.methylated_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "analyze-methylation-motifs":
            payload = _read_json(args.input)
            result = MethylationSensitiveMotifAnalyzer().analyze(
                str(payload.get("sequence", "")),
                sequence_id=args.sequence_id
                or str(payload.get("sequence_id", Path(args.input).stem)),
                motifs=_methylation_motifs(payload.get("motifs", ())),
                methylation_records=payload.get("methylation_records", payload.get("records", ())),
                window_start=(
                    args.window_start
                    if args.window_start is not None
                    else int(payload.get("window_start", 1))
                ),
                chromosome=args.chromosome or str(payload.get("chromosome", "unspecified")),
                context_key=args.context_key or payload.get("context_key"),
                methylation_spread_tolerance=args.methylation_spread_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "model-idh-hypermethylation":
            payload = _read_json(args.input)
            result = IdhHypermethylationContextModel().assess(
                payload.get("target_records", payload.get("records", ())),
                context_key=args.context_key,
                molecular_state=args.molecular_state,
                comparator_records=payload.get("comparator_records", ()),
                comparator_state=args.comparator_state,
                model_id=args.model_id,
                model_version=args.model_version,
                methylated_threshold=args.methylated_threshold,
                minimum_sites=args.minimum_sites,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in {"scan-motif-disruption", "scan-motif-creation"}:
            payload = _read_json(args.input)
            variant_id = args.variant_id or str(payload.get("variant_id", Path(args.input).stem))
            window_start = args.window_start
            if window_start is None:
                window_start = int(payload.get("window_start", 1))
            context_key = args.context_key or payload.get("context_key")
            motifs = _motif_definitions(payload.get("motifs", ()))
            scanner = (
                MotifDisruptionScanner()
                if args.command == "scan-motif-disruption"
                else MotifCreationScanner()
            )
            result = scanner.scan(
                str(payload.get("reference_sequence", "")),
                str(payload.get("alternate_sequence", "")),
                variant_id=variant_id,
                motifs=motifs,
                window_start=window_start,
                context_key=context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "analyze-motif-grammar":
            payload = _read_json(args.input)
            result = MotifSpacingGrammarAnalyzer().analyze(
                payload.get("hits", ()),
                _grammar_rules(payload.get("rules", ())),
                context_key=args.context_key or payload.get("context_key"),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "score-cooperative-grammar":
            payload = _read_json(args.input)
            result = CooperativeTFGrammarModel().score(
                payload.get("hits", ()),
                _grammar_interactions(payload.get("interactions", ())),
                sequence_id=str(payload.get("sequence_id", Path(args.input).stem)),
                sequence=str(payload.get("sequence", "")),
                model_id=args.model_id,
                model_version=args.model_version,
                context_key=args.context_key or payload.get("context_key"),
                baseline=args.baseline,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-context":
            input_path = Path(args.input)
            result = ContextObservationParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-contacts":
            input_path = Path(args.input)
            result = ContactMatrixParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                assay=args.assay,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-boundaries":
            input_path = Path(args.input)
            result = TadBoundaryParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                assay=args.assay,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-genes":
            input_path = Path(args.input)
            result = GeneFeatureParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                input_format=args.format,
                default_genome_build=args.genome_build,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "factor-graph":
            payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
            rows = payload.get("factors", payload) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ValueError("factor graph JSON must contain a factors list")
            factors = tuple(
                FactorObservation.from_mapping(
                    row,
                    fallback_id=f"{Path(args.input).stem}:{index}",
                    context_key=args.context_key,
                )
                for index, row in enumerate(rows, start=1)
            )
            result = FactorGraphConstructor().construct(
                factors, context_key=args.context_key, graph_id=args.graph_id
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "cohort-query":
            payload = _read_json(args.input)
            context = ReferenceContext.from_dict(payload["context"])
            records = tuple(
                CohortVariantRecord(
                    record_id=str(item["record_id"]),
                    variant=VariantIdentity.from_dict(item["variant"]),
                    context_key=str(item.get("context_key", context.key)),
                    source_id=str(item.get("source_id", "cohort-cli")),
                    sample_id=str(item.get("sample_id", "unspecified")),
                    callable=bool(item.get("callable", True)),
                    sequence_context=item.get("sequence_context"),
                    chromatin_features={
                        str(key): float(value)
                        for key, value in dict(item.get("chromatin_features", {})).items()
                    },
                    annotations=dict(item.get("annotations", {})),
                )
                for item in payload.get("records", ())
            )
            query_raw = dict(payload.get("query", {}))
            query = CohortQuery(
                query_id=str(query_raw.get("query_id", "cohort-cli")),
                context_key=str(query_raw.get("context_key", context.key)),
                variant_kinds=tuple(str(item) for item in query_raw.get("variant_kinds", ())),
                origins=tuple(str(item) for item in query_raw.get("origins", ())),
                chromosomes=tuple(str(item) for item in query_raw.get("chromosomes", ())),
                sample_ids=tuple(str(item) for item in query_raw.get("sample_ids", ())),
                require_callable=bool(query_raw.get("require_callable", True)),
            )
            result = CohortQueryBuilder().build(query, records)
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "encode-sequence":
            result = SequenceContextEncoder().encode(
                args.sequence,
                sequence_id=args.sequence_id,
                source_id=args.source_id,
                kmer_size=args.kmer_size,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-effect":
            input_path = Path(args.input)
            adapter = (
                LongContextVariantEffectAdapter()
                if args.adapter == "long-context"
                else SequenceFoundationModelAdapter()
            )
            result = adapter.parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evaluate":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            retriever = (
                PublicReferenceRetriever(
                    cache_root=Path(args.data_root) / "source-cache", window_bp=args.window_bp
                )
                if args.live_reference
                else None
            )
            dossier = CaseRuntime(args.data_root, reference_retriever=retriever).evaluate(
                manifest,
                live_reference=args.live_reference,
            )
            _write_json(dossier.to_dict(), args.output)
            return 0
        if args.command == "fetch-public":
            manifest = CaseManifest.from_dict(_read_json(args.manifest))
            retriever = PublicReferenceRetriever(
                cache_root=Path(args.data_root) / "source-cache",
                window_bp=args.window_bp,
            )
            _write_json(retriever.enrich_manifest(manifest).to_dict(), args.output)
            return 0
        if args.command == "serve":
            server = create_server(args.host, args.port, args.data_root)
            print(f"glio-noncode listening on http://{args.host}:{args.port}")
            server.serve_forever()
            return 0
    except (GlioError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1
