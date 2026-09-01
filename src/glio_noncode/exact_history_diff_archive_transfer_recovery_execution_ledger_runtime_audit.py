"""Independent audit receipts for exact execution-ledger runtime handoffs."""

from __future__ import annotations

# ruff: noqa: E501, I001

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import exact_history_diff_archive_transfer_recovery_execution_ledger as ledger_model
from . import exact_history_diff_archive_transfer_recovery_execution_ledger_runtime as runtime_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = (
    "version", "boundary", "runtime-address", "stage-count", "stage-order",
    "stage-addresses", "stage-state-replay", "stage-acceptance-replay",
    "ledger-linkage", "audit-linkage", "query-linkage", "query-audit-linkage",
    "component-acceptance", "complete-replay", "public-boundary", "mapping-round-trip",
)
CHECK_FIELDS = ("check_id", "passed", "observed", "expected", "content_address")
AUDIT_FIELDS = ("runtime_address", "runtime_id", "version", "boundary", "checks", "check_count", "passed", "content_address")
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
    if allow_pending and value.startswith("pending:"):
        return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has the wrong address namespace")
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


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck:
    """One independently recomputed runtime handoff check."""

    FIELDS = CHECK_FIELDS

    def __init__(self, check_id: str, passed: bool, observed: Any, expected: Any, content_address: str) -> None:
        if check_id not in CHECK_IDS:
            raise ValidationError("ledger runtime audit check is unsupported")
        self.check_id = check_id
        self.passed = _bool(passed, "ledger runtime audit check result")
        self.observed = observed
        self.expected = expected
        self.content_address = _address(content_address, "ledger runtime audit check address", CHECK_PREFIX, allow_pending=True)
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("ledger runtime audit check address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck":
        value = _mapping(value, "ledger runtime audit check")
        _strict(value, set(cls.FIELDS), "ledger runtime audit check")
        return cls(*(value[field] for field in cls.FIELDS))


class ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit:
    """A fixed-size, value-free audit of a durable runtime handoff."""

    FIELDS = AUDIT_FIELDS

    def __init__(self, runtime_address: str, runtime_id: str, version: str, boundary: str, checks: Sequence[ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck], check_count: int, passed: bool, content_address: str) -> None:
        self.runtime_address = _address(runtime_address, "ledger runtime audit runtime address", runtime_model.RUNTIME_PREFIX)
        self.runtime_id = _label(runtime_id, "ledger runtime audit ID")
        self.version = _text(version, "ledger runtime audit version", 2048)
        self.boundary = _text(boundary, "ledger runtime audit boundary", 1024)
        self.checks = tuple(item if isinstance(item, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck) else ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck.from_mapping(item) for item in _sequence(checks, "ledger runtime audit checks", MAX_CHECKS))
        self.check_count = _count(check_count, "ledger runtime audit check count", MAX_CHECKS)
        self.passed = _bool(passed, "ledger runtime audit result")
        self.content_address = _address(content_address, "ledger runtime audit address", AUDIT_PREFIX, allow_pending=True)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("ledger runtime audit version or boundary is not current")
        if self.check_count != MAX_CHECKS or tuple(item.check_id for item in self.checks) != CHECK_IDS or self.passed != all(item.passed for item in self.checks):
            raise ValidationError("ledger runtime audit checks do not replay")
        if not self.content_address.startswith("pending:") and address_audit(self) != self.content_address:
            raise ValidationError("ledger runtime audit address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"runtime_address": self.runtime_address, "runtime_id": self.runtime_id, "version": self.version, "boundary": self.boundary, "checks": [item.to_dict() for item in self.checks], "check_count": self.check_count, "passed": self.passed, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "checks"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit":
        value = _mapping(value, "ledger runtime audit")
        _strict(value, set(cls.FIELDS), "ledger runtime audit")
        return cls(value["runtime_address"], value["runtime_id"], value["version"], value["boundary"], tuple(ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck.from_mapping(item) for item in _sequence(value["checks"], "ledger runtime audit checks", MAX_CHECKS)), value["check_count"], value["passed"], value["content_address"])


def address_check(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck):
        raise ValidationError("ledger runtime audit check address requires a typed check")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


def address_audit(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit) -> str:
    if not isinstance(value, ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit):
        raise ValidationError("ledger runtime audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, observed: Any, expected: Any) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck:
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck(check_id, observed == expected, observed, expected, "pending:ledger-runtime-audit-check")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck(check_id, provisional.passed, observed, expected, address_check(provisional))


def _components(value: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime) -> tuple[Any, Any, Any, Any]:
    components = (value.ledger, value.ledger_audit, value.query, value.query_audit)
    if any(item is None for item in components):
        raise ValidationError("ledger runtime audit requires composed receipts")
    return components


def audit_runtime(value: runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit:
    if not isinstance(value, runtime_model.ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntime):
        raise ValidationError("ledger runtime audit requires a typed runtime")
    value = runtime_model.verify_runtime(value)
    ledger, ledger_audit, query, query_audit = _components(value)
    expected_stages = runtime_model._build_stages(value, ledger, ledger_audit, query, query_audit)
    expected_acceptance = ledger.accepted and ledger_audit.passed and query_audit.passed
    checks = (
        _check("version", value.version, runtime_model.VERSION),
        _check("boundary", value.boundary, runtime_model.BOUNDARY),
        _check("runtime-address", runtime_model.address_runtime(value), value.content_address),
        _check("stage-count", (value.stage_count, len(value.stages)), (len(runtime_model.STAGES), len(runtime_model.STAGES))),
        _check("stage-order", tuple(item.stage for item in value.stages), runtime_model.STAGES),
        _check("stage-addresses", tuple(item.content_address for item in value.stages), tuple(item.content_address for item in expected_stages)),
        _check("stage-state-replay", tuple(item.state for item in value.stages), tuple(item.state for item in expected_stages)),
        _check("stage-acceptance-replay", tuple(item.accepted for item in value.stages), tuple(item.accepted for item in expected_stages)),
        _check("ledger-linkage", (value.ledger_id, value.ledger_address), (ledger.ledger_id, ledger.content_address)),
        _check("audit-linkage", value.ledger_audit_address, ledger_audit.content_address),
        _check("query-linkage", value.query_address, query.content_address),
        _check("query-audit-linkage", value.query_audit_address, query_audit.content_address),
        _check("component-acceptance", (ledger.accepted, ledger_audit.passed, query_audit.passed), (ledger.accepted, ledger_audit.passed, query_audit.passed)),
        _check("complete-replay", (value.state, value.accepted), ("ready" if expected_acceptance else "blocked", expected_acceptance)),
        _check("public-boundary", runtime_model._public(value.to_dict()), True),
        _check("mapping-round-trip", runtime_model.runtime_from_mapping(value.to_dict()).content_address, value.content_address),
    )
    provisional = ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit(value.content_address, value.runtime_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), "pending:ledger-runtime-audit")
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit(value.content_address, value.runtime_id, VERSION, BOUNDARY, checks, len(checks), all(item.passed for item in checks), address_audit(provisional))


def audit_from_mapping(value: Mapping[str, Any]) -> ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit:
    return ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit.from_mapping(value)


def audit_json(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit) -> str:
    return canonical_json(audit_from_mapping(value.to_dict()).to_dict())


def audit_csv(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CHECK_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def render_audit_markdown(value: ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit) -> str:
    value = audit_from_mapping(value.to_dict())
    lines = ["# Exact execution ledger runtime audit", "", f"- Runtime: `{value.runtime_id}`", f"- Checks: `{value.check_count}`", f"- Passed: `{value.passed}`", f"- Address: `{value.content_address}`", "", "| # | check | passed | observed | expected |", "| ---: | --- | --- | --- | --- |"]
    lines.extend(f"| {index} | `{item.check_id}` | `{item.passed}` | `{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |" for index, item in enumerate(value.checks, 1))
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime audit check", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {"check_id": {"type": "string", "enum": list(CHECK_IDS)}, "passed": {"type": "boolean"}, "observed": {}, "expected": {}, "content_address": {"type": "string", "pattern": "^" + CHECK_PREFIX + ":"}}}


def audit_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Exact execution ledger runtime audit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {"runtime_address": {"type": "string", "pattern": "^" + runtime_model.RUNTIME_PREFIX + ":"}, "runtime_id": {"type": "string"}, "version": {"type": "string", "const": VERSION}, "boundary": {"type": "string", "const": BOUNDARY}, "checks": {"type": "array", "items": check_schema(), "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS}, "check_count": {"type": "integer", "const": MAX_CHECKS}, "passed": {"type": "boolean"}, "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "audit_prefix": AUDIT_PREFIX, "check_prefix": CHECK_PREFIX, "check_ids": CHECK_IDS, "check_count": MAX_CHECKS, "operations": ("audit_runtime", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown"), "public_boundary": {"source_paths": False, "source_records": False, "raw_bytes": False, "private_fields": False}}


__all__ = ["AUDIT_FIELDS", "AUDIT_PREFIX", "BOUNDARY", "CHECK_FIELDS", "CHECK_IDS", "CHECK_PREFIX", "MAX_CHECKS", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAudit", "ExactHistoryDiffArchiveTransferRecoveryExecutionLedgerRuntimeAuditCheck", "VERSION", "address_audit", "address_check", "audit_csv", "audit_from_mapping", "audit_json", "audit_runtime", "audit_schema", "capabilities", "check_schema", "render_audit_markdown"]
