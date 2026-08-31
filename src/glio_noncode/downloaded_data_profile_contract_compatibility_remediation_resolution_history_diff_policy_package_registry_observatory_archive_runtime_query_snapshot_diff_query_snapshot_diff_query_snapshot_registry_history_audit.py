"""Independent audit for comparison-query snapshot registry histories."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_query_snapshot_diff_query_snapshot_diff_query_snapshot_registry_history as history_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version",
    "boundary",
    "entry-order",
    "identity",
    "unique-addresses",
    "predecessor-links",
    "transition-replay",
    "transition-counts",
    "latest-replay",
    "count-conservation",
    "query-conservation",
    "summary-replay",
    "entries-replay",
    "manifest-replay",
    "mapping-replay",
    "public-boundary",
)
CHECK_FIELDS = ("ordinal", "check_id", "passed", "detail", "evidence_addresses", "content_address")
AUDIT_FIELDS = ("history_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, required: bool = True) -> str:
    value = _text(value, field, 2048, required=required)
    if value and ("/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":"))):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _quality(value: Mapping[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    return (
        int(value["accepted"]),
        int(value["state"] == "ready"),
        int(value["ready_count"]),
        -int(value["blocked_count"]),
        -int(value["rejected_count"]),
        int(value["returned_query_rows"]),
        int(value["matched_query_rows"]),
        -int(value["entry_count"]),
    )


def _transition(current: Mapping[str, Any], previous: Mapping[str, Any] | None) -> str:
    if previous is None:
        return "initial"
    fields = ("entry_count", "ready_count", "blocked_count", "accepted_count", "rejected_count", "total_query_rows", "matched_query_rows", "returned_query_rows", "distinct_diff_count", "distinct_query_count", "state", "accepted")
    if tuple(current[key] for key in fields) == tuple(previous[key] for key in fields):
        return "unchanged"
    if _quality(current) > _quality(previous):
        return "improved"
    if _quality(current) < _quality(previous):
        return "regressed"
    return "changed"


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck:
    FIELDS = CHECK_FIELDS

    def __init__(self, ordinal: int, check_id: str, passed: bool, detail: str, evidence_addresses: Sequence[str], content_address: str) -> None:
        self.ordinal = _count(ordinal, "history audit check ordinal", MAX_CHECKS, positive=True)
        self.check_id = _label(check_id, "history audit check ID")
        if self.check_id not in CHECK_IDS:
            raise ValidationError("history audit check ID is unsupported")
        self.passed = _bool(passed, "history audit check result")
        self.detail = _text(detail, "history audit check detail", 4096)
        self.evidence_addresses = tuple(_address(item, "history audit evidence address") for item in _sequence(evidence_addresses, "history audit evidence", 32))
        self.content_address = _address(content_address, "history audit check address", CHECK_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history audit check crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("history audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history audit check")
        _strict(value, set(cls.FIELDS), "history audit check")
        return cls(*(value[field] for field in cls.FIELDS))


def address_check(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck):
        raise ValidationError("history audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit:
    FIELDS = AUDIT_FIELDS

    def __init__(self, history_address: str, checks: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck | Mapping[str, Any]], check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.history_address = _address(history_address, "history audit history address", history_model.HISTORY_PREFIX)
        self.checks = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck.from_mapping(item) for item in _sequence(checks, "history audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "history audit check count", MAX_CHECKS)
        self.passed_count = _count(passed_count, "history audit passed count", MAX_CHECKS)
        self.failed_count = _count(failed_count, "history audit failed count", MAX_CHECKS)
        self.accepted = _bool(accepted, "history audit acceptance")
        self.content_address = _address(content_address, "history audit address", AUDIT_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks) or self.accepted != (self.failed_count == 0):
            raise ValidationError("history audit check accounting does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history audit crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_audit(self) != self.content_address:
            raise ValidationError("history audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "checks": [check.to_dict() for check in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {"history_address": self.history_address, "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]):
        value = _mapping(value, "history audit")
        _strict(value, set(cls.FIELDS), "history audit")
        return cls(*(value[field] for field in cls.FIELDS))


def address_audit(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit):
        raise ValidationError("history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(ordinal: int, check_id: str, passed: bool, detail: str, evidence: Sequence[str]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "detail": detail, "evidence_addresses": tuple(evidence), "content_address": CHECK_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck(**(body | {"content_address": address_check(provisional)}))


def audit_history(value: history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
    if not isinstance(value, history_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistory):
        raise ValidationError("history audit requires a typed history")
    entries = value.entries.entries
    previous = None
    checks: list[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAuditCheck] = []
    checks.append(_check(1, "version", value.version == history_model.VERSION, "history version is current", (value.content_address,)))
    checks.append(_check(2, "boundary", value.boundary == history_model.BOUNDARY and history_model._public(value.to_dict()), "history boundary is public and value-free", (value.content_address,)))
    checks.append(_check(3, "entry-order", tuple(item.ordinal for item in entries) == tuple(range(1, len(entries) + 1)), "history entries are ordinal and contiguous", tuple(item.content_address for item in entries)))
    checks.append(_check(4, "identity", value.registry_id == (entries[0].registry_id if entries else ""), "history registry identity is conserved", (value.content_address,)))
    checks.append(_check(5, "unique-addresses", len({item.registry_address for item in entries}) == len(entries), "history registry addresses are unique", tuple(item.registry_address for item in entries)))
    checks.append(_check(6, "predecessor-links", all((not index and not item.previous_registry_address) or (index and item.previous_registry_address == entries[index - 1].registry_address) for index, item in enumerate(entries)), "history predecessor links are sequential", tuple(item.content_address for item in entries)))
    transition_passed = True
    for item in entries:
        expected = _transition(item.to_dict(), previous)
        transition_passed = transition_passed and item.transition == expected
        previous = item.to_dict()
    checks.append(_check(7, "transition-replay", transition_passed, "history transitions replay from adjacent summaries", tuple(item.content_address for item in entries)))
    observed_transitions = tuple(sum(item.transition == transition for item in entries) for transition in history_model.TRANSITIONS)
    expected_transitions = (value.initial_count, value.improved_count, value.regressed_count, value.unchanged_count, value.changed_count)
    checks.append(_check(8, "transition-counts", observed_transitions == expected_transitions, "history transition counts are conserved", (value.summary.content_address,)))
    latest = entries[-1] if entries else None
    expected_latest = (latest.registry_address, latest.entry_count, latest.ready_count, latest.blocked_count, latest.accepted_count, latest.rejected_count, latest.total_query_rows, latest.matched_query_rows, latest.returned_query_rows) if latest else ("", 0, 0, 0, 0, 0, 0, 0, 0)
    actual_latest = (value.latest_registry_address, value.latest_entry_count, value.latest_ready_count, value.latest_blocked_count, value.latest_accepted_count, value.latest_rejected_count, value.latest_total_query_rows, value.latest_matched_query_rows, value.latest_returned_query_rows)
    checks.append(_check(9, "latest-replay", actual_latest == expected_latest and (value.state, value.accepted) == ((latest.state, latest.accepted) if latest else ("empty", False)), "latest history disposition replays from the final entry", (value.summary.content_address,)))
    checks.append(_check(10, "count-conservation", all(item.ready_count + item.blocked_count == item.entry_count and item.accepted_count + item.rejected_count == item.entry_count for item in entries), "entry readiness and acceptance counts are conserved", tuple(item.content_address for item in entries)))
    checks.append(_check(11, "query-conservation", all(item.returned_query_rows <= item.matched_query_rows <= item.total_query_rows for item in entries), "entry query counts are conserved", tuple(item.content_address for item in entries)))
    summary_values = tuple(getattr(value.summary, field) for field in history_model.SUMMARY_FIELDS if field != "content_address")
    expected_summary = tuple(getattr(value, field) for field in history_model.SUMMARY_FIELDS if field != "content_address")
    checks.append(_check(12, "summary-replay", summary_values == expected_summary, "history summary replays the aggregate", (value.summary.content_address,)))
    checks.append(_check(13, "entries-replay", value.entries.content_address == history_model.address_entries(entries), "history entries address replays", (value.entries.content_address,)))
    checks.append(_check(14, "manifest-replay", value.manifest.files == history_model.FILES and tuple(value.manifest.artifact_addresses) == (value.entries.content_address, value.summary.content_address), "history manifest replays the exact members", (value.manifest.content_address,)))
    try:
        mapping_round_trip = history_model.history_from_mapping(value.to_dict()).content_address == value.content_address
    except ValidationError:
        mapping_round_trip = False
    checks.append(_check(15, "mapping-replay", mapping_round_trip, "history mapping round-trips to the same address", (value.content_address,)))
    checks.append(_check(16, "public-boundary", _public(value.to_dict()), "history contains no forbidden public metadata", (value.content_address,)))
    body = {"history_address": value.content_address, "checks": tuple(checks), "check_count": len(checks), "passed_count": sum(check.passed for check in checks), "failed_count": sum(not check.passed for check in checks), "accepted": all(check.passed for check in checks), "content_address": AUDIT_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit(**(body | {"content_address": address_audit(provisional)}))


def audit_from_mapping(value: Mapping[str, Any]):
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyPackageRegistryHistoryAudit.from_mapping(value)


def audit_json(value) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value) -> str:
    typed = audit_from_mapping(value.to_dict())
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHECK_FIELDS)
    for check in typed.checks:
        body = check.to_dict()
        writer.writerow(json.dumps(body[field], ensure_ascii=False, sort_keys=True) if isinstance(body[field], (tuple, list, dict)) else body[field] for field in CHECK_FIELDS)
    return output.getvalue()


def render_audit_markdown(value) -> str:
    typed = audit_from_mapping(value.to_dict())
    lines = ["# Comparison-Query Snapshot Registry History Audit", "", f"- History: `{typed.history_address}`", f"- Checks: `{typed.passed_count}/{typed.check_count}`", f"- Accepted: `{typed.accepted}`", f"- Address: `{typed.content_address}`", "", "| # | check | passed | detail |", "| ---: | --- | ---: | --- |"]
    lines.extend(f"| {check.ordinal} | `{check.check_id}` | `{check.passed}` | {check.detail} |" for check in typed.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1}, "check_id": {"enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_addresses": {"type": "array", "items": {"type": "string"}}, "content_address": {"type": "string"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Comparison-query snapshot registry history audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"history_address": {"type": "string"}, "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0}, "failed_count": {"type": "integer", "minimum": 0}, "accepted": {"type": "boolean"}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "check_ids": list(CHECK_IDS), "max_checks": MAX_CHECKS, "value_free": True, "operations": ["audit", "json", "csv", "markdown", "schema"]}
