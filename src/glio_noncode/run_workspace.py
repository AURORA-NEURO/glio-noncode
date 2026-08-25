"""Replay-gated workspace projections for persisted case runs.

The typed workspace builders already provide deterministic navigation for
manifests, dossiers, cohorts, and regulatory tracks.  This module connects the
case workspace to the durable run store.  It reopens the input and current
dossier only after replay verification, applies bounded workspace filters, and
returns a public projection suitable for an API, CLI, or offline handoff.

The projection is intentionally read-only.  It does not mutate a run, infer a
clinical conclusion, or expose the raw input object.  Public content addresses
are calculated after filtering prohibited attribution and direct-identifier
keys, so the address describes exactly what a consumer can receive.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from .errors import ValidationError
from .models import CaseManifest, Dossier
from .module_fabric_support import contains_private_key
from .run_catalog import RunInspection, inspect_run
from .runtime import CaseRuntime
from .serialization import content_hash, jsonable, require_non_empty
from .workspace import (
    CaseWorkspaceBuilder,
    ResearchWorkspace,
    VariantDetail,
    VariantExplorer,
    WorkspacePage,
    WorkspaceQuery,
    WorkspaceRecord,
    WorkspaceRecordType,
    WorkspaceState,
)

RUN_WORKSPACE_VERSION = "run-workspace-v1"
RUN_WORKSPACE_DEFAULT_LIMIT = 50
RUN_WORKSPACE_MAX_LIMIT = 500

_FORBIDDEN_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "contact_name",
        "email",
        "phone",
        "sample_id",
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "generated_by",
        "produced_by",
        "model_id",
        "model_name",
        "model_version",
        "author",
        "author_id",
        "author_name",
        "programming_language",
        "language",
    }
)


def _key_is_forbidden(key: object) -> bool:
    return str(key).casefold() in _FORBIDDEN_KEYS


def _public_projection(value: Any) -> Any:
    """Recursively project a value without direct identifiers or attribution."""

    value = jsonable(value)
    if isinstance(value, Mapping):
        return {
            str(key): _public_projection(item)
            for key, item in value.items()
            if not _key_is_forbidden(key)
        }
    if isinstance(value, (list, tuple)):
        return [_public_projection(item) for item in value]
    return value


def _has_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_key_is_forbidden(key) or _has_forbidden_key(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden_key(item) for item in value)
    return False


def _address(value: Any, prefix: str) -> str:
    return content_hash(value, prefix=prefix)


def _addressed_public(value: Mapping[str, Any], prefix: str) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_address", None)
    public = _public_projection(body)
    public["content_address"] = _address(public, prefix)
    return public


def _split_values(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """Normalize repeated or comma-separated filter values deterministically."""

    if value is None:
        return ()
    values = (value,) if isinstance(value, str) else tuple(value)
    result: list[str] = []
    for item in values:
        for part in str(item).split(","):
            normalized = part.strip()
            if normalized and normalized not in result:
                result.append(normalized)
    return tuple(result)


def _enum_values(
    value: str | Iterable[str] | None,
    enum_type: type[WorkspaceRecordType] | type[WorkspaceState],
    label: str,
) -> tuple[Any, ...]:
    selected: list[Any] = []
    for item in _split_values(value):
        try:
            parsed = enum_type(item)
        except ValueError as exc:
            allowed = ", ".join(member.value for member in enum_type)
            raise ValidationError(f"{label} must be one of: {allowed}") from exc
        if parsed not in selected:
            selected.append(parsed)
    return tuple(selected)


def workspace_query_from_filters(
    *,
    text: str | None = None,
    context_key: str | None = None,
    record_types: str | Iterable[str] | None = None,
    states: str | Iterable[str] | None = None,
    chromosome: str | None = None,
    start: int | None = None,
    end: int | None = None,
    source_ids: str | Iterable[str] | None = None,
    tags_all: str | Iterable[str] | None = None,
    offset: int = 0,
    limit: int = RUN_WORKSPACE_DEFAULT_LIMIT,
) -> WorkspaceQuery:
    """Build the shared workspace query contract used by HTTP and CLI callers."""

    return WorkspaceQuery(
        text=text or "",
        context_key=context_key,
        record_types=_enum_values(record_types, WorkspaceRecordType, "record_type"),
        states=_enum_values(states, WorkspaceState, "state"),
        chromosome=chromosome,
        start=start,
        end=end,
        source_ids=_split_values(source_ids),
        tags_all=_split_values(tags_all),
        offset=offset,
        limit=limit,
    )


def _public_workspace(workspace: ResearchWorkspace) -> dict[str, Any]:
    raw = workspace.to_dict()
    raw.pop("content_address", None)
    return _addressed_public(raw, "run-workspace")


def _public_page(page: WorkspacePage) -> dict[str, Any]:
    raw = page.to_dict()
    return _addressed_public(raw, "run-workspace-page")


def _public_variant_detail(detail: VariantDetail | None) -> dict[str, Any] | None:
    if detail is None:
        return None
    return _addressed_public(detail.to_dict(), "run-workspace-variant")


def _public_run_summary(inspection: RunInspection) -> dict[str, Any]:
    return _public_projection(inspection.summary.to_dict())


def _default_query(query: WorkspaceQuery | None) -> WorkspaceQuery:
    return query if query is not None else WorkspaceQuery(limit=RUN_WORKSPACE_DEFAULT_LIMIT)


@dataclass(frozen=True, slots=True)
class RunWorkspaceProjection:
    """One replay-gated, bounded persisted-run workspace response."""

    run_id: str
    case_id: str
    workspace_version: str
    run: Mapping[str, Any]
    integrity: Mapping[str, Any]
    workspace: Mapping[str, Any] | None
    page: Mapping[str, Any] | None
    variant: Mapping[str, Any] | None
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_version": self.workspace_version,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "run": dict(self.run),
            "integrity": dict(self.integrity),
            "workspace": self.workspace,
            "page": self.page,
            "variant": self.variant,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _projection(
    inspection: RunInspection,
    workspace: ResearchWorkspace | None,
    *,
    query: WorkspaceQuery,
    variant_id: str | None,
) -> RunWorkspaceProjection:
    run = _public_run_summary(inspection)
    integrity = _public_projection(inspection.summary.integrity.to_dict())
    warnings = list(str(item) for item in inspection.summary.warnings)
    warnings.extend(str(item) for item in inspection.summary.integrity.warnings)
    if workspace is None or not inspection.accepted:
        warnings.append("run failed replay verification; workspace records were withheld")
        body = {
            "workspace_version": RUN_WORKSPACE_VERSION,
            "run_id": inspection.summary.run_id,
            "case_id": inspection.summary.case_id,
            "run": run,
            "integrity": integrity,
            "workspace": None,
            "page": None,
            "variant": None,
            "warnings": tuple(dict.fromkeys(warnings)),
            "accepted": False,
        }
        return RunWorkspaceProjection(
            run_id=inspection.summary.run_id,
            case_id=inspection.summary.case_id,
            workspace_version=RUN_WORKSPACE_VERSION,
            run=run,
            integrity=integrity,
            workspace=None,
            page=None,
            variant=None,
            warnings=tuple(dict.fromkeys(warnings)),
            accepted=False,
            content_address=_address(body, "run-workspace-projection"),
        )

    page = workspace.search(query)
    detail = VariantExplorer().inspect(workspace, variant_id, context_key=query.context_key) if variant_id else None
    public_workspace = _public_workspace(workspace)
    public_page = _public_page(page)
    public_variant = _public_variant_detail(detail)
    warnings.extend(str(item) for item in page.warnings)
    accepted = not _has_forbidden_key(
        {
            "run": run,
            "integrity": integrity,
            "workspace": public_workspace,
            "page": public_page,
            "variant": public_variant,
        }
    ) and not contains_private_key(
        {
            "run": run,
            "integrity": integrity,
            "workspace": public_workspace,
            "page": public_page,
            "variant": public_variant,
        }
    )
    if not accepted:
        warnings.append("public workspace boundary rejected the projection")
    body = {
        "workspace_version": RUN_WORKSPACE_VERSION,
        "run_id": inspection.summary.run_id,
        "case_id": inspection.summary.case_id,
        "run": run,
        "integrity": integrity,
        "workspace": public_workspace,
        "page": public_page,
        "variant": public_variant,
        "warnings": tuple(dict.fromkeys(warnings)),
        "accepted": accepted,
    }
    return RunWorkspaceProjection(
        run_id=inspection.summary.run_id,
        case_id=inspection.summary.case_id,
        workspace_version=RUN_WORKSPACE_VERSION,
        run=run,
        integrity=integrity,
        workspace=public_workspace,
        page=public_page,
        variant=public_variant,
        warnings=tuple(dict.fromkeys(warnings)),
        accepted=accepted,
        content_address=_address(body, "run-workspace-projection"),
    )


def _load_workspace(
    runtime: CaseRuntime,
    run_id: str,
) -> tuple[RunInspection, ResearchWorkspace | None]:
    inspection = inspect_run(runtime, run_id)
    if not inspection.accepted:
        return inspection, None
    input_address = str(inspection.summary.input_address)
    input_payload = runtime.store.store.get(input_address)
    if not isinstance(input_payload, Mapping):
        raise ValidationError("persisted run input must be an object")
    manifest = CaseManifest.from_dict(input_payload)
    dossier = Dossier.from_dict(inspection.dossier_record)
    if manifest.case_id != dossier.case_id:
        raise ValidationError("workspace input and dossier case IDs do not match")
    if dossier.run_id != inspection.summary.run_id:
        raise ValidationError("workspace dossier run identifier does not match the run")
    return inspection, CaseWorkspaceBuilder().build(manifest, dossier=dossier)


def build_persisted_run_workspace(
    runtime: CaseRuntime,
    run_id: str,
    *,
    query: WorkspaceQuery | None = None,
    variant_id: str | None = None,
) -> RunWorkspaceProjection:
    """Reopen one run and return its bounded, public workspace page."""

    require_non_empty(str(run_id), "run_id")
    selected_query = _default_query(query)
    inspection, workspace = _load_workspace(runtime, run_id)
    return _projection(inspection, workspace, query=selected_query, variant_id=variant_id)


def _complete_records(
    workspace: ResearchWorkspace,
    query: WorkspaceQuery,
) -> tuple[WorkspaceRecord, ...]:
    """Page through the bounded browser so a closure never silently truncates."""

    page_size = RUN_WORKSPACE_MAX_LIMIT
    selected = replace(query, offset=0, limit=page_size)
    records: list[WorkspaceRecord] = []
    while True:
        page = workspace.search(selected)
        records.extend(page.records)
        if len(records) >= page.total_matches or not page.records:
            return tuple(records[: page.total_matches])
        selected = replace(selected, offset=len(records))


def _complete_page(
    workspace: ResearchWorkspace,
    query: WorkspaceQuery,
) -> dict[str, Any]:
    records = _complete_records(workspace, query)
    base = workspace.search(replace(query, offset=0, limit=RUN_WORKSPACE_MAX_LIMIT))
    facets = {
        "record_type": dict(sorted(Counter(item.record_type.value for item in records).items())),
        "state": dict(sorted(Counter(item.state.value for item in records).items())),
        "source_id": dict(
            sorted(Counter(source for item in records for source in item.source_ids).items())
        ),
    }
    warnings = tuple(dict.fromkeys(base.warnings))
    raw = {
        "workspace_id": workspace.workspace_id,
        "workspace_kind": workspace.kind,
        "query": replace(query, offset=0, limit=RUN_WORKSPACE_MAX_LIMIT),
        "state": WorkspaceState.ABSENT if not records else base.state,
        "records": records,
        "total_matches": len(records),
        "facets": facets,
        "warnings": warnings,
        "offset": 0,
        "limit": None,
        "has_more": False,
        "complete": True,
    }
    return _addressed_public(raw, "run-workspace-page")


def build_persisted_run_workspace_closure(
    runtime: CaseRuntime,
    run_id: str,
    *,
    query: WorkspaceQuery | None = None,
    variant_id: str | None = None,
) -> dict[str, Any]:
    """Return the complete replay-gated workspace closure for offline review."""

    selected_query = _default_query(query)
    inspection, workspace = _load_workspace(runtime, run_id)
    projection = _projection(inspection, workspace, query=selected_query, variant_id=variant_id)
    if workspace is None or not projection.accepted:
        closure = {
            "workspace_version": RUN_WORKSPACE_VERSION,
            "accepted": False,
            "complete": True,
            "projection": projection.to_dict(),
            "record_count": 0,
            "record_type_counts": {},
            "state_counts": {},
        }
        closure["content_address"] = _address(closure, "run-workspace-closure")
        return closure

    complete_page = _complete_page(workspace, selected_query)
    public_workspace = _public_workspace(workspace)
    page_records = complete_page.get("records", [])
    body = {
        "workspace_version": RUN_WORKSPACE_VERSION,
        "accepted": projection.accepted,
        "complete": True,
        "run": projection.run,
        "integrity": projection.integrity,
        "workspace": public_workspace,
        "page": complete_page,
        "variant": projection.variant,
        "warnings": list(projection.warnings),
        "record_count": len(page_records),
        "record_type_counts": dict(
            sorted(Counter(str(item.get("record_type", "")) for item in page_records).items())
        ),
        "state_counts": dict(
            sorted(Counter(str(item.get("state", "")) for item in page_records).items())
        ),
    }
    if _has_forbidden_key(body) or contains_private_key(body):
        body["accepted"] = False
        body["warnings"] = list(dict.fromkeys([*body["warnings"], "public workspace closure failed boundary checks"]))
    body["content_address"] = _address(body, "run-workspace-closure")
    return body


__all__ = [
    "RUN_WORKSPACE_DEFAULT_LIMIT",
    "RUN_WORKSPACE_MAX_LIMIT",
    "RUN_WORKSPACE_VERSION",
    "RunWorkspaceProjection",
    "build_persisted_run_workspace",
    "build_persisted_run_workspace_closure",
    "workspace_query_from_filters",
]
