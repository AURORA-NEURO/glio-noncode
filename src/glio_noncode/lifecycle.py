"""Review, reclassification, and drift lifecycle orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .models import Dossier, EvidenceState, ResearchStatus
from .monitoring import MonitorRegistry, SignalObservation, SignalStatus
from .reclassification import EvidenceDelta, ReclassificationEngine, ReclassificationRecord
from .serialization import content_hash, jsonable
from .validation import ReleaseGate, ValidationReport


class ReviewPriority(StrEnum):
    """Review queue priority."""

    ROUTINE = "routine"
    ELEVATED = "elevated"
    BLOCKING = "blocking"


@dataclass(frozen=True, slots=True)
class ReviewPacket:
    """Human-readable review work item with machine-readable blockers."""

    packet_id: str
    dossier_id: str
    case_id: str
    priority: ReviewPriority
    validation: ValidationReport
    hypothesis_ids: tuple[str, ...]
    claim_state_counts: Mapping[str, int]
    open_questions: tuple[str, ...]
    required_expertise: tuple[str, ...]
    release_blockers: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReviewPacketBuilder:
    """Build review packets without deciding the expert's conclusion."""

    def __init__(self, release_gate: ReleaseGate | None = None) -> None:
        self.release_gate = release_gate or ReleaseGate()

    def build(self, dossier: Dossier) -> ReviewPacket:
        validation = self.release_gate.check(dossier)
        counts = {state.value: 0 for state in EvidenceState}
        for claim in dossier.evidence:
            counts[claim.state.value] += 1
        open_questions: list[str] = []
        for hypothesis in dossier.hypotheses:
            open_questions.extend(hypothesis.missing_evidence)
            open_questions.extend(hypothesis.alternatives)
        expertise: set[str] = set()
        channels = {claim.channel for claim in dossier.evidence}
        if channels & {"regulatory_overlap", "reference_annotation"}:
            expertise.add("regulatory genomics")
        if channels & {"motif_delta", "sequence_model"}:
            expertise.add("sequence and motif interpretation")
        if channels & {"accessibility", "histone_activity", "methylation"}:
            expertise.add("epigenomics")
        if channels & {"contact", "boundary_support"}:
            expertise.add("3D genome or chromatin topology")
        if channels & {"perturbation", "functional"}:
            expertise.add("functional assay design")
        if not expertise:
            expertise.add("research domain review")
        blockers = tuple(
            issue.message for issue in validation.issues if issue.severity.value == "error"
        )
        if (
            blockers
            or dossier.status == ResearchStatus.RELEASED_RESEARCH
            and dossier.review is None
        ):
            priority = ReviewPriority.BLOCKING
        elif dossier.status == ResearchStatus.REVIEW_REQUIRED:
            priority = ReviewPriority.ELEVATED
        else:
            priority = ReviewPriority.ROUTINE
        payload = {
            "dossier_id": dossier.dossier_id,
            "priority": priority,
            "hypothesis_ids": tuple(item.hypothesis_id for item in dossier.hypotheses),
            "claim_state_counts": counts,
            "open_questions": tuple(sorted(set(open_questions))),
            "required_expertise": tuple(sorted(expertise)),
            "release_blockers": blockers,
        }
        return ReviewPacket(
            packet_id="review-packet-" + content_hash(payload).split(":", 1)[1][:20],
            dossier_id=dossier.dossier_id,
            case_id=dossier.case_id,
            priority=priority,
            validation=validation,
            hypothesis_ids=tuple(item.hypothesis_id for item in dossier.hypotheses),
            claim_state_counts=counts,
            open_questions=tuple(sorted(set(open_questions))),
            required_expertise=tuple(sorted(expertise)),
            release_blockers=blockers,
            content_address=content_hash(payload),
        )


@dataclass(frozen=True, slots=True)
class ReclassificationPlan:
    """Selective recomputation plan after source or evidence changes."""

    plan_id: str
    previous_dossier_id: str
    current_dossier_id: str
    deltas: tuple[EvidenceDelta, ...]
    records: tuple[ReclassificationRecord, ...]
    requires_review: bool
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LifecycleReclassifier:
    """Compare immutable dossier snapshots and name affected hypotheses."""

    def __init__(self, engine: ReclassificationEngine | None = None) -> None:
        self.engine = engine or ReclassificationEngine()

    def plan(
        self,
        previous: Dossier,
        current: Dossier,
        *,
        source_version_before: str,
        source_version_after: str,
        reason: str,
    ) -> ReclassificationPlan:
        deltas = self.engine.compare(
            previous.evidence,
            current.evidence,
            source_version_before=source_version_before,
            source_version_after=source_version_after,
            reason=reason,
        )
        current_by_id = {hypothesis.hypothesis_id: hypothesis for hypothesis in current.hypotheses}
        records: list[ReclassificationRecord] = []
        for hypothesis in previous.hypotheses:
            if hypothesis.hypothesis_id in current_by_id:
                records.append(self.engine.impact_for(hypothesis, deltas))
        requires_review = (
            source_version_before != source_version_after
            or any(record.recompute_required for record in records)
            or bool(deltas)
        )
        payload = {
            "previous": previous.dossier_id,
            "current": current.dossier_id,
            "deltas": deltas,
            "records": records,
            "reason": reason,
        }
        return ReclassificationPlan(
            plan_id="reclass-plan-" + content_hash(payload).split(":", 1)[1][:20],
            previous_dossier_id=previous.dossier_id,
            current_dossier_id=current.dossier_id,
            deltas=deltas,
            records=tuple(records),
            requires_review=requires_review,
            reason=reason,
            content_address=content_hash(payload),
        )


class DriftStatus(StrEnum):
    """Aggregate drift state."""

    HEALTHY = "healthy"
    WATCH = "watch"
    ALERT = "alert"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DriftSignal:
    """One baseline/current metric comparison."""

    metric: str
    baseline: float | None
    current: float | None
    delta: float | None
    status: DriftStatus
    note: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DriftReport:
    """Versioned source/model drift snapshot."""

    report_id: str
    status: DriftStatus
    signals: tuple[DriftSignal, ...]
    monitoring_observations: tuple[SignalObservation, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DriftMonitor:
    """Compare run metrics with a declared baseline and monitoring thresholds."""

    def __init__(self, registry: MonitorRegistry | None = None) -> None:
        self.registry = registry or MonitorRegistry()

    def compare(
        self,
        baseline: Mapping[str, float | None],
        current: Mapping[str, float | None],
        *,
        case_id: str,
    ) -> DriftReport:
        signals: list[DriftSignal] = []
        for metric in sorted(set(baseline) | set(current)):
            before = baseline.get(metric)
            after = current.get(metric)
            delta = round(after - before, 6) if before is not None and after is not None else None
            if before is None or after is None:
                status = DriftStatus.UNKNOWN
                note = "Baseline or current metric is missing."
            elif abs(delta or 0.0) >= 0.25:
                status = DriftStatus.ALERT
                note = "Metric changed materially; inspect source, model, or workflow drift."
            elif abs(delta or 0.0) >= 0.10:
                status = DriftStatus.WATCH
                note = "Metric moved enough to warrant review."
            else:
                status = DriftStatus.HEALTHY
                note = "Metric is within the coarse drift envelope."
            signals.append(DriftSignal(metric, before, after, delta, status, note))
        observations = self.registry.evaluate_run(current, case_id=case_id)
        statuses = [signal.status for signal in signals]
        if DriftStatus.ALERT in statuses or any(
            item.status == SignalStatus.ALERT for item in observations
        ):
            overall = DriftStatus.ALERT
        elif DriftStatus.WATCH in statuses or any(
            item.status == SignalStatus.WATCH for item in observations
        ):
            overall = DriftStatus.WATCH
        elif not signals or DriftStatus.UNKNOWN in statuses:
            overall = DriftStatus.UNKNOWN
        else:
            overall = DriftStatus.HEALTHY
        warnings = (
            "Drift thresholds are operational review signals, not proof of scientific invalidity.",
        )
        payload = {
            "case_id": case_id,
            "signals": signals,
            "observations": observations,
            "status": overall,
        }
        return DriftReport(
            report_id="drift-" + content_hash(payload).split(":", 1)[1][:20],
            status=overall,
            signals=tuple(signals),
            monitoring_observations=observations,
            warnings=warnings,
            content_address=content_hash(payload),
        )
