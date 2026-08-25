"""Provenance-first review workspaces for replay-verified research runs.

The ordinary workspace is optimized for navigation: records, filters, facets,
and variant inspection. This module is the review read model that sits beside
it. It retains the decomposed hypothesis graph, evidence states, alternatives,
source lineage, review work items, and explicit cross-snapshot deltas without
turning the dossier into one ranking score.

The projection is deliberately aggregate. Evidence payloads and producer
metadata are not copied into the public view. A persisted workspace is built
only after run replay verification; a baseline run is required to pass the same
gate before deltas are emitted. Review state is not a scientific conclusion.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .models import Dossier, EvidenceClaim, EvidenceState, Hypothesis, HypothesisEdge, ResearchStatus
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .runtime import CaseRuntime
from .serialization import content_hash, jsonable, require_non_empty


REVIEW_WORKSPACE_VERSION = "review-workspace-v1"
REVIEW_WORKSPACE_SCHEMA_VERSION = "review-workspace-schema-v1"
REVIEW_WORKSPACE_MAX_HYPOTHESES = 500
REVIEW_WORKSPACE_MAX_EDGES = 5_000
REVIEW_WORKSPACE_MAX_EVIDENCE = 20_000
REVIEW_WORKSPACE_MAX_ALTERNATIVES = 5_000
REVIEW_WORKSPACE_MAX_DELTAS = 20_000
REVIEW_WORKSPACE_MAX_PROVENANCE = 5_000

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "contact",
        "contact_name",
        "credential",
        "credential_value",
        "email",
        "generated_by",
        "individual",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "model_version",
        "participant",
        "participant_id",
        "patient",
        "patient_id",
        "phone",
        "programming_language",
        "produced_by",
        "sample",
        "sample_id",
        "secret",
        "secret_key",
        "subject",
        "subject_id",
        "token",
    }
)


class ReviewWorkspaceState(StrEnum):
    """Review-readiness state, separate from biological support."""

    READY_FOR_REVIEW = "ready_for_review"
    REVIEW = "review"
    ABSTAINED = "abstained"
    BLOCKED = "blocked"


def _text(value: Any, field: str) -> str:
    return require_non_empty(str(value), field)


def _bounded(value: Any, field: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if not 0.0 <= result <= 1.0:
        raise ValidationError(f"{field} must be between 0 and 1")
    return round(result, 6)


def _unique(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _short_text(value: Any, limit: int = 500) -> str:
    text = str(value).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _public(value: Any) -> Any:
    """Drop forbidden keys recursively from an aggregate review value."""

    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public(item)
            for key, item in value.items()
            if str(key).casefold() not in _FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public(item) for item in value]
    return value


def _has_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or _has_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden(item) for item in value)
    return False


def _address(body: Any, prefix: str) -> str:
    return content_hash(_public(body), prefix=prefix)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceConfig:
    """Bounded review triage thresholds; these are not scientific cutoffs."""

    uncertainty_review_threshold: float = 0.5
    context_fit_review_threshold: float = 0.75
    max_hypotheses: int = REVIEW_WORKSPACE_MAX_HYPOTHESES
    max_edges: int = REVIEW_WORKSPACE_MAX_EDGES
    max_evidence: int = REVIEW_WORKSPACE_MAX_EVIDENCE
    max_alternatives: int = REVIEW_WORKSPACE_MAX_ALTERNATIVES
    max_deltas: int = REVIEW_WORKSPACE_MAX_DELTAS

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "uncertainty_review_threshold",
            _bounded(self.uncertainty_review_threshold, "uncertainty_review_threshold"),
        )
        object.__setattr__(
            self,
            "context_fit_review_threshold",
            _bounded(self.context_fit_review_threshold, "context_fit_review_threshold"),
        )
        ceilings = {
            "max_hypotheses": REVIEW_WORKSPACE_MAX_HYPOTHESES,
            "max_edges": REVIEW_WORKSPACE_MAX_EDGES,
            "max_evidence": REVIEW_WORKSPACE_MAX_EVIDENCE,
            "max_alternatives": REVIEW_WORKSPACE_MAX_ALTERNATIVES,
            "max_deltas": REVIEW_WORKSPACE_MAX_DELTAS,
        }
        for field_name, ceiling in ceilings.items():
            value = int(getattr(self, field_name))
            if value < 1 or value > ceiling:
                raise ValidationError(f"{field_name} is outside the configured ceiling")
            object.__setattr__(self, field_name, value)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> "ReviewWorkspaceConfig":
        if raw is not None and not isinstance(raw, Mapping):
            raise ValidationError("review workspace config must be an object")
        value = raw or {}
        return cls(**{key: value[key] for key in (
            "uncertainty_review_threshold",
            "context_fit_review_threshold",
            "max_hypotheses",
            "max_edges",
            "max_evidence",
            "max_alternatives",
            "max_deltas",
        ) if key in value})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewEvidenceView:
    """Public evidence claim view with payload-free provenance fields."""

    evidence_id: str
    edge_id: str
    source_id: str
    channel: str
    state: str
    tier: str
    score: float | None
    confidence: float
    context_key: str
    summary: str
    depends_on: tuple[str, ...]
    supersedes: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewEdgeView:
    """One decomposed edge with claim-state and source coverage."""

    edge_id: str
    hypothesis_id: str
    edge_type: str
    source_id: str
    target_id: str
    support: float
    uncertainty: float
    context_fit: float
    support_level: str
    claim_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    evidence_state_counts: Mapping[str, int]
    alternatives: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewAlternativeView:
    """An alternative explanation retained as a reviewable branch."""

    alternative_id: str
    hypothesis_id: str
    label: str
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewHypothesisView:
    """Hypothesis projection retaining component dimensions separately."""

    hypothesis_id: str
    variant_id: str
    element_id: str
    gene_id: str
    state_id: str
    mechanism: str
    context_key: str
    status: str
    support: float
    uncertainty: float
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    alternative_ids: tuple[str, ...]
    provenance_ids: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    negative_evidence: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewDelta:
    """One explicit before/after change; no aggregate ranking is implied."""

    delta_id: str
    item_type: str
    item_id: str
    dimension: str
    before: Any
    after: Any
    delta: float | None
    direction: str
    baseline_run_id: str
    current_run_id: str
    provenance_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewQueueItem:
    """Bounded human-review work item with an explainable priority band."""

    item_id: str
    item_type: str
    target_id: str
    priority: int
    reasons: tuple[str, ...]
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    state: str
    content_address: str

    def __post_init__(self) -> None:
        if self.priority not in {0, 1, 2, 3}:
            raise ValidationError("review queue priority must be between 0 and 3")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewProvenanceView:
    """Source-centric lineage summary for edges and claims."""

    provenance_id: str
    source_id: str
    edge_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    tiers: tuple[str, ...]
    states: tuple[str, ...]
    context_keys: tuple[str, ...]
    depends_on: tuple[str, ...]
    supersedes: tuple[str, ...]
    receipt_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewWorkspaceReport:
    """Complete review read model for one verified run and optional baseline."""

    workspace_id: str
    run_id: str
    case_id: str
    version: str
    state: ReviewWorkspaceState
    accepted: bool
    run_integrity: Mapping[str, Any]
    baseline_run_id: str | None
    baseline_integrity: Mapping[str, Any] | None
    hypotheses: tuple[ReviewHypothesisView, ...]
    edges: tuple[ReviewEdgeView, ...]
    evidence: tuple[ReviewEvidenceView, ...]
    alternatives: tuple[ReviewAlternativeView, ...]
    deltas: tuple[ReviewDelta, ...]
    provenance: tuple[ReviewProvenanceView, ...]
    review_queue: tuple[ReviewQueueItem, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _evidence_view(claim: EvidenceClaim) -> ReviewEvidenceView:
    body = {
        "evidence_id": claim.evidence_id,
        "edge_id": claim.edge_id,
        "source_id": claim.source_id,
        "channel": claim.channel,
        "state": claim.state.value,
        "tier": claim.tier.value,
        "score": None if claim.score is None else round(claim.score, 6),
        "confidence": round(claim.confidence, 6),
        "context_key": claim.context.key,
        "summary": _short_text(claim.summary),
        "depends_on": _unique(claim.depends_on),
        "supersedes": claim.supersedes,
    }
    return ReviewEvidenceView(**body, content_address=_address(body, "review-evidence"))


def _edge_view(
    hypothesis: Hypothesis,
    edge: HypothesisEdge,
    evidence_by_id: Mapping[str, EvidenceClaim],
) -> ReviewEdgeView:
    claims = tuple(evidence_by_id[claim_id] for claim_id in edge.claim_ids if claim_id in evidence_by_id)
    body = {
        "edge_id": edge.edge_id,
        "hypothesis_id": hypothesis.hypothesis_id,
        "edge_type": edge.edge_type.value,
        "source_id": edge.source_id,
        "target_id": edge.target_id,
        "support": round(edge.support, 6),
        "uncertainty": round(edge.uncertainty, 6),
        "context_fit": round(edge.context_fit, 6),
        "support_level": edge.support_level.value,
        "claim_ids": _unique(edge.claim_ids),
        "source_ids": _unique(claim.source_id for claim in claims),
        "evidence_state_counts": {
            state: sum(claim.state.value == state for claim in claims)
            for state in sorted({claim.state.value for claim in claims})
        },
        "alternatives": tuple(_short_text(item) for item in edge.alternatives),
    }
    return ReviewEdgeView(**body, content_address=_address(body, "review-edge"))


def _alternative_views(
    hypothesis: Hypothesis,
    edges: Sequence[ReviewEdgeView],
    evidence_by_id: Mapping[str, EvidenceClaim],
) -> tuple[ReviewAlternativeView, ...]:
    labels = list(hypothesis.alternatives)
    labels.extend(item for edge in hypothesis.edges for item in edge.alternatives)
    result: list[ReviewAlternativeView] = []
    for index, label in enumerate(dict.fromkeys(_short_text(item) for item in labels), start=1):
        normalized = label.casefold()
        edge_ids = tuple(
            edge.edge_id
            for edge in edges
            if normalized in {edge.edge_id.casefold(), edge.source_id.casefold(), edge.target_id.casefold()}
            or normalized in {item.casefold() for item in edge.alternatives}
        )
        evidence_ids = tuple(
            claim.evidence_id
            for claim in evidence_by_id.values()
            if claim.evidence_id.casefold() == normalized or claim.channel.casefold() == normalized
        )
        source_ids = _unique(
            source_id
            for edge in edges
            if edge.edge_id in edge_ids
            for source_id in edge.source_ids
        )
        states = {
            claim.state
            for claim in evidence_by_id.values()
            if claim.evidence_id in evidence_ids
        }
        state = (
            EvidenceState.CONTRADICTORY.value
            if EvidenceState.CONTRADICTORY in states
            else EvidenceState.SUPPORTED.value
            if EvidenceState.SUPPORTED in states
            else "review"
        )
        body = {
            "alternative_id": f"{hypothesis.hypothesis_id}:alternative:{index:03d}",
            "hypothesis_id": hypothesis.hypothesis_id,
            "label": label,
            "edge_ids": edge_ids,
            "evidence_ids": evidence_ids,
            "source_ids": source_ids,
            "state": state,
        }
        result.append(ReviewAlternativeView(**body, content_address=_address(body, "review-alternative")))
    return tuple(result)


def _provenance_views(
    dossier: Dossier,
    evidence_by_id: Mapping[str, EvidenceClaim],
    edge_views: Sequence[ReviewEdgeView],
) -> tuple[ReviewProvenanceView, ...]:
    by_source: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {
            "edges": set(),
            "evidence": set(),
            "tiers": set(),
            "states": set(),
            "contexts": set(),
            "depends": set(),
            "supersedes": set(),
            "receipts": set(),
        }
    )
    for claim in evidence_by_id.values():
        item = by_source[claim.source_id]
        item["evidence"].add(claim.evidence_id)
        item["edges"].add(claim.edge_id)
        item["tiers"].add(claim.tier.value)
        item["states"].add(claim.state.value)
        item["contexts"].add(claim.context.key)
        item["depends"].update(claim.depends_on)
        if claim.supersedes:
            item["supersedes"].add(claim.supersedes)
    for edge in edge_views:
        for source_id in edge.source_ids:
            by_source[source_id]["edges"].add(edge.edge_id)
    for receipt in dossier.source_receipts:
        if not isinstance(receipt, Mapping):
            continue
        source_id = str(receipt.get("source_id", "")).strip()
        receipt_id = str(receipt.get("content_address", receipt.get("receipt_id", ""))).strip()
        if source_id and receipt_id and not _has_forbidden({"source_id": source_id, "receipt_id": receipt_id}):
            by_source[source_id]["receipts"].add(receipt_id)
    result: list[ReviewProvenanceView] = []
    for source_id in sorted(by_source):
        item = by_source[source_id]
        body = {
            "provenance_id": f"source:{source_id}",
            "source_id": source_id,
            "edge_ids": tuple(sorted(item["edges"])),
            "evidence_ids": tuple(sorted(item["evidence"])),
            "tiers": tuple(sorted(item["tiers"])),
            "states": tuple(sorted(item["states"])),
            "context_keys": tuple(sorted(item["contexts"])),
            "depends_on": tuple(sorted(item["depends"])),
            "supersedes": tuple(sorted(item["supersedes"])),
            "receipt_ids": tuple(sorted(item["receipts"])),
        }
        result.append(ReviewProvenanceView(**body, content_address=_address(body, "review-provenance")))
    return tuple(result)


def _queue_item(
    item_type: str,
    target_id: str,
    priority: int,
    reasons: Iterable[str],
    edge_ids: Iterable[str],
    evidence_ids: Iterable[str],
    state: str,
) -> ReviewQueueItem:
    body = {
        "item_id": f"review:{item_type}:{target_id}",
        "item_type": item_type,
        "target_id": target_id,
        "priority": priority,
        "reasons": tuple(dict.fromkeys(str(item) for item in reasons if str(item).strip())),
        "edge_ids": _unique(edge_ids),
        "evidence_ids": _unique(evidence_ids),
        "state": state,
    }
    return ReviewQueueItem(**body, content_address=_address(body, "review-queue-item"))


def _build_review_queue(
    hypotheses: Sequence[Hypothesis],
    edge_views: Sequence[ReviewEdgeView],
    evidence_by_id: Mapping[str, EvidenceClaim],
    config: ReviewWorkspaceConfig,
) -> tuple[ReviewQueueItem, ...]:
    edges_by_hypothesis: dict[str, list[ReviewEdgeView]] = defaultdict(list)
    for edge in edge_views:
        edges_by_hypothesis[edge.hypothesis_id].append(edge)
    result: list[ReviewQueueItem] = []
    for hypothesis in hypotheses:
        edges = tuple(edges_by_hypothesis.get(hypothesis.hypothesis_id, ()))
        claim_ids = _unique(claim_id for edge in edges for claim_id in edge.claim_ids)
        reasons: list[str] = []
        priorities: list[int] = []
        if hypothesis.status in {ResearchStatus.DRAFT, ResearchStatus.REVIEW_REQUIRED}:
            reasons.append("hypothesis status requires human review")
            priorities.append(1)
        if hypothesis.uncertainty >= config.uncertainty_review_threshold:
            reasons.append("hypothesis uncertainty is at or above the review threshold")
            priorities.append(1)
        if hypothesis.missing_evidence:
            reasons.append("hypothesis declares missing evidence")
            priorities.append(1)
        if hypothesis.negative_evidence:
            reasons.append("negative evidence is retained for adjudication")
            priorities.append(1)
        for edge in edges:
            if edge.context_fit < config.context_fit_review_threshold:
                reasons.append(f"edge {edge.edge_id} has limited context fit")
                priorities.append(2)
            states = set(edge.evidence_state_counts)
            if EvidenceState.CONTRADICTORY.value in states:
                reasons.append(f"edge {edge.edge_id} has contradictory evidence")
                priorities.append(0)
            if EvidenceState.ABSTAINED.value in states or not edge.claim_ids:
                reasons.append(f"edge {edge.edge_id} has incomplete evidence coverage")
                priorities.append(1)
        if reasons:
            result.append(
                _queue_item(
                    "hypothesis",
                    hypothesis.hypothesis_id,
                    min(priorities),
                    reasons,
                    (edge.edge_id for edge in edges),
                    claim_ids,
                    hypothesis.status.value,
                )
            )
    for claim in evidence_by_id.values():
        if claim.state in {EvidenceState.CONTRADICTORY, EvidenceState.ABSTAINED, EvidenceState.OUT_OF_DOMAIN}:
            result.append(
                _queue_item(
                    "evidence",
                    claim.evidence_id,
                    0 if claim.state is EvidenceState.CONTRADICTORY else 1,
                    (f"evidence state is {claim.state.value}",),
                    (claim.edge_id,),
                    (claim.evidence_id,),
                    claim.state.value,
                )
            )
    return tuple(sorted(result, key=lambda item: (item.priority, item.item_type, item.target_id)))


def _direction(before: Any, after: Any) -> tuple[str, float | None]:
    if before is None and after is None:
        return "unchanged", None
    if before is None:
        return "introduced", None
    if after is None:
        return "removed", None
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        delta = round(float(after) - float(before), 6)
        return ("increase" if delta > 0 else "decrease" if delta < 0 else "unchanged"), delta
    return ("unchanged" if before == after else "changed"), None


def _delta(
    *,
    item_type: str,
    item_id: str,
    dimension: str,
    before: Any,
    after: Any,
    baseline_run_id: str,
    current_run_id: str,
    provenance_ids: Iterable[str],
) -> ReviewDelta:
    direction, numeric_delta = _direction(before, after)
    body = {
        "delta_id": f"{item_type}:{item_id}:{dimension}",
        "item_type": item_type,
        "item_id": item_id,
        "dimension": dimension,
        "before": before,
        "after": after,
        "delta": numeric_delta,
        "direction": direction,
        "baseline_run_id": baseline_run_id,
        "current_run_id": current_run_id,
        "provenance_ids": _unique(provenance_ids),
    }
    return ReviewDelta(**body, content_address=_address(body, "review-delta"))


def _map_hypotheses(dossier: Dossier) -> dict[str, Hypothesis]:
    return {item.hypothesis_id: item for item in dossier.hypotheses}


def _map_edges(dossier: Dossier) -> dict[str, tuple[Hypothesis, HypothesisEdge]]:
    return {
        edge.edge_id: (hypothesis, edge)
        for hypothesis in dossier.hypotheses
        for edge in hypothesis.edges
    }


def _build_deltas(
    baseline: Dossier,
    current: Dossier,
    *,
    baseline_run_id: str,
    current_run_id: str,
) -> tuple[ReviewDelta, ...]:
    result: list[ReviewDelta] = []
    baseline_hypotheses = _map_hypotheses(baseline)
    current_hypotheses = _map_hypotheses(current)
    for hypothesis_id in sorted(set(baseline_hypotheses) | set(current_hypotheses)):
        before = baseline_hypotheses.get(hypothesis_id)
        after = current_hypotheses.get(hypothesis_id)
        provenance = (after or before).provenance if after or before else ()
        if before is None or after is None:
            result.append(
                _delta(
                    item_type="hypothesis",
                    item_id=hypothesis_id,
                    dimension="presence",
                    before=before is not None,
                    after=after is not None,
                    baseline_run_id=baseline_run_id,
                    current_run_id=current_run_id,
                    provenance_ids=provenance,
                )
            )
            continue
        for dimension, before_value, after_value in (
            ("support", before.support, after.support),
            ("uncertainty", before.uncertainty, after.uncertainty),
            ("status", before.status.value, after.status.value),
            ("alternatives", before.alternatives, after.alternatives),
        ):
            if before_value != after_value:
                result.append(
                    _delta(
                        item_type="hypothesis",
                        item_id=hypothesis_id,
                        dimension=dimension,
                        before=before_value,
                        after=after_value,
                        baseline_run_id=baseline_run_id,
                        current_run_id=current_run_id,
                        provenance_ids=provenance,
                    )
                )
    baseline_edges = _map_edges(baseline)
    current_edges = _map_edges(current)
    for edge_id in sorted(set(baseline_edges) | set(current_edges)):
        before_pair = baseline_edges.get(edge_id)
        after_pair = current_edges.get(edge_id)
        if before_pair is None or after_pair is None:
            result.append(
                _delta(
                    item_type="edge",
                    item_id=edge_id,
                    dimension="presence",
                    before=before_pair is not None,
                    after=after_pair is not None,
                    baseline_run_id=baseline_run_id,
                    current_run_id=current_run_id,
                    provenance_ids=(),
                )
            )
            continue
        before_edge = before_pair[1]
        after_edge = after_pair[1]
        for dimension, before_value, after_value in (
            ("support", before_edge.support, after_edge.support),
            ("uncertainty", before_edge.uncertainty, after_edge.uncertainty),
            ("context_fit", before_edge.context_fit, after_edge.context_fit),
            ("support_level", before_edge.support_level.value, after_edge.support_level.value),
        ):
            if before_value != after_value:
                result.append(
                    _delta(
                        item_type="edge",
                        item_id=edge_id,
                        dimension=dimension,
                        before=before_value,
                        after=after_value,
                        baseline_run_id=baseline_run_id,
                        current_run_id=current_run_id,
                        provenance_ids=tuple(
                            claim.source_id
                            for claim in current.evidence
                            if claim.edge_id == edge_id
                        ),
                    )
                )
    baseline_evidence = {item.evidence_id: item for item in baseline.evidence}
    current_evidence = {item.evidence_id: item for item in current.evidence}
    for evidence_id in sorted(set(baseline_evidence) | set(current_evidence)):
        before = baseline_evidence.get(evidence_id)
        after = current_evidence.get(evidence_id)
        source_ids = ((after or before).source_id,) if after or before else ()
        if before is None or after is None:
            result.append(
                _delta(
                    item_type="evidence",
                    item_id=evidence_id,
                    dimension="presence",
                    before=before is not None,
                    after=after is not None,
                    baseline_run_id=baseline_run_id,
                    current_run_id=current_run_id,
                    provenance_ids=source_ids,
                )
            )
            continue
        for dimension, before_value, after_value in (
            ("score", before.score, after.score),
            ("confidence", before.confidence, after.confidence),
            ("state", before.state.value, after.state.value),
        ):
            if before_value != after_value:
                result.append(
                    _delta(
                        item_type="evidence",
                        item_id=evidence_id,
                        dimension=dimension,
                        before=before_value,
                        after=after_value,
                        baseline_run_id=baseline_run_id,
                        current_run_id=current_run_id,
                        provenance_ids=source_ids,
                    )
                )
    return tuple(sorted(result, key=lambda item: (item.item_type, item.item_id, item.dimension)))


def _empty_report(
    *,
    run_id: str,
    case_id: str,
    run_integrity: Mapping[str, Any],
    baseline_run_id: str | None,
    baseline_integrity: Mapping[str, Any] | None,
    state: ReviewWorkspaceState,
    accepted: bool,
    warnings: Iterable[str],
) -> ReviewWorkspaceReport:
    body = {
        "workspace_id": f"review:{run_id}",
        "run_id": run_id,
        "case_id": case_id,
        "version": REVIEW_WORKSPACE_VERSION,
        "state": state,
        "accepted": accepted,
        "run_integrity": _public(run_integrity),
        "baseline_run_id": baseline_run_id,
        "baseline_integrity": _public(baseline_integrity) if baseline_integrity else None,
        "hypotheses": (),
        "edges": (),
        "evidence": (),
        "alternatives": (),
        "deltas": (),
        "provenance": (),
        "review_queue": (),
        "warnings": tuple(dict.fromkeys(str(item) for item in warnings)),
    }
    return ReviewWorkspaceReport(
        workspace_id=body["workspace_id"],
        run_id=run_id,
        case_id=case_id,
        version=REVIEW_WORKSPACE_VERSION,
        state=state,
        accepted=accepted,
        run_integrity=body["run_integrity"],
        baseline_run_id=baseline_run_id,
        baseline_integrity=body["baseline_integrity"],
        hypotheses=(),
        edges=(),
        evidence=(),
        alternatives=(),
        deltas=(),
        provenance=(),
        review_queue=(),
        warnings=body["warnings"],
        content_address=_address(body, "review-workspace"),
    )


def build_review_workspace(
    dossier: Dossier,
    *,
    run_id: str | None = None,
    baseline_dossier: Dossier | None = None,
    baseline_run_id: str | None = None,
    run_integrity: Mapping[str, Any] | None = None,
    baseline_integrity: Mapping[str, Any] | None = None,
    config: ReviewWorkspaceConfig | None = None,
) -> ReviewWorkspaceReport:
    """Build a complete review projection from typed dossier snapshots."""

    selected_config = config or ReviewWorkspaceConfig()
    if not isinstance(dossier, Dossier):
        raise ValidationError("review workspace requires a typed dossier")
    current_run_id = _text(run_id or dossier.run_id, "run_id")
    if baseline_dossier is not None:
        if not baseline_run_id:
            baseline_run_id = baseline_dossier.run_id
        if baseline_dossier.case_id != dossier.case_id:
            raise ValidationError("review baseline and current case IDs must match")
        if baseline_run_id == current_run_id:
            raise ValidationError("review baseline and current run IDs must differ")
    if len(dossier.hypotheses) > selected_config.max_hypotheses:
        raise ValidationError("review hypothesis ceiling was exceeded")
    if len(dossier.evidence) > selected_config.max_evidence:
        raise ValidationError("review evidence ceiling was exceeded")
    edge_count = sum(len(item.edges) for item in dossier.hypotheses)
    if edge_count > selected_config.max_edges:
        raise ValidationError("review edge ceiling was exceeded")

    evidence_by_id = {item.evidence_id: item for item in dossier.evidence}
    warnings: list[str] = [
        "review workspace preserves evidence dimensions and does not produce one decision score",
        "review values are descriptive research projections and require human adjudication",
        "evidence payloads and producer metadata are withheld from the public review projection",
    ]
    if len(evidence_by_id) != len(dossier.evidence):
        warnings.append("duplicate evidence identifiers were collapsed for safe review rendering")
    evidence_views = tuple(_evidence_view(item) for item in sorted(evidence_by_id.values(), key=lambda item: item.evidence_id))
    edge_views = tuple(
        _edge_view(hypothesis, edge, evidence_by_id)
        for hypothesis in sorted(dossier.hypotheses, key=lambda item: item.hypothesis_id)
        for edge in sorted(hypothesis.edges, key=lambda item: item.edge_id)
    )
    alternatives: list[ReviewAlternativeView] = []
    hypotheses: list[ReviewHypothesisView] = []
    edges_by_hypothesis: dict[str, list[ReviewEdgeView]] = defaultdict(list)
    for edge in edge_views:
        edges_by_hypothesis[edge.hypothesis_id].append(edge)
    alternatives_by_hypothesis: dict[str, tuple[ReviewAlternativeView, ...]] = {}
    for hypothesis in sorted(dossier.hypotheses, key=lambda item: item.hypothesis_id):
        related_edges = tuple(edges_by_hypothesis[hypothesis.hypothesis_id])
        related_alternatives = _alternative_views(hypothesis, related_edges, evidence_by_id)
        alternatives_by_hypothesis[hypothesis.hypothesis_id] = related_alternatives
        alternatives.extend(related_alternatives)
        claim_ids = _unique(claim_id for edge in related_edges for claim_id in edge.claim_ids)
        source_ids = _unique(
            source_id
            for edge in related_edges
            for source_id in edge.source_ids
        )
        body = {
            "hypothesis_id": hypothesis.hypothesis_id,
            "variant_id": hypothesis.variant_id,
            "element_id": hypothesis.element_id,
            "gene_id": hypothesis.gene_id,
            "state_id": hypothesis.state_id,
            "mechanism": _short_text(hypothesis.mechanism),
            "context_key": hypothesis.context.key,
            "status": hypothesis.status.value,
            "support": round(hypothesis.support, 6),
            "uncertainty": round(hypothesis.uncertainty, 6),
            "edge_ids": tuple(edge.edge_id for edge in related_edges),
            "evidence_ids": claim_ids,
            "alternative_ids": tuple(item.alternative_id for item in related_alternatives),
            "provenance_ids": tuple(f"source:{source_id}" for source_id in source_ids),
            "missing_evidence": _unique(hypothesis.missing_evidence),
            "negative_evidence": _unique(hypothesis.negative_evidence),
        }
        hypotheses.append(ReviewHypothesisView(**body, content_address=_address(body, "review-hypothesis")))
    if len(alternatives) > selected_config.max_alternatives:
        raise ValidationError("review alternative ceiling was exceeded")
    provenance_views = _provenance_views(dossier, evidence_by_id, edge_views)
    if len(provenance_views) > REVIEW_WORKSPACE_MAX_PROVENANCE:
        raise ValidationError("review provenance ceiling was exceeded")
    queue = _build_review_queue(dossier.hypotheses, edge_views, evidence_by_id, selected_config)
    deltas = (
        _build_deltas(
            baseline_dossier,
            dossier,
            baseline_run_id=str(baseline_run_id),
            current_run_id=current_run_id,
        )
        if baseline_dossier is not None and baseline_run_id
        else ()
    )
    if len(deltas) > selected_config.max_deltas:
        raise ValidationError("review delta ceiling was exceeded")
    if not dossier.hypotheses or not dossier.evidence:
        state = ReviewWorkspaceState.ABSTAINED
        warnings.append("review workspace abstained because hypotheses or evidence are absent")
    elif queue or deltas:
        state = ReviewWorkspaceState.REVIEW
    else:
        state = ReviewWorkspaceState.READY_FOR_REVIEW
    body = {
        "workspace_id": f"review:{current_run_id}",
        "run_id": current_run_id,
        "case_id": dossier.case_id,
        "version": REVIEW_WORKSPACE_VERSION,
        "state": state,
        "accepted": True,
        "run_integrity": _public(run_integrity or {}),
        "baseline_run_id": baseline_run_id,
        "baseline_integrity": _public(baseline_integrity) if baseline_integrity else None,
        "hypotheses": tuple(hypotheses),
        "edges": edge_views,
        "evidence": evidence_views,
        "alternatives": tuple(alternatives),
        "deltas": deltas,
        "provenance": provenance_views,
        "review_queue": queue,
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    public_body = _public(body)
    accepted = not _has_forbidden(public_body) and not contains_private_key(public_body)
    if not accepted:
        warnings.append("review workspace public-boundary audit rejected the projection")
        public_body["accepted"] = False
    return ReviewWorkspaceReport(
        workspace_id=body["workspace_id"],
        run_id=current_run_id,
        case_id=dossier.case_id,
        version=REVIEW_WORKSPACE_VERSION,
        state=state,
        accepted=accepted,
        run_integrity=public_body["run_integrity"],
        baseline_run_id=baseline_run_id,
        baseline_integrity=public_body["baseline_integrity"],
        hypotheses=tuple(hypotheses),
        edges=edge_views,
        evidence=evidence_views,
        alternatives=tuple(alternatives),
        deltas=deltas,
        provenance=provenance_views,
        review_queue=queue,
        warnings=tuple(dict.fromkeys(warnings)),
        content_address=_address(public_body, "review-workspace"),
    )


def build_persisted_review_workspace(
    runtime: CaseRuntime,
    run_id: str,
    *,
    baseline_run_id: str | None = None,
    config: ReviewWorkspaceConfig | None = None,
) -> ReviewWorkspaceReport:
    """Build review data only from replay-verified persisted runs."""

    current = inspect_run(runtime, run_id)
    current_integrity = _public(current.summary.integrity.to_dict())
    if not current.accepted:
        return _empty_report(
            run_id=current.summary.run_id,
            case_id=current.summary.case_id,
            run_integrity=current_integrity,
            baseline_run_id=baseline_run_id,
            baseline_integrity=None,
            state=ReviewWorkspaceState.ABSTAINED,
            accepted=False,
            warnings=(
                "run failed replay verification; review details were withheld",
                *current.summary.integrity.warnings,
            ),
        )
    dossier = Dossier.from_dict(current.dossier_record)
    baseline = None
    baseline_integrity = None
    if baseline_run_id is not None:
        baseline_inspection = inspect_run(runtime, baseline_run_id)
        baseline_integrity = _public(baseline_inspection.summary.integrity.to_dict())
        if not baseline_inspection.accepted:
            return _empty_report(
                run_id=current.summary.run_id,
                case_id=current.summary.case_id,
                run_integrity=current_integrity,
                baseline_run_id=baseline_run_id,
                baseline_integrity=baseline_integrity,
                state=ReviewWorkspaceState.ABSTAINED,
                accepted=False,
                warnings=("baseline run failed replay verification; deltas were withheld",),
            )
        if baseline_inspection.summary.case_id != current.summary.case_id:
            raise ValidationError("review baseline and current case IDs must match")
        baseline = Dossier.from_dict(baseline_inspection.dossier_record)
    return build_review_workspace(
        dossier,
        run_id=current.summary.run_id,
        baseline_dossier=baseline,
        baseline_run_id=baseline_run_id,
        run_integrity=current_integrity,
        baseline_integrity=baseline_integrity,
        config=config,
    )


def review_workspace_schema() -> dict[str, Any]:
    """Return the machine-readable public review workspace contract."""

    return {
        "version": REVIEW_WORKSPACE_SCHEMA_VERSION,
        "workspace_version": REVIEW_WORKSPACE_VERSION,
        "states": [item.value for item in ReviewWorkspaceState],
        "collections": [
            "hypotheses",
            "edges",
            "evidence",
            "alternatives",
            "deltas",
            "provenance",
            "review_queue",
        ],
        "delta_dimensions": [
            "presence",
            "support",
            "uncertainty",
            "context_fit",
            "support_level",
            "status",
            "alternatives",
            "score",
            "confidence",
            "state",
        ],
        "public_boundary": [
            "review output is aggregate and payload-free",
            "producer, agent, assistant, model, language, contact, sample, and subject keys are rejected",
            "evidence states remain distinct from review state",
            "deltas are per-item before/after changes and never an aggregate ranking",
            "baseline deltas require replay verification for both runs",
        ],
        "exports": {
            "json": "review-workspace.json",
            "markdown": "review-workspace.md",
            "csv_collections": [
                "hypotheses",
                "edges",
                "evidence",
                "alternatives",
                "deltas",
                "provenance",
                "review_queue",
            ],
            "portable_release": "review-workspace-release-v1",
            "manifest_exact_byte_verification": True,
            "query_contract": "review-workspace-query-v1",
            "triage_plan_contract": "review-workspace-plan-v1",
            "execution_contract": "review-workspace-execution-v1",
        },
        "limits": {
            "max_hypotheses": REVIEW_WORKSPACE_MAX_HYPOTHESES,
            "max_edges": REVIEW_WORKSPACE_MAX_EDGES,
            "max_evidence": REVIEW_WORKSPACE_MAX_EVIDENCE,
            "max_alternatives": REVIEW_WORKSPACE_MAX_ALTERNATIVES,
            "max_deltas": REVIEW_WORKSPACE_MAX_DELTAS,
            "max_provenance": REVIEW_WORKSPACE_MAX_PROVENANCE,
        },
    }


def review_workspace_capabilities() -> dict[str, Any]:
    """Return capability metadata without exposing a dossier or source rows."""

    return {
        "version": REVIEW_WORKSPACE_VERSION,
        "replay_gate": {
            "current_run_required": True,
            "baseline_run_required_for_deltas": True,
            "invalid_runs_withhold_details": True,
        },
        "views": {
            "hypotheses_retain_component_dimensions": True,
            "edges_retain_claim_ids_and_state_counts": True,
            "alternatives_are_explicit_branches": True,
            "provenance_is_source_centric": True,
            "review_queue_has_explainable_priority": True,
            "deltas_are_item_level": True,
        },
        "exports": {
            "json": True,
            "markdown": True,
            "csv": True,
            "portable_release": True,
            "exact_byte_manifest_verification": True,
            "filesystem_writes_are_cli_explicit": True,
        },
        "query": {
            "bounded_pagination": True,
            "faceted_filtering": True,
            "complete_match_facets": True,
            "content_addressed_rows": True,
        },
        "triage_plan": {
            "ordered_actions": True,
            "cross_queue_dependencies": True,
            "lane_summaries": True,
            "structural_checks": True,
            "offline_release_compatible": True,
        },
        "execution": {
            "append_only_event_ledger": True,
            "hash_chained_replay": True,
            "dependency_aware_completion": True,
            "required_check_confirmation": True,
            "exact_byte_manifest_verification": True,
        },
        "privacy": {
            "raw_evidence_payloads_published": False,
            "producer_metadata_published": False,
            "direct_subject_sample_contact_fields_published": False,
        },
        "limits": review_workspace_schema()["limits"],
    }


__all__ = [
    "REVIEW_WORKSPACE_MAX_ALTERNATIVES",
    "REVIEW_WORKSPACE_MAX_DELTAS",
    "REVIEW_WORKSPACE_MAX_EDGES",
    "REVIEW_WORKSPACE_MAX_EVIDENCE",
    "REVIEW_WORKSPACE_MAX_HYPOTHESES",
    "REVIEW_WORKSPACE_MAX_PROVENANCE",
    "REVIEW_WORKSPACE_SCHEMA_VERSION",
    "REVIEW_WORKSPACE_VERSION",
    "ReviewAlternativeView",
    "ReviewDelta",
    "ReviewEdgeView",
    "ReviewEvidenceView",
    "ReviewHypothesisView",
    "ReviewProvenanceView",
    "ReviewQueueItem",
    "ReviewWorkspaceConfig",
    "ReviewWorkspaceReport",
    "ReviewWorkspaceState",
    "build_persisted_review_workspace",
    "build_review_workspace",
    "review_workspace_capabilities",
    "review_workspace_schema",
]
