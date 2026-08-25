"""Replay-gated cross-run search over public dossier projections.

Single-run query endpoints are precise, but a research workbench also needs to
discover a hypothesis, evidence claim, validation route, review, or run across
the persisted corpus.  This module scans verified run projections on demand,
uses deterministic token ranking, retains blocked-run evidence, and never
searches or emits raw input objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import GlioError, ValidationError
from .models import AssayType, Dossier, EvidenceState, EvidenceTier
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .runtime import CaseRuntime
from .serialization import content_hash

RUN_SEARCH_VERSION = "run-search-v1"
RUN_SEARCH_DEFAULT_LIMIT = 25
RUN_SEARCH_MAX_LIMIT = 100
RUN_SEARCH_RESOURCES = ("all", "runs", "hypotheses", "evidence", "experiments", "reviews")

_RESOURCE_ORDER = {name: index for index, name in enumerate(RUN_SEARCH_RESOURCES)}
_SEARCH_FORBIDDEN_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "contact_name",
        "email",
        "phone",
        "agent_id",
        "agent_name",
        "assistant_id",
        "assistant_name",
        "generated_by",
        "model_name",
        "author_name",
        "programming_language",
        "language",
    }
)


def _bounded(offset: int, limit: int | None) -> None:
    if offset < 0:
        raise ValidationError("offset must be non-negative")
    if limit is not None and (limit < 1 or limit > RUN_SEARCH_MAX_LIMIT):
        raise ValidationError(f"limit must be between 1 and {RUN_SEARCH_MAX_LIMIT}")


def _tokens(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(dict.fromkeys(item for item in value.lower().split() if item))


def _text_match(fields: dict[str, Any], query: str | None) -> tuple[bool, int, tuple[str, ...]]:
    tokens = _tokens(query)
    if not tokens:
        return True, 0, ()
    normalized = {name: str(value).lower() for name, value in fields.items()}
    matched_fields: set[str] = set()
    score = 0
    for token in tokens:
        token_fields = {name for name, value in normalized.items() if token in value}
        if not token_fields:
            return False, 0, ()
        matched_fields.update(token_fields)
        score += 1 + (1 if any(value == token for value in normalized.values()) else 0)
    return True, score, tuple(sorted(matched_fields))


def _public_projection(value: Any) -> Any:
    """Drop direct identifiers and attribution metadata before matching or emitting."""

    if isinstance(value, dict):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if str(key).lower() not in _SEARCH_FORBIDDEN_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _hit(
    *,
    resource: str,
    run_id: str,
    case_id: str,
    dossier_id: str,
    status: str,
    record_id: str,
    title: str,
    fields: dict[str, Any],
    payload: dict[str, Any],
    query: str | None,
    accepted: bool = True,
) -> RunSearchHit | None:
    public_fields = _public_projection(fields)
    public_payload = _public_projection(payload)
    matched, score, match_fields = _text_match(public_fields, query)
    if not matched:
        return None
    body = {
        "resource": resource,
        "run_id": run_id,
        "case_id": case_id,
        "dossier_id": dossier_id,
        "status": status,
        "record_id": record_id,
        "title": title,
        "score": score,
        "match_fields": match_fields,
        "payload": public_payload,
        "accepted": accepted and not contains_private_key(public_payload),
    }
    return RunSearchHit(**body, content_address=content_hash(body, prefix="run-search-hit"))


@dataclass(frozen=True, slots=True)
class RunSearchHit:
    """One public search hit from a verified persisted run."""

    resource: str
    run_id: str
    case_id: str
    dossier_id: str
    status: str
    record_id: str
    title: str
    score: int
    match_fields: tuple[str, ...]
    payload: dict[str, Any]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_id": self.dossier_id,
            "status": self.status,
            "record_id": self.record_id,
            "title": self.title,
            "score": self.score,
            "match_fields": list(self.match_fields),
            "payload": self.payload,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunSearchPage:
    """Bounded deterministic search page with scan-integrity evidence."""

    query: str | None
    resource: str
    rows: tuple[RunSearchHit, ...]
    total_count: int
    offset: int
    limit: int | None
    has_more: bool
    filters: dict[str, Any]
    scanned_run_count: int
    blocked_run_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_version": RUN_SEARCH_VERSION,
            "query": self.query,
            "resource": self.resource,
            "rows": [row.to_dict() for row in self.rows],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "filters": self.filters,
            "scanned_run_count": self.scanned_run_count,
            "blocked_run_count": self.blocked_run_count,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _common_filter(
    *,
    case_id: str | None,
    status: str | None,
    reviewer: str | None,
    review_state: str | None,
    dossier: Dossier,
) -> bool:
    if case_id is not None and dossier.case_id != case_id:
        return False
    if status is not None and dossier.status.value != status:
        return False
    review = dossier.review.to_dict() if dossier.review is not None else {}
    if reviewer is not None and str(review.get("reviewer", "")) != reviewer:
        return False
    if review_state is not None and str(review.get("state", "")) != review_state:
        return False
    return True


def _resource_hits(
    dossier: Dossier,
    *,
    run_id: str,
    resource: str,
    query: str | None,
    case_id: str | None,
    status: str | None,
    reviewer: str | None,
    review_state: str | None,
    state: str | None,
    tier: str | None,
    channel: str | None,
    min_support: float | None,
    max_uncertainty: float | None,
    assay: str | None,
) -> list[RunSearchHit]:
    run_status = dossier.status.value
    dossier_id = dossier.dossier_id
    if not _common_filter(
        case_id=case_id,
        status=status,
        reviewer=reviewer,
        review_state=review_state,
        dossier=dossier,
    ):
        return []
    resources = RUN_SEARCH_RESOURCES[1:] if resource == "all" else (resource,)
    hits: list[RunSearchHit] = []
    if "runs" in resources:
        run_payload = {
            "run_id": run_id,
            "case_id": dossier.case_id,
            "dossier_id": dossier.dossier_id,
            "status": run_status,
            "research_use_only": dossier.research_use_only,
            "is_releasable": dossier.is_releasable,
            "hypothesis_count": len(dossier.hypotheses),
            "evidence_count": len(dossier.evidence),
            "experiment_count": len(dossier.experiments),
            "warning_count": len(dossier.warnings),
            "warnings": list(dossier.warnings),
            "review": dossier.review.to_dict() if dossier.review else None,
        }
        hit = _hit(
            resource="runs",
            run_id=run_id,
            case_id=dossier.case_id,
            dossier_id=dossier_id,
            status=run_status,
            record_id=run_id,
            title=f"Run {run_id}",
            fields=run_payload,
            payload=run_payload,
            query=query,
        )
        if hit is not None:
            hits.append(hit)
    if "hypotheses" in resources:
        for item in dossier.hypotheses:
            if min_support is not None and item.support < min_support:
                continue
            if max_uncertainty is not None and item.uncertainty > max_uncertainty:
                continue
            if state is not None and item.status.value != state:
                continue
            payload = item.to_dict()
            fields = payload | {
                "run_id": run_id,
                "case_id": dossier.case_id,
                "status": run_status,
            }
            hit = _hit(
                resource="hypotheses",
                run_id=run_id,
                case_id=dossier.case_id,
                dossier_id=dossier_id,
                status=run_status,
                record_id=item.hypothesis_id,
                title=f"Hypothesis {item.hypothesis_id}",
                fields=fields,
                payload=payload,
                query=query,
            )
            if hit is not None:
                hits.append(hit)
    if "evidence" in resources:
        for item in dossier.evidence:
            if state is not None and item.state.value != state:
                continue
            if tier is not None and item.tier.value != tier:
                continue
            if channel is not None and item.channel != channel:
                continue
            payload = item.to_dict()
            fields = payload | {"run_id": run_id, "case_id": dossier.case_id, "status": run_status}
            hit = _hit(
                resource="evidence",
                run_id=run_id,
                case_id=dossier.case_id,
                dossier_id=dossier_id,
                status=run_status,
                record_id=item.evidence_id,
                title=f"Evidence {item.evidence_id}",
                fields=fields,
                payload=payload,
                query=query,
            )
            if hit is not None:
                hits.append(hit)
    if "experiments" in resources:
        for item in dossier.experiments:
            if assay is not None and item.assay.value != assay:
                continue
            payload = item.to_dict()
            fields = payload | {"run_id": run_id, "case_id": dossier.case_id, "status": run_status}
            hit = _hit(
                resource="experiments",
                run_id=run_id,
                case_id=dossier.case_id,
                dossier_id=dossier_id,
                status=run_status,
                record_id=item.option_id,
                title=f"Experiment {item.option_id}",
                fields=fields,
                payload=payload,
                query=query,
            )
            if hit is not None:
                hits.append(hit)
    if "reviews" in resources and dossier.review is not None:
        payload = dossier.review.to_dict()
        fields = payload | {"run_id": run_id, "case_id": dossier.case_id, "status": run_status}
        hit = _hit(
            resource="reviews",
            run_id=run_id,
            case_id=dossier.case_id,
            dossier_id=dossier_id,
            status=run_status,
            record_id=dossier.review.review_id,
            title=f"Review {dossier.review.review_id}",
            fields=fields,
            payload=payload,
            query=query,
        )
        if hit is not None:
            hits.append(hit)
    return hits


def _blocked_hit(run_id: str, query: str | None) -> RunSearchHit | None:
    payload = {
        "run_id": run_id,
        "state": "blocked",
        "accepted": False,
        "warning": "run failed replay verification and was excluded from scientific projections",
    }
    return _hit(
        resource="runs",
        run_id=run_id,
        case_id="",
        dossier_id="",
        status="blocked",
        record_id=run_id,
        title=f"Blocked run {run_id}",
        fields=payload,
        payload=payload,
        query=query,
        accepted=False,
    )


def _search(
    runtime: CaseRuntime,
    *,
    query: str | None,
    resource: str,
    case_id: str | None,
    status: str | None,
    reviewer: str | None,
    review_state: str | None,
    state: str | None,
    tier: str | None,
    channel: str | None,
    min_support: float | None,
    max_uncertainty: float | None,
    assay: str | None,
    accepted_only: bool,
    offset: int,
    limit: int | None,
) -> RunSearchPage:
    if resource not in RUN_SEARCH_RESOURCES:
        raise ValidationError(f"resource must be one of: {', '.join(RUN_SEARCH_RESOURCES)}")
    _bounded(offset, limit)
    if min_support is not None and not 0.0 <= min_support <= 1.0:
        raise ValidationError("min_support must be between 0 and 1")
    if max_uncertainty is not None and not 0.0 <= max_uncertainty <= 1.0:
        raise ValidationError("max_uncertainty must be between 0 and 1")
    if state is not None:
        try:
            EvidenceState(state)
        except ValueError:
            if resource != "hypotheses":
                raise ValidationError(
                    "state must be a valid evidence state for evidence search"
                ) from None
    if tier is not None:
        try:
            EvidenceTier(tier)
        except ValueError as exc:
            raise ValidationError("tier must be a valid evidence tier") from exc
    if assay is not None:
        try:
            AssayType(assay)
        except ValueError as exc:
            raise ValidationError("assay must be a valid experiment assay") from exc

    filters = {
        "case_id": case_id,
        "status": status,
        "reviewer": reviewer,
        "review_state": review_state,
        "state": state,
        "tier": tier,
        "channel": channel,
        "min_support": min_support,
        "max_uncertainty": max_uncertainty,
        "assay": assay,
        "accepted_only": accepted_only,
    }
    hits: list[RunSearchHit] = []
    scanned = 0
    blocked = 0
    all_integrity_accepted = True
    for run_record in runtime.store.list_runs():
        scanned += 1
        run_id = str(run_record.get("run_id", ""))
        try:
            inspection = inspect_run(runtime, run_id)
        except (GlioError, OSError, ValueError, TypeError, KeyError):
            inspection = None
        if inspection is None or not inspection.accepted:
            blocked += 1
            all_integrity_accepted = False
            if not accepted_only and resource in {"all", "runs"}:
                hit = _blocked_hit(run_id, query)
                if hit is not None:
                    hits.append(hit)
            continue
        try:
            dossier = Dossier.from_dict(inspection.dossier_record)
        except (GlioError, OSError, ValueError, TypeError, KeyError):
            blocked += 1
            all_integrity_accepted = False
            if not accepted_only and resource in {"all", "runs"}:
                hit = _blocked_hit(run_id, query)
                if hit is not None:
                    hits.append(hit)
            continue
        hits.extend(
            _resource_hits(
                dossier,
                run_id=run_id,
                resource=resource,
                query=query,
                case_id=case_id,
                status=status,
                reviewer=reviewer,
                review_state=review_state,
                state=state,
                tier=tier,
                channel=channel,
                min_support=min_support,
                max_uncertainty=max_uncertainty,
                assay=assay,
            )
        )
    hits.sort(
        key=lambda item: (
            -item.score,
            _RESOURCE_ORDER.get(item.resource, 99),
            item.case_id,
            item.run_id,
            item.record_id,
        )
    )
    selected = tuple(hits[offset:] if limit is None else hits[offset : offset + limit])
    has_more = False if limit is None else offset + len(selected) < len(hits)
    public_body = {
        "query": query,
        "resource": resource,
        "rows": [item.to_dict() for item in selected],
        "total_count": len(hits),
        "offset": offset,
        "limit": limit,
        "has_more": has_more,
        "filters": filters,
        "scanned_run_count": scanned,
        "blocked_run_count": blocked,
    }
    accepted = all_integrity_accepted and not contains_private_key(public_body)
    return RunSearchPage(
        query=query,
        resource=resource,
        rows=selected,
        total_count=len(hits),
        offset=offset,
        limit=limit,
        has_more=has_more,
        filters=filters,
        scanned_run_count=scanned,
        blocked_run_count=blocked,
        accepted=accepted,
        content_address=content_hash(
            public_body | {"accepted": accepted},
            prefix="run-search-page",
        ),
    )


def search_persisted_runs(
    runtime: CaseRuntime,
    *,
    query: str | None = None,
    resource: str = "all",
    case_id: str | None = None,
    status: str | None = None,
    reviewer: str | None = None,
    review_state: str | None = None,
    state: str | None = None,
    tier: str | None = None,
    channel: str | None = None,
    min_support: float | None = None,
    max_uncertainty: float | None = None,
    assay: str | None = None,
    accepted_only: bool = False,
    offset: int = 0,
    limit: int | None = RUN_SEARCH_DEFAULT_LIMIT,
) -> RunSearchPage:
    """Search verified persisted runs with bounded deterministic ranking."""

    return _search(
        runtime,
        query=query,
        resource=resource,
        case_id=case_id,
        status=status,
        reviewer=reviewer,
        review_state=review_state,
        state=state,
        tier=tier,
        channel=channel,
        min_support=min_support,
        max_uncertainty=max_uncertainty,
        assay=assay,
        accepted_only=accepted_only,
        offset=offset,
        limit=limit,
    )


def build_run_search_closure(
    runtime: CaseRuntime,
    **filters: Any,
) -> dict[str, Any]:
    """Build a complete cross-run search closure without page truncation."""

    page = _search(
        runtime,
        query=filters.get("query"),
        resource=filters.get("resource", "all"),
        case_id=filters.get("case_id"),
        status=filters.get("status"),
        reviewer=filters.get("reviewer"),
        review_state=filters.get("review_state"),
        state=filters.get("state"),
        tier=filters.get("tier"),
        channel=filters.get("channel"),
        min_support=filters.get("min_support"),
        max_uncertainty=filters.get("max_uncertainty"),
        assay=filters.get("assay"),
        accepted_only=filters.get("accepted_only", False),
        offset=filters.get("offset", 0),
        limit=None,
    )
    closure = {
        "search_version": RUN_SEARCH_VERSION,
        "accepted": page.accepted,
        "page": page.to_dict(),
    }
    closure["content_address"] = content_hash(closure, prefix="run-search-closure")
    return closure


__all__ = [
    "RUN_SEARCH_DEFAULT_LIMIT",
    "RUN_SEARCH_MAX_LIMIT",
    "RUN_SEARCH_RESOURCES",
    "RUN_SEARCH_VERSION",
    "RunSearchHit",
    "RunSearchPage",
    "build_run_search_closure",
    "search_persisted_runs",
]
