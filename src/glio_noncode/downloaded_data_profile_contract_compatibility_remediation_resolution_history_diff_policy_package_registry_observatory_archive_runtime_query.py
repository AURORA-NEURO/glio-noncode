"""Bounded inspection queries over a persisted archive inspection runtime.

The query reads public runtime receipts and attached component receipts. It
emits deterministic, value-free rows for state-machine stages, lineage links,
component summaries, and materialized runtime artifact receipts. A public
runtime JSON projection remains useful without attached component bodies.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = runtime_model.VERSION + "-query-v1"
BOUNDARY = runtime_model.BOUNDARY + "_query"
QUERY_PREFIX = runtime_model.RUNTIME_PREFIX + "-query"
ROW_PREFIX = QUERY_PREFIX + "-row"
RESOURCES = ("summary", "stages", "links", "components", "artifacts")
COMPONENTS = ("archive", "archive-audit", "query", "query-audit")
MAX_LIMIT = 128
MAX_TOTAL_COUNT = 1 + len(runtime_model.STAGES) + 2 * len(COMPONENTS) + len(runtime_model.ARTIFACT_FILES)
ROW_FIELDS = ("resource", "ordinal", "stage", "component", "name", "size", "hash", "runtime_id", "archive_id", "version", "boundary", "state", "accepted", "count", "matched_count", "returned_count", "address", "detail", "content_address")
QUERY_FIELDS = ("runtime_address", "runtime_id", "resources", "stage_filter", "state_filter", "accepted_filter", "component_filter", "address_filter", "name_filter", "text_filter", "offset", "limit", "total_count", "matched_count", "returned_count", "rows", "content_address")


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = False) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = False) -> str:
    value = _text(value, field, 4096, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool_or_none(value: Any, field: str) -> bool | None:
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


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and key.casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _runtime_state(value: Any, field: str) -> str:
    value = _label(value, field)
    if value and value not in runtime_model.STATES:
        raise ValidationError(f"{field} is unsupported")
    return value


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow:
    """One addressed row in a runtime inspection query."""

    FIELDS = ROW_FIELDS

    def __init__(self, resource: str, ordinal: int, stage: str, component: str, name: str, size: int, hash: str, runtime_id: str, archive_id: str, version: str, boundary: str, state: str, accepted: bool, count: int, matched_count: int, returned_count: int, address: str, detail: str, content_address: str) -> None:
        self.resource = _label(resource, "runtime query row resource", required=True)
        if self.resource not in RESOURCES:
            raise ValidationError("runtime query row resource is unsupported")
        self.ordinal = _count(ordinal, "runtime query row ordinal", MAX_TOTAL_COUNT)
        if self.ordinal < 1:
            raise ValidationError("runtime query row ordinal must be positive")
        self.stage = _label(stage, "runtime query row stage")
        if self.stage and self.stage not in runtime_model.STAGES:
            raise ValidationError("runtime query row stage is unsupported")
        self.component = _label(component, "runtime query row component")
        if self.component and self.component not in COMPONENTS:
            raise ValidationError("runtime query row component is unsupported")
        self.name = _label(name, "runtime query row name")
        self.size = _count(size, "runtime query row size", runtime_model.MAX_RUNTIME_BYTES)
        self.hash = _address(hash, "runtime query row hash")
        self.runtime_id = _label(runtime_id, "runtime query row runtime ID", required=True)
        self.archive_id = _label(archive_id, "runtime query row archive ID", required=True)
        self.version = _text(version, "runtime query row version")
        self.boundary = _label(boundary, "runtime query row boundary", required=True)
        self.state = _runtime_state(state, "runtime query row state")
        if not isinstance(accepted, bool):
            raise ValidationError("runtime query row acceptance must be boolean")
        self.accepted = accepted
        self.count = _count(count, "runtime query row count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "runtime query row matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "runtime query row returned count", MAX_TOTAL_COUNT)
        self.address = _address(address, "runtime query row address", required=True)
        self.detail = _text(detail, "runtime query row detail", 2048, required=False)
        self.content_address = _address(content_address, "runtime query row content address", ROW_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.resource == "summary" and (self.stage or self.component or self.name):
            raise ValidationError("runtime summary row has unexpected identity fields")
        if self.resource == "stages" and (not self.stage or self.component or self.name):
            raise ValidationError("runtime stage row has invalid identity fields")
        if self.resource in {"links", "components"} and (not self.component or self.stage or self.name):
            raise ValidationError("runtime component row has invalid identity fields")
        if self.resource == "artifacts" and (not self.name or self.stage or self.component):
            raise ValidationError("runtime artifact row has invalid identity fields")
        if self.resource == "artifacts" and self.size < 1:
            raise ValidationError("runtime artifact rows require positive byte sizes")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query row crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_row(self) != self.content_address:
            raise ValidationError("runtime query row address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime query row")
        _strict(value, set(cls.FIELDS), "runtime query row")
        return cls(*(value[field] for field in cls.FIELDS))


def address_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow):
        raise ValidationError("runtime query row address requires a typed row")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ROW_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery:
    """A bounded, addressed runtime inspection query result."""

    FIELDS = QUERY_FIELDS

    def __init__(self, runtime_address: str, runtime_id: str, resources: Sequence[str], stage_filter: str, state_filter: str, accepted_filter: bool | None, component_filter: str, address_filter: str, name_filter: str, text_filter: str, offset: int, limit: int, total_count: int, matched_count: int, returned_count: int, rows: Sequence[Any], content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "runtime query runtime address", runtime_model.RUNTIME_PREFIX, required=True)
        self.runtime_id = _label(runtime_id, "runtime query runtime ID", required=True)
        resources = _sequence(resources, "runtime query resources", len(RESOURCES))
        if not resources or len(set(resources)) != len(resources) or any(item not in RESOURCES for item in resources):
            raise ValidationError("runtime query resources are invalid")
        self.resources = tuple(item for item in RESOURCES if item in resources)
        self.stage_filter = _label(stage_filter, "runtime query stage filter")
        if self.stage_filter and self.stage_filter not in runtime_model.STAGES:
            raise ValidationError("runtime query stage filter is unsupported")
        self.state_filter = _runtime_state(state_filter, "runtime query state filter")
        self.accepted_filter = _bool_or_none(accepted_filter, "runtime query acceptance filter")
        self.component_filter = _label(component_filter, "runtime query component filter")
        if self.component_filter and self.component_filter not in COMPONENTS:
            raise ValidationError("runtime query component filter is unsupported")
        self.address_filter = _address(address_filter, "runtime query address filter")
        self.name_filter = _label(name_filter, "runtime query name filter")
        self.text_filter = _text(text_filter, "runtime query text filter", 1024, required=False)
        self.offset = _count(offset, "runtime query offset", MAX_TOTAL_COUNT)
        self.limit = _count(limit, "runtime query limit", MAX_LIMIT)
        if self.limit < 1:
            raise ValidationError("runtime query limit must be positive")
        self.total_count = _count(total_count, "runtime query total count", MAX_TOTAL_COUNT)
        self.matched_count = _count(matched_count, "runtime query matched count", MAX_TOTAL_COUNT)
        self.returned_count = _count(returned_count, "runtime query returned count", MAX_LIMIT)
        self.rows = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow.from_mapping(item) for item in _sequence(rows, "runtime query rows", MAX_LIMIT))
        self.content_address = _address(content_address, "runtime query content address", QUERY_PREFIX, required=True)
        self._validate()

    def _validate(self) -> None:
        if self.matched_count > self.total_count or self.returned_count != len(self.rows) or self.returned_count > self.limit or self.returned_count > max(0, self.matched_count - self.offset) or tuple(item.ordinal for item in self.rows) != tuple(range(self.offset + 1, self.offset + self.returned_count + 1)):
            raise ValidationError("runtime query counts or pagination do not replay")
        if any(item.resource not in self.resources for item in self.rows):
            raise ValidationError("runtime query contains a row outside the selected resources")
        if any(item.runtime_id != self.runtime_id or not item.address for item in self.rows):
            raise ValidationError("runtime query row lineage does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("runtime query crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_query(self) != self.content_address:
            raise ValidationError("runtime query address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "runtime_id": self.runtime_id, "resources": self.resources, "stage_filter": self.stage_filter, "state_filter": self.state_filter, "accepted_filter": self.accepted_filter, "component_filter": self.component_filter, "address_filter": self.address_filter, "name_filter": self.name_filter, "text_filter": self.text_filter, "offset": self.offset, "limit": self.limit, "total_count": self.total_count, "matched_count": self.matched_count, "returned_count": self.returned_count, "rows": [item.to_dict() for item in self.rows], "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rows"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "runtime query")
        _strict(value, set(cls.FIELDS), "runtime query")
        return cls(*(value[field] for field in cls.FIELDS))


def address_query(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery):
        raise ValidationError("runtime query address requires a typed query")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX)


def _row(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime, resource: str, ordinal: int, **updates: Any) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow:
    body = {"resource": resource, "ordinal": ordinal, "stage": "", "component": "", "name": "", "size": 0, "hash": "", "runtime_id": value.runtime_id, "archive_id": value.archive_id, "version": value.version, "boundary": value.boundary, "state": value.state, "accepted": value.accepted, "count": 0, "matched_count": 0, "returned_count": 0, "address": value.content_address, "detail": "", "content_address": ROW_PREFIX + ":pending"}
    body.update(updates)
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow(**(body | {"content_address": address_row(provisional)}))


def _renumber_row(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow, ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow:
    body = value.to_dict() | {"ordinal": ordinal, "content_address": ROW_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow(**(body | {"content_address": address_row(provisional)}))


def _component_rows(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> tuple[dict[str, Any], ...]:
    details: dict[str, dict[str, Any]] = {
        "archive": {"address": value.archive_address, "state": "ready", "accepted": True, "count": value.archive.artifact_count if value.archive is not None else 0, "detail": "archive envelope receipt"},
        "archive-audit": {"address": value.archive_audit_address, "state": "ready" if value.archive_audit is None or value.archive_audit.accepted else "blocked", "accepted": value.archive_audit.accepted if value.archive_audit is not None else value.accepted, "count": value.archive_audit.check_count if value.archive_audit is not None else 0, "detail": "independent archive audit receipt"},
        "query": {"address": value.query_address, "state": "ready", "accepted": True, "count": value.query.total_count if value.query is not None else 0, "matched_count": value.query.matched_count if value.query is not None else 0, "returned_count": value.query.returned_count if value.query is not None else 0, "detail": "bounded archive query receipt"},
        "query-audit": {"address": value.query_audit_address, "state": "ready" if value.query_audit is None or value.query_audit.accepted else "blocked", "accepted": value.query_audit.accepted if value.query_audit is not None else value.accepted, "count": value.query_audit.check_count if value.query_audit is not None else 0, "detail": "independent archive query audit receipt"},
    }
    return tuple(details[item] | {"component": item} for item in COMPONENTS)


def _all_rows(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime) -> tuple[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow, ...]:
    value = runtime_model.verify_runtime(value)
    rows: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow] = []
    ordinal = 1
    rows.append(_row(value, "summary", ordinal, count=value.stage_count, address=value.content_address, detail="runtime acceptance and stage-count summary"))
    ordinal += 1
    for stage in value.stages:
        rows.append(_row(value, "stages", ordinal, stage=stage.stage, state=stage.state, accepted=stage.accepted, address=stage.address, detail=stage.detail))
        ordinal += 1
    for resource in ("links", "components"):
        for item in _component_rows(value):
            rows.append(_row(value, resource, ordinal, component=item["component"], state=item["state"], accepted=item["accepted"], count=item.get("count", 0), matched_count=item.get("matched_count", 0), returned_count=item.get("returned_count", 0), address=item["address"], detail=item["detail"]))
            ordinal += 1
    try:
        manifest = runtime_model.manifest_document(value)
    except ValidationError:
        manifest = None
    if manifest is not None:
        for receipt in manifest["artifacts"]:
            rows.append(_row(value, "artifacts", ordinal, name=receipt["name"], size=receipt["size"], hash=receipt["hash"], accepted=value.accepted, address=receipt["content_address"], detail="runtime document byte receipt"))
            ordinal += 1
    return tuple(rows)


def _matches(row: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow, *, stage: str, state: str, accepted: bool | None, component: str, address: str, name: str, text: str) -> bool:
    if stage and row.stage != stage or state and row.state != state or accepted is not None and row.accepted != accepted or component and row.component != component or address and row.address != address or name and row.name != name:
        return False
    if text:
        return text.casefold() in " ".join(str(row.to_dict()[field]) for field in ROW_FIELDS if field != "content_address").casefold()
    return True


def query_runtime(value: runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime, *, resources: Sequence[str] | None = None, stage: str = "", state: str = "", accepted: bool | None = None, component: str = "", address: str = "", name: str = "", text: str = "", offset: int = 0, limit: int = MAX_LIMIT) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery:
    if not isinstance(value, runtime_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntime):
        raise ValidationError("runtime query requires a typed runtime")
    value = runtime_model.verify_runtime(value)
    selected = tuple(RESOURCES if resources is None else _sequence(resources, "runtime query resources", len(RESOURCES)))
    if not selected or len(set(selected)) != len(selected) or any(item not in RESOURCES for item in selected):
        raise ValidationError("runtime query resources are invalid")
    _label(stage, "runtime query stage filter")
    _runtime_state(state, "runtime query state filter")
    _bool_or_none(accepted, "runtime query acceptance filter")
    _label(component, "runtime query component filter")
    _address(address, "runtime query address filter")
    _label(name, "runtime query name filter")
    _text(text, "runtime query text filter", 1024, required=False)
    _count(offset, "runtime query offset", MAX_TOTAL_COUNT)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
        raise ValidationError("runtime query limit is outside its bound")
    selected_rows = tuple(row for row in _all_rows(value) if row.resource in selected)
    matched = tuple(row for row in selected_rows if _matches(row, stage=stage, state=state, accepted=accepted, component=component, address=address, name=name, text=text))
    page = tuple(_renumber_row(row, index) for index, row in enumerate(matched[offset:offset + limit], offset + 1))
    body = {"runtime_address": value.content_address, "runtime_id": value.runtime_id, "resources": tuple(item for item in RESOURCES if item in selected), "stage_filter": stage, "state_filter": state, "accepted_filter": accepted, "component_filter": component, "address_filter": address, "name_filter": name, "text_filter": text, "offset": offset, "limit": limit, "total_count": len(selected_rows), "matched_count": len(matched), "returned_count": len(page), "rows": page, "content_address": QUERY_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery(**(body | {"content_address": address_query(provisional)}))


def query_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery.from_mapping(value)


def query_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> str:
    return canonical_json(query_from_mapping(value.to_dict()).to_dict())


def query_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> str:
    value = query_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.rows:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_query_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery) -> str:
    value = query_from_mapping(value.to_dict())
    lines = ["# Policy Package Registry Observatory Archive Runtime Query", "", f"- Runtime: {chr(96)}{value.runtime_id}{chr(96)}", f"- Resources: {chr(96)}{', '.join(value.resources)}{chr(96)}", f"- Rows: {chr(96)}{value.returned_count}{chr(96)} of {chr(96)}{value.matched_count}{chr(96)}", f"- Address: {chr(96)}{value.content_address}{chr(96)}", "", "| # | resource | stage | component | name | state | accepted |", "| ---: | --- | --- | --- | --- | --- | :---: |"]
    lines.extend(f"| {item.ordinal} | {chr(96)}{item.resource}{chr(96)} | {chr(96)}{item.stage}{chr(96)} | {chr(96)}{item.component}{chr(96)} | {chr(96)}{item.name}{chr(96)} | {chr(96)}{item.state}{chr(96)} | {chr(96)}{item.accepted}{chr(96)} |" for item in value.rows)
    return "\n".join(lines) + "\n"


def row_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query row", "type": "object", "additionalProperties": False, "required": list(ROW_FIELDS), "properties": {"resource": {"type": "string", "enum": list(RESOURCES)}, "ordinal": {"type": "integer", "minimum": 1}, "stage": {"type": "string", "enum": [""] + list(runtime_model.STAGES)}, "component": {"type": "string", "enum": [""] + list(COMPONENTS)}, "name": {"type": "string"}, "size": {"type": "integer", "minimum": 0}, "hash": {"type": "string"}, "runtime_id": {"type": "string"}, "archive_id": {"type": "string"}, "version": {"type": "string"}, "boundary": {"type": "string"}, "state": {"type": "string", "enum": list(runtime_model.STATES)}, "accepted": {"type": "boolean"}, "count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "address": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string", "pattern": "^" + ROW_PREFIX + ":"}}}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Policy package registry observatory archive runtime query", "type": "object", "additionalProperties": False, "required": list(QUERY_FIELDS), "properties": {"runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "runtime_id": {"type": "string"}, "resources": {"type": "array", "items": {"enum": list(RESOURCES)}}, "stage_filter": {"type": "string"}, "state_filter": {"type": "string"}, "accepted_filter": {"type": ["boolean", "null"]}, "component_filter": {"type": "string"}, "address_filter": {"type": "string"}, "name_filter": {"type": "string"}, "text_filter": {"type": "string"}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT}, "total_count": {"type": "integer", "minimum": 0}, "matched_count": {"type": "integer", "minimum": 0}, "returned_count": {"type": "integer", "minimum": 0}, "rows": {"type": "array", "items": row_schema(), "maxItems": MAX_LIMIT}, "content_address": {"type": "string", "pattern": "^" + QUERY_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "query_prefix": QUERY_PREFIX, "row_prefix": ROW_PREFIX, "resources": list(RESOURCES), "components": list(COMPONENTS), "max_limit": MAX_LIMIT, "max_total_count": MAX_TOTAL_COUNT, "features": ["runtime state-machine projection", "component lineage projection", "runtime manifest receipt projection", "exact address and text filters", "deterministic pagination", "JSON CSV and Markdown projections"]}


__all__ = ["BOUNDARY", "COMPONENTS", "MAX_LIMIT", "MAX_TOTAL_COUNT", "QUERY_FIELDS", "QUERY_PREFIX", "RESOURCES", "ROW_FIELDS", "ROW_PREFIX", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQuery", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryObservatoryArchiveRuntimeQueryRow", "address_query", "address_row", "capabilities", "query_csv", "query_from_mapping", "query_json", "query_runtime", "query_schema", "render_query_markdown", "row_schema"]

