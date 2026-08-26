"""Bounded, deterministic queries over verified mission-plan releases.

Queries operate only on a :class:`MissionPlanOfflineRelease` that has passed
filesystem verification.  They never reopen the live planner and never return
the request or internal routing fields used to produce the release.  Filtered
step rows retain their original dependency-safe order, making pagination
stable across repeated reads of the same immutable handoff.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MissionPlanOfflineRelease,
    MissionPlanReleaseBundle,
    load_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt, MissionPublicWorkflowStep
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_QUERY_VERSION = "mission-plan-release-query-v1"
MISSION_PLAN_RELEASE_QUERY_SCHEMA_VERSION = "mission-plan-release-query-schema-v1"
MISSION_PLAN_RELEASE_QUERY_CAPABILITIES_VERSION = "mission-plan-release-query-capabilities-v1"
MISSION_PLAN_RELEASE_QUERY_MAX_LIMIT = 512
MISSION_PLAN_RELEASE_QUERY_MAX_OFFSET = 1_000_000


def _text(value: Any, field: str) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    return normalized


def _optional_text(value: Any, field: str) -> str | None:
    if value in (None, ""):
        return None
    return _text(value, field)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be a boolean or null")
    return value


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseQuery:
    """Stable step filter and bounded page request."""

    kind: str | None = None
    optional: bool | None = None
    deterministic: bool | None = None
    depends_on: str | None = None
    offset: int = 0
    limit: int = 100

    def __post_init__(self) -> None:
        if self.kind is not None:
            _text(self.kind, "query.kind")
        if self.depends_on is not None:
            _text(self.depends_on, "query.depends_on")
        if self.offset < 0 or self.offset > MISSION_PLAN_RELEASE_QUERY_MAX_OFFSET:
            raise ValidationError("query.offset is outside the public bound")
        if self.limit <= 0 or self.limit > MISSION_PLAN_RELEASE_QUERY_MAX_LIMIT:
            raise ValidationError("query.limit is outside the public bound")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "MissionPlanReleaseQuery":
        if value is None:
            return cls()
        body = _mapping(value, "mission plan release query")
        allowed = {"kind", "optional", "deterministic", "depends_on", "offset", "limit"}
        unexpected = set(body) - allowed
        if unexpected:
            raise ValidationError(f"query contains unsupported fields: {sorted(unexpected)}")
        try:
            offset = int(body.get("offset", 0))
            limit = int(body.get("limit", 100))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError("query offset and limit must be integers") from exc
        return cls(
            kind=_optional_text(body.get("kind"), "query.kind"),
            optional=_optional_bool(body.get("optional"), "query.optional"),
            deterministic=_optional_bool(body.get("deterministic"), "query.deterministic"),
            depends_on=_optional_text(body.get("depends_on"), "query.depends_on"),
            offset=offset,
            limit=limit,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseQueryResult:
    """Addressed page of public workflow steps."""

    query_version: str
    release_id: str
    plan_id: str
    plan_address: str
    kind: str | None
    optional: bool | None
    deterministic: bool | None
    depends_on: str | None
    total_matches: int
    offset: int
    limit: int
    has_more: bool
    steps: tuple[MissionPublicWorkflowStep, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.query_version != MISSION_PLAN_RELEASE_QUERY_VERSION:
            raise ValidationError("mission plan release query version is invalid")
        _text(self.release_id, "result.release_id")
        _text(self.plan_id, "result.plan_id")
        _text(self.plan_address, "result.plan_address")
        if self.total_matches < 0 or self.offset < 0 or self.limit <= 0:
            raise ValidationError("query result pagination values are invalid")
        if len(self.steps) > self.limit:
            raise ValidationError("query result exceeds its limit")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _as_offline(
    value: MissionPlanOfflineRelease | str | Path,
) -> MissionPlanOfflineRelease:
    if isinstance(value, MissionPlanOfflineRelease):
        if not value.accepted:
            raise ValidationError("mission plan release is not accepted")
        return value
    return load_mission_plan_release(value)


def _query_steps(
    receipt: MissionPlanPublicReceipt,
    release_id: str,
    request: MissionPlanReleaseQuery,
) -> MissionPlanReleaseQueryResult:
    matches = []
    for step in receipt.steps:
        if request.kind is not None and step.kind != request.kind:
            continue
        if request.optional is not None and step.optional != request.optional:
            continue
        if request.deterministic is not None and step.deterministic != request.deterministic:
            continue
        if request.depends_on is not None and request.depends_on not in step.depends_on:
            continue
        matches.append(step)
    page = tuple(matches[request.offset : request.offset + request.limit])
    body = {
        "query_version": MISSION_PLAN_RELEASE_QUERY_VERSION,
        "release_id": release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "kind": request.kind,
        "optional": request.optional,
        "deterministic": request.deterministic,
        "depends_on": request.depends_on,
        "total_matches": len(matches),
        "offset": request.offset,
        "limit": request.limit,
        "has_more": request.offset + request.limit < len(matches),
        "steps": page,
        "accepted": True,
    }
    return MissionPlanReleaseQueryResult(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-query-result"),
    )


def query_mission_plan_receipt(
    receipt: MissionPlanPublicReceipt | Mapping[str, Any],
    query: MissionPlanReleaseQuery | Mapping[str, Any] | None = None,
    *,
    release_id: str | None = None,
) -> MissionPlanReleaseQueryResult:
    """Query an already public receipt without requiring a filesystem."""

    value = receipt if isinstance(receipt, MissionPlanPublicReceipt) else MissionPlanPublicReceipt.from_mapping(receipt)
    request = query if isinstance(query, MissionPlanReleaseQuery) else MissionPlanReleaseQuery.from_mapping(query)
    return _query_steps(value, release_id or f"plan-{value.plan_id}", request)


def query_mission_plan_release(
    release: MissionPlanOfflineRelease | MissionPlanReleaseBundle | str | Path,
    query: MissionPlanReleaseQuery | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseQueryResult:
    """Apply a bounded public step query to a verified release."""

    request = query if isinstance(query, MissionPlanReleaseQuery) else MissionPlanReleaseQuery.from_mapping(query)
    if isinstance(release, MissionPlanReleaseBundle):
        return _query_steps(release.receipt, release.release_id, request)
    offline = _as_offline(release)
    return _query_steps(offline.receipt, offline.release_id, request)


def mission_plan_release_query_json(result: MissionPlanReleaseQueryResult) -> str:
    """Render a canonical JSON query page."""

    return canonical_json(result.to_dict()) + "\n"


def mission_plan_release_query_csv(result: MissionPlanReleaseQueryResult) -> str:
    """Render a deterministic step table for a query page."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "step_id",
            "kind",
            "depends_on",
            "optional",
            "deterministic",
            "input_contract",
            "output_contract",
            "cpu",
            "memory_gb",
            "gpu_count",
            "storage_gb",
            "network_egress",
            "max_seconds",
        )
    )
    for step in result.steps:
        resource = step.resource
        writer.writerow(
            (
                step.step_id,
                step.kind,
                "|".join(step.depends_on),
                step.optional,
                step.deterministic,
                step.input_contract,
                step.output_contract,
                resource.get("cpu"),
                resource.get("memory_gb"),
                resource.get("gpu_count"),
                resource.get("storage_gb"),
                resource.get("network_egress"),
                resource.get("max_seconds"),
            )
        )
    return output.getvalue()


def mission_plan_release_query_markdown(result: MissionPlanReleaseQueryResult) -> str:
    """Render a human-readable query page without restricted metadata."""

    lines = [
        "# Mission plan release query",
        "",
        f"- Release: `{result.release_id}`",
        f"- Matching steps: `{result.total_matches}`",
        f"- Page: `{result.offset}`–`{result.offset + len(result.steps)}` of `{result.total_matches}`",
        f"- More pages: `{result.has_more}`",
        "",
        "| Step | Kind | Dependencies | Optional | Deterministic |",
        "| --- | --- | --- | --- | --- |",
    ]
    for step in result.steps:
        lines.append(
            f"| `{step.step_id}` | `{step.kind}` | `{', '.join(step.depends_on) or 'none'}` | "
            f"{step.optional} | {step.deterministic} |"
        )
    return "\n".join(lines) + "\n"


def mission_plan_release_query_export_payloads(
    result: MissionPlanReleaseQueryResult,
) -> dict[str, str]:
    """Return deterministic JSON, Markdown, and CSV query artifacts."""

    return {
        "mission-plan-release-query.json": mission_plan_release_query_json(result),
        "mission-plan-release-query.md": mission_plan_release_query_markdown(result),
        "mission-plan-release-query.csv": mission_plan_release_query_csv(result),
    }


def mission_plan_release_query_schema() -> dict[str, Any]:
    """Return the bounded query contract."""

    return {
        "version": MISSION_PLAN_RELEASE_QUERY_SCHEMA_VERSION,
        "query_version": MISSION_PLAN_RELEASE_QUERY_VERSION,
        "type": "object",
        "filters": {
            "kind": {"type": ["string", "null"]},
            "optional": {"type": ["boolean", "null"]},
            "deterministic": {"type": ["boolean", "null"]},
            "depends_on": {"type": ["string", "null"]},
            "offset": {"type": "integer", "minimum": 0, "maximum": MISSION_PLAN_RELEASE_QUERY_MAX_OFFSET},
            "limit": {"type": "integer", "minimum": 1, "maximum": MISSION_PLAN_RELEASE_QUERY_MAX_LIMIT},
        },
        "result_fields": [
            "query_version",
            "release_id",
            "plan_id",
            "plan_address",
            "total_matches",
            "offset",
            "limit",
            "has_more",
            "steps",
            "accepted",
            "content_address",
        ],
        "stable_order": "source workflow order",
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_query_capabilities() -> dict[str, Any]:
    """Return operational query capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_QUERY_CAPABILITIES_VERSION,
        "verified_release_input": True,
        "bounded_pagination": True,
        "kind_filter": True,
        "optionality_filter": True,
        "determinism_filter": True,
        "dependency_filter": True,
        "stable_workflow_order": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_QUERY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_QUERY_MAX_LIMIT",
    "MISSION_PLAN_RELEASE_QUERY_MAX_OFFSET",
    "MISSION_PLAN_RELEASE_QUERY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_QUERY_VERSION",
    "MissionPlanReleaseQuery",
    "MissionPlanReleaseQueryResult",
    "mission_plan_release_query_capabilities",
    "mission_plan_release_query_csv",
    "mission_plan_release_query_export_payloads",
    "mission_plan_release_query_json",
    "mission_plan_release_query_markdown",
    "mission_plan_release_query_schema",
    "query_mission_plan_release",
    "query_mission_plan_receipt",
]
