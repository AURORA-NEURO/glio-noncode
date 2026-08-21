"""Scientific-beta evidence adjudication, lineage, uncertainty, and review.

The evidence-lifecycle beta layer adds operational views over the immutable
graph contracts. It does not rewrite claims or promote a research dossier. The
four surfaces retain tier ambiguity, source and parent lineage, uncertainty
drivers, and reviewer routing requirements as separate inspectable records.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .evidence_lifecycle import (
    ContradictionDisagreementTracker,
    DisagreementState,
    EvidenceGraphSnapshot,
    LifecycleState,
)
from .serialization import content_hash, jsonable, require_non_empty


class LifecycleBetaState(StrEnum):
    """State for an evidence-lifecycle beta view."""

    SUPPORTED = "supported"
    REVIEW_REQUIRED = "review_required"
    PARTIAL = "partial"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class EvidenceTier(StrEnum):
    """Declared evidence strength class; ordering is explicit and configurable."""

    DIRECT_PERTURBATION = "direct_perturbation"
    ORTHOGONAL_MEASUREMENT = "orthogonal_measurement"
    CONTEXT_MATCHED_OBSERVATION = "context_matched_observation"
    COMPUTATIONAL_PROXY = "computational_proxy"
    UNCLASSIFIED = "unclassified"


class TierDirection(StrEnum):
    SUPPORTS = "supports"
    AGAINST = "against"
    UNKNOWN = "unknown"


class UncertaintyDimension(StrEnum):
    MEASUREMENT = "measurement"
    CONTEXT = "context"
    PROVENANCE = "provenance"
    TRANSPORT = "transport"
    CALIBRATION = "calibration"
    DEPENDENCE = "dependence"
    REVIEW = "review"


class ReviewerRole(StrEnum):
    DOMAIN_EXPERT = "domain_expert"
    DATA_PROVENANCE = "data_provenance"
    STATISTICAL_REVIEW = "statistical_review"
    MOLECULAR_ASSAY = "molecular_assay"
    COMPUTATIONAL_METHODS = "computational_methods"
    CONTEXT_TRANSLATION = "context_translation"


@dataclass(frozen=True, slots=True)
class LifecycleBetaIssue:
    """A row-level or graph-level issue retained by a beta view."""

    code: str
    message: str
    raw_hash: str
    claim_id: str | None = None
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "lifecycle beta issue code")
        require_non_empty(self.message, "lifecycle beta issue message")
        require_non_empty(self.raw_hash, "lifecycle beta issue raw_hash")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceTierObservation:
    """One declared tier and directional assessment for a versioned claim."""

    observation_id: str
    claim_id: str
    edge_id: str
    context_key: str
    tier: EvidenceTier
    direction: TierDirection
    support: float | None
    confidence: float
    source_id: str
    source_version: str
    raw_hash: str
    rationale: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "claim_id",
            "edge_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "rationale",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.support is not None and not 0 <= self.support <= 1:
            raise ValidationError("tier support must be between zero and one")
        if not 0 <= self.confidence <= 1:
            raise ValidationError("tier confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceTierDecision:
    """Adjudicated tier view for one claim without deleting alternatives."""

    claim_id: str
    edge_id: str
    state: LifecycleBetaState
    highest_tier: EvidenceTier
    observed_tiers: tuple[EvidenceTier, ...]
    directions: tuple[TierDirection, ...]
    supporting_observation_ids: tuple[str, ...]
    against_observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceTierAdjudication:
    """Complete tier adjudication for one exact-context evidence bundle."""

    context_key: str
    state: LifecycleBetaState
    decisions: tuple[EvidenceTierDecision, ...]
    unresolved_claim_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceTierAdjudicator:
    """Adjudicate declared evidence tiers while preserving directional conflict."""

    _RANK = {
        EvidenceTier.UNCLASSIFIED: 0,
        EvidenceTier.COMPUTATIONAL_PROXY: 1,
        EvidenceTier.CONTEXT_MATCHED_OBSERVATION: 2,
        EvidenceTier.ORTHOGONAL_MEASUREMENT: 3,
        EvidenceTier.DIRECT_PERTURBATION: 4,
    }

    def adjudicate(
        self,
        observations: Iterable[EvidenceTierObservation | Mapping[str, Any]],
        *,
        context_key: str,
    ) -> EvidenceTierAdjudication:
        require_non_empty(context_key, "tier adjudication context_key")
        values = tuple(_coerce_tier(item) for item in observations)
        exact = tuple(item for item in values if item.context_key == context_key)
        if not exact:
            state = LifecycleBetaState.OUT_OF_DOMAIN if values else LifecycleBetaState.ABSTAINED
            return self._result(
                context_key,
                state,
                (),
                (),
                "tier observations do not match the requested exact context",
            )
        by_claim: dict[str, list[EvidenceTierObservation]] = defaultdict(list)
        for item in exact:
            by_claim[item.claim_id].append(item)
        decisions: list[EvidenceTierDecision] = []
        unresolved: list[str] = []
        for claim_id, rows in sorted(by_claim.items()):
            directions = tuple(
                sorted({item.direction for item in rows}, key=lambda item: item.value)
            )
            supports = tuple(
                item.observation_id for item in rows if item.direction == TierDirection.SUPPORTS
            )
            against = tuple(
                item.observation_id for item in rows if item.direction == TierDirection.AGAINST
            )
            highest = max((item.tier for item in rows), key=lambda item: self._RANK[item])
            if supports and against:
                state = LifecycleBetaState.CONTRADICTORY
                rationale = "supporting and against-direction tier observations coexist"
            elif highest == EvidenceTier.UNCLASSIFIED:
                state = LifecycleBetaState.PARTIAL
                rationale = "claim has observations but no declared evidence tier"
            elif not supports:
                state = LifecycleBetaState.REVIEW_REQUIRED
                rationale = "claim has no supporting tier observation"
            else:
                state = LifecycleBetaState.SUPPORTED
                rationale = "highest declared tier retains supporting observation lineage"
            if state != LifecycleBetaState.SUPPORTED:
                unresolved.append(claim_id)
            decisions.append(
                EvidenceTierDecision(
                    claim_id=claim_id,
                    edge_id=rows[0].edge_id,
                    state=state,
                    highest_tier=highest,
                    observed_tiers=tuple(
                        sorted({item.tier for item in rows}, key=lambda item: self._RANK[item])
                    ),
                    directions=directions,
                    supporting_observation_ids=supports,
                    against_observation_ids=against,
                    source_ids=tuple(sorted({item.source_id for item in rows})),
                    rationale=rationale,
                )
            )
        if any(item.state == LifecycleBetaState.CONTRADICTORY for item in decisions):
            state = LifecycleBetaState.CONTRADICTORY
            reason = "at least one claim has contradictory tier directions"
        elif unresolved:
            state = LifecycleBetaState.REVIEW_REQUIRED
            reason = "tier adjudication contains unresolved or non-supporting claims"
        else:
            state = LifecycleBetaState.SUPPORTED
            reason = "all exact-context claims have supporting declared tiers"
        return self._result(
            context_key,
            state,
            tuple(decisions),
            tuple(unresolved),
            reason,
            source_ids=tuple(sorted({item.source_id for item in exact})),
        )

    @staticmethod
    def _result(
        context_key: str,
        state: LifecycleBetaState,
        decisions: tuple[EvidenceTierDecision, ...],
        unresolved: tuple[str, ...],
        reason: str,
        *,
        source_ids: tuple[str, ...] = (),
    ) -> EvidenceTierAdjudication:
        body = {
            "context_key": context_key,
            "state": state,
            "decisions": decisions,
            "unresolved": unresolved,
        }
        return EvidenceTierAdjudication(
            context_key=context_key,
            state=state,
            decisions=decisions,
            unresolved_claim_ids=unresolved,
            source_ids=source_ids,
            warnings=(
                "Evidence tiers are declared adjudication labels, not universal effect-size "
                "or clinical-validity rankings.",
                "A higher tier does not erase lower-tier alternatives or directional disagreement.",
                reason,
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class LineageNode:
    """One claim, source, or citation node in a provenance view."""

    node_id: str
    node_kind: str
    label: str
    active: bool
    context_key: str | None
    source_version: str | None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LineageEdge:
    """One typed provenance or versioning relation."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    active: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProvenanceLineageView:
    """Filtered or complete graph lineage view."""

    graph_id: str
    graph_version: int
    context_key: str
    state: LifecycleBetaState
    nodes: tuple[LineageNode, ...]
    edges: tuple[LineageEdge, ...]
    selected_claim_ids: tuple[str, ...]
    omitted_claim_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ProvenanceLineageViewer:
    """Expose claim parents, supersession, sources, and citations as a view."""

    def view(
        self,
        graph: EvidenceGraphSnapshot,
        *,
        claim_id: str | None = None,
        include_superseded: bool = True,
    ) -> ProvenanceLineageView:
        claims = graph.claims
        if claim_id is not None:
            require_non_empty(claim_id, "lineage claim_id")
            selected = tuple(claim for claim in claims if claim.claim_id == claim_id)
            if not selected:
                return self._empty(graph, claim_id)
            reachable = {claim_id}
            changed = True
            while changed:
                changed = False
                for claim in claims:
                    if claim.claim_id in reachable:
                        for parent in claim.parent_claim_ids:
                            if parent not in reachable:
                                reachable.add(parent)
                                changed = True
                        if claim.supersedes and claim.supersedes not in reachable:
                            reachable.add(claim.supersedes)
                            changed = True
            claims = tuple(claim for claim in claims if claim.claim_id in reachable)
        if not include_superseded:
            claims = tuple(
                claim for claim in claims if claim.claim_id in set(graph.active_claim_ids)
            )
        selected_claim_ids = tuple(claim.claim_id for claim in claims)
        omitted_claim_ids = tuple(
            sorted({claim.claim_id for claim in graph.claims} - set(selected_claim_ids))
        )
        active_ids = set(graph.active_claim_ids)
        nodes: dict[str, LineageNode] = {}
        edges: list[LineageEdge] = []
        included_ids = set(selected_claim_ids)
        for claim in claims:
            nodes[claim.claim_id] = LineageNode(
                node_id=claim.claim_id,
                node_kind="claim",
                label=claim.summary,
                active=claim.claim_id in active_ids,
                context_key=claim.context_key,
                source_version=None,
                attributes={"edge_id": claim.edge_id, "claim_type": claim.claim_type},
            )
            for parent in claim.parent_claim_ids:
                if parent in included_ids:
                    edges.append(
                        LineageEdge(
                            edge_id=content_hash(
                                {"from": parent, "to": claim.claim_id, "relation": "parent"},
                                prefix="lineage",
                            ),
                            source_node_id=parent,
                            target_node_id=claim.claim_id,
                            relation="parent",
                            active=claim.claim_id in active_ids,
                        )
                    )
            if claim.supersedes and claim.supersedes in included_ids:
                edges.append(
                    LineageEdge(
                        edge_id=content_hash(
                            {
                                "from": claim.claim_id,
                                "to": claim.supersedes,
                                "relation": "supersedes",
                            },
                            prefix="lineage",
                        ),
                        source_node_id=claim.claim_id,
                        target_node_id=claim.supersedes,
                        relation="supersedes",
                        active=claim.claim_id in active_ids,
                    )
                )
            for source_id in claim.source_ids:
                source_node_id = f"source:{source_id}"
                nodes.setdefault(
                    source_node_id,
                    LineageNode(
                        node_id=source_node_id,
                        node_kind="source",
                        label=source_id,
                        active=True,
                        context_key=claim.context_key,
                        source_version=claim.source_versions.get(source_id),
                    ),
                )
                edges.append(
                    LineageEdge(
                        edge_id=content_hash(
                            {"from": claim.claim_id, "to": source_node_id, "relation": "source"},
                            prefix="lineage",
                        ),
                        source_node_id=claim.claim_id,
                        target_node_id=source_node_id,
                        relation="source",
                        active=claim.claim_id in active_ids,
                    )
                )
        citation_by_source = {citation.source_id: citation for citation in graph.citations}
        for source_id, citation in sorted(citation_by_source.items()):
            source_node_id = f"source:{source_id}"
            citation_node_id = f"citation:{citation.citation_id}"
            if source_node_id not in nodes:
                continue
            nodes[citation_node_id] = LineageNode(
                node_id=citation_node_id,
                node_kind="citation",
                label=citation.title,
                active=True,
                context_key=citation.context_key,
                source_version=citation.version,
                attributes={"uri": citation.source_uri, "raw_hash": citation.raw_hash},
            )
            edges.append(
                LineageEdge(
                    edge_id=content_hash(
                        {"from": source_node_id, "to": citation_node_id, "relation": "citation"},
                        prefix="lineage",
                    ),
                    source_node_id=source_node_id,
                    target_node_id=citation_node_id,
                    relation="citation",
                    active=True,
                )
            )
        state = (
            LifecycleBetaState.SUPPORTED
            if graph.state == LifecycleState.SUPPORTED
            else LifecycleBetaState.REVIEW_REQUIRED
        )
        if graph.state == LifecycleState.OUT_OF_DOMAIN:
            state = LifecycleBetaState.OUT_OF_DOMAIN
        return ProvenanceLineageView(
            graph_id=graph.graph_id,
            graph_version=graph.graph_version,
            context_key=graph.context_key,
            state=state,
            nodes=tuple(nodes[key] for key in sorted(nodes)),
            edges=tuple(sorted(edges, key=lambda item: item.edge_id)),
            selected_claim_ids=selected_claim_ids,
            omitted_claim_ids=omitted_claim_ids,
            warnings=(
                "Lineage view is an inspectable projection; it does not validate claim truth.",
                "Superseded history remains available when include_superseded is true.",
            )
            + graph.warnings,
            content_address=content_hash(
                {
                    "graph_id": graph.graph_id,
                    "graph_version": graph.graph_version,
                    "selected_claim_ids": selected_claim_ids,
                    "nodes": tuple(nodes.values()),
                    "edges": tuple(edges),
                }
            ),
        )

    @staticmethod
    def _empty(graph: EvidenceGraphSnapshot, claim_id: str) -> ProvenanceLineageView:
        return ProvenanceLineageView(
            graph_id=graph.graph_id,
            graph_version=graph.graph_version,
            context_key=graph.context_key,
            state=LifecycleBetaState.ABSTAINED,
            nodes=(),
            edges=(),
            selected_claim_ids=(),
            omitted_claim_ids=tuple(sorted(claim.claim_id for claim in graph.claims)),
            warnings=(f"claim_id {claim_id} was not found in the graph history",),
            content_address=content_hash({"graph": graph.content_address, "claim_id": claim_id}),
        )


@dataclass(frozen=True, slots=True)
class UncertaintyObservation:
    """One uncertainty driver for a claim or edge."""

    observation_id: str
    claim_id: str
    edge_id: str
    context_key: str
    dimension: UncertaintyDimension
    value: float
    source_id: str
    source_version: str
    raw_hash: str
    rationale: str

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "claim_id",
            "edge_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "rationale",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.value <= 1:
            raise ValidationError("uncertainty value must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UncertaintyClaimSummary:
    """Conservative uncertainty summary for one claim."""

    claim_id: str
    edge_id: str
    uncertainty: float
    dimensions: Mapping[str, float]
    top_dimension: str
    observation_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class UncertaintyLedger:
    """Explicit uncertainty drivers without a calibrated probability."""

    context_key: str
    state: LifecycleBetaState
    entries: tuple[UncertaintyObservation, ...]
    claims: tuple[UncertaintyClaimSummary, ...]
    top_drivers: tuple[str, ...]
    aggregation_method: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class UncertaintyLedgerBuilder:
    """Build a conservative, dimension-labeled uncertainty ledger."""

    def build(
        self,
        entries: Iterable[UncertaintyObservation | Mapping[str, Any]],
        *,
        context_key: str,
    ) -> UncertaintyLedger:
        require_non_empty(context_key, "uncertainty ledger context_key")
        values = tuple(_coerce_uncertainty(item) for item in entries)
        exact = tuple(item for item in values if item.context_key == context_key)
        if not exact:
            state = LifecycleBetaState.OUT_OF_DOMAIN if values else LifecycleBetaState.ABSTAINED
            return self._result(
                context_key, state, (), (), (), "no uncertainty entries match the requested context"
            )
        by_claim: dict[str, list[UncertaintyObservation]] = defaultdict(list)
        for entry in exact:
            by_claim[entry.claim_id].append(entry)
        summaries: list[UncertaintyClaimSummary] = []
        for claim_id, rows in sorted(by_claim.items()):
            dimensions: dict[str, float] = {}
            for row in rows:
                dimensions[row.dimension.value] = max(
                    dimensions.get(row.dimension.value, 0.0), row.value
                )
            top_dimension = max(dimensions, key=lambda key: (dimensions[key], key))
            summaries.append(
                UncertaintyClaimSummary(
                    claim_id=claim_id,
                    edge_id=rows[0].edge_id,
                    uncertainty=round(max(dimensions.values()), 9),
                    dimensions=dict(sorted(dimensions.items())),
                    top_dimension=top_dimension,
                    observation_ids=tuple(item.observation_id for item in rows),
                )
            )
        top_drivers = tuple(
            f"{summary.claim_id}:{summary.top_dimension}"
            for summary in sorted(summaries, key=lambda item: (-item.uncertainty, item.claim_id))
        )
        state = LifecycleBetaState.SUPPORTED if summaries else LifecycleBetaState.ABSTAINED
        return self._result(
            context_key,
            state,
            exact,
            tuple(summaries),
            top_drivers,
            "uncertainty dimensions are retained with conservative per-claim maxima",
        )

    @staticmethod
    def _result(
        context_key: str,
        state: LifecycleBetaState,
        entries: tuple[UncertaintyObservation, ...],
        claims: tuple[UncertaintyClaimSummary, ...],
        top_drivers: tuple[str, ...],
        reason: str,
    ) -> UncertaintyLedger:
        body = {
            "context_key": context_key,
            "state": state,
            "entries": entries,
            "claims": claims,
            "top_drivers": top_drivers,
        }
        return UncertaintyLedger(
            context_key=context_key,
            state=state,
            entries=entries,
            claims=claims,
            top_drivers=top_drivers,
            aggregation_method="maximum supplied uncertainty by claim and dimension",
            warnings=(
                "The ledger is not a calibrated probability or confidence interval.",
                "Missing dimensions, dependence, source quality, transport, and review "
                "status remain explicit limitations.",
                reason,
            ),
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class ReviewerAssignment:
    """One claim routed to explicit review roles."""

    assignment_id: str
    claim_id: str
    edge_id: str
    state: LifecycleBetaState
    roles: tuple[ReviewerRole, ...]
    priority: float
    uncertainty: float | None
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewerRoutingResult:
    """Review queue with claim assignment lineage and unassigned claims."""

    graph_id: str
    graph_version: int
    context_key: str
    state: LifecycleBetaState
    assignments: tuple[ReviewerAssignment, ...]
    unassigned_claim_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReviewerAssignmentRouter:
    """Route active claims to human-review roles from explicit graph signals."""

    def route(
        self,
        graph: EvidenceGraphSnapshot,
        *,
        uncertainty: UncertaintyLedger | None = None,
        tier_adjudication: EvidenceTierAdjudication | None = None,
        required_roles: Iterable[ReviewerRole | str] = (),
    ) -> ReviewerRoutingResult:
        roles = tuple(dict.fromkeys(ReviewerRole(str(role)) for role in required_roles))
        uncertainty_by_claim = {
            item.claim_id: item.uncertainty for item in (uncertainty.claims if uncertainty else ())
        }
        tier_by_claim = {
            item.claim_id: item
            for item in (tier_adjudication.decisions if tier_adjudication else ())
        }
        disagreement = ContradictionDisagreementTracker().track(graph)
        disagreement_by_edge = {item.edge_id: item for item in disagreement.records}
        assignments: list[ReviewerAssignment] = []
        active_claims = graph.active_claims()
        for claim in active_claims:
            claim_roles = list(roles) or [ReviewerRole.DATA_PROVENANCE, ReviewerRole.DOMAIN_EXPERT]
            reasons = ["active claim requires reviewable evidence lineage"]
            blockers: list[str] = []
            disagreement_record = disagreement_by_edge.get(claim.edge_id)
            if disagreement_record and disagreement_record.state == DisagreementState.CONTRADICTORY:
                claim_roles.extend((ReviewerRole.STATISTICAL_REVIEW, ReviewerRole.DOMAIN_EXPERT))
                reasons.append("edge has contradictory active evidence")
            if claim.claim_type in {"sequence", "chromatin", "functional", "perturbation"}:
                claim_roles.append(ReviewerRole.MOLECULAR_ASSAY)
                reasons.append("claim type requires assay-aware review")
            if claim.context_key != graph.context_key:
                claim_roles.append(ReviewerRole.CONTEXT_TRANSLATION)
                blockers.append("claim_context_mismatch")
            tier = tier_by_claim.get(claim.claim_id)
            if tier and tier.state != LifecycleBetaState.SUPPORTED:
                reasons.append("tier adjudication is unresolved")
                blockers.append("tier_not_resolved")
            claim_roles = tuple(dict.fromkeys(claim_roles))
            uncertainty_value = uncertainty_by_claim.get(claim.claim_id)
            priority = max(
                0.50,
                min(
                    1.0,
                    (uncertainty_value if uncertainty_value is not None else 0.50)
                    + (0.25 if disagreement_record and disagreement_record.unresolved else 0.0)
                    + (0.15 if blockers else 0.0),
                ),
            )
            state = LifecycleBetaState.REVIEW_REQUIRED
            if claim.claim_id in graph.context_mismatch_claim_ids:
                state = LifecycleBetaState.OUT_OF_DOMAIN
            elif (
                disagreement_record and disagreement_record.state == DisagreementState.CONTRADICTORY
            ):
                state = LifecycleBetaState.CONTRADICTORY
            assignments.append(
                ReviewerAssignment(
                    assignment_id=content_hash(
                        {
                            "graph": graph.content_address,
                            "claim": claim.claim_id,
                            "roles": claim_roles,
                        },
                        prefix="review",
                    ),
                    claim_id=claim.claim_id,
                    edge_id=claim.edge_id,
                    state=state,
                    roles=claim_roles,
                    priority=round(priority, 9),
                    uncertainty=uncertainty_value,
                    reasons=tuple(dict.fromkeys(reasons)),
                    blockers=tuple(dict.fromkeys(blockers)),
                )
            )
        assignments.sort(key=lambda item: (-item.priority, item.claim_id))
        state = LifecycleBetaState.SUPPORTED if assignments else LifecycleBetaState.ABSTAINED
        if any(item.state == LifecycleBetaState.CONTRADICTORY for item in assignments):
            state = LifecycleBetaState.CONTRADICTORY
        elif any(item.state == LifecycleBetaState.OUT_OF_DOMAIN for item in assignments):
            state = LifecycleBetaState.OUT_OF_DOMAIN
        return ReviewerRoutingResult(
            graph_id=graph.graph_id,
            graph_version=graph.graph_version,
            context_key=graph.context_key,
            state=state,
            assignments=tuple(assignments),
            unassigned_claim_ids=(),
            warnings=(
                "Assignments are review routing suggestions and do not authorize experiments "
                "or clinical action.",
                "Role coverage and priority require project-specific staffing, conflict "
                "checks, and human acceptance.",
            ),
            content_address=content_hash(
                {
                    "graph": graph.content_address,
                    "assignments": assignments,
                    "state": state,
                }
            ),
        )


def _coerce_tier(value: EvidenceTierObservation | Mapping[str, Any]) -> EvidenceTierObservation:
    if isinstance(value, EvidenceTierObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("tier observation must be a mapping")
    return EvidenceTierObservation(
        observation_id=str(value.get("observation_id", value.get("id", "tier-input"))),
        claim_id=str(value.get("claim_id", value.get("claim", ""))),
        edge_id=str(value.get("edge_id", value.get("edge", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        tier=EvidenceTier(str(value.get("tier", EvidenceTier.UNCLASSIFIED.value))),
        direction=TierDirection(str(value.get("direction", TierDirection.SUPPORTS.value))),
        support=None if value.get("support") is None else float(value["support"]),
        confidence=float(value.get("confidence", 1.0)),
        source_id=str(value.get("source_id", "tier-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        rationale=str(value.get("rationale", "declared tier observation")),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_uncertainty(
    value: UncertaintyObservation | Mapping[str, Any],
) -> UncertaintyObservation:
    if isinstance(value, UncertaintyObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("uncertainty observation must be a mapping")
    return UncertaintyObservation(
        observation_id=str(value.get("observation_id", value.get("id", "uncertainty-input"))),
        claim_id=str(value.get("claim_id", value.get("claim", ""))),
        edge_id=str(value.get("edge_id", value.get("edge", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        dimension=UncertaintyDimension(
            str(value.get("dimension", UncertaintyDimension.REVIEW.value))
        ),
        value=float(value.get("value", value.get("uncertainty", 1.0))),
        source_id=str(value.get("source_id", "uncertainty-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        rationale=str(value.get("rationale", "declared uncertainty observation")),
    )


__all__ = [
    "DisagreementState",
    "EvidenceTier",
    "EvidenceTierAdjudication",
    "EvidenceTierAdjudicator",
    "EvidenceTierDecision",
    "EvidenceTierObservation",
    "LifecycleBetaIssue",
    "LifecycleBetaState",
    "LineageEdge",
    "LineageNode",
    "ProvenanceLineageView",
    "ProvenanceLineageViewer",
    "ReviewerAssignment",
    "ReviewerAssignmentRouter",
    "ReviewerRole",
    "TierDirection",
    "UncertaintyClaimSummary",
    "UncertaintyDimension",
    "UncertaintyLedger",
    "UncertaintyLedgerBuilder",
    "UncertaintyObservation",
]
