"""Executable bindings from bounded control-plane tools to domain modules."""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import partial
from math import isfinite
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
from .inference_extensions import InferenceExtensionSuite, InferenceState
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
from .variant_normalization import NormalizationState, VRSNormalizer


def _input_text(value: object, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _input_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValidationError(f"{field} must be a boolean")
    return value


def _input_number(value: object, field: str) -> float:
    if type(value) not in {int, float} or isinstance(value, bool):
        raise ValidationError(f"{field} must be a number")
    result = float(value)
    if not isfinite(result):
        raise ValidationError(f"{field} must be finite")
    return result


def _input_integer(value: object, field: str) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field} must be an integer")
    return value


def _input_strings(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    result = tuple(_input_text(item, f"{field}[]") for item in value)
    if len(result) != len(set(result)):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


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
        try:
            requested_ids = _input_strings(requested, "requested_agent_ids")
        except ValidationError as exc:
            return Abstention("invalid_requested_roles", "mission", str(exc), ("requested_agent_ids",))
        return self.planner.plan(request.mission, requested_ids)

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
            requested_ids = _input_strings(requested, "requested_agent_ids")
            decision = self.planner.plan(request.mission, requested_ids)
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
        source_ids = _input_strings(raw.get("source_ids", ()), "evidence source_ids")
        limitations = _input_strings(raw.get("limitations", ()), "evidence limitations")
        return EvidenceEnvelope(
            evidence_id=_input_text(raw["evidence_id"], "evidence_id"),
            agent_id=_input_text(raw["agent_id"], "agent_id"),
            tool_id=_input_text(raw["tool_id"], "tool_id"),
            state=EvidenceState(_input_text(raw["state"], "evidence state")),
            tier=EvidenceTier(_input_text(raw["tier"], "evidence tier")),
            claim_summary=_input_text(raw["claim_summary"], "claim_summary"),
            payload_hash=_input_text(raw["payload_hash"], "payload_hash"),
            source_ids=source_ids,
            provenance_digest=_input_text(
                raw.get("provenance_digest", "declared"), "provenance_digest"
            ),
            confidence=(
                _input_number(raw["confidence"], "confidence")
                if raw.get("confidence") is not None
                else None
            ),
            limitations=limitations,
        )

    @classmethod
    def _control_output(cls, raw: object) -> Any:
        if not isinstance(raw, Mapping):
            raise ValidationError("review response must be a mapping")
        kind = _input_text(raw.get("kind", raw.get("type", "abstention")), "response kind")
        if kind == "abstention":
            return Abstention(
                _input_text(raw["reason_code"], "reason_code"),
                _input_text(raw["scope"], "scope"),
                _input_text(raw["explanation"], "explanation"),
                _input_strings(raw.get("missing_inputs", ()), "missing_inputs"),
                _input_text(raw.get("remediation", "Route the case for review."), "remediation"),
            )
        if kind == "typed_error":
            details = raw.get("details", {})
            if not isinstance(details, Mapping):
                raise ValidationError("typed error details must be a mapping")
            return TypedInvocationError(
                _input_text(raw["code"], "typed error code"),
                _input_text(raw["message"], "typed error message"),
                _input_bool(raw.get("retryable", False), "typed error retryable"),
                details,
            )
        if kind == "evidence_envelope":
            return cls._evidence_envelope(raw)
        if kind == "workflow_decision":
            return WorkflowDecision(
                decision=_input_text(raw["decision"], "decision"),
                selected_agent_ids=_input_strings(
                    raw.get("selected_agent_ids", ()), "selected_agent_ids"
                ),
                selected_tool_ids=_input_strings(
                    raw.get("selected_tool_ids", ()), "selected_tool_ids"
                ),
                requires_human_review=_input_bool(
                    raw.get("requires_human_review", False), "requires_human_review"
                ),
                reasons=_input_strings(raw.get("reasons", ()), "reasons"),
                warnings=_input_strings(raw.get("warnings", ()), "warnings"),
                abstained=_input_bool(raw.get("abstained", False), "abstained"),
            )
        raise ValidationError(f"unsupported review response type: {kind}")

    def _intake(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        source_id = request.input_payload.get("source_id")
        text = request.input_payload.get("text")
        binary_b64 = request.input_payload.get("bytes_base64")
        if not isinstance(source_id, str) or (
            not isinstance(text, str) and not isinstance(binary_b64, str)
        ):
            return Abstention(
                "missing_intake_payload",
                "variant_intake",
                "Intake requires text or bytes_base64 together with source_id.",
                ("text", "bytes_base64", "source_id"),
            )
        if isinstance(text, str) and isinstance(binary_b64, str):
            return Abstention(
                "ambiguous_intake_payload",
                "variant_intake",
                "Intake accepts either text or bytes_base64, not both.",
                ("text", "bytes_base64"),
            )
        try:
            sample_raw = request.input_payload.get("sample_id")
            sample_id = None if sample_raw is None else _input_text(sample_raw, "sample_id")
            build = _input_text(
                request.input_payload.get("genome_build", self.intake.default_build),
                "genome_build",
            )
            include_no_call = _input_bool(
                request.input_payload.get("include_no_call", False), "include_no_call"
            )
            if isinstance(binary_b64, str):
                data = base64.b64decode(binary_b64, validate=True)
                batch = self.intake.parse_bytes(
                    data,
                    source_id=source_id,
                    genome_build=build,
                    sample_id=sample_id,
                    include_no_call=include_no_call,
                )
            else:
                batch = self.intake.parse_text(
                    text,
                    source_id=source_id,
                    input_format=request.input_payload.get("input_format"),
                    genome_build=build,
                    sample_id=sample_id,
                    include_no_call=include_no_call,
                )
        except (TypeError, ValueError, ValidationError) as exc:
            return Abstention(
                "invalid_intake_payload",
                "variant_intake",
                str(exc),
                ("text", "bytes_base64", "source_id", "input_format"),
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
        try:
            genome_build = _input_text(raw.get("genome_build", "GRCh38"), "genome_build")
            sequence_digest = raw.get("sequence_digest")
            if sequence_digest is not None:
                sequence_digest = _input_text(sequence_digest, "sequence_digest")
            reference_sequence = raw.get("reference_sequence")
            if reference_sequence is not None:
                reference_sequence = _input_text(reference_sequence, "reference_sequence")
            reference_start = raw.get("reference_start")
            if reference_start is not None and type(reference_start) is not int:
                raise ValidationError("reference_start must be an integer")
            report = VRSNormalizer().normalize(
                notation,
                genome_build=genome_build,
                sequence_digest=sequence_digest,
                reference_sequence=reference_sequence,
                reference_start=reference_start,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            return Abstention(
                "invalid_variant_payload",
                "variant_identity",
                str(exc),
                ("notation", "genome_build"),
            )
        if report.state == NormalizationState.INVALID:
            return Abstention(
                "invalid_variant_notation",
                "variant_identity",
                "; ".join(report.warnings),
                ("notation",),
            )
        state = (
            EvidenceState.SUPPORTED
            if report.state == NormalizationState.SUPPORTED
            else EvidenceState.ABSTAINED
        )
        candidate = report.candidates[0] if report.candidates else None
        return EvidenceEnvelope(
            evidence_id=f"identity:{report.content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"Variant normalization is {report.state.value}; "
                f"{len(report.candidates)} candidate(s) emitted."
            ),
            payload_hash=report.content_address,
            source_ids=("vrs-normalizer",),
            provenance_digest=request.provenance.digest,
            confidence=1.0 if state == EvidenceState.SUPPORTED else 0.0,
            limitations=report.warnings
            + report.ambiguities
            + (() if candidate is None else candidate.transformation_steps),
        )

    def _reference_projection(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        try:
            variant = self._variant_from_payload(raw)
            target_build = _input_text(raw["target_build"], "target_build")
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
            targets = (_input_text(targets_raw, "target_build"),)
        elif isinstance(targets_raw, (list, tuple)):
            targets = _input_strings(targets_raw, "target_builds")
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
            mapping_id=_input_text(raw["mapping_id"], "mapping_id"),
            source_assembly=_input_text(raw["source_assembly"], "source_assembly"),
            source_chromosome=_input_text(raw["source_chromosome"], "source_chromosome"),
            source_start=_input_integer(raw["source_start"], "source_start"),
            source_end=_input_integer(raw["source_end"], "source_end"),
            target_assembly=_input_text(raw["target_assembly"], "target_assembly"),
            target_chromosome=_input_text(raw["target_chromosome"], "target_chromosome"),
            target_start=_input_integer(raw["target_start"], "target_start"),
            target_end=_input_integer(raw["target_end"], "target_end"),
            strand=_input_text(raw["strand"], "strand"),
            source_version=_input_text(raw["source_version"], "source_version"),
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
                source_id=_input_text(raw.get("source_id", "structural-input"), "source_id"),
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
        info = raw.get("info", {})
        sample = raw.get("sample", {})
        if not isinstance(info, Mapping) or not isinstance(sample, Mapping):
            raise ValidationError("structural record info and sample must be mappings")
        return RawVariantRecord(
            record_id=_input_text(raw["record_id"], "record_id"),
            chromosome=_input_text(raw["chromosome"], "chromosome"),
            position=_input_integer(raw["position"], "position"),
            reference=_input_text(raw.get("reference", "N"), "reference"),
            alternate=_input_text(raw["alternate"], "alternate"),
            source_line=_input_integer(raw.get("source_line", 1), "source_line"),
            raw_hash=_input_text(raw.get("raw_hash", content_hash(raw)), "raw_hash"),
            info=dict(info),
            sample=dict(sample),
            filter_value=_input_text(raw.get("filter_value", "."), "filter_value"),
            quality=_input_text(raw.get("quality", "."), "quality"),
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
            records_list: list[SampleLineageRecord] = []
            for index, item in enumerate(records_raw):
                if not isinstance(item, Mapping):
                    raise ValidationError(f"lineage record[{index}] must be a mapping")
                metadata = item.get("metadata", {})
                if metadata is not None and not isinstance(metadata, Mapping):
                    raise ValidationError(f"lineage record[{index}].metadata must be a mapping")
                records_list.append(
                    SampleLineageRecord(
                        sample_id=_input_text(item["sample_id"], f"lineage record[{index}].sample_id"),
                        parent_sample_ids=_input_strings(
                            item.get("parent_sample_ids", ()),
                            f"lineage record[{index}].parent_sample_ids",
                        ),
                        relationship=_input_text(
                            item["relationship"], f"lineage record[{index}].relationship"
                        ),
                        timepoint=_input_text(
                            item.get("timepoint", "unspecified"),
                            f"lineage record[{index}].timepoint",
                        ),
                        source_id=_input_text(
                            item.get("source_id", "lineage-input"),
                            f"lineage record[{index}].source_id",
                        ),
                        metadata=None if metadata is None else dict(metadata),
                    )
                )
            records = tuple(records_list)
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
            observations_list: list[OriginObservation] = []
            for index, item in enumerate(observations_raw):
                if not isinstance(item, Mapping):
                    raise ValidationError(f"origin observation[{index}] must be a mapping")
                fraction = item.get("alternate_fraction")
                observations_list.append(
                    OriginObservation(
                        observation_id=_input_text(item["observation_id"], f"origin observation[{index}].observation_id"),
                        variant_id=_input_text(item["variant_id"], f"origin observation[{index}].variant_id"),
                        sample_id=_input_text(item["sample_id"], f"origin observation[{index}].sample_id"),
                        relationship=_input_text(item["relationship"], f"origin observation[{index}].relationship"),
                        alternate_fraction=(
                            None
                            if fraction is None
                            else _input_number(fraction, f"origin observation[{index}].alternate_fraction")
                        ),
                        present_in_normal=self._optional_bool(item.get("present_in_normal")),
                        timepoint=_input_text(
                            item.get("timepoint", "unspecified"),
                            f"origin observation[{index}].timepoint",
                        ),
                        source_id=_input_text(
                            item.get("source_id", "origin-input"),
                            f"origin observation[{index}].source_id",
                        ),
                    )
                )
            observations = tuple(observations_list)
            result = self.origin.assess(
                observations,
                variant_id=(
                    _input_text(raw["variant_id"], "variant_id")
                    if raw.get("variant_id") is not None
                    else None
                ),
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
            observations_list: list[AssayQCObservation] = []
            for index, item in enumerate(observations_raw):
                if not isinstance(item, Mapping):
                    raise ValidationError(f"assay QC observation[{index}] must be a mapping")
                observations_list.append(
                    AssayQCObservation(
                        assay_id=_input_text(item["assay_id"], f"assay QC observation[{index}].assay_id"),
                        sample_id=_input_text(item["sample_id"], f"assay QC observation[{index}].sample_id"),
                        assay_type=_input_text(item["assay_type"], f"assay QC observation[{index}].assay_type"),
                        usable_reads=(
                            None
                            if item.get("usable_reads") is None
                            else _input_integer(item["usable_reads"], f"assay QC observation[{index}].usable_reads")
                        ),
                        mapping_rate=(
                            None
                            if item.get("mapping_rate") is None
                            else _input_number(item["mapping_rate"], f"assay QC observation[{index}].mapping_rate")
                        ),
                        replicate_correlation=(
                            None
                            if item.get("replicate_correlation") is None
                            else _input_number(item["replicate_correlation"], f"assay QC observation[{index}].replicate_correlation")
                        ),
                        contamination_rate=(
                            None
                            if item.get("contamination_rate") is None
                            else _input_number(item["contamination_rate"], f"assay QC observation[{index}].contamination_rate")
                        ),
                        controls_passed=self._optional_bool(item.get("controls_passed")),
                        source_id=_input_text(
                            item.get("source_id", "assay-qc-input"),
                            f"assay QC observation[{index}].source_id",
                        ),
                    )
                )
            observations = tuple(observations_list)
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
        if type(value) is not bool:
            raise ValidationError("boolean field must be true or false")
        return value

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
                variant_id=_input_text(raw["variant_id"], "variant_id"),
                edge_id=_input_text(
                    raw.get("edge_id", f"{raw['variant_id']}:{role_id}"), "edge_id"
                ),
                case_context=context,
                observations=observations,
                minimum_context_score=_input_number(
                    raw.get("minimum_context_score", 0.35), "minimum_context_score"
                ),
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
        channel = _input_text(raw.get("channel", expected_channel), "observation channel")
        if channel != expected_channel:
            raise ValidationError(
                f"observation channel {channel!r} does not match role channel {expected_channel!r}"
            )
        payload_raw = raw.get("payload", {})
        if not isinstance(payload_raw, Mapping):
            raise ValidationError("observation payload must be a mapping")
        return ContextObservation(
            observation_id=_input_text(raw["observation_id"], "observation_id"),
            source_id=_input_text(raw["source_id"], "observation source_id"),
            source_version=_input_text(raw["source_version"], "observation source_version"),
            context=ReferenceContext.from_dict(context_raw),
            channel=channel,
            state=EvidenceState(_input_text(raw["state"], "observation state")),
            tier=EvidenceTier(_input_text(raw["tier"], "observation tier")),
            score=(
                None
                if raw.get("score") is None
                else _input_number(raw["score"], "observation score")
            ),
            confidence=_input_number(raw["confidence"], "observation confidence"),
            summary=_input_text(raw["summary"], "observation summary"),
            payload=dict(payload_raw),
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
        window_bp = query_raw.get("window_bp", 2_000)
        encode_limit = query_raw.get("encode_limit", 25)
        if type(window_bp) is not int or type(encode_limit) is not int:
            raise ValidationError("atlas query limits must be integers")
        return AtlasQuery(
            variant_id=_input_text(query_raw.get("variant_id", variant.variant_id), "variant_id"),
            window_bp=window_bp,
            include_encode_catalog=_input_bool(
                query_raw.get("include_encode_catalog", False), "include_encode_catalog"
            ),
            encode_assay_title=(
                _input_text(query_raw["encode_assay_title"], "encode_assay_title")
                if query_raw.get("encode_assay_title") is not None
                else None
            ),
            encode_biosample=(
                _input_text(query_raw["encode_biosample"], "encode_biosample")
                if query_raw.get("encode_biosample") is not None
                else None
            ),
            encode_limit=encode_limit,
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
            if type(getattr(result, "state", None)) is not InferenceState:
                raise ValidationError("inference extension returned an invalid state")
            uncertainty = _input_number(
                getattr(result, "uncertainty", None), f"{scope} uncertainty"
            )
            if not 0.0 <= uncertainty <= 1.0:
                raise ValidationError(f"{scope} uncertainty must be between 0 and 1")
            content_address = _input_text(
                getattr(result, "content_address", None), f"{scope} content_address"
            )
            payload = result.to_dict()
            if not isinstance(payload, Mapping) or any(
                type(key) is not str for key in payload
            ):
                raise ValidationError(f"{scope} result payload must be a mapping")
            sources = _input_strings(payload.get("source_ids", ()), f"{scope} source_ids")
            if not sources:
                sources = ("declared_inference_input",)
            limitations = _input_strings(
                getattr(result, "limitations", ()), f"{scope} limitations"
            )
        except (AttributeError, TypeError, ValueError, ValidationError, KeyError) as exc:
            return Abstention(
                f"invalid_{scope}_payload",
                scope,
                str(exc),
                missing_inputs,
            )
        state = EvidenceState(result.state.value)
        return EvidenceEnvelope(
            evidence_id=f"{scope}:{content_address}",
            agent_id=request.agent_id,
            tool_id=request.tool_id,
            state=state,
            tier=EvidenceTier.COMPUTED,
            claim_summary=(
                f"{scope} result is {result.state.value}; uncertainty={uncertainty:.3f}."
            ),
            payload_hash=content_address,
            source_ids=sources,
            provenance_digest=request.provenance.digest,
            confidence=round(1.0 - uncertainty, 6),
            limitations=limitations
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
        http_status = receipt_raw.get("http_status")
        elapsed_seconds = receipt_raw.get("elapsed_seconds")
        response_hash = receipt_raw.get("response_hash")
        cache_expires_at = receipt_raw.get("cache_expires_at")
        error_type = receipt_raw.get("error_type")
        error_message = receipt_raw.get("error_message")
        receipt = FetchReceipt(
            source_id=_input_text(receipt_raw["source_id"], "receipt source_id"),
            source_version=_input_text(receipt_raw["source_version"], "receipt source_version"),
            url=_input_text(receipt_raw["url"], "receipt url"),
            request_hash=_input_text(receipt_raw["request_hash"], "receipt request_hash"),
            response_hash=(None if response_hash is None else _input_text(response_hash, "receipt response_hash")),
            status=FetchStatus(_input_text(receipt_raw["status"], "receipt status")),
            http_status=(None if http_status is None else _input_integer(http_status, "receipt http_status")),
            attempts=_input_integer(receipt_raw["attempts"], "receipt attempts"),
            retrieved_at=_input_text(receipt_raw["retrieved_at"], "receipt retrieved_at"),
            elapsed_seconds=(None if elapsed_seconds is None else _input_number(elapsed_seconds, "receipt elapsed_seconds")),
            cache_expires_at=(None if cache_expires_at is None else _input_text(cache_expires_at, "receipt cache_expires_at")),
            warnings=_input_strings(receipt_raw.get("warnings", ()), "receipt warnings"),
            error_type=(None if error_type is None else _input_text(error_type, "receipt error_type")),
            error_message=(None if error_message is None else _input_text(error_message, "receipt error_message")),
        )
        return SequenceSlice(
            assembly=_input_text(raw["assembly"], "sequence assembly"),
            chromosome=_input_text(raw["chromosome"], "sequence chromosome"),
            start=_input_integer(raw["start"], "sequence start"),
            end=_input_integer(raw["end"], "sequence end"),
            sequence=_input_text(raw["sequence"], "sequence"),
            source_id=_input_text(raw["source_id"], "sequence source_id"),
            receipt=receipt,
        )

    @staticmethod
    def _motifs(raw: object) -> tuple[MotifDefinition, ...]:
        if not isinstance(raw, (list, tuple)):
            raise ValidationError("motifs must be a list")
        if len(raw) > 10_000:
            raise ValidationError("motifs exceed the maximum count")
        motifs: list[MotifDefinition] = []
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                raise ValidationError(f"motifs[{index}] must be a mapping")
            motifs.append(
                MotifDefinition(
                    motif_id=_input_text(item["motif_id"], f"motifs[{index}].motif_id"),
                    name=_input_text(
                        item.get("name", item.get("label", "")),
                        f"motifs[{index}].name",
                    ),
                    pattern=_input_text(item["pattern"], f"motifs[{index}].pattern"),
                    source_id=_input_text(
                        item.get("source_id", "declared_motif"),
                        f"motifs[{index}].source_id",
                    ),
                )
            )
        if len({motif.motif_id for motif in motifs}) != len(motifs):
            raise ValidationError("motifs must contain unique motif_id values")
        return tuple(motifs)

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
                features: dict[str, float] = {}
                for key, value in features_raw.items():
                    name = _input_text(key, "uncertainty feature name")
                    if name in features:
                        raise ValidationError("uncertainty features must have unique names")
                    features[name] = _input_number(value, f"uncertainty feature {name}")
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
        depends_on = _input_strings(raw.get("depends_on", ()), "claim depends_on")
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValidationError("claim payload must be a mapping")
        score_raw = raw.get("score")
        score = None if score_raw is None else _input_number(score_raw, "claim score")
        return EvidenceClaim(
            evidence_id=_input_text(raw["evidence_id"], "claim evidence_id"),
            edge_id=_input_text(raw["edge_id"], "claim edge_id"),
            source_id=_input_text(raw["source_id"], "claim source_id"),
            channel=_input_text(raw["channel"], "claim channel"),
            state=EvidenceState(_input_text(raw["state"], "claim state")),
            tier=EvidenceTier(_input_text(raw["tier"], "claim tier")),
            score=score,
            confidence=_input_number(raw["confidence"], "claim confidence"),
            context=ReferenceContext.from_dict(context_raw),
            summary=_input_text(raw["summary"], "claim summary"),
            payload=payload,
            depends_on=depends_on,
            produced_by=_input_text(
                raw.get("produced_by", "control_plane_input"), "claim produced_by"
            ),
            created_at=_input_text(
                raw.get("created_at", "control-plane-input"), "claim created_at"
            ),
            supersedes=(
                _input_text(raw["supersedes"], "claim supersedes")
                if raw.get("supersedes") is not None
                else None
            ),
        )

    @staticmethod
    def _domain_profile(raw: object) -> DomainProfile | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise ValidationError("domain_profile must be a mapping")
        feature_ranges = raw.get("feature_ranges")
        if not isinstance(feature_ranges, Mapping):
            raise ValidationError("domain_profile.feature_ranges must be a mapping")
        ranges: dict[str, tuple[float, float]] = {}
        for key, value in feature_ranges.items():
            name = _input_text(key, "domain feature name")
            if not isinstance(value, (list, tuple)) or len(value) != 2:
                raise ValidationError(f"domain feature range for {name} must have two values")
            low = _input_number(value[0], f"domain feature range {name}[0]")
            high = _input_number(value[1], f"domain feature range {name}[1]")
            if low > high:
                raise ValidationError(f"domain feature range for {name} is reversed")
            ranges[name] = (low, high)
        return DomainProfile(
            profile_id=_input_text(raw["profile_id"], "domain profile_id"),
            context_key=_input_text(raw["context_key"], "domain context_key"),
            required_features=_input_strings(raw["required_features"], "domain required_features"),
            feature_ranges=ranges,
            source_version=_input_text(raw["source_version"], "domain source_version"),
            model_digest=(
                _input_text(raw["model_digest"], "domain model_digest")
                if raw.get("model_digest") is not None
                else None
            ),
            watch_threshold=_input_number(raw.get("watch_threshold", 0.15), "domain watch_threshold"),
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
        if not isinstance(raw, Mapping):
            raise ValidationError("uncertainty report must be a mapping")
        components_raw = raw.get("components", ())
        if not isinstance(components_raw, (list, tuple)):
            raise ValidationError("uncertainty report components must be an array")
        components_list: list[UncertaintyComponent] = []
        for index, item in enumerate(components_raw):
            if not isinstance(item, Mapping):
                raise ValidationError(f"uncertainty component[{index}] must be a mapping")
            name_raw = item.get("name", item.get("component_id", item.get("label")))
            components_list.append(
                UncertaintyComponent(
                    name=_input_text(name_raw, f"uncertainty component[{index}].name"),
                    value=_input_number(
                        item["value"], f"uncertainty component[{index}].value"
                    ),
                    rationale=_input_text(
                        item["rationale"], f"uncertainty component[{index}].rationale"
                    ),
                    evidence_ids=_input_strings(
                        item.get("evidence_ids", ()),
                        f"uncertainty component[{index}].evidence_ids",
                    ),
                )
            )
        components = tuple(components_list)
        if not components:
            raise ValidationError("uncertainty report requires components")
        ood_raw = raw.get("ood")
        ood: OODAssessment | None = None
        if isinstance(ood_raw, Mapping):
            ood = OODAssessment(
                status=OODStatus(_input_text(ood_raw["status"], "uncertainty OOD status")),
                distance=_input_number(ood_raw["distance"], "uncertainty OOD distance"),
                missing_features=_input_strings(
                    ood_raw.get("missing_features", ()),
                    "uncertainty OOD missing_features",
                ),
                out_of_range_features=_input_strings(
                    ood_raw.get("out_of_range_features", ()),
                    "uncertainty OOD out_of_range_features",
                ),
                warnings=_input_strings(
                    ood_raw.get("warnings", ()), "uncertainty OOD warnings"
                ),
                profile_id=_input_text(ood_raw["profile_id"], "uncertainty OOD profile_id"),
                content_address=_input_text(
                    ood_raw["content_address"], "uncertainty OOD content_address"
                ),
            )
        return UncertaintyReport(
            overall=_input_number(raw["overall"], "uncertainty overall"),
            band=UncertaintyBand(_input_text(raw["band"], "uncertainty band")),
            components=components,
            ood=ood,
            limitations=_input_strings(
                raw.get("limitations", ()), "uncertainty limitations"
            ),
            content_address=_input_text(
                raw["content_address"], "uncertainty content_address"
            ),
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
            observation_id=_input_text(raw["observation_id"], "cohort observation_id"),
            subject_id=_input_text(raw["subject_id"], "cohort subject_id"),
            locus_id=_input_text(raw["locus_id"], "cohort locus_id"),
            mutated=_input_bool(raw["mutated"], "cohort mutated"),
            callable=_input_bool(raw["callable"], "cohort callable"),
            mutability_score=_input_number(raw["mutability_score"], "cohort mutability_score"),
            chromatin_score=_input_number(raw["chromatin_score"], "cohort chromatin_score"),
            ancestry_group=_input_text(raw["ancestry_group"], "cohort ancestry_group"),
            disease_class=_input_text(raw["disease_class"], "cohort disease_class"),
            context=ReferenceContext.from_dict(context_raw),
        )

    def _causal(self, request: InvocationRequest) -> EvidenceEnvelope | Abstention:
        raw = request.input_payload
        path_id = raw.get("path_id")
        edges_raw = raw.get("edges")
        if not isinstance(edges_raw, (list, tuple)):
            return Abstention(
                "missing_causal_payload",
                "causal_lattice",
                "Causal lattice assembly requires path_id and edge mappings.",
                ("path_id", "edges"),
            )
        try:
            path_id = _input_text(path_id, "path_id")
            edges = tuple(self._hypothesis_edge(item) for item in edges_raw)
            summary = self.causal.summarize(
                path_id,
                edges,
                alternatives=_input_strings(raw.get("alternatives", ()), "alternatives"),
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
            edge_id=_input_text(raw["edge_id"], "edge_id"),
            edge_type=EdgeType(_input_text(raw["edge_type"], "edge_type")),
            source_id=_input_text(raw["source_id"], "edge source_id"),
            target_id=_input_text(raw["target_id"], "edge target_id"),
            support=_input_number(raw["support"], "edge support"),
            uncertainty=_input_number(raw["uncertainty"], "edge uncertainty"),
            context_fit=_input_number(raw["context_fit"], "edge context_fit"),
            claim_ids=_input_strings(raw["claim_ids"], "edge claim_ids"),
            support_level=SupportLevel(_input_text(raw["support_level"], "support_level")),
            alternatives=_input_strings(raw.get("alternatives", ()), "edge alternatives"),
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
                source_version_before=_input_text(
                    raw["source_version_before"], "source_version_before"
                ),
                source_version_after=_input_text(
                    raw["source_version_after"], "source_version_after"
                ),
                reason=_input_text(raw["reason"], "reclassification reason"),
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
        if not isinstance(raw, Mapping):
            raise ValidationError("dossier must be a mapping")
        hypotheses = tuple(cls._hypothesis_from_mapping(item) for item in raw["hypotheses"])
        evidence = tuple(cls._claim_from_mapping(item) for item in raw["evidence"])
        experiments = tuple(cls._experiment_from_mapping(item) for item in raw["experiments"])
        review_raw = raw.get("review")
        review = cls._review_from_mapping(review_raw) if isinstance(review_raw, Mapping) else None
        if review_raw is not None and review is None:
            raise ValidationError("dossier review must be a mapping or null")
        warnings = _input_strings(raw.get("warnings", ()), "dossier warnings")
        source_bundle_addresses = _input_strings(
            raw.get("source_bundle_addresses", ()), "dossier source_bundle_addresses"
        )
        receipts_raw = raw.get("source_receipts", ())
        if not isinstance(receipts_raw, (list, tuple)):
            raise ValidationError("dossier source_receipts must be an array")
        if any(not isinstance(item, Mapping) for item in receipts_raw):
            raise ValidationError("dossier source_receipts must contain mappings")
        return Dossier(
            dossier_id=_input_text(raw["dossier_id"], "dossier_id"),
            case_id=_input_text(raw["case_id"], "case_id"),
            run_id=_input_text(raw["run_id"], "run_id"),
            created_at=_input_text(raw["created_at"], "dossier created_at"),
            input_address=_input_text(raw["input_address"], "dossier input_address"),
            hypotheses=hypotheses,
            evidence=evidence,
            experiments=experiments,
            review=review,
            research_use_only=_input_bool(raw["research_use_only"], "research_use_only"),
            policy_version=_input_text(raw["policy_version"], "policy_version"),
            event_head=_input_text(raw["event_head"], "event_head"),
            content_address=_input_text(raw["content_address"], "dossier content_address"),
            status=ResearchStatus(_input_text(raw["status"], "dossier status")),
            warnings=warnings,
            source_receipts=tuple(dict(item) for item in receipts_raw),
            source_bundle_addresses=source_bundle_addresses,
        )

    @classmethod
    def _hypothesis_from_mapping(cls, raw: object) -> Hypothesis:
        if not isinstance(raw, Mapping):
            raise ValidationError("each dossier hypothesis must be a mapping")
        context_raw = raw.get("context")
        if not isinstance(context_raw, Mapping):
            raise ValidationError("each hypothesis requires a context mapping")
        edges_raw = raw["edges"]
        if not isinstance(edges_raw, (list, tuple)):
            raise ValidationError("hypothesis edges must be an array")
        return Hypothesis(
            hypothesis_id=_input_text(raw["hypothesis_id"], "hypothesis_id"),
            variant_id=_input_text(raw["variant_id"], "hypothesis variant_id"),
            element_id=_input_text(raw["element_id"], "hypothesis element_id"),
            gene_id=_input_text(raw["gene_id"], "hypothesis gene_id"),
            state_id=_input_text(raw["state_id"], "hypothesis state_id"),
            mechanism=_input_text(raw["mechanism"], "hypothesis mechanism"),
            context=ReferenceContext.from_dict(context_raw),
            edges=tuple(cls._hypothesis_edge(item) for item in edges_raw),
            support=_input_number(raw["support"], "hypothesis support"),
            uncertainty=_input_number(raw["uncertainty"], "hypothesis uncertainty"),
            status=ResearchStatus(
                _input_text(raw.get("status", ResearchStatus.DRAFT.value), "hypothesis status")
            ),
            missing_evidence=_input_strings(
                raw.get("missing_evidence", ()), "hypothesis missing_evidence"
            ),
            negative_evidence=_input_strings(
                raw.get("negative_evidence", ()), "hypothesis negative_evidence"
            ),
            alternatives=_input_strings(raw.get("alternatives", ()), "hypothesis alternatives"),
            provenance=_input_strings(raw.get("provenance", ()), "hypothesis provenance"),
        )

    @staticmethod
    def _experiment_from_mapping(raw: object) -> ExperimentOption:
        if not isinstance(raw, Mapping):
            raise ValidationError("each dossier experiment must be a mapping")
        return ExperimentOption(
            option_id=_input_text(raw["option_id"], "option_id"),
            assay=AssayType(_input_text(raw["assay"], "assay")),
            tests_edges=_input_strings(raw["tests_edges"], "tests_edges"),
            expected_information_gain=_input_number(
                raw["expected_information_gain"], "expected_information_gain"
            ),
            feasibility=_input_number(raw["feasibility"], "feasibility"),
            cost_class=_input_text(raw["cost_class"], "cost_class"),
            required_context=_input_strings(raw["required_context"], "required_context"),
            controls=_input_strings(raw["controls"], "controls"),
            readouts=_input_strings(raw["readouts"], "readouts"),
            limitations=_input_strings(raw["limitations"], "limitations"),
        )

    @staticmethod
    def _review_from_mapping(raw: Mapping[str, Any]) -> ReviewDecision:
        return ReviewDecision(
            review_id=_input_text(raw["review_id"], "review_id"),
            case_id=_input_text(raw["case_id"], "review case_id"),
            reviewer=_input_text(raw["reviewer"], "reviewer"),
            state=ReviewState(_input_text(raw["state"], "review state")),
            reviewed_hypothesis_ids=_input_strings(
                raw["reviewed_hypothesis_ids"], "reviewed_hypothesis_ids"
            ),
            rationale=_input_text(raw["rationale"], "review rationale"),
            checked_claim_ids=_input_strings(raw["checked_claim_ids"], "checked_claim_ids"),
            created_at=_input_text(
                raw.get("created_at", "control-plane-input"), "review created_at"
            ),
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
                genome_build=_input_text(raw.get("genome_build", "GRCh38"), "genome_build"),
                variant_id=(
                    _input_text(raw["variant_id"], "variant_id")
                    if raw.get("variant_id") is not None
                    else None
                ),
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
                effect_size=_input_number(raw["effect_size"], "effect_size"),
                baseline_rate=_input_number(raw.get("baseline_rate", 0.5), "baseline_rate"),
                alpha=_input_number(raw.get("alpha", 0.05), "alpha"),
                target_power=_input_number(raw.get("target_power", 0.80), "target_power"),
                controls=_input_strings(raw.get("controls", ()), "controls"),
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
        try:
            baseline_values = self._metric_mapping(baseline, "baseline")
            current_values = self._metric_mapping(current, "current")
            report = self.drift.compare(
                baseline_values,
                current_values,
                case_id=request.mission.mission_id,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            return Abstention(
                "invalid_drift_metrics",
                "drift_monitor",
                str(exc),
                ("baseline", "current"),
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
        return _input_number(value, "drift metric")

    @classmethod
    def _metric_mapping(cls, raw: Mapping[str, Any], field: str) -> dict[str, float | None]:
        if len(raw) > 4096 or any(type(key) is not str for key in raw):
            raise ValidationError(f"{field} metrics must have bounded string keys")
        result: dict[str, float | None] = {}
        for key, value in raw.items():
            name = _input_text(key, f"{field} metric name")
            if name in result:
                raise ValidationError(f"{field} metrics must have unique names")
            result[name] = cls._optional_float(value)
        return result

    def manifest(self) -> dict[str, Any]:
        return {
            "registry": self.executor.registry.manifest(),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "binding_count": len(self.bindings),
        }
