"""Executable bindings from bounded control-plane tools to domain modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .atlas import AtlasQuery, PublicAtlasRetriever
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
from .lifecycle import DriftMonitor, ReviewPacketBuilder
from .models import EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext
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
