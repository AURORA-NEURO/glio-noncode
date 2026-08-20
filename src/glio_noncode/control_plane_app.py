"""Executable bindings from bounded control-plane tools to domain modules."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .control_plane import (
    Abstention,
    ControlPlaneExecutor,
    EvidenceEnvelope,
    InvocationRequest,
    MissionPlanner,
    WorkflowDecision,
    default_control_plane_registry,
)
from .errors import ValidationError
from .identity import parse_variant
from .intake import VariantIntake
from .lifecycle import DriftMonitor, ReviewPacketBuilder
from .models import EvidenceState, EvidenceTier
from .serialization import content_hash
from .uncertainty import CalibrationEvaluator, UncertaintyPropagator
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

    def __init__(self, executor: ControlPlaneExecutor | None = None) -> None:
        self.executor = executor or ControlPlaneExecutor(default_control_plane_registry())
        self.intake = VariantIntake()
        self.planner = MissionPlanner(self.executor.registry)
        self.power = PowerPlanner()
        self.drift = DriftMonitor()
        self.review_packets = ReviewPacketBuilder()
        self.calibration = CalibrationEvaluator()
        self.uncertainty = UncertaintyPropagator()
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
