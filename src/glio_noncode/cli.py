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
from .atlas_alpha_evidence_contracts import default_atlas_alpha_evidence_contracts
from .atlas_alpha_evidence_exports import (
    export_atlas_alpha_evidence_metrics_csv,
    export_atlas_alpha_evidence_receipts_csv,
    export_atlas_alpha_evidence_review_csv,
    render_atlas_alpha_evidence_review_markdown,
)
from .atlas_alpha_evidence_fixture_eval import evaluate_atlas_alpha_evidence_fixture
from .atlas_alpha_evidence_lineage import build_atlas_alpha_evidence_lineage
from .atlas_alpha_evidence_metrics import compute_atlas_alpha_evidence_metrics
from .atlas_alpha_evidence_observability import build_atlas_alpha_evidence_trace
from .atlas_alpha_evidence_public_data import (
    audit_atlas_alpha_evidence_data,
    default_atlas_alpha_evidence_fixture,
    load_atlas_alpha_evidence_fixture,
)
from .atlas_alpha_evidence_quality_gate import run_atlas_alpha_evidence_quality_gate
from .atlas_alpha_evidence_reconciliation import reconcile_atlas_alpha_evidence
from .atlas_alpha_evidence_release import (
    build_atlas_alpha_evidence_release,
)
from .atlas_alpha_evidence_replay import replay_atlas_alpha_evidence_evaluation
from .atlas_alpha_evidence_runtime import (
    AtlasAlphaEvidenceRuntimeOptions,
    run_atlas_alpha_evidence_pipeline,
)
from .atlas_alpha_evidence_scenario_matrix import evaluate_atlas_alpha_evidence_scenarios
from .atlas_alpha_evidence_schema import (
    atlas_alpha_evidence_schema_manifest,
    validate_atlas_alpha_evidence_schema,
)
from .atlas_alpha_evidence_views import build_atlas_alpha_evidence_view, review_queue_summary
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
from .cell_state_frontier_contracts import default_cell_state_frontier_contracts
from .cell_state_frontier_exports import (
    export_cell_state_frontier_metrics_csv,
    export_cell_state_frontier_receipts_csv,
    export_cell_state_frontier_review_csv,
    render_cell_state_frontier_review_markdown,
)
from .cell_state_frontier_fixture_eval import evaluate_cell_state_frontier_fixture
from .cell_state_frontier_lineage import build_cell_state_frontier_lineage
from .cell_state_frontier_metrics import compute_cell_state_frontier_metrics
from .cell_state_frontier_observability import build_cell_state_frontier_trace
from .cell_state_frontier_policy import evaluate_cell_state_frontier_policy
from .cell_state_frontier_public_data import (
    audit_cell_state_frontier_data,
    default_cell_state_frontier_fixture,
    load_cell_state_frontier_fixture,
)
from .cell_state_frontier_quality_gate import run_cell_state_frontier_quality_gate
from .cell_state_frontier_reconciliation import reconcile_cell_state_frontier
from .cell_state_frontier_release import build_cell_state_frontier_release
from .cell_state_frontier_replay import replay_cell_state_frontier_evaluation
from .cell_state_frontier_runtime import (
    CellStateFrontierRuntimeOptions,
    run_cell_state_frontier_pipeline,
)
from .cell_state_frontier_scenario_matrix import evaluate_cell_state_frontier_scenarios
from .cell_state_frontier_schema import (
    cell_state_frontier_schema_manifest,
    validate_cell_state_frontier_schema,
)
from .cell_state_frontier_views import (
    build_cell_state_frontier_view,
    cell_state_frontier_review_summary,
)
from .chromatin_alpha import (
    AlleleSpecificChromatinAnalyzer,
    BatchCellCompositionCorrector,
    ChromatinStateSegmentationAdapter,
    EpigenomicPurityDeconvolver,
)
from .chromatin_context import ChromatinTrackKind, ChromatinTrackParser
from .chromatin_frontier_contracts import default_chromatin_frontier_contracts
from .chromatin_frontier_exports import (
    export_chromatin_frontier_metrics_csv,
    export_chromatin_frontier_receipts_csv,
    export_chromatin_frontier_review_csv,
    render_chromatin_frontier_review_markdown,
)
from .chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from .chromatin_frontier_lineage import build_chromatin_frontier_lineage
from .chromatin_frontier_metrics import compute_chromatin_frontier_metrics
from .chromatin_frontier_observability import build_chromatin_frontier_trace
from .chromatin_frontier_policy import evaluate_chromatin_frontier_policy
from .chromatin_frontier_public_data import (
    audit_chromatin_frontier_data,
    default_chromatin_frontier_fixture,
    load_chromatin_frontier_fixture,
)
from .chromatin_frontier_quality_gate import run_chromatin_frontier_quality_gate
from .chromatin_frontier_reconciliation import reconcile_chromatin_frontier
from .chromatin_frontier_release import build_chromatin_frontier_release
from .chromatin_frontier_replay import replay_chromatin_frontier_evaluation
from .chromatin_frontier_runtime import (
    ChromatinFrontierRuntimeOptions,
    run_chromatin_frontier_pipeline,
)
from .chromatin_frontier_scenario_matrix import evaluate_chromatin_frontier_scenarios
from .chromatin_frontier_schema import (
    chromatin_frontier_schema_manifest,
    validate_chromatin_frontier_schema,
)
from .chromatin_frontier_views import (
    build_chromatin_frontier_view,
    chromatin_frontier_review_summary,
)
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
from .evidence_lifecycle_frontier_artifacts import build_evidence_lifecycle_artifact_inventory
from .evidence_lifecycle_frontier_bundle import assemble_evidence_lifecycle_bundle
from .evidence_lifecycle_frontier_contracts import default_evidence_lifecycle_contracts
from .evidence_lifecycle_frontier_depth import audit_evidence_lifecycle_depth
from .evidence_lifecycle_frontier_exports import export_evidence_lifecycle_review_csv
from .evidence_lifecycle_frontier_fixture_eval import evaluate_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_lineage import build_evidence_lifecycle_lineage
from .evidence_lifecycle_frontier_metrics import measure_evidence_lifecycle
from .evidence_lifecycle_frontier_observability import observe_evidence_lifecycle
from .evidence_lifecycle_frontier_policy import default_evidence_lifecycle_policy
from .evidence_lifecycle_frontier_public_data import audit_evidence_lifecycle_data, default_evidence_lifecycle_fixture, load_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_quality_gate import evaluate_evidence_lifecycle_quality
from .evidence_lifecycle_frontier_reconciliation import reconcile_evidence_lifecycle
from .evidence_lifecycle_frontier_release import build_evidence_lifecycle_release_manifest
from .evidence_lifecycle_frontier_replay import replay_evidence_lifecycle
from .evidence_lifecycle_frontier_review_queue import build_evidence_lifecycle_review_queue
from .evidence_lifecycle_frontier_runtime import run_evidence_lifecycle_runtime
from .evidence_lifecycle_frontier_schema import default_evidence_lifecycle_schema
from .evidence_lifecycle_frontier_views import build_evidence_lifecycle_review_view
from .frontier_atlas_contracts import default_frontier_atlas_contracts
from .frontier_atlas_exports import (
    export_frontier_atlas_metrics_csv,
    export_frontier_atlas_receipts_csv,
    export_frontier_atlas_review_csv,
    render_frontier_atlas_review_markdown,
)
from .frontier_atlas_fixture_eval import evaluate_frontier_atlas_fixture
from .frontier_atlas_lineage import build_frontier_atlas_lineage
from .frontier_atlas_metrics import compute_frontier_atlas_metrics
from .frontier_atlas_observability import build_frontier_atlas_trace
from .frontier_atlas_policy import evaluate_frontier_atlas_policy
from .frontier_atlas_public_data import (
    audit_frontier_atlas_data,
    default_frontier_atlas_fixture,
    load_frontier_atlas_fixture,
)
from .frontier_atlas_quality_gate import run_frontier_atlas_quality_gate
from .frontier_atlas_reconciliation import reconcile_frontier_atlas
from .frontier_atlas_release import build_frontier_atlas_release
from .frontier_atlas_replay import replay_frontier_atlas_evaluation
from .frontier_atlas_runtime import FrontierAtlasRuntimeOptions, run_frontier_atlas_pipeline
from .frontier_atlas_scenario_matrix import evaluate_frontier_atlas_scenarios
from .frontier_atlas_schema import frontier_atlas_schema_manifest, validate_frontier_atlas_schema
from .frontier_atlas_views import build_frontier_atlas_view, frontier_atlas_review_summary
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
from .frontier_release_hardening import HARDENING_OPERATIONS, run_hardening_operation
from .frontier_replay import replay_frontier_fixtures
from .frontier_scenario_matrix import evaluate_frontier_scenarios
from .identity_beta import (
    BatchSampleIdentityChecker,
    ChainOfCustodyCapture,
    DuplicateAliasReconciler,
    VariantEquivalenceResolver,
)
from .identity_bundle import IdentityBundleFormat, IdentityEvidenceBundleBuilder
from .identity_contracts import default_identity_contract_registry
from .identity_fixture_eval import evaluate_identity_fixture
from .identity_public_data import IdentityFixtureCatalog, audit_identity_fixture
from .identity_quality_gate import evaluate_identity_quality_gate
from .identity_replay import IdentityReplayExpectation, replay_identity_fixtures
from .identity_scenario_matrix import evaluate_identity_scenarios
from .intake import IntakeFormat, VariantIntake
from .intake_bundle import IntakeBundleFormat, IntakeEvidenceBundleBuilder
from .intake_contracts import default_intake_contract_registry
from .intake_fixture_eval import evaluate_intake_fixture
from .intake_public_data import IntakeFixtureCatalog, audit_intake_fixture
from .intake_quality_gate import evaluate_intake_quality_gate
from .intake_replay import IntakeReplayExpectation, replay_intake_fixtures
from .intake_runtime import run_intake_pipeline
from .intake_scenario_matrix import evaluate_intake_scenarios
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
from .link_frontier_bundle import build_link_frontier_bundle
from .link_frontier_contracts import default_link_frontier_contracts
from .link_frontier_depth import run_link_frontier_depth_audit
from .link_frontier_exports import (
    export_link_frontier_metrics_csv,
    export_link_frontier_receipts_csv,
    export_link_frontier_review_csv,
    render_link_frontier_review_markdown,
)
from .link_frontier_fixture_eval import evaluate_link_frontier_fixture
from .link_frontier_lineage import build_link_frontier_lineage
from .link_frontier_metrics import compute_link_frontier_metrics
from .link_frontier_observability import build_link_frontier_trace
from .link_frontier_policy import evaluate_link_frontier_policy
from .link_frontier_public_data import (
    audit_link_frontier_data,
    default_link_frontier_fixture,
    load_link_frontier_fixture,
)
from .link_frontier_quality_gate import run_link_frontier_quality_gate
from .link_frontier_reconciliation import reconcile_link_frontier
from .link_frontier_release import build_link_frontier_release
from .link_frontier_replay import replay_link_frontier_evaluation
from .link_frontier_runtime import run_link_frontier_pipeline
from .link_frontier_scenario_matrix import evaluate_link_frontier_scenarios
from .link_frontier_schema import default_link_frontier_schemas, validate_link_frontier_schema
from .link_frontier_views import build_link_frontier_view, link_frontier_review_summary
from .causal_frontier_bundle import assemble_causal_frontier_bundle
from .causal_frontier_contracts import default_causal_frontier_contracts
from .causal_frontier_depth import audit_causal_frontier_depth
from .causal_frontier_exports import export_causal_frontier_review_csv
from .causal_frontier_fixture_eval import evaluate_causal_frontier_fixture
from .causal_frontier_lineage import build_causal_frontier_lineage
from .causal_frontier_metrics import measure_causal_frontier
from .causal_frontier_policy import default_causal_frontier_policy
from .causal_frontier_public_data import audit_causal_frontier_data, default_causal_frontier_fixture, load_causal_frontier_fixture
from .causal_frontier_quality_gate import evaluate_causal_frontier_quality
from .causal_frontier_reconciliation import reconcile_causal_frontier
from .causal_frontier_release import build_causal_frontier_release_manifest
from .causal_frontier_replay import replay_causal_frontier
from .causal_frontier_runtime import run_causal_frontier_runtime
from .causal_frontier_schema import default_causal_frontier_schema
from .causal_frontier_views import build_causal_frontier_review_view
from .cohort_frontier_bundle import assemble_cohort_frontier_bundle
from .cohort_frontier_contracts import default_cohort_frontier_contracts
from .cohort_frontier_depth import audit_cohort_frontier_depth
from .cohort_frontier_exports import export_cohort_frontier_review_csv
from .cohort_frontier_fixture_eval import evaluate_cohort_frontier_fixture
from .cohort_frontier_lineage import build_cohort_frontier_lineage
from .cohort_frontier_metrics import measure_cohort_frontier
from .cohort_frontier_policy import default_cohort_frontier_policy
from .cohort_frontier_public_data import audit_cohort_frontier_data, default_cohort_frontier_fixture, load_cohort_frontier_fixture
from .cohort_frontier_quality_gate import evaluate_cohort_frontier_quality
from .cohort_frontier_reconciliation import reconcile_cohort_frontier
from .cohort_frontier_release import build_cohort_frontier_release_manifest
from .cohort_frontier_replay import replay_cohort_frontier
from .cohort_frontier_runtime import run_cohort_frontier_runtime
from .cohort_frontier_schema import default_cohort_frontier_schema
from .cohort_frontier_views import build_cohort_frontier_review_view
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
from .molecular_atlas_bundle import MolecularAtlasBundleBuilder, MolecularAtlasBundleFormat
from .molecular_atlas_contracts import default_molecular_atlas_contracts
from .molecular_atlas_fixture_eval import evaluate_molecular_atlas_fixture
from .molecular_atlas_lineage import build_molecular_atlas_lineage
from .molecular_atlas_metrics import (
    build_molecular_atlas_metrics,
    render_molecular_atlas_metrics,
    verify_molecular_atlas_metrics,
)
from .molecular_atlas_public_data import audit_molecular_atlas_data, load_molecular_atlas_fixture
from .molecular_atlas_quality_gate import evaluate_molecular_atlas_quality_gate
from .molecular_atlas_reconciliation import reconcile_molecular_atlas_views
from .molecular_atlas_release import (
    build_molecular_atlas_release_manifest,
    write_molecular_atlas_release_manifest,
)
from .molecular_atlas_replay import replay_molecular_atlas_evaluation
from .molecular_atlas_runtime import run_molecular_atlas_pipeline_file
from .molecular_atlas_scenario_matrix import evaluate_molecular_atlas_scenarios
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
from .reference_annotation_bundle import (
    ReferenceAnnotationBundleBuilder,
    ReferenceAnnotationBundleFormat,
)
from .reference_annotation_contracts import default_reference_annotation_contracts
from .reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from .reference_annotation_lineage import build_reference_annotation_lineage
from .reference_annotation_public_data import (
    audit_reference_annotation_data,
    load_reference_annotation_fixture,
)
from .reference_annotation_quality_gate import evaluate_reference_annotation_quality_gate
from .reference_annotation_reconciliation import reconcile_reference_annotation_views
from .reference_annotation_release import (
    build_reference_annotation_release_manifest,
    write_reference_annotation_release_manifest,
)
from .reference_annotation_replay import replay_reference_annotation_evaluation
from .reference_annotation_runtime import run_reference_annotation_pipeline_file
from .reference_annotation_scenario_matrix import evaluate_reference_annotation_scenarios
from .reference_beta import (
    DiseaseOntologyMapper,
    GencodeTranscriptAdapter,
    ManeTranscriptAdapter,
    RegulatoryOntologyAdapter,
)
from .reference_coordinate_bundle import (
    ReferenceCoordinateBundleBuilder,
    ReferenceCoordinateBundleFormat,
)
from .reference_coordinate_contracts import default_reference_coordinate_contracts
from .reference_coordinate_fixture_eval import evaluate_reference_coordinate_fixture
from .reference_coordinate_lineage import build_reference_coordinate_lineage
from .reference_coordinate_public_data import (
    ReferenceCoordinateFixtureCatalog,
    audit_reference_coordinate_data,
)
from .reference_coordinate_quality_gate import evaluate_reference_coordinate_quality_gate
from .reference_coordinate_reconciliation import reconcile_reference_coordinate_views
from .reference_coordinate_replay import (
    default_reference_coordinate_expectation,
    replay_reference_coordinate_fixture,
)
from .reference_coordinate_runtime import (
    ReferenceCoordinatePipelineRequest,
    run_reference_coordinate_pipeline,
)
from .reference_coordinate_scenario_matrix import evaluate_reference_coordinate_scenarios
from .reference_governance_bundle import (
    ReferenceGovernanceBundleBuilder,
    ReferenceGovernanceBundleFormat,
)
from .reference_governance_contracts import default_reference_governance_contracts
from .reference_governance_fixture_eval import evaluate_reference_governance_fixture
from .reference_governance_lineage import build_reference_governance_lineage
from .reference_governance_metrics import (
    build_reference_governance_metrics,
    render_reference_governance_metrics,
    verify_reference_governance_metrics,
)
from .reference_governance_public_data import (
    audit_reference_governance_data,
    load_reference_governance_fixture,
)
from .reference_governance_quality_gate import evaluate_reference_governance_quality_gate
from .reference_governance_reconciliation import reconcile_reference_governance_views
from .reference_governance_release import (
    build_reference_governance_release_manifest,
    write_reference_governance_release_manifest,
)
from .reference_governance_replay import replay_reference_governance_evaluation
from .reference_governance_runtime import run_reference_governance_pipeline_file
from .reference_governance_scenario_matrix import evaluate_reference_governance_scenarios
from .reference_registry import default_reference_registry
from .regulatory_atlas_bundle import RegulatoryAtlasBundleBuilder, RegulatoryAtlasBundleFormat
from .regulatory_atlas_contracts import default_regulatory_atlas_contracts
from .regulatory_atlas_fixture_eval import evaluate_regulatory_atlas_fixture
from .regulatory_atlas_lineage import build_regulatory_atlas_lineage
from .regulatory_atlas_metrics import (
    build_regulatory_atlas_metrics,
    render_regulatory_atlas_metrics,
    verify_regulatory_atlas_metrics,
)
from .regulatory_atlas_public_data import (
    audit_regulatory_atlas_data,
    load_regulatory_atlas_fixture,
)
from .regulatory_atlas_quality_gate import evaluate_regulatory_atlas_quality_gate
from .regulatory_atlas_reconciliation import reconcile_regulatory_atlas_views
from .regulatory_atlas_release import (
    build_regulatory_atlas_release_manifest,
    write_regulatory_atlas_release_manifest,
)
from .regulatory_atlas_replay import replay_regulatory_atlas_evaluation
from .regulatory_atlas_runtime import run_regulatory_atlas_pipeline_file
from .regulatory_atlas_scenario_matrix import evaluate_regulatory_atlas_scenarios
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
from .sequence_frontier_contracts import default_sequence_frontier_contracts
from .sequence_frontier_exports import (
    export_sequence_frontier_metrics_csv,
    export_sequence_frontier_receipts_csv,
    export_sequence_frontier_review_csv,
    render_sequence_frontier_review_markdown,
)
from .sequence_frontier_fixture_eval import evaluate_sequence_frontier_fixture
from .sequence_frontier_lineage import build_sequence_frontier_lineage
from .sequence_frontier_metrics import compute_sequence_frontier_metrics
from .sequence_frontier_observability import build_sequence_frontier_trace
from .sequence_frontier_policy import evaluate_sequence_frontier_policy
from .sequence_frontier_public_data import (
    audit_sequence_frontier_data,
    default_sequence_frontier_fixture,
    load_sequence_frontier_fixture,
)
from .sequence_frontier_quality_gate import run_sequence_frontier_quality_gate
from .sequence_frontier_reconciliation import reconcile_sequence_frontier
from .sequence_frontier_release import build_sequence_frontier_release
from .sequence_frontier_replay import replay_sequence_frontier_evaluation
from .sequence_frontier_runtime import (
    SequenceFrontierRuntimeOptions,
    run_sequence_frontier_pipeline,
)
from .sequence_frontier_scenario_matrix import evaluate_sequence_frontier_scenarios
from .sequence_frontier_schema import (
    sequence_frontier_schema_manifest,
    validate_sequence_frontier_schema,
)
from .sequence_frontier_views import build_sequence_frontier_view, sequence_frontier_review_summary
from .specimen_beta import (
    CancerCellFractionEstimator,
    MosaicismPosteriorEstimator,
    SomaticGermlineOriginClassifier,
    SubcloneAssigner,
)
from .specimen_beta_frontier_bundle import (
    SpecimenBetaFrontierBundleFormat,
    SpecimenBetaFrontierEvidenceBundleBuilder,
)
from .specimen_beta_frontier_contracts import default_specimen_beta_frontier_contracts
from .specimen_beta_frontier_fixture_eval import evaluate_specimen_beta_frontier_fixture
from .specimen_beta_frontier_lineage import (
    audit_specimen_beta_frontier_lineage,
    build_specimen_beta_frontier_lineage,
)
from .specimen_beta_frontier_public_data import (
    SpecimenBetaFrontierFixtureCatalog,
    audit_specimen_beta_frontier_fixture,
)
from .specimen_beta_frontier_quality_gate import evaluate_specimen_beta_frontier_quality_gate
from .specimen_beta_frontier_replay import (
    SpecimenBetaFrontierReplayExpectation,
    replay_specimen_beta_frontier_fixtures,
)
from .specimen_beta_frontier_runtime import (
    run_specimen_beta_frontier_pipeline,
    specimen_beta_frontier_pipeline_request_from_file,
)
from .specimen_beta_frontier_scenario_matrix import evaluate_specimen_beta_frontier_scenarios
from .specimen_context import PurityPloidyImporter
from .specimen_frontier_bundle import (
    SpecimenFrontierBundleFormat,
    SpecimenFrontierEvidenceBundleBuilder,
)
from .specimen_frontier_contracts import default_specimen_frontier_contract_registry
from .specimen_frontier_fixture_eval import evaluate_specimen_frontier_fixture
from .specimen_frontier_lineage import (
    audit_specimen_frontier_lineage,
    build_specimen_frontier_lineage,
)
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureCatalog,
    audit_specimen_frontier_fixture,
)
from .specimen_frontier_quality_gate import evaluate_specimen_frontier_quality_gate
from .specimen_frontier_replay import (
    SpecimenFrontierReplayExpectation,
    replay_specimen_frontier_fixtures,
)
from .specimen_frontier_runtime import run_specimen_frontier_pipeline
from .specimen_frontier_scenario_matrix import evaluate_specimen_frontier_scenarios
from .specimen_lineage import (
    LongitudinalSpecimenLinker,
    MultiRegionLineageResolver,
    PrimaryRecurrencePhaseMapper,
    TreatmentExposureContextualizer,
)
from .specimen_lineage_bundle import (
    SpecimenLineageBundleFormat,
    SpecimenLineageEvidenceBundleBuilder,
)
from .specimen_lineage_contracts import default_specimen_lineage_contracts
from .specimen_lineage_fixture_eval import evaluate_specimen_lineage_fixture
from .specimen_lineage_lineage import (
    audit_specimen_lineage_lineage,
    build_specimen_lineage_lineage,
)
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
    audit_specimen_lineage_fixture,
)
from .specimen_lineage_quality_gate import evaluate_specimen_lineage_quality_gate
from .specimen_lineage_reconciliation import (
    audit_specimen_lineage_receipt_index,
    build_specimen_lineage_receipt_index,
)
from .specimen_lineage_replay import (
    SpecimenLineageReplayExpectation,
    replay_specimen_lineage_fixtures,
)
from .specimen_lineage_runtime import (
    run_specimen_lineage_pipeline,
    specimen_lineage_pipeline_request_from_file,
)
from .specimen_lineage_scenario_matrix import evaluate_specimen_lineage_scenarios
from .specimen_preanalytic_bundle import (
    SpecimenPreanalyticBundleFormat,
    SpecimenPreanalyticEvidenceBundleBuilder,
)
from .specimen_preanalytic_contracts import default_specimen_preanalytic_contracts
from .specimen_preanalytic_fixture_eval import evaluate_specimen_preanalytic_fixture
from .specimen_preanalytic_lineage import (
    audit_specimen_preanalytic_lineage,
    build_specimen_preanalytic_lineage,
)
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    audit_specimen_preanalytic_data,
)
from .specimen_preanalytic_quality_gate import evaluate_specimen_preanalytic_quality_gate
from .specimen_preanalytic_reconciliation import (
    audit_specimen_preanalytic_receipt_index,
    build_specimen_preanalytic_receipt_index,
)
from .specimen_preanalytic_replay import (
    SpecimenPreanalyticReplayExpectation,
    replay_specimen_preanalytic_file,
)
from .specimen_preanalytic_runtime import (
    SpecimenPreanalyticPipelineRequest,
    run_specimen_preanalytic_pipeline,
)
from .specimen_preanalytic_scenario_matrix import evaluate_specimen_preanalytic_scenarios
from .structural_beta import (
    ChromothripsisPatternDetector,
    EnhancerHijackingCandidateDetector,
    ExtrachromosomalDnaCandidateDetector,
    FocalAmplificationBoundaryMapper,
)
from .structural_beta_bundle import StructuralBetaBundleFormat, StructuralBetaEvidenceBundleBuilder
from .structural_beta_contracts import default_structural_beta_contract_registry
from .structural_beta_fixture_eval import evaluate_structural_beta_fixture
from .structural_beta_lineage import audit_structural_beta_lineage, build_structural_beta_lineage
from .structural_beta_public_data import StructuralBetaFixtureCatalog, audit_structural_beta_fixture
from .structural_beta_quality_gate import evaluate_structural_beta_quality_gate
from .structural_beta_replay import StructuralBetaReplayExpectation, replay_structural_beta_fixtures
from .structural_beta_runtime import run_structural_beta_pipeline
from .structural_beta_scenario_matrix import evaluate_structural_beta_scenarios
from .structural_bundle import StructuralBundleFormat, StructuralEvidenceBundleBuilder
from .structural_contracts import default_structural_contract_registry
from .structural_extensions import CopyNumberSegmentHarmonizer, SVConsensusImporter
from .structural_fixture_eval import evaluate_structural_fixture
from .structural_frontier_bundle import (
    StructuralFrontierBundleFormat,
    StructuralFrontierEvidenceBundleBuilder,
)
from .structural_frontier_contracts import default_structural_frontier_contract_registry
from .structural_frontier_fixture_eval import evaluate_structural_frontier_fixture
from .structural_frontier_lineage import (
    audit_structural_frontier_lineage,
    build_structural_frontier_lineage,
)
from .structural_frontier_public_data import (
    StructuralFrontierFixtureCatalog,
    audit_structural_frontier_fixture,
)
from .structural_frontier_quality_gate import evaluate_structural_frontier_quality_gate
from .structural_frontier_replay import (
    StructuralFrontierReplayExpectation,
    replay_structural_frontier_fixtures,
)
from .structural_frontier_runtime import run_structural_frontier_pipeline
from .structural_frontier_scenario_matrix import evaluate_structural_frontier_scenarios
from .structural_haplotype import (
    AlleleAwareSvRepresenter,
    PangenomeGraphProjector,
    PhasedHaplotypeAssembler,
    RepeatMobileElementAnnotator,
)
from .structural_haplotype_bundle import (
    StructuralHaplotypeBundleFormat,
    StructuralHaplotypeEvidenceBundleBuilder,
)
from .structural_haplotype_contracts import default_structural_haplotype_contract_registry
from .structural_haplotype_fixture_eval import evaluate_structural_haplotype_fixture
from .structural_haplotype_lineage import (
    audit_structural_haplotype_lineage,
    build_structural_haplotype_lineage,
)
from .structural_haplotype_public_data import (
    StructuralHaplotypeFixtureCatalog,
    audit_structural_haplotype_fixture,
)
from .structural_haplotype_quality_gate import evaluate_structural_haplotype_quality_gate
from .structural_haplotype_replay import (
    StructuralHaplotypeReplayExpectation,
    replay_structural_haplotype_fixtures,
)
from .structural_haplotype_runtime import run_structural_haplotype_pipeline
from .structural_haplotype_scenario_matrix import evaluate_structural_haplotype_scenarios
from .structural_lineage import audit_structural_lineage, build_structural_lineage
from .structural_public_data import StructuralFixtureCatalog, audit_structural_fixture
from .structural_quality_gate import evaluate_structural_quality_gate
from .structural_replay import StructuralReplayExpectation, replay_structural_fixtures
from .structural_runtime import run_structural_pipeline
from .structural_scenario_matrix import evaluate_structural_scenarios
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
from .topology_frontier_contracts import default_topology_frontier_contracts
from .topology_frontier_exports import (
    export_topology_frontier_metrics_csv,
    export_topology_frontier_receipts_csv,
    export_topology_frontier_review_csv,
    render_topology_frontier_review_markdown,
)
from .topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from .topology_frontier_lineage import build_topology_frontier_lineage
from .topology_frontier_metrics import compute_topology_frontier_metrics
from .topology_frontier_observability import build_topology_frontier_trace
from .topology_frontier_policy import evaluate_topology_frontier_policy
from .topology_frontier_public_data import (
    audit_topology_frontier_data,
    default_topology_frontier_fixture,
    load_topology_frontier_fixture,
)
from .topology_frontier_quality_gate import run_topology_frontier_quality_gate
from .topology_frontier_reconciliation import reconcile_topology_frontier
from .topology_frontier_release import build_topology_frontier_release
from .topology_frontier_replay import replay_topology_frontier_evaluation
from .topology_frontier_runtime import (
    TopologyFrontierRuntimeOptions,
    run_topology_frontier_pipeline,
)
from .topology_frontier_scenario_matrix import evaluate_topology_frontier_scenarios
from .topology_frontier_schema import (
    default_topology_frontier_schemas,
    validate_topology_frontier_schema,
)
from .topology_frontier_views import build_topology_frontier_view, topology_frontier_review_summary
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
from .validation_frontier_artifacts import ValidationFrontierArtifactKind, build_validation_frontier_artifact_inventory
from .validation_frontier_bundle import assemble_validation_frontier_bundle
from .validation_frontier_contracts import default_validation_frontier_contracts
from .validation_frontier_depth import audit_validation_frontier_depth
from .validation_frontier_exports import export_validation_frontier_review_csv
from .validation_frontier_fixture_eval import evaluate_validation_frontier_fixture
from .validation_frontier_lineage import build_validation_frontier_lineage
from .validation_frontier_metrics import measure_validation_frontier
from .validation_frontier_observability import observe_validation_frontier
from .validation_frontier_policy import default_validation_frontier_policy
from .validation_frontier_public_data import audit_validation_frontier_data, default_validation_frontier_fixture, load_validation_frontier_fixture
from .validation_frontier_quality_gate import evaluate_validation_frontier_quality
from .validation_frontier_reconciliation import reconcile_validation_frontier
from .validation_frontier_release import build_validation_frontier_release_manifest
from .validation_frontier_replay import replay_validation_frontier
from .validation_frontier_review_queue import build_validation_frontier_review_queue
from .validation_frontier_runtime import run_validation_frontier_runtime
from .validation_frontier_schema import default_validation_frontier_schema
from .validation_frontier_views import build_validation_frontier_review_view
from .variant_beta import (
    CategoricalCatalogParser,
    CatVRSNormalizer,
    MultiAllelicDecomposer,
    RepeatAwareNormalizer,
    VAAnnotationEnvelopeBuilder,
)
from .variant_normalization import VRSNormalizer
from .variation_bundle import VariationBundleFormat, VariationEvidenceBundleBuilder
from .variation_contracts import default_variation_contract_registry
from .variation_fixture_eval import evaluate_variation_fixture
from .variation_public_data import audit_variation_fixture
from .variation_quality_gate import evaluate_variation_quality_gate
from .variation_replay import replay_variation_fixtures
from .variation_scenario_matrix import evaluate_variation_scenarios
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


def _write_text(text: str, output: str | None) -> None:
    """Write a text export or stream it to standard output."""

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


def _read_atlas_alpha_evidence_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return (
        load_atlas_alpha_evidence_fixture(path) if path else default_atlas_alpha_evidence_fixture()
    )


def _read_frontier_atlas_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_frontier_atlas_fixture(path) if path else default_frontier_atlas_fixture()


def _read_sequence_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_sequence_frontier_fixture(path) if path else default_sequence_frontier_fixture()


def _read_chromatin_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_chromatin_frontier_fixture(path) if path else default_chromatin_frontier_fixture()


def _read_cell_state_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_cell_state_frontier_fixture(path) if path else default_cell_state_frontier_fixture()


def _read_topology_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_topology_frontier_fixture(path) if path else default_topology_frontier_fixture()


def _read_link_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_link_frontier_fixture(path) if path else default_link_frontier_fixture()


def _read_causal_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_causal_frontier_fixture(path) if path else default_causal_frontier_fixture()


def _read_cohort_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_cohort_frontier_fixture(path) if path else default_cohort_frontier_fixture()


def _read_validation_frontier_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_validation_frontier_fixture(path) if path else default_validation_frontier_fixture()


def _read_evidence_lifecycle_fixture(path: str | None):
    """Load a caller fixture or use the deterministic public aggregate."""

    return load_evidence_lifecycle_fixture(path) if path else default_evidence_lifecycle_fixture()


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

    variation_fixture = subparsers.add_parser(
        "evaluate-variation-fixture",
        help="evaluate the public aggregate fixture across five Domain 01 variation adapters",
    )
    variation_fixture.add_argument("input", type=str)
    variation_fixture.add_argument("--output", default=None)

    variation_data = subparsers.add_parser(
        "audit-variation-data",
        help="audit public aggregate variation records, source receipts, and exact context",
    )
    variation_data.add_argument("input", type=str)
    variation_data.add_argument("--output", default=None)

    variation_replay = subparsers.add_parser(
        "replay-variation-fixtures",
        help="replay one or more variation fixtures with identity and context controls",
    )
    variation_replay.add_argument("inputs", nargs="+", type=str)
    variation_replay.add_argument("--required-context-key", default=None)
    variation_replay.add_argument("--output", default=None)

    variation_quality = subparsers.add_parser(
        "variation-quality-gate",
        help="reconcile Domain 01 variation fixture, data, and replay evidence",
    )
    variation_quality.add_argument("input", type=str)
    variation_quality.add_argument("--output", default=None)
    variation_scenarios = subparsers.add_parser(
        "evaluate-variation-scenarios",
        help="run independent positive and review state-transition scenarios",
    )
    variation_scenarios.add_argument("input", type=str)
    variation_scenarios.add_argument("--output", default=None)
    variation_contracts = subparsers.add_parser(
        "variation-contracts",
        help="print the five-operation Domain 01 variation contract registry",
    )
    variation_contracts.add_argument("--output", default=None)
    variation_bundle = subparsers.add_parser(
        "build-variation-bundle",
        help="build a compact JSON, CSV, or Markdown variation evidence bundle",
    )
    variation_bundle.add_argument("input", type=str)
    variation_bundle.add_argument("--output", required=True)
    variation_bundle.add_argument(
        "--format",
        choices=[item.value for item in VariationBundleFormat],
        default=VariationBundleFormat.JSON.value,
    )
    variation_bundle.add_argument("--bundle-id", default=None)

    identity_fixture = subparsers.add_parser(
        "evaluate-identity-fixture",
        help="evaluate the public aggregate fixture across four Domain 01 identity adapters",
    )
    identity_fixture.add_argument("input", type=str)
    identity_fixture.add_argument("--output", default=None)

    identity_data = subparsers.add_parser(
        "audit-identity-data",
        help="audit public aggregate identity records, source receipts, and exact context",
    )
    identity_data.add_argument("input", type=str)
    identity_data.add_argument("--output", default=None)

    identity_replay = subparsers.add_parser(
        "replay-identity-fixtures",
        help="replay identity fixtures with identity, context, source, and count controls",
    )
    identity_replay.add_argument("inputs", nargs="+", type=str)
    identity_replay.add_argument("--required-context-key", default=None)
    identity_replay.add_argument("--output", default=None)

    identity_quality = subparsers.add_parser(
        "identity-quality-gate",
        help="reconcile Domain 01 identity fixture, data, replay, scenario, and contract evidence",
    )
    identity_quality.add_argument("input", type=str)
    identity_quality.add_argument("--output", default=None)

    identity_scenarios = subparsers.add_parser(
        "evaluate-identity-scenarios",
        help="run independent positive and review state-transition identity scenarios",
    )
    identity_scenarios.add_argument("input", type=str)
    identity_scenarios.add_argument("--output", default=None)

    identity_contracts = subparsers.add_parser(
        "identity-contracts",
        help="print the four-operation Domain 01 identity contract registry",
    )
    identity_contracts.add_argument("--output", default=None)

    identity_bundle = subparsers.add_parser(
        "build-identity-bundle",
        help="build a compact JSON, CSV, or Markdown identity evidence bundle",
    )
    identity_bundle.add_argument("input", type=str)
    identity_bundle.add_argument("--output", required=True)
    identity_bundle.add_argument(
        "--format",
        choices=[item.value for item in IdentityBundleFormat],
        default=IdentityBundleFormat.JSON.value,
    )
    identity_bundle.add_argument("--bundle-id", default=None)

    intake_fixture = subparsers.add_parser(
        "evaluate-intake-fixture",
        help="evaluate the public policy and aggregate fixture across four Domain 01 intake adapters",
    )
    intake_fixture.add_argument("input", type=str)
    intake_fixture.add_argument("--output", default=None)

    intake_data = subparsers.add_parser(
        "audit-intake-data",
        help="audit public policy and aggregate intake records, source receipts, and exact context",
    )
    intake_data.add_argument("input", type=str)
    intake_data.add_argument("--output", default=None)

    intake_replay = subparsers.add_parser(
        "replay-intake-fixtures",
        help="replay intake fixtures with identity, context, source, and evidence-floor controls",
    )
    intake_replay.add_argument("inputs", nargs="+", type=str)
    intake_replay.add_argument("--required-context-key", default=None)
    intake_replay.add_argument("--output", default=None)

    intake_quality = subparsers.add_parser(
        "intake-quality-gate",
        help="reconcile Domain 01 intake fixture, data, replay, scenario, and contract evidence",
    )
    intake_quality.add_argument("input", type=str)
    intake_quality.add_argument("--output", default=None)

    intake_scenarios = subparsers.add_parser(
        "evaluate-intake-scenarios",
        help="run independent positive and review state-transition intake scenarios",
    )
    intake_scenarios.add_argument("input", type=str)
    intake_scenarios.add_argument("--output", default=None)

    intake_contracts = subparsers.add_parser(
        "intake-contracts",
        help="print the four-operation Domain 01 intake contract registry",
    )
    intake_contracts.add_argument("--output", default=None)

    intake_bundle = subparsers.add_parser(
        "build-intake-bundle",
        help="build a compact JSON, CSV, or Markdown intake evidence bundle",
    )
    intake_bundle.add_argument("input", type=str)
    intake_bundle.add_argument("--output", required=True)
    intake_bundle.add_argument(
        "--format",
        choices=[item.value for item in IntakeBundleFormat],
        default=IntakeBundleFormat.JSON.value,
    )
    intake_bundle.add_argument("--bundle-id", default=None)
    intake_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state bundle for inspection instead of requiring the gate",
    )

    intake_pipeline = subparsers.add_parser(
        "run-intake-pipeline",
        help="run policy, anomaly, completeness, and export stages over one intake batch",
    )
    intake_pipeline.add_argument("input", type=str)
    intake_pipeline.add_argument("--output", default=None)

    structural_fixture = subparsers.add_parser(
        "evaluate-structural-fixture",
        help="evaluate the public aggregate fixture across Domain 02 C01-C04 structural operations",
    )
    structural_fixture.add_argument("input", type=str)
    structural_fixture.add_argument("--output", default=None)

    structural_data = subparsers.add_parser(
        "audit-structural-data",
        help="audit public aggregate structural sources, contexts, identities, and payload scope",
    )
    structural_data.add_argument("input", type=str)
    structural_data.add_argument("--output", default=None)

    structural_replay = subparsers.add_parser(
        "replay-structural-fixtures",
        help="replay structural fixtures with identity, context, source, and evidence floors",
    )
    structural_replay.add_argument("inputs", nargs="+", type=str)
    structural_replay.add_argument("--required-context-key", default=None)
    structural_replay.add_argument("--output", default=None)

    structural_quality = subparsers.add_parser(
        "structural-quality-gate",
        help="reconcile Domain 02 structural fixture, data, replay, scenario, and contract evidence",
    )
    structural_quality.add_argument("input", type=str)
    structural_quality.add_argument("--output", default=None)

    structural_scenarios = subparsers.add_parser(
        "evaluate-structural-scenarios",
        help="run independent positive and review state-transition structural scenarios",
    )
    structural_scenarios.add_argument("input", type=str)
    structural_scenarios.add_argument("--output", default=None)

    structural_contracts = subparsers.add_parser(
        "structural-contracts",
        help="print the four-operation Domain 02 structural contract registry",
    )
    structural_contracts.add_argument("--output", default=None)

    structural_bundle = subparsers.add_parser(
        "build-structural-bundle",
        help="build a compact JSON, CSV, or Markdown structural evidence bundle",
    )
    structural_bundle.add_argument("input", type=str)
    structural_bundle.add_argument("--output", required=True)
    structural_bundle.add_argument(
        "--format",
        choices=[item.value for item in StructuralBundleFormat],
        default=StructuralBundleFormat.JSON.value,
    )
    structural_bundle.add_argument("--bundle-id", default=None)
    structural_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state bundle for inspection instead of requiring the gate",
    )

    structural_pipeline = subparsers.add_parser(
        "run-structural-pipeline",
        help="run C01 reconstruction, C02 consensus, C03 complex resolution, and C04 harmonization",
    )
    structural_pipeline.add_argument("input", type=str)
    structural_pipeline.add_argument("--output", default=None)

    structural_lineage = subparsers.add_parser(
        "structural-lineage",
        help="build and audit a sanitized source-to-result structural lineage graph",
    )
    structural_lineage.add_argument("input", type=str)
    structural_lineage.add_argument("--output", default=None)

    structural_haplotype_fixture = subparsers.add_parser(
        "evaluate-structural-haplotype-fixture",
        help="evaluate the public aggregate fixture across Domain 02 C09-C12 structural haplotype operations",
    )
    structural_haplotype_fixture.add_argument("input", type=str)
    structural_haplotype_fixture.add_argument("--output", default=None)

    structural_haplotype_data = subparsers.add_parser(
        "audit-structural-haplotype-data",
        help="audit public aggregate C09-C12 sources, contexts, identities, and payload scope",
    )
    structural_haplotype_data.add_argument("input", type=str)
    structural_haplotype_data.add_argument("--output", default=None)

    structural_haplotype_replay = subparsers.add_parser(
        "replay-structural-haplotype-fixtures",
        help="replay C09-C12 fixtures with identity, context, source, and evidence floors",
    )
    structural_haplotype_replay.add_argument("inputs", nargs="+", type=str)
    structural_haplotype_replay.add_argument("--required-context-key", default=None)
    structural_haplotype_replay.add_argument("--output", default=None)

    structural_haplotype_quality = subparsers.add_parser(
        "structural-haplotype-quality-gate",
        help="reconcile C09-C12 fixture, data, replay, scenario, contract, and lineage evidence",
    )
    structural_haplotype_quality.add_argument("input", type=str)
    structural_haplotype_quality.add_argument("--output", default=None)

    structural_haplotype_scenarios = subparsers.add_parser(
        "evaluate-structural-haplotype-scenarios",
        help="run independent C09-C12 positive and review state-transition scenarios",
    )
    structural_haplotype_scenarios.add_argument("input", type=str)
    structural_haplotype_scenarios.add_argument("--output", default=None)

    structural_haplotype_contracts = subparsers.add_parser(
        "structural-haplotype-contracts",
        help="print the four-operation Domain 02 C09-C12 structural haplotype contract registry",
    )
    structural_haplotype_contracts.add_argument("--output", default=None)

    structural_haplotype_bundle = subparsers.add_parser(
        "build-structural-haplotype-bundle",
        help="build a compact JSON, CSV, or Markdown C09-C12 structural haplotype evidence bundle",
    )
    structural_haplotype_bundle.add_argument("input", type=str)
    structural_haplotype_bundle.add_argument("--output", required=True)
    structural_haplotype_bundle.add_argument(
        "--format",
        choices=[item.value for item in StructuralHaplotypeBundleFormat],
        default=StructuralHaplotypeBundleFormat.JSON.value,
    )
    structural_haplotype_bundle.add_argument("--bundle-id", default=None)
    structural_haplotype_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C09-C12 bundle for inspection instead of requiring the gate",
    )

    structural_haplotype_lineage = subparsers.add_parser(
        "structural-haplotype-lineage",
        help="build and audit a sanitized C09-C12 source-to-result lineage graph",
    )
    structural_haplotype_lineage.add_argument("input", type=str)
    structural_haplotype_lineage.add_argument("--output", default=None)

    structural_haplotype_pipeline = subparsers.add_parser(
        "run-structural-haplotype-pipeline",
        help="run phased haplotype, allele-aware SV, pangenome projection, and repeat annotation stages",
    )
    structural_haplotype_pipeline.add_argument("input", type=str)
    structural_haplotype_pipeline.add_argument("--output", default=None)

    structural_frontier_fixture = subparsers.add_parser(
        "evaluate-structural-frontier-fixture",
        help="evaluate the public aggregate fixture across Domain 02 C13-C16 frontier operations",
    )
    structural_frontier_fixture.add_argument("input", type=str)
    structural_frontier_fixture.add_argument("--output", default=None)

    structural_frontier_data = subparsers.add_parser(
        "audit-structural-frontier-data",
        help="audit public aggregate C13-C16 sources, contexts, identities, and payload scope",
    )
    structural_frontier_data.add_argument("input", type=str)
    structural_frontier_data.add_argument("--output", default=None)

    structural_frontier_replay = subparsers.add_parser(
        "replay-structural-frontier-fixtures",
        help="replay C13-C16 fixtures with identity, context, source, and evidence floors",
    )
    structural_frontier_replay.add_argument("inputs", nargs="+", type=str)
    structural_frontier_replay.add_argument("--required-context-key", default=None)
    structural_frontier_replay.add_argument("--output", default=None)

    structural_frontier_quality = subparsers.add_parser(
        "structural-frontier-quality-gate",
        help="reconcile C13-C16 fixture, data, replay, scenario, contract, and lineage evidence",
    )
    structural_frontier_quality.add_argument("input", type=str)
    structural_frontier_quality.add_argument("--output", default=None)

    structural_frontier_scenarios = subparsers.add_parser(
        "evaluate-structural-frontier-scenarios",
        help="run independent C13-C16 positive and review state-transition scenarios",
    )
    structural_frontier_scenarios.add_argument("input", type=str)
    structural_frontier_scenarios.add_argument("--output", default=None)

    structural_frontier_contracts = subparsers.add_parser(
        "structural-frontier-contracts",
        help="print the four-operation Domain 02 C13-C16 structural frontier contract registry",
    )
    structural_frontier_contracts.add_argument("--output", default=None)

    structural_frontier_bundle = subparsers.add_parser(
        "build-structural-frontier-bundle",
        help="build a compact JSON, CSV, or Markdown C13-C16 structural frontier evidence bundle",
    )
    structural_frontier_bundle.add_argument("input", type=str)
    structural_frontier_bundle.add_argument("--output", required=True)
    structural_frontier_bundle.add_argument(
        "--format",
        choices=[item.value for item in StructuralFrontierBundleFormat],
        default=StructuralFrontierBundleFormat.JSON.value,
    )
    structural_frontier_bundle.add_argument("--bundle-id", default=None)
    structural_frontier_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C13-C16 bundle for inspection instead of requiring the gate",
    )

    structural_frontier_lineage = subparsers.add_parser(
        "structural-frontier-lineage",
        help="build and audit a sanitized C13-C16 source-to-result lineage graph",
    )
    structural_frontier_lineage.add_argument("input", type=str)
    structural_frontier_lineage.add_argument("--output", default=None)

    structural_frontier_pipeline = subparsers.add_parser(
        "run-structural-frontier-pipeline",
        help="run tandem-repeat, compound-haplotype, breakpoint, and evidence-export stages",
    )
    structural_frontier_pipeline.add_argument("input", type=str)
    structural_frontier_pipeline.add_argument("--output", default=None)

    structural_beta_fixture = subparsers.add_parser(
        "evaluate-structural-beta-fixture",
        help="evaluate the public aggregate fixture across Domain 02 C05-C08 beta operations",
    )
    structural_beta_fixture.add_argument("input", type=str)
    structural_beta_fixture.add_argument("--output", default=None)

    structural_beta_data = subparsers.add_parser(
        "audit-structural-beta-data",
        help="audit C05-C08 public aggregate sources, contexts, identities, and payload scope",
    )
    structural_beta_data.add_argument("input", type=str)
    structural_beta_data.add_argument("--output", default=None)

    structural_beta_replay = subparsers.add_parser(
        "replay-structural-beta-fixtures",
        help="replay C05-C08 fixtures with identity, context, source, and evidence floors",
    )
    structural_beta_replay.add_argument("inputs", nargs="+", type=str)
    structural_beta_replay.add_argument("--required-context-key", default=None)
    structural_beta_replay.add_argument("--output", default=None)

    structural_beta_quality = subparsers.add_parser(
        "structural-beta-quality-gate",
        help="reconcile C05-C08 fixture, data, replay, scenario, contract, and lineage evidence",
    )
    structural_beta_quality.add_argument("input", type=str)
    structural_beta_quality.add_argument("--output", default=None)

    structural_beta_scenarios = subparsers.add_parser(
        "evaluate-structural-beta-scenarios",
        help="run independent C05-C08 positive and review state-transition scenarios",
    )
    structural_beta_scenarios.add_argument("input", type=str)
    structural_beta_scenarios.add_argument("--output", default=None)

    structural_beta_contracts = subparsers.add_parser(
        "structural-beta-contracts",
        help="print the four-operation Domain 02 C05-C08 beta contract registry",
    )
    structural_beta_contracts.add_argument("--output", default=None)

    structural_beta_bundle = subparsers.add_parser(
        "build-structural-beta-bundle",
        help="build a compact JSON, CSV, or Markdown C05-C08 beta evidence bundle",
    )
    structural_beta_bundle.add_argument("input", type=str)
    structural_beta_bundle.add_argument("--output", required=True)
    structural_beta_bundle.add_argument(
        "--format",
        choices=[item.value for item in StructuralBetaBundleFormat],
        default=StructuralBetaBundleFormat.JSON.value,
    )
    structural_beta_bundle.add_argument("--bundle-id", default=None)
    structural_beta_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state beta bundle for inspection instead of requiring the gate",
    )

    structural_beta_lineage = subparsers.add_parser(
        "structural-beta-lineage",
        help="build and audit a sanitized C05-C08 source-to-result lineage graph",
    )
    structural_beta_lineage.add_argument("input", type=str)
    structural_beta_lineage.add_argument("--output", default=None)

    structural_beta_pipeline = subparsers.add_parser(
        "run-structural-beta-pipeline",
        help="run C05-C08 focal, chromothripsis, ecDNA, and enhancer-hijacking stages",
    )
    structural_beta_pipeline.add_argument("input", type=str)
    structural_beta_pipeline.add_argument("--output", default=None)

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

    specimen_frontier_fixture = subparsers.add_parser(
        "evaluate-specimen-frontier-fixture",
        help="evaluate the public aggregate fixture across Domain 03 C01-C04 specimen operations",
    )
    specimen_frontier_fixture.add_argument("input", type=str)
    specimen_frontier_fixture.add_argument("--output", default=None)

    specimen_frontier_data = subparsers.add_parser(
        "audit-specimen-frontier-data",
        help="audit public aggregate C01-C04 sources, contexts, identities, and payload scope",
    )
    specimen_frontier_data.add_argument("input", type=str)
    specimen_frontier_data.add_argument("--output", default=None)

    specimen_frontier_replay = subparsers.add_parser(
        "replay-specimen-frontier-fixtures",
        help="replay C01-C04 fixtures with identity, context, source, and evidence floors",
    )
    specimen_frontier_replay.add_argument("inputs", nargs="+", type=str)
    specimen_frontier_replay.add_argument("--required-context-key", default=None)
    specimen_frontier_replay.add_argument("--output", default=None)

    specimen_frontier_quality = subparsers.add_parser(
        "specimen-frontier-quality-gate",
        help="reconcile C01-C04 fixture, data, replay, scenario, contract, and lineage evidence",
    )
    specimen_frontier_quality.add_argument("input", type=str)
    specimen_frontier_quality.add_argument("--output", default=None)

    specimen_frontier_scenarios = subparsers.add_parser(
        "evaluate-specimen-frontier-scenarios",
        help="run independent C01-C04 positive and review state-transition scenarios",
    )
    specimen_frontier_scenarios.add_argument("input", type=str)
    specimen_frontier_scenarios.add_argument("--output", default=None)

    specimen_frontier_contracts = subparsers.add_parser(
        "specimen-frontier-contracts",
        help="print the four-operation Domain 03 C01-C04 specimen contract registry",
    )
    specimen_frontier_contracts.add_argument("--output", default=None)

    specimen_frontier_bundle = subparsers.add_parser(
        "build-specimen-frontier-bundle",
        help="build a compact JSON, CSV, or Markdown C01-C04 specimen evidence bundle",
    )
    specimen_frontier_bundle.add_argument("input", type=str)
    specimen_frontier_bundle.add_argument("--output", required=True)
    specimen_frontier_bundle.add_argument(
        "--format",
        choices=[item.value for item in SpecimenFrontierBundleFormat],
        default=SpecimenFrontierBundleFormat.JSON.value,
    )
    specimen_frontier_bundle.add_argument("--bundle-id", default=None)
    specimen_frontier_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C01-C04 bundle for inspection instead of requiring the gate",
    )

    specimen_frontier_lineage = subparsers.add_parser(
        "specimen-frontier-lineage",
        help="build and audit a sanitized C01-C04 source-to-result lineage graph",
    )
    specimen_frontier_lineage.add_argument("input", type=str)
    specimen_frontier_lineage.add_argument("--output", default=None)

    specimen_frontier_pipeline = subparsers.add_parser(
        "run-specimen-frontier-pipeline",
        help="run ontology, matched-normal, purity/ploidy, and integrity stages",
    )
    specimen_frontier_pipeline.add_argument("input", type=str)
    specimen_frontier_pipeline.add_argument("--output", default=None)

    specimen_beta_frontier_fixture = subparsers.add_parser(
        "evaluate-specimen-beta-frontier-fixture",
        help="evaluate the public aggregate fixture across Domain 03 C05-C08 variant operations",
    )
    specimen_beta_frontier_fixture.add_argument("input", type=str)
    specimen_beta_frontier_fixture.add_argument("--output", default=None)

    specimen_beta_frontier_data = subparsers.add_parser(
        "audit-specimen-beta-frontier-data",
        help="audit public aggregate C05-C08 sources, contexts, identities, and payload scope",
    )
    specimen_beta_frontier_data.add_argument("input", type=str)
    specimen_beta_frontier_data.add_argument("--output", default=None)

    specimen_beta_frontier_replay = subparsers.add_parser(
        "replay-specimen-beta-frontier-fixtures",
        help="replay C05-C08 fixtures with identity, context, source, and evidence floors",
    )
    specimen_beta_frontier_replay.add_argument("inputs", nargs="+", type=str)
    specimen_beta_frontier_replay.add_argument("--required-context-key", default=None)
    specimen_beta_frontier_replay.add_argument("--output", default=None)

    specimen_beta_frontier_quality = subparsers.add_parser(
        "specimen-beta-frontier-quality-gate",
        help="reconcile C05-C08 fixture, data, replay, scenario, contract, and lineage evidence",
    )
    specimen_beta_frontier_quality.add_argument("input", type=str)
    specimen_beta_frontier_quality.add_argument("--output", default=None)

    specimen_beta_frontier_scenarios = subparsers.add_parser(
        "evaluate-specimen-beta-frontier-scenarios",
        help="run independent C05-C08 positive and review state-transition scenarios",
    )
    specimen_beta_frontier_scenarios.add_argument("input", type=str)
    specimen_beta_frontier_scenarios.add_argument("--output", default=None)

    specimen_beta_frontier_contracts = subparsers.add_parser(
        "specimen-beta-frontier-contracts",
        help="print the four-operation Domain 03 C05-C08 variant contract registry",
    )
    specimen_beta_frontier_contracts.add_argument("--output", default=None)

    specimen_beta_frontier_bundle = subparsers.add_parser(
        "build-specimen-beta-frontier-bundle",
        help="build a compact JSON, CSV, or Markdown C05-C08 variant evidence bundle",
    )
    specimen_beta_frontier_bundle.add_argument("input", type=str)
    specimen_beta_frontier_bundle.add_argument("--output", required=True)
    specimen_beta_frontier_bundle.add_argument(
        "--format",
        choices=[item.value for item in SpecimenBetaFrontierBundleFormat],
        default=SpecimenBetaFrontierBundleFormat.JSON.value,
    )
    specimen_beta_frontier_bundle.add_argument("--bundle-id", default=None)
    specimen_beta_frontier_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C05-C08 bundle for inspection instead of requiring the gate",
    )

    specimen_beta_frontier_lineage = subparsers.add_parser(
        "specimen-beta-frontier-lineage",
        help="build and audit a sanitized C05-C08 source-to-result lineage graph",
    )
    specimen_beta_frontier_lineage.add_argument("input", type=str)
    specimen_beta_frontier_lineage.add_argument("--output", default=None)

    specimen_beta_frontier_pipeline = subparsers.add_parser(
        "run-specimen-beta-frontier-pipeline",
        help="run origin, mosaicism, CCF, and relative subclone stages",
    )
    specimen_beta_frontier_pipeline.add_argument("input", type=str)
    specimen_beta_frontier_pipeline.add_argument("--output", default=None)

    specimen_lineage_fixture = subparsers.add_parser(
        "evaluate-specimen-lineage-fixture",
        help="evaluate the public aggregate fixture across Domain 03 C09-C12 specimen context operations",
    )
    specimen_lineage_fixture.add_argument("input", type=str)
    specimen_lineage_fixture.add_argument("--output", default=None)

    specimen_lineage_data = subparsers.add_parser(
        "audit-specimen-lineage-data",
        help="audit public aggregate C09-C12 specimen lineage sources, context, and payload scope",
    )
    specimen_lineage_data.add_argument("input", type=str)
    specimen_lineage_data.add_argument("--output", default=None)

    specimen_lineage_replay = subparsers.add_parser(
        "replay-specimen-lineage-fixtures",
        help="replay C09-C12 specimen lineage fixtures with identity, context, and evidence floors",
    )
    specimen_lineage_replay.add_argument("inputs", nargs="+", type=str)
    specimen_lineage_replay.add_argument("--required-context-key", default=None)
    specimen_lineage_replay.add_argument("--output", default=None)

    specimen_lineage_quality = subparsers.add_parser(
        "specimen-lineage-quality-gate",
        help="reconcile C09-C12 specimen fixture, data, scenario, contract, and lineage evidence",
    )
    specimen_lineage_quality.add_argument("input", type=str)
    specimen_lineage_quality.add_argument("--output", default=None)

    specimen_lineage_scenarios = subparsers.add_parser(
        "evaluate-specimen-lineage-scenarios",
        help="run independent C09-C12 specimen lineage positive and review state scenarios",
    )
    specimen_lineage_scenarios.add_argument("input", type=str)
    specimen_lineage_scenarios.add_argument("--output", default=None)

    specimen_lineage_contracts = subparsers.add_parser(
        "specimen-lineage-contracts",
        help="print the four-operation Domain 03 C09-C12 specimen lineage contract registry",
    )
    specimen_lineage_contracts.add_argument("--output", default=None)

    specimen_lineage_bundle = subparsers.add_parser(
        "build-specimen-lineage-bundle",
        help="build a compact JSON, CSV, or Markdown C09-C12 specimen lineage evidence bundle",
    )
    specimen_lineage_bundle.add_argument("input", type=str)
    specimen_lineage_bundle.add_argument("--output", required=True)
    specimen_lineage_bundle.add_argument(
        "--format",
        choices=[item.value for item in SpecimenLineageBundleFormat],
        default=SpecimenLineageBundleFormat.JSON.value,
    )
    specimen_lineage_bundle.add_argument("--bundle-id", default=None)
    specimen_lineage_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C09-C12 bundle for inspection instead of requiring the gate",
    )

    specimen_lineage_graph = subparsers.add_parser(
        "specimen-lineage-lineage",
        help="build and audit a sanitized C09-C12 specimen source-to-result lineage graph",
    )
    specimen_lineage_graph.add_argument("input", type=str)
    specimen_lineage_graph.add_argument("--output", default=None)

    specimen_lineage_reconciliation = subparsers.add_parser(
        "specimen-lineage-reconciliation",
        help="reconcile C09-C12 fixture records with sanitized execution receipt addresses",
    )
    specimen_lineage_reconciliation.add_argument("input", type=str)
    specimen_lineage_reconciliation.add_argument("--output", default=None)

    specimen_lineage_pipeline = subparsers.add_parser(
        "run-specimen-lineage-pipeline",
        help="run region lineage, longitudinal linking, phase mapping, and treatment context stages",
    )
    specimen_lineage_pipeline.add_argument("input", type=str)
    specimen_lineage_pipeline.add_argument("--output", default=None)

    specimen_preanalytic_fixture = subparsers.add_parser(
        "evaluate-specimen-preanalytic-fixture",
        help="evaluate the public aggregate fixture across Domain 03 C13-C16 specimen operations",
    )
    specimen_preanalytic_fixture.add_argument("input", type=str)
    specimen_preanalytic_fixture.add_argument("--output", default=None)

    specimen_preanalytic_data = subparsers.add_parser(
        "audit-specimen-preanalytic-data",
        help="audit public aggregate C13-C16 source, context, role, and payload boundaries",
    )
    specimen_preanalytic_data.add_argument("input", type=str)
    specimen_preanalytic_data.add_argument("--output", default=None)

    specimen_preanalytic_replay = subparsers.add_parser(
        "replay-specimen-preanalytic-fixtures",
        help="replay C13-C16 specimen fixtures with identity, context, and evidence floors",
    )
    specimen_preanalytic_replay.add_argument("inputs", nargs="+", type=str)
    specimen_preanalytic_replay.add_argument("--required-context-key", default=None)
    specimen_preanalytic_replay.add_argument("--output", default=None)

    specimen_preanalytic_quality = subparsers.add_parser(
        "specimen-preanalytic-quality-gate",
        help=(
            "reconcile C13-C16 specimen data, fixture, scenario, contract, graph, "
            "bundle, and runtime evidence"
        ),
    )
    specimen_preanalytic_quality.add_argument("input", type=str)
    specimen_preanalytic_quality.add_argument("--output", default=None)

    specimen_preanalytic_scenarios = subparsers.add_parser(
        "evaluate-specimen-preanalytic-scenarios",
        help="run C13-C16 specimen positive and review state scenarios",
    )
    specimen_preanalytic_scenarios.add_argument("input", type=str)
    specimen_preanalytic_scenarios.add_argument("--output", default=None)

    specimen_preanalytic_contracts = subparsers.add_parser(
        "specimen-preanalytic-contracts",
        help="print the four-operation Domain 03 C13-C16 specimen contract registry",
    )
    specimen_preanalytic_contracts.add_argument("--output", default=None)

    specimen_preanalytic_bundle = subparsers.add_parser(
        "build-specimen-preanalytic-bundle",
        help="build a compact JSON, CSV, or Markdown C13-C16 specimen evidence bundle",
    )
    specimen_preanalytic_bundle.add_argument("input", type=str)
    specimen_preanalytic_bundle.add_argument("--output", required=True)
    specimen_preanalytic_bundle.add_argument(
        "--format",
        choices=[item.value for item in SpecimenPreanalyticBundleFormat],
        default=SpecimenPreanalyticBundleFormat.JSON.value,
    )
    specimen_preanalytic_bundle.add_argument("--bundle-id", default=None)
    specimen_preanalytic_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="write a review-state C13-C16 bundle for inspection",
    )

    specimen_preanalytic_graph = subparsers.add_parser(
        "specimen-preanalytic-lineage",
        help="build and audit a sanitized C13-C16 specimen source-to-result graph",
    )
    specimen_preanalytic_graph.add_argument("input", type=str)
    specimen_preanalytic_graph.add_argument("--output", default=None)

    specimen_preanalytic_reconciliation = subparsers.add_parser(
        "specimen-preanalytic-reconciliation",
        help="reconcile C13-C16 fixture records with sanitized execution receipts",
    )
    specimen_preanalytic_reconciliation.add_argument("input", type=str)
    specimen_preanalytic_reconciliation.add_argument("--output", default=None)

    specimen_preanalytic_pipeline = subparsers.add_parser(
        "run-specimen-preanalytic-pipeline",
        help="run C13 quality, C14 lineage, C15 identity, and C16 publication stages",
    )
    specimen_preanalytic_pipeline.add_argument("input", type=str)
    specimen_preanalytic_pipeline.add_argument("--output", default=None)

    reference_coordinate_fixture = subparsers.add_parser(
        "evaluate-reference-coordinate-fixture",
        help="evaluate the public aggregate fixture across Domain 04 C01-C04 coordinate operations",
    )
    reference_coordinate_fixture.add_argument("input", type=str)
    reference_coordinate_fixture.add_argument("--output", default=None)

    reference_coordinate_data = subparsers.add_parser(
        "audit-reference-coordinate-data",
        help="audit public C01-C04 assembly, liftover, ambiguity, and pangenome boundaries",
    )
    reference_coordinate_data.add_argument("input", type=str)
    reference_coordinate_data.add_argument("--output", default=None)

    reference_coordinate_replay = subparsers.add_parser(
        "replay-reference-coordinate-fixtures",
        help="replay C01-C04 coordinate fixtures with identity, context, and evidence floors",
    )
    reference_coordinate_replay.add_argument("input", type=str)
    reference_coordinate_replay.add_argument("--output", default=None)

    reference_coordinate_quality = subparsers.add_parser(
        "reference-coordinate-quality-gate",
        help=(
            "reconcile C01-C04 public data, fixture, scenarios, contracts, graph, "
            "bundle, and runtime evidence"
        ),
    )
    reference_coordinate_quality.add_argument("input", type=str)
    reference_coordinate_quality.add_argument("--output", default=None)

    reference_coordinate_scenarios = subparsers.add_parser(
        "evaluate-reference-coordinate-scenarios",
        help="run C01-C04 coordinate positive and review state scenarios",
    )
    reference_coordinate_scenarios.add_argument("input", type=str)
    reference_coordinate_scenarios.add_argument("--output", default=None)

    reference_coordinate_contracts = subparsers.add_parser(
        "reference-coordinate-contracts",
        help="print the four-operation Domain 04 reference-coordinate contract registry",
    )
    reference_coordinate_contracts.add_argument("--output", default=None)

    reference_coordinate_bundle = subparsers.add_parser(
        "build-reference-coordinate-bundle",
        help="build a JSON, CSV, or Markdown C01-C04 coordinate evidence bundle",
    )
    reference_coordinate_bundle.add_argument("input", type=str)
    reference_coordinate_bundle.add_argument("--output", required=True)
    reference_coordinate_bundle.add_argument(
        "--format",
        choices=[item.value for item in ReferenceCoordinateBundleFormat],
        default=ReferenceCoordinateBundleFormat.JSON.value,
    )
    reference_coordinate_bundle.add_argument(
        "--accepted-only",
        action="store_true",
        help="include only supported positive operation receipts",
    )
    reference_coordinate_bundle.add_argument(
        "--allow-review",
        action="store_true",
        help="retain review controls in a verification bundle",
    )

    reference_coordinate_graph = subparsers.add_parser(
        "reference-coordinate-lineage",
        help="build and audit the sanitized C01-C04 coordinate source-to-result graph",
    )
    reference_coordinate_graph.add_argument("input", type=str)
    reference_coordinate_graph.add_argument("--output", default=None)

    reference_coordinate_reconciliation = subparsers.add_parser(
        "reference-coordinate-reconciliation",
        help="reconcile C01-C04 fixture records with coordinate receipt and graph addresses",
    )
    reference_coordinate_reconciliation.add_argument("input", type=str)
    reference_coordinate_reconciliation.add_argument("--output", default=None)

    reference_coordinate_pipeline = subparsers.add_parser(
        "run-reference-coordinate-pipeline",
        help="run C01 registry, C02 liftover, C03 ambiguity, and C04 pangenome stages",
    )
    reference_coordinate_pipeline.add_argument("input", type=str)
    reference_coordinate_pipeline.add_argument("--output", default=None)

    reference_annotation_fixture = subparsers.add_parser(
        "evaluate-reference-annotation-fixture",
        help="evaluate the public aggregate fixture across Domain 04 C05-C08 annotation operations",
    )
    reference_annotation_fixture.add_argument("input", type=str)
    reference_annotation_fixture.add_argument("--output", default=None)

    reference_annotation_data = subparsers.add_parser(
        "audit-reference-annotation-data",
        help="audit public C05-C08 transcript and ontology source boundaries",
    )
    reference_annotation_data.add_argument("input", type=str)
    reference_annotation_data.add_argument("--output", default=None)

    reference_annotation_replay = subparsers.add_parser(
        "replay-reference-annotation-fixtures",
        help="replay C05-C08 annotation fixtures with identity, context, and evidence floors",
    )
    reference_annotation_replay.add_argument("input", type=str)
    reference_annotation_replay.add_argument("--output", default=None)

    reference_annotation_quality = subparsers.add_parser(
        "reference-annotation-quality-gate",
        help="reconcile C05-C08 public data, fixture, scenarios, contracts, graph, and bundle evidence",
    )
    reference_annotation_quality.add_argument("input", type=str)
    reference_annotation_quality.add_argument("--output", default=None)

    reference_annotation_scenarios = subparsers.add_parser(
        "evaluate-reference-annotation-scenarios",
        help="run C05-C08 annotation positive and review state scenarios",
    )
    reference_annotation_scenarios.add_argument("input", type=str)
    reference_annotation_scenarios.add_argument("--output", default=None)

    reference_annotation_contracts = subparsers.add_parser(
        "reference-annotation-contracts",
        help="print the four-operation Domain 04 reference-annotation contract registry",
    )
    reference_annotation_contracts.add_argument("--output", default=None)

    reference_annotation_bundle = subparsers.add_parser(
        "build-reference-annotation-bundle",
        help="build a JSON, CSV, or Markdown C05-C08 annotation evidence bundle",
    )
    reference_annotation_bundle.add_argument("input", type=str)
    reference_annotation_bundle.add_argument("--output", required=True)
    reference_annotation_bundle.add_argument(
        "--format",
        choices=[item.value for item in ReferenceAnnotationBundleFormat],
        default=ReferenceAnnotationBundleFormat.JSON.value,
    )
    reference_annotation_bundle.add_argument(
        "--accepted-only",
        action="store_true",
        help="include only supported positive operation receipts",
    )

    reference_annotation_graph = subparsers.add_parser(
        "reference-annotation-lineage",
        help="build and audit the sanitized C05-C08 annotation source-to-result graph",
    )
    reference_annotation_graph.add_argument("input", type=str)
    reference_annotation_graph.add_argument("--output", default=None)

    reference_annotation_reconciliation = subparsers.add_parser(
        "reference-annotation-reconciliation",
        help="reconcile C05-C08 fixture records with annotation receipts, bundle, and graph",
    )
    reference_annotation_reconciliation.add_argument("input", type=str)
    reference_annotation_reconciliation.add_argument("--output", default=None)

    reference_annotation_pipeline = subparsers.add_parser(
        "run-reference-annotation-pipeline",
        help="run C05 GENCODE, C06 MANE, C07 regulatory, and C08 disease stages",
    )
    reference_annotation_pipeline.add_argument("input", type=str)
    reference_annotation_pipeline.add_argument("--output", default=None)

    reference_annotation_release = subparsers.add_parser(
        "build-reference-annotation-release",
        help="build and verify the C05-C08 annotation publication manifest",
    )
    reference_annotation_release.add_argument("input", type=str)
    reference_annotation_release.add_argument("--output", required=True)

    reference_governance_fixture = subparsers.add_parser(
        "evaluate-reference-governance-fixture",
        help="evaluate the public aggregate fixture across Domain 04 C09-C12 governance operations",
    )
    reference_governance_fixture.add_argument("input", type=str)
    reference_governance_fixture.add_argument("--output", default=None)

    reference_governance_data = subparsers.add_parser(
        "audit-reference-governance-data",
        help="audit public C09-C12 governance source boundaries and payload scope",
    )
    reference_governance_data.add_argument("input", type=str)
    reference_governance_data.add_argument("--output", default=None)

    reference_governance_replay = subparsers.add_parser(
        "replay-reference-governance-fixtures",
        help="replay C09-C12 governance fixtures with identity, context, and state floors",
    )
    reference_governance_replay.add_argument("input", type=str)
    reference_governance_replay.add_argument("--output", default=None)

    reference_governance_quality = subparsers.add_parser(
        "reference-governance-quality-gate",
        help="reconcile C09-C12 public data, execution, scenarios, lineage, and release bundle",
    )
    reference_governance_quality.add_argument("input", type=str)
    reference_governance_quality.add_argument("--output", default=None)

    reference_governance_scenarios = subparsers.add_parser(
        "evaluate-reference-governance-scenarios",
        help="run C09-C12 governance support, ambiguity, drift, and missing-evidence scenarios",
    )
    reference_governance_scenarios.add_argument("input", type=str)
    reference_governance_scenarios.add_argument("--output", default=None)

    reference_governance_contracts = subparsers.add_parser(
        "reference-governance-contracts",
        help="print the four-operation Domain 04 C09-C12 governance contract registry",
    )
    reference_governance_contracts.add_argument("--output", default=None)

    reference_governance_metrics = subparsers.add_parser(
        "reference-governance-metrics",
        help="render C09-C12 governance coverage, issue, and sanitization metrics",
    )
    reference_governance_metrics.add_argument("input", type=str)
    reference_governance_metrics.add_argument("--output", default=None)

    reference_governance_bundle = subparsers.add_parser(
        "build-reference-governance-bundle",
        help="build a compact JSON, CSV, or Markdown C09-C12 governance evidence bundle",
    )
    reference_governance_bundle.add_argument("input", type=str)
    reference_governance_bundle.add_argument("--output", required=True)
    reference_governance_bundle.add_argument(
        "--format",
        choices=[item.value for item in ReferenceGovernanceBundleFormat],
        default=ReferenceGovernanceBundleFormat.JSON.value,
    )
    reference_governance_bundle.add_argument("--accepted-only", action="store_true")

    reference_governance_graph = subparsers.add_parser(
        "reference-governance-lineage",
        help="build and audit the sanitized C09-C12 governance source-to-result graph",
    )
    reference_governance_graph.add_argument("input", type=str)
    reference_governance_graph.add_argument("--output", default=None)

    reference_governance_reconciliation = subparsers.add_parser(
        "reference-governance-reconciliation",
        help="reconcile C09-C12 fixture, data, replay, scenario, lineage, and bundle views",
    )
    reference_governance_reconciliation.add_argument("input", type=str)
    reference_governance_reconciliation.add_argument("--output", default=None)

    reference_governance_pipeline = subparsers.add_parser(
        "run-reference-governance-pipeline",
        help="run C09 alias, C10 frequency, C11 snapshot, and C12 license stages",
    )
    reference_governance_pipeline.add_argument("input", type=str)
    reference_governance_pipeline.add_argument("--output", default=None)

    reference_governance_release = subparsers.add_parser(
        "build-reference-governance-release",
        help="build and verify the C09-C12 governance publication manifest",
    )
    reference_governance_release.add_argument("input", type=str)
    reference_governance_release.add_argument("--output", required=True)

    regulatory_atlas_fixture = subparsers.add_parser(
        "evaluate-regulatory-atlas-fixture",
        help="evaluate the public aggregate cCRE fixture across Domain 05 C01-C04 profiles",
    )
    regulatory_atlas_fixture.add_argument("input", type=str)
    regulatory_atlas_fixture.add_argument("--output", default=None)

    regulatory_atlas_data = subparsers.add_parser(
        "audit-regulatory-atlas-data",
        help="audit public ENCODE SCREEN-shaped C01-C04 source boundaries and payload scope",
    )
    regulatory_atlas_data.add_argument("input", type=str)
    regulatory_atlas_data.add_argument("--output", default=None)

    regulatory_atlas_replay = subparsers.add_parser(
        "replay-regulatory-atlas-fixtures",
        help="replay C01-C04 cCRE profiles with identity, context, and state floors",
    )
    regulatory_atlas_replay.add_argument("input", type=str)
    regulatory_atlas_replay.add_argument("--output", default=None)

    regulatory_atlas_quality = subparsers.add_parser(
        "regulatory-atlas-quality-gate",
        help="run the integrated C01-C04 public-data and publication quality gate",
    )
    regulatory_atlas_quality.add_argument("input", type=str)
    regulatory_atlas_quality.add_argument("--output", default=None)

    regulatory_atlas_scenarios = subparsers.add_parser(
        "evaluate-regulatory-atlas-scenarios",
        help="run C01-C04 parse, context mismatch, absence, and ambiguity scenarios",
    )
    regulatory_atlas_scenarios.add_argument("input", type=str)
    regulatory_atlas_scenarios.add_argument("--output", default=None)

    regulatory_atlas_contracts = subparsers.add_parser(
        "regulatory-atlas-contracts",
        help="print the four-operation Domain 05 C01-C04 contract registry",
    )
    regulatory_atlas_contracts.add_argument("--output", default=None)

    regulatory_atlas_metrics = subparsers.add_parser(
        "regulatory-atlas-metrics",
        help="render C01-C04 cCRE coverage, issue, and sanitization metrics",
    )
    regulatory_atlas_metrics.add_argument("input", type=str)
    regulatory_atlas_metrics.add_argument("--output", default=None)

    regulatory_atlas_bundle = subparsers.add_parser(
        "build-regulatory-atlas-bundle",
        help="build a compact JSON, CSV, or Markdown C01-C04 evidence bundle",
    )
    regulatory_atlas_bundle.add_argument("input", type=str)
    regulatory_atlas_bundle.add_argument("--output", required=True)
    regulatory_atlas_bundle.add_argument(
        "--format",
        choices=[item.value for item in RegulatoryAtlasBundleFormat],
        default=RegulatoryAtlasBundleFormat.JSON.value,
    )
    regulatory_atlas_bundle.add_argument("--accepted-only", action="store_true")

    regulatory_atlas_graph = subparsers.add_parser(
        "regulatory-atlas-lineage",
        help="build and audit the sanitized C01-C04 source-to-result graph",
    )
    regulatory_atlas_graph.add_argument("input", type=str)
    regulatory_atlas_graph.add_argument("--output", default=None)

    regulatory_atlas_reconciliation = subparsers.add_parser(
        "regulatory-atlas-reconciliation",
        help="reconcile C01-C04 fixture, data, replay, scenario, and lineage views",
    )
    regulatory_atlas_reconciliation.add_argument("input", type=str)
    regulatory_atlas_reconciliation.add_argument("--output", default=None)

    regulatory_atlas_pipeline = subparsers.add_parser(
        "run-regulatory-atlas-pipeline",
        help="run the complete C01-C04 regulatory atlas pipeline",
    )
    regulatory_atlas_pipeline.add_argument("input", type=str)
    regulatory_atlas_pipeline.add_argument("--output", default=None)

    regulatory_atlas_release = subparsers.add_parser(
        "build-regulatory-atlas-release",
        help="build and verify the C01-C04 regulatory atlas publication manifest",
    )
    regulatory_atlas_release.add_argument("input", type=str)
    regulatory_atlas_release.add_argument("--output", required=True)

    molecular_atlas_fixture = subparsers.add_parser(
        "evaluate-molecular-atlas-fixture",
        help="evaluate the public aggregate C05-C08 molecular-state and histone fixture",
    )
    molecular_atlas_fixture.add_argument("input", type=str)
    molecular_atlas_fixture.add_argument("--output", default=None)

    molecular_atlas_data = subparsers.add_parser(
        "audit-molecular-atlas-data",
        help="audit public C05-C08 molecular-state and histone source boundaries",
    )
    molecular_atlas_data.add_argument("input", type=str)
    molecular_atlas_data.add_argument("--output", default=None)

    molecular_atlas_replay = subparsers.add_parser(
        "replay-molecular-atlas-fixtures",
        help="replay C05-C08 state separation and histone harmonization fixtures",
    )
    molecular_atlas_replay.add_argument("input", type=str)
    molecular_atlas_replay.add_argument("--output", default=None)

    molecular_atlas_quality = subparsers.add_parser(
        "molecular-atlas-quality-gate",
        help="run the integrated C05-C08 molecular atlas quality gate",
    )
    molecular_atlas_quality.add_argument("input", type=str)
    molecular_atlas_quality.add_argument("--output", default=None)

    molecular_atlas_scenarios = subparsers.add_parser(
        "evaluate-molecular-atlas-scenarios",
        help="run C05-C08 state, context, absence, ambiguity, and replicate scenarios",
    )
    molecular_atlas_scenarios.add_argument("input", type=str)
    molecular_atlas_scenarios.add_argument("--output", default=None)

    molecular_atlas_contracts = subparsers.add_parser(
        "molecular-atlas-contracts",
        help="print the four-operation Domain 05 C05-C08 contract registry",
    )
    molecular_atlas_contracts.add_argument("--output", default=None)

    molecular_atlas_metrics = subparsers.add_parser(
        "molecular-atlas-metrics",
        help="render C05-C08 molecular-state and histone coverage metrics",
    )
    molecular_atlas_metrics.add_argument("input", type=str)
    molecular_atlas_metrics.add_argument("--output", default=None)

    molecular_atlas_bundle = subparsers.add_parser(
        "build-molecular-atlas-bundle",
        help="build a compact JSON, CSV, or Markdown C05-C08 evidence bundle",
    )
    molecular_atlas_bundle.add_argument("input", type=str)
    molecular_atlas_bundle.add_argument("--output", required=True)
    molecular_atlas_bundle.add_argument(
        "--format",
        choices=[item.value for item in MolecularAtlasBundleFormat],
        default=MolecularAtlasBundleFormat.JSON.value,
    )
    molecular_atlas_bundle.add_argument("--accepted-only", action="store_true")

    molecular_atlas_graph = subparsers.add_parser(
        "molecular-atlas-lineage",
        help="build and audit the sanitized C05-C08 source-to-result graph",
    )
    molecular_atlas_graph.add_argument("input", type=str)
    molecular_atlas_graph.add_argument("--output", default=None)

    molecular_atlas_reconciliation = subparsers.add_parser(
        "molecular-atlas-reconciliation",
        help="reconcile C05-C08 fixture, data, replay, scenario, and lineage views",
    )
    molecular_atlas_reconciliation.add_argument("input", type=str)
    molecular_atlas_reconciliation.add_argument("--output", default=None)

    molecular_atlas_pipeline = subparsers.add_parser(
        "run-molecular-atlas-pipeline",
        help="run the complete C05-C08 molecular atlas pipeline",
    )
    molecular_atlas_pipeline.add_argument("input", type=str)
    molecular_atlas_pipeline.add_argument("--output", default=None)

    molecular_atlas_release = subparsers.add_parser(
        "build-molecular-atlas-release",
        help="build and verify the C05-C08 molecular atlas publication manifest",
    )
    molecular_atlas_release.add_argument("input", type=str)
    molecular_atlas_release.add_argument("--output", required=True)

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

    alpha_evidence_evaluate = subparsers.add_parser(
        "evaluate-atlas-alpha-evidence",
        help="evaluate the public aggregate C09-C12 atlas-alpha fixture",
    )
    alpha_evidence_evaluate.add_argument("input", nargs="?", default=None)
    alpha_evidence_evaluate.add_argument("--output", default=None)

    alpha_evidence_audit = subparsers.add_parser(
        "audit-atlas-alpha-evidence-data",
        help="audit C09-C12 public source closure and aggregate scope",
    )
    alpha_evidence_audit.add_argument("input", nargs="?", default=None)
    alpha_evidence_audit.add_argument("--output", default=None)

    alpha_evidence_replay = subparsers.add_parser(
        "replay-atlas-alpha-evidence",
        help="replay C09-C12 states, issues, and receipt addresses",
    )
    alpha_evidence_replay.add_argument("input", nargs="?", default=None)
    alpha_evidence_replay.add_argument("--output", default=None)

    alpha_evidence_quality = subparsers.add_parser(
        "atlas-alpha-evidence-quality-gate",
        help="run the complete C09-C12 evidence quality gate",
    )
    alpha_evidence_quality.add_argument("input", nargs="?", default=None)
    alpha_evidence_quality.add_argument("--output", default=None)

    alpha_evidence_scenarios = subparsers.add_parser(
        "evaluate-atlas-alpha-evidence-scenarios",
        help="evaluate positive and review scenario floors for C09-C12",
    )
    alpha_evidence_scenarios.add_argument("input", nargs="?", default=None)
    alpha_evidence_scenarios.add_argument("--output", default=None)

    alpha_evidence_contracts = subparsers.add_parser(
        "atlas-alpha-evidence-contracts",
        help="emit typed C09-C12 contracts",
    )
    alpha_evidence_contracts.add_argument("--output", default=None)

    alpha_evidence_schema = subparsers.add_parser(
        "atlas-alpha-evidence-schema",
        help="emit or validate C09-C12 operation schemas",
    )
    alpha_evidence_schema.add_argument("input", nargs="?", default=None)
    alpha_evidence_schema.add_argument("--output", default=None)

    alpha_evidence_metrics = subparsers.add_parser(
        "atlas-alpha-evidence-metrics",
        help="emit C09-C12 operational metrics",
    )
    alpha_evidence_metrics.add_argument("input", nargs="?", default=None)
    alpha_evidence_metrics.add_argument("--output", default=None)

    alpha_evidence_bundle = subparsers.add_parser(
        "build-atlas-alpha-evidence-bundle",
        help="build the serialized C09-C12 evidence bundle",
    )
    alpha_evidence_bundle.add_argument("input", nargs="?", default=None)
    alpha_evidence_bundle.add_argument("--output", default=None)

    alpha_evidence_lineage = subparsers.add_parser(
        "atlas-alpha-evidence-lineage",
        help="emit C09-C12 source-to-receipt lineage",
    )
    alpha_evidence_lineage.add_argument("input", nargs="?", default=None)
    alpha_evidence_lineage.add_argument("--output", default=None)

    alpha_evidence_reconciliation = subparsers.add_parser(
        "atlas-alpha-evidence-reconciliation",
        help="reconcile C09-C12 expected and observed states",
    )
    alpha_evidence_reconciliation.add_argument("input", nargs="?", default=None)
    alpha_evidence_reconciliation.add_argument("--output", default=None)

    alpha_evidence_pipeline = subparsers.add_parser(
        "run-atlas-alpha-evidence-pipeline",
        help="run the C09-C12 quality-gated public aggregate pipeline",
    )
    alpha_evidence_pipeline.add_argument("input", nargs="?", default=None)
    alpha_evidence_pipeline.add_argument("--run-id", default="atlas-alpha-cli")
    alpha_evidence_pipeline.add_argument("--context-key", default=None)
    alpha_evidence_pipeline.add_argument("--fail-on-review", action="store_true")
    alpha_evidence_pipeline.add_argument("--output", default=None)

    alpha_evidence_release = subparsers.add_parser(
        "build-atlas-alpha-evidence-release",
        help="build a C09-C12 release manifest after the quality gate",
    )
    alpha_evidence_release.add_argument("input", nargs="?", default=None)
    alpha_evidence_release.add_argument("--run-id", default="atlas-alpha-release")
    alpha_evidence_release.add_argument("--output", default=None)

    alpha_evidence_view = subparsers.add_parser(
        "atlas-alpha-evidence-review-view",
        help="emit the sanitized C09-C12 review queue and source matrix",
    )
    alpha_evidence_view.add_argument("input", nargs="?", default=None)
    alpha_evidence_view.add_argument("--output", default=None)

    alpha_evidence_trace = subparsers.add_parser(
        "atlas-alpha-evidence-trace",
        help="emit the nine-stage C09-C12 runtime trace",
    )
    alpha_evidence_trace.add_argument("input", nargs="?", default=None)
    alpha_evidence_trace.add_argument("--run-id", default="atlas-alpha-trace")
    alpha_evidence_trace.add_argument("--output", default=None)

    alpha_evidence_receipts_csv = subparsers.add_parser(
        "export-atlas-alpha-evidence-receipts-csv",
        help="export sanitized C09-C12 receipts as CSV",
    )
    alpha_evidence_receipts_csv.add_argument("input", nargs="?", default=None)
    alpha_evidence_receipts_csv.add_argument("--output", default=None)

    alpha_evidence_review_csv = subparsers.add_parser(
        "export-atlas-alpha-evidence-review-csv",
        help="export the C09-C12 review queue as CSV",
    )
    alpha_evidence_review_csv.add_argument("input", nargs="?", default=None)
    alpha_evidence_review_csv.add_argument("--output", default=None)

    alpha_evidence_review_md = subparsers.add_parser(
        "export-atlas-alpha-evidence-review-markdown",
        help="export the C09-C12 review queue as Markdown",
    )
    alpha_evidence_review_md.add_argument("input", nargs="?", default=None)
    alpha_evidence_review_md.add_argument("--output", default=None)

    alpha_evidence_metrics_csv = subparsers.add_parser(
        "export-atlas-alpha-evidence-metrics-csv",
        help="export C09-C12 operation metrics as CSV",
    )
    alpha_evidence_metrics_csv.add_argument("input", nargs="?", default=None)
    alpha_evidence_metrics_csv.add_argument("--output", default=None)

    frontier_atlas_evaluate = subparsers.add_parser(
        "evaluate-frontier-atlas-fixture",
        help="evaluate the public C13-C16 frontier atlas fixture and controls",
    )
    frontier_atlas_evaluate.add_argument("input", nargs="?", default=None)
    frontier_atlas_evaluate.add_argument("--output", default=None)

    frontier_atlas_audit = subparsers.add_parser(
        "audit-frontier-atlas-data",
        help="audit C13-C16 source receipts and aggregate data boundaries",
    )
    frontier_atlas_audit.add_argument("input", nargs="?", default=None)
    frontier_atlas_audit.add_argument("--output", default=None)

    frontier_atlas_replay = subparsers.add_parser(
        "replay-frontier-atlas",
        help="replay C13-C16 states, issues, and content addresses",
    )
    frontier_atlas_replay.add_argument("input", nargs="?", default=None)
    frontier_atlas_replay.add_argument("--output", default=None)

    frontier_atlas_quality = subparsers.add_parser(
        "frontier-atlas-quality-gate",
        help="run the complete C13-C16 frontier atlas quality gate",
    )
    frontier_atlas_quality.add_argument("input", nargs="?", default=None)
    frontier_atlas_quality.add_argument("--output", default=None)

    frontier_atlas_scenarios = subparsers.add_parser(
        "evaluate-frontier-atlas-scenarios",
        help="evaluate C13-C16 positive and negative control scenarios",
    )
    frontier_atlas_scenarios.add_argument("input", nargs="?", default=None)
    frontier_atlas_scenarios.add_argument("--output", default=None)

    frontier_atlas_policy = subparsers.add_parser(
        "frontier-atlas-policy",
        help="evaluate C13-C16 state and issue policy rules",
    )
    frontier_atlas_policy.add_argument("input", nargs="?", default=None)
    frontier_atlas_policy.add_argument("--output", default=None)

    frontier_atlas_contracts = subparsers.add_parser(
        "frontier-atlas-contracts",
        help="emit typed C13-C16 frontier atlas contracts",
    )
    frontier_atlas_contracts.add_argument("--output", default=None)

    frontier_atlas_schema = subparsers.add_parser(
        "frontier-atlas-schema",
        help="emit or validate C13-C16 frontier atlas schemas",
    )
    frontier_atlas_schema.add_argument("input", nargs="?", default=None)
    frontier_atlas_schema.add_argument("--output", default=None)

    frontier_atlas_metrics = subparsers.add_parser(
        "frontier-atlas-metrics",
        help="emit C13-C16 frontier atlas operational metrics",
    )
    frontier_atlas_metrics.add_argument("input", nargs="?", default=None)
    frontier_atlas_metrics.add_argument("--output", default=None)

    frontier_atlas_bundle = subparsers.add_parser(
        "build-frontier-atlas-bundle",
        help="build the serialized C13-C16 frontier atlas bundle",
    )
    frontier_atlas_bundle.add_argument("input", nargs="?", default=None)
    frontier_atlas_bundle.add_argument("--output", default=None)

    frontier_atlas_lineage = subparsers.add_parser(
        "frontier-atlas-lineage",
        help="emit C13-C16 source-to-receipt lineage",
    )
    frontier_atlas_lineage.add_argument("input", nargs="?", default=None)
    frontier_atlas_lineage.add_argument("--output", default=None)

    frontier_atlas_reconciliation = subparsers.add_parser(
        "frontier-atlas-reconciliation",
        help="reconcile C13-C16 expected and observed states",
    )
    frontier_atlas_reconciliation.add_argument("input", nargs="?", default=None)
    frontier_atlas_reconciliation.add_argument("--output", default=None)

    frontier_atlas_pipeline = subparsers.add_parser(
        "run-frontier-atlas-pipeline",
        help="run the C13-C16 quality-gated frontier atlas pipeline",
    )
    frontier_atlas_pipeline.add_argument("input", nargs="?", default=None)
    frontier_atlas_pipeline.add_argument("--run-id", default="frontier-atlas-cli")
    frontier_atlas_pipeline.add_argument("--context-key", default=None)
    frontier_atlas_pipeline.add_argument("--fail-on-review", action="store_true")
    frontier_atlas_pipeline.add_argument("--output", default=None)

    frontier_atlas_release = subparsers.add_parser(
        "build-frontier-atlas-release",
        help="build a C13-C16 release manifest after the quality gate",
    )
    frontier_atlas_release.add_argument("input", nargs="?", default=None)
    frontier_atlas_release.add_argument("--run-id", default="frontier-atlas-release")
    frontier_atlas_release.add_argument("--output", default=None)

    frontier_atlas_view = subparsers.add_parser(
        "frontier-atlas-review-view",
        help="emit the sanitized C13-C16 review queue and source matrix",
    )
    frontier_atlas_view.add_argument("input", nargs="?", default=None)
    frontier_atlas_view.add_argument("--output", default=None)

    frontier_atlas_trace = subparsers.add_parser(
        "frontier-atlas-trace",
        help="emit the nine-stage C13-C16 runtime trace",
    )
    frontier_atlas_trace.add_argument("input", nargs="?", default=None)
    frontier_atlas_trace.add_argument("--run-id", default="frontier-atlas-trace")
    frontier_atlas_trace.add_argument("--output", default=None)

    frontier_atlas_receipts_csv = subparsers.add_parser(
        "export-frontier-atlas-receipts-csv",
        help="export sanitized C13-C16 receipts as CSV",
    )
    frontier_atlas_receipts_csv.add_argument("input", nargs="?", default=None)
    frontier_atlas_receipts_csv.add_argument("--output", default=None)

    frontier_atlas_review_csv = subparsers.add_parser(
        "export-frontier-atlas-review-csv",
        help="export the C13-C16 review queue as CSV",
    )
    frontier_atlas_review_csv.add_argument("input", nargs="?", default=None)
    frontier_atlas_review_csv.add_argument("--output", default=None)

    frontier_atlas_review_md = subparsers.add_parser(
        "export-frontier-atlas-review-markdown",
        help="export the C13-C16 review queue as Markdown",
    )
    frontier_atlas_review_md.add_argument("input", nargs="?", default=None)
    frontier_atlas_review_md.add_argument("--output", default=None)

    frontier_atlas_metrics_csv = subparsers.add_parser(
        "export-frontier-atlas-metrics-csv",
        help="export C13-C16 operation metrics as CSV",
    )
    frontier_atlas_metrics_csv.add_argument("input", nargs="?", default=None)
    frontier_atlas_metrics_csv.add_argument("--output", default=None)

    sequence_frontier_evaluate = subparsers.add_parser(
        "evaluate-sequence-frontier-fixture",
        help="evaluate the public Domain 06 C13-C16 fixture and controls",
    )
    sequence_frontier_evaluate.add_argument("input", nargs="?", default=None)
    sequence_frontier_evaluate.add_argument("--output", default=None)

    sequence_frontier_audit = subparsers.add_parser(
        "audit-sequence-frontier-data",
        help="audit Domain 06 C13-C16 source receipts and aggregate boundaries",
    )
    sequence_frontier_audit.add_argument("input", nargs="?", default=None)
    sequence_frontier_audit.add_argument("--output", default=None)

    sequence_frontier_replay = subparsers.add_parser(
        "replay-sequence-frontier",
        help="replay Domain 06 C13-C16 states and receipt addresses",
    )
    sequence_frontier_replay.add_argument("input", nargs="?", default=None)
    sequence_frontier_replay.add_argument("--output", default=None)

    sequence_frontier_quality = subparsers.add_parser(
        "sequence-frontier-quality-gate",
        help="run the complete Domain 06 C13-C16 quality gate",
    )
    sequence_frontier_quality.add_argument("input", nargs="?", default=None)
    sequence_frontier_quality.add_argument("--output", default=None)

    sequence_frontier_scenarios = subparsers.add_parser(
        "evaluate-sequence-frontier-scenarios",
        help="evaluate Domain 06 C13-C16 positive and negative controls",
    )
    sequence_frontier_scenarios.add_argument("input", nargs="?", default=None)
    sequence_frontier_scenarios.add_argument("--output", default=None)

    sequence_frontier_policy = subparsers.add_parser(
        "sequence-frontier-policy",
        help="evaluate Domain 06 C13-C16 interpretation and state policy",
    )
    sequence_frontier_policy.add_argument("input", nargs="?", default=None)
    sequence_frontier_policy.add_argument("--output", default=None)

    sequence_frontier_contracts = subparsers.add_parser(
        "sequence-frontier-contracts",
        help="emit typed Domain 06 C13-C16 contracts",
    )
    sequence_frontier_contracts.add_argument("--output", default=None)

    sequence_frontier_schema = subparsers.add_parser(
        "sequence-frontier-schema",
        help="emit or validate Domain 06 C13-C16 schemas",
    )
    sequence_frontier_schema.add_argument("input", nargs="?", default=None)
    sequence_frontier_schema.add_argument("--output", default=None)

    sequence_frontier_metrics = subparsers.add_parser(
        "sequence-frontier-metrics",
        help="emit Domain 06 C13-C16 operation metrics",
    )
    sequence_frontier_metrics.add_argument("input", nargs="?", default=None)
    sequence_frontier_metrics.add_argument("--output", default=None)

    sequence_frontier_bundle = subparsers.add_parser(
        "build-sequence-frontier-bundle",
        help="build the serialized Domain 06 C13-C16 bundle",
    )
    sequence_frontier_bundle.add_argument("input", nargs="?", default=None)
    sequence_frontier_bundle.add_argument("--output", default=None)

    sequence_frontier_lineage = subparsers.add_parser(
        "sequence-frontier-lineage",
        help="emit Domain 06 C13-C16 source-to-receipt lineage",
    )
    sequence_frontier_lineage.add_argument("input", nargs="?", default=None)
    sequence_frontier_lineage.add_argument("--output", default=None)

    sequence_frontier_reconciliation = subparsers.add_parser(
        "sequence-frontier-reconciliation",
        help="reconcile Domain 06 C13-C16 expected and observed states",
    )
    sequence_frontier_reconciliation.add_argument("input", nargs="?", default=None)
    sequence_frontier_reconciliation.add_argument("--output", default=None)

    sequence_frontier_pipeline = subparsers.add_parser(
        "run-sequence-frontier-pipeline",
        help="run the Domain 06 C13-C16 quality-gated pipeline",
    )
    sequence_frontier_pipeline.add_argument("input", nargs="?", default=None)
    sequence_frontier_pipeline.add_argument("--run-id", default="sequence-frontier-cli")
    sequence_frontier_pipeline.add_argument("--context-key", default=None)
    sequence_frontier_pipeline.add_argument("--fail-on-review", action="store_true")
    sequence_frontier_pipeline.add_argument("--output", default=None)

    sequence_frontier_release = subparsers.add_parser(
        "build-sequence-frontier-release",
        help="build a Domain 06 C13-C16 release manifest",
    )
    sequence_frontier_release.add_argument("input", nargs="?", default=None)
    sequence_frontier_release.add_argument("--run-id", default="sequence-frontier-release")
    sequence_frontier_release.add_argument("--output", default=None)

    sequence_frontier_view = subparsers.add_parser(
        "sequence-frontier-review-view",
        help="emit the sanitized Domain 06 review queue and source matrix",
    )
    sequence_frontier_view.add_argument("input", nargs="?", default=None)
    sequence_frontier_view.add_argument("--output", default=None)

    sequence_frontier_trace = subparsers.add_parser(
        "sequence-frontier-trace",
        help="emit the nine-stage Domain 06 runtime trace",
    )
    sequence_frontier_trace.add_argument("input", nargs="?", default=None)
    sequence_frontier_trace.add_argument("--run-id", default="sequence-frontier-trace")
    sequence_frontier_trace.add_argument("--output", default=None)

    sequence_frontier_receipts_csv = subparsers.add_parser(
        "export-sequence-frontier-receipts-csv",
        help="export sanitized Domain 06 receipts as CSV",
    )
    sequence_frontier_receipts_csv.add_argument("input", nargs="?", default=None)
    sequence_frontier_receipts_csv.add_argument("--output", default=None)

    sequence_frontier_review_csv = subparsers.add_parser(
        "export-sequence-frontier-review-csv",
        help="export the Domain 06 review queue as CSV",
    )
    sequence_frontier_review_csv.add_argument("input", nargs="?", default=None)
    sequence_frontier_review_csv.add_argument("--output", default=None)

    sequence_frontier_review_md = subparsers.add_parser(
        "export-sequence-frontier-review-markdown",
        help="export the Domain 06 review queue as Markdown",
    )
    sequence_frontier_review_md.add_argument("input", nargs="?", default=None)
    sequence_frontier_review_md.add_argument("--output", default=None)

    sequence_frontier_metrics_csv = subparsers.add_parser(
        "export-sequence-frontier-metrics-csv",
        help="export Domain 06 operation metrics as CSV",
    )
    sequence_frontier_metrics_csv.add_argument("input", nargs="?", default=None)
    sequence_frontier_metrics_csv.add_argument("--output", default=None)

    chromatin_frontier_evaluate = subparsers.add_parser(
        "evaluate-chromatin-frontier-fixture",
        help="evaluate the public Domain 07 C13-C16 fixture and controls",
    )
    chromatin_frontier_evaluate.add_argument("input", nargs="?", default=None)
    chromatin_frontier_evaluate.add_argument("--output", default=None)

    chromatin_frontier_audit = subparsers.add_parser(
        "audit-chromatin-frontier-data",
        help="audit Domain 07 C13-C16 source receipts and aggregate boundaries",
    )
    chromatin_frontier_audit.add_argument("input", nargs="?", default=None)
    chromatin_frontier_audit.add_argument("--output", default=None)

    chromatin_frontier_replay = subparsers.add_parser(
        "replay-chromatin-frontier",
        help="replay Domain 07 C13-C16 states and receipt addresses",
    )
    chromatin_frontier_replay.add_argument("input", nargs="?", default=None)
    chromatin_frontier_replay.add_argument("--output", default=None)

    chromatin_frontier_quality = subparsers.add_parser(
        "chromatin-frontier-quality-gate",
        help="run the complete Domain 07 C13-C16 quality gate",
    )
    chromatin_frontier_quality.add_argument("input", nargs="?", default=None)
    chromatin_frontier_quality.add_argument("--output", default=None)

    chromatin_frontier_scenarios = subparsers.add_parser(
        "evaluate-chromatin-frontier-scenarios",
        help="evaluate Domain 07 C13-C16 positive and negative controls",
    )
    chromatin_frontier_scenarios.add_argument("input", nargs="?", default=None)
    chromatin_frontier_scenarios.add_argument("--output", default=None)

    chromatin_frontier_policy = subparsers.add_parser(
        "chromatin-frontier-policy",
        help="evaluate Domain 07 C13-C16 interpretation and state policy",
    )
    chromatin_frontier_policy.add_argument("input", nargs="?", default=None)
    chromatin_frontier_policy.add_argument("--output", default=None)

    chromatin_frontier_contracts = subparsers.add_parser(
        "chromatin-frontier-contracts",
        help="emit typed Domain 07 C13-C16 contracts",
    )
    chromatin_frontier_contracts.add_argument("--output", default=None)

    chromatin_frontier_schema = subparsers.add_parser(
        "chromatin-frontier-schema",
        help="emit or validate Domain 07 C13-C16 schemas",
    )
    chromatin_frontier_schema.add_argument("input", nargs="?", default=None)
    chromatin_frontier_schema.add_argument("--output", default=None)

    chromatin_frontier_metrics = subparsers.add_parser(
        "chromatin-frontier-metrics",
        help="emit Domain 07 C13-C16 operation metrics",
    )
    chromatin_frontier_metrics.add_argument("input", nargs="?", default=None)
    chromatin_frontier_metrics.add_argument("--output", default=None)

    chromatin_frontier_bundle = subparsers.add_parser(
        "build-chromatin-frontier-bundle",
        help="build the serialized Domain 07 C13-C16 bundle",
    )
    chromatin_frontier_bundle.add_argument("input", nargs="?", default=None)
    chromatin_frontier_bundle.add_argument("--output", default=None)

    chromatin_frontier_lineage = subparsers.add_parser(
        "chromatin-frontier-lineage",
        help="emit Domain 07 C13-C16 source-to-receipt lineage",
    )
    chromatin_frontier_lineage.add_argument("input", nargs="?", default=None)
    chromatin_frontier_lineage.add_argument("--output", default=None)

    chromatin_frontier_reconciliation = subparsers.add_parser(
        "chromatin-frontier-reconciliation",
        help="reconcile Domain 07 C13-C16 expected and observed states",
    )
    chromatin_frontier_reconciliation.add_argument("input", nargs="?", default=None)
    chromatin_frontier_reconciliation.add_argument("--output", default=None)

    chromatin_frontier_pipeline = subparsers.add_parser(
        "run-chromatin-frontier-pipeline",
        help="run the Domain 07 C13-C16 quality-gated pipeline",
    )
    chromatin_frontier_pipeline.add_argument("input", nargs="?", default=None)
    chromatin_frontier_pipeline.add_argument("--run-id", default="chromatin-frontier-cli")
    chromatin_frontier_pipeline.add_argument("--context-key", default=None)
    chromatin_frontier_pipeline.add_argument("--fail-on-review", action="store_true")
    chromatin_frontier_pipeline.add_argument("--output", default=None)

    chromatin_frontier_release = subparsers.add_parser(
        "build-chromatin-frontier-release",
        help="build a Domain 07 C13-C16 release manifest",
    )
    chromatin_frontier_release.add_argument("input", nargs="?", default=None)
    chromatin_frontier_release.add_argument("--run-id", default="chromatin-frontier-release")
    chromatin_frontier_release.add_argument("--output", default=None)

    chromatin_frontier_view = subparsers.add_parser(
        "chromatin-frontier-review-view",
        help="emit the sanitized Domain 07 review queue and source matrix",
    )
    chromatin_frontier_view.add_argument("input", nargs="?", default=None)
    chromatin_frontier_view.add_argument("--output", default=None)

    chromatin_frontier_trace = subparsers.add_parser(
        "chromatin-frontier-trace",
        help="emit the nine-stage Domain 07 runtime trace",
    )
    chromatin_frontier_trace.add_argument("input", nargs="?", default=None)
    chromatin_frontier_trace.add_argument("--run-id", default="chromatin-frontier-trace")
    chromatin_frontier_trace.add_argument("--output", default=None)

    chromatin_frontier_receipts_csv = subparsers.add_parser(
        "export-chromatin-frontier-receipts-csv",
        help="export sanitized Domain 07 receipts as CSV",
    )
    chromatin_frontier_receipts_csv.add_argument("input", nargs="?", default=None)
    chromatin_frontier_receipts_csv.add_argument("--output", default=None)

    chromatin_frontier_review_csv = subparsers.add_parser(
        "export-chromatin-frontier-review-csv",
        help="export the Domain 07 review queue as CSV",
    )
    chromatin_frontier_review_csv.add_argument("input", nargs="?", default=None)
    chromatin_frontier_review_csv.add_argument("--output", default=None)

    chromatin_frontier_review_md = subparsers.add_parser(
        "export-chromatin-frontier-review-markdown",
        help="export the Domain 07 review queue as Markdown",
    )
    chromatin_frontier_review_md.add_argument("input", nargs="?", default=None)
    chromatin_frontier_review_md.add_argument("--output", default=None)

    chromatin_frontier_metrics_csv = subparsers.add_parser(
        "export-chromatin-frontier-metrics-csv",
        help="export Domain 07 operation metrics as CSV",
    )
    chromatin_frontier_metrics_csv.add_argument("input", nargs="?", default=None)
    chromatin_frontier_metrics_csv.add_argument("--output", default=None)

    cell_state_frontier_evaluate = subparsers.add_parser(
        "evaluate-cell-state-frontier-fixture",
        help="evaluate the public Domain 08 C13-C16 fixture and controls",
    )
    cell_state_frontier_evaluate.add_argument("input", nargs="?", default=None)
    cell_state_frontier_evaluate.add_argument("--output", default=None)
    cell_state_frontier_audit = subparsers.add_parser(
        "audit-cell-state-frontier-data",
        help="audit Domain 08 C13-C16 source receipts and aggregate boundaries",
    )
    cell_state_frontier_audit.add_argument("input", nargs="?", default=None)
    cell_state_frontier_audit.add_argument("--output", default=None)
    cell_state_frontier_replay = subparsers.add_parser(
        "replay-cell-state-frontier",
        help="replay Domain 08 C13-C16 states and receipt addresses",
    )
    cell_state_frontier_replay.add_argument("input", nargs="?", default=None)
    cell_state_frontier_replay.add_argument("--output", default=None)
    cell_state_frontier_quality = subparsers.add_parser(
        "cell-state-frontier-quality-gate",
        help="run the complete Domain 08 C13-C16 quality gate",
    )
    cell_state_frontier_quality.add_argument("input", nargs="?", default=None)
    cell_state_frontier_quality.add_argument("--output", default=None)
    cell_state_frontier_scenarios = subparsers.add_parser(
        "evaluate-cell-state-frontier-scenarios",
        help="evaluate Domain 08 C13-C16 positive and negative controls",
    )
    cell_state_frontier_scenarios.add_argument("input", nargs="?", default=None)
    cell_state_frontier_scenarios.add_argument("--output", default=None)
    cell_state_frontier_policy = subparsers.add_parser(
        "cell-state-frontier-policy",
        help="evaluate Domain 08 C13-C16 interpretation and state policy",
    )
    cell_state_frontier_policy.add_argument("input", nargs="?", default=None)
    cell_state_frontier_policy.add_argument("--output", default=None)
    cell_state_frontier_contracts = subparsers.add_parser(
        "cell-state-frontier-contracts",
        help="emit typed Domain 08 C13-C16 contracts",
    )
    cell_state_frontier_contracts.add_argument("--output", default=None)
    cell_state_frontier_schema = subparsers.add_parser(
        "cell-state-frontier-schema",
        help="emit or validate Domain 08 C13-C16 schemas",
    )
    cell_state_frontier_schema.add_argument("input", nargs="?", default=None)
    cell_state_frontier_schema.add_argument("--output", default=None)
    cell_state_frontier_metrics = subparsers.add_parser(
        "cell-state-frontier-metrics",
        help="emit Domain 08 C13-C16 operation metrics",
    )
    cell_state_frontier_metrics.add_argument("input", nargs="?", default=None)
    cell_state_frontier_metrics.add_argument("--output", default=None)
    cell_state_frontier_bundle = subparsers.add_parser(
        "build-cell-state-frontier-bundle",
        help="build the serialized Domain 08 C13-C16 bundle",
    )
    cell_state_frontier_bundle.add_argument("input", nargs="?", default=None)
    cell_state_frontier_bundle.add_argument("--output", default=None)
    cell_state_frontier_lineage = subparsers.add_parser(
        "cell-state-frontier-lineage",
        help="emit Domain 08 C13-C16 source-to-receipt lineage",
    )
    cell_state_frontier_lineage.add_argument("input", nargs="?", default=None)
    cell_state_frontier_lineage.add_argument("--output", default=None)
    cell_state_frontier_reconciliation = subparsers.add_parser(
        "cell-state-frontier-reconciliation",
        help="reconcile Domain 08 C13-C16 expected and observed states",
    )
    cell_state_frontier_reconciliation.add_argument("input", nargs="?", default=None)
    cell_state_frontier_reconciliation.add_argument("--output", default=None)
    cell_state_frontier_pipeline = subparsers.add_parser(
        "run-cell-state-frontier-pipeline",
        help="run the Domain 08 C13-C16 quality-gated pipeline",
    )
    cell_state_frontier_pipeline.add_argument("input", nargs="?", default=None)
    cell_state_frontier_pipeline.add_argument("--run-id", default="cell-state-frontier-cli")
    cell_state_frontier_pipeline.add_argument("--context-key", default=None)
    cell_state_frontier_pipeline.add_argument("--fail-on-review", action="store_true")
    cell_state_frontier_pipeline.add_argument("--output", default=None)
    cell_state_frontier_release = subparsers.add_parser(
        "build-cell-state-frontier-release",
        help="build a Domain 08 C13-C16 release manifest",
    )
    cell_state_frontier_release.add_argument("input", nargs="?", default=None)
    cell_state_frontier_release.add_argument("--run-id", default="cell-state-frontier-release")
    cell_state_frontier_release.add_argument("--output", default=None)
    cell_state_frontier_view = subparsers.add_parser(
        "cell-state-frontier-review-view",
        help="emit the sanitized Domain 08 review queue and source matrix",
    )
    cell_state_frontier_view.add_argument("input", nargs="?", default=None)
    cell_state_frontier_view.add_argument("--output", default=None)
    cell_state_frontier_trace = subparsers.add_parser(
        "cell-state-frontier-trace",
        help="emit the nine-stage Domain 08 runtime trace",
    )
    cell_state_frontier_trace.add_argument("input", nargs="?", default=None)
    cell_state_frontier_trace.add_argument("--run-id", default="cell-state-frontier-trace")
    cell_state_frontier_trace.add_argument("--output", default=None)
    cell_state_frontier_receipts_csv = subparsers.add_parser(
        "export-cell-state-frontier-receipts-csv",
        help="export sanitized Domain 08 receipts as CSV",
    )
    cell_state_frontier_receipts_csv.add_argument("input", nargs="?", default=None)
    cell_state_frontier_receipts_csv.add_argument("--output", default=None)
    cell_state_frontier_review_csv = subparsers.add_parser(
        "export-cell-state-frontier-review-csv",
        help="export the Domain 08 review queue as CSV",
    )
    cell_state_frontier_review_csv.add_argument("input", nargs="?", default=None)
    cell_state_frontier_review_csv.add_argument("--output", default=None)
    cell_state_frontier_review_md = subparsers.add_parser(
        "export-cell-state-frontier-review-markdown",
        help="export the Domain 08 review queue as Markdown",
    )
    cell_state_frontier_review_md.add_argument("input", nargs="?", default=None)
    cell_state_frontier_review_md.add_argument("--output", default=None)
    cell_state_frontier_metrics_csv = subparsers.add_parser(
        "export-cell-state-frontier-metrics-csv",
        help="export Domain 08 operation metrics as CSV",
    )
    cell_state_frontier_metrics_csv.add_argument("input", nargs="?", default=None)
    cell_state_frontier_metrics_csv.add_argument("--output", default=None)

    topology_frontier_evaluate = subparsers.add_parser(
        "evaluate-topology-frontier-fixture",
        help="evaluate the public Domain 09 C13-C16 topology fixture and controls",
    )
    topology_frontier_evaluate.add_argument("input", nargs="?", default=None)
    topology_frontier_evaluate.add_argument("--output", default=None)
    topology_frontier_audit = subparsers.add_parser(
        "audit-topology-frontier-data",
        help="audit Domain 09 C13-C16 source receipts and aggregate boundaries",
    )
    topology_frontier_audit.add_argument("input", nargs="?", default=None)
    topology_frontier_audit.add_argument("--output", default=None)
    topology_frontier_replay = subparsers.add_parser(
        "replay-topology-frontier",
        help="replay Domain 09 C13-C16 states and receipt addresses",
    )
    topology_frontier_replay.add_argument("input", nargs="?", default=None)
    topology_frontier_replay.add_argument("--output", default=None)
    topology_frontier_quality = subparsers.add_parser(
        "topology-frontier-quality-gate",
        help="run the complete Domain 09 C13-C16 quality gate",
    )
    topology_frontier_quality.add_argument("input", nargs="?", default=None)
    topology_frontier_quality.add_argument("--output", default=None)
    topology_frontier_scenarios = subparsers.add_parser(
        "evaluate-topology-frontier-scenarios",
        help="evaluate Domain 09 C13-C16 positive and negative controls",
    )
    topology_frontier_scenarios.add_argument("input", nargs="?", default=None)
    topology_frontier_scenarios.add_argument("--output", default=None)
    topology_frontier_policy = subparsers.add_parser(
        "topology-frontier-policy",
        help="evaluate Domain 09 C13-C16 interpretation and state policy",
    )
    topology_frontier_policy.add_argument("input", nargs="?", default=None)
    topology_frontier_policy.add_argument("--output", default=None)
    topology_frontier_contracts = subparsers.add_parser(
        "topology-frontier-contracts",
        help="emit typed Domain 09 C13-C16 contracts",
    )
    topology_frontier_contracts.add_argument("--output", default=None)
    topology_frontier_schema = subparsers.add_parser(
        "topology-frontier-schema",
        help="emit or validate Domain 09 C13-C16 schemas",
    )
    topology_frontier_schema.add_argument("input", nargs="?", default=None)
    topology_frontier_schema.add_argument("--output", default=None)
    topology_frontier_metrics = subparsers.add_parser(
        "topology-frontier-metrics",
        help="emit Domain 09 C13-C16 operation metrics",
    )
    topology_frontier_metrics.add_argument("input", nargs="?", default=None)
    topology_frontier_metrics.add_argument("--output", default=None)
    topology_frontier_bundle = subparsers.add_parser(
        "build-topology-frontier-bundle",
        help="build the serialized Domain 09 C13-C16 bundle",
    )
    topology_frontier_bundle.add_argument("input", nargs="?", default=None)
    topology_frontier_bundle.add_argument("--output", default=None)
    topology_frontier_lineage = subparsers.add_parser(
        "topology-frontier-lineage",
        help="emit Domain 09 C13-C16 source-to-receipt lineage",
    )
    topology_frontier_lineage.add_argument("input", nargs="?", default=None)
    topology_frontier_lineage.add_argument("--output", default=None)
    topology_frontier_reconciliation = subparsers.add_parser(
        "topology-frontier-reconciliation",
        help="reconcile Domain 09 C13-C16 expected and observed states",
    )
    topology_frontier_reconciliation.add_argument("input", nargs="?", default=None)
    topology_frontier_reconciliation.add_argument("--output", default=None)
    topology_frontier_pipeline = subparsers.add_parser(
        "run-topology-frontier-pipeline",
        help="run the Domain 09 C13-C16 quality-gated pipeline",
    )
    topology_frontier_pipeline.add_argument("input", nargs="?", default=None)
    topology_frontier_pipeline.add_argument("--run-id", default="topology-frontier-cli")
    topology_frontier_pipeline.add_argument("--output", default=None)
    topology_frontier_release = subparsers.add_parser(
        "build-topology-frontier-release",
        help="build a Domain 09 C13-C16 release manifest",
    )
    topology_frontier_release.add_argument("input", nargs="?", default=None)
    topology_frontier_release.add_argument("--run-id", default="topology-frontier-release")
    topology_frontier_release.add_argument("--release-id", default="topology-frontier-release-v1")
    topology_frontier_release.add_argument("--output", default=None)
    topology_frontier_view = subparsers.add_parser(
        "topology-frontier-review-view",
        help="emit the sanitized Domain 09 review queue and source matrix",
    )
    topology_frontier_view.add_argument("input", nargs="?", default=None)
    topology_frontier_view.add_argument("--output", default=None)
    topology_frontier_trace = subparsers.add_parser(
        "topology-frontier-trace",
        help="emit the nine-stage Domain 09 runtime trace",
    )
    topology_frontier_trace.add_argument("input", nargs="?", default=None)
    topology_frontier_trace.add_argument("--run-id", default="topology-frontier-trace")
    topology_frontier_trace.add_argument("--output", default=None)
    topology_frontier_receipts_csv = subparsers.add_parser(
        "export-topology-frontier-receipts-csv",
        help="export sanitized Domain 09 receipts as CSV",
    )
    topology_frontier_receipts_csv.add_argument("input", nargs="?", default=None)
    topology_frontier_receipts_csv.add_argument("--output", default=None)
    topology_frontier_review_csv = subparsers.add_parser(
        "export-topology-frontier-review-csv",
        help="export the Domain 09 review queue as CSV",
    )
    topology_frontier_review_csv.add_argument("input", nargs="?", default=None)
    topology_frontier_review_csv.add_argument("--output", default=None)
    topology_frontier_review_md = subparsers.add_parser(
        "export-topology-frontier-review-markdown",
        help="export the Domain 09 review queue as Markdown",
    )
    topology_frontier_review_md.add_argument("input", nargs="?", default=None)
    topology_frontier_review_md.add_argument("--output", default=None)
    topology_frontier_metrics_csv = subparsers.add_parser(
        "export-topology-frontier-metrics-csv",
        help="export Domain 09 operation metrics as CSV",
    )
    topology_frontier_metrics_csv.add_argument("input", nargs="?", default=None)
    topology_frontier_metrics_csv.add_argument("--output", default=None)

    link_frontier_evaluate = subparsers.add_parser(
        "evaluate-link-frontier-fixture",
        help="evaluate the public Domain 10 C13-C16 link fixture and controls",
    )
    link_frontier_evaluate.add_argument("input", nargs="?", default=None)
    link_frontier_evaluate.add_argument("--output", default=None)
    link_frontier_audit = subparsers.add_parser(
        "audit-link-frontier-data",
        help="audit Domain 10 C13-C16 source receipts and aggregate boundaries",
    )
    link_frontier_audit.add_argument("input", nargs="?", default=None)
    link_frontier_audit.add_argument("--output", default=None)
    link_frontier_replay = subparsers.add_parser(
        "replay-link-frontier",
        help="replay Domain 10 C13-C16 states and receipt addresses",
    )
    link_frontier_replay.add_argument("input", nargs="?", default=None)
    link_frontier_replay.add_argument("--output", default=None)
    link_frontier_quality = subparsers.add_parser(
        "link-frontier-quality-gate",
        help="run the complete Domain 10 C13-C16 quality gate",
    )
    link_frontier_quality.add_argument("input", nargs="?", default=None)
    link_frontier_quality.add_argument("--output", default=None)
    link_frontier_scenarios = subparsers.add_parser(
        "evaluate-link-frontier-scenarios",
        help="evaluate Domain 10 C13-C16 positive and negative controls",
    )
    link_frontier_scenarios.add_argument("input", nargs="?", default=None)
    link_frontier_scenarios.add_argument("--output", default=None)
    link_frontier_policy = subparsers.add_parser(
        "link-frontier-policy",
        help="evaluate Domain 10 C13-C16 interpretation and state policy",
    )
    link_frontier_policy.add_argument("input", nargs="?", default=None)
    link_frontier_policy.add_argument("--output", default=None)
    link_frontier_contracts = subparsers.add_parser(
        "link-frontier-contracts",
        help="emit typed Domain 10 C13-C16 contracts",
    )
    link_frontier_contracts.add_argument("--output", default=None)
    link_frontier_schema = subparsers.add_parser(
        "link-frontier-schema",
        help="emit or validate Domain 10 C13-C16 schemas",
    )
    link_frontier_schema.add_argument("input", nargs="?", default=None)
    link_frontier_schema.add_argument("--output", default=None)
    link_frontier_metrics = subparsers.add_parser(
        "link-frontier-metrics",
        help="emit Domain 10 C13-C16 operation metrics",
    )
    link_frontier_metrics.add_argument("input", nargs="?", default=None)
    link_frontier_metrics.add_argument("--output", default=None)
    link_frontier_bundle = subparsers.add_parser(
        "build-link-frontier-bundle",
        help="build the serialized Domain 10 C13-C16 bundle",
    )
    link_frontier_bundle.add_argument("input", nargs="?", default=None)
    link_frontier_bundle.add_argument("--output", default=None)
    link_frontier_lineage = subparsers.add_parser(
        "link-frontier-lineage",
        help="emit Domain 10 C13-C16 source-to-receipt lineage",
    )
    link_frontier_lineage.add_argument("input", nargs="?", default=None)
    link_frontier_lineage.add_argument("--output", default=None)
    link_frontier_reconciliation = subparsers.add_parser(
        "link-frontier-reconciliation",
        help="reconcile Domain 10 C13-C16 expected and observed states",
    )
    link_frontier_reconciliation.add_argument("input", nargs="?", default=None)
    link_frontier_reconciliation.add_argument("--output", default=None)
    link_frontier_pipeline = subparsers.add_parser(
        "run-link-frontier-pipeline",
        help="run the Domain 10 C13-C16 quality-gated pipeline",
    )
    link_frontier_pipeline.add_argument("input", nargs="?", default=None)
    link_frontier_pipeline.add_argument("--run-id", default="link-frontier-cli")
    link_frontier_pipeline.add_argument("--output", default=None)
    link_frontier_release = subparsers.add_parser(
        "build-link-frontier-release",
        help="build a Domain 10 C13-C16 release manifest",
    )
    link_frontier_release.add_argument("input", nargs="?", default=None)
    link_frontier_release.add_argument("--run-id", default="link-frontier-release")
    link_frontier_release.add_argument("--release-id", default="link-frontier-release-v1")
    link_frontier_release.add_argument("--output", default=None)
    link_frontier_view = subparsers.add_parser(
        "link-frontier-review-view",
        help="emit the sanitized Domain 10 review queue and source matrix",
    )
    link_frontier_view.add_argument("input", nargs="?", default=None)
    link_frontier_view.add_argument("--output", default=None)
    link_frontier_trace = subparsers.add_parser(
        "link-frontier-trace",
        help="emit the nine-stage Domain 10 runtime trace",
    )
    link_frontier_trace.add_argument("input", nargs="?", default=None)
    link_frontier_trace.add_argument("--run-id", default="link-frontier-trace")
    link_frontier_trace.add_argument("--output", default=None)
    link_frontier_receipts_csv = subparsers.add_parser(
        "export-link-frontier-receipts-csv",
        help="export sanitized Domain 10 receipts as CSV",
    )
    link_frontier_receipts_csv.add_argument("input", nargs="?", default=None)
    link_frontier_receipts_csv.add_argument("--output", default=None)
    link_frontier_review_csv = subparsers.add_parser(
        "export-link-frontier-review-csv",
        help="export the Domain 10 review queue as CSV",
    )
    link_frontier_review_csv.add_argument("input", nargs="?", default=None)
    link_frontier_review_csv.add_argument("--output", default=None)
    link_frontier_review_md = subparsers.add_parser(
        "export-link-frontier-review-markdown",
        help="export the Domain 10 review queue as Markdown",
    )
    link_frontier_review_md.add_argument("input", nargs="?", default=None)
    link_frontier_review_md.add_argument("--output", default=None)
    link_frontier_metrics_csv = subparsers.add_parser(
        "export-link-frontier-metrics-csv",
        help="export Domain 10 operation metrics as CSV",
    )
    link_frontier_metrics_csv.add_argument("input", nargs="?", default=None)
    link_frontier_metrics_csv.add_argument("--output", default=None)
    link_frontier_depth = subparsers.add_parser(
        "link-frontier-depth-audit",
        help="run operation-specific Domain 10 depth invariants",
    )
    link_frontier_depth.add_argument("input", nargs="?", default=None)
    link_frontier_depth.add_argument("--output", default=None)

    causal_frontier_commands = (
        ("causal-frontier-data-audit", "audit public Domain 11 source receipts"),
        ("causal-frontier-contracts", "emit Domain 11 operation contracts"),
        ("causal-frontier-schema", "emit Domain 11 field schema"),
        ("causal-frontier-evaluate", "evaluate Domain 11 positive and control records"),
        ("causal-frontier-replay", "replay Domain 11 content-addressed receipts"),
        ("causal-frontier-metrics", "emit Domain 11 operation metrics"),
        ("causal-frontier-lineage", "emit Domain 11 source lineage"),
        ("causal-frontier-policy", "emit Domain 11 policy decisions"),
        ("causal-frontier-quality-gate", "run Domain 11 quality checks"),
        ("causal-frontier-runtime", "run Domain 11 release rehearsal"),
        ("causal-frontier-release", "build Domain 11 release manifest"),
        ("causal-frontier-depth-audit", "run Domain 11 depth audit"),
    )
    for command_name, command_help in causal_frontier_commands:
        command_parser = subparsers.add_parser(command_name, help=command_help)
        if command_name != "causal-frontier-contracts":
            command_parser.add_argument("input", nargs="?", default=None)
        command_parser.add_argument("--output", default=None)
    causal_frontier_csv = subparsers.add_parser(
        "export-causal-frontier-review-csv",
        help="export the Domain 11 review rows as CSV",
    )
    causal_frontier_csv.add_argument("input", nargs="?", default=None)
    causal_frontier_csv.add_argument("--output", default=None)

    cohort_frontier_commands = (
        ("cohort-frontier-data-audit", "audit public Domain 12 source receipts"),
        ("cohort-frontier-contracts", "emit Domain 12 operation contracts"),
        ("cohort-frontier-schema", "emit Domain 12 field schema"),
        ("cohort-frontier-evaluate", "evaluate Domain 12 positive and control records"),
        ("cohort-frontier-replay", "replay Domain 12 content-addressed receipts"),
        ("cohort-frontier-metrics", "emit Domain 12 operation metrics"),
        ("cohort-frontier-lineage", "emit Domain 12 source lineage"),
        ("cohort-frontier-policy", "emit Domain 12 policy decisions"),
        ("cohort-frontier-quality-gate", "run Domain 12 quality checks"),
        ("cohort-frontier-runtime", "run Domain 12 release rehearsal"),
        ("cohort-frontier-release", "build Domain 12 release manifest"),
        ("cohort-frontier-depth-audit", "run Domain 12 depth audit"),
    )
    for command_name, command_help in cohort_frontier_commands:
        command_parser = subparsers.add_parser(command_name, help=command_help)
        if command_name != "cohort-frontier-contracts":
            command_parser.add_argument("input", nargs="?", default=None)
        command_parser.add_argument("--output", default=None)
    cohort_frontier_bundle = subparsers.add_parser(
        "cohort-frontier-bundle",
        help="assemble the Domain 12 research-use release bundle",
    )
    cohort_frontier_bundle.add_argument("input", nargs="?", default=None)
    cohort_frontier_bundle.add_argument("--output", default=None)
    cohort_frontier_csv = subparsers.add_parser(
        "export-cohort-frontier-review-csv",
        help="export the Domain 12 review rows as CSV",
    )
    cohort_frontier_csv.add_argument("input", nargs="?", default=None)
    cohort_frontier_csv.add_argument("--output", default=None)

    validation_frontier_commands = (
        ("validation-frontier-data-audit", "audit public Domain 13 planning receipts"),
        ("validation-frontier-contracts", "emit Domain 13 planning contracts"),
        ("validation-frontier-schema", "emit Domain 13 planning schema"),
        ("validation-frontier-evaluate", "evaluate Domain 13 planning records"),
        ("validation-frontier-replay", "replay Domain 13 planning receipts"),
        ("validation-frontier-metrics", "emit Domain 13 planning metrics"),
        ("validation-frontier-lineage", "emit Domain 13 planning lineage"),
        ("validation-frontier-policy", "emit Domain 13 planning policy"),
        ("validation-frontier-quality-gate", "run Domain 13 planning quality checks"),
        ("validation-frontier-runtime", "run Domain 13 planning release rehearsal"),
        ("validation-frontier-observability", "emit Domain 13 planning observability"),
        ("validation-frontier-artifacts", "emit Domain 13 planning artifact inventory"),
        ("validation-frontier-release", "build Domain 13 planning release manifest"),
        ("validation-frontier-review-queue", "build Domain 13 planning review queue"),
        ("validation-frontier-depth-audit", "run Domain 13 planning depth audit"),
    )
    for command_name, command_help in validation_frontier_commands:
        command_parser = subparsers.add_parser(command_name, help=command_help)
        if command_name != "validation-frontier-contracts":
            command_parser.add_argument("input", nargs="?", default=None)
        command_parser.add_argument("--output", default=None)
    validation_frontier_bundle = subparsers.add_parser(
        "validation-frontier-bundle",
        help="assemble the Domain 13 planning review bundle",
    )
    validation_frontier_bundle.add_argument("input", nargs="?", default=None)
    validation_frontier_bundle.add_argument("--output", default=None)
    validation_frontier_csv = subparsers.add_parser(
        "export-validation-frontier-review-csv",
        help="export Domain 13 planning review rows as CSV",
    )
    validation_frontier_csv.add_argument("input", nargs="?", default=None)
    validation_frontier_csv.add_argument("--output", default=None)

    evidence_lifecycle_commands = (
        ("evidence-lifecycle-data-audit", "audit public Domain 14 lifecycle receipts"),
        ("evidence-lifecycle-contracts", "emit Domain 14 lifecycle contracts"),
        ("evidence-lifecycle-schema", "emit Domain 14 lifecycle schema"),
        ("evidence-lifecycle-evaluate", "evaluate Domain 14 lifecycle records"),
        ("evidence-lifecycle-replay", "replay Domain 14 lifecycle receipts"),
        ("evidence-lifecycle-metrics", "emit Domain 14 lifecycle metrics"),
        ("evidence-lifecycle-lineage", "emit Domain 14 lifecycle lineage"),
        ("evidence-lifecycle-policy", "emit Domain 14 lifecycle policy"),
        ("evidence-lifecycle-quality-gate", "run Domain 14 lifecycle quality checks"),
        ("evidence-lifecycle-runtime", "run Domain 14 lifecycle release rehearsal"),
        ("evidence-lifecycle-observability", "emit Domain 14 lifecycle observability"),
        ("evidence-lifecycle-artifacts", "emit Domain 14 lifecycle artifact inventory"),
        ("evidence-lifecycle-release", "build Domain 14 lifecycle release manifest"),
        ("evidence-lifecycle-review-queue", "build Domain 14 lifecycle review queue"),
        ("evidence-lifecycle-depth-audit", "run Domain 14 lifecycle depth audit"),
    )
    for command_name, command_help in evidence_lifecycle_commands:
        command_parser = subparsers.add_parser(command_name, help=command_help)
        if command_name != "evidence-lifecycle-contracts":
            command_parser.add_argument("input", nargs="?", default=None)
        command_parser.add_argument("--output", default=None)
    evidence_lifecycle_bundle = subparsers.add_parser("evidence-lifecycle-bundle", help="assemble the Domain 14 lifecycle review bundle")
    evidence_lifecycle_bundle.add_argument("input", nargs="?", default=None)
    evidence_lifecycle_bundle.add_argument("--output", default=None)
    evidence_lifecycle_csv = subparsers.add_parser("export-evidence-lifecycle-review-csv", help="export Domain 14 lifecycle review rows as CSV")
    evidence_lifecycle_csv.add_argument("input", nargs="?", default=None)
    evidence_lifecycle_csv.add_argument("--output", default=None)

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
        if args.command == "evaluate-variation-fixture":
            report = evaluate_variation_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-variation-data":
            report = audit_variation_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-variation-fixtures":
            report = replay_variation_fixtures(
                args.inputs,
                required_context_key=args.required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "variation-quality-gate":
            report = evaluate_variation_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-variation-scenarios":
            report = evaluate_variation_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "variation-contracts":
            _write_json(default_variation_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-variation-bundle":
            bundle = VariationEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
            )
            return 0 if bundle.accepted else 2
        if args.command == "evaluate-identity-fixture":
            report = evaluate_identity_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-identity-data":
            report = audit_identity_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-identity-fixtures":
            first_catalog = IdentityFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = IdentityReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                tuple(sorted(source.source_id for source in first_catalog.sources)),
            )
            report = replay_identity_fixtures(args.inputs, expectation=expectation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "identity-quality-gate":
            report = evaluate_identity_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-identity-scenarios":
            report = evaluate_identity_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "identity-contracts":
            _write_json(default_identity_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-identity-bundle":
            bundle = IdentityEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
            )
            return 0 if bundle.accepted else 2
        if args.command == "evaluate-intake-fixture":
            report = evaluate_intake_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-intake-data":
            report = audit_intake_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-intake-fixtures":
            first_catalog = IntakeFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = IntakeReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                tuple(sorted(source.source_id for source in first_catalog.sources)),
                minimum_checks=33,
                minimum_positive_records=4,
                minimum_negative_controls=8,
            )
            report = replay_intake_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "intake-quality-gate":
            report = evaluate_intake_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-intake-scenarios":
            report = evaluate_intake_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "intake-contracts":
            _write_json(default_intake_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-intake-bundle":
            bundle = IntakeEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "run-intake-pipeline":
            report = run_intake_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-structural-fixture":
            report = evaluate_structural_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-structural-data":
            catalog = StructuralFixtureCatalog.from_file(args.input)
            report = audit_structural_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-structural-fixtures":
            first_catalog = StructuralFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = StructuralReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=30,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_structural_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-quality-gate":
            report = evaluate_structural_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-structural-scenarios":
            report = evaluate_structural_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-contracts":
            _write_json(default_structural_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-structural-bundle":
            bundle = StructuralEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "run-structural-pipeline":
            report = run_structural_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "structural-lineage":
            graph = build_structural_lineage(args.input)
            audit = audit_structural_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "evaluate-structural-haplotype-fixture":
            report = evaluate_structural_haplotype_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-structural-haplotype-data":
            catalog = StructuralHaplotypeFixtureCatalog.from_file(args.input)
            report = audit_structural_haplotype_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-structural-haplotype-fixtures":
            first_catalog = StructuralHaplotypeFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = StructuralHaplotypeReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=40,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_structural_haplotype_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-haplotype-quality-gate":
            report = evaluate_structural_haplotype_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-structural-haplotype-scenarios":
            report = evaluate_structural_haplotype_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-haplotype-contracts":
            _write_json(default_structural_haplotype_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-structural-haplotype-bundle":
            bundle = StructuralHaplotypeEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "structural-haplotype-lineage":
            graph = build_structural_haplotype_lineage(args.input)
            audit = audit_structural_haplotype_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-structural-haplotype-pipeline":
            report = run_structural_haplotype_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-structural-frontier-fixture":
            report = evaluate_structural_frontier_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-structural-frontier-data":
            catalog = StructuralFrontierFixtureCatalog.from_file(args.input)
            report = audit_structural_frontier_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-structural-frontier-fixtures":
            first_catalog = StructuralFrontierFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = StructuralFrontierReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=40,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_structural_frontier_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-frontier-quality-gate":
            report = evaluate_structural_frontier_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-structural-frontier-scenarios":
            report = evaluate_structural_frontier_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-frontier-contracts":
            _write_json(default_structural_frontier_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-structural-frontier-bundle":
            bundle = StructuralFrontierEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "structural-frontier-lineage":
            graph = build_structural_frontier_lineage(args.input)
            audit = audit_structural_frontier_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-structural-frontier-pipeline":
            report = run_structural_frontier_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-structural-beta-fixture":
            report = evaluate_structural_beta_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-structural-beta-data":
            catalog = StructuralBetaFixtureCatalog.from_file(args.input)
            report = audit_structural_beta_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-structural-beta-fixtures":
            first_catalog = StructuralBetaFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = StructuralBetaReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=40,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_structural_beta_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-beta-quality-gate":
            report = evaluate_structural_beta_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-structural-beta-scenarios":
            report = evaluate_structural_beta_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "structural-beta-contracts":
            _write_json(default_structural_beta_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-structural-beta-bundle":
            bundle = StructuralBetaEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "structural-beta-lineage":
            graph = build_structural_beta_lineage(args.input)
            audit = audit_structural_beta_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-structural-beta-pipeline":
            report = run_structural_beta_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
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
        if args.command == "evaluate-specimen-frontier-fixture":
            report = evaluate_specimen_frontier_fixture(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-specimen-frontier-data":
            catalog = SpecimenFrontierFixtureCatalog.from_file(args.input)
            report = audit_specimen_frontier_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-specimen-frontier-fixtures":
            first_catalog = SpecimenFrontierFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = SpecimenFrontierReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=40,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_specimen_frontier_fixtures(
                args.inputs,
                expectation=expectation,
                required_context_key=required_context_key,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-frontier-quality-gate":
            report = evaluate_specimen_frontier_quality_gate(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-specimen-frontier-scenarios":
            report = evaluate_specimen_frontier_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-frontier-contracts":
            _write_json(default_specimen_frontier_contract_registry().manifest(), args.output)
            return 0
        if args.command == "build-specimen-frontier-bundle":
            bundle = SpecimenFrontierEvidenceBundleBuilder().write(
                args.input,
                args.output,
                output_format=args.format,
                bundle_id=args.bundle_id,
                allow_review=args.allow_review,
            )
            return 0 if bundle.accepted else 2
        if args.command == "specimen-frontier-lineage":
            graph = build_specimen_frontier_lineage(args.input)
            audit = audit_specimen_frontier_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-specimen-frontier-pipeline":
            report = run_specimen_frontier_pipeline(_read_json(args.input))
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-specimen-beta-frontier-fixture":
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_beta_frontier_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-specimen-beta-frontier-data":
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.input)
            report = audit_specimen_beta_frontier_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-specimen-beta-frontier-fixtures":
            first_catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = SpecimenBetaFrontierReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=72,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_specimen_beta_frontier_fixtures(
                args.inputs,
                expectation=expectation,
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-beta-frontier-quality-gate":
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_beta_frontier_quality_gate(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-specimen-beta-frontier-scenarios":
            report = evaluate_specimen_beta_frontier_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-beta-frontier-contracts":
            _write_json(default_specimen_beta_frontier_contracts().to_dict(), args.output)
            return 0
        if args.command == "build-specimen-beta-frontier-bundle":
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.input)
            builder = SpecimenBetaFrontierEvidenceBundleBuilder()
            bundle = builder.build(
                catalog,
                bundle_id=args.bundle_id or "specimen-beta-frontier-c05-c08",
                allow_review=args.allow_review,
            )
            builder.write(
                bundle,
                args.output,
                format=SpecimenBetaFrontierBundleFormat(args.format),
            )
            return 0 if builder.verify(bundle) else 2
        if args.command == "specimen-beta-frontier-lineage":
            catalog = SpecimenBetaFrontierFixtureCatalog.from_file(args.input)
            graph = build_specimen_beta_frontier_lineage(catalog)
            audit = audit_specimen_beta_frontier_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-specimen-beta-frontier-pipeline":
            request = specimen_beta_frontier_pipeline_request_from_file(args.input)
            report = run_specimen_beta_frontier_pipeline(request)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "evaluate-specimen-lineage-fixture":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_lineage_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-specimen-lineage-data":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            report = audit_specimen_lineage_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-specimen-lineage-fixtures":
            first_catalog = SpecimenLineageFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = SpecimenLineageReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                first_catalog.source_ids,
                minimum_checks=159,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_specimen_lineage_fixtures(args.inputs, expectation=expectation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-lineage-quality-gate":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_lineage_quality_gate(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-specimen-lineage-scenarios":
            report = evaluate_specimen_lineage_scenarios(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-lineage-contracts":
            _write_json(default_specimen_lineage_contracts().to_dict(), args.output)
            return 0
        if args.command == "build-specimen-lineage-bundle":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            builder = SpecimenLineageEvidenceBundleBuilder()
            bundle = builder.build(
                catalog,
                bundle_id=args.bundle_id or "specimen-lineage-c09-c12",
                allow_review=args.allow_review,
            )
            builder.write(bundle, args.output, format=SpecimenLineageBundleFormat(args.format))
            return 0 if builder.verify(bundle) else 2
        if args.command == "specimen-lineage-lineage":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            graph = build_specimen_lineage_lineage(catalog)
            audit = audit_specimen_lineage_lineage(graph)
            payload = graph.to_dict()
            payload["node_count"] = len(graph.nodes)
            payload["edge_count"] = len(graph.edges)
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "specimen-lineage-reconciliation":
            catalog = SpecimenLineageFixtureCatalog.from_file(args.input)
            index = build_specimen_lineage_receipt_index(catalog)
            audit = audit_specimen_lineage_receipt_index(catalog, index)
            payload = index.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-specimen-lineage-pipeline":
            request = specimen_lineage_pipeline_request_from_file(args.input)
            report = run_specimen_lineage_pipeline(request)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "evaluate-specimen-preanalytic-fixture":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_preanalytic_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-specimen-preanalytic-data":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            report = audit_specimen_preanalytic_data(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "replay-specimen-preanalytic-fixtures":
            first_catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.inputs[0])
            required_context_key = args.required_context_key or first_catalog.context_key
            expectation = SpecimenPreanalyticReplayExpectation(
                first_catalog.fixture_id,
                required_context_key,
                minimum_receipts=12,
                minimum_checks=120,
                positive_count=4,
                control_count=8,
            )
            report = replay_specimen_preanalytic_file(args.inputs[0], expectation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-preanalytic-quality-gate":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_preanalytic_quality_gate(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-specimen-preanalytic-scenarios":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            report = evaluate_specimen_preanalytic_scenarios(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "specimen-preanalytic-contracts":
            _write_json(default_specimen_preanalytic_contracts().to_dict(), args.output)
            return 0
        if args.command == "build-specimen-preanalytic-bundle":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            builder = SpecimenPreanalyticEvidenceBundleBuilder()
            bundle = builder.build(
                catalog,
                bundle_id=args.bundle_id or "specimen-preanalytic-c13-c16",
                allow_review=args.allow_review,
            )
            builder.write(bundle, args.output, format=SpecimenPreanalyticBundleFormat(args.format))
            return 0 if builder.verify(bundle) else 2
        if args.command == "specimen-preanalytic-lineage":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            graph = build_specimen_preanalytic_lineage(catalog)
            audit = audit_specimen_preanalytic_lineage(graph)
            payload = graph.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "specimen-preanalytic-reconciliation":
            catalog = SpecimenPreanalyticFixtureCatalog.from_file(args.input)
            index = build_specimen_preanalytic_receipt_index(catalog)
            audit = audit_specimen_preanalytic_receipt_index(catalog, index)
            payload = index.to_dict()
            payload["audit"] = audit.to_dict()
            _write_json(payload, args.output)
            return 0 if audit.passed else 2
        if args.command == "run-specimen-preanalytic-pipeline":
            request, catalog = SpecimenPreanalyticPipelineRequest.from_file(args.input)
            report = run_specimen_preanalytic_pipeline(request, catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "evaluate-reference-coordinate-fixture":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            report = evaluate_reference_coordinate_fixture(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "audit-reference-coordinate-data":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            report = audit_reference_coordinate_data(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "replay-reference-coordinate-fixtures":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            expectation = default_reference_coordinate_expectation(catalog)
            report = replay_reference_coordinate_fixture(catalog, expectation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "reference-coordinate-quality-gate":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            report = evaluate_reference_coordinate_quality_gate(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "evaluate-reference-coordinate-scenarios":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            report = evaluate_reference_coordinate_scenarios(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "reference-coordinate-contracts":
            _write_json(default_reference_coordinate_contracts().manifest(), args.output)
            return 0
        if args.command == "build-reference-coordinate-bundle":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            builder = ReferenceCoordinateBundleBuilder()
            bundle = builder.build(
                catalog,
                output_format=ReferenceCoordinateBundleFormat(args.format),
                accepted_only=args.accepted_only,
                allow_review=args.allow_review,
            )
            rendered = builder.render(bundle)
            Path(args.output).write_text(rendered, encoding="utf-8")
            verification = builder.verify(bundle, catalog)
            return 0 if verification.passed else 2
        if args.command == "reference-coordinate-lineage":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            graph = build_reference_coordinate_lineage(catalog)
            payload = graph.to_dict()
            payload["audit"] = graph.audit(catalog).to_dict()
            _write_json(payload, args.output)
            return 0 if graph.audit(catalog).passed else 2
        if args.command == "reference-coordinate-reconciliation":
            catalog = ReferenceCoordinateFixtureCatalog.from_file(args.input)
            report = reconcile_reference_coordinate_views(catalog)
            _write_json(report.to_dict(), args.output)
            return 0 if report.passed else 2
        if args.command == "run-reference-coordinate-pipeline":
            request = ReferenceCoordinatePipelineRequest.from_file(args.input)
            report = run_reference_coordinate_pipeline(request)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "evaluate-reference-annotation-fixture":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            report = evaluate_reference_annotation_fixture(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "audit-reference-annotation-data":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            report = audit_reference_annotation_data(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-reference-annotation-fixtures":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            report = evaluate_reference_annotation_fixture(fixture)
            replay = replay_reference_annotation_evaluation(report)
            _write_json(replay.to_dict(), args.output)
            return 0 if replay.accepted else 2
        if args.command == "reference-annotation-quality-gate":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            report = evaluate_reference_annotation_quality_gate(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-reference-annotation-scenarios":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            evaluation = evaluate_reference_annotation_fixture(fixture)
            report = evaluate_reference_annotation_scenarios(fixture, report=evaluation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "reference-annotation-contracts":
            _write_json(default_reference_annotation_contracts().manifest(), args.output)
            return 0
        if args.command == "build-reference-annotation-bundle":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            evaluation = evaluate_reference_annotation_fixture(fixture)
            builder = ReferenceAnnotationBundleBuilder()
            bundle = builder.build(evaluation, fixture=fixture, accepted_only=args.accepted_only)
            builder.write(bundle, args.output, format=ReferenceAnnotationBundleFormat(args.format))
            return 0 if not builder.verify(bundle) else 2
        if args.command == "reference-annotation-lineage":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            evaluation = evaluate_reference_annotation_fixture(fixture)
            graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
            payload = graph.to_dict() | {
                "audit": graph.audit.to_dict(),
                "accepted": graph.audit.accepted,
            }
            _write_json(payload, args.output)
            return 0 if graph.audit.accepted else 2
        if args.command == "reference-annotation-reconciliation":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            evaluation = evaluate_reference_annotation_fixture(fixture)
            builder = ReferenceAnnotationBundleBuilder()
            bundle = builder.build(evaluation, fixture=fixture)
            graph = build_reference_annotation_lineage(evaluation, fixture=fixture)
            report = reconcile_reference_annotation_views(
                evaluation, bundle, graph, fixture=fixture
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "run-reference-annotation-pipeline":
            report = run_reference_annotation_pipeline_file(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "build-reference-annotation-release":
            fixture = load_reference_annotation_fixture(_read_json(args.input))
            evaluation = evaluate_reference_annotation_fixture(fixture)
            quality = evaluate_reference_annotation_quality_gate(fixture)
            replay = replay_reference_annotation_evaluation(evaluation)
            bundle = ReferenceAnnotationBundleBuilder().build(
                evaluation, fixture=fixture, accepted_only=True
            )
            manifest = build_reference_annotation_release_manifest(
                evaluation, quality, bundle, replay, fixture=fixture
            )
            write_reference_annotation_release_manifest(manifest, args.output)
            return 0 if manifest.publishable else 2
        if args.command == "evaluate-reference-governance-fixture":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            report = evaluate_reference_governance_fixture(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "audit-reference-governance-data":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            report = audit_reference_governance_data(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-reference-governance-fixtures":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            report = replay_reference_governance_evaluation(evaluation, fixture=fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "reference-governance-quality-gate":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            report = evaluate_reference_governance_quality_gate(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-reference-governance-scenarios":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            report = evaluate_reference_governance_scenarios(fixture, report=evaluation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "reference-governance-contracts":
            _write_json(default_reference_governance_contracts().manifest(), args.output)
            return 0
        if args.command == "reference-governance-metrics":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            report = build_reference_governance_metrics(evaluation)
            _write_json(
                render_reference_governance_metrics(report)
                | {
                    "accepted": report.accepted,
                    "failures": list(verify_reference_governance_metrics(report)),
                },
                args.output,
            )
            return 0 if report.accepted and not verify_reference_governance_metrics(report) else 2
        if args.command == "build-reference-governance-bundle":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            builder = ReferenceGovernanceBundleBuilder()
            bundle = builder.build(
                evaluation,
                fixture=fixture,
                output_format=ReferenceGovernanceBundleFormat(args.format),
                accepted_only=args.accepted_only,
            )
            builder.write(bundle, args.output)
            return 0 if not builder.verify(bundle) else 2
        if args.command == "reference-governance-lineage":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            graph = build_reference_governance_lineage(evaluation, fixture=fixture)
            payload = graph.to_dict() | {
                "audit": graph.audit(evaluation).to_dict(),
                "accepted": graph.audit(evaluation).passed,
            }
            _write_json(payload, args.output)
            return 0 if graph.audit(evaluation).passed else 2
        if args.command == "reference-governance-reconciliation":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            data = audit_reference_governance_data(fixture)
            evaluation = evaluate_reference_governance_fixture(fixture)
            replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
            scenarios = evaluate_reference_governance_scenarios(fixture, report=evaluation)
            graph = build_reference_governance_lineage(evaluation, fixture=fixture)
            report = reconcile_reference_governance_views(
                fixture, data, evaluation, replay, scenarios, graph
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "run-reference-governance-pipeline":
            report = run_reference_governance_pipeline_file(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "build-reference-governance-release":
            fixture = load_reference_governance_fixture(_read_json(args.input))
            evaluation = evaluate_reference_governance_fixture(fixture)
            quality = evaluate_reference_governance_quality_gate(fixture)
            replay = replay_reference_governance_evaluation(evaluation, fixture=fixture)
            bundle = ReferenceGovernanceBundleBuilder().build(
                evaluation, fixture=fixture, accepted_only=True
            )
            manifest = build_reference_governance_release_manifest(
                evaluation, quality, bundle, replay, fixture=fixture
            )
            write_reference_governance_release_manifest(manifest, args.output)
            return 0 if manifest.publishable else 2
        if args.command == "evaluate-regulatory-atlas-fixture":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            report = evaluate_regulatory_atlas_fixture(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "audit-regulatory-atlas-data":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            report = audit_regulatory_atlas_data(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-regulatory-atlas-fixtures":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            report = replay_regulatory_atlas_evaluation(evaluation, fixture=fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "regulatory-atlas-quality-gate":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            report = evaluate_regulatory_atlas_quality_gate(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-regulatory-atlas-scenarios":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            report = evaluate_regulatory_atlas_scenarios(fixture, report=evaluation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "regulatory-atlas-contracts":
            _write_json(default_regulatory_atlas_contracts().manifest(), args.output)
            return 0
        if args.command == "regulatory-atlas-metrics":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            report = build_regulatory_atlas_metrics(evaluation)
            failures = verify_regulatory_atlas_metrics(report)
            _write_json(
                render_regulatory_atlas_metrics(report)
                | {"accepted": report.accepted, "failures": list(failures)},
                args.output,
            )
            return 0 if report.accepted and not failures else 2
        if args.command == "build-regulatory-atlas-bundle":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            builder = RegulatoryAtlasBundleBuilder()
            bundle = builder.build(
                evaluation,
                fixture=fixture,
                output_format=RegulatoryAtlasBundleFormat(args.format),
                accepted_only=args.accepted_only,
            )
            builder.write(bundle, args.output)
            return 0 if not builder.verify(bundle) else 2
        if args.command == "regulatory-atlas-lineage":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            graph = build_regulatory_atlas_lineage(evaluation, fixture=fixture)
            audit = graph.audit(evaluation)
            _write_json(
                graph.to_dict() | {"audit": audit.to_dict(), "accepted": audit.passed}, args.output
            )
            return 0 if audit.passed else 2
        if args.command == "regulatory-atlas-reconciliation":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            data = audit_regulatory_atlas_data(fixture)
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            replay = replay_regulatory_atlas_evaluation(evaluation, fixture=fixture)
            scenarios = evaluate_regulatory_atlas_scenarios(fixture, report=evaluation)
            graph = build_regulatory_atlas_lineage(evaluation, fixture=fixture)
            report = reconcile_regulatory_atlas_views(
                fixture, data, evaluation, replay, scenarios, graph
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "run-regulatory-atlas-pipeline":
            report = run_regulatory_atlas_pipeline_file(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "build-regulatory-atlas-release":
            fixture = load_regulatory_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_regulatory_atlas_fixture(fixture)
            quality = evaluate_regulatory_atlas_quality_gate(fixture)
            replay = replay_regulatory_atlas_evaluation(evaluation, fixture=fixture)
            bundle = RegulatoryAtlasBundleBuilder().build(
                evaluation, fixture=fixture, accepted_only=True
            )
            manifest = build_regulatory_atlas_release_manifest(
                evaluation, quality, bundle, replay, fixture=fixture
            )
            write_regulatory_atlas_release_manifest(manifest, args.output)
            return 0 if manifest.publishable else 2
        if args.command == "evaluate-molecular-atlas-fixture":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            report = evaluate_molecular_atlas_fixture(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "audit-molecular-atlas-data":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            report = audit_molecular_atlas_data(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "replay-molecular-atlas-fixtures":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            report = replay_molecular_atlas_evaluation(evaluation, fixture=fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "molecular-atlas-quality-gate":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            report = evaluate_molecular_atlas_quality_gate(fixture)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "evaluate-molecular-atlas-scenarios":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            report = evaluate_molecular_atlas_scenarios(fixture, report=evaluation)
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "molecular-atlas-contracts":
            _write_json(default_molecular_atlas_contracts().manifest(), args.output)
            return 0
        if args.command == "molecular-atlas-metrics":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            report = build_molecular_atlas_metrics(evaluation)
            failures = verify_molecular_atlas_metrics(report)
            _write_json(
                render_molecular_atlas_metrics(report)
                | {"accepted": report.accepted, "failures": list(failures)},
                args.output,
            )
            return 0 if report.accepted and not failures else 2
        if args.command == "build-molecular-atlas-bundle":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            builder = MolecularAtlasBundleBuilder()
            bundle = builder.build(
                evaluation,
                fixture=fixture,
                output_format=MolecularAtlasBundleFormat(args.format),
                accepted_only=args.accepted_only,
            )
            builder.write(bundle, args.output)
            return 0 if not builder.verify(bundle) else 2
        if args.command == "molecular-atlas-lineage":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            graph = build_molecular_atlas_lineage(evaluation, fixture=fixture)
            audit = graph.audit(evaluation)
            _write_json(
                graph.to_dict() | {"audit": audit.to_dict(), "accepted": audit.passed}, args.output
            )
            return 0 if audit.passed else 2
        if args.command == "molecular-atlas-reconciliation":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            data = audit_molecular_atlas_data(fixture)
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            replay = replay_molecular_atlas_evaluation(evaluation, fixture=fixture)
            scenarios = evaluate_molecular_atlas_scenarios(fixture, report=evaluation)
            graph = build_molecular_atlas_lineage(evaluation, fixture=fixture)
            report = reconcile_molecular_atlas_views(
                fixture, data, evaluation, replay, scenarios, graph
            )
            _write_json(report.to_dict(), args.output)
            return 0 if report.accepted else 2
        if args.command == "run-molecular-atlas-pipeline":
            report = run_molecular_atlas_pipeline_file(args.input)
            _write_json(report.to_dict(), args.output)
            return 0 if report.published else 2
        if args.command == "build-molecular-atlas-release":
            fixture = load_molecular_atlas_fixture(_read_json(args.input))
            evaluation = evaluate_molecular_atlas_fixture(fixture)
            quality = evaluate_molecular_atlas_quality_gate(fixture)
            replay = replay_molecular_atlas_evaluation(evaluation, fixture=fixture)
            bundle = MolecularAtlasBundleBuilder().build(
                evaluation, fixture=fixture, accepted_only=True
            )
            manifest = build_molecular_atlas_release_manifest(
                evaluation, quality, bundle, replay, fixture=fixture
            )
            write_molecular_atlas_release_manifest(manifest, args.output)
            return 0 if manifest.publishable else 2
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
        if args.command == "evaluate-atlas-alpha-evidence":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(evaluate_atlas_alpha_evidence_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-atlas-alpha-evidence-data":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(audit_atlas_alpha_evidence_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-atlas-alpha-evidence":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            _write_json(
                replay_atlas_alpha_evidence_evaluation(evaluation, fixture=fixture).to_dict(),
                args.output,
            )
            return 0
        if args.command == "atlas-alpha-evidence-quality-gate":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(run_atlas_alpha_evidence_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-atlas-alpha-evidence-scenarios":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(
                evaluate_atlas_alpha_evidence_scenarios(
                    evaluate_atlas_alpha_evidence_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "atlas-alpha-evidence-contracts":
            _write_json(default_atlas_alpha_evidence_contracts().manifest(), args.output)
            return 0
        if args.command == "atlas-alpha-evidence-schema":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            _write_json(
                atlas_alpha_evidence_schema_manifest()
                | {
                    "validation": validate_atlas_alpha_evidence_schema(
                        fixture, evaluation
                    ).to_dict()
                },
                args.output,
            )
            return 0
        if args.command == "atlas-alpha-evidence-metrics":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(
                compute_atlas_alpha_evidence_metrics(
                    evaluate_atlas_alpha_evidence_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "build-atlas-alpha-evidence-bundle":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            quality = run_atlas_alpha_evidence_quality_gate(fixture)
            _write_json(quality.bundle.to_dict(), args.output)
            return 0
        if args.command == "atlas-alpha-evidence-lineage":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            _write_json(
                build_atlas_alpha_evidence_lineage(fixture, evaluation).to_dict(), args.output
            )
            return 0
        if args.command == "atlas-alpha-evidence-reconciliation":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_json(
                reconcile_atlas_alpha_evidence(
                    fixture, evaluate_atlas_alpha_evidence_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "run-atlas-alpha-evidence-pipeline":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            options = AtlasAlphaEvidenceRuntimeOptions(
                run_id=args.run_id,
                fail_on_review=args.fail_on_review,
                requested_context_key=args.context_key,
            )
            _write_json(
                run_atlas_alpha_evidence_pipeline(options, fixture=fixture).to_dict(), args.output
            )
            return 0
        if args.command == "build-atlas-alpha-evidence-release":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            quality = run_atlas_alpha_evidence_quality_gate(fixture)
            runtime = run_atlas_alpha_evidence_pipeline(
                AtlasAlphaEvidenceRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_atlas_alpha_evidence_release(quality, runtime).to_dict(), args.output)
            return 0
        if args.command == "atlas-alpha-evidence-review-view":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            view = build_atlas_alpha_evidence_view(fixture, evaluation)
            _write_json(view.to_dict() | {"summary": review_queue_summary(view)}, args.output)
            return 0
        if args.command == "atlas-alpha-evidence-trace":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            runtime = run_atlas_alpha_evidence_pipeline(
                AtlasAlphaEvidenceRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_atlas_alpha_evidence_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-atlas-alpha-evidence-receipts-csv":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_text(
                export_atlas_alpha_evidence_receipts_csv(
                    evaluate_atlas_alpha_evidence_fixture(fixture)
                ),
                args.output,
            )
            return 0
        if args.command == "export-atlas-alpha-evidence-review-csv":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            _write_text(
                export_atlas_alpha_evidence_review_csv(
                    build_atlas_alpha_evidence_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-atlas-alpha-evidence-review-markdown":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            evaluation = evaluate_atlas_alpha_evidence_fixture(fixture)
            _write_text(
                render_atlas_alpha_evidence_review_markdown(
                    build_atlas_alpha_evidence_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-atlas-alpha-evidence-metrics-csv":
            fixture = _read_atlas_alpha_evidence_fixture(args.input)
            _write_text(
                export_atlas_alpha_evidence_metrics_csv(
                    compute_atlas_alpha_evidence_metrics(
                        evaluate_atlas_alpha_evidence_fixture(fixture)
                    )
                ),
                args.output,
            )
            return 0
        if args.command == "evaluate-frontier-atlas-fixture":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(evaluate_frontier_atlas_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-frontier-atlas-data":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(audit_frontier_atlas_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-frontier-atlas":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_json(
                replay_frontier_atlas_evaluation(evaluation, fixture=fixture).to_dict(),
                args.output,
            )
            return 0
        if args.command == "frontier-atlas-quality-gate":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(run_frontier_atlas_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-frontier-atlas-scenarios":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(
                evaluate_frontier_atlas_scenarios(
                    evaluate_frontier_atlas_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "frontier-atlas-contracts":
            _write_json(default_frontier_atlas_contracts().manifest(), args.output)
            return 0
        if args.command == "frontier-atlas-schema":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_json(
                frontier_atlas_schema_manifest()
                | {"validation": validate_frontier_atlas_schema(fixture, evaluation).to_dict()},
                args.output,
            )
            return 0
        if args.command == "frontier-atlas-metrics":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(
                compute_frontier_atlas_metrics(evaluate_frontier_atlas_fixture(fixture)).to_dict(),
                args.output,
            )
            return 0
        if args.command == "build-frontier-atlas-bundle":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_json(run_frontier_atlas_quality_gate(fixture).bundle.to_dict(), args.output)
            return 0
        if args.command == "frontier-atlas-lineage":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_json(build_frontier_atlas_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "frontier-atlas-reconciliation":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_json(reconcile_frontier_atlas(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "frontier-atlas-policy":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_json(evaluate_frontier_atlas_policy(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-frontier-atlas-pipeline":
            fixture = _read_frontier_atlas_fixture(args.input)
            options = FrontierAtlasRuntimeOptions(
                run_id=args.run_id,
                fail_on_review=args.fail_on_review,
                requested_context_key=args.context_key,
            )
            _write_json(
                run_frontier_atlas_pipeline(options, fixture=fixture).to_dict(), args.output
            )
            return 0
        if args.command == "build-frontier-atlas-release":
            fixture = _read_frontier_atlas_fixture(args.input)
            quality = run_frontier_atlas_quality_gate(fixture)
            runtime = run_frontier_atlas_pipeline(
                FrontierAtlasRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_frontier_atlas_release(quality, runtime).to_dict(), args.output)
            return 0
        if args.command == "frontier-atlas-review-view":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            view = build_frontier_atlas_view(fixture, evaluation)
            _write_json(
                view.to_dict() | {"summary": frontier_atlas_review_summary(view)}, args.output
            )
            return 0
        if args.command == "frontier-atlas-trace":
            fixture = _read_frontier_atlas_fixture(args.input)
            runtime = run_frontier_atlas_pipeline(
                FrontierAtlasRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_frontier_atlas_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-frontier-atlas-receipts-csv":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_text(
                export_frontier_atlas_receipts_csv(evaluate_frontier_atlas_fixture(fixture)),
                args.output,
            )
            return 0
        if args.command == "export-frontier-atlas-review-csv":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_text(
                export_frontier_atlas_review_csv(build_frontier_atlas_view(fixture, evaluation)),
                args.output,
            )
            return 0
        if args.command == "export-frontier-atlas-review-markdown":
            fixture = _read_frontier_atlas_fixture(args.input)
            evaluation = evaluate_frontier_atlas_fixture(fixture)
            _write_text(
                render_frontier_atlas_review_markdown(
                    build_frontier_atlas_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-frontier-atlas-metrics-csv":
            fixture = _read_frontier_atlas_fixture(args.input)
            _write_text(
                export_frontier_atlas_metrics_csv(
                    compute_frontier_atlas_metrics(evaluate_frontier_atlas_fixture(fixture))
                ),
                args.output,
            )
            return 0
        if args.command == "evaluate-sequence-frontier-fixture":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(evaluate_sequence_frontier_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-sequence-frontier-data":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(audit_sequence_frontier_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-sequence-frontier":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_json(
                replay_sequence_frontier_evaluation(evaluation, fixture=fixture).to_dict(),
                args.output,
            )
            return 0
        if args.command == "sequence-frontier-quality-gate":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(run_sequence_frontier_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-sequence-frontier-scenarios":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(
                evaluate_sequence_frontier_scenarios(
                    evaluate_sequence_frontier_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "sequence-frontier-policy":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_json(
                evaluate_sequence_frontier_policy(fixture, evaluation).to_dict(), args.output
            )
            return 0
        if args.command == "sequence-frontier-contracts":
            _write_json(default_sequence_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "sequence-frontier-schema":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_json(
                sequence_frontier_schema_manifest()
                | {"validation": validate_sequence_frontier_schema(fixture, evaluation).to_dict()},
                args.output,
            )
            return 0
        if args.command == "sequence-frontier-metrics":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(
                compute_sequence_frontier_metrics(
                    evaluate_sequence_frontier_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "build-sequence-frontier-bundle":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_json(run_sequence_frontier_quality_gate(fixture).bundle.to_dict(), args.output)
            return 0
        if args.command == "sequence-frontier-lineage":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_json(build_sequence_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "sequence-frontier-reconciliation":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_json(reconcile_sequence_frontier(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-sequence-frontier-pipeline":
            fixture = _read_sequence_frontier_fixture(args.input)
            options = SequenceFrontierRuntimeOptions(
                run_id=args.run_id,
                fail_on_review=args.fail_on_review,
                requested_context_key=args.context_key,
            )
            _write_json(
                run_sequence_frontier_pipeline(options, fixture=fixture).to_dict(), args.output
            )
            return 0
        if args.command == "build-sequence-frontier-release":
            fixture = _read_sequence_frontier_fixture(args.input)
            quality = run_sequence_frontier_quality_gate(fixture)
            runtime = run_sequence_frontier_pipeline(
                SequenceFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_sequence_frontier_release(quality, runtime).to_dict(), args.output)
            return 0
        if args.command == "sequence-frontier-review-view":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            view = build_sequence_frontier_view(fixture, evaluation)
            _write_json(
                view.to_dict() | {"summary": sequence_frontier_review_summary(view)}, args.output
            )
            return 0
        if args.command == "sequence-frontier-trace":
            fixture = _read_sequence_frontier_fixture(args.input)
            runtime = run_sequence_frontier_pipeline(
                SequenceFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_sequence_frontier_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-sequence-frontier-receipts-csv":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_text(
                export_sequence_frontier_receipts_csv(evaluate_sequence_frontier_fixture(fixture)),
                args.output,
            )
            return 0
        if args.command == "export-sequence-frontier-review-csv":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_text(
                export_sequence_frontier_review_csv(
                    build_sequence_frontier_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-sequence-frontier-review-markdown":
            fixture = _read_sequence_frontier_fixture(args.input)
            evaluation = evaluate_sequence_frontier_fixture(fixture)
            _write_text(
                render_sequence_frontier_review_markdown(
                    build_sequence_frontier_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-sequence-frontier-metrics-csv":
            fixture = _read_sequence_frontier_fixture(args.input)
            _write_text(
                export_sequence_frontier_metrics_csv(
                    compute_sequence_frontier_metrics(evaluate_sequence_frontier_fixture(fixture))
                ),
                args.output,
            )
            return 0
        if args.command == "evaluate-chromatin-frontier-fixture":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(evaluate_chromatin_frontier_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-chromatin-frontier-data":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(audit_chromatin_frontier_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-chromatin-frontier":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_json(
                replay_chromatin_frontier_evaluation(evaluation, fixture=fixture).to_dict(),
                args.output,
            )
            return 0
        if args.command == "chromatin-frontier-quality-gate":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(run_chromatin_frontier_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-chromatin-frontier-scenarios":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(
                evaluate_chromatin_frontier_scenarios(
                    evaluate_chromatin_frontier_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "chromatin-frontier-policy":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_json(
                evaluate_chromatin_frontier_policy(fixture, evaluation).to_dict(), args.output
            )
            return 0
        if args.command == "chromatin-frontier-contracts":
            _write_json(default_chromatin_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "chromatin-frontier-schema":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_json(
                chromatin_frontier_schema_manifest()
                | {"validation": validate_chromatin_frontier_schema(fixture, evaluation).to_dict()},
                args.output,
            )
            return 0
        if args.command == "chromatin-frontier-metrics":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(
                compute_chromatin_frontier_metrics(
                    evaluate_chromatin_frontier_fixture(fixture)
                ).to_dict(),
                args.output,
            )
            return 0
        if args.command == "build-chromatin-frontier-bundle":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_json(run_chromatin_frontier_quality_gate(fixture).bundle.to_dict(), args.output)
            return 0
        if args.command == "chromatin-frontier-lineage":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_json(
                build_chromatin_frontier_lineage(fixture, evaluation).to_dict(), args.output
            )
            return 0
        if args.command == "chromatin-frontier-reconciliation":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_json(reconcile_chromatin_frontier(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-chromatin-frontier-pipeline":
            fixture = _read_chromatin_frontier_fixture(args.input)
            options = ChromatinFrontierRuntimeOptions(
                run_id=args.run_id,
                fail_on_review=args.fail_on_review,
                requested_context_key=args.context_key,
            )
            _write_json(
                run_chromatin_frontier_pipeline(options, fixture=fixture).to_dict(), args.output
            )
            return 0
        if args.command == "build-chromatin-frontier-release":
            fixture = _read_chromatin_frontier_fixture(args.input)
            quality = run_chromatin_frontier_quality_gate(fixture)
            runtime = run_chromatin_frontier_pipeline(
                ChromatinFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_chromatin_frontier_release(quality, runtime).to_dict(), args.output)
            return 0
        if args.command == "chromatin-frontier-review-view":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            view = build_chromatin_frontier_view(fixture, evaluation)
            _write_json(
                view.to_dict() | {"summary": chromatin_frontier_review_summary(view)}, args.output
            )
            return 0
        if args.command == "chromatin-frontier-trace":
            fixture = _read_chromatin_frontier_fixture(args.input)
            runtime = run_chromatin_frontier_pipeline(
                ChromatinFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture
            )
            _write_json(build_chromatin_frontier_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-chromatin-frontier-receipts-csv":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_text(
                export_chromatin_frontier_receipts_csv(
                    evaluate_chromatin_frontier_fixture(fixture)
                ),
                args.output,
            )
            return 0
        if args.command == "export-chromatin-frontier-review-csv":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_text(
                export_chromatin_frontier_review_csv(
                    build_chromatin_frontier_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-chromatin-frontier-review-markdown":
            fixture = _read_chromatin_frontier_fixture(args.input)
            evaluation = evaluate_chromatin_frontier_fixture(fixture)
            _write_text(
                render_chromatin_frontier_review_markdown(
                    build_chromatin_frontier_view(fixture, evaluation)
                ),
                args.output,
            )
            return 0
        if args.command == "export-chromatin-frontier-metrics-csv":
            fixture = _read_chromatin_frontier_fixture(args.input)
            _write_text(
                export_chromatin_frontier_metrics_csv(
                    compute_chromatin_frontier_metrics(evaluate_chromatin_frontier_fixture(fixture))
                ),
                args.output,
            )
            return 0
        if args.command == "evaluate-cell-state-frontier-fixture":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(evaluate_cell_state_frontier_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-cell-state-frontier-data":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(audit_cell_state_frontier_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-cell-state-frontier":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_json(replay_cell_state_frontier_evaluation(evaluation, fixture=fixture).to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-quality-gate":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(run_cell_state_frontier_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-cell-state-frontier-scenarios":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(evaluate_cell_state_frontier_scenarios(evaluate_cell_state_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-policy":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_json(evaluate_cell_state_frontier_policy(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-contracts":
            _write_json(default_cell_state_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "cell-state-frontier-schema":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_json(cell_state_frontier_schema_manifest() | {"validation": validate_cell_state_frontier_schema(fixture, evaluation).to_dict()}, args.output)
            return 0
        if args.command == "cell-state-frontier-metrics":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(compute_cell_state_frontier_metrics(evaluate_cell_state_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "build-cell-state-frontier-bundle":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_json(run_cell_state_frontier_quality_gate(fixture).bundle.to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-lineage":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_json(build_cell_state_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-reconciliation":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_json(reconcile_cell_state_frontier(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-cell-state-frontier-pipeline":
            fixture = _read_cell_state_frontier_fixture(args.input)
            options = CellStateFrontierRuntimeOptions(run_id=args.run_id, fail_on_review=args.fail_on_review, requested_context_key=args.context_key)
            _write_json(run_cell_state_frontier_pipeline(options, fixture=fixture).to_dict(), args.output)
            return 0
        if args.command == "build-cell-state-frontier-release":
            fixture = _read_cell_state_frontier_fixture(args.input)
            quality = run_cell_state_frontier_quality_gate(fixture)
            runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture)
            _write_json(build_cell_state_frontier_release(quality, runtime).to_dict(), args.output)
            return 0
        if args.command == "cell-state-frontier-review-view":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            view = build_cell_state_frontier_view(fixture, evaluation)
            _write_json(view.to_dict() | {"summary": cell_state_frontier_review_summary(view)}, args.output)
            return 0
        if args.command == "cell-state-frontier-trace":
            fixture = _read_cell_state_frontier_fixture(args.input)
            runtime = run_cell_state_frontier_pipeline(CellStateFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture)
            _write_json(build_cell_state_frontier_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-cell-state-frontier-receipts-csv":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_text(export_cell_state_frontier_receipts_csv(evaluate_cell_state_frontier_fixture(fixture)), args.output)
            return 0
        if args.command == "export-cell-state-frontier-review-csv":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_text(export_cell_state_frontier_review_csv(build_cell_state_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-cell-state-frontier-review-markdown":
            fixture = _read_cell_state_frontier_fixture(args.input)
            evaluation = evaluate_cell_state_frontier_fixture(fixture)
            _write_text(render_cell_state_frontier_review_markdown(build_cell_state_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-cell-state-frontier-metrics-csv":
            fixture = _read_cell_state_frontier_fixture(args.input)
            _write_text(export_cell_state_frontier_metrics_csv(compute_cell_state_frontier_metrics(evaluate_cell_state_frontier_fixture(fixture))), args.output)
            return 0
        if args.command == "evaluate-link-frontier-fixture":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(evaluate_link_frontier_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-link-frontier-data":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(audit_link_frontier_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-link-frontier":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_json(replay_link_frontier_evaluation(fixture, first=evaluation).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-quality-gate":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(run_link_frontier_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-link-frontier-scenarios":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(evaluate_link_frontier_scenarios(fixture).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-policy":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_json(evaluate_link_frontier_policy(fixture, evaluation=evaluation).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-contracts":
            _write_json(default_link_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "link-frontier-schema":
            fixture = _read_link_frontier_fixture(args.input)
            schemas = default_link_frontier_schemas()
            _write_json({"schemas": [item.to_dict() for item in schemas], "validation": validate_link_frontier_schema(fixture).to_dict()}, args.output)
            return 0
        if args.command == "link-frontier-metrics":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(compute_link_frontier_metrics(fixture, evaluate_link_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "build-link-frontier-bundle":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            lineage = build_link_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_link_frontier(fixture, evaluation)
            policy = evaluate_link_frontier_policy(fixture, evaluation=evaluation)
            metrics = compute_link_frontier_metrics(fixture, evaluation)
            _write_json(build_link_frontier_bundle(fixture, evaluation, reconciliation, lineage, metrics, policy).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-lineage":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_json(build_link_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-reconciliation":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_json(reconcile_link_frontier(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-link-frontier-pipeline":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(run_link_frontier_pipeline(fixture).to_dict(), args.output)
            return 0
        if args.command == "build-link-frontier-release":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(build_link_frontier_release(fixture, release_id=args.release_id).to_dict(), args.output)
            return 0
        if args.command == "link-frontier-review-view":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            view = build_link_frontier_view(fixture, evaluation)
            _write_json(view.to_dict() | {"summary": link_frontier_review_summary(view)}, args.output)
            return 0
        if args.command == "link-frontier-trace":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(build_link_frontier_trace(run_link_frontier_pipeline(fixture), run_id=args.run_id).to_dict(), args.output)
            return 0
        if args.command == "export-link-frontier-receipts-csv":
            fixture = _read_link_frontier_fixture(args.input)
            _write_text(export_link_frontier_receipts_csv(evaluate_link_frontier_fixture(fixture)), args.output)
            return 0
        if args.command == "export-link-frontier-review-csv":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_text(export_link_frontier_review_csv(build_link_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-link-frontier-review-markdown":
            fixture = _read_link_frontier_fixture(args.input)
            evaluation = evaluate_link_frontier_fixture(fixture)
            _write_text(render_link_frontier_review_markdown(build_link_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-link-frontier-metrics-csv":
            fixture = _read_link_frontier_fixture(args.input)
            _write_text(export_link_frontier_metrics_csv(compute_link_frontier_metrics(fixture, evaluate_link_frontier_fixture(fixture))), args.output)
            return 0
        if args.command == "link-frontier-depth-audit":
            fixture = _read_link_frontier_fixture(args.input)
            _write_json(run_link_frontier_depth_audit(fixture).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-data-audit":
            _write_json(audit_causal_frontier_data(_read_causal_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-contracts":
            _write_json(default_causal_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "causal-frontier-schema":
            _write_json(default_causal_frontier_schema().to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-evaluate":
            _write_json(evaluate_causal_frontier_fixture(_read_causal_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-replay":
            _write_json(replay_causal_frontier(_read_causal_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-metrics":
            fixture = _read_causal_frontier_fixture(args.input)
            _write_json(measure_causal_frontier(evaluate_causal_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-lineage":
            fixture = _read_causal_frontier_fixture(args.input)
            evaluation = evaluate_causal_frontier_fixture(fixture)
            _write_json(build_causal_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-policy":
            fixture = _read_causal_frontier_fixture(args.input)
            contracts = default_causal_frontier_contracts()
            evaluation = evaluate_causal_frontier_fixture(fixture)
            _write_json({"policy": default_causal_frontier_policy(contracts).to_dict(), "decisions": [item.to_dict() for item in default_causal_frontier_policy(contracts).decide(evaluation)]}, args.output)
            return 0
        if args.command == "causal-frontier-quality-gate":
            fixture = _read_causal_frontier_fixture(args.input)
            contracts = default_causal_frontier_contracts()
            schema = default_causal_frontier_schema()
            evaluation = evaluate_causal_frontier_fixture(fixture)
            policy = default_causal_frontier_policy(contracts)
            lineage = build_causal_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_causal_frontier(fixture, evaluation, policy)
            _write_json(evaluate_causal_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-runtime":
            _write_json(run_causal_frontier_runtime(_read_causal_frontier_fixture(args.input), run_id="causal-frontier-cli").to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-release":
            fixture = _read_causal_frontier_fixture(args.input)
            runtime = run_causal_frontier_runtime(fixture, run_id="causal-frontier-release")
            contracts = default_causal_frontier_contracts()
            evaluation = evaluate_causal_frontier_fixture(fixture)
            schema = default_causal_frontier_schema()
            policy = default_causal_frontier_policy(contracts)
            lineage = build_causal_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_causal_frontier(fixture, evaluation, policy)
            gate = evaluate_causal_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
            replay = replay_causal_frontier(fixture, replay_id="causal-frontier-release-replay")
            _write_json(build_causal_frontier_release_manifest(runtime.bundle, gate, replay).to_dict(), args.output)
            return 0
        if args.command == "causal-frontier-depth-audit":
            _write_json(audit_causal_frontier_depth().to_dict(), args.output)
            return 0
        if args.command == "export-causal-frontier-review-csv":
            fixture = _read_causal_frontier_fixture(args.input)
            evaluation = evaluate_causal_frontier_fixture(fixture)
            metrics = measure_causal_frontier(evaluation)
            contracts = default_causal_frontier_contracts()
            policy = default_causal_frontier_policy(contracts)
            lineage = build_causal_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_causal_frontier(fixture, evaluation, policy)
            gate = evaluate_causal_frontier_quality(fixture, evaluation, contracts, default_causal_frontier_schema(), lineage, reconciliation)
            runtime = run_causal_frontier_runtime(fixture, run_id="causal-frontier-csv")
            release = build_causal_frontier_release_manifest(runtime.bundle, gate, replay_causal_frontier(fixture, replay_id="causal-frontier-csv-replay"))
            _write_text(export_causal_frontier_review_csv(build_causal_frontier_review_view(fixture, evaluation, metrics, policy.decide(evaluation), release)), args.output)
            return 0
        if args.command == "cohort-frontier-data-audit":
            _write_json(audit_cohort_frontier_data(_read_cohort_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-contracts":
            _write_json(default_cohort_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "cohort-frontier-schema":
            _write_json(default_cohort_frontier_schema().to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-evaluate":
            _write_json(evaluate_cohort_frontier_fixture(_read_cohort_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-replay":
            _write_json(replay_cohort_frontier(_read_cohort_frontier_fixture(args.input), replay_id="cohort-frontier-cli-replay").to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-metrics":
            fixture = _read_cohort_frontier_fixture(args.input)
            _write_json(measure_cohort_frontier(evaluate_cohort_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-lineage":
            fixture = _read_cohort_frontier_fixture(args.input)
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            _write_json(build_cohort_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-policy":
            fixture = _read_cohort_frontier_fixture(args.input)
            contracts = default_cohort_frontier_contracts()
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            policy = default_cohort_frontier_policy(contracts)
            _write_json({"policy": policy.to_dict(), "decisions": [item.to_dict() for item in policy.decide(evaluation)]}, args.output)
            return 0
        if args.command == "cohort-frontier-quality-gate":
            fixture = _read_cohort_frontier_fixture(args.input)
            contracts = default_cohort_frontier_contracts()
            schema = default_cohort_frontier_schema()
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            policy = default_cohort_frontier_policy(contracts)
            lineage = build_cohort_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
            _write_json(evaluate_cohort_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-runtime":
            _write_json(run_cohort_frontier_runtime(_read_cohort_frontier_fixture(args.input), run_id="cohort-frontier-cli").to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-bundle":
            fixture = _read_cohort_frontier_fixture(args.input)
            contracts = default_cohort_frontier_contracts()
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            metrics = measure_cohort_frontier(evaluation)
            policy = default_cohort_frontier_policy(contracts)
            lineage = build_cohort_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
            _write_json(assemble_cohort_frontier_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-release":
            fixture = _read_cohort_frontier_fixture(args.input)
            runtime = run_cohort_frontier_runtime(fixture, run_id="cohort-frontier-release")
            contracts = default_cohort_frontier_contracts()
            schema = default_cohort_frontier_schema()
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            policy = default_cohort_frontier_policy(contracts)
            lineage = build_cohort_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
            gate = evaluate_cohort_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation)
            replay = replay_cohort_frontier(fixture, replay_id="cohort-frontier-release-replay")
            _write_json(build_cohort_frontier_release_manifest(runtime.bundle, gate, replay).to_dict(), args.output)
            return 0
        if args.command == "cohort-frontier-depth-audit":
            _write_json(audit_cohort_frontier_depth().to_dict(), args.output)
            return 0
        if args.command == "export-cohort-frontier-review-csv":
            fixture = _read_cohort_frontier_fixture(args.input)
            evaluation = evaluate_cohort_frontier_fixture(fixture)
            metrics = measure_cohort_frontier(evaluation)
            contracts = default_cohort_frontier_contracts()
            policy = default_cohort_frontier_policy(contracts)
            lineage = build_cohort_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_cohort_frontier(fixture, evaluation, policy)
            gate = evaluate_cohort_frontier_quality(fixture, evaluation, contracts, default_cohort_frontier_schema(), lineage, reconciliation)
            runtime = run_cohort_frontier_runtime(fixture, run_id="cohort-frontier-csv")
            release = build_cohort_frontier_release_manifest(runtime.bundle, gate, replay_cohort_frontier(fixture, replay_id="cohort-frontier-csv-replay"))
            view = build_cohort_frontier_review_view(fixture, evaluation, metrics, policy.decide(evaluation), release)
            _write_text(export_cohort_frontier_review_csv(view), args.output)
            return 0
        if args.command == "evidence-lifecycle-data-audit":
            _write_json(audit_evidence_lifecycle_data(_read_evidence_lifecycle_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-contracts":
            _write_json(default_evidence_lifecycle_contracts().manifest(), args.output)
            return 0
        if args.command == "evidence-lifecycle-schema":
            _write_json(default_evidence_lifecycle_schema().to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-evaluate":
            _write_json(evaluate_evidence_lifecycle_fixture(_read_evidence_lifecycle_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-replay":
            _write_json(replay_evidence_lifecycle(_read_evidence_lifecycle_fixture(args.input), replay_id="evidence-lifecycle-cli-replay").to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-metrics":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            _write_json(measure_evidence_lifecycle(evaluate_evidence_lifecycle_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-lineage":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            _write_json(build_evidence_lifecycle_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-policy":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            policy = default_evidence_lifecycle_policy()
            _write_json({"policy": policy.to_dict(), "decisions": [item.to_dict() for item in policy.decide(evaluation)]}, args.output)
            return 0
        if args.command == "evidence-lifecycle-quality-gate":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            contracts = default_evidence_lifecycle_contracts()
            schema = default_evidence_lifecycle_schema()
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            policy = default_evidence_lifecycle_policy()
            lineage = build_evidence_lifecycle_lineage(fixture, evaluation)
            reconciliation = reconcile_evidence_lifecycle(fixture, evaluation, policy)
            _write_json(evaluate_evidence_lifecycle_quality(fixture, evaluation, contracts, schema, lineage, reconciliation).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-runtime":
            _write_json(run_evidence_lifecycle_runtime(_read_evidence_lifecycle_fixture(args.input), run_id="evidence-lifecycle-cli").to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-observability":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            runtime = run_evidence_lifecycle_runtime(fixture, run_id="evidence-lifecycle-observability")
            _write_json(observe_evidence_lifecycle(runtime, evaluate_evidence_lifecycle_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-artifacts":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            contracts = default_evidence_lifecycle_contracts()
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            metrics = measure_evidence_lifecycle(evaluation)
            policy = default_evidence_lifecycle_policy()
            lineage = build_evidence_lifecycle_lineage(fixture, evaluation)
            reconciliation = reconcile_evidence_lifecycle(fixture, evaluation, policy)
            gate = evaluate_evidence_lifecycle_quality(fixture, evaluation, contracts, default_evidence_lifecycle_schema(), lineage, reconciliation)
            runtime = run_evidence_lifecycle_runtime(fixture, run_id="evidence-lifecycle-artifacts")
            bundle = runtime.bundle
            release = build_evidence_lifecycle_release_manifest(bundle, gate, replay_evidence_lifecycle(fixture, replay_id="evidence-lifecycle-artifacts-replay"))
            _write_json(build_evidence_lifecycle_artifact_inventory(fixture, evaluation, metrics, gate, runtime, release, bundle).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-bundle":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            metrics = measure_evidence_lifecycle(evaluation)
            policy = default_evidence_lifecycle_policy()
            lineage = build_evidence_lifecycle_lineage(fixture, evaluation)
            reconciliation = reconcile_evidence_lifecycle(fixture, evaluation, policy)
            _write_json(assemble_evidence_lifecycle_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-release":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            runtime = run_evidence_lifecycle_runtime(fixture, run_id="evidence-lifecycle-release")
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            contracts = default_evidence_lifecycle_contracts()
            policy = default_evidence_lifecycle_policy()
            lineage = build_evidence_lifecycle_lineage(fixture, evaluation)
            reconciliation = reconcile_evidence_lifecycle(fixture, evaluation, policy)
            gate = evaluate_evidence_lifecycle_quality(fixture, evaluation, contracts, default_evidence_lifecycle_schema(), lineage, reconciliation)
            _write_json(build_evidence_lifecycle_release_manifest(runtime.bundle, gate, replay_evidence_lifecycle(fixture, replay_id="evidence-lifecycle-release-replay")).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-review-queue":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            policy = default_evidence_lifecycle_policy()
            _write_json(build_evidence_lifecycle_review_queue(fixture, evaluation, policy.decide(evaluation)).to_dict(), args.output)
            return 0
        if args.command == "evidence-lifecycle-depth-audit":
            _write_json(audit_evidence_lifecycle_depth().to_dict(), args.output)
            return 0
        if args.command == "export-evidence-lifecycle-review-csv":
            fixture = _read_evidence_lifecycle_fixture(args.input)
            evaluation = evaluate_evidence_lifecycle_fixture(fixture)
            policy = default_evidence_lifecycle_policy()
            metrics = measure_evidence_lifecycle(evaluation)
            lineage = build_evidence_lifecycle_lineage(fixture, evaluation)
            reconciliation = reconcile_evidence_lifecycle(fixture, evaluation, policy)
            gate = evaluate_evidence_lifecycle_quality(fixture, evaluation, default_evidence_lifecycle_contracts(), default_evidence_lifecycle_schema(), lineage, reconciliation)
            runtime = run_evidence_lifecycle_runtime(fixture, run_id="evidence-lifecycle-csv")
            release = build_evidence_lifecycle_release_manifest(runtime.bundle, gate, replay_evidence_lifecycle(fixture, replay_id="evidence-lifecycle-csv-replay"))
            view = build_evidence_lifecycle_review_view(fixture, evaluation, policy.decide(evaluation), release)
            _write_text(export_evidence_lifecycle_review_csv(view), args.output)
            return 0
        if args.command == "validation-frontier-data-audit":
            _write_json(audit_validation_frontier_data(_read_validation_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-contracts":
            _write_json(default_validation_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "validation-frontier-schema":
            _write_json(default_validation_frontier_schema().to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-evaluate":
            _write_json(evaluate_validation_frontier_fixture(_read_validation_frontier_fixture(args.input)).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-replay":
            _write_json(replay_validation_frontier(_read_validation_frontier_fixture(args.input), replay_id="validation-frontier-cli-replay").to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-metrics":
            fixture = _read_validation_frontier_fixture(args.input)
            _write_json(measure_validation_frontier(evaluate_validation_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-lineage":
            fixture = _read_validation_frontier_fixture(args.input)
            evaluation = evaluate_validation_frontier_fixture(fixture)
            _write_json(build_validation_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-policy":
            fixture = _read_validation_frontier_fixture(args.input)
            contracts = default_validation_frontier_contracts()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            policy = default_validation_frontier_policy(contracts)
            _write_json({"policy": policy.to_dict(), "decisions": [item.to_dict() for item in policy.decide(evaluation)]}, args.output)
            return 0
        if args.command == "validation-frontier-quality-gate":
            fixture = _read_validation_frontier_fixture(args.input)
            contracts = default_validation_frontier_contracts()
            schema = default_validation_frontier_schema()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            policy = default_validation_frontier_policy(contracts)
            lineage = build_validation_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
            _write_json(evaluate_validation_frontier_quality(fixture, evaluation, contracts, schema, lineage, reconciliation).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-runtime":
            _write_json(run_validation_frontier_runtime(_read_validation_frontier_fixture(args.input), run_id="validation-frontier-cli").to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-observability":
            fixture = _read_validation_frontier_fixture(args.input)
            runtime = run_validation_frontier_runtime(fixture, run_id="validation-frontier-observability")
            _write_json(observe_validation_frontier(runtime, evaluate_validation_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-artifacts":
            fixture = _read_validation_frontier_fixture(args.input)
            contracts = default_validation_frontier_contracts()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            metrics = measure_validation_frontier(evaluation)
            policy = default_validation_frontier_policy(contracts)
            lineage = build_validation_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
            gate = evaluate_validation_frontier_quality(fixture, evaluation, contracts, default_validation_frontier_schema(), lineage, reconciliation)
            runtime = run_validation_frontier_runtime(fixture, run_id="validation-frontier-artifacts")
            release = build_validation_frontier_release_manifest(runtime.bundle, gate, replay_validation_frontier(fixture, replay_id="validation-frontier-artifacts-replay"))
            _write_json(build_validation_frontier_artifact_inventory(fixture, evaluation, metrics, lineage, gate, runtime, release).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-bundle":
            fixture = _read_validation_frontier_fixture(args.input)
            contracts = default_validation_frontier_contracts()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            metrics = measure_validation_frontier(evaluation)
            policy = default_validation_frontier_policy(contracts)
            lineage = build_validation_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
            _write_json(assemble_validation_frontier_bundle(fixture, evaluation, metrics, lineage, reconciliation, policy).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-release":
            fixture = _read_validation_frontier_fixture(args.input)
            runtime = run_validation_frontier_runtime(fixture, run_id="validation-frontier-release")
            contracts = default_validation_frontier_contracts()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            policy = default_validation_frontier_policy(contracts)
            lineage = build_validation_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
            gate = evaluate_validation_frontier_quality(fixture, evaluation, contracts, default_validation_frontier_schema(), lineage, reconciliation)
            replay = replay_validation_frontier(fixture, replay_id="validation-frontier-release-replay")
            _write_json(build_validation_frontier_release_manifest(runtime.bundle, gate, replay).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-review-queue":
            fixture = _read_validation_frontier_fixture(args.input)
            contracts = default_validation_frontier_contracts()
            evaluation = evaluate_validation_frontier_fixture(fixture)
            policy = default_validation_frontier_policy(contracts)
            _write_json(build_validation_frontier_review_queue(fixture, evaluation, policy.decide(evaluation)).to_dict(), args.output)
            return 0
        if args.command == "validation-frontier-depth-audit":
            _write_json(audit_validation_frontier_depth().to_dict(), args.output)
            return 0
        if args.command == "export-validation-frontier-review-csv":
            fixture = _read_validation_frontier_fixture(args.input)
            evaluation = evaluate_validation_frontier_fixture(fixture)
            metrics = measure_validation_frontier(evaluation)
            contracts = default_validation_frontier_contracts()
            policy = default_validation_frontier_policy(contracts)
            lineage = build_validation_frontier_lineage(fixture, evaluation)
            reconciliation = reconcile_validation_frontier(fixture, evaluation, policy)
            gate = evaluate_validation_frontier_quality(fixture, evaluation, contracts, default_validation_frontier_schema(), lineage, reconciliation)
            runtime = run_validation_frontier_runtime(fixture, run_id="validation-frontier-csv")
            release = build_validation_frontier_release_manifest(runtime.bundle, gate, replay_validation_frontier(fixture, replay_id="validation-frontier-csv-replay"))
            view = build_validation_frontier_review_view(fixture, evaluation, metrics, policy.decide(evaluation), release)
            _write_text(export_validation_frontier_review_csv(view), args.output)
            return 0
        if args.command == "evaluate-topology-frontier-fixture":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(evaluate_topology_frontier_fixture(fixture).to_dict(), args.output)
            return 0
        if args.command == "audit-topology-frontier-data":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(audit_topology_frontier_data(fixture).to_dict(), args.output)
            return 0
        if args.command == "replay-topology-frontier":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_json(replay_topology_frontier_evaluation(evaluation, fixture=fixture).to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-quality-gate":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(run_topology_frontier_quality_gate(fixture).to_dict(), args.output)
            return 0
        if args.command == "evaluate-topology-frontier-scenarios":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_json(evaluate_topology_frontier_scenarios(evaluation, fixture=fixture).to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-policy":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_json(evaluate_topology_frontier_policy(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-contracts":
            _write_json(default_topology_frontier_contracts().manifest(), args.output)
            return 0
        if args.command == "topology-frontier-schema":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            schemas = default_topology_frontier_schemas()
            _write_json({"schemas": [item.to_dict() for item in schemas], "validation": validate_topology_frontier_schema(evaluation, schemas=schemas).to_dict()}, args.output)
            return 0
        if args.command == "topology-frontier-metrics":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(compute_topology_frontier_metrics(evaluate_topology_frontier_fixture(fixture)).to_dict(), args.output)
            return 0
        if args.command == "build-topology-frontier-bundle":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(run_topology_frontier_quality_gate(fixture).bundle.to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-lineage":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_json(build_topology_frontier_lineage(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-reconciliation":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_json(reconcile_topology_frontier(fixture, evaluation).to_dict(), args.output)
            return 0
        if args.command == "run-topology-frontier-pipeline":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_json(run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture).to_dict(), args.output)
            return 0
        if args.command == "build-topology-frontier-release":
            fixture = _read_topology_frontier_fixture(args.input)
            quality = run_topology_frontier_quality_gate(fixture)
            _write_json(build_topology_frontier_release(quality, run_id=args.run_id, release_id=args.release_id).to_dict(), args.output)
            return 0
        if args.command == "topology-frontier-review-view":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            view = build_topology_frontier_view(fixture, evaluation)
            _write_json(view.to_dict() | {"summary": topology_frontier_review_summary(view)}, args.output)
            return 0
        if args.command == "topology-frontier-trace":
            fixture = _read_topology_frontier_fixture(args.input)
            runtime = run_topology_frontier_pipeline(TopologyFrontierRuntimeOptions(run_id=args.run_id), fixture=fixture)
            _write_json(build_topology_frontier_trace(runtime).to_dict(), args.output)
            return 0
        if args.command == "export-topology-frontier-receipts-csv":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_text(export_topology_frontier_receipts_csv(evaluate_topology_frontier_fixture(fixture)), args.output)
            return 0
        if args.command == "export-topology-frontier-review-csv":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_text(export_topology_frontier_review_csv(build_topology_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-topology-frontier-review-markdown":
            fixture = _read_topology_frontier_fixture(args.input)
            evaluation = evaluate_topology_frontier_fixture(fixture)
            _write_text(render_topology_frontier_review_markdown(build_topology_frontier_view(fixture, evaluation)), args.output)
            return 0
        if args.command == "export-topology-frontier-metrics-csv":
            fixture = _read_topology_frontier_fixture(args.input)
            _write_text(export_topology_frontier_metrics_csv(compute_topology_frontier_metrics(evaluate_topology_frontier_fixture(fixture))), args.output)
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
