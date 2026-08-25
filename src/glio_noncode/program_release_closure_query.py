"""Bounded queries for the aggregate release closure."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_DEFAULT_LIMIT,
    PROGRAM_RELEASE_CLOSURE_MAX_LIMIT,
    ProgramReleaseQueryResult,
    ProgramReleaseSnapshot,
)
from .program_release_closure_support import csv_payload, jsonable, markdown_payload
from .serialization import content_hash

PROGRAM_RELEASE_CLOSURE_RESOURCES = ("domains", "artifacts", "dependencies", "gates", "runtime")


def _rows(snapshot: ProgramReleaseSnapshot, resource: str) -> list[dict[str, Any]]:
    if resource == "domains":
        return [item.to_dict() for item in snapshot.domains]
    if resource == "artifacts":
        return [item.to_dict() for item in snapshot.artifacts]
    if resource == "dependencies":
        return [item.to_dict() for item in snapshot.dependencies]
    if resource == "gates":
        return [item.to_dict() for item in snapshot.gates]
    if resource == "runtime":
        return [
            {
                "bundle_id": snapshot.bundle_id,
                "run_id": snapshot.run_id,
                "source_bundle_id": snapshot.source_bundle_id,
                "source_bundle_address": snapshot.source_bundle_address,
                "accepted": snapshot.accepted,
                "content_address": snapshot.content_address,
            }
        ]
    raise ValidationError(f"unsupported program release closure resource: {resource}")


def _matches(
    item: Mapping[str, Any],
    *,
    domain_id: str | None,
    gate_type: str | None,
    state: str | None,
    relation: str | None,
    accepted_only: bool,
    text: str | None,
) -> bool:
    if (
        domain_id
        and str(item.get("domain_id", "")) != domain_id
        and str(item.get("source_domain_id", "")) != domain_id
        and str(item.get("target_domain_id", "")) != domain_id
    ):
        return False
    if gate_type and str(item.get("gate_type", "")) != gate_type:
        return False
    if state and str(item.get("state", item.get("runtime_state", ""))) != state:
        return False
    if relation and str(item.get("relation", "")) != relation:
        return False
    if accepted_only and str(item.get("accepted", item.get("passed", False))).casefold() not in {
        "true",
        "1",
        "yes",
        "accepted",
        "published",
    }:
        return False
    if (
        text
        and text.casefold()
        not in json.dumps(jsonable(item), ensure_ascii=False, sort_keys=True).casefold()
    ):
        return False
    return True


def query_program_release_closure(
    snapshot: ProgramReleaseSnapshot,
    *,
    resource: str = "domains",
    domain_id: str | None = None,
    gate_type: str | None = None,
    state: str | None = None,
    relation: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = PROGRAM_RELEASE_CLOSURE_DEFAULT_LIMIT,
) -> ProgramReleaseQueryResult:
    """Return a deterministic bounded page from one public resource."""

    if resource not in PROGRAM_RELEASE_CLOSURE_RESOURCES:
        raise ValidationError(f"unsupported program release closure resource: {resource}")
    if offset < 0 or limit < 1 or limit > PROGRAM_RELEASE_CLOSURE_MAX_LIMIT:
        raise ValidationError("program release closure pagination is outside its contract")
    rows = [
        row
        for row in _rows(snapshot, resource)
        if _matches(
            row,
            domain_id=domain_id,
            gate_type=gate_type,
            state=state,
            relation=relation,
            accepted_only=accepted_only,
            text=text,
        )
    ]
    rows.sort(
        key=lambda row: (
            str(row.get("domain_id", row.get("source_domain_id", ""))),
            str(
                row.get(
                    "ordinal",
                    row.get("dependency_id", row.get("artifact_ref", row.get("gate_id", ""))),
                )
            ),
        )
    )
    page = tuple(rows[offset : offset + limit])
    filters = {
        "domain_id": domain_id,
        "gate_type": gate_type,
        "state": state,
        "relation": relation,
        "accepted_only": accepted_only,
        "text": text,
    }
    body = {
        "bundle_id": snapshot.bundle_id,
        "resource": resource,
        "filters": filters,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": page,
        "accepted": snapshot.accepted,
    }
    return ProgramReleaseQueryResult(
        snapshot.bundle_id,
        resource,
        filters,
        len(rows),
        offset,
        limit,
        page,
        snapshot.accepted,
        content_hash(body, prefix="program-release-query"),
    )


def export_program_release_query_csv(result: ProgramReleaseQueryResult) -> bytes:
    return csv_payload(result.items)


def export_program_release_query_markdown(result: ProgramReleaseQueryResult) -> bytes:
    return markdown_payload(f"Program release closure: {result.resource}", result.items)


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE_CLOSURE_RESOURCES")
    or name.startswith("query_program_release")
    or name.startswith("export_program_release")
    or name.startswith("ProgramRelease")
]
