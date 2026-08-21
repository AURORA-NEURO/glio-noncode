"""Command-line entry point for local case evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .api import create_server
from .atlas_alpha import (
    EnhancerPromoterSilencerClassifier,
    MethylationTrackHarmonizer,
    OpenChromatinTrackHarmonizer,
    SuperEnhancerCandidateAtlas,
)
from .atlas_beta import (
    HistoneMarkTrackHarmonizer,
    MolecularAtlasState,
    MolecularStateAtlasAdapter,
)
from .atlas_extensions import CcreAtlasProfile, CcreTrackParser
from .capability_registry import default_capability_registry
from .causal_alpha import (
    ConfoundingChecklistAdjudicator,
    DependenceMethod,
    EvidenceDependenceCorrector,
    MediationSensitivityAnalyzer,
    NegativeEvidenceIntegrator,
)
from .causal_beta import (
    CausalMediatorEvidenceParser,
    CounterfactualAlleleStateSimulator,
    ElementToGeneCausalMediator,
    GeneToStateCausalMediator,
    MediatorKind,
    SequenceToElementCausalMediator,
)
from .causal_reasoning import FactorGraphConstructor, FactorObservation
from .cell_context import ContextObservationParser
from .cell_context_alpha import (
    CoreMarginTerritoryPrior,
    RecurrenceStatePrior,
    SpatialNichePrior,
    TreatmentInducedStatePrior,
)
from .cell_context_beta import (
    ContextPriorObservationParser,
    DevelopmentalLineagePrior,
    GlioblastomaMalignantStatePrior,
    H3K27AlteredDevelopmentalStatePrior,
    IdhMutantLineageStatePrior,
)
from .chromatin_alpha import (
    AlleleSpecificChromatinAnalyzer,
    BatchCellCompositionCorrector,
    ChromatinStateSegmentationAdapter,
    EpigenomicPurityDeconvolver,
)
from .chromatin_context import ChromatinTrackKind, ChromatinTrackParser
from .cohort_alpha import (
    ClonalityTimingIntegrator,
    CrossCohortReplicationEngine,
    PrimaryRecurrenceComparator,
    TreatmentSelectionSignalDetector,
)
from .cohort_beta import (
    FunctionalConvergenceParser,
    FunctionalConvergenceTester,
    PathwayRegulonConvergenceTester,
    PathwayRegulonParser,
    RegionalBurdenParser,
    RegionalBurdenTester,
    RegulatoryRecurrenceParser,
    RegulatoryRecurrenceTester,
    SetKind,
)
from .cohort_discovery import CohortQuery, CohortQueryBuilder, CohortVariantRecord
from .control_beta import (
    BudgetResourceScheduler,
    DeterministicFallbackRouter,
    FallbackRequest,
    HumanReviewQueueRouter,
    PolicyClaimAuditor,
)
from .control_plane import (
    ClaimCeiling,
    InvocationRequest,
    MissionContext,
    ProvenanceContext,
    default_control_plane_registry,
)
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
from .frontier_context_alpha import (
    CONTEXT_FRONTIER_OPERATIONS,
    run_context_frontier_operation,
)
from .frontier_contracts import default_frontier_contract_registry
from .frontier_data_alpha import FRONTIER_OPERATIONS, run_frontier_operation
from .frontier_end_to_end import END_TO_END_OPERATIONS, run_end_to_end_operation
from .frontier_fixture_eval import evaluate_frontier_fixture
from .frontier_inference_alpha import (
    INFERENCE_FRONTIER_OPERATIONS,
    run_inference_frontier_operation,
)
from .frontier_public_data import audit_public_fixture
from .frontier_quality_gate import evaluate_frontier_quality_gate
from .frontier_release_alpha import (
    RELEASE_FRONTIER_OPERATIONS,
    run_release_frontier_operation,
)
from .frontier_scenario_matrix import evaluate_frontier_scenarios
from .frontier_release_hardening import HARDENING_OPERATIONS, run_hardening_operation
from .frontier_replay import replay_frontier_fixtures
from .identity_beta import (
    BatchSampleIdentityChecker,
    ChainOfCustodyCapture,
    DuplicateAliasReconciler,
    VariantEquivalenceResolver,
)
from .intake import IntakeFormat, VariantIntake
from .lifecycle_alpha import (
    BlindedAdjudicationPlan,
    BlindedAdjudicationWorkflow,
    EvidenceDeltaDetector,
    ReleaseDecision,
    ReleaseDecisionRecorder,
    ReviewerCommentChangeLogger,
)
from .lifecycle_beta import (
    EvidenceTierAdjudicator,
    ProvenanceLineageViewer,
    ReviewerAssignmentRouter,
    ReviewerRole,
    UncertaintyLedgerBuilder,
)
from .link_graph import GeneFeatureParser
from .link_graph_alpha import (
    ContactAssayKind,
    CRISPRPerturbationLinkAdapter,
    CRISPRPerturbationLinker,
    MultiGeneElementGraphBuilder,
    PromoterTetheringModel,
    ThreeDContactLinkAdapter,
    ThreeDContactLinker,
)
from .link_graph_beta import (
    ActivityByContactLinkAdapter,
    AlleleSpecificLinkEvidenceIntegrator,
    CoaccessibilityLinker,
    MolecularQtlLinker,
)
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
from .platform_alpha import (
    DataReferenceRegistry,
    DriftAndOODMonitor,
    EventSourcedExecutionLedger,
    ModelRegistry,
)
from .reference_alpha import (
    GeneAliasVersionResolver,
    LicenseUseRestrictionRegistry,
    PopulationFrequencyAdapter,
    ReferenceSnapshotManager,
)
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
from .sequence_alpha import (
    NucleosomeSequencePropensityModel,
    PromoterCoreGrammarModel,
    PromoterGrammarRule,
    PromoterMotifDefinition,
    SpliceMotifDefinition,
    SpliceRegulatoryNoncodingScanner,
    UtrMotifDefinition,
    UtrRegulatoryScanner,
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
from .specimen_lineage import (
    LongitudinalSpecimenLinker,
    MultiRegionLineageResolver,
    PrimaryRecurrencePhaseMapper,
    TreatmentExposureContextualizer,
)
from .structural_beta import (
    ChromothripsisPatternDetector,
    EnhancerHijackingCandidateDetector,
    ExtrachromosomalDnaCandidateDetector,
    FocalAmplificationBoundaryMapper,
)
from .structural_extensions import CopyNumberSegmentHarmonizer, SVConsensusImporter
from .structural_haplotype import (
    AlleleAwareSvRepresenter,
    PangenomeGraphProjector,
    PhasedHaplotypeAssembler,
    RepeatMobileElementAnnotator,
)
from .topology_alpha import (
    BoundaryMotifOrientationAnalyzer,
    CTCFCohesinDisruptionModel,
    IDHInsulatorDysfunctionModel,
    SVTopologyRewiringSimulator,
)
from .topology_beta import (
    ActivityByContactScorer,
    EnhancerPromoterContactScorer,
    LoopStripeAdapter,
    PromoterCaptureContactAdapter,
)
from .topology_context import (
    ContactMatrixParser,
    TadBoundaryParser,
    TopologyAssay,
)
from .validation_alpha import (
    ControlsRandomizationPlanner,
    ControlType,
    GuideOligoDesignAdapter,
    ModelSystemEligibilityMatcher,
    PowerReplicationEstimator,
)
from .validation_beta import (
    AlleleSpecificReporterPlanner,
    BaseEditingDesignPlanner,
    CRISPRaDesignPlanner,
    CRISPRiDesignPlanner,
    GuideDesignConstraints,
    PerturbationMode,
    PrimeEditingDesignPlanner,
    ValidationBetaTarget,
)
from .variant_beta import (
    CategoricalCatalogParser,
    CatVRSNormalizer,
    MultiAllelicDecomposer,
    RepeatAwareNormalizer,
    VAAnnotationEnvelopeBuilder,
)
from .variant_normalization import VRSNormalizer
from .workflow import ResourceEnvelope
from .workspace import (
    CaseWorkspaceBuilder,
    RegulatoryTrackBrowser,
    ResearchWorkspace,
    WorkspaceKind,
    WorkspaceRecord,
    WorkspaceRecordType,
    WorkspaceSection,
    WorkspaceState,
)
from .workspace_alpha import (
    NotebookRuntime,
    NotebookSDKLauncher,
    RoleBasedCollaborationEvaluator,
    ShareableSnapshotPublisher,
    ValidationExperimentBoardBuilder,
)
from .workspace_beta import (
    CausalChainExplorer,
    EvidenceTableAndFilters,
    EvidenceTableFilter,
    PosteriorDecompositionViewer,
    TopologyViewer,
)


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


def _workspace_from_payload(payload: Mapping[str, Any]) -> ResearchWorkspace:
    raw = payload.get("workspace", payload)
    if not isinstance(raw, Mapping):
        raise ValueError("workspace payload must be an object")
    records = tuple(
        WorkspaceRecord(
            record_id=str(row["record_id"]),
            record_type=WorkspaceRecordType(str(row["record_type"])),
            label=str(row["label"]),
            context_key=str(row["context_key"]),
            state=WorkspaceState(str(row["state"])),
            source_ids=tuple(str(item) for item in row.get("source_ids", ())),
            chromosome=str(row["chromosome"]) if row.get("chromosome") is not None else None,
            start=int(row["start"]) if row.get("start") is not None else None,
            end=int(row["end"]) if row.get("end") is not None else None,
            tags=tuple(str(item) for item in row.get("tags", ())),
            fields=dict(row.get("fields", {})),
            searchable_text=str(row.get("searchable_text", "")),
            content_address=str(row.get("content_address", "")),
        )
        for row in raw.get("records", ())
    )
    sections = tuple(
        WorkspaceSection(
            section_id=str(row["section_id"]),
            title=str(row["title"]),
            record_types=tuple(WorkspaceRecordType(str(item)) for item in row["record_types"]),
            order=int(row["order"]),
            accessible_label=str(row["accessible_label"]),
            description=str(row["description"]),
        )
        for row in raw.get("sections", ())
    )
    return ResearchWorkspace(
        workspace_id=str(raw["workspace_id"]),
        kind=WorkspaceKind(str(raw["kind"])),
        context_key=str(raw["context_key"]),
        records=records,
        sections=sections,
        state=WorkspaceState(str(raw["state"])),
        warnings=tuple(str(item) for item in raw.get("warnings", ())),
        content_address=str(raw.get("content_address", "")),
    )


def _invocation_request_from_payload(payload: Mapping[str, Any]) -> InvocationRequest:
    raw = payload.get("request", payload)
    if not isinstance(raw, Mapping):
        raise ValueError("invocation request payload must be an object")
    mission_raw = raw.get("mission", {})
    if not isinstance(mission_raw, Mapping):
        raise ValueError("invocation mission must be an object")
    provenance_raw = raw.get("provenance", {})
    if not isinstance(provenance_raw, Mapping):
        raise ValueError("invocation provenance must be an object")
    mission = MissionContext(
        mission_id=str(mission_raw.get("mission_id", "mission-cli")),
        project_id=str(mission_raw.get("project_id", "glio-noncode")),
        intended_use=str(mission_raw.get("intended_use", "research-only control audit")),
        requested_question=str(
            mission_raw.get("requested_question", "Which declared control path is allowed?")
        ),
        claim_ceiling=ClaimCeiling(
            str(mission_raw.get("claim_ceiling", ClaimCeiling.HYPOTHESIS.value))
        ),
        allowed_source_ids=tuple(str(item) for item in mission_raw.get("allowed_source_ids", ())),
        allowed_data_scopes=tuple(
            str(item)
            for item in mission_raw.get("allowed_data_scopes", ("synthetic", "public_reference"))
        ),
        allowed_mutations=tuple(
            str(item)
            for item in mission_raw.get(
                "allowed_mutations", ("none", "event_log", "content_addressed_store")
            )
        ),
        allow_network=bool(mission_raw.get("allow_network", False)),
        private_data_allowed=bool(mission_raw.get("private_data_allowed", False)),
    )
    provenance = ProvenanceContext(
        input_hashes=tuple(
            str(item) for item in provenance_raw.get("input_hashes", ("sha256:input",))
        ),
        source_versions={
            str(key): str(value) for key, value in provenance_raw.get("source_versions", {}).items()
        },
        upstream_event_ids=tuple(
            str(item) for item in provenance_raw.get("upstream_event_ids", ())
        ),
        reference_build=str(provenance_raw.get("reference_build", "GRCh38")),
        model_digests=tuple(str(item) for item in provenance_raw.get("model_digests", ())),
        parent_bundle_addresses=tuple(
            str(item) for item in provenance_raw.get("parent_bundle_addresses", ())
        ),
    )
    input_payload = raw.get("input_payload", raw.get("payload", {}))
    if not isinstance(input_payload, Mapping):
        raise ValueError("invocation input_payload must be an object")
    return InvocationRequest(
        request_id=str(raw.get("request_id", "request-cli")),
        mission=mission,
        agent_id=str(raw.get("agent_id", raw.get("execution_role_id", "A08"))),
        tool_id=str(raw.get("tool_id", "A08.publish")),
        input_payload=dict(input_payload),
        provenance=provenance,
        idempotency_key=str(raw.get("idempotency_key", "idempotency-cli")),
    )


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


def _splice_alpha_motifs(rows: Any) -> tuple[SpliceMotifDefinition, ...]:
    if not isinstance(rows, list):
        raise ValueError("splice motifs must be a list")
    return tuple(
        SpliceMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", row.get("motif_id", ""))),
            consensus=str(row.get("consensus", "")),
            role=str(row.get("role", "splice_regulatory")),
            source_id=str(row.get("source_id", "splice-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _utr_alpha_motifs(rows: Any) -> tuple[UtrMotifDefinition, ...]:
    if not isinstance(rows, list):
        raise ValueError("UTR motifs must be a list")
    return tuple(
        UtrMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", row.get("motif_id", ""))),
            consensus=str(row.get("consensus", "")),
            element_kind=str(row.get("element_kind", "utr_regulatory")),
            region=str(row.get("region", "both")).lower(),
            source_id=str(row.get("source_id", "utr-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _promoter_alpha_motifs(rows: Any) -> tuple[PromoterMotifDefinition, ...]:
    if not isinstance(rows, list):
        raise ValueError("promoter motifs must be a list")
    return tuple(
        PromoterMotifDefinition(
            motif_id=str(row.get("motif_id", "")),
            name=str(row.get("name", row.get("motif_id", ""))),
            consensus=str(row.get("consensus", "")),
            element_kind=str(row.get("element_kind", "core_promoter")),
            source_id=str(row.get("source_id", "promoter-input")),
            source_version=str(row.get("source_version", "unspecified")),
            threshold=float(row.get("threshold", 0.8)),
            strand_aware=bool(row.get("strand_aware", True)),
        )
        for row in rows
        if isinstance(row, Mapping)
    )


def _promoter_alpha_rules(rows: Any) -> tuple[PromoterGrammarRule, ...]:
    if not isinstance(rows, list):
        raise ValueError("promoter grammar rules must be a list")
    return tuple(
        PromoterGrammarRule(
            rule_id=str(row.get("rule_id", "")),
            motif_a=str(row.get("motif_a", "")),
            motif_b=str(row.get("motif_b", "")),
            minimum_spacing=int(row.get("minimum_spacing", 0)),
            maximum_spacing=int(row.get("maximum_spacing", 0)),
            allowed_orientations=tuple(
                str(item) for item in row.get("allowed_orientations", ("same", "opposite", "any"))
            ),
            weight=float(row.get("weight", 1.0)),
            source_id=str(row.get("source_id", "promoter-grammar")),
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


def _validation_beta_targets(rows: Any) -> tuple[ValidationBetaTarget, ...]:
    if not isinstance(rows, list):
        raise ValueError("validation beta input must contain a targets list")
    return tuple(ValidationBetaTarget.from_mapping(row) for row in rows)


def _guide_constraints(
    payload: Mapping[str, Any],
    *,
    mode: PerturbationMode,
    context_key: str,
    design_id: str | None,
    guide_length: int | None,
    max_guides: int | None,
    require_pam: bool,
    pam_pattern: str | None,
) -> GuideDesignConstraints:
    raw = dict(payload.get("constraints", {}))
    raw["context_key"] = context_key
    raw["mode"] = mode.value
    if design_id is not None:
        raw["design_id"] = design_id
    if guide_length is not None:
        raw["guide_length"] = guide_length
    if max_guides is not None:
        raw["max_guides"] = max_guides
    if require_pam:
        raw["require_pam"] = True
    if pam_pattern is not None:
        raw["pam_pattern"] = pam_pattern
    return GuideDesignConstraints.from_mapping(raw, context_key=context_key, mode=mode)


def _graph_from_payload(payload: Mapping[str, Any]):
    context_key = str(payload.get("context_key", ""))
    if not context_key:
        raise ValueError("graph input requires context_key")
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
            fallback_id=f"graph-cli:{index}",
            context_key=context_key,
        )
        for index, row in enumerate(payload.get("claims", ()), start=1)
    )
    return VersionedEvidenceGraphConstructor().construct(
        claims,
        citations=citations,
        graph_id=str(payload.get("graph_id", "evidence-graph-cli")),
        context_key=context_key,
        graph_version=int(payload.get("graph_version", 1)),
    )


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

    frontier_fixture = subparsers.add_parser(
        "evaluate-frontier-fixture",
        help="run the checked-in D13-D16 frontier fixture and its negative controls",
    )
    frontier_fixture.add_argument("input", type=str)
    frontier_fixture.add_argument("--output", default=None)

    frontier_data = subparsers.add_parser(
        "audit-frontier-data",
        help="audit public identifiers, source receipts, and exact-context fixture data",
    )
    frontier_data.add_argument("input", type=str)
    frontier_data.add_argument("--output", default=None)

    frontier_replay = subparsers.add_parser(
        "replay-frontier-fixtures",
        help="replay one or more frontier fixtures with cross-case integrity checks",
    )
    frontier_replay.add_argument("inputs", nargs="+", type=str)
    frontier_replay.add_argument("--required-context-key", default=None)
    frontier_replay.add_argument("--output", default=None)

    subparsers.add_parser("sources", help="print the live public source catalog")
    subparsers.add_parser("registry", help="print the bounded control-plane registry")
    subparsers.add_parser("bindings", help="print executable control-plane handler bindings")
    subparsers.add_parser("capabilities", help="print the 256-capability implementation ledger")
    subparsers.add_parser("references", help="print the reference assembly registry")
    frontier_contracts = subparsers.add_parser(
        "frontier-contracts", help="print the 79-operation frontier contract registry"
    )
    frontier_contracts.add_argument("--output", default=None)
    frontier_scenarios = subparsers.add_parser(
        "evaluate-frontier-scenarios",
        help="run accepted and review scenarios declared by a frontier fixture",
    )
    frontier_scenarios.add_argument("input", type=str)
    frontier_scenarios.add_argument("--output", default=None)
    frontier_quality = subparsers.add_parser(
        "frontier-quality-gate",
        help="reconcile fixture, public-data, replay, scenario, and contract evidence",
    )
    frontier_quality.add_argument("input", type=str)
    frontier_quality.add_argument("--output", default=None)

    equivalence = subparsers.add_parser(
        "resolve-variant-equivalence",
        help="resolve a variant identity or explicit alias across source records",
    )
    equivalence.add_argument("input", type=str)
    equivalence.add_argument("--query", required=True)
    equivalence.add_argument("--genome-build", default=None)
    equivalence.add_argument("--context-key", default=None)
    equivalence.add_argument("--output", default=None)

    reconciliation = subparsers.add_parser(
        "reconcile-variant-aliases",
        help="reconcile duplicate normalized identities and alias collisions",
    )
    reconciliation.add_argument("input", type=str)
    reconciliation.add_argument("--output", default=None)

    sample_identity = subparsers.add_parser(
        "check-batch-sample-identity",
        help="check declared batch, sample, and subject identity mappings",
    )
    sample_identity.add_argument("input", type=str)
    sample_identity.add_argument("--require-subject", action="store_true")
    sample_identity.add_argument("--allow-missing-batch", action="store_true")
    sample_identity.add_argument("--allow-missing-sample", action="store_true")
    sample_identity.add_argument("--output", default=None)

    custody = subparsers.add_parser(
        "capture-chain-of-custody",
        help="capture artifact custody events and validate chain continuity",
    )
    custody.add_argument("input", type=str)
    custody.add_argument("--output", default=None)

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

    gene_alias = subparsers.add_parser(
        "resolve-gene-alias",
        help="resolve gene identifiers, symbols, aliases, and declared versions",
    )
    gene_alias.add_argument("input", type=str)
    gene_alias.add_argument("--catalog", required=True)
    gene_alias.add_argument("--assembly", default=None)
    gene_alias.add_argument("--output", default=None)

    population_frequency = subparsers.add_parser(
        "adapt-population-frequency",
        help="adapt population-frequency rows with count derivation and source receipts",
    )
    population_frequency.add_argument("input", type=str)
    population_frequency.add_argument("--genome-build", default=None)
    population_frequency.add_argument("--variant-id", default=None)
    population_frequency.add_argument("--output", default=None)

    snapshot = subparsers.add_parser(
        "build-reference-snapshot",
        help="build a content-addressed reference resource manifest",
    )
    snapshot.add_argument("input", type=str)
    snapshot.add_argument("--snapshot-id", required=True)
    snapshot.add_argument("--assembly", required=True)
    snapshot.add_argument("--source-id", required=True)
    snapshot.add_argument("--source-version", default="unspecified")
    snapshot.add_argument("--expected-manifest-hash", default=None)
    snapshot.add_argument("--output", default=None)

    license_use = subparsers.add_parser(
        "evaluate-license-use",
        help="evaluate requested use against explicit resource license restrictions",
    )
    license_use.add_argument("input", type=str)
    license_use.add_argument("--restrictions", required=True)
    license_use.add_argument("--requested-use", required=True)
    license_use.add_argument("--redistribution", action="store_true")
    license_use.add_argument("--commercial", action="store_true")
    license_use.add_argument("--as-of", default=None)
    license_use.add_argument("--output", default=None)

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

    haplotype = subparsers.add_parser(
        "assemble-haplotype",
        help="assemble explicitly phased genotype records into retained haplotype paths",
    )
    haplotype.add_argument("input", type=str)
    haplotype.add_argument("--context-key", default=None)
    haplotype.add_argument("--max-haplotypes", type=int, default=8)
    haplotype.add_argument("--output", default=None)

    allele_sv = subparsers.add_parser(
        "represent-allele-aware-sv",
        help="represent structural events with explicit allele dosage and phase metadata",
    )
    allele_sv.add_argument("input", type=str)
    allele_sv.add_argument("--context-key", default=None)
    allele_sv.add_argument("--output", default=None)

    pangenome = subparsers.add_parser(
        "project-pangenome",
        help="project interval records onto supplied pangenome graph nodes and paths",
    )
    pangenome.add_argument("input", type=str)
    pangenome.add_argument("--nodes", required=True)
    pangenome.add_argument("--context-key", default=None)
    pangenome.add_argument("--max-candidates-per-query", type=int, default=32)
    pangenome.add_argument("--output", default=None)

    repeat_mobile = subparsers.add_parser(
        "annotate-repeat-mobile",
        help="annotate structural intervals with indexed repeat and mobile-element features",
    )
    repeat_mobile.add_argument("input", type=str)
    repeat_mobile.add_argument("--annotations", required=True)
    repeat_mobile.add_argument("--context-key", default=None)
    repeat_mobile.add_argument("--min-overlap-fraction", type=float, default=0.0)
    repeat_mobile.add_argument("--flank-bp", type=int, default=0)
    repeat_mobile.add_argument("--mobile-only", action="store_true")
    repeat_mobile.add_argument("--output", default=None)

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

    region_lineage = subparsers.add_parser(
        "resolve-multi-region-lineage",
        help="resolve declared multi-region specimen parent edges within each subject",
    )
    region_lineage.add_argument("input", type=str)
    region_lineage.add_argument("--context-key", default=None)
    region_lineage.add_argument("--output", default=None)

    longitudinal = subparsers.add_parser(
        "link-longitudinal-specimens",
        help="link same-subject specimens using declared or ordered temporal evidence",
    )
    longitudinal.add_argument("input", type=str)
    longitudinal.add_argument("--context-key", default=None)
    longitudinal.add_argument("--link-singleton", action="store_true")
    longitudinal.add_argument("--output", default=None)

    phase_map = subparsers.add_parser(
        "map-primary-recurrence",
        help="map explicit primary, recurrence, interval, and unknown specimen phases",
    )
    phase_map.add_argument("input", type=str)
    phase_map.add_argument("--context-key", default=None)
    phase_map.add_argument("--output", default=None)

    treatment_context = subparsers.add_parser(
        "contextualize-treatment",
        help="join specimens to same-subject treatment exposure intervals",
    )
    treatment_context.add_argument("input", type=str)
    treatment_context.add_argument("--exposures", required=True)
    treatment_context.add_argument("--context-key", default=None)
    treatment_context.add_argument("--output", default=None)

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

    chromatin_segments = subparsers.add_parser(
        "segment-chromatin-state",
        help="segment context-qualified chromatin observations at observed boundaries",
    )
    chromatin_segments.add_argument("input", type=str)
    chromatin_segments.add_argument("--context-key", default=None)
    chromatin_segments.add_argument("--low-signal", type=float, default=0.25)
    chromatin_segments.add_argument("--high-signal", type=float, default=0.75)
    chromatin_segments.add_argument("--output", default=None)

    allele_chromatin = subparsers.add_parser(
        "analyze-allele-specific-chromatin",
        help="compare reference and alternate chromatin signals by replicate",
    )
    allele_chromatin.add_argument("input", type=str)
    allele_chromatin.add_argument("--context-key", default=None)
    allele_chromatin.add_argument("--ambiguity-tolerance", type=float, default=0.25)
    allele_chromatin.add_argument("--delta-threshold", type=float, default=0.0)
    allele_chromatin.add_argument("--output", default=None)

    purity = subparsers.add_parser(
        "deconvolve-epigenomic-purity",
        help="estimate bounded purity from declared tumor and normal epigenomic references",
    )
    purity.add_argument("input", type=str)
    purity.add_argument("--context-key", default=None)
    purity.add_argument("--minimum-markers", type=int, default=2)
    purity.add_argument("--spread-tolerance", type=float, default=0.2)
    purity.add_argument("--output", default=None)

    batch_composition = subparsers.add_parser(
        "correct-batch-cell-composition",
        help="apply declared batch offsets and cell-composition corrections",
    )
    batch_composition.add_argument("input", type=str)
    batch_composition.add_argument("--context-key", default=None)
    batch_composition.add_argument("--output", default=None)

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

    open_chromatin = subparsers.add_parser(
        "harmonize-open-chromatin",
        help="harmonize context-qualified open-chromatin tracks into observed intervals",
    )
    open_chromatin.add_argument("input", type=str)
    open_chromatin.add_argument("--context-key", default=None)
    open_chromatin.add_argument("--spread-tolerance", type=float, default=0.25)
    open_chromatin.add_argument("--minimum-signal", type=float, default=0.0)
    open_chromatin.add_argument("--output", default=None)

    methylation_harmonizer = subparsers.add_parser(
        "harmonize-methylation",
        help="harmonize coverage-aware methylation tracks into observed intervals",
    )
    methylation_harmonizer.add_argument("input", type=str)
    methylation_harmonizer.add_argument("--context-key", default=None)
    methylation_harmonizer.add_argument("--spread-tolerance", type=float, default=0.25)
    methylation_harmonizer.add_argument("--output", default=None)

    regulatory_role = subparsers.add_parser(
        "classify-regulatory-role",
        help="classify enhancer, promoter, and silencer roles from declared channels",
    )
    regulatory_role.add_argument("input", type=str)
    regulatory_role.add_argument("--context-key", default=None)
    regulatory_role.add_argument("--role-threshold", type=float, default=0.5)
    regulatory_role.add_argument("--methylation-silencer-threshold", type=float, default=0.8)
    regulatory_role.add_argument("--output", default=None)

    super_enhancer = subparsers.add_parser(
        "build-super-enhancer-atlas",
        help="build ranked super-enhancer candidate intervals from enhancer records",
    )
    super_enhancer.add_argument("input", type=str)
    super_enhancer.add_argument("--context-key", default=None)
    super_enhancer.add_argument("--minimum-constituents", type=int, default=2)
    super_enhancer.add_argument("--merge-gap-bp", type=int, default=0)
    super_enhancer.add_argument("--rank-quantile", type=float, default=0.8)
    super_enhancer.add_argument("--output", default=None)

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

    nucleosome = subparsers.add_parser(
        "predict-nucleosome-propensity",
        help="calculate a transparent sequence-only nucleosome propensity index",
    )
    nucleosome.add_argument("input", type=str)
    nucleosome.add_argument("--context-key", default=None)
    nucleosome.add_argument("--minimum-length", type=int, default=147)
    nucleosome.add_argument("--periodicity-period", type=int, default=10)
    nucleosome.add_argument("--favored-threshold", type=float, default=0.65)
    nucleosome.add_argument("--depleted-threshold", type=float, default=0.35)
    nucleosome.add_argument("--output", default=None)

    splice_alpha = subparsers.add_parser(
        "scan-splice-regulatory",
        help="scan declared splice-regulatory motifs in noncoding sequence windows",
    )
    splice_alpha.add_argument("input", type=str)
    splice_alpha.add_argument("--context-key", default=None)
    splice_alpha.add_argument("--output", default=None)

    utr_alpha = subparsers.add_parser(
        "scan-utr-regulatory",
        help="scan declared 5-prime and 3-prime UTR regulatory elements",
    )
    utr_alpha.add_argument("input", type=str)
    utr_alpha.add_argument("--context-key", default=None)
    utr_alpha.add_argument("--minimum-uorf-codons", type=int, default=2)
    utr_alpha.add_argument("--output", default=None)

    promoter_alpha = subparsers.add_parser(
        "evaluate-promoter-grammar",
        help="evaluate declared core-promoter motif grammar and spacing coverage",
    )
    promoter_alpha.add_argument("input", type=str)
    promoter_alpha.add_argument("--context-key", default=None)
    promoter_alpha.add_argument("--minimum-coverage", type=float, default=0.5)
    promoter_alpha.add_argument("--output", default=None)

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

    prior_parse = subparsers.add_parser(
        "parse-context-prior",
        help="parse versioned lineage or malignant-state prior observations",
    )
    prior_parse.add_argument("input", type=str)
    prior_parse.add_argument("--source-id", default=None)
    prior_parse.add_argument("--source-version", default="unspecified")
    prior_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    prior_parse.add_argument("--output", default=None)

    developmental_prior = subparsers.add_parser(
        "estimate-developmental-lineage-prior",
        help="estimate a context-gated developmental-lineage research prior",
    )
    developmental_prior.add_argument("input", type=str)
    developmental_prior.add_argument("--context-key", required=True)
    developmental_prior.add_argument("--subject-id", default=None)
    developmental_prior.add_argument("--model-id", default="developmental-lineage-prior")
    developmental_prior.add_argument("--model-version", default="beta-1")
    developmental_prior.add_argument("--minimum-evidence", type=int, default=1)
    developmental_prior.add_argument("--ambiguity-margin", type=float, default=0.15)
    developmental_prior.add_argument("--output", default=None)

    gbm_prior = subparsers.add_parser(
        "estimate-glioblastoma-state-prior",
        help="estimate a glioblastoma malignant-state research prior",
    )
    gbm_prior.add_argument("input", type=str)
    gbm_prior.add_argument("--context-key", required=True)
    gbm_prior.add_argument("--subject-id", default=None)
    gbm_prior.add_argument("--model-id", default="glioblastoma-malignant-state-prior")
    gbm_prior.add_argument("--model-version", default="beta-1")
    gbm_prior.add_argument("--minimum-evidence", type=int, default=1)
    gbm_prior.add_argument("--ambiguity-margin", type=float, default=0.15)
    gbm_prior.add_argument("--output", default=None)

    idh_prior = subparsers.add_parser(
        "estimate-idh-lineage-prior",
        help="estimate an IDH-mutant lineage-state research prior",
    )
    idh_prior.add_argument("input", type=str)
    idh_prior.add_argument("--context-key", required=True)
    idh_prior.add_argument("--molecular-state", required=True)
    idh_prior.add_argument("--subject-id", default=None)
    idh_prior.add_argument("--model-id", default="idh-mutant-lineage-state-prior")
    idh_prior.add_argument("--model-version", default="beta-1")
    idh_prior.add_argument("--minimum-evidence", type=int, default=1)
    idh_prior.add_argument("--ambiguity-margin", type=float, default=0.15)
    idh_prior.add_argument("--output", default=None)

    h3_prior = subparsers.add_parser(
        "estimate-h3k27-developmental-prior",
        help="estimate an H3K27-altered developmental-state research prior",
    )
    h3_prior.add_argument("input", type=str)
    h3_prior.add_argument("--context-key", required=True)
    h3_prior.add_argument("--molecular-state", required=True)
    h3_prior.add_argument("--subject-id", default=None)
    h3_prior.add_argument("--model-id", default="h3k27-altered-developmental-state-prior")
    h3_prior.add_argument("--model-version", default="beta-1")
    h3_prior.add_argument("--minimum-evidence", type=int, default=1)
    h3_prior.add_argument("--ambiguity-margin", type=float, default=0.15)
    h3_prior.add_argument("--output", default=None)

    spatial_niche = subparsers.add_parser(
        "estimate-spatial-niche-prior",
        help="rank context-qualified spatial niche candidates",
    )
    spatial_niche.add_argument("input", type=str)
    spatial_niche.add_argument("--context-key", default=None)
    spatial_niche.add_argument("--ambiguity-margin", type=float, default=0.1)
    spatial_niche.add_argument("--output", default=None)

    core_margin = subparsers.add_parser(
        "estimate-core-margin-prior",
        help="estimate a core-versus-margin territory prior",
    )
    core_margin.add_argument("input", type=str)
    core_margin.add_argument("--context-key", default=None)
    core_margin.add_argument("--ambiguity-tolerance", type=float, default=0.1)
    core_margin.add_argument("--output", default=None)

    recurrence_prior = subparsers.add_parser(
        "estimate-recurrence-state-prior",
        help="rank declared primary and recurrence-state candidates",
    )
    recurrence_prior.add_argument("input", type=str)
    recurrence_prior.add_argument("--context-key", default=None)
    recurrence_prior.add_argument("--ambiguity-margin", type=float, default=0.1)
    recurrence_prior.add_argument("--output", default=None)

    treatment_prior = subparsers.add_parser(
        "estimate-treatment-induced-state-prior",
        help="compare baseline and post-treatment cell-state support",
    )
    treatment_prior.add_argument("input", type=str)
    treatment_prior.add_argument("--context-key", default=None)
    treatment_prior.add_argument("--induction-threshold", type=float, default=0.1)
    treatment_prior.add_argument("--output", default=None)

    loop_stripe = subparsers.add_parser(
        "parse-loop-stripe",
        help="parse versioned loop and stripe features with two-anchor provenance",
    )
    loop_stripe.add_argument("input", type=str)
    loop_stripe.add_argument("--source-id", default=None)
    loop_stripe.add_argument("--source-version", default="unspecified")
    loop_stripe.add_argument("--format", choices=("tsv", "json"), default=None)
    loop_stripe.add_argument("--coordinate-system", choices=("bed", "one_based"), default="bed")
    loop_stripe.add_argument("--output", default=None)

    promoter_capture = subparsers.add_parser(
        "parse-promoter-capture",
        help="parse promoter-capture bait-to-element contact records",
    )
    promoter_capture.add_argument("input", type=str)
    promoter_capture.add_argument("--source-id", default=None)
    promoter_capture.add_argument("--source-version", default="unspecified")
    promoter_capture.add_argument("--format", choices=("tsv", "json"), default=None)
    promoter_capture.add_argument(
        "--coordinate-system", choices=("bed", "one_based"), default="bed"
    )
    promoter_capture.add_argument("--output", default=None)

    contact_score = subparsers.add_parser(
        "score-enhancer-promoter-contact",
        help="score exact-context enhancer-promoter contact observations",
    )
    contact_score.add_argument("input", type=str)
    contact_score.add_argument("--enhancer-id", required=True)
    contact_score.add_argument("--promoter-id", required=True)
    contact_score.add_argument("--context-key", required=True)
    contact_score.add_argument("--signal-scale", type=float, default=10.0)
    contact_score.add_argument("--ambiguity-tolerance", type=float, default=0.50)
    contact_score.add_argument("--output", default=None)

    abc_score = subparsers.add_parser(
        "score-activity-by-contact",
        help="combine exact-context enhancer activity and contact components",
    )
    abc_score.add_argument("input", type=str)
    abc_score.add_argument("--enhancer-id", required=True)
    abc_score.add_argument("--promoter-id", required=True)
    abc_score.add_argument("--context-key", required=True)
    abc_score.add_argument("--model-id", required=True)
    abc_score.add_argument("--model-version", required=True)
    abc_score.add_argument("--contact-scale", type=float, default=10.0)
    abc_score.add_argument("--activity-scale", type=float, default=1.0)
    abc_score.add_argument("--ambiguity-tolerance", type=float, default=0.50)
    abc_score.add_argument("--output", default=None)

    boundary_motif = subparsers.add_parser(
        "analyze-boundary-motif-orientation",
        help="analyze left/right boundary motif orientations",
    )
    boundary_motif.add_argument("input", type=str)
    boundary_motif.add_argument("--context-key", default=None)
    boundary_motif.add_argument("--minimum-score", type=float, default=0.5)
    boundary_motif.add_argument("--output", default=None)

    ctcf_cohesin = subparsers.add_parser(
        "model-ctcf-cohesin-disruption",
        help="compare reference and alternate CTCF/cohesin evidence",
    )
    ctcf_cohesin.add_argument("input", type=str)
    ctcf_cohesin.add_argument("--context-key", default=None)
    ctcf_cohesin.add_argument("--disruption-threshold", type=float, default=0.2)
    ctcf_cohesin.add_argument("--output", default=None)

    idh_insulator = subparsers.add_parser(
        "model-idh-insulator-dysfunction",
        help="compare IDH-mutant and IDH-wildtype insulator evidence",
    )
    idh_insulator.add_argument("input", type=str)
    idh_insulator.add_argument("--context-key", default=None)
    idh_insulator.add_argument("--dysfunction-threshold", type=float, default=0.2)
    idh_insulator.add_argument("--output", default=None)

    sv_rewire = subparsers.add_parser(
        "simulate-sv-topology-rewiring",
        help="simulate declared SV contact-edge deletion and rewiring",
    )
    sv_rewire.add_argument("input", type=str)
    sv_rewire.add_argument("--context-key", default=None)
    sv_rewire.add_argument("--output", default=None)

    activity_contact_link = subparsers.add_parser(
        "parse-activity-contact-link",
        help="parse activity-by-contact variant-element-gene evidence rows",
    )
    activity_contact_link.add_argument("input", type=str)
    activity_contact_link.add_argument("--source-id", default=None)
    activity_contact_link.add_argument("--source-version", default="unspecified")
    activity_contact_link.add_argument("--format", choices=("tsv", "json"), default=None)
    activity_contact_link.add_argument("--contact-scale", type=float, default=10.0)
    activity_contact_link.add_argument("--output", default=None)

    coaccess_link = subparsers.add_parser(
        "link-coaccessibility",
        help="link exact-context coaccessibility evidence into candidate graph edges",
    )
    coaccess_link.add_argument("input", type=str)
    coaccess_link.add_argument("--context-key", required=True)
    coaccess_link.add_argument("--variant-id", default=None)
    coaccess_link.add_argument("--output", default=None)

    qtl_link = subparsers.add_parser(
        "link-molecular-qtl",
        help="link exact-context molecular-QTL evidence into candidate graph edges",
    )
    qtl_link.add_argument("input", type=str)
    qtl_link.add_argument("--context-key", required=True)
    qtl_link.add_argument("--variant-id", default=None)
    qtl_link.add_argument("--output", default=None)

    allele_link = subparsers.add_parser(
        "integrate-allele-specific-links",
        help="integrate allele-specific link paths while retaining direction conflict",
    )
    allele_link.add_argument("input", type=str)
    allele_link.add_argument("--context-key", required=True)
    allele_link.add_argument("--variant-id", default=None)
    allele_link.add_argument("--output", default=None)

    crispr_parse = subparsers.add_parser(
        "parse-crispr-perturbation-links",
        help="parse CRISPR perturbation variant-element-gene evidence rows",
    )
    crispr_parse.add_argument("input", type=str)
    crispr_parse.add_argument("--source-id", default=None)
    crispr_parse.add_argument("--source-version", default="unspecified")
    crispr_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    crispr_parse.add_argument("--effect-scale", type=float, default=1.0)
    crispr_parse.add_argument("--output", default=None)

    crispr_link = subparsers.add_parser(
        "link-crispr-perturbations",
        help="link exact-context CRISPR perturbation paths into candidate edges",
    )
    crispr_link.add_argument("input", type=str)
    crispr_link.add_argument("--context-key", required=True)
    crispr_link.add_argument("--variant-id", default=None)
    crispr_link.add_argument("--output", default=None)

    contact_parse = subparsers.add_parser(
        "parse-3d-contact-links",
        help="parse 3D contact variant-element-gene evidence rows",
    )
    contact_parse.add_argument("input", type=str)
    contact_parse.add_argument("--source-id", default=None)
    contact_parse.add_argument("--source-version", default="unspecified")
    contact_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    contact_parse.add_argument("--contact-scale", type=float, default=1.0)
    contact_parse.add_argument("--resolution-bp", type=int, default=5000)
    contact_parse.add_argument(
        "--assay-kind",
        choices=tuple(item.value for item in ContactAssayKind),
        default=ContactAssayKind.HIC.value,
    )
    contact_parse.add_argument("--output", default=None)

    contact_link = subparsers.add_parser(
        "link-3d-contacts",
        help="link exact-context 3D contact paths into candidate edges",
    )
    contact_link.add_argument("input", type=str)
    contact_link.add_argument("--context-key", required=True)
    contact_link.add_argument("--variant-id", default=None)
    contact_link.add_argument("--output", default=None)

    tether = subparsers.add_parser(
        "model-promoter-tethering",
        help="score a bounded promoter-tethering evidence baseline",
    )
    tether.add_argument("input", type=str)
    tether.add_argument("--context-key", default=None)
    tether.add_argument("--minimum-score", type=float, default=0.35)
    tether.add_argument("--maximum-distance-bp", type=int, default=None)
    tether.add_argument("--minimum-components", type=int, default=2)
    tether.add_argument("--output", default=None)

    graph = subparsers.add_parser(
        "build-multi-gene-element-graph",
        help="build a context-qualified multi-gene multi-element graph",
    )
    graph.add_argument("input", type=str)
    graph.add_argument("--context-key", required=True)
    graph.add_argument("--graph-id", default="multi-gene-element-graph")
    graph.add_argument("--variant-id", default=None)
    graph.add_argument("--minimum-support", type=float, default=0.0)
    graph.add_argument("--output", default=None)

    causal_parse = subparsers.add_parser(
        "parse-causal-evidence",
        help="parse causal mediator evidence with row-level quarantine",
    )
    causal_parse.add_argument("input", type=str)
    causal_parse.add_argument("--source-id", default=None)
    causal_parse.add_argument("--source-version", default="unspecified")
    causal_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    causal_parse.add_argument("--output", default=None)

    for command, help_text in (
        (
            "evaluate-sequence-element-mediator",
            "evaluate exact-context sequence-to-element mediator evidence",
        ),
        (
            "evaluate-element-gene-mediator",
            "evaluate exact-context element-to-gene mediator evidence",
        ),
        (
            "evaluate-gene-state-mediator",
            "evaluate exact-context gene-to-state mediator evidence",
        ),
    ):
        mediator = subparsers.add_parser(command, help=help_text)
        mediator.add_argument("input", type=str)
        mediator.add_argument("--source-node", required=True)
        mediator.add_argument("--target-node", required=True)
        mediator.add_argument("--context-key", required=True)
        mediator.add_argument("--model-id", required=True)
        mediator.add_argument("--model-version", required=True)
        mediator.add_argument("--minimum-sources", type=int, default=2)
        mediator.add_argument("--output", default=None)

    counterfactual = subparsers.add_parser(
        "simulate-counterfactual-allele-state",
        help="compare exact-context reference and alternate state observations",
    )
    counterfactual.add_argument("input", type=str)
    counterfactual.add_argument("--state-id", required=True)
    counterfactual.add_argument("--context-key", required=True)
    counterfactual.add_argument("--model-id", required=True)
    counterfactual.add_argument("--model-version", required=True)
    counterfactual.add_argument("--ambiguity-tolerance", type=float, default=0.20)
    counterfactual.add_argument("--output", default=None)

    sensitivity = subparsers.add_parser(
        "analyze-mediation-sensitivity",
        help="run leave-one-source-out sensitivity for a typed mediator edge",
    )
    sensitivity.add_argument("input", type=str)
    sensitivity.add_argument(
        "--mediator-kind",
        choices=tuple(item.value for item in MediatorKind),
        required=True,
    )
    sensitivity.add_argument("--source-node", required=True)
    sensitivity.add_argument("--target-node", required=True)
    sensitivity.add_argument("--context-key", required=True)
    sensitivity.add_argument("--model-id", required=True)
    sensitivity.add_argument("--model-version", required=True)
    sensitivity.add_argument("--minimum-sources", type=int, default=2)
    sensitivity.add_argument("--robustness-tolerance", type=float, default=0.20)
    sensitivity.add_argument("--output", default=None)

    confounding = subparsers.add_parser(
        "adjudicate-confounding",
        help="adjudicate declared confounder checklist observations",
    )
    confounding.add_argument("input", type=str)
    confounding.add_argument("--context-key", default=None)
    confounding.add_argument("--required-confounder", action="append", default=[])
    confounding.add_argument("--output", default=None)

    dependence = subparsers.add_parser(
        "correct-evidence-dependence",
        help="correct repeated evidence paths using declared dependence groups",
    )
    dependence.add_argument("input", type=str)
    dependence.add_argument("--context-key", required=True)
    dependence.add_argument("--edge-id", default=None)
    dependence.add_argument(
        "--correction-method",
        choices=tuple(item.value for item in DependenceMethod),
        default=DependenceMethod.DECLARED_GROUP.value,
    )
    dependence.add_argument("--minimum-independent-groups", type=int, default=2)
    dependence.add_argument("--output", default=None)

    negative = subparsers.add_parser(
        "integrate-negative-evidence",
        help="integrate positive paths and negative controls without erasing either",
    )
    negative.add_argument("input", type=str)
    negative.add_argument("--context-key", required=True)
    negative.add_argument("--edge-id", default=None)
    negative.add_argument("--minimum-negative-controls", type=int, default=1)
    negative.add_argument("--output", default=None)

    recurrence_parse = subparsers.add_parser(
        "parse-regulatory-recurrence",
        help="parse context-qualified recurrence observations with row quarantine",
    )
    recurrence_parse.add_argument("input", type=str)
    recurrence_parse.add_argument("--source-id", default=None)
    recurrence_parse.add_argument("--source-version", default="unspecified")
    recurrence_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    recurrence_parse.add_argument("--output", default=None)

    regional_parse = subparsers.add_parser(
        "parse-regional-burden",
        help="parse a regional burden JSON bundle with region and observation quarantine",
    )
    regional_parse.add_argument("input", type=str)
    regional_parse.add_argument("--source-id", default=None)
    regional_parse.add_argument("--source-version", default="unspecified")
    regional_parse.add_argument("--output", default=None)

    recurrence_test = subparsers.add_parser(
        "test-regulatory-recurrence",
        help="test exact-context regulatory recurrence and local hotspots",
    )
    recurrence_test.add_argument("input", type=str)
    recurrence_test.add_argument("--context-key", required=True)
    recurrence_test.add_argument("--target-region-id", default=None)
    recurrence_test.add_argument("--minimum-recurrent-samples", type=int, default=2)
    recurrence_test.add_argument("--hotspot-window-bp", type=int, default=50)
    recurrence_test.add_argument("--minimum-hotspot-variants", type=int, default=2)
    recurrence_test.add_argument("--minimum-hotspot-samples", type=int, default=2)
    recurrence_test.add_argument("--output", default=None)

    regional_test = subparsers.add_parser(
        "test-regional-burden",
        help="compare exact-context regional burden with callable-space background",
    )
    regional_test.add_argument("input", type=str)
    regional_test.add_argument("--region-id", required=True)
    regional_test.add_argument("--context-key", required=True)
    regional_test.add_argument("--background-rate", type=float, default=None)
    regional_test.add_argument("--output", default=None)

    functional_parse = subparsers.add_parser(
        "parse-functional-convergence",
        help="parse functional feature observations with row quarantine",
    )
    functional_parse.add_argument("input", type=str)
    functional_parse.add_argument("--source-id", default=None)
    functional_parse.add_argument("--source-version", default="unspecified")
    functional_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    functional_parse.add_argument("--output", default=None)

    functional_test = subparsers.add_parser(
        "test-functional-convergence",
        help="test exact-context functional feature convergence",
    )
    functional_test.add_argument("input", type=str)
    functional_test.add_argument("--context-key", required=True)
    functional_test.add_argument("--minimum-observed-variants", type=int, default=1)
    functional_test.add_argument("--ambiguity-margin", type=float, default=0.05)
    functional_test.add_argument("--output", default=None)

    pathway_parse = subparsers.add_parser(
        "parse-pathway-regulon",
        help="parse pathway or regulon membership observations",
    )
    pathway_parse.add_argument("input", type=str)
    pathway_parse.add_argument("--source-id", default=None)
    pathway_parse.add_argument("--source-version", default="unspecified")
    pathway_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    pathway_parse.add_argument("--output", default=None)

    pathway_test = subparsers.add_parser(
        "test-pathway-regulon-convergence",
        help="test exact-context pathway or regulon convergence",
    )
    pathway_test.add_argument("input", type=str)
    pathway_test.add_argument("--context-key", required=True)
    pathway_test.add_argument("--set-kind", choices=[item.value for item in SetKind], default=None)
    pathway_test.add_argument("--minimum-genes", type=int, default=2)
    pathway_test.add_argument("--ambiguity-margin", type=float, default=0.05)
    pathway_test.add_argument("--output", default=None)

    clonality = subparsers.add_parser(
        "integrate-clonality-timing",
        help="integrate exact-context CCF, specimen phase, and timing observations",
    )
    clonality.add_argument("input", type=str)
    clonality.add_argument("--context-key", required=True)
    clonality.add_argument("--clonal-threshold", type=float, default=0.85)
    clonality.add_argument("--subclonal-threshold", type=float, default=0.25)
    clonality.add_argument("--output", default=None)

    primary_recurrence = subparsers.add_parser(
        "compare-primary-recurrence",
        help="compare exact-context primary and recurrence frequencies",
    )
    primary_recurrence.add_argument("input", type=str)
    primary_recurrence.add_argument("--context-key", required=True)
    primary_recurrence.add_argument("--change-threshold", type=float, default=0.20)
    primary_recurrence.add_argument("--output", default=None)

    treatment_selection = subparsers.add_parser(
        "detect-treatment-selection",
        help="detect descriptive pre/post treatment frequency signals",
    )
    treatment_selection.add_argument("input", type=str)
    treatment_selection.add_argument("--context-key", required=True)
    treatment_selection.add_argument("--change-threshold", type=float, default=0.20)
    treatment_selection.add_argument("--output", default=None)

    replication = subparsers.add_parser(
        "replicate-cross-cohort",
        help="compare exact-context effects across pseudonymous cohorts",
    )
    replication.add_argument("input", type=str)
    replication.add_argument("--context-key", required=True)
    replication.add_argument("--minimum-cohorts", type=int, default=2)
    replication.add_argument("--minimum-concordance", type=float, default=0.75)
    replication.add_argument("--output", default=None)

    for command, help_text in (
        ("plan-crispri", "plan context-qualified CRISPRi guides"),
        ("plan-crispra", "plan context-qualified CRISPRa guides"),
        ("plan-base-editing", "plan context-qualified base-editing guides"),
        ("plan-prime-editing", "plan context-qualified prime-editing guides"),
        ("plan-allele-specific-reporter", "plan matched reference/alternate reporter constructs"),
    ):
        validation = subparsers.add_parser(command, help=help_text)
        validation.add_argument("input", type=str)
        validation.add_argument("--context-key", required=True)
        validation.add_argument("--design-id", default=None)
        validation.add_argument("--guide-length", type=int, default=None)
        validation.add_argument("--max-guides", type=int, default=None)
        validation.add_argument("--require-pam", action="store_true")
        validation.add_argument("--pam-pattern", default=None)
        validation.add_argument("--output", default=None)

    eligibility = subparsers.add_parser(
        "match-model-system-eligibility",
        help="match validation targets to declared model-system eligibility",
    )
    eligibility.add_argument("input", type=str)
    eligibility.add_argument("--context-key", required=True)
    eligibility.add_argument("--model-system", default=None)
    eligibility.add_argument("--minimum-evidence-strength", type=float, default=0.5)
    eligibility.add_argument("--output", default=None)

    oligo_parse = subparsers.add_parser(
        "parse-guide-oligo-design",
        help="adapt guide and oligo design rows with sequence receipts",
    )
    oligo_parse.add_argument("input", type=str)
    oligo_parse.add_argument("--source-id", default=None)
    oligo_parse.add_argument("--source-version", default="unspecified")
    oligo_parse.add_argument("--format", choices=("tsv", "json"), default=None)
    oligo_parse.add_argument("--output", default=None)

    controls = subparsers.add_parser(
        "plan-controls-randomization",
        help="plan deterministic controls and biological/technical replicates",
    )
    controls.add_argument("input", type=str)
    controls.add_argument("--context-key", required=True)
    controls.add_argument("--plan-id", default="validation-alpha-plan")
    controls.add_argument(
        "--control-type",
        action="append",
        choices=tuple(item.value for item in ControlType),
        default=None,
    )
    controls.add_argument("--biological-replicates", type=int, default=3)
    controls.add_argument("--technical-replicates", type=int, default=1)
    controls.add_argument("--randomization-seed", default="seed-1")
    controls.add_argument("--output", default=None)

    power = subparsers.add_parser(
        "estimate-power-replication",
        help="estimate transparent replicate requirements and planned power",
    )
    power.add_argument("input", type=str)
    power.add_argument("--context-key", required=True)
    power.add_argument("--output", default=None)

    for operation in (
        FRONTIER_OPERATIONS
        + CONTEXT_FRONTIER_OPERATIONS
        + INFERENCE_FRONTIER_OPERATIONS
        + RELEASE_FRONTIER_OPERATIONS
        + HARDENING_OPERATIONS
        + END_TO_END_OPERATIONS
    ):
        frontier = subparsers.add_parser(operation, help=f"run frontier capability: {operation}")
        frontier.add_argument("input", type=str)
        frontier.add_argument("--context-key", default=None)
        frontier.add_argument("--output", default=None)

    blinded_plan = subparsers.add_parser(
        "plan-blinded-adjudication",
        help="create masked exact-context evidence adjudication cases",
    )
    blinded_plan.add_argument("input", type=str)
    blinded_plan.add_argument("--context-key", required=True)
    blinded_plan.add_argument("--workflow-id", default="blinded-review")
    blinded_plan.add_argument("--reviewer-count", type=int, default=2)
    blinded_plan.add_argument("--required-decisions", type=int, default=None)
    blinded_plan.add_argument("--randomization-seed", default="seed-1")
    blinded_plan.add_argument("--output", default=None)

    blinded_adjudication = subparsers.add_parser(
        "adjudicate-blinded-evidence",
        help="reconcile masked reviewer decisions without unmasking sources",
    )
    blinded_adjudication.add_argument("input", type=str)
    blinded_adjudication.add_argument("--output", default=None)

    review_log = subparsers.add_parser(
        "record-review-log",
        help="record immutable reviewer comments and before/after changes",
    )
    review_log.add_argument("input", type=str)
    review_log.add_argument("--context-key", required=True)
    review_log.add_argument("--review-id", default="review-1")
    review_log.add_argument("--output", default=None)

    release_record = subparsers.add_parser(
        "record-release-decision",
        help="record research-only release gates and reviewer conditions",
    )
    release_record.add_argument("input", type=str)
    release_record.add_argument("--release-id", default="release-1")
    release_record.add_argument("--required-role", action="append", default=None)
    release_record.add_argument("--completed-role", action="append", default=None)
    release_record.add_argument("--reviewer-id", action="append", default=None)
    release_record.add_argument(
        "--requested-decision",
        choices=tuple(item.value for item in ReleaseDecision),
        default=None,
    )
    release_record.add_argument("--comment-log-address", default=None)
    release_record.add_argument("--output", default=None)

    delta = subparsers.add_parser(
        "detect-evidence-delta",
        help="compare two immutable evidence graph snapshots",
    )
    delta.add_argument("input", type=str)
    delta.add_argument("--expected-context-key", default=None)
    delta.add_argument("--output", default=None)

    board = subparsers.add_parser(
        "build-validation-board",
        help="build an exact-context validation experiment board",
    )
    board.add_argument("input", type=str)
    board.add_argument("--context-key", required=True)
    board.add_argument("--board-id", default="validation-board")
    board.add_argument("--output", default=None)

    launch = subparsers.add_parser(
        "plan-notebook-launch",
        help="plan a bounded notebook or SDK launch descriptor",
    )
    launch.add_argument("input", type=str)
    launch.add_argument("--context-key", required=True)
    launch.add_argument("--plan-id", default="notebook-launch-plan")
    launch.add_argument(
        "--allowed-runtime",
        action="append",
        choices=tuple(item.value for item in NotebookRuntime),
        default=None,
    )
    launch.add_argument("--output", default=None)

    share = subparsers.add_parser(
        "publish-shareable-snapshot",
        help="publish a research-only shareable HMAC snapshot",
    )
    share.add_argument("input", type=str)
    share.add_argument("--snapshot-id", required=True)
    share.add_argument("--snapshot-type", default="workspace")
    share.add_argument("--context-key", required=True)
    share.add_argument("--key-id", required=True)
    share.add_argument("--signing-secret", required=True)
    share.add_argument("--audience", action="append", default=None)
    share.add_argument("--expires-at", default=None)
    share.add_argument("--output", default=None)

    verify_share = subparsers.add_parser(
        "verify-shareable-snapshot",
        help="verify a shareable HMAC snapshot envelope",
    )
    verify_share.add_argument("input", type=str)
    verify_share.add_argument("--signing-secret", required=True)
    verify_share.add_argument("--now", default=None)
    verify_share.add_argument("--output", default=None)

    collaboration = subparsers.add_parser(
        "evaluate-collaboration-access",
        help="evaluate role-based research workspace access requests",
    )
    collaboration.add_argument("input", type=str)
    collaboration.add_argument("--workspace-id", default="workspace-1")
    collaboration.add_argument("--context-key", required=True)
    collaboration.add_argument("--output", default=None)

    ledger = subparsers.add_parser(
        "replay-execution-ledger",
        help="replay typed append-only execution events",
    )
    ledger.add_argument("input", type=str)
    ledger.add_argument("--execution-id", required=True)
    ledger.add_argument("--context-key", required=True)
    ledger.add_argument("--output", default=None)

    model_resolve = subparsers.add_parser(
        "resolve-model-registry",
        help="resolve a versioned model against context and contracts",
    )
    model_resolve.add_argument("input", type=str)
    model_resolve.add_argument("--model-id", required=True)
    model_resolve.add_argument("--version", default=None)
    model_resolve.add_argument("--context-key", required=True)
    model_resolve.add_argument("--input-contract", default=None)
    model_resolve.add_argument("--output-contract", default=None)
    model_resolve.add_argument("--output", default=None)

    data_resolve = subparsers.add_parser(
        "resolve-data-reference",
        help="resolve a versioned data/reference record",
    )
    data_resolve.add_argument("input", type=str)
    data_resolve.add_argument("--dataset-id", required=True)
    data_resolve.add_argument("--version", default=None)
    data_resolve.add_argument("--context-key", required=True)
    data_resolve.add_argument("--coordinate-system", default=None)
    data_resolve.add_argument("--license-id", default=None)
    data_resolve.add_argument("--output", default=None)

    drift = subparsers.add_parser(
        "monitor-drift",
        help="evaluate declared drift and out-of-domain monitor observations",
    )
    drift.add_argument("input", type=str)
    drift.add_argument("--monitor-id", required=True)
    drift.add_argument("--context-key", required=True)
    drift.add_argument("--output", default=None)

    tier_adjudication = subparsers.add_parser(
        "adjudicate-evidence-tier",
        help="adjudicate declared evidence tiers without erasing alternatives",
    )
    tier_adjudication.add_argument("input", type=str)
    tier_adjudication.add_argument("--context-key", required=True)
    tier_adjudication.add_argument("--output", default=None)

    lineage = subparsers.add_parser(
        "view-provenance-lineage",
        help="view claim, parent, supersession, source, and citation lineage",
    )
    lineage.add_argument("input", type=str)
    lineage.add_argument("--claim-id", default=None)
    lineage.add_argument("--active-only", action="store_true")
    lineage.add_argument("--output", default=None)

    uncertainty = subparsers.add_parser(
        "build-uncertainty-ledger",
        help="build a dimension-labeled uncertainty ledger",
    )
    uncertainty.add_argument("input", type=str)
    uncertainty.add_argument("--context-key", required=True)
    uncertainty.add_argument("--output", default=None)

    reviewer = subparsers.add_parser(
        "route-reviewers",
        help="route graph claims to explicit review roles",
    )
    reviewer.add_argument("input", type=str)
    reviewer.add_argument(
        "--roles",
        nargs="*",
        choices=[item.value for item in ReviewerRole],
        default=(),
    )
    reviewer.add_argument("--output", default=None)

    topology_view = subparsers.add_parser(
        "view-topology",
        help="build a bounded exact-context 3D topology viewport",
    )
    topology_view.add_argument("input", type=str)
    topology_view.add_argument("--context-key", required=True)
    topology_view.add_argument("--focus-chromosome", default=None)
    topology_view.add_argument("--focus-start", type=int, default=None)
    topology_view.add_argument("--focus-end", type=int, default=None)
    topology_view.add_argument("--max-nodes", type=int, default=500)
    topology_view.add_argument("--max-edges", type=int, default=1000)
    topology_view.add_argument("--output", default=None)

    causal_chain = subparsers.add_parser(
        "explore-causal-chain",
        help="join exact-context sequence-to-state mediator results",
    )
    causal_chain.add_argument("input", type=str)
    causal_chain.add_argument("--context-key", required=True)
    causal_chain.add_argument("--chain-id", default=None)
    causal_chain.add_argument("--output", default=None)

    posterior_view = subparsers.add_parser(
        "view-posterior-decomposition",
        help="render declared-prior posterior support components and residual",
    )
    posterior_view.add_argument("input", type=str)
    posterior_view.add_argument("--context-key", required=True)
    posterior_view.add_argument("--residual-tolerance", type=float, default=0.05)
    posterior_view.add_argument("--output", default=None)

    evidence_table = subparsers.add_parser(
        "filter-evidence-table",
        help="filter a serialized workspace evidence table with deterministic facets",
    )
    evidence_table.add_argument("input", type=str)
    evidence_table.add_argument("--context-key", default=None)
    evidence_table.add_argument("--text", default="")
    evidence_table.add_argument("--channel", nargs="*", default=())
    evidence_table.add_argument("--tier", nargs="*", default=())
    evidence_table.add_argument(
        "--state",
        nargs="*",
        choices=[item.value for item in WorkspaceState],
        default=(),
    )
    evidence_table.add_argument("--source-id", nargs="*", default=())
    evidence_table.add_argument("--min-confidence", type=float, default=None)
    evidence_table.add_argument("--offset", type=int, default=0)
    evidence_table.add_argument("--limit", type=int, default=50)
    evidence_table.add_argument("--output", default=None)

    policy_audit = subparsers.add_parser(
        "audit-policy-claim",
        help="audit one invocation against claim, source, scope, and privacy policy",
    )
    policy_audit.add_argument("input", type=str)
    policy_audit.add_argument("--output", default=None)

    budget_schedule = subparsers.add_parser(
        "schedule-budget",
        help="plan dependency-aware work against declared budgets",
    )
    budget_schedule.add_argument("input", type=str)
    budget_schedule.add_argument("--max-invocations", type=int, default=128)
    budget_schedule.add_argument("--max-network-requests", type=int, default=32)
    budget_schedule.add_argument("--max-seconds", type=int, default=3600)
    budget_schedule.add_argument("--max-cost-units", type=float, default=1000.0)
    budget_schedule.add_argument("--cpu", type=float, default=8.0)
    budget_schedule.add_argument("--memory-gb", type=float, default=32.0)
    budget_schedule.add_argument("--gpu-count", type=int, default=0)
    budget_schedule.add_argument("--storage-gb", type=float, default=100.0)
    budget_schedule.add_argument("--network-egress", action="store_true")
    budget_schedule.add_argument("--schedule-id", default="budget-schedule-cli")
    budget_schedule.add_argument("--output", default=None)

    fallback_route = subparsers.add_parser(
        "route-fallback",
        help="choose a declared deterministic alternate after a retryable failure",
    )
    fallback_route.add_argument("input", type=str)
    fallback_route.add_argument("--output", default=None)

    review_queue = subparsers.add_parser(
        "queue-human-review",
        help="route declared outcomes into a bounded human-review queue",
    )
    review_queue.add_argument("input", type=str)
    review_queue.add_argument("--roles", nargs="*", default=())
    review_queue.add_argument("--max-review-candidates", type=int, default=100)
    review_queue.add_argument("--queue-id", default="human-review-queue-cli")
    review_queue.add_argument("--output", default=None)

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
        if args.command == "resolve-variant-equivalence":
            payload = _read_json(args.input)
            records = payload.get("records", payload.get("variants", ()))
            result = VariantEquivalenceResolver().resolve(
                records,
                args.query,
                genome_build=args.genome_build,
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "reconcile-variant-aliases":
            payload = _read_json(args.input)
            result = DuplicateAliasReconciler().reconcile(
                payload.get("records", payload.get("variants", ()))
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "check-batch-sample-identity":
            payload = _read_json(args.input)
            result = BatchSampleIdentityChecker().check(
                payload.get("observations", payload.get("records", ())),
                require_batch=not args.allow_missing_batch,
                require_sample=not args.allow_missing_sample,
                require_subject=args.require_subject,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "capture-chain-of-custody":
            payload = _read_json(args.input)
            result = ChainOfCustodyCapture().capture(
                payload.get("events", payload.get("records", ()))
            )
            _write_json(result.to_dict(), args.output)
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
        if args.command == "resolve-gene-alias":
            catalog = _read_rows(args.catalog, "records", "genes", "catalog")
            queries = _read_rows(args.input, "queries", "records")
            result = GeneAliasVersionResolver().resolve(
                queries,
                catalog,
                assembly=args.assembly,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "adapt-population-frequency":
            result = PopulationFrequencyAdapter().adapt(
                _read_rows(args.input, "records", "frequencies", "observations"),
                genome_build=args.genome_build,
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "build-reference-snapshot":
            result = ReferenceSnapshotManager().build(
                _read_rows(args.input, "resources", "records"),
                snapshot_id=args.snapshot_id,
                assembly=args.assembly,
                source_id=args.source_id,
                source_version=args.source_version,
                expected_manifest_hash=args.expected_manifest_hash,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evaluate-license-use":
            result = LicenseUseRestrictionRegistry().evaluate(
                _read_rows(args.input, "resources", "records"),
                _read_rows(args.restrictions, "restrictions", "records"),
                requested_use=args.requested_use,
                redistribution=args.redistribution,
                commercial=args.commercial,
                as_of=args.as_of,
            )
            _write_json(result.to_dict(), args.output)
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
        if args.command == "assemble-haplotype":
            result = PhasedHaplotypeAssembler().assemble(
                _read_rows(args.input, "records", "observations", "variants"),
                context_key=args.context_key,
                max_haplotypes=args.max_haplotypes,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "represent-allele-aware-sv":
            result = AlleleAwareSvRepresenter().represent(
                _read_rows(args.input, "records", "observations", "events"),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "project-pangenome":
            result = PangenomeGraphProjector().project(
                _read_rows(args.input, "records", "queries", "variants", "events"),
                _read_rows(args.nodes, "nodes", "records"),
                context_key=args.context_key,
                max_candidates_per_query=args.max_candidates_per_query,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "annotate-repeat-mobile":
            result = RepeatMobileElementAnnotator().annotate(
                _read_rows(args.input, "records", "queries", "variants", "events"),
                _read_rows(args.annotations, "annotations", "records", "features"),
                context_key=args.context_key,
                min_overlap_fraction=args.min_overlap_fraction,
                flank_bp=args.flank_bp,
                include_non_mobile=not args.mobile_only,
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
        if args.command == "resolve-multi-region-lineage":
            result = MultiRegionLineageResolver().resolve(
                _read_rows(args.input, "records", "regions", "observations"),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "link-longitudinal-specimens":
            result = LongitudinalSpecimenLinker().link(
                _read_rows(args.input, "records", "specimens", "observations"),
                context_key=args.context_key,
                link_singleton=args.link_singleton,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "map-primary-recurrence":
            result = PrimaryRecurrencePhaseMapper().map(
                _read_rows(args.input, "records", "specimens", "observations"),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "contextualize-treatment":
            result = TreatmentExposureContextualizer().contextualize(
                _read_rows(args.input, "records", "specimens", "observations"),
                _read_rows(args.exposures, "exposures", "records"),
                context_key=args.context_key,
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
        if args.command == "segment-chromatin-state":
            result = ChromatinStateSegmentationAdapter().segment(
                _read_rows(args.input, "records", "observations", "segments"),
                context_key=args.context_key,
                low_signal=args.low_signal,
                high_signal=args.high_signal,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "analyze-allele-specific-chromatin":
            result = AlleleSpecificChromatinAnalyzer().analyze(
                _read_rows(args.input, "records", "observations", "measurements"),
                context_key=args.context_key,
                ambiguity_tolerance=args.ambiguity_tolerance,
                delta_threshold=args.delta_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "deconvolve-epigenomic-purity":
            result = EpigenomicPurityDeconvolver().estimate(
                _read_rows(args.input, "records", "markers", "observations"),
                context_key=args.context_key,
                minimum_markers=args.minimum_markers,
                spread_tolerance=args.spread_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "correct-batch-cell-composition":
            payload = _read_json(args.input)
            result = BatchCellCompositionCorrector().correct(
                payload.get("records", payload.get("observations", ())),
                context_key=args.context_key or payload.get("context_key"),
                batch_offsets=payload.get("batch_offsets"),
                target_composition=payload.get("target_composition"),
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
        if args.command == "harmonize-open-chromatin":
            result = OpenChromatinTrackHarmonizer().harmonize(
                _read_rows(args.input, "records", "observations", "intervals", "elements"),
                context_key=args.context_key,
                spread_tolerance=args.spread_tolerance,
                minimum_signal=args.minimum_signal,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "harmonize-methylation":
            result = MethylationTrackHarmonizer().harmonize(
                _read_rows(args.input, "records", "observations", "intervals"),
                context_key=args.context_key,
                spread_tolerance=args.spread_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "classify-regulatory-role":
            result = EnhancerPromoterSilencerClassifier().classify(
                _read_rows(args.input, "records", "observations", "elements"),
                context_key=args.context_key,
                role_threshold=args.role_threshold,
                methylation_silencer_threshold=args.methylation_silencer_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "build-super-enhancer-atlas":
            result = SuperEnhancerCandidateAtlas().build(
                _read_rows(args.input, "records", "observations", "intervals", "elements"),
                context_key=args.context_key,
                minimum_constituents=args.minimum_constituents,
                merge_gap_bp=args.merge_gap_bp,
                rank_quantile=args.rank_quantile,
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
        if args.command == "parse-context-prior":
            input_path = Path(args.input)
            result = ContextPriorObservationParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in {
            "estimate-developmental-lineage-prior",
            "estimate-glioblastoma-state-prior",
            "estimate-idh-lineage-prior",
            "estimate-h3k27-developmental-prior",
        }:
            payload = _read_json(args.input)
            context = _context_from_key(args.context_key)
            observations = payload.get("observations", payload.get("records", ()))
            subject_id = args.subject_id or str(payload.get("subject_id", "unspecified"))
            common = {
                "subject_id": subject_id,
                "model_id": args.model_id,
                "model_version": args.model_version,
                "minimum_evidence": args.minimum_evidence,
                "ambiguity_margin": args.ambiguity_margin,
            }
            if args.command == "estimate-developmental-lineage-prior":
                result = DevelopmentalLineagePrior().estimate(context, observations, **common)
            elif args.command == "estimate-glioblastoma-state-prior":
                result = GlioblastomaMalignantStatePrior().estimate(context, observations, **common)
            elif args.command == "estimate-idh-lineage-prior":
                result = IdhMutantLineageStatePrior().estimate(
                    context,
                    observations,
                    declared_molecular_state=args.molecular_state,
                    **common,
                )
            else:
                result = H3K27AlteredDevelopmentalStatePrior().estimate(
                    context,
                    observations,
                    declared_molecular_state=args.molecular_state,
                    **common,
                )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-spatial-niche-prior":
            result = SpatialNichePrior().estimate(
                _read_rows(args.input, "records", "observations", "niches"),
                context_key=args.context_key,
                ambiguity_margin=args.ambiguity_margin,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-core-margin-prior":
            result = CoreMarginTerritoryPrior().estimate(
                _read_rows(args.input, "records", "observations", "territories"),
                context_key=args.context_key,
                ambiguity_tolerance=args.ambiguity_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-recurrence-state-prior":
            result = RecurrenceStatePrior().estimate(
                _read_rows(args.input, "records", "observations", "states"),
                context_key=args.context_key,
                ambiguity_margin=args.ambiguity_margin,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-treatment-induced-state-prior":
            result = TreatmentInducedStatePrior().estimate(
                _read_rows(args.input, "records", "observations", "states"),
                context_key=args.context_key,
                induction_threshold=args.induction_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-loop-stripe":
            input_path = Path(args.input)
            result = LoopStripeAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                coordinate_system=args.coordinate_system,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-promoter-capture":
            input_path = Path(args.input)
            result = PromoterCaptureContactAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                coordinate_system=args.coordinate_system,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "score-enhancer-promoter-contact":
            payload = _read_json(args.input)
            result = EnhancerPromoterContactScorer().score(
                payload.get("observations", payload.get("contacts", ())),
                enhancer_id=args.enhancer_id,
                promoter_id=args.promoter_id,
                context_key=args.context_key,
                signal_scale=args.signal_scale,
                ambiguity_tolerance=args.ambiguity_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "score-activity-by-contact":
            payload = _read_json(args.input)
            result = ActivityByContactScorer().score(
                payload.get("contacts", payload.get("contact_observations", ())),
                payload.get("activities", payload.get("activity_observations", ())),
                enhancer_id=args.enhancer_id,
                promoter_id=args.promoter_id,
                context_key=args.context_key,
                model_id=args.model_id,
                model_version=args.model_version,
                contact_scale=args.contact_scale,
                activity_scale=args.activity_scale,
                ambiguity_tolerance=args.ambiguity_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "analyze-boundary-motif-orientation":
            result = BoundaryMotifOrientationAnalyzer().analyze(
                _read_rows(args.input, "records", "observations", "motifs"),
                context_key=args.context_key,
                minimum_score=args.minimum_score,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "model-ctcf-cohesin-disruption":
            result = CTCFCohesinDisruptionModel().analyze(
                _read_rows(args.input, "records", "observations", "measurements"),
                context_key=args.context_key,
                disruption_threshold=args.disruption_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "model-idh-insulator-dysfunction":
            result = IDHInsulatorDysfunctionModel().assess(
                _read_rows(args.input, "records", "observations", "insulators"),
                context_key=args.context_key,
                dysfunction_threshold=args.dysfunction_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "simulate-sv-topology-rewiring":
            payload = _read_json(args.input)
            result = SVTopologyRewiringSimulator().simulate(
                payload.get("contacts", payload.get("edges", ())),
                payload.get("events", payload.get("structural_variants", ())),
                context_key=args.context_key or payload.get("context_key"),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-activity-contact-link":
            input_path = Path(args.input)
            result = ActivityByContactLinkAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                contact_scale=args.contact_scale,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "link-coaccessibility":
            payload = _read_json(args.input)
            result = CoaccessibilityLinker().link(
                payload.get("observations", payload.get("evidence", payload.get("records", ()))),
                _context_from_key(args.context_key),
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "link-molecular-qtl":
            payload = _read_json(args.input)
            result = MolecularQtlLinker().link(
                payload.get("observations", payload.get("evidence", payload.get("records", ()))),
                _context_from_key(args.context_key),
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "integrate-allele-specific-links":
            payload = _read_json(args.input)
            result = AlleleSpecificLinkEvidenceIntegrator().integrate(
                payload.get("observations", payload.get("evidence", payload.get("records", ()))),
                _context_from_key(args.context_key),
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-crispr-perturbation-links":
            input_path = Path(args.input)
            result = CRISPRPerturbationLinkAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                effect_scale=args.effect_scale,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "link-crispr-perturbations":
            payload = _read_json(args.input)
            result = CRISPRPerturbationLinker().link(
                payload.get("observations", payload.get("evidence", payload.get("records", ()))),
                _context_from_key(args.context_key),
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-3d-contact-links":
            input_path = Path(args.input)
            result = ThreeDContactLinkAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
                contact_scale=args.contact_scale,
                resolution_bp=args.resolution_bp,
                assay_kind=ContactAssayKind(args.assay_kind),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "link-3d-contacts":
            payload = _read_json(args.input)
            result = ThreeDContactLinker().link(
                payload.get("observations", payload.get("evidence", payload.get("records", ()))),
                _context_from_key(args.context_key),
                variant_id=args.variant_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "model-promoter-tethering":
            result = PromoterTetheringModel().assess(
                _read_rows(args.input, "observations", "records", "tethering"),
                context_key=args.context_key,
                minimum_score=args.minimum_score,
                maximum_distance_bp=args.maximum_distance_bp,
                minimum_components=args.minimum_components,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "build-multi-gene-element-graph":
            payload = _read_json(args.input)
            result = MultiGeneElementGraphBuilder().build(
                payload.get("evidence", payload.get("observations", payload.get("records", ()))),
                _context_from_key(args.context_key),
                graph_id=args.graph_id,
                variant_id=args.variant_id,
                minimum_support=args.minimum_support,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-causal-evidence":
            input_path = Path(args.input)
            result = CausalMediatorEvidenceParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in {
            "evaluate-sequence-element-mediator",
            "evaluate-element-gene-mediator",
            "evaluate-gene-state-mediator",
        }:
            payload = _read_json(args.input)
            evidence = payload.get("evidence", payload.get("records", ()))
            mediator = {
                "evaluate-sequence-element-mediator": SequenceToElementCausalMediator,
                "evaluate-element-gene-mediator": ElementToGeneCausalMediator,
                "evaluate-gene-state-mediator": GeneToStateCausalMediator,
            }[args.command]()
            result = mediator.evaluate(
                evidence,
                source_node=args.source_node,
                target_node=args.target_node,
                context_key=args.context_key,
                model_id=args.model_id,
                model_version=args.model_version,
                minimum_sources=args.minimum_sources,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "simulate-counterfactual-allele-state":
            payload = _read_json(args.input)
            result = CounterfactualAlleleStateSimulator().simulate(
                payload.get("observations", payload.get("records", ())),
                state_id=args.state_id,
                context_key=args.context_key,
                model_id=args.model_id,
                model_version=args.model_version,
                ambiguity_tolerance=args.ambiguity_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "analyze-mediation-sensitivity":
            payload = _read_json(args.input)
            result = MediationSensitivityAnalyzer().analyze(
                payload.get("evidence", payload.get("records", ())),
                mediator_kind=MediatorKind(args.mediator_kind),
                source_node=args.source_node,
                target_node=args.target_node,
                context_key=args.context_key,
                model_id=args.model_id,
                model_version=args.model_version,
                minimum_sources=args.minimum_sources,
                robustness_tolerance=args.robustness_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "adjudicate-confounding":
            result = ConfoundingChecklistAdjudicator().assess(
                _read_rows(args.input, "observations", "records", "confounders"),
                context_key=args.context_key,
                required_confounder_ids=args.required_confounder,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "correct-evidence-dependence":
            result = EvidenceDependenceCorrector().correct(
                _read_rows(args.input, "observations", "evidence", "records"),
                context_key=args.context_key,
                edge_id=args.edge_id,
                correction_method=DependenceMethod(args.correction_method),
                minimum_independent_groups=args.minimum_independent_groups,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "integrate-negative-evidence":
            result = NegativeEvidenceIntegrator().integrate(
                _read_rows(args.input, "observations", "evidence", "records"),
                context_key=args.context_key,
                edge_id=args.edge_id,
                minimum_negative_controls=args.minimum_negative_controls,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-regulatory-recurrence":
            input_path = Path(args.input)
            result = RegulatoryRecurrenceParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-regional-burden":
            input_path = Path(args.input)
            result = RegionalBurdenParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "test-regulatory-recurrence":
            payload = _read_json(args.input)
            result = RegulatoryRecurrenceTester().test(
                payload.get("records", payload.get("observations", ())),
                context_key=args.context_key,
                target_region_id=args.target_region_id,
                minimum_recurrent_samples=args.minimum_recurrent_samples,
                hotspot_window_bp=args.hotspot_window_bp,
                minimum_hotspot_variants=args.minimum_hotspot_variants,
                minimum_hotspot_samples=args.minimum_hotspot_samples,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "test-regional-burden":
            payload = _read_json(args.input)
            result = RegionalBurdenTester().test(
                payload.get("regions", ()),
                payload.get("observations", payload.get("records", ())),
                region_id=args.region_id,
                context_key=args.context_key,
                background_rate=args.background_rate,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-functional-convergence":
            input_path = Path(args.input)
            result = FunctionalConvergenceParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "test-functional-convergence":
            payload = _read_json(args.input)
            result = FunctionalConvergenceTester().test(
                payload.get("observations", payload.get("records", ())),
                context_key=args.context_key,
                minimum_observed_variants=args.minimum_observed_variants,
                ambiguity_margin=args.ambiguity_margin,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-pathway-regulon":
            input_path = Path(args.input)
            result = PathwayRegulonParser().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "test-pathway-regulon-convergence":
            payload = _read_json(args.input)
            result = PathwayRegulonConvergenceTester().test(
                payload.get("observations", payload.get("records", ())),
                context_key=args.context_key,
                set_kind=args.set_kind,
                minimum_genes=args.minimum_genes,
                ambiguity_margin=args.ambiguity_margin,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "integrate-clonality-timing":
            result = ClonalityTimingIntegrator().integrate(
                _read_rows(args.input, "observations", "records", "clonality"),
                context_key=args.context_key,
                clonal_threshold=args.clonal_threshold,
                subclonal_threshold=args.subclonal_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "compare-primary-recurrence":
            result = PrimaryRecurrenceComparator().compare(
                _read_rows(args.input, "observations", "records", "phases"),
                context_key=args.context_key,
                change_threshold=args.change_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "detect-treatment-selection":
            result = TreatmentSelectionSignalDetector().detect(
                _read_rows(args.input, "observations", "records", "selection"),
                context_key=args.context_key,
                change_threshold=args.change_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "replicate-cross-cohort":
            result = CrossCohortReplicationEngine().replicate(
                _read_rows(args.input, "observations", "records", "replication"),
                context_key=args.context_key,
                minimum_cohorts=args.minimum_cohorts,
                minimum_concordance=args.minimum_concordance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in {
            "plan-crispri",
            "plan-crispra",
            "plan-base-editing",
            "plan-prime-editing",
            "plan-allele-specific-reporter",
        }:
            payload = _read_json(args.input)
            mode = {
                "plan-crispri": PerturbationMode.CRISPRI,
                "plan-crispra": PerturbationMode.CRISPRA,
                "plan-base-editing": PerturbationMode.BASE_EDITING,
                "plan-prime-editing": PerturbationMode.PRIME_EDITING,
                "plan-allele-specific-reporter": PerturbationMode.ALLELE_SPECIFIC_REPORTER,
            }[args.command]
            constraints = _guide_constraints(
                payload,
                mode=mode,
                context_key=args.context_key,
                design_id=args.design_id,
                guide_length=args.guide_length,
                max_guides=args.max_guides,
                require_pam=args.require_pam,
                pam_pattern=args.pam_pattern,
            )
            targets = _validation_beta_targets(payload.get("targets", ()))
            if mode == PerturbationMode.CRISPRI:
                result = CRISPRiDesignPlanner().plan(targets, constraints)
            elif mode == PerturbationMode.CRISPRA:
                result = CRISPRaDesignPlanner().plan(targets, constraints)
            elif mode == PerturbationMode.BASE_EDITING:
                result = BaseEditingDesignPlanner().plan(targets, constraints)
            elif mode == PerturbationMode.PRIME_EDITING:
                result = PrimeEditingDesignPlanner().plan(targets, constraints)
            else:
                result = AlleleSpecificReporterPlanner().plan(targets, constraints)
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "match-model-system-eligibility":
            result = ModelSystemEligibilityMatcher().match(
                _read_rows(args.input, "observations", "records", "eligibility"),
                context_key=args.context_key,
                model_system=args.model_system,
                minimum_evidence_strength=args.minimum_evidence_strength,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "parse-guide-oligo-design":
            input_path = Path(args.input)
            result = GuideOligoDesignAdapter().parse_text(
                input_path.read_text(encoding="utf-8"),
                source_id=args.source_id or input_path.stem,
                source_version=args.source_version,
                input_format=args.format,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "plan-controls-randomization":
            payload = _read_json(args.input)
            control_types = (
                tuple(ControlType(item) for item in args.control_type)
                if args.control_type
                else (ControlType.NEGATIVE, ControlType.NON_TARGETING)
            )
            result = ControlsRandomizationPlanner().plan(
                payload.get("targets", payload.get("records", payload.get("observations", ()))),
                context_key=args.context_key,
                plan_id=args.plan_id,
                control_types=control_types,
                biological_replicates=args.biological_replicates,
                technical_replicates=args.technical_replicates,
                randomization_seed=args.randomization_seed,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "estimate-power-replication":
            result = PowerReplicationEstimator().estimate(
                _read_rows(args.input, "observations", "records", "power"),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in FRONTIER_OPERATIONS:
            result = run_frontier_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in CONTEXT_FRONTIER_OPERATIONS:
            result = run_context_frontier_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in INFERENCE_FRONTIER_OPERATIONS:
            result = run_inference_frontier_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in RELEASE_FRONTIER_OPERATIONS:
            result = run_release_frontier_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in HARDENING_OPERATIONS:
            result = run_hardening_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command in END_TO_END_OPERATIONS:
            result = run_end_to_end_operation(
                args.command,
                _read_json(args.input),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "plan-blinded-adjudication":
            result = BlindedAdjudicationWorkflow().plan(
                _read_rows(args.input, "observations", "records", "evidence"),
                workflow_id=args.workflow_id,
                context_key=args.context_key,
                reviewer_count=args.reviewer_count,
                required_decisions=args.required_decisions,
                randomization_seed=args.randomization_seed,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "adjudicate-blinded-evidence":
            payload = _read_json(args.input)
            plan = BlindedAdjudicationPlan.from_mapping(payload.get("plan", payload))
            result = BlindedAdjudicationWorkflow().adjudicate(
                plan,
                payload.get("decisions", payload.get("observations", ())),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "record-review-log":
            payload = _read_json(args.input)
            result = ReviewerCommentChangeLogger().record(
                payload.get("comments", ()),
                payload.get("changes", ()),
                review_id=args.review_id,
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "record-release-decision":
            payload = _read_json(args.input)
            result = ReleaseDecisionRecorder().record(
                payload.get("graph", payload),
                payload.get("gates", payload.get("observations", ())),
                release_id=args.release_id,
                required_roles=args.required_role or (),
                completed_roles=args.completed_role or (),
                reviewer_ids=args.reviewer_id or (),
                comment_log_address=args.comment_log_address,
                requested_decision=args.requested_decision,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "detect-evidence-delta":
            payload = _read_json(args.input)
            result = EvidenceDeltaDetector().compare(
                payload.get("previous", {}),
                payload.get("current", {}),
                expected_context_key=args.expected_context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "build-validation-board":
            result = ValidationExperimentBoardBuilder().build(
                _read_rows(args.input, "experiments", "cards", "records"),
                context_key=args.context_key,
                board_id=args.board_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "plan-notebook-launch":
            result = NotebookSDKLauncher().plan(
                _read_rows(args.input, "requests", "launches", "records"),
                context_key=args.context_key,
                plan_id=args.plan_id,
                allowed_runtimes=(
                    tuple(NotebookRuntime(item) for item in args.allowed_runtime)
                    if args.allowed_runtime
                    else tuple(NotebookRuntime)
                ),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "publish-shareable-snapshot":
            payload = _read_json(args.input)
            snapshot_payload = payload.get("payload", payload)
            result = ShareableSnapshotPublisher().publish(
                snapshot_payload,
                snapshot_id=args.snapshot_id,
                snapshot_type=args.snapshot_type,
                context_key=args.context_key,
                key_id=args.key_id,
                signing_secret=args.signing_secret,
                audience=args.audience or (),
                expires_at=args.expires_at,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "verify-shareable-snapshot":
            result = ShareableSnapshotPublisher().verify(
                _read_json(args.input),
                signing_secret=args.signing_secret,
                now=args.now,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evaluate-collaboration-access":
            payload = _read_json(args.input)
            result = RoleBasedCollaborationEvaluator().evaluate(
                payload.get("members", payload.get("roster", ())),
                payload.get("requests", payload.get("access_requests", ())),
                workspace_id=args.workspace_id,
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "replay-execution-ledger":
            result = EventSourcedExecutionLedger().replay(
                _read_rows(args.input, "events", "records"),
                execution_id=args.execution_id,
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "resolve-model-registry":
            payload = _read_json(args.input)
            result = ModelRegistry.from_mappings(
                payload.get("records", payload.get("models", ()))
            ).snapshot.resolve(
                args.model_id,
                context_key=args.context_key,
                version=args.version,
                input_contract=args.input_contract,
                output_contract=args.output_contract,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "resolve-data-reference":
            payload = _read_json(args.input)
            result = DataReferenceRegistry.from_mappings(
                payload.get("records", payload.get("references", ()))
            ).snapshot.resolve(
                args.dataset_id,
                context_key=args.context_key,
                version=args.version,
                coordinate_system=args.coordinate_system,
                license_id=args.license_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "monitor-drift":
            result = DriftAndOODMonitor().evaluate(
                _read_rows(args.input, "observations", "records", "drift"),
                monitor_id=args.monitor_id,
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "adjudicate-evidence-tier":
            payload = _read_json(args.input)
            result = EvidenceTierAdjudicator().adjudicate(
                payload.get("observations", payload.get("records", ())),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "view-provenance-lineage":
            graph = _graph_from_payload(_read_json(args.input))
            result = ProvenanceLineageViewer().view(
                graph,
                claim_id=args.claim_id,
                include_superseded=not args.active_only,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "build-uncertainty-ledger":
            payload = _read_json(args.input)
            result = UncertaintyLedgerBuilder().build(
                payload.get("entries", payload.get("observations", payload.get("records", ()))),
                context_key=args.context_key,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "route-reviewers":
            payload = _read_json(args.input)
            graph = _graph_from_payload(payload)
            uncertainty = None
            if payload.get("uncertainty"):
                uncertainty = UncertaintyLedgerBuilder().build(
                    payload["uncertainty"], context_key=graph.context_key
                )
            tier_adjudication = None
            if payload.get("tier_observations"):
                tier_adjudication = EvidenceTierAdjudicator().adjudicate(
                    payload["tier_observations"], context_key=graph.context_key
                )
            result = ReviewerAssignmentRouter().route(
                graph,
                uncertainty=uncertainty,
                tier_adjudication=tier_adjudication,
                required_roles=args.roles,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "view-topology":
            payload = _read_json(args.input)
            result = TopologyViewer().build(
                context_key=args.context_key,
                loops=payload.get("loops", payload.get("observations", ())),
                contacts=payload.get("contacts", ()),
                contact_scores=payload.get("contact_scores", payload.get("scores", ())),
                activity_results=payload.get("activity_results", payload.get("activity", ())),
                focus_chromosome=args.focus_chromosome,
                focus_start=args.focus_start,
                focus_end=args.focus_end,
                max_nodes=args.max_nodes,
                max_edges=args.max_edges,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "explore-causal-chain":
            payload = _read_json(args.input)
            result = CausalChainExplorer().explore(
                payload.get("results", payload.get("mediators", payload)),
                context_key=args.context_key,
                chain_id=args.chain_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "view-posterior-decomposition":
            payload = _read_json(args.input)
            result = PosteriorDecompositionViewer().view(
                payload.get("posterior", payload),
                payload.get("components", ()),
                context_key=args.context_key,
                residual_tolerance=args.residual_tolerance,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "filter-evidence-table":
            payload = _read_json(args.input)
            workspace = _workspace_from_payload(payload)
            table_filter = EvidenceTableFilter(
                text=args.text,
                context_key=args.context_key or workspace.context_key,
                channels=tuple(args.channel),
                tiers=tuple(args.tier),
                states=tuple(WorkspaceState(value) for value in args.state),
                source_ids=tuple(args.source_id),
                min_confidence=args.min_confidence,
                offset=args.offset,
                limit=args.limit,
            )
            result = EvidenceTableAndFilters().build(workspace, table_filter)
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "audit-policy-claim":
            payload = _read_json(args.input)
            request = _invocation_request_from_payload(payload)
            registry = default_control_plane_registry()
            result = PolicyClaimAuditor().audit(
                request,
                registry.agent(request.agent_id),
                registry.tool(request.tool_id),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "schedule-budget":
            payload = _read_json(args.input)
            result = BudgetResourceScheduler().schedule(
                payload.get("items", payload.get("work", ())),
                max_invocations=args.max_invocations,
                max_network_requests=args.max_network_requests,
                max_seconds=args.max_seconds,
                max_cost_units=args.max_cost_units,
                capacity=ResourceEnvelope(
                    cpu=args.cpu,
                    memory_gb=args.memory_gb,
                    gpu_count=args.gpu_count,
                    storage_gb=args.storage_gb,
                    network_egress=args.network_egress,
                    max_seconds=args.max_seconds,
                ),
                schedule_id=args.schedule_id,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "route-fallback":
            payload = _read_json(args.input)
            request = FallbackRequest.from_mapping(
                payload.get("request", payload)
                if isinstance(payload.get("request", payload), Mapping)
                else payload
            )
            result = DeterministicFallbackRouter().route(
                request,
                payload.get("candidates", payload.get("alternates", ())),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "queue-human-review":
            payload = _read_json(args.input)
            result = HumanReviewQueueRouter().route(
                payload.get("items", payload.get("outcomes", ())),
                required_roles=args.roles,
                max_review_candidates=args.max_review_candidates,
                queue_id=args.queue_id,
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
        if args.command == "predict-nucleosome-propensity":
            result = NucleosomeSequencePropensityModel().predict(
                _read_rows(args.input, "records", "windows", "observations"),
                context_key=args.context_key,
                minimum_length=args.minimum_length,
                periodicity_period=args.periodicity_period,
                favored_threshold=args.favored_threshold,
                depleted_threshold=args.depleted_threshold,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "scan-splice-regulatory":
            payload = _read_json(args.input)
            result = SpliceRegulatoryNoncodingScanner().scan(
                payload.get("records", payload.get("windows", payload.get("observations", ()))),
                _splice_alpha_motifs(payload.get("motifs", ())),
                context_key=args.context_key or payload.get("context_key"),
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "scan-utr-regulatory":
            payload = _read_json(args.input)
            result = UtrRegulatoryScanner().scan(
                payload.get("records", payload.get("windows", payload.get("observations", ()))),
                _utr_alpha_motifs(payload.get("motifs", ())),
                context_key=args.context_key or payload.get("context_key"),
                minimum_uorf_codons=args.minimum_uorf_codons,
            )
            _write_json(result.to_dict(), args.output)
            return 0
        if args.command == "evaluate-promoter-grammar":
            payload = _read_json(args.input)
            result = PromoterCoreGrammarModel().evaluate(
                payload.get("records", payload.get("promoters", payload.get("observations", ()))),
                _promoter_alpha_motifs(payload.get("motifs", ())),
                _promoter_alpha_rules(payload.get("rules", ())),
                context_key=args.context_key or payload.get("context_key"),
                minimum_coverage=args.minimum_coverage,
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
        if args.command == "evaluate-frontier-fixture":
            report = evaluate_frontier_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "frontier-contracts":
            _write_json(default_frontier_contract_registry().manifest(), args.output)
            return 0
        if args.command == "evaluate-frontier-scenarios":
            report = evaluate_frontier_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "frontier-quality-gate":
            report = evaluate_frontier_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-frontier-data":
            report = audit_public_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-frontier-fixtures":
            report = replay_frontier_fixtures(
                args.inputs,
                required_context_key=args.required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "serve":
            server = create_server(args.host, args.port, args.data_root)
            print(f"glio-noncode listening on http://{args.host}:{args.port}")
            server.serve_forever()
            return 0
    except (GlioError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 1
