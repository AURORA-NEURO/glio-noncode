"""Executable bindings from bounded control-plane tools to domain modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .atlas import AtlasQuery, PublicAtlasRetriever
from .causal import CausalLattice
from .cohort import CohortObservation, RecurrenceModel
from .control_plane import (
    Abstention,
    ControlPlaneExecutor,
    EvidenceEnvelope,
    InvocationRequest,
    MissionPlanner,
    WorkflowDecision,
    default_control_plane_registry,
)
from .data_sources import FetchReceipt, FetchStatus, SequenceSlice
from .errors import ValidationError
from .identity import normalize_variant, parse_variant
from .intake import VariantIntake
from .lifecycle import DriftMonitor, LifecycleReclassifier, ReviewPacketBuilder
from .models import (
    AssayType,
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
from .sequence_inference import (
    MotifDefinition,
    SequenceAnalysisResult,
    SequenceAnalysisState,
    SequenceInference,
)
from .serialization import content_hash
from .uncertainty import (
    CalibrationEvaluator,
    DomainProfile,
    OutOfDomainDetector,
    UncertaintyBand,
    UncertaintyPropagator,
)
from .validation_design import PowerPlanner


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
        self.reclassifier = LifecycleReclassifier()
        self.review_packets = ReviewPacketBuilder()
        self.calibration = CalibrationEvaluator()
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
            "A15.publish",
            self._atlas,
            "atlas.PublicAtlasRetriever",
            "Retrieve bounded public reference observations with source receipts.",
        )
        self._bind(
            "A23.publish",
            self._sequence,
            "sequence_inference.SequenceInference",
            "Compare reference and alternate sequence windows with motif deltas.",
        )
        self._bind(
            "A36.publish",
            self._uncertainty,
            "uncertainty.UncertaintyPropagator",
            "Aggregate typed uncertainty components and optional domain assessment.",
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
