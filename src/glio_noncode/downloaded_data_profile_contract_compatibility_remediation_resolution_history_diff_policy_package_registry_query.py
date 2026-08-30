"""Bounded public queries over the policy-package admission registry."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as registry_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-query-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_query"
QUERY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "entries", "ready", "decisions")
DECISIONS = registry_model.DECISIONS
STATES = registry_model.STATES
QUERY_FIELDS = ("registry_address", "version", "boundary", "resources", "resource", "package_id", "decision", "state", "accepted", "release_ready", "text", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "rows", "content_address")
ROW_FIELDS = ("ordinal", "resource", "identity", "package_id", "package_address", "policy_id", "evaluation_id", "decision", "state", "accepted", "release_ready", "detail", "content_address")
MAX_TOTAL_COUNT = 1 + registry_model.MAX_ENTRIES
MAX_LIMIT = 100


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if any(char.isspace() for char in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _label(value, field)
    if ":" not in value or (prefix and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} must be an addressed public receipt")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} must be a bounded count")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _optional_bool(value: Any, field: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean or null")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    values = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not values or len(values) != len(set(values)) or any(item not in allowed for item in values) or values != tuple(sorted(values, key=allowed.index)):
        raise ValidationError(f"{field} must contain unique values in canonical order")
    return values


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow:
    FIELDS = ROW_FIELDS

    def __init__(self, ordinal: int, resource: str, identity: str, package_id: str, package_address: str, policy_id: str, evaluation_id: str, decision: str, state: str, accepted: bool, release_ready: bool, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "policy package registry query row ordinal", MAX_TOTAL_COUNT, positive=True)
        self.resource = _label(resource, "policy package registry query row resource")
        if self.resource not in RESOURCES:
            raise ValidationError("policy package registry query row resource is unsupported")
        self.identity = _label(identity, "policy package registry query row identity")
        self.package_id = _label(package_id, "policy package registry query row package ID")
        self.package_address = _address(package_address, "policy package registry query row package address", registry_model.package_model.PACKAGE_PREFIX)
        self.policy_id = _label(policy_id, "policy package registry query row policy ID")
        self.evaluation_id = _label(evaluation_id, "policy package registry query row evaluation ID")
        self.decision = _label(decision, "policy package registry query row decision")
        if self.decision not in DECISIONS:
            raise ValidationError("policy package registry query row decision is unsupported")
        self.state = _label(state, "policy package registry query row state")
        if self.state not in {"complete", "incomplete"}:
            raise ValidationError("policy package registry query row state is unsupported")
        self.accepted = _bool(accepted, "policy package registry query row acceptance")
        self.release_ready = _bool(release_ready, "policy package registry query row release readiness")
        self.detail = _text(detail, "policy package registry query row detail", 1024)
        self.content_address = _address(content_address, "policy package registry query row address", ROW_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("policy package registry query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("policy package registry query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow:
        value = _mapping(value, "policy package registry query row")
        _strict(value, set(cls.FIELDS), "policy package registry query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow):
        raise ValidationError("policy package registry query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery:
    FIELDS = QUERY_FIELDS

    def __init__(self, registry_address: str, version: str, boundary: str, resources: Sequence[str], resource: str, package_id: str, decision: str, state: str, accepted: bool | None, release_ready: bool | None, text: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, next_offset: int, truncated: bool, rows: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow | Mapping[str, Any]], content_address: str) -> None:
        self.registry_address = _address(registry_address, "policy package registry query registry address", registry_model.REGISTRY_PREFIX)
        self.version = _text(version, "policy package registry query version", 512)
        self.boundary = _text(boundary, "policy package registry query boundary", 512)
        self.resources = _ordered_labels(resources, "policy package registry query resources", RESOURCES)
        self.resource = _label(resource, "policy package registry query resource", required=False)
        if self.resource and self.resource not in self.resources:
            raise ValidationError("policy package registry query resource filter is not selected")
        self.package_id = _label(package_id, "policy package registry query package ID", required=False)
        self.decision = _label(decision, "policy package registry query decision", required=False)
        if self.decision and self.decision not in DECISIONS:
            raise ValidationError("policy package registry query decision filter is unsupported")
        self.state = _label(state, "policy package registry query state", required=False)
        if self.state and self.state not in {"complete", "incomplete"}:
            raise ValidationError("policy package registry query state filter is unsupported")
        self.accepted = _optional_bool(accepted, "policy package registry query accepted filter")
        self.release_ready = _optional_bool(release_ready, "policy package registry query release-ready filter")
        self.text = _text(text, "policy package registry query text", 512, required=False)
        self.offset = _count(offset, "policy package registry query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "policy package registry query limit", MAX_LIMIT, positive=True)
        self.total_count = _count(total_count, "policy package registry query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "policy package registry query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "policy package registry query returned count", MAX_LIMIT)
        self.next_offset = _count(next_offset, "policy package registry query next offset", MAX_TOTAL_COUNT + MAX_LIMIT)
        self.truncated = _bool(truncated, "policy package registry query truncation")
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow.from_mapping(item) for item in _sequence(rows, "policy package registry query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "policy package registry query address", QUERY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("policy package registry query version or boundary is not current")
        if self.returned_count != len(self.rows) or self.returned_count > self.limit or self.matched_count > self.total_count or self.returned_count > self.matched_count or self.next_offset != self.offset + self.returned_count or self.truncated != (self.next_offset < self.matched_count) or tuple(item.ordinal for item in self.rows) != tuple(range(1, self.returned_count + 1)) or not _public(self.to_dict()):
            raise ValidationError("policy package registry query counts or rows do not replay")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("policy package registry query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "version": self.version, "boundary": self.boundary, "resources": self.resources, "resource": self.resource, "package_id": self.package_id, "decision": self.decision, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "text": self.text, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "next_offset": self.next_offset, "truncated": self.truncated, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in ("registry_address", "version", "boundary", "resources", "resource", "package_id", "decision", "state", "accepted", "release_ready", "offset", "limit", "total_count", "matched_count", "returned_count", "next_offset", "truncated", "content_address")}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery:
        value = _mapping(value, "policy package registry query")
        _strict(value, set(cls.FIELDS), "policy package registry query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery):
        raise ValidationError("policy package registry query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(ordinal: int, resource: str, item: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry, detail: str) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow:
    body = {"ordinal": ordinal, "resource": resource, "identity": item.package_address, "package_id": item.package_id, "package_address": item.package_address, "policy_id": item.policy_id, "evaluation_id": item.evaluation_id, "decision": item.decision, "state": item.state, "accepted": item.accepted, "release_ready": item.release_ready, "detail": detail, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow(**(body | {"content_address": address_row(provisional)}))


def _rows(value: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry, resources: Sequence[str]) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow, ...]:
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow] = []
    ordinal = 1
    for resource in resources:
        if resource == "summary":
            summary = value.summary
            summary_entry = registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryEntry(
                ordinal=1,
                package_id=summary.registry_id,
                package_address=value.entries[0].package_address if value.entries else registry_model.package_model.PACKAGE_PREFIX + ":empty",
                package_version="summary",
                policy_id=summary.registry_id,
                evaluation_id=summary.registry_id,
                runtime_address=value.registry_id + ":summary-runtime",
                policy_audit_address=value.registry_id + ":summary-policy-audit",
                runtime_audit_address=value.registry_id + ":summary-runtime-audit",
                direction="aggregate",
                state="complete" if summary.state != "blocked" else "incomplete",
                decision="promote" if summary.promote_count else "hold" if summary.hold_count else "block",
                accepted=summary.accepted,
                release_ready=summary.release_ready,
                content_address=registry_model.ENTRY_PREFIX + ":pending",
            )
            rows.append(_row(ordinal, resource, summary_entry, "registry summary counters"))
            ordinal += 1
        elif resource == "entries":
            for item in value.entries:
                rows.append(_row(ordinal, resource, item, "admitted policy package entry"))
                ordinal += 1
        elif resource == "ready":
            for item in value.entries:
                if item.release_ready:
                    rows.append(_row(ordinal, resource, item, "release-ready policy package entry"))
                    ordinal += 1
        elif resource == "decisions":
            for item in value.entries:
                rows.append(_row(ordinal, resource, item, f"{item.decision} policy package decision"))
                ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow, query: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery) -> bool:
    if query.resource and row.resource != query.resource:
        return False
    if query.package_id and row.package_id != query.package_id:
        return False
    if query.decision and row.decision != query.decision:
        return False
    if query.state and row.state != query.state:
        return False
    if query.accepted is not None and row.accepted != query.accepted:
        return False
    if query.release_ready is not None and row.release_ready != query.release_ready:
        return False
    if query.text and query.text.casefold() not in " ".join((row.identity, row.package_id, row.policy_id, row.evaluation_id, row.detail)).casefold():
        return False
    return True


def query_registry(value: registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry, *, resources: Sequence[str] = RESOURCES, resource: str = "", package_id: str = "", decision: str = "", state: str = "", accepted: bool | None = None, release_ready: bool | None = None, text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery:
    if not isinstance(value, registry_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistry):
        raise ValidationError("policy package registry query requires a typed registry")
    resources = _ordered_labels(resources, "policy package registry query resources", RESOURCES)
    body = {"registry_address": value.content_address, "version": VERSION, "boundary": BOUNDARY, "resources": resources, "resource": resource, "package_id": package_id, "decision": decision, "state": state, "accepted": accepted, "release_ready": release_ready, "text": text, "offset": offset, "limit": limit, "total_count": 0, "matched_count": 0, "returned_count": 0, "next_offset": 0, "truncated": False, "rows": (), "content_address": QUERY_PREFIX + ":pending"}
    provisional_query = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery(**body)
    all_rows = _rows(value, resources)
    matching = tuple(item for item in all_rows if _matches(item, provisional_query))
    page = matching[offset:offset + limit]
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow(**(item.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"})) for ordinal, item in enumerate(page, 1))
    rows = tuple(DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow(**(item.to_dict() | {"content_address": address_row(item)})) for item in rows)
    body = body | {"total_count": len(all_rows), "matched_count": len(matching), "returned_count": len(rows), "next_offset": offset + len(rows), "truncated": offset + len(rows) < len(matching), "rows": rows}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(ROW_FIELDS)
    for item in value.rows:
        writer.writerow(tuple(json.dumps(item.to_dict()[field], ensure_ascii=False, sort_keys=True) if isinstance(item.to_dict()[field], (tuple, list, dict)) else item.to_dict()[field] for field in ROW_FIELDS))
    return output.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Policy Package Registry Query", "", f"- Registry: `{value.registry_address}`", f"- Resources: `{', '.join(value.resources)}`", f"- Matched: `{value.matched_count}`", f"- Returned: `{value.returned_count}`", f"- Address: `{value.content_address}`", "", "| ordinal | resource | package | decision | state | ready |", "| ---: | --- | --- | --- | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.resource}` | `{item.package_id}` | `{item.decision}` | `{item.state}` | `{item.release_ready}` |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "resource": {"enum": list(RESOURCES)}, "identity": {"type": "string"}, "package_id": {"type": "string"}, "package_address": {"type": "string"}, "policy_id": {"type": "string"}, "evaluation_id": {"type": "string"}, "decision": {"enum": list(DECISIONS)}, "state": {"enum": ["complete", "incomplete"]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data policy package registry query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"registry_address": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "resource": {"type": "string"}, "package_id": {"type": "string"}, "decision": {"type": "string"}, "state": {"type": "string"}, "accepted": {"type": ["boolean", "null"]}, "release_ready": {"type": ["boolean", "null"]}, "text": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "next_offset": {"type": "integer", "minimum": 0}, "truncated": {"type": "boolean"}, "rows": {"type": "array", "items": {"$ref": "#/$defs/row"}}, "content_address": {"type": "string"}}, "$defs": {"row": row_schema()}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "resources": list(RESOURCES), "decisions": list(DECISIONS), "states": list(STATES), "max_total_count": MAX_TOTAL_COUNT, "max_limit": MAX_LIMIT, "features": ["bounded summary and entry queries", "readiness and decision projections", "package identity and text filters", "deterministic pagination", "addressable rows", "JSON CSV and Markdown projections"], "public_boundary": {"source_paths": False, "source_records": False}}


__all__ = ["BOUNDARY", "DECISIONS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "STATES", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_registry", "query_schema", "render_query_markdown", "row_schema"]
