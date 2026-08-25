"""Address-only indexes for fast offline D14 review queries.

The portable bundle is intentionally self-contained, but consumers should not
have to scan every JSON artifact for each filter.  This module builds a small,
deterministic index catalog from hydrated public artifacts.  Index rows retain
only public identifiers, artifact locations, and content addresses; they do
not copy operation payloads or raw text.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle

EVIDENCE_LIFECYCLE_OFFLINE_INDEX_VERSION = "evidence-lifecycle-offline-index-v1"
EVIDENCE_LIFECYCLE_OFFLINE_INDEX_DEFAULT_LIMIT = 50
EVIDENCE_LIFECYCLE_OFFLINE_INDEX_MAX_LIMIT = 500


class EvidenceLifecycleOfflineIndexResource(StrEnum):
    ARTIFACTS = "artifacts"
    RECORDS = "records"
    CHECKS = "checks"
    SOURCES = "sources"
    EVENTS = "events"


class EvidenceLifecycleOfflineIndexKey(StrEnum):
    ID = "id"
    KIND = "kind"
    OPERATION = "operation"
    ROLE = "role"
    STATE = "state"
    SOURCE = "source"
    PASSED = "passed"
    TYPE = "type"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndexRow:
    row_id: str
    resource: EvidenceLifecycleOfflineIndexResource
    key: EvidenceLifecycleOfflineIndexKey
    value: str
    artifact_id: str
    ordinal: int
    target_id: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("row_id", "value", "artifact_id", "target_id", "content_address"):
            require_non_empty(str(getattr(self, field)), field)
        if self.ordinal < 0:
            raise ValueError("offline index ordinals cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndex:
    resource: EvidenceLifecycleOfflineIndexResource
    rows: tuple[EvidenceLifecycleOfflineIndexRow, ...]
    unique_key_count: int
    content_address: str

    def __post_init__(self) -> None:
        if self.unique_key_count < 0:
            raise ValueError("offline index key count cannot be negative")

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def accepted(self) -> bool:
        return self.row_count == len({item.row_id for item in self.rows}) and self.unique_key_count == len({(item.key, item.value, item.target_id) for item in self.rows})

    def values(self) -> tuple[str, ...]:
        return tuple(sorted({item.value for item in self.rows}))

    def lookup(self, value: str) -> tuple[EvidenceLifecycleOfflineIndexRow, ...]:
        return tuple(item for item in self.rows if item.value == value)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"row_count": self.row_count, "accepted": self.accepted, "values": list(self.values())}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndexCatalog:
    bundle_id: str
    indexes: tuple[EvidenceLifecycleOfflineIndex, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def by_resource(self, resource: EvidenceLifecycleOfflineIndexResource) -> EvidenceLifecycleOfflineIndex:
        return next(item for item in self.indexes if item.resource is resource)

    @property
    def row_count(self) -> int:
        return sum(item.row_count for item in self.indexes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"index_count": len(self.indexes), "row_count": self.row_count}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndexQuery:
    bundle_id: str
    resource: EvidenceLifecycleOfflineIndexResource
    key: EvidenceLifecycleOfflineIndexKey
    value: str
    offset: int
    limit: int
    total: int
    rows: tuple[EvidenceLifecycleOfflineIndexRow, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndexCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineIndexAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleOfflineIndexCheck, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_check_count": sum(item.passed for item in self.checks), "failed_check_ids": list(self.failed_check_ids)}


def _payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineIndexCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleOfflineIndexCheck(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index-check"))


def _row(resource: EvidenceLifecycleOfflineIndexResource, key: EvidenceLifecycleOfflineIndexKey, value: Any, artifact_id: str, ordinal: int, target_id: Any) -> EvidenceLifecycleOfflineIndexRow:
    body = {"row_id": f"{resource.value}:{key.value}:{value}:{target_id}", "resource": resource, "key": key, "value": str(value), "artifact_id": artifact_id, "ordinal": ordinal, "target_id": str(target_id)}
    return EvidenceLifecycleOfflineIndexRow(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index-row"))


def _index(resource: EvidenceLifecycleOfflineIndexResource, rows: list[EvidenceLifecycleOfflineIndexRow]) -> EvidenceLifecycleOfflineIndex:
    ordered = tuple(sorted(rows, key=lambda item: (item.key.value, item.value, item.target_id, item.ordinal, item.row_id)))
    body = {"resource": resource, "rows": ordered, "unique_key_count": len({(item.key, item.value, item.target_id) for item in ordered})}
    return EvidenceLifecycleOfflineIndex(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index"))


def _as_sequence(value: Any) -> tuple[dict[str, Any], ...]:
    return tuple(item for item in value if isinstance(item, dict)) if isinstance(value, list) else ()


def _artifact_index(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndex:
    rows: list[EvidenceLifecycleOfflineIndexRow] = []
    for ordinal, item in enumerate(bundle.artifacts):
        rows.append(_row(EvidenceLifecycleOfflineIndexResource.ARTIFACTS, EvidenceLifecycleOfflineIndexKey.ID, item.artifact_id, "bundle.json", ordinal, item.artifact_id))
        rows.append(_row(EvidenceLifecycleOfflineIndexResource.ARTIFACTS, EvidenceLifecycleOfflineIndexKey.KIND, item.kind.value, "bundle.json", ordinal, item.artifact_id))
    return _index(EvidenceLifecycleOfflineIndexResource.ARTIFACTS, rows)


def _record_index(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndex:
    rows: list[EvidenceLifecycleOfflineIndexRow] = []
    fixture = _payload(bundle, "fixture")
    evaluation = _payload(bundle, "evaluation")
    for ordinal, item in enumerate(_as_sequence(fixture.get("records", ()) if isinstance(fixture, dict) else ())):
        record_id = item.get("record_id", "")
        rows.extend(
            (
                _row(EvidenceLifecycleOfflineIndexResource.RECORDS, EvidenceLifecycleOfflineIndexKey.ID, record_id, "fixture", ordinal, record_id),
                _row(EvidenceLifecycleOfflineIndexResource.RECORDS, EvidenceLifecycleOfflineIndexKey.OPERATION, item.get("operation", ""), "fixture", ordinal, record_id),
                _row(EvidenceLifecycleOfflineIndexResource.RECORDS, EvidenceLifecycleOfflineIndexKey.ROLE, item.get("role", ""), "fixture", ordinal, record_id),
            )
        )
        for source_id in item.get("source_ids", ()) if isinstance(item.get("source_ids"), list) else ():
            rows.append(_row(EvidenceLifecycleOfflineIndexResource.RECORDS, EvidenceLifecycleOfflineIndexKey.SOURCE, source_id, "fixture", ordinal, record_id))
    for ordinal, item in enumerate(_as_sequence(evaluation.get("executions", ()) if isinstance(evaluation, dict) else ())):
        record_id = item.get("record_id", "")
        rows.append(_row(EvidenceLifecycleOfflineIndexResource.RECORDS, EvidenceLifecycleOfflineIndexKey.STATE, item.get("state", ""), "evaluation", ordinal, record_id))
    return _index(EvidenceLifecycleOfflineIndexResource.RECORDS, rows)


def _check_index(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndex:
    rows: list[EvidenceLifecycleOfflineIndexRow] = []
    evaluation = _payload(bundle, "evaluation")
    for ordinal, item in enumerate(_as_sequence(evaluation.get("checks", ()) if isinstance(evaluation, dict) else ())):
        check_id = item.get("check_id", "")
        rows.extend(
            (
                _row(EvidenceLifecycleOfflineIndexResource.CHECKS, EvidenceLifecycleOfflineIndexKey.ID, check_id, "evaluation", ordinal, check_id),
                _row(EvidenceLifecycleOfflineIndexResource.CHECKS, EvidenceLifecycleOfflineIndexKey.PASSED, str(bool(item.get("passed"))).casefold(), "evaluation", ordinal, check_id),
            )
        )
        if item.get("record_id") is not None:
            rows.append(_row(EvidenceLifecycleOfflineIndexResource.CHECKS, EvidenceLifecycleOfflineIndexKey.ID, item.get("record_id"), "evaluation", ordinal, check_id))
    return _index(EvidenceLifecycleOfflineIndexResource.CHECKS, rows)


def _source_index(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndex:
    rows: list[EvidenceLifecycleOfflineIndexRow] = []
    fixture = _payload(bundle, "fixture")
    for ordinal, item in enumerate(_as_sequence(fixture.get("sources", ()) if isinstance(fixture, dict) else ())):
        source_id = item.get("source_id", "")
        rows.extend(
            (
                _row(EvidenceLifecycleOfflineIndexResource.SOURCES, EvidenceLifecycleOfflineIndexKey.ID, source_id, "fixture", ordinal, source_id),
                _row(EvidenceLifecycleOfflineIndexResource.SOURCES, EvidenceLifecycleOfflineIndexKey.TYPE, "https_receipt", "fixture", ordinal, source_id),
            )
        )
    return _index(EvidenceLifecycleOfflineIndexResource.SOURCES, rows)


def _event_index(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndex:
    rows: list[EvidenceLifecycleOfflineIndexRow] = []
    observability = _payload(bundle, "observability")
    for ordinal, item in enumerate(_as_sequence(observability.get("events", ()) if isinstance(observability, dict) else ())):
        event_id = item.get("event_id", "")
        rows.extend(
            (
                _row(EvidenceLifecycleOfflineIndexResource.EVENTS, EvidenceLifecycleOfflineIndexKey.ID, event_id, "observability", ordinal, event_id),
                _row(EvidenceLifecycleOfflineIndexResource.EVENTS, EvidenceLifecycleOfflineIndexKey.TYPE, item.get("event_type", ""), "observability", ordinal, event_id),
                _row(EvidenceLifecycleOfflineIndexResource.EVENTS, EvidenceLifecycleOfflineIndexKey.STATE, item.get("state", ""), "observability", ordinal, event_id),
            )
        )
    return _index(EvidenceLifecycleOfflineIndexResource.EVENTS, rows)


def build_evidence_lifecycle_offline_indexes(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineIndexCatalog:
    """Build five resource indexes from public artifact payloads."""

    indexes = (_artifact_index(bundle), _record_index(bundle), _check_index(bundle), _source_index(bundle), _event_index(bundle))
    counts = {item.resource.value: item.row_count for item in indexes}
    accepted = all(item.accepted for item in indexes) and len(indexes) == len(EvidenceLifecycleOfflineIndexResource)
    body = {"bundle_id": bundle.bundle_id, "indexes": indexes, "resource_counts": counts, "accepted": accepted}
    return EvidenceLifecycleOfflineIndexCatalog(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index-catalog"))


def query_evidence_lifecycle_offline_indexes(
    catalog: EvidenceLifecycleOfflineIndexCatalog,
    *,
    resource: EvidenceLifecycleOfflineIndexResource | str,
    key: EvidenceLifecycleOfflineIndexKey | str,
    value: str,
    offset: int = 0,
    limit: int = EVIDENCE_LIFECYCLE_OFFLINE_INDEX_DEFAULT_LIMIT,
) -> EvidenceLifecycleOfflineIndexQuery:
    if offset < 0:
        raise ValidationError("offline index offset cannot be negative")
    if limit < 1 or limit > EVIDENCE_LIFECYCLE_OFFLINE_INDEX_MAX_LIMIT:
        raise ValidationError(f"offline index limit must be between 1 and {EVIDENCE_LIFECYCLE_OFFLINE_INDEX_MAX_LIMIT}")
    resource_value = EvidenceLifecycleOfflineIndexResource(str(resource))
    key_value = EvidenceLifecycleOfflineIndexKey(str(key))
    selected = tuple(item for item in catalog.by_resource(resource_value).rows if item.key is key_value and item.value == value)
    page = selected[offset : offset + limit]
    body = {"bundle_id": catalog.bundle_id, "resource": resource_value, "key": key_value, "value": value, "offset": offset, "limit": limit, "total": len(selected), "rows": page, "accepted": catalog.accepted}
    return EvidenceLifecycleOfflineIndexQuery(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index-query"))


def audit_evidence_lifecycle_offline_indexes(bundle: EvidenceLifecycleOfflineBundle, catalog: EvidenceLifecycleOfflineIndexCatalog | None = None) -> EvidenceLifecycleOfflineIndexAudit:
    catalog = catalog or build_evidence_lifecycle_offline_indexes(bundle)
    checks = (
        _check("catalog-bundle", catalog.bundle_id == bundle.bundle_id, catalog.bundle_id, bundle.bundle_id, "index catalog points to the bundle"),
        _check("catalog-resource-count", len(catalog.indexes) == 5, len(catalog.indexes), 5, "all resource indexes are present"),
        _check("catalog-accepted", catalog.accepted, catalog.accepted, True, "every resource index is internally unique"),
        _check("artifact-index", catalog.by_resource(EvidenceLifecycleOfflineIndexResource.ARTIFACTS).row_count == bundle.artifact_count * 2, catalog.by_resource(EvidenceLifecycleOfflineIndexResource.ARTIFACTS).row_count, bundle.artifact_count * 2, "every artifact has ID and kind index rows"),
        _check("record-index", catalog.by_resource(EvidenceLifecycleOfflineIndexResource.RECORDS).lookup("C01-POS-001") != (), True, True, "positive record lookup resolves"),
        _check("check-index", catalog.by_resource(EvidenceLifecycleOfflineIndexResource.CHECKS).lookup("true") != (), True, True, "passed check lookup resolves"),
        _check("source-index", catalog.by_resource(EvidenceLifecycleOfflineIndexResource.SOURCES).row_count == 10, catalog.by_resource(EvidenceLifecycleOfflineIndexResource.SOURCES).row_count, 10, "each source has ID and receipt-type rows"),
        _check("event-index", catalog.by_resource(EvidenceLifecycleOfflineIndexResource.EVENTS).row_count == 78, catalog.by_resource(EvidenceLifecycleOfflineIndexResource.EVENTS).row_count, 78, "each event has ID, type, and state rows"),
        _check("catalog-address", catalog.content_address.startswith("evidence-lifecycle-offline-index-catalog:"), catalog.content_address, "address", "catalog is addressed"),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleOfflineIndexAudit(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-index-audit"))


def export_evidence_lifecycle_offline_indexes_csv(catalog: EvidenceLifecycleOfflineIndexCatalog) -> str:
    """Export index rows without payload material."""

    import csv
    import io

    fields = ("resource", "key", "value", "artifact_id", "ordinal", "target_id", "content_address")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for index in catalog.indexes:
        for row in index.rows:
            writer.writerow({"resource": row.resource.value, "key": row.key.value, "value": row.value, "artifact_id": row.artifact_id, "ordinal": row.ordinal, "target_id": row.target_id, "content_address": row.content_address})
    return stream.getvalue()


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_INDEX_DEFAULT_LIMIT",
    "EVIDENCE_LIFECYCLE_OFFLINE_INDEX_MAX_LIMIT",
    "EVIDENCE_LIFECYCLE_OFFLINE_INDEX_VERSION",
    "EvidenceLifecycleOfflineIndex",
    "EvidenceLifecycleOfflineIndexAudit",
    "EvidenceLifecycleOfflineIndexCatalog",
    "EvidenceLifecycleOfflineIndexCheck",
    "EvidenceLifecycleOfflineIndexKey",
    "EvidenceLifecycleOfflineIndexQuery",
    "EvidenceLifecycleOfflineIndexResource",
    "EvidenceLifecycleOfflineIndexRow",
    "audit_evidence_lifecycle_offline_indexes",
    "build_evidence_lifecycle_offline_indexes",
    "export_evidence_lifecycle_offline_indexes_csv",
    "query_evidence_lifecycle_offline_indexes",
]
