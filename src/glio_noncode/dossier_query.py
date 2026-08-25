"""Typed query and lineage projections for persisted research dossiers.

The stored dossier remains the canonical immutable object. This module provides
bounded, content-addressed projections for clients that need to review one
evidence plane at a time without downloading or reimplementing the whole
dossier graph.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .models import AssayType, Dossier, EvidenceState, EvidenceTier
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .runtime import CaseRuntime
from .serialization import content_hash

DOSSIER_QUERY_VERSION = "dossier-query-v1"
DOSSIER_QUERY_DEFAULT_LIMIT = 25
DOSSIER_QUERY_MAX_LIMIT = 100
DOSSIER_QUERY_RESOURCES = ("hypotheses", "evidence", "experiments")


def _bounded_page(offset: int, limit: int) -> None:
    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit < 1 or limit > DOSSIER_QUERY_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {DOSSIER_QUERY_MAX_LIMIT}")


def _row(value: Any, resource: str) -> dict[str, Any]:
    body = value.to_dict()
    return body | {"content_address": content_hash(body, prefix=f"dossier-{resource}-row")}


@dataclass(frozen=True, slots=True)
class DossierQueryPage:
    """Bounded query result for one dossier resource."""

    run_id: str
    case_id: str
    resource: str
    rows: tuple[dict[str, Any], ...]
    total_count: int
    offset: int
    limit: int
    has_more: bool
    accepted: bool
    filters: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_version": DOSSIER_QUERY_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "resource": self.resource,
            "rows": list(self.rows),
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "accepted": self.accepted,
            "filters": self.filters,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class DossierQuerySummary:
    """Aggregated evidence and review counters for one dossier."""

    run_id: str
    case_id: str
    dossier_id: str
    status: str
    research_use_only: bool
    is_releasable: bool
    hypothesis_count: int
    edge_count: int
    evidence_count: int
    experiment_count: int
    warning_count: int
    evidence_state_counts: dict[str, int]
    evidence_channel_counts: dict[str, int]
    evidence_tier_counts: dict[str, int]
    evidence_source_counts: dict[str, int]
    review: dict[str, Any] | None
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_version": DOSSIER_QUERY_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_id": self.dossier_id,
            "status": self.status,
            "research_use_only": self.research_use_only,
            "is_releasable": self.is_releasable,
            "hypothesis_count": self.hypothesis_count,
            "edge_count": self.edge_count,
            "evidence_count": self.evidence_count,
            "experiment_count": self.experiment_count,
            "warning_count": self.warning_count,
            "evidence_state_counts": self.evidence_state_counts,
            "evidence_channel_counts": self.evidence_channel_counts,
            "evidence_tier_counts": self.evidence_tier_counts,
            "evidence_source_counts": self.evidence_source_counts,
            "review": self.review,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class DossierLineageProjection:
    """Edge-to-claim graph projection for one dossier or hypothesis subset."""

    run_id: str
    case_id: str
    hypothesis_ids: tuple[str, ...]
    nodes: tuple[dict[str, str], ...]
    edges: tuple[dict[str, Any], ...]
    claims: tuple[dict[str, Any], ...]
    missing_claim_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        return len(self.edges)

    @property
    def claim_count(self) -> int:
        return len(self.claims)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query_version": DOSSIER_QUERY_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "hypothesis_ids": list(self.hypothesis_ids),
            "nodes": list(self.nodes),
            "edges": list(self.edges),
            "claims": list(self.claims),
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "claim_count": len(self.claims),
            "missing_claim_ids": list(self.missing_claim_ids),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def summarize_dossier(dossier: Dossier) -> DossierQuerySummary:
    """Build stable aggregate counts without flattening uncertainty states."""

    review = dossier.review.to_dict() if dossier.review is not None else None
    body = {
        "run_id": dossier.run_id,
        "case_id": dossier.case_id,
        "dossier_id": dossier.dossier_id,
        "status": dossier.status.value,
        "research_use_only": dossier.research_use_only,
        "is_releasable": dossier.is_releasable,
        "hypothesis_count": len(dossier.hypotheses),
        "edge_count": sum(len(item.edges) for item in dossier.hypotheses),
        "evidence_count": len(dossier.evidence),
        "experiment_count": len(dossier.experiments),
        "warning_count": len(dossier.warnings),
        "evidence_state_counts": dict(sorted(Counter(item.state.value for item in dossier.evidence).items())),
        "evidence_channel_counts": dict(sorted(Counter(item.channel for item in dossier.evidence).items())),
        "evidence_tier_counts": dict(sorted(Counter(item.tier.value for item in dossier.evidence).items())),
        "evidence_source_counts": dict(sorted(Counter(item.source_id for item in dossier.evidence).items())),
        "review": review,
    }
    accepted = not contains_private_key(body)
    return DossierQuerySummary(
        **body,
        accepted=accepted,
        content_address=content_hash(body | {"accepted": accepted}, prefix="dossier-summary"),
    )


def query_dossier(
    dossier: Dossier,
    resource: str,
    *,
    offset: int = 0,
    limit: int = DOSSIER_QUERY_DEFAULT_LIMIT,
    text: str | None = None,
    hypothesis_id: str | None = None,
    status: str | None = None,
    min_support: float | None = None,
    max_uncertainty: float | None = None,
    evidence_id: str | None = None,
    edge_id: str | None = None,
    state: str | None = None,
    tier: str | None = None,
    channel: str | None = None,
    source_id: str | None = None,
    option_id: str | None = None,
    assay: str | None = None,
) -> DossierQueryPage:
    """Filter one dossier plane with explicit bounded query semantics."""

    if resource not in DOSSIER_QUERY_RESOURCES:
        raise ValueError(f"resource must be one of: {', '.join(DOSSIER_QUERY_RESOURCES)}")
    _bounded_page(offset, limit)
    if min_support is not None and not 0.0 <= min_support <= 1.0:
        raise ValueError("min_support must be between 0 and 1")
    if max_uncertainty is not None and not 0.0 <= max_uncertainty <= 1.0:
        raise ValueError("max_uncertainty must be between 0 and 1")
    if state is not None:
        EvidenceState(state)
    if tier is not None:
        EvidenceTier(tier)
    if assay is not None:
        AssayType(assay)
    normalized = text.strip().lower() if text else None

    if resource == "hypotheses":
        candidates = [
            item
            for item in dossier.hypotheses
            if (hypothesis_id is None or item.hypothesis_id == hypothesis_id)
            and (status is None or item.status.value == status)
            and (min_support is None or item.support >= min_support)
            and (max_uncertainty is None or item.uncertainty <= max_uncertainty)
            and (
                normalized is None
                or normalized
                in f"{item.hypothesis_id} {item.variant_id} {item.element_id} {item.gene_id} {item.state_id} {item.mechanism}".lower()
            )
        ]
        rows = [_row(item, resource) for item in candidates]
    elif resource == "evidence":
        candidates = [
            item
            for item in dossier.evidence
            if (evidence_id is None or item.evidence_id == evidence_id)
            and (edge_id is None or item.edge_id == edge_id)
            and (state is None or item.state.value == state)
            and (tier is None or item.tier.value == tier)
            and (channel is None or item.channel == channel)
            and (source_id is None or item.source_id == source_id)
            and (
                normalized is None
                or normalized
                in f"{item.evidence_id} {item.edge_id} {item.source_id} {item.channel} {item.summary}".lower()
            )
        ]
        rows = [_row(item, resource) for item in candidates]
    else:
        candidates = [
            item
            for item in dossier.experiments
            if (option_id is None or item.option_id == option_id)
            and (assay is None or item.assay.value == assay)
            and (
                normalized is None
                or normalized
                in f"{item.option_id} {item.assay.value} {item.cost_class} {' '.join(item.readouts)}".lower()
            )
        ]
        rows = [_row(item, resource) for item in candidates]

    selected = tuple(rows[offset : offset + limit])
    filters = {
        key: value
        for key, value in {
            "text": text,
            "hypothesis_id": hypothesis_id,
            "status": status,
            "min_support": min_support,
            "max_uncertainty": max_uncertainty,
            "evidence_id": evidence_id,
            "edge_id": edge_id,
            "state": state,
            "tier": tier,
            "channel": channel,
            "source_id": source_id,
            "option_id": option_id,
            "assay": assay,
        }.items()
        if value is not None
    }
    body = {
        "run_id": dossier.run_id,
        "case_id": dossier.case_id,
        "resource": resource,
        "rows": selected,
        "total_count": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(selected) < len(rows),
        "filters": filters,
    }
    accepted = not contains_private_key(body)
    return DossierQueryPage(
        run_id=dossier.run_id,
        case_id=dossier.case_id,
        resource=resource,
        rows=selected,
        total_count=len(rows),
        offset=offset,
        limit=limit,
        has_more=body["has_more"],
        accepted=accepted,
        filters=filters,
        content_address=content_hash(body | {"accepted": accepted}, prefix="dossier-query"),
    )


def build_dossier_lineage(dossier: Dossier, *, hypothesis_id: str | None = None) -> DossierLineageProjection:
    """Join hypothesis edges to their referenced evidence claims."""

    hypotheses = tuple(
        item for item in dossier.hypotheses if hypothesis_id is None or item.hypothesis_id == hypothesis_id
    )
    claim_map = {item.evidence_id: item for item in dossier.evidence}
    nodes: dict[str, dict[str, str]] = {}
    edges: list[dict[str, Any]] = []
    claims: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    seen_edges: set[str] = set()

    for hypothesis in hypotheses:
        for edge in hypothesis.edges:
            if edge.edge_id in seen_edges:
                continue
            seen_edges.add(edge.edge_id)
            nodes.setdefault(edge.source_id, {"node_id": edge.source_id, "kind": "entity"})
            nodes.setdefault(edge.target_id, {"node_id": edge.target_id, "kind": "entity"})
            edge_claims: list[str] = []
            for claim_id in edge.claim_ids:
                claim = claim_map.get(claim_id)
                if claim is None:
                    missing.append(claim_id)
                    continue
                edge_claims.append(claim_id)
                claims.setdefault(claim_id, _row(claim, "evidence"))
            edges.append(
                {
                    "hypothesis_id": hypothesis.hypothesis_id,
                    "edge_id": edge.edge_id,
                    "edge_type": edge.edge_type.value,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "claim_ids": edge_claims,
                    "support": edge.support,
                    "uncertainty": edge.uncertainty,
                    "context_fit": edge.context_fit,
                }
            )
    body = {
        "run_id": dossier.run_id,
        "case_id": dossier.case_id,
        "hypothesis_ids": tuple(item.hypothesis_id for item in hypotheses),
        "nodes": tuple(nodes.values()),
        "edges": tuple(edges),
        "claims": tuple(claims.values()),
        "missing_claim_ids": tuple(sorted(set(missing))),
    }
    accepted = not missing and not contains_private_key(body)
    return DossierLineageProjection(
        **body,
        accepted=accepted,
        content_address=content_hash(body | {"accepted": accepted}, prefix="dossier-lineage"),
    )


def _load_query_dossier(runtime: CaseRuntime, run_id: str) -> Dossier:
    inspection = inspect_run(runtime, run_id)
    if not inspection.accepted:
        raise ValidationError("cannot query a run that fails replay integrity")
    return Dossier.from_dict(inspection.dossier_record)


def query_persisted_dossier(runtime: CaseRuntime, run_id: str, resource: str, **filters: Any) -> DossierQueryPage:
    """Query a verified persisted dossier without exposing unverified projections."""

    return query_dossier(_load_query_dossier(runtime, run_id), resource, **filters)


def summarize_persisted_dossier(runtime: CaseRuntime, run_id: str) -> DossierQuerySummary:
    """Summarize a verified persisted dossier."""

    return summarize_dossier(_load_query_dossier(runtime, run_id))


def lineage_persisted_dossier(
    runtime: CaseRuntime,
    run_id: str,
    *,
    hypothesis_id: str | None = None,
) -> DossierLineageProjection:
    """Build lineage only after the persisted run has passed replay verification."""

    return build_dossier_lineage(_load_query_dossier(runtime, run_id), hypothesis_id=hypothesis_id)


def build_dossier_query_closure(dossier: Dossier) -> dict[str, Any]:
    """Package every public dossier query plane into one offline projection."""

    closure = {
        "query_version": DOSSIER_QUERY_VERSION,
        "accepted": True,
        "summary": summarize_dossier(dossier).to_dict(),
        "hypotheses": query_dossier(dossier, "hypotheses", limit=DOSSIER_QUERY_MAX_LIMIT).to_dict(),
        "evidence": query_dossier(dossier, "evidence", limit=DOSSIER_QUERY_MAX_LIMIT).to_dict(),
        "experiments": query_dossier(dossier, "experiments", limit=DOSSIER_QUERY_MAX_LIMIT).to_dict(),
        "lineage": build_dossier_lineage(dossier).to_dict(),
    }
    closure["accepted"] = all(
        bool(closure[key]["accepted"])
        for key in ("summary", "hypotheses", "evidence", "experiments", "lineage")
    )
    closure["content_address"] = content_hash(closure, prefix="dossier-query-closure")
    return closure


def build_persisted_dossier_query_closure(runtime: CaseRuntime, run_id: str) -> dict[str, Any]:
    """Build a query closure only after persisted replay integrity passes."""

    return build_dossier_query_closure(_load_query_dossier(runtime, run_id))


__all__ = [
    "DOSSIER_QUERY_DEFAULT_LIMIT",
    "DOSSIER_QUERY_MAX_LIMIT",
    "DOSSIER_QUERY_RESOURCES",
    "DOSSIER_QUERY_VERSION",
    "DossierLineageProjection",
    "DossierQueryPage",
    "DossierQuerySummary",
    "build_dossier_lineage",
    "build_dossier_query_closure",
    "build_persisted_dossier_query_closure",
    "lineage_persisted_dossier",
    "query_dossier",
    "query_persisted_dossier",
    "summarize_dossier",
    "summarize_persisted_dossier",
]
