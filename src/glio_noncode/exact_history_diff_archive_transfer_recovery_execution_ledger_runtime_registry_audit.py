"""Independent audit receipts for exact execution-ledger runtime registries."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry as registry_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = registry_model.VERSION + "-audit-v1"
BOUNDARY = registry_model.BOUNDARY + "_audit"
AUDIT_PREFIX = registry_model.REGISTRY_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version", "boundary", "registry-address", "entry-count", "entry-order",
    "identity-order", "entry-addresses", "accepted-count", "ready-count",
    "blocked-count", "state-replay", "acceptance-replay", "manifest-linkage",
    "summary-linkage", "public-boundary", "mapping-round-trip",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("registry_address", "registry_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
MAX_CHECKS = len(CHECK_IDS)


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or len(value) > maximum or not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value:
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None, *, allow_pending: bool = False) -> str:
    value = _text(value, field)
    if allow_pending and (value.startswith("pending:") or value.endswith(":pending")):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong public address namespace")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < lower or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck:
    """One independently recomputed registry check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger runtime registry audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger runtime registry audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger runtime registry audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and not self.content_address.endswith(":pending") and address_check(self) != self.content_address:
            raise ValidationError("ledger runtime registry audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck":
        value = _mapping(value, "ledger runtime registry audit check")
        _strict(value, set(cls.FIELDS), "ledger runtime registry audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit:
    """A fixed-size, value-free audit of a runtime registry."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, registry_address: str, registry_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.registry_address = _address(registry_address, "ledger runtime registry audit registry address", registry_model.REGISTRY_PREFIX)
        self.registry_id = _label(registry_id, "ledger runtime registry audit ID")
        self.version = _text(version, "ledger runtime registry audit version", 2048)
        self.boundary = _text(boundary, "ledger runtime registry audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger runtime registry audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger runtime registry audit check count", MAX_CHECKS)
        self.passed = _bool(passed, "ledger runtime registry audit result")
        self.content_address = _address(content_address, "ledger runtime registry audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime registry audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger runtime registry audit checks do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("ledger runtime registry audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"registry_address": self.registry_address, "registry_id": self.registry_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit":
        value = _mapping(value, "ledger runtime registry audit")
        _strict(value, set(cls.FIELDS), "ledger runtime registry audit")
        return cls(value["registry_address"], value["registry_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger runtime registry audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck):
        raise ValidationError("ledger runtime registry audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit):
        raise ValidationError("ledger runtime registry audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-runtime-registry-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def audit_registry(value: registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit:
    if not isinstance(value, registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistry):
        raise ValidationError("ledger runtime registry audit requires a typed registry")
    value = registry_model.verify_registry(value)
    keys = tuple((item.runtime_id, item.runtime_address) for item in value.entries)
    expected_entries = tuple(registry_model._entry_from_record(item.to_dict(), item.ordinal) for item in value.entries)
    expected_accepted = sum(item.accepted for item in value.entries)
    expected_ready = sum(item.state == "ready" for item in value.entries)
    expected_blocked = sum(item.state == "blocked" for item in value.entries)
    expected_state = "empty" if not value.entries else "ready" if expected_blocked == 0 else "blocked"
    expected_acceptance = not value.entries or expected_accepted == len(value.entries)
    expected_summary_body = {
        "registry_id": value.registry_id,
        "entry_count": len(value.entries),
        "accepted_count": expected_accepted,
        "ready_count": expected_ready,
        "blocked_count": expected_blocked,
        "state": expected_state,
        "accepted": expected_acceptance,
        "content_address": "pending:ledger-runtime-registry-summary",
    }
    expected_summary_provisional = registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary(**expected_summary_body)
    expected_summary = registry_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistrySummary(**(expected_summary_body | {"content_address": registry_model.address_summary(expected_summary_provisional)}))
    checks = (
        _check("version", value.version, registry_model.VERSION),
        _check("boundary", value.boundary, registry_model.BOUNDARY),
        _check("registry-address", registry_model.address_registry(value), value.content_address),
        _check("entry-count", (value.entry_count, len(value.entries)), (len(value.entries), len(value.entries))),
        _check("entry-order", tuple(item.ordinal for item in value.entries), tuple(range(1, len(value.entries) + 1))),
        _check("identity-order", keys, tuple(sorted(keys))),
        _check("entry-addresses", tuple(item.content_address for item in value.entries), tuple(item.content_address for item in expected_entries)),
        _check("accepted-count", value.accepted_count, expected_accepted),
        _check("ready-count", value.ready_count, expected_ready),
        _check("blocked-count", value.blocked_count, expected_blocked),
        _check("state-replay", value.state, expected_state),
        _check("acceptance-replay", value.accepted, expected_acceptance),
        _check("manifest-linkage", (value.manifest.registry_id, value.manifest.registry_address, value.manifest.files), (value.registry_id, value.content_address, registry_model.FILES)),
        _check("summary-linkage", value.summary.to_dict(), expected_summary.to_dict()),
        _check("public-boundary", registry_model._public(value.to_dict()), True),
        _check("mapping-round-trip", registry_model.registry_from_mapping(value.to_dict()).content_address, value.content_address),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit(value.content_address, value.registry_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-runtime-registry-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit(value.content_address, value.registry_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime registry audit", "", f"- Registry: `{value.registry_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime registry audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"registry_address": {"type": "string", "pattern": "^" + registry_model.REGISTRY_PREFIX + ":"}, "registry_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_registry", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeRegistryAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_registry", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
