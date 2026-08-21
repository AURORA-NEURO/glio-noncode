"""Executable bindings from bounded control-plane tools to domain modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import partial
from tempfile import TemporaryDirectory
from typing import Any

from .assay_qc import AssayQCEvaluator, AssayQCObservation, QCStatus
from .atlas import AtlasQuery, PublicAtlasRetriever
from .atlas_context import ATLAS_ROLE_CHANNELS, ContextEvidenceBuilder, ContextObservation
from .benchmarks import BenchmarkExample, BenchmarkRunner
from .causal import CausalLattice
from .cohort import CohortObservation, RecurrenceModel
from .control_plane import (
    Abstention,
    ArbitrationResult,
    ControlPlaneExecutor,
    ControlPolicyDecision,
    EvidenceArbiter,
    EvidenceEnvelope,
    InvocationRequest,
    MissionPlanner,
    ReviewRoute,
    ScheduleDecision,
    TypedInvocationError,
    WorkflowDecision,
    default_control_plane_registry,
)
from .controls import ExportTarget, LocalDataController, default_local_policy
from .data_sources import FetchReceipt, FetchStatus, SequenceSlice
from .errors import ValidationError
from .evidence import EvidenceGraph
from .identity import normalize_variant, parse_variant
from .inference_extensions import InferenceExtensionSuite
from .intake import RawVariantRecord, VariantIntake
from .lifecycle import DriftMonitor, LifecycleReclassifier, ReviewPacketBuilder
from .lineage import LineageResolver, SampleLineageRecord
from .models import (
    AssayType,
    CandidateElement,
    CaseManifest,
    Dossier,
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    ExperimentOption,
    Hypothesis,
    HypothesisEdge,
    ReferenceContext,
    ResearchStatus,
    ReviewDecision,
    ReviewState,
    SupportLevel,
)
from .origin import OriginClonalityAssessor, OriginObservation
from .reference_registry import (
    MappingCatalog,
    MappingSegment,
    ProjectionStatus,
    ReferenceProjector,
    default_reference_registry,
)
from .reports import render_json, render_markdown, summarize
from .sequence_inference import (
    MotifDefinition,
    SequenceAnalysisResult,
    SequenceAnalysisState,
    SequenceInference,
)
from .serialization import content_hash
from .structural_reconstruction import StructuralReconstructor
from .uncertainty import (
    CalibrationEvaluator,
    DomainProfile,
    OODAssessment,
    OODStatus,
    OutOfDomainDetector,
    UncertaintyBand,
    UncertaintyComponent,
    UncertaintyPropagator,
    UncertaintyReport,
)
from .validation_controls import (
    NegativeControlBuilder,
    ValidationValuePlanner,
)
from .validation_design import AssayRouter, DesignStatus, GuideDesigner, PowerPlanner


@dataclass(frozen=True, slots=True)
class HandlerBinding:
    """Human-readable record of one installed executable tool binding."""

    tool_id: str
    module: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "tool_id": self.tool_id,
            "module": self.module,
            "description": self.description,
        }


class ControlPlaneApplication:
    """Install safe, deterministic core handlers on a control-plane executor."""

    _atlas_sources = frozenset({"SRC-ENSEMBL-REST", "SRC-UCSC-REST", "SRC-ENCODE-REST"})

    def __init__(
        self,
        executor: ControlPlaneExecutor | None = None,
        *,
        atlas_retriever: PublicAtlasRetriever | None = None,
        sequence_inference: SequenceInference | None = None,
        uncertainty_propagator: UncertaintyPropagator | None = None,
    ) -> None:
        self.executor = executor or ControlPlaneExecutor(default_control_plane_registry())
        self.intake = VariantIntake()
        self.planner = MissionPlanner(self.executor.registry)
        self.power = PowerPlanner()
        self.drift = DriftMonitor()
        self.recurrence = RecurrenceModel()
        self.causal = CausalLattice()
        self.arbiter = EvidenceArbiter()
        self.reclassifier = LifecycleReclassifier()
        self.reference_registry = default_reference_registry()
        self.structural = StructuralReconstructor()
        self.lineage = LineageResolver()
        self.origin = OriginClonalityAssessor()
        self.assay_qc = AssayQCEvaluator()
        self.context_evidence = ContextEvidenceBuilder()
        self.negative_controls = NegativeControlBuilder()
        self.validation_value = ValidationValuePlanner()
        self.benchmarks = BenchmarkRunner()
        self.review_packets = ReviewPacketBuilder()
        self.calibration = CalibrationEvaluator()
        self.inference = InferenceExtensionSuite()
        self.sequence_inference = sequence_inference or SequenceInference()
        self.uncertainty = uncertainty_propagator or UncertaintyPropagator()
        self.atlas = atlas_retriever or PublicAtlasRetriever(
            sequence_inference=self.sequence_inference,
            uncertainty_propagator=self.uncertainty,
        )
        self.bindings: list[HandlerBinding] = []
        self._install_core_handlers()

    def _bind(self, tool_id: str, handler: object, module: str, description: str) -> None:
        self.executor.register(tool_id, handler)  # type: ignore[arg-type]
        self.bindings.append(HandlerBinding(tool_id, module, description))

    def _install_core_handlers(self) -> None:
        self._bind(
            "A01.publish",
            self._plan,
            "control_plane.MissionPlanner",
            "Expand requested roles and dependencies into a named workflow decision.",
        )
        self._bind(
            "A02.publish",
            self._compile,
            "control_plane.MissionPlanner",
            "Compile a dependency-safe workflow graph with the declared mission boundary.",
        )
        self._bind(
            "A03.publish",
            self._policy,
            "control_plane.PolicyClaimGate",
            "Evaluate claim, source, data-scope, and mutation policy for one invocation.",
        )
        self._bind(
            "A04.publish",
            self._schedule,
            "control_plane.ResourceScheduler",
            "Preview resource admission without mutating scheduler counters.",
        )
        self._bind(
            "A05.publish",
            self._arbitrate,
            "control_plane.EvidenceArbiter",
            "Merge matching envelopes while retaining payload conflicts as abstentions.",
        )
        self._bind(
            "A06.publish",
            self._review,
            "control_plane.HumanReviewRouter",
            "Route a declared outcome to an explicit human-review gate.",
        )
        self._bind(
            "A07.publish",
            self._intake,
            "intake.VariantIntake",
            "Parse VCF, TSV, or JSON and return a receipt-backed evidence envelope.",
        )
        self._bind(
            "A08.publish",
            self._identity,
            "identity.normalize_variant",
            "Normalize one declared variant notation into a canonical identity.",
        )
        self._bind(
            "A09.publish",
            self._reference_projection,
            "reference_registry.ReferenceProjector",
            "Project a canonical variant through an explicit reference mapping.",
        )
        self._bind(
            "A10.publish",
            self._structural_reconstruction,
            "structural_reconstruction.StructuralReconstructor",
            "Reconstruct symbolic and breakend events without flattening unsupported records.",
        )
        self._bind(
            "A11.publish",
            self._pangenome_projection,
            "reference_registry.ReferenceProjector",
            "Return explicit projections for every declared target assembly.",
        )
        self._bind(
            "A12.publish",
            self._lineage_resolution,
            "lineage.LineageResolver",
            "Validate pseudonymous sample relationships and retain missing-parent warnings.",
        )
        self._bind(
            "A13.publish",
            self._origin_assessment,
            "origin.OriginClonalityAssessor",
            "Assess origin and clonality from declared multi-sample observations.",
        )
        self._bind(
            "A14.publish",
            self._assay_qc,
            "assay_qc.AssayQCEvaluator",
            "Evaluate assay QC metrics with explicit missingness and thresholds.",
        )
        self._bind(
            "A15.publish",
            self._atlas,
            "atlas.PublicAtlasRetriever",
            "Retrieve bounded public reference observations with source receipts.",
        )
        for agent_id, channel in ATLAS_ROLE_CHANNELS.items():
            self._bind(
                f"{agent_id}.publish",
                partial(
                    self._context_atlas,
                    role_id=agent_id,
                    expected_channel=channel,
                ),
                "atlas_context.ContextEvidenceBuilder",
                f"Transport {channel} observations only when their declared context is compatible.",
            )
        self._bind(
            "A23.publish",
            self._sequence,
            "sequence_inference.SequenceInference",
            "Compare reference and alternate sequence windows with motif deltas.",
        )
        self._bind(
            "A24.publish",
            self._motif_grammar,
            "inference_extensions.InferenceExtensionSuite",
            "Interpret supplied sequence motif deltas as bounded element-grammar evidence.",
        )
        self._bind(
            "A25.publish",
            self._accessibility_delta,
            "inference_extensions.InferenceExtensionSuite",
            "Compare explicit chromatin accessibility measurements with context gating.",
        )
        self._bind(
            "A26.publish",
            self._topology_rewiring,
            "inference_extensions.InferenceExtensionSuite",
            "Evaluate explicit contact changes without inferring gene causality.",
        )
        self._bind(
            "A27.publish",
            self._variant_element_link,
            "inference_extensions.InferenceExtensionSuite",
            "Score variant-element linkage from declared contextual features.",
        )
        self._bind(
            "A28.publish",
            self._element_gene_link,
            "inference_extensions.InferenceExtensionSuite",
            "Score element-gene linkage from nominated genes and contact observations.",
        )
        self._bind(
            "A29.publish",
            self._allele_specific,
            "inference_extensions.InferenceExtensionSuite",
            "Compare reference and alternate functional measurements explicitly.",
        )
        self._bind(
            "A30.publish",
            self._cell_state_mechanism,
            "inference_extensions.InferenceExtensionSuite",
            "Assemble context-specific mechanism edges from supplied links.",
        )
        self._bind(
            "A31.publish",
            self._longitudinal,
            "inference_extensions.InferenceExtensionSuite",
            "Compare measured longitudinal timepoints without treating missingness as a negative.",
        )
        self._bind(
            "A33.publish",
            self._germline_context,
            "inference_extensions.InferenceExtensionSuite",
            "Separate inherited context from the somatic research path.",
        )
        self._bind(
            "A35.publish",
            self._driver_posterior,
            "inference_extensions.InferenceExtensionSuite",
            "Compute a declared-prior research posterior proxy with review routing.",
        )
        self._bind(
            "A36.publish",
            self._uncertainty,
            "uncertainty.UncertaintyPropagator",
            "Aggregate typed uncertainty components and optional domain assessment.",
        )
        self._bind(
            "A39.publish",
            self._assay_route,
            "validation_design.AssayRouter",
            "Rank declared assay options against explicit hypothesis uncertainty.",
        )
        self._bind(
            "A40.publish",
            self._guide_design,
            "validation_design.GuideDesigner",
            "Enumerate local NGG guide candidates with unassessed off-target status.",
        )
        self._bind(
            "A37.publish",
            self._negative_control,
            "validation_controls.NegativeControlBuilder",
            "Select matched control candidates without declaring measured negatives.",
        )
        self._bind(
            "A38.publish",
            self._benchmark,
            "benchmarks.BenchmarkRunner",
            "Run declared fixture benchmarks and retain abstention and review metrics.",
        )
        self._bind(
            "A32.publish",
            self._cohort,
            "cohort.RecurrenceModel",
            "Estimate recurrence against a declared callable matched cohort.",
        )
        self._bind(
            "A34.publish",
            self._causal,
            "causal.CausalLattice",
            "Assemble factorized causal path support and edge sensitivity.",
        )
        self._bind(
            "A46.publish",
            self._reclassify,
            "lifecycle.LifecycleReclassifier",
            "Compare immutable dossier snapshots and emit a review-aware plan.",
        )
        self._bind(
            "A43.publish",
            self._evidence_graph,
            "evidence.EvidenceGraph",
            "Aggregate claims for one declared hypothesis edge without erasing negatives.",
        )
        self._bind(
            "A44.publish",
            self._report,
            "reports.render_markdown",
            "Render a typed dossier summary while preserving research-use caveats.",
        )
        self._bind(
            "A42.publish",
            self._validation_value,
            "validation_controls.ValidationValuePlanner",
            "Rank validation actions by declared information value, uncertainty, and cost.",
        )
        self._bind(
            "A48.publish",
            self._security,
            "controls.LocalDataController",
            "Sanitize metadata and evaluate project-scoped export policy.",
        )
        self._bind(
            "A41.publish",
            self._power,
            "validation_design.PowerPlanner",
            "Build an approximate power envelope with explicit controls.",
        )
        self._bind(
            "A45.publish",
            self._human_review,
            "lifecycle.ReviewPacketBuilder",
            "Refuse automated adjudication and preserve an explicit human-review abstention.",
        )
        self._bind(
            "A47.publish",
            self._drift,
            "lifecycle.DriftMonitor",
            "Compare baseline/current operational metrics and return a drift envelope.",
        )

    def _plan(self, request: InvocationRequest) -> WorkflowDecision | Abstention:
        requested = request.input_payload.get("requested_agent_ids", ())
        if not isinstance(requested, (list, tuple)):
            return Abstention(
                "missing_requested_roles",
                "mission",
                "Mission planning requires a requested_agent_ids list.",
                ("requested_agent_ids",),
            )
        return self.planner.plan(request.mission, (str(item) for item in requested))

    def _compile(self, request: InvocationRequest) -> WorkflowDecision | Abstention:
        requested = request.input_payload.get("requested_agent_ids", ())
        if not isinstance(requested, (list, tuple)):
            return Abstention(
                "missing_requested_roles",
                "workflow_compiler",
                "Workflow compilation requires a requested_agent_ids list.",
                ("requested_agent_ids",),
            )
        try:
            decision = self.planner.plan(request.mission, (str(item) for item in requested))
        except (TypeError, ValueError, ValidationError) as exc:
            return Abstention(
                "invalid_workflow_request",
                "workflow_compiler",
                str(exc),
                ("requested_agent_ids", "mission.claim_ceiling"),
            )
        warnings = list(decision.warnings)
        if request.budget.max_invocations < len(decision.selected_agent_ids):
            warnings.append("Mission invocation budget is smaller than the selected role count.")
        return replace(decision, warnings=tuple(dict.fromkeys(warnings)))

    def _policy(self, request: InvocationRequest) -> ControlPolicyDecision | Abstention:
        raw = request.input_payload
        target_agent_id = raw.get("target_agent_id")
        target_tool_id = raw.get("target_tool_id")
        nested_payload = raw.get("invocation_payload", {})
        if not isinstance(target_agent_id, str) or not isinstance(target_tool_id, str):
            return Abstention(
                "missing_policy_target",
                "policy_gate",
                "Policy inspection requires target_agent_id and target_tool_id.",
                ("target_agent_id", "target_tool_id"),
            )
        if not isinstance(nested_payload, Mapping):
            return Abstention(
                "invalid_policy_payload",
                "policy_gate",
                "invocation_payload must be a mapping.",
                ("invocation_payload",),
            )
        try:
            agent = self.executor.registry.agent(target_agent_id)
            tool = self.executor.registry.tool(target_tool_id)
            if tool.owner_agent_id != agent.agent_id:
                raise ValidationError("target tool is not owned by target agent")
            nested_request = replace(
                request,
                agent_id=target_agent_id,
                tool_id=target_tool_id,
                input_payload=nested_payload,
                idempotency_key=f"{request.idempotency_key}:policy-target",
            )
            return self.executor.policy_gate.inspect(nested_request, agent, tool)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_policy_target",
                "policy_gate",
                str(exc),
                ("target_agent_id", "target_tool_id"),
            )

    def _schedule(self, request: InvocationRequest) -> ScheduleDecision | Abstention:
        target_tool_id = request.input_payload.get("target_tool_id", "A04.publish")
        if not isinstance(target_tool_id, str):
            return Abstention(
                "invalid_schedule_target",
                "resource_scheduler",
                "target_tool_id must be a string.",
                ("target_tool_id",),
            )
        try:
            tool = self.executor.registry.tool(target_tool_id)
            preview_request = replace(
                request,
                request_id=f"{request.request_id}:schedule-preview",
                agent_id=tool.owner_agent_id,
                tool_id=target_tool_id,
                idempotency_key=f"{request.idempotency_key}:schedule-preview",
            )
            return self.executor.scheduler.preview(preview_request, tool)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_schedule_target",
                "resource_scheduler",
                str(exc),
                ("target_tool_id",),
            )

    def _arbitrate(self, request: InvocationRequest) -> ArbitrationResult | Abstention:
        raw = request.input_payload.get("envelopes", ())
        if not isinstance(raw, (list, tuple)):
            return Abstention(
                "missing_evidence_envelopes",
                "evidence_arbiter",
                "Arbitration requires an envelopes list.",
                ("envelopes",),
            )
        try:
            envelopes = tuple(self._evidence_envelope(item) for item in raw)
            if not envelopes:
                return ArbitrationResult(
                    accepted=(),
                    abstentions=(
                        Abstention(
                            "no_evidence_envelopes",
                            "evidence_arbiter",
                            "No evidence envelopes were supplied for arbitration.",
                            ("envelopes",),
                        ),
                    ),
                )
            return self.arbiter.arbitrate(envelopes)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_evidence_envelope",
                "evidence_arbiter",
                str(exc),
                ("envelopes",),
            )

    def _review(self, request: InvocationRequest) -> ReviewRoute | Abstention:
        raw = request.input_payload
        target_agent_id = raw.get("target_agent_id")
        if not isinstance(target_agent_id, str):
            return Abstention(
                "missing_review_target",
                "human_review_router",
                "Review routing requires target_agent_id.",
                ("target_agent_id", "response"),
            )
        try:
            agent = self.executor.registry.agent(target_agent_id)
            response = self._control_output(raw.get("response"))
            return self.executor.review_router.route(agent, response)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_review_outcome",
                "human_review_router",
                str(exc),
                ("target_agent_id", "response"),
            )

    @staticmethod
    def _evidence_envelope(raw: object) -> EvidenceEnvelope:
        if not isinstance(raw, Mapping):
            raise ValidationError("evidence envelope must be a mapping")
        return EvidenceEnvelope(
            evidence_id=str(raw["evidence_id"]),
            agent_id=str(raw["agent_id"]),
            tool_id=str(raw["tool_id"]),
            state=EvidenceState(str(raw["state"])),
            tier=EvidenceTier(str(raw["tier"])),
            claim_summary=str(raw["claim_summary"]),
            payload_hash=str(raw["payload_hash"]),
            source_ids=tuple(str(value) for value in raw.get("source_ids", ())),
            provenance_digest=str(raw.get("provenance_digest", "declared")),
            confidence=(float(raw["confidence"]) if raw.get("confidence") is not None else None),
            limitations=tuple(str(value) for value in raw.get("limitations", ())),
        )

    @classmethod
    def _control_output(cls, raw: object) -> Any:
        if not isinstance(raw, Mapping):
            raise ValidationError("review response must be a mapping")
        kind = str(raw.get("kind", raw.get("type", "abstention")))
        if kind == "abstention":
            return Abstention(
                str(raw["reason_code"]),
                str(raw["scope"]),
                str(raw["explanation"]),
                tuple(str(value) for value in raw.get("missing_inputs", ())),
                str(raw.get("remediation", "Route the case for review.")),
            )
        if kind == "typed_error":
            return TypedInvocationError(
                str(raw["code"]),
                str(raw["message"]),
                bool(raw.get("retryable", False)),
                raw.get("details", {}),
            )
        if kind == "evidence_envelope":
            return cls._evidence_envelope(raw)
        if kind == "workflow_decision":
            return WorkflowDecision(
                decision=str(raw["decision"]),
                selected_agent_ids=tuple(str(value) for value in raw.get("selected_agent_ids", ())),
                selected_tool_ids=tuple(str(value) for value in raw.get("selected_tool_ids", ())),
                requires_human_review=bool(raw.get("requires_human_review", False)),
                reasons=tuple(str(value) for value in raw.get("reasons", ())),
                warnings=tuple(str(value) for value in raw.get("warnings", ())),
                abstained=bool(raw.get("abstained", False)),
            )
        raise ValidationError(f"unsupported review response type: {kind}")

    def _intake(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        text = request.input_payload.get("text")
        source_id = request.input_payload.get("source_id")
        if not isinstance(text, str) or not isinstance(source_id, str):
            return Abstention(
                "missing_intake_payload",
                "variant_intake",
                "Intake requires text and source_id fields.",
                ("text", "source_id"),
            )
        batch = self.intake.parse_text(
            text,
            source_id=source_id,
            input_format=request.input_payload.get("input_format"),
            genome_build=str(request.input_payload.get("genome_build", self.intake.default_build)),
            sample_id=(
                str(request.input_payload["sample_id"])
                if request.input_payload.get("sample_id") is not None
                else None
            ),
            include_no_call=bool(request.input_payload.get("include_no_call", False)),
        )
        return EvidenceEnvelope(
            evidence_id=f"intake:{batch.receipt.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED if batch.variants else EvidenceState.ABSTAINED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Intake accepted {len(batch.variants)} canonical variants from {source_id}."
            ),
            payload_hash=batch.content_address,
            source_ids=(source_id,),
            provenance_digest=request.provenance.digest,
            confidence=1.0 if batch.variants else 0.0,
            limitations=tuple(issue.message for issue in batch.issues),
        )

    def _identity(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        notation = raw.get("notation")
        if not isinstance(notation, str) or not notation.strip():
            return Abstention(
                "missing_variant_notation",
                "variant_identity",
                "Identity normalization requires a notation field.",
                ("notation",),
            )
        variant = parse_variant(
            notation,
            genome_build=str(raw.get("genome_build", "GRCh38")),
            variant_id=str(raw.get("variant_id")) if raw.get("variant_id") else None,
        )
        return EvidenceEnvelope(
            evidence_id=f"identity:{variant.canonical_key}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=f"Canonical identity normalized for {variant.variant_id}.",
            payload_hash=content_hash(variant.to_dict()),
            source_ids=("control-plane-input",),
            provenance_digest=request.provenance.digest,
            confidence=1.0,
        )

    def _reference_projection(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        try:
            variant = self._variant_from_payload(raw)
            target_build = str(raw["target_build"])
            projector = self._projector(raw.get("mappings", ()))
            result = projector.project(variant, target_build)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_reference_projection_inputs",
                "reference_projection",
                str(exc),
                ("variant", "target_build"),
            )
        state = (
            EvidenceState.SUPPORTED
            if result.status in {ProjectionStatus.IDENTITY, ProjectionStatus.MAPPED}
            else EvidenceState.ABSTAINED
        )
        payload_hash = content_hash(result.to_dict())
        return EvidenceEnvelope(
            evidence_id=f"reference-projection:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.REFERENCE,
            claim_summary=f"Reference projection status is {result.status.value}: {result.reason}.",
            payload_hash=payload_hash,
            source_ids=("reference-registry",),
            provenance_digest=request.provenance.digest,
            confidence=0.95 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=(result.reason,),
        )

    def _pangenome_projection(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        targets_raw = raw.get("target_builds", raw.get("target_build"))
        if isinstance(targets_raw, str):
            targets = (targets_raw,)
        elif isinstance(targets_raw, (list, tuple)):
            targets = tuple(str(item) for item in targets_raw)
        else:
            targets = ()
        if not targets:
            return Abstention(
                "missing_projection_targets",
                "pangenome_projection",
                "Pangenome projection requires at least one target assembly.",
                ("target_builds",),
            )
        try:
            variant = self._variant_from_payload(raw)
            projector = self._projector(raw.get("mappings", ()))
            results = tuple(projector.project(variant, target) for target in targets)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_projection_inputs",
                "pangenome_projection",
                str(exc),
                ("variant", "target_builds"),
            )
        mapped = sum(
            result.status in {ProjectionStatus.IDENTITY, ProjectionStatus.MAPPED}
            for result in results
        )
        payload_hash = content_hash(results)
        return EvidenceEnvelope(
            evidence_id=f"pangenome-projection:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED if mapped else EvidenceState.ABSTAINED,
            tier=EvidenceTier.REFERENCE,
            claim_summary=(
                f"Pangenome projection returned {mapped} supported results across "
                f"{len(results)} target assemblies."
            ),
            payload_hash=payload_hash,
            source_ids=("reference-registry",),
            provenance_digest=request.provenance.digest,
            confidence=round(mapped / max(1, len(results)), 6),
            limitations=tuple(
                result.reason for result in results if result.status != ProjectionStatus.MAPPED
            ),
        )

    def _projector(self, mappings_raw: object) -> ReferenceProjector:
        if not isinstance(mappings_raw, (list, tuple)):
            raise ValidationError("reference mappings must be a list")
        segments = tuple(self._mapping_segment(item) for item in mappings_raw)
        return ReferenceProjector(self.reference_registry, MappingCatalog(segments))

    @staticmethod
    def _mapping_segment(raw: object) -> MappingSegment:
        if not isinstance(raw, Mapping):
            raise ValidationError("each mapping segment must be a mapping")
        return MappingSegment(
            mapping_id=str(raw["mapping_id"]),
            source_assembly=str(raw["source_assembly"]),
            source_chromosome=str(raw["source_chromosome"]),
            source_start=int(raw["source_start"]),
            source_end=int(raw["source_end"]),
            target_assembly=str(raw["target_assembly"]),
            target_chromosome=str(raw["target_chromosome"]),
            target_start=int(raw["target_start"]),
            target_end=int(raw["target_end"]),
            strand=str(raw["strand"]),
            source_version=str(raw["source_version"]),
        )

    def _structural_reconstruction(
        self, request: InvocationRequest
    ) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        records_raw = raw.get("records")
        try:
            context = self._context_from_payload(raw)
            if not isinstance(records_raw, (list, tuple)):
                raise ValidationError("structural reconstruction requires records")
            records = tuple(self._raw_variant_record(item) for item in records_raw)
            result = self.structural.reconstruct(
                records,
                context=context,
                source_id=str(raw.get("source_id", "structural-input")),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_structural_inputs",
                "structural_reconstruction",
                str(exc),
                ("context", "records"),
            )
        state = EvidenceState.SUPPORTED if result.events else EvidenceState.ABSTAINED
        return EvidenceEnvelope(
            evidence_id=f"structural:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Structural reconstruction produced {len(result.events)} events from "
                f"{result.deferred_count} records."
            ),
            payload_hash=result.content_address,
            source_ids=(result.source_id,),
            provenance_digest=request.provenance.digest,
            confidence=0.9 if state == EvidenceState.SUPPORTED and not result.has_errors else 0.45,
            limitations=tuple(issue.message for issue in result.issues),
        )

    @staticmethod
    def _raw_variant_record(raw: object) -> RawVariantRecord:
        if not isinstance(raw, Mapping):
            raise ValidationError("each structural record must be a mapping")
        return RawVariantRecord(
            record_id=str(raw["record_id"]),
            chromosome=str(raw["chromosome"]),
            position=int(raw["position"]),
            reference=str(raw.get("reference", "N")),
            alternate=str(raw["alternate"]),
            source_line=int(raw.get("source_line", 1)),
            raw_hash=str(raw.get("raw_hash", content_hash(raw))),
            info=dict(raw.get("info", {})),
            sample=dict(raw.get("sample", {})),
            filter_value=str(raw.get("filter_value", ".")),
            quality=str(raw.get("quality", ".")),
        )

    def _lineage_resolution(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        records_raw = raw.get("records")
        if not isinstance(records_raw, (list, tuple)):
            return Abstention(
                "missing_lineage_records",
                "sample_lineage",
                "Lineage resolution requires a records list.",
                ("records",),
            )
        try:
            records = tuple(
                SampleLineageRecord(
                    sample_id=str(item["sample_id"]),
                    parent_sample_ids=tuple(
                        str(value) for value in item.get("parent_sample_ids", ())
                    ),
                    relationship=str(item["relationship"]),
                    timepoint=str(item.get("timepoint", "unspecified")),
                    source_id=str(item.get("source_id", "lineage-input")),
                    metadata=dict(item.get("metadata", {})) if item.get("metadata") else None,
                )
                for item in records_raw
                if isinstance(item, Mapping)
            )
            result = self.lineage.resolve(records)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_lineage_records",
                "sample_lineage",
                str(exc),
                ("records",),
            )
        state = EvidenceState.SUPPORTED if result.supported else EvidenceState.ABSTAINED
        return EvidenceEnvelope(
            evidence_id=f"lineage:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Lineage resolution retained {len(result.records)} records and "
                f"{len(result.edges)} directed relationships."
            ),
            payload_hash=result.content_address,
            source_ids=tuple(sorted({record.source_id for record in result.records})),
            provenance_digest=request.provenance.digest,
            confidence=0.9 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=result.warnings + result.errors,
        )

    def _origin_assessment(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        observations_raw = raw.get("observations")
        if not isinstance(observations_raw, (list, tuple)):
            return Abstention(
                "missing_origin_observations",
                "origin_clonality",
                "Origin assessment requires observation mappings.",
                ("observations",),
            )
        try:
            observations = tuple(
                OriginObservation(
                    observation_id=str(item["observation_id"]),
                    variant_id=str(item["variant_id"]),
                    sample_id=str(item["sample_id"]),
                    relationship=str(item["relationship"]),
                    alternate_fraction=(
                        float(item["alternate_fraction"])
                        if item.get("alternate_fraction") is not None
                        else None
                    ),
                    present_in_normal=self._optional_bool(item.get("present_in_normal")),
                    timepoint=str(item.get("timepoint", "unspecified")),
                    source_id=str(item.get("source_id", "origin-input")),
                )
                for item in observations_raw
                if isinstance(item, Mapping)
            )
            result = self.origin.assess(
                observations,
                variant_id=str(raw["variant_id"]) if raw.get("variant_id") else None,
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_origin_observations",
                "origin_clonality",
                str(exc),
                ("observations",),
            )
        return EvidenceEnvelope(
            evidence_id=f"origin:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Origin assessment is {result.origin.value} and clonality is {result.clonality}."
            ),
            payload_hash=result.content_address,
            source_ids=tuple(sorted({item.source_id for item in observations})),
            provenance_digest=request.provenance.digest,
            confidence=result.support,
            limitations=result.warnings,
        )

    def _assay_qc(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        observations_raw = raw.get("observations")
        if not isinstance(observations_raw, (list, tuple)):
            return Abstention(
                "missing_assay_qc_observations",
                "assay_qc",
                "Assay QC requires observation mappings.",
                ("observations",),
            )
        try:
            observations = tuple(
                AssayQCObservation(
                    assay_id=str(item["assay_id"]),
                    sample_id=str(item["sample_id"]),
                    assay_type=str(item["assay_type"]),
                    usable_reads=int(item["usable_reads"])
                    if item.get("usable_reads") is not None
                    else None,
                    mapping_rate=float(item["mapping_rate"])
                    if item.get("mapping_rate") is not None
                    else None,
                    replicate_correlation=(
                        float(item["replicate_correlation"])
                        if item.get("replicate_correlation") is not None
                        else None
                    ),
                    contamination_rate=(
                        float(item["contamination_rate"])
                        if item.get("contamination_rate") is not None
                        else None
                    ),
                    controls_passed=self._optional_bool(item.get("controls_passed")),
                    source_id=str(item.get("source_id", "assay-qc-input")),
                )
                for item in observations_raw
                if isinstance(item, Mapping)
            )
            results = self.assay_qc.evaluate_many(observations)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_assay_qc_observations",
                "assay_qc",
                str(exc),
                ("observations",),
            )
        if not results:
            return Abstention(
                "empty_assay_qc_observations",
                "assay_qc",
                "No assay QC observations were supplied.",
                ("observations",),
            )
        counts = {
            status.value: sum(result.status == status for result in results) for status in QCStatus
        }
        payload_hash = content_hash(results)
        state = (
            EvidenceState.ABSTAINED
            if counts[QCStatus.ABSTAINED.value] == len(results)
            else EvidenceState.SUPPORTED
        )
        return EvidenceEnvelope(
            evidence_id=f"assay-qc:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Assay QC evaluated {len(results)} observations: "
                + ", ".join(f"{key}={value}" for key, value in counts.items())
                + "."
            ),
            payload_hash=payload_hash,
            source_ids=tuple(sorted({result.source_id for result in results})),
            provenance_digest=request.provenance.digest,
            confidence=0.8 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=tuple(issue for result in results for issue in result.issues),
        )

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "1"}:
                return True
            if normalized in {"false", "no", "0"}:
                return False
        raise ValidationError("boolean field must be true, false, 1, or 0")

    def _context_atlas(
        self,
        request: InvocationRequest,
        *,
        role_id: str,
        expected_channel: str,
    ) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        observations_raw = raw.get("observations")
        context_raw = raw.get("context")
        if not isinstance(observations_raw, (list, tuple)) or not isinstance(context_raw, Mapping):
            return Abstention(
                "missing_context_atlas_inputs",
                f"{role_id}.context_atlas",
                "Context atlas execution requires context and observation mappings.",
                ("context", "observations"),
            )
        try:
            context = ReferenceContext.from_dict(context_raw)
            observations = tuple(
                self._context_observation(item, expected_channel) for item in observations_raw
            )
            bundle = self.context_evidence.build(
                variant_id=str(raw["variant_id"]),
                edge_id=str(raw.get("edge_id", f"{raw['variant_id']}:{role_id}")),
                case_context=context,
                observations=observations,
                minimum_context_score=float(raw.get("minimum_context_score", 0.35)),
                produced_by=f"{role_id}.context_atlas",
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_context_atlas_inputs",
                f"{role_id}.context_atlas",
                str(exc),
                ("variant_id", "edge_id", "context", "observations"),
            )
        supported = sum(claim.state == EvidenceState.SUPPORTED for claim in bundle.claims)
        if supported:
            state = EvidenceState.SUPPORTED
        elif bundle.claims and all(claim.state == EvidenceState.ABSENT for claim in bundle.claims):
            state = EvidenceState.ABSENT
        else:
            state = EvidenceState.ABSTAINED
        source_ids = tuple(sorted({claim.source_id for claim in bundle.claims}))
        return EvidenceEnvelope(
            evidence_id=f"{role_id}:context:{bundle.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.REFERENCE,
            claim_summary=(
                f"{role_id} transported {len(bundle.claims)} context observations; "
                f"{bundle.matched_count} met the context threshold."
            ),
            payload_hash=bundle.content_address,
            source_ids=source_ids,
            provenance_digest=request.provenance.digest,
            confidence=round(
                sum(claim.confidence for claim in bundle.claims) / max(1, len(bundle.claims)),
                6,
            ),
            limitations=bundle.warnings,
        )

    @staticmethod
    def _context_observation(raw: object, expected_channel: str) -> ContextObservation:
        if not isinstance(raw, Mapping):
            raise ValidationError("each context observation must be a mapping")
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("each context observation requires a context mapping")
        channel = str(raw.get("channel", expected_channel))
        if channel != expected_channel:
            raise ValidationError(
                f"observation channel {channel!r} does not match role channel {expected_channel!r}"
            )
        return ContextObservation(
            observation_id=str(raw["observation_id"]),
            source_id=str(raw["source_id"]),
            source_version=str(raw["source_version"]),
            context=ReferenceContext.from_dict(context_raw),
            channel=channel,
            state=EvidenceState(str(raw["state"])),
            tier=EvidenceTier(str(raw["tier"])),
            score=float(raw["score"]) if raw.get("score") is not None else None,
            confidence=float(raw["confidence"]),
            summary=str(raw["summary"]),
            payload=dict(raw.get("payload", {})),
        )

    def _atlas(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        """Run a public atlas query only under an explicit network allowlist."""

        if not request.mission.allow_network:
            return Abstention(
                "network_not_enabled",
                "public_atlas",
                "Atlas retrieval requires a mission with network access enabled.",
                ("mission.allow_network",),
                "Declare allow_network=True and an explicit public-source allowlist.",
            )
        raw = request.input_payload
        try:
            variant = self._variant_from_payload(raw)
            context = self._context_from_payload(raw)
            query = self._atlas_query(raw, variant)
        except (TypeError, ValueError, ValidationError) as exc:
            return Abstention(
                "invalid_atlas_payload",
                "public_atlas",
                str(exc),
                ("variant", "context"),
            )
        required_sources = set(self._atlas_sources) - {"SRC-ENCODE-REST"}
        if query.include_encode_catalog:
            required_sources.add("SRC-ENCODE-REST")
        missing_sources = tuple(sorted(required_sources - set(request.mission.allowed_source_ids)))
        if missing_sources:
            return Abstention(
                "source_allowlist_incomplete",
                "public_atlas",
                "The atlas query would use public sources outside the mission allowlist.",
                missing_sources,
                "Add only the requested public source IDs to the mission allowlist.",
            )
        bundle = self.atlas.retrieve(variant, context, query=query)
        return self._atlas_envelope(request, bundle)

    @staticmethod
    def _atlas_envelope(request: InvocationRequest, bundle: Any) -> EvidenceEnvelope:
        observations = tuple(bundle.observations)
        supported = sum(item.state == EvidenceState.SUPPORTED for item in observations)
        state = (
            EvidenceState.SUPPORTED
            if supported
            else EvidenceState.ABSENT
            if observations and all(item.state == EvidenceState.ABSENT for item in observations)
            else EvidenceState.ABSTAINED
        )
        sources = tuple(
            sorted(
                {
                    source_id
                    for source_id in (
                        *(receipt.source_id for receipt in bundle.receipts),
                        *(item.source_id for item in observations),
                    )
                }
            )
        )
        limitations = tuple(
            dict.fromkeys(
                (
                    *bundle.warnings,
                    *(limitation for item in observations for limitation in item.limitations),
                )
            )
        )
        return EvidenceEnvelope(
            evidence_id=f"atlas:{bundle.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.REFERENCE,
            claim_summary=(
                f"Atlas returned {supported} supported observations across "
                f"{len(observations)} bounded observations."
            ),
            payload_hash=bundle.content_address,
            source_ids=sources,
            provenance_digest=request.provenance.digest,
            confidence=round(supported / max(1, len(observations)), 6),
            limitations=limitations,
        )

    @staticmethod
    def _atlas_query(raw: Mapping[str, Any], variant: Any) -> AtlasQuery:
        query_raw = raw.get("query", raw)
        if not isinstance(query_raw, Mapping):
            raise ValidationError("atlas query must be a mapping")
        return AtlasQuery(
            variant_id=str(query_raw.get("variant_id", variant.variant_id)),
            window_bp=int(query_raw.get("window_bp", 2_000)),
            include_encode_catalog=bool(query_raw.get("include_encode_catalog", False)),
            encode_assay_title=(
                str(query_raw["encode_assay_title"])
                if query_raw.get("encode_assay_title") is not None
                else None
            ),
            encode_biosample=(
                str(query_raw["encode_biosample"])
                if query_raw.get("encode_biosample") is not None
                else None
            ),
            encode_limit=int(query_raw.get("encode_limit", 25)),
        )

    def _sequence(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        try:
            variant = self._variant_from_payload(raw)
            sequence_raw = raw.get("sequence")
            if not isinstance(sequence_raw, Mapping):
                raise ValidationError("sequence inference requires a sequence mapping")
            sequence = self._sequence_slice(sequence_raw)
            motifs = self._motifs(raw.get("motifs", ()))
            result = self.sequence_inference.analyze(variant, sequence, motifs=motifs)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_sequence_payload",
                "sequence_inference",
                str(exc),
                ("variant", "sequence", "sequence.receipt"),
            )
        return self._sequence_envelope(request, result)

    @staticmethod
    def _sequence_envelope(
        request: InvocationRequest, result: SequenceAnalysisResult
    ) -> EvidenceEnvelope:
        if result.state == SequenceAnalysisState.SUPPORTED:
            state = EvidenceState.SUPPORTED
            confidence = 0.8
        elif result.state == SequenceAnalysisState.OUT_OF_WINDOW:
            state = EvidenceState.OUT_OF_DOMAIN
            confidence = 0.0
        else:
            state = EvidenceState.ABSTAINED
            confidence = 0.0
        return EvidenceEnvelope(
            evidence_id=f"sequence:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Sequence analysis is {result.state.value}; "
                f"{len(result.created_hits)} motifs created and "
                f"{len(result.disrupted_hits)} disrupted."
            ),
            payload_hash=result.content_address,
            source_ids=(result.source_id,),
            provenance_digest=request.provenance.digest,
            confidence=confidence,
            limitations=result.limitations,
        )

    def _inference_extension(
        self,
        request: InvocationRequest,
        *,
        scope: str,
        missing_inputs: tuple[str, ...],
        calculation: Any,
    ) -> EvidenceEnvelope | Abstention:
        try:
            result = calculation()
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                f"invalid_{scope}_payload",
                scope,
                str(exc),
                missing_inputs,
            )
        payload = result.to_dict()
        state = EvidenceState(result.state.value)
        sources = tuple(
            dict.fromkeys(
                str(value) for value in payload.get("source_ids", ()) if str(value).strip()
            )
        )
        if not sources:
            sources = ("declared_inference_input",)
        return EvidenceEnvelope(
            evidence_id=f"{scope}:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"{scope} result is {result.state.value}; uncertainty={result.uncertainty:.3f}."
            ),
            payload_hash=result.content_address,
            source_ids=sources,
            provenance_digest=request.provenance.digest,
            confidence=round(1.0 - result.uncertainty, 6),
            limitations=tuple(result.limitations)
            + (f"Result payload fields: {', '.join(sorted(payload))}.",),
        )

    def _motif_grammar(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="motif_grammar",
            missing_inputs=("sequence_evidence", "candidate_element"),
            calculation=lambda: self.inference.motif_grammar(
                raw["sequence_evidence"],
                raw["candidate_element"],
            ),
        )

    def _accessibility_delta(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="accessibility_delta",
            missing_inputs=("sequence_evidence", "chromatin_evidence"),
            calculation=lambda: self.inference.accessibility_delta(
                raw["sequence_evidence"],
                raw["chromatin_evidence"],
            ),
        )

    def _topology_rewiring(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="topology_rewiring",
            missing_inputs=("contact_evidence", "candidate_element"),
            calculation=lambda: self.inference.topology_rewiring(
                raw["contact_evidence"],
                raw["candidate_element"],
            ),
        )

    def _variant_element_link(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="variant_element_link",
            missing_inputs=("canonical_variant", "candidate_element"),
            calculation=lambda: self.inference.variant_element_link(
                raw["canonical_variant"],
                raw["candidate_element"],
            ),
        )

    def _element_gene_link(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="element_gene_link",
            missing_inputs=("candidate_element", "contact_evidence"),
            calculation=lambda: self.inference.element_gene_link(
                raw["candidate_element"],
                raw["contact_evidence"],
            ),
        )

    def _allele_specific(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="allele_specific",
            missing_inputs=("canonical_variant", "functional_evidence"),
            calculation=lambda: self.inference.allele_specific(
                raw["canonical_variant"],
                raw["functional_evidence"],
            ),
        )

    def _cell_state_mechanism(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="cell_state_mechanism",
            missing_inputs=("link_evidence", "cell_state_annotation"),
            calculation=lambda: self.inference.cell_state_mechanism(
                raw["link_evidence"],
                raw["cell_state_annotation"],
            ),
        )

    def _longitudinal(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="longitudinal",
            missing_inputs=("origin_assessment", "functional_evidence"),
            calculation=lambda: self.inference.longitudinal(
                raw["origin_assessment"],
                raw["functional_evidence"],
            ),
        )

    def _germline_context(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="germline_context",
            missing_inputs=("origin_assessment", "cohort_record"),
            calculation=lambda: self.inference.germline_context(
                raw["origin_assessment"],
                raw["cohort_record"],
            ),
        )

    def _driver_posterior(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        return self._inference_extension(
            request,
            scope="driver_posterior",
            missing_inputs=("causal_lattice", "evidence_envelope", "causal_lattice.declared_prior"),
            calculation=lambda: self.inference.driver_posterior(
                raw["causal_lattice"],
                raw["evidence_envelope"],
            ),
        )

    @staticmethod
    def _sequence_slice(raw: Mapping[str, Any]) -> SequenceSlice:
        receipt_raw = raw.get("receipt")
        if not isinstance(receipt_raw, Mapping):
            raise ValidationError("sequence receipt is required")
        receipt = FetchReceipt(
            source_id=str(receipt_raw["source_id"]),
            source_version=str(receipt_raw["source_version"]),
            url=str(receipt_raw["url"]),
            request_hash=str(receipt_raw["request_hash"]),
            response_hash=(
                str(receipt_raw["response_hash"])
                if receipt_raw.get("response_hash") is not None
                else None
            ),
            status=FetchStatus(str(receipt_raw["status"])),
            http_status=(
                int(receipt_raw["http_status"])
                if receipt_raw.get("http_status") is not None
                else None
            ),
            attempts=int(receipt_raw["attempts"]),
            retrieved_at=str(receipt_raw["retrieved_at"]),
            elapsed_seconds=(
                float(receipt_raw["elapsed_seconds"])
                if receipt_raw.get("elapsed_seconds") is not None
                else None
            ),
            cache_expires_at=(
                str(receipt_raw["cache_expires_at"])
                if receipt_raw.get("cache_expires_at") is not None
                else None
            ),
            warnings=tuple(str(item) for item in receipt_raw.get("warnings", ())),
            error_type=(
                str(receipt_raw["error_type"])
                if receipt_raw.get("error_type") is not None
                else None
            ),
            error_message=(
                str(receipt_raw["error_message"])
                if receipt_raw.get("error_message") is not None
                else None
            ),
        )
        return SequenceSlice(
            assembly=str(raw["assembly"]),
            chromosome=str(raw["chromosome"]),
            start=int(raw["start"]),
            end=int(raw["end"]),
            sequence=str(raw["sequence"]),
            source_id=str(raw["source_id"]),
            receipt=receipt,
        )

    @staticmethod
    def _motifs(raw: object) -> tuple[MotifDefinition, ...]:
        if not isinstance(raw, (list, tuple)):
            raise ValidationError("motifs must be a list")
        return tuple(
            MotifDefinition(
                motif_id=str(item["motif_id"]),
                name=str(item.get("name", item.get("label", ""))),
                pattern=str(item["pattern"]),
                source_id=str(item.get("source_id", "declared_motif")),
            )
            for item in raw
            if isinstance(item, Mapping)
        )

    def _uncertainty(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        claims_raw = raw.get("claims")
        if not isinstance(claims_raw, (list, tuple)) or not claims_raw:
            return Abstention(
                "missing_uncertainty_claims",
                "uncertainty",
                "Uncertainty aggregation requires at least one typed evidence claim.",
                ("claims",),
            )
        try:
            claims = tuple(self._claim_from_mapping(item) for item in claims_raw)
            profile = self._domain_profile(raw.get("domain_profile"))
            ood = None
            features_raw = raw.get("features", {})
            if profile is not None:
                if not isinstance(features_raw, Mapping):
                    raise ValidationError("uncertainty features must be a mapping")
                features = {str(key): float(value) for key, value in features_raw.items()}
                ood = OutOfDomainDetector().assess(features, profile)
            report = self.uncertainty.summarize(claims, ood=ood)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_uncertainty_payload",
                "uncertainty",
                str(exc),
                ("claims",),
            )
        state = (
            EvidenceState.ABSTAINED
            if report.band == UncertaintyBand.ABSTAIN
            else EvidenceState.SUPPORTED
        )
        limitations = report.limitations + (report.ood.warnings if report.ood else ())
        return EvidenceEnvelope(
            evidence_id=f"uncertainty:{report.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Uncertainty aggregation is {report.band.value} "
                f"with overall value {report.overall:.6f}."
            ),
            payload_hash=report.content_address,
            source_ids=tuple(sorted({claim.source_id for claim in claims})),
            provenance_digest=request.provenance.digest,
            confidence=round(1.0 - report.overall, 6),
            limitations=limitations,
        )

    @staticmethod
    def _claim_from_mapping(raw: object) -> EvidenceClaim:
        if not isinstance(raw, Mapping):
            raise ValidationError("each uncertainty claim must be a mapping")
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("each uncertainty claim requires a context mapping")
        return EvidenceClaim(
            evidence_id=str(raw["evidence_id"]),
            edge_id=str(raw["edge_id"]),
            source_id=str(raw["source_id"]),
            channel=str(raw["channel"]),
            state=EvidenceState(str(raw["state"])),
            tier=EvidenceTier(str(raw["tier"])),
            score=float(raw["score"]) if raw.get("score") is not None else None,
            confidence=float(raw["confidence"]),
            context=ReferenceContext.from_dict(context_raw),
            summary=str(raw["summary"]),
            payload=dict(raw.get("payload", {})),
            depends_on=tuple(str(item) for item in raw.get("depends_on", ())),
            produced_by=str(raw.get("produced_by", "control_plane_input")),
            created_at=str(raw.get("created_at", "control-plane-input")),
            supersedes=(str(raw["supersedes"]) if raw.get("supersedes") is not None else None),
        )

    @staticmethod
    def _domain_profile(raw: object) -> DomainProfile | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise ValidationError("domain_profile must be a mapping")
        ranges = {
            str(key): (float(value[0]), float(value[1]))
            for key, value in dict(raw["feature_ranges"]).items()
        }
        return DomainProfile(
            profile_id=str(raw["profile_id"]),
            context_key=str(raw["context_key"]),
            required_features=tuple(str(item) for item in raw["required_features"]),
            feature_ranges=ranges,
            source_version=str(raw["source_version"]),
            model_digest=(
                str(raw["model_digest"]) if raw.get("model_digest") is not None else None
            ),
            watch_threshold=float(raw.get("watch_threshold", 0.15)),
        )

    def _assay_route(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        hypothesis_raw = raw.get("hypothesis")
        options_raw = raw.get("options")
        uncertainty_raw = raw.get("uncertainty")
        if (
            not isinstance(hypothesis_raw, Mapping)
            or not isinstance(options_raw, (list, tuple))
            or not isinstance(uncertainty_raw, Mapping)
        ):
            return Abstention(
                "missing_validation_route_inputs",
                "assay_router",
                "Assay routing requires a hypothesis, experiment options, and uncertainty report.",
                ("hypothesis", "options", "uncertainty"),
            )
        try:
            hypothesis = self._hypothesis_from_mapping(hypothesis_raw)
            options = tuple(self._experiment_from_mapping(item) for item in options_raw)
            uncertainty = self._uncertainty_report_from_mapping(uncertainty_raw)
            routes = AssayRouter().route(hypothesis, options, uncertainty)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_validation_route_inputs",
                "assay_router",
                str(exc),
                ("hypothesis", "options", "uncertainty"),
            )
        if not routes:
            return Abstention(
                "no_supported_validation_route",
                "assay_router",
                "No declared assay option tests an edge in the supplied hypothesis.",
                ("options.tests_edges", "hypothesis.edges"),
            )
        payload_hash = content_hash(routes)
        return EvidenceEnvelope(
            evidence_id=f"assay-route:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Assay routing produced {len(routes)} ranked validation routes; "
                f"top priority is {routes[0].priority:.6f}."
            ),
            payload_hash=payload_hash,
            source_ids=("validation-design",),
            provenance_digest=request.provenance.digest,
            confidence=round(max(0.0, 1.0 - uncertainty.overall), 6),
            limitations=tuple(
                dict.fromkeys(blocker for route in routes for blocker in route.blockers)
            ),
        )

    @staticmethod
    def _uncertainty_report_from_mapping(raw: Mapping[str, Any]) -> UncertaintyReport:
        components = tuple(
            UncertaintyComponent(
                name=str(item.get("name", item.get("component_id", item.get("label", "")))),
                value=float(item["value"]),
                rationale=str(item["rationale"]),
                evidence_ids=tuple(str(value) for value in item.get("evidence_ids", ())),
            )
            for item in raw.get("components", ())
            if isinstance(item, Mapping)
        )
        if not components:
            raise ValidationError("uncertainty report requires components")
        ood_raw = raw.get("ood")
        ood: OODAssessment | None = None
        if isinstance(ood_raw, Mapping):
            ood = OODAssessment(
                status=OODStatus(str(ood_raw["status"])),
                distance=float(ood_raw["distance"]),
                missing_features=tuple(str(item) for item in ood_raw.get("missing_features", ())),
                out_of_range_features=tuple(
                    str(item) for item in ood_raw.get("out_of_range_features", ())
                ),
                warnings=tuple(str(item) for item in ood_raw.get("warnings", ())),
                profile_id=str(ood_raw["profile_id"]),
                content_address=str(ood_raw["content_address"]),
            )
        return UncertaintyReport(
            overall=float(raw["overall"]),
            band=UncertaintyBand(str(raw["band"])),
            components=components,
            ood=ood,
            limitations=tuple(str(item) for item in raw.get("limitations", ())),
            content_address=str(raw["content_address"]),
        )

    def _guide_design(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        try:
            variant = self._variant_from_payload(raw)
            sequence_raw = raw.get("sequence")
            if not isinstance(sequence_raw, Mapping):
                raise ValidationError("guide design requires a sequence mapping")
            sequence = self._sequence_slice(sequence_raw)
            result = GuideDesigner().design(
                variant,
                sequence,
                protospacer_length=int(raw.get("protospacer_length", 20)),
                pam_pattern=str(raw.get("pam_pattern", "NGG")),
                max_candidates=int(raw.get("max_candidates", 50)),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_guide_design_inputs",
                "guide_design",
                str(exc),
                ("variant", "sequence", "sequence.receipt"),
            )
        state = (
            EvidenceState.SUPPORTED
            if result.status == DesignStatus.READY_FOR_REVIEW
            else EvidenceState.ABSTAINED
        )
        payload_hash = result.content_address
        return EvidenceEnvelope(
            evidence_id=f"guide-design:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Guide design status is {result.status.value}; "
                f"{len(result.candidates)} local candidates were enumerated."
            ),
            payload_hash=payload_hash,
            source_ids=(result.source_id,),
            provenance_digest=request.provenance.digest,
            confidence=0.7 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=result.warnings,
        )

    def _evidence_graph(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        claims_raw = raw.get("claims")
        edge_raw = raw.get("edge")
        if not isinstance(claims_raw, (list, tuple)) or not isinstance(edge_raw, Mapping):
            return Abstention(
                "missing_evidence_graph_inputs",
                "evidence_graph",
                "Evidence aggregation requires claims and one hypothesis edge.",
                ("claims", "edge"),
            )
        try:
            claims = tuple(self._claim_from_mapping(item) for item in claims_raw)
            edge = self._hypothesis_edge(edge_raw)
            graph = EvidenceGraph()
            graph.extend(claims)
            aggregate = graph.aggregate(edge)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_evidence_graph_inputs",
                "evidence_graph",
                str(exc),
                ("claims", "edge"),
            )
        payload_hash = content_hash(aggregate.to_dict())
        state = (
            EvidenceState.SUPPORTED if aggregate.supported_claim_ids else EvidenceState.ABSTAINED
        )
        return EvidenceEnvelope(
            evidence_id=f"evidence-graph:{edge.edge_id}:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Evidence graph aggregate for {edge.edge_id} has score "
                f"{aggregate.score:.6f} and uncertainty {aggregate.uncertainty:.6f}."
            ),
            payload_hash=payload_hash,
            source_ids=tuple(sorted({claim.source_id for claim in claims})),
            provenance_digest=request.provenance.digest,
            confidence=aggregate.context_support,
            limitations=(aggregate.rationale,),
        )

    def _report(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        dossier_raw = raw.get("dossier")
        output_format = str(raw.get("format", "markdown"))
        if not isinstance(dossier_raw, Mapping):
            return Abstention(
                "missing_report_dossier",
                "reporting",
                "Report rendering requires a typed dossier mapping.",
                ("dossier",),
            )
        if output_format not in {"markdown", "json"}:
            return Abstention(
                "unsupported_report_format",
                "reporting",
                "Report format must be markdown or json.",
                ("format",),
            )
        try:
            dossier = self._dossier_from_mapping(dossier_raw)
            summary = summarize(dossier)
            rendered = (
                render_markdown(dossier) if output_format == "markdown" else render_json(dossier)
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_report_dossier",
                "reporting",
                str(exc),
                ("dossier",),
            )
        payload_hash = content_hash(
            {"format": output_format, "summary": summary.to_dict(), "rendered": rendered}
        )
        return EvidenceEnvelope(
            evidence_id=f"report:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"{output_format} research report rendered for {summary.case_id} with "
                f"{summary.evidence_count} evidence claims."
            ),
            payload_hash=payload_hash,
            source_ids=("report-renderer",),
            provenance_digest=request.provenance.digest,
            confidence=1.0,
            limitations=(
                "Rendering preserves research-use status and does not create a release decision.",
            ),
        )

    def _negative_control(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        target_raw = raw.get("target")
        pool_raw = raw.get("pool")
        try:
            context = self._context_from_payload(raw)
            if not isinstance(target_raw, Mapping) or not isinstance(pool_raw, (list, tuple)):
                raise ValidationError(
                    "negative control construction requires target and pool mappings"
                )
            target = CandidateElement.from_dict(target_raw, context)
            pool = tuple(CandidateElement.from_dict(item, context) for item in pool_raw)
            result = self.negative_controls.build(
                target,
                pool,
                limit=int(raw.get("limit", 5)),
                source_id=str(raw.get("source_id", "validation-control-builder")),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_negative_control_inputs",
                "negative_controls",
                str(exc),
                ("context", "target", "pool"),
            )
        state = EvidenceState.SUPPORTED if result.controls else EvidenceState.ABSTAINED
        return EvidenceEnvelope(
            evidence_id=f"negative-controls:{result.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Negative-control construction selected {len(result.controls)} "
                f"unmeasured candidates for {result.target_element_id}."
            ),
            payload_hash=result.content_address,
            source_ids=(result.source_id,),
            provenance_digest=request.provenance.digest,
            confidence=1.0 if result.controls else 0.0,
            limitations=result.warnings
            + ("Selected candidates remain unsupported until an assay measures them.",),
        )

    def _benchmark(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        examples_raw = raw.get("examples")
        benchmark_id = raw.get("benchmark_id")
        if not isinstance(examples_raw, (list, tuple)) or not isinstance(benchmark_id, str):
            return Abstention(
                "missing_benchmark_inputs",
                "benchmark",
                "Benchmark execution requires benchmark_id and example mappings.",
                ("benchmark_id", "examples"),
            )
        try:
            examples = tuple(
                BenchmarkExample(
                    example_id=str(item["example_id"]),
                    manifest=CaseManifest.from_dict(item["manifest"]),
                    expected_element_id=(
                        str(item["expected_element_id"])
                        if item.get("expected_element_id") is not None
                        else None
                    ),
                    expected_gene_id=(
                        str(item["expected_gene_id"])
                        if item.get("expected_gene_id") is not None
                        else None
                    ),
                    max_review_candidates=int(item.get("max_review_candidates", 3)),
                )
                for item in examples_raw
                if isinstance(item, Mapping)
            )
            if not examples:
                raise ValidationError("benchmark requires at least one example")
            with TemporaryDirectory(prefix="glio-benchmark-") as data_root:
                report = self.benchmarks.run(benchmark_id, examples, data_root=data_root)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_benchmark_inputs",
                "benchmark",
                str(exc),
                ("benchmark_id", "examples"),
            )
        payload_hash = content_hash(report.to_dict())
        return EvidenceEnvelope(
            evidence_id=f"benchmark:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Benchmark {report.name} evaluated {len(report.examples)} examples with "
                f"abstention rate {report.abstention_rate:.6f}."
            ),
            payload_hash=payload_hash,
            source_ids=("local-benchmark-runner",),
            provenance_digest=request.provenance.digest,
            confidence=1.0,
            limitations=(
                "Benchmark metrics are internal research-quality signals, not external validation.",
            ),
        )

    def _validation_value(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        options_raw = raw.get("options")
        uncertainty_raw = raw.get("uncertainty")
        if not isinstance(options_raw, (list, tuple)) or not isinstance(uncertainty_raw, Mapping):
            return Abstention(
                "missing_validation_value_inputs",
                "validation_value",
                "Validation value requires experiment options and an uncertainty report.",
                ("options", "uncertainty"),
            )
        try:
            options = tuple(self._experiment_from_mapping(item) for item in options_raw)
            uncertainty = self._uncertainty_report_from_mapping(uncertainty_raw)
            priority_set = self.validation_value.rank(
                options,
                uncertainty,
                budget_class=str(raw.get("budget_class", "medium")),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_validation_value_inputs",
                "validation_value",
                str(exc),
                ("options", "uncertainty"),
            )
        state = EvidenceState.SUPPORTED if priority_set.priorities else EvidenceState.ABSTAINED
        return EvidenceEnvelope(
            evidence_id=f"validation-value:{priority_set.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Validation value ranked {len(priority_set.priorities)} actions; "
                f"top priority is {priority_set.priorities[0].priority:.6f}."
                if priority_set.priorities
                else "Validation value produced no actionable options."
            ),
            payload_hash=priority_set.content_address,
            source_ids=("validation-value-planner",),
            provenance_digest=request.provenance.digest,
            confidence=0.8 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=priority_set.warnings
            + ("Priority is an information-planning aid, not a causal or clinical conclusion.",),
        )

    def _security(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        project_id = raw.get("project_id", request.mission.project_id)
        artifact_class = raw.get("artifact_class")
        target_raw = raw.get("target")
        if (
            not isinstance(project_id, str)
            or not isinstance(artifact_class, str)
            or not isinstance(target_raw, str)
        ):
            return Abstention(
                "missing_security_inputs",
                "security_privacy",
                "Security evaluation requires project_id, artifact_class, and target.",
                ("project_id", "artifact_class", "target"),
            )
        try:
            target = ExportTarget(target_raw)
            metadata = raw.get("metadata", {})
            if not isinstance(metadata, Mapping):
                raise ValidationError("security metadata must be a mapping")
            controller = LocalDataController(default_local_policy(project_id))
            decision = controller.decide_export(artifact_class, target)
            sanitized = controller.sanitize_metadata(metadata)
            warnings = controller.validate_project_metadata(metadata)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_security_inputs",
                "security_privacy",
                str(exc),
                ("project_id", "artifact_class", "target", "metadata"),
            )
        payload_hash = content_hash(
            {
                "decision": decision.to_dict(),
                "sanitized_metadata": sanitized,
                "warnings": warnings,
            }
        )
        return EvidenceEnvelope(
            evidence_id=f"security:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Security decision for {artifact_class} to {target.value}: "
                f"allowed={str(decision.allowed).lower()}; "
                f"{len(sanitized)} metadata fields retained."
            ),
            payload_hash=payload_hash,
            source_ids=("local-project-policy",),
            provenance_digest=request.provenance.digest,
            confidence=1.0,
            limitations=decision.reasons + warnings,
        )

    def _cohort(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        observations_raw = raw.get("observations")
        locus_id = raw.get("locus_id")
        if not isinstance(observations_raw, (list, tuple)) or not isinstance(locus_id, str):
            return Abstention(
                "missing_cohort_payload",
                "cohort_recurrence",
                "Cohort recurrence requires observations and a locus_id.",
                ("observations", "locus_id"),
            )
        try:
            observations = tuple(self._cohort_observation(item) for item in observations_raw)
            result = self.recurrence.evaluate(observations, locus_id)
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_cohort_payload",
                "cohort_recurrence",
                str(exc),
                ("observations", "locus_id"),
            )
        payload_hash = content_hash(result.to_dict())
        return EvidenceEnvelope(
            evidence_id=f"cohort:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED if result.callable_count else EvidenceState.ABSTAINED,
            tier=EvidenceTier.COHORT,
            claim_summary=(
                f"Cohort recurrence for {result.locus_id} observed "
                f"{result.observed_count} mutations in {result.callable_count} callable rows."
            ),
            payload_hash=payload_hash,
            source_ids=(str(raw.get("source_id", "declared-cohort")),),
            provenance_digest=request.provenance.digest,
            confidence=round(max(0.0, 1.0 - result.uncertainty), 6),
            limitations=result.limitations + result.matched_control.warnings,
        )

    @staticmethod
    def _cohort_observation(raw: object) -> CohortObservation:
        if not isinstance(raw, Mapping):
            raise ValidationError("each cohort observation must be a mapping")
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("each cohort observation requires a context mapping")
        return CohortObservation(
            observation_id=str(raw["observation_id"]),
            subject_id=str(raw["subject_id"]),
            locus_id=str(raw["locus_id"]),
            mutated=bool(raw["mutated"]),
            callable=bool(raw["callable"]),
            mutability_score=float(raw["mutability_score"]),
            chromatin_score=float(raw["chromatin_score"]),
            ancestry_group=str(raw["ancestry_group"]),
            disease_class=str(raw["disease_class"]),
            context=ReferenceContext.from_dict(context_raw),
        )

    def _causal(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        path_id = raw.get("path_id")
        edges_raw = raw.get("edges")
        if not isinstance(path_id, str) or not isinstance(edges_raw, (list, tuple)):
            return Abstention(
                "missing_causal_payload",
                "causal_lattice",
                "Causal lattice assembly requires path_id and edge mappings.",
                ("path_id", "edges"),
            )
        try:
            edges = tuple(self._hypothesis_edge(item) for item in edges_raw)
            summary = self.causal.summarize(
                path_id,
                edges,
                alternatives=tuple(str(item) for item in raw.get("alternatives", ())),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_causal_payload",
                "causal_lattice",
                str(exc),
                ("path_id", "edges"),
            )
        payload_hash = content_hash(summary.to_dict())
        return EvidenceEnvelope(
            evidence_id=f"causal:{payload_hash}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Causal path {summary.path_id} has support {summary.support:.6f}; "
                f"weakest edge is {summary.weakest_edge_id}."
            ),
            payload_hash=payload_hash,
            source_ids=tuple(sorted({edge.source_id for edge in edges})),
            provenance_digest=request.provenance.digest,
            confidence=round(1.0 - summary.uncertainty, 6),
            limitations=summary.limitations,
        )

    @staticmethod
    def _hypothesis_edge(raw: object) -> HypothesisEdge:
        if not isinstance(raw, Mapping):
            raise ValidationError("each causal edge must be a mapping")
        return HypothesisEdge(
            edge_id=str(raw["edge_id"]),
            edge_type=EdgeType(str(raw["edge_type"])),
            source_id=str(raw["source_id"]),
            target_id=str(raw["target_id"]),
            support=float(raw["support"]),
            uncertainty=float(raw["uncertainty"]),
            context_fit=float(raw["context_fit"]),
            claim_ids=tuple(str(item) for item in raw["claim_ids"]),
            support_level=SupportLevel(str(raw["support_level"])),
            alternatives=tuple(str(item) for item in raw.get("alternatives", ())),
        )

    def _reclassify(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        previous_raw = raw.get("previous")
        current_raw = raw.get("current")
        if not isinstance(previous_raw, Mapping) or not isinstance(current_raw, Mapping):
            return Abstention(
                "missing_dossier_snapshots",
                "lifecycle_reclassification",
                "Reclassification requires previous and current dossier snapshots.",
                ("previous", "current"),
            )
        try:
            previous = self._dossier_from_mapping(previous_raw)
            current = self._dossier_from_mapping(current_raw)
            plan = self.reclassifier.plan(
                previous,
                current,
                source_version_before=str(raw["source_version_before"]),
                source_version_after=str(raw["source_version_after"]),
                reason=str(raw["reason"]),
            )
        except (TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                "invalid_dossier_snapshots",
                "lifecycle_reclassification",
                str(exc),
                ("previous", "current", "source versions", "reason"),
            )
        return EvidenceEnvelope(
            evidence_id=f"reclassification:{plan.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Reclassification identified {len(plan.deltas)} evidence deltas "
                f"across {len(plan.records)} hypothesis records."
            ),
            payload_hash=plan.content_address,
            source_ids=("lifecycle-reclassifier",),
            provenance_digest=request.provenance.digest,
            confidence=0.8 if plan.requires_review else 0.95,
            limitations=(
                plan.reason,
                "A reclassification plan is not an expert adjudication or release decision.",
            ),
        )

    @classmethod
    def _dossier_from_mapping(cls, raw: Mapping[str, Any]) -> Dossier:
        hypotheses = tuple(cls._hypothesis_from_mapping(item) for item in raw["hypotheses"])
        evidence = tuple(cls._claim_from_mapping(item) for item in raw["evidence"])
        experiments = tuple(cls._experiment_from_mapping(item) for item in raw["experiments"])
        review_raw = raw.get("review")
        review = cls._review_from_mapping(review_raw) if isinstance(review_raw, Mapping) else None
        return Dossier(
            dossier_id=str(raw["dossier_id"]),
            case_id=str(raw["case_id"]),
            run_id=str(raw["run_id"]),
            created_at=str(raw["created_at"]),
            input_address=str(raw["input_address"]),
            hypotheses=hypotheses,
            evidence=evidence,
            experiments=experiments,
            review=review,
            research_use_only=bool(raw["research_use_only"]),
            policy_version=str(raw["policy_version"]),
            event_head=str(raw["event_head"]),
            content_address=str(raw["content_address"]),
            status=ResearchStatus(str(raw["status"])),
            warnings=tuple(str(item) for item in raw.get("warnings", ())),
            source_receipts=tuple(dict(item) for item in raw.get("source_receipts", ())),
            source_bundle_addresses=tuple(
                str(item) for item in raw.get("source_bundle_addresses", ())
            ),
        )

    @classmethod
    def _hypothesis_from_mapping(cls, raw: object) -> Hypothesis:
        if not isinstance(raw, Mapping):
            raise ValidationError("each dossier hypothesis must be a mapping")
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("each hypothesis requires a context mapping")
        return Hypothesis(
            hypothesis_id=str(raw["hypothesis_id"]),
            variant_id=str(raw["variant_id"]),
            element_id=str(raw["element_id"]),
            gene_id=str(raw["gene_id"]),
            state_id=str(raw["state_id"]),
            mechanism=str(raw["mechanism"]),
            context=ReferenceContext.from_dict(context_raw),
            edges=tuple(cls._hypothesis_edge(item) for item in raw["edges"]),
            support=float(raw["support"]),
            uncertainty=float(raw["uncertainty"]),
            status=ResearchStatus(str(raw.get("status", ResearchStatus.DRAFT.value))),
            missing_evidence=tuple(str(item) for item in raw.get("missing_evidence", ())),
            negative_evidence=tuple(str(item) for item in raw.get("negative_evidence", ())),
            alternatives=tuple(str(item) for item in raw.get("alternatives", ())),
            provenance=tuple(str(item) for item in raw.get("provenance", ())),
        )

    @staticmethod
    def _experiment_from_mapping(raw: object) -> ExperimentOption:
        if not isinstance(raw, Mapping):
            raise ValidationError("each dossier experiment must be a mapping")
        return ExperimentOption(
            option_id=str(raw["option_id"]),
            assay=AssayType(str(raw["assay"])),
            tests_edges=tuple(str(item) for item in raw["tests_edges"]),
            expected_information_gain=float(raw["expected_information_gain"]),
            feasibility=float(raw["feasibility"]),
            cost_class=str(raw["cost_class"]),
            required_context=tuple(str(item) for item in raw["required_context"]),
            controls=tuple(str(item) for item in raw["controls"]),
            readouts=tuple(str(item) for item in raw["readouts"]),
            limitations=tuple(str(item) for item in raw["limitations"]),
        )

    @staticmethod
    def _review_from_mapping(raw: Mapping[str, Any]) -> ReviewDecision:
        return ReviewDecision(
            review_id=str(raw["review_id"]),
            case_id=str(raw["case_id"]),
            reviewer=str(raw["reviewer"]),
            state=ReviewState(str(raw["state"])),
            reviewed_hypothesis_ids=tuple(str(item) for item in raw["reviewed_hypothesis_ids"]),
            rationale=str(raw["rationale"]),
            checked_claim_ids=tuple(str(item) for item in raw["checked_claim_ids"]),
            created_at=str(raw.get("created_at", "control-plane-input")),
        )

    @staticmethod
    def _variant_from_payload(raw: Mapping[str, Any]) -> Any:
        variant_raw = raw.get("variant")
        if isinstance(variant_raw, Mapping):
            return normalize_variant(variant_raw)
        notation = raw.get("notation")
        if isinstance(notation, str) and notation.strip():
            return parse_variant(
                notation,
                genome_build=str(raw.get("genome_build", "GRCh38")),
                variant_id=str(raw.get("variant_id")) if raw.get("variant_id") else None,
            )
        raise ValidationError("variant notation or variant mapping is required")

    @staticmethod
    def _context_from_payload(raw: Mapping[str, Any]) -> ReferenceContext:
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("context mapping is required")
        return ReferenceContext.from_dict(context_raw)

    def _power(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        try:
            plan = self.power.plan(
                effect_size=float(raw["effect_size"]),
                baseline_rate=float(raw.get("baseline_rate", 0.5)),
                alpha=float(raw.get("alpha", 0.05)),
                target_power=float(raw.get("target_power", 0.80)),
                controls=tuple(str(item) for item in raw.get("controls", ())),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            return Abstention("invalid_power_inputs", "power_plan", str(exc), ("effect_size",))
        return EvidenceEnvelope(
            evidence_id=f"power:{plan.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Approximate power envelope requires {plan.samples_per_group} samples per group."
            ),
            payload_hash=plan.content_address,
            source_ids=("power-planner",),
            provenance_digest=request.provenance.digest,
            confidence=0.65,
            limitations=plan.limitations,
        )

    def _human_review(self, request: InvocationRequest) -> Abstention:
        return Abstention(
            "human_adjudication_required",
            "review",
            "Review decisions cannot be automated by the control-plane handler.",
            ("reviewer", "rationale", "checked_claim_ids"),
            "Create a signed ReviewDecision through the lifecycle API.",
        )

    def _drift(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        baseline = request.input_payload.get("baseline")
        current = request.input_payload.get("current")
        if not isinstance(baseline, Mapping) or not isinstance(current, Mapping):
            return Abstention(
                "missing_drift_metrics",
                "drift_monitor",
                "Drift monitoring requires baseline and current metric mappings.",
                ("baseline", "current"),
            )
        report = self.drift.compare(
            {str(key): self._optional_float(value) for key, value in baseline.items()},
            {str(key): self._optional_float(value) for key, value in current.items()},
            case_id=request.mission.mission_id,
        )
        return EvidenceEnvelope(
            evidence_id=f"drift:{report.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            claim_summary=f"Operational drift report status is {report.status.value}.",
            payload_hash=report.content_address,
            source_ids=("monitor-registry",),
            provenance_digest=request.provenance.digest,
            confidence=1.0,
            limitations=report.warnings,
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def manifest(self) -> dict[str, Any]:
        return {
            "registry": self.executor.registry.manifest(),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "binding_count": len(self.bindings),
        }
