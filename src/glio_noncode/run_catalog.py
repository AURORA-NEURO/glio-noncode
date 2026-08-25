"""Catalog, inspection, and replay-integrity projections for persisted runs.

Case evaluation already writes immutable input, event, and dossier objects. This
module turns those objects into a deterministic read surface for local clients:
catalog pages contain bounded summaries, while inspection responses can reopen
the exact stored records and their replay verification report.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import StoreError
from .replay import ReplayReport, ReplayVerifier
from .runtime import CaseRuntime
from .serialization import content_hash

RUN_CATALOG_VERSION = "run-catalog-v1"
RUN_CATALOG_DEFAULT_LIMIT = 25
RUN_CATALOG_MAX_LIMIT = 100


def _require_run_id(run_id: str) -> str:
    """Reject path-like identifiers before they reach the filesystem store."""

    value = str(run_id).strip()
    if not value or len(value) > 128 or any(char in value for char in ("/", "\\", "..")):
        raise StoreError("invalid run identifier")
    return value


@dataclass(frozen=True, slots=True)
class RunIntegrity:
    """Integrity observations for one persisted run."""

    event_chain_valid: bool
    stored_dossier_matches_address: bool
    input_object_present: bool
    event_object_present: bool
    dossier_object_present: bool
    warnings: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            self.event_chain_valid
            and self.stored_dossier_matches_address
            and self.input_object_present
            and self.event_object_present
            and self.dossier_object_present
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_chain_valid": self.event_chain_valid,
            "stored_dossier_matches_address": self.stored_dossier_matches_address,
            "input_object_present": self.input_object_present,
            "event_object_present": self.event_object_present,
            "dossier_object_present": self.dossier_object_present,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Bounded catalog row for a persisted case evaluation."""

    run_id: str
    run_address: str
    case_id: str
    dossier_id: str
    dossier_address: str
    event_address: str
    input_address: str
    created_at: str
    status: str
    research_use_only: bool
    is_releasable: bool
    event_count: int
    hypothesis_count: int
    evidence_count: int
    experiment_count: int
    warning_count: int
    warnings: tuple[str, ...]
    integrity: RunIntegrity
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.integrity.accepted

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_address": self.run_address,
            "case_id": self.case_id,
            "dossier_id": self.dossier_id,
            "dossier_address": self.dossier_address,
            "event_address": self.event_address,
            "input_address": self.input_address,
            "created_at": self.created_at,
            "status": self.status,
            "research_use_only": self.research_use_only,
            "is_releasable": self.is_releasable,
            "event_count": self.event_count,
            "hypothesis_count": self.hypothesis_count,
            "evidence_count": self.evidence_count,
            "experiment_count": self.experiment_count,
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
            "integrity": self.integrity.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunCatalogPage:
    """Deterministic bounded page over run summaries."""

    rows: tuple[RunSummary, ...]
    total_count: int
    offset: int
    limit: int
    has_more: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "catalog_version": RUN_CATALOG_VERSION,
            "rows": [item.to_dict() for item in self.rows],
            "count": len(self.rows),
            "total_count": self.total_count,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.has_more,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunInspection:
    """Full immutable inspection response for one run."""

    summary: RunSummary
    run_record: dict[str, Any]
    event_record: dict[str, Any]
    dossier_record: dict[str, Any]
    replay: ReplayReport
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.summary.accepted

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "run": self.run_record,
            "events": list(self.event_record.get("events", [])),
            "dossier": self.dossier_record,
            "replay": self.replay.to_dict(),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _build_integrity(
    runtime: CaseRuntime,
    run_record: dict[str, Any],
    event_record: dict[str, Any],
    dossier_record: dict[str, Any],
) -> tuple[RunIntegrity, ReplayReport]:
    replay = ReplayVerifier().verify(run_record, event_record, dossier_record)
    warnings = list(replay.warnings)
    run_id = str(run_record.get("run_id", ""))
    if event_record.get("run_id") != run_id:
        warnings.append("event record run identifier does not match run record")
    if dossier_record.get("run_id") != run_id:
        warnings.append("dossier run identifier does not match run record")
    input_address = str(run_record.get("input_address", ""))
    event_address = str(run_record.get("event_address", ""))
    dossier_address = str(run_record.get("dossier_address", ""))
    body = {
        "event_chain_valid": replay.event_chain_valid,
        "stored_dossier_matches_address": replay.stored_dossier_matches_address,
        "input_object_present": runtime.store.store.exists(input_address),
        "event_object_present": runtime.store.store.exists(event_address),
        "dossier_object_present": runtime.store.store.exists(dossier_address),
        "warnings": tuple(warnings),
    }
    integrity = RunIntegrity(
        **body,
        content_address=content_hash(body, prefix="run-integrity"),
    )
    return integrity, replay


def _build_summary(
    runtime: CaseRuntime,
    run_record: dict[str, Any],
    event_record: dict[str, Any],
    dossier_record: dict[str, Any],
) -> tuple[RunSummary, ReplayReport]:
    integrity, replay = _build_integrity(runtime, run_record, event_record, dossier_record)
    review = dossier_record.get("review")
    body = {
        "run_id": str(run_record.get("run_id", "")),
        "run_address": content_hash(run_record, prefix="run-record"),
        "case_id": str(dossier_record.get("case_id", "")),
        "dossier_id": str(dossier_record.get("dossier_id", "")),
        "dossier_address": str(run_record.get("dossier_address", "")),
        "event_address": str(run_record.get("event_address", "")),
        "input_address": str(run_record.get("input_address", "")),
        "created_at": str(dossier_record.get("created_at", "")),
        "status": str(dossier_record.get("status", "")),
        "research_use_only": bool(dossier_record.get("research_use_only", False)),
        "is_releasable": bool(
            dossier_record.get("research_use_only", False)
            and isinstance(review, dict)
            and review.get("state") == "accepted"
        ),
        "event_count": len(event_record.get("events", [])),
        "hypothesis_count": len(dossier_record.get("hypotheses", [])),
        "evidence_count": len(dossier_record.get("evidence", [])),
        "experiment_count": len(dossier_record.get("experiments", [])),
        "warning_count": len(dossier_record.get("warnings", [])),
        "warnings": tuple(str(item) for item in dossier_record.get("warnings", ())),
        "integrity": integrity,
    }
    summary = RunSummary(
        **body,
        content_address=content_hash(body, prefix="run-summary"),
    )
    return summary, replay


def inspect_run(runtime: CaseRuntime, run_id: str) -> RunInspection:
    """Load one run and verify every persisted object involved in its replay."""

    selected_run_id = _require_run_id(run_id)
    run_record = runtime.get_run(selected_run_id)
    event_record = runtime.store.store.get(str(run_record["event_address"]))
    dossier_record = runtime.store.store.get(str(run_record["dossier_address"]))
    summary, replay = _build_summary(runtime, run_record, event_record, dossier_record)
    body = {
        "summary": summary,
        "run": run_record,
        "events": event_record.get("events", []),
        "dossier": dossier_record,
        "replay": replay,
    }
    return RunInspection(
        summary=summary,
        run_record=run_record,
        event_record=event_record,
        dossier_record=dossier_record,
        replay=replay,
        content_address=content_hash(body, prefix="run-inspection"),
    )


def get_run_dossier(runtime: CaseRuntime, run_id: str) -> dict[str, Any]:
    """Return only the immutable dossier payload for one validated run."""

    return inspect_run(runtime, run_id).dossier_record


def get_run_events(runtime: CaseRuntime, run_id: str) -> dict[str, Any]:
    """Return the stored event record for one validated run."""

    inspection = inspect_run(runtime, run_id)
    return {
        "run_id": inspection.summary.run_id,
        "event_address": inspection.summary.event_address,
        "events": list(inspection.event_record.get("events", [])),
        "replay": inspection.replay.to_dict(),
        "accepted": inspection.accepted,
        "content_address": content_hash(
            {
                "run_id": inspection.summary.run_id,
                "event_address": inspection.summary.event_address,
                "events": inspection.event_record.get("events", []),
                "replay": inspection.replay.to_dict(),
            },
            prefix="run-events",
        ),
    }


def build_run_catalog_page(
    runtime: CaseRuntime,
    *,
    case_id: str | None = None,
    status: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = RUN_CATALOG_DEFAULT_LIMIT,
) -> RunCatalogPage:
    """Build a bounded, filterable page from all persisted runs."""

    if offset < 0:
        raise ValueError("offset must be non-negative")
    if limit < 1 or limit > RUN_CATALOG_MAX_LIMIT:
        raise ValueError(f"limit must be between 1 and {RUN_CATALOG_MAX_LIMIT}")
    normalized_text = text.strip().lower() if text else None
    summaries: list[RunSummary] = []
    for record in runtime.store.list_runs():
        inspection = inspect_run(runtime, str(record.get("run_id", "")))
        summary = inspection.summary
        haystack = f"{summary.run_id} {summary.case_id} {summary.dossier_id} {summary.status}".lower()
        if case_id is not None and summary.case_id != case_id:
            continue
        if status is not None and summary.status != status:
            continue
        if normalized_text is not None and normalized_text not in haystack:
            continue
        summaries.append(summary)
    summaries.sort(key=lambda item: item.run_id)
    selected = tuple(summaries[offset : offset + limit])
    body = {
        "rows": selected,
        "total_count": len(summaries),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(selected) < len(summaries),
    }
    return RunCatalogPage(
        rows=selected,
        total_count=len(summaries),
        offset=offset,
        limit=limit,
        has_more=body["has_more"],
        accepted=all(item.accepted for item in summaries),
        content_address=content_hash(body, prefix="run-catalog-page"),
    )


def build_run_catalog_closure(runtime: CaseRuntime) -> dict[str, Any]:
    """Build a self-contained catalog and inspection closure for offline review."""

    page = build_run_catalog_page(runtime, limit=RUN_CATALOG_MAX_LIMIT)
    inspections = [inspect_run(runtime, item.run_id).to_dict() for item in page.rows]
    closure = {
        "catalog_version": RUN_CATALOG_VERSION,
        "accepted": page.accepted,
        "page": page.to_dict(),
        "inspections": inspections,
    }
    closure["content_address"] = content_hash(closure, prefix="run-catalog-closure")
    return closure


__all__ = [
    "RUN_CATALOG_DEFAULT_LIMIT",
    "RUN_CATALOG_MAX_LIMIT",
    "RUN_CATALOG_VERSION",
    "RunCatalogPage",
    "RunInspection",
    "RunIntegrity",
    "RunSummary",
    "build_run_catalog_closure",
    "build_run_catalog_page",
    "get_run_dossier",
    "get_run_events",
    "inspect_run",
]
