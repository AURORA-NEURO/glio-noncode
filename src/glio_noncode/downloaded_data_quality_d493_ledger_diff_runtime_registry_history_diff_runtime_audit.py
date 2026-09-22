"""Independent replay audit for D493 history-diff policy runtimes."""
from __future__ import annotations
# ruff: noqa: E501, I001
import csv
import io
from collections.abc import Mapping
from typing import Any
from . import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from . import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from .errors import ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash

VERSION = runtime_model.VERSION + "-audit-v1"
BOUNDARY = runtime_model.BOUNDARY + "_audit"
AUDIT_PREFIX = runtime_model.RUNTIME_PREFIX + "-audit"
CHECK_PREFIX = AUDIT_PREFIX + "-check"
CHECK_IDS = ("typed_runtime", "diff_link", "check_sequence", "counter_replay", "policy_replay", "summary_replay", "manifest_replay", "disposition_replay", "direction_link", "transition_link", "comparison_link", "check_addresses", "address_integrity", "public_boundary", "canonical_runtime")
CHECK_FIELDS = ("ordinal", "check_id", "passed", "actual", "expected", "detail", "content_address")
AUDIT_FIELDS = ("runtime_id", "diff_id", "runtime_address", "checks", "check_count", "passed_count", "failed_count", "accepted", "content_address")
MAX_CHECKS = len(CHECK_IDS)

def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()) or any(ord(c) < 32 and c not in "\n\t" for c in value): raise ValidationError(f"{field} must be bounded text")
    return value
def _label(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if value.strip() != value or any(c.isspace() for c in value) or "/" in value or "\\" in value or '"' in value: raise ValidationError(f"{field} must be a compact label")
    return value
def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 4096)
    if value.startswith("pending:") or value.endswith(":pending"): return value
    if ":" not in value or "/" in value or "\\" in value or '"' in value or (prefix and not value.startswith(prefix + ":")): raise ValidationError(f"{field} has the wrong namespace")
    return value
def _count(value: Any, field: str, maximum: int, *, lower: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum: raise ValidationError(f"{field} is outside its bound")
    return value
def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool): raise ValidationError(f"{field} must be boolean")
    return value
def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not hasattr(value, "__len__") or not hasattr(value, "__iter__") or len(value) > maximum: raise ValidationError(f"{field} must be a bounded array")
    return tuple(value)
def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping): raise ValidationError(f"{field} must be an object")
    return value
def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed: raise ValidationError(f"{field} contains unknown or missing fields")
def _public(value: Any) -> bool: return runtime_model.diff_model._public(value)
def _address_for(value: Any, prefix: str) -> str: return content_hash(value.to_dict() | {"content_address": None}, prefix=prefix)
def _seal(value: Any, address_function: Any) -> Any:
    value.content_address = address_function(value); value._validate(); return value

class AuditCheck:
    FIELDS = CHECK_FIELDS
    def __init__(self, ordinal: int, check_id: str, passed: bool, actual: str, expected: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "D493 audit ordinal", MAX_CHECKS, lower=1); self.check_id = _label(check_id, "D493 check ID"); self.passed = _bool(passed, "D493 check result"); self.actual = _text(actual, "D493 actual", 32768); self.expected = _text(expected, "D493 expected", 32768); self.detail = _text(detail, "D493 detail", 4096); self.content_address = _address(content_address, "D493 check address", CHECK_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_id not in CHECK_IDS: raise ValidationError("D493 audit check is unsupported")
        if not self.content_address.startswith("pending:") and _address_for(self, CHECK_PREFIX) != self.content_address: raise ValidationError("D493 audit check address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 audit check crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {f: getattr(self, f) for f in self.FIELDS[:-1]} | {"content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AuditCheck":
        value = _mapping(value, "D493 audit check"); _strict(value, set(cls.FIELDS), "D493 audit check"); return cls(*(value[f] for f in cls.FIELDS))

def address_check(value: AuditCheck) -> str:
    if not isinstance(value, AuditCheck): raise ValidationError("D493 addressing requires a typed check")
    return _address_for(value, CHECK_PREFIX)

class RuntimeAudit:
    FIELDS = AUDIT_FIELDS
    def __init__(self, runtime_id: str, diff_id: str, runtime_address: str, checks: Any, check_count: int, passed_count: int, failed_count: int, accepted: bool, content_address: str) -> None:
        self.runtime_id = _label(runtime_id, "D493 audit runtime ID"); self.diff_id = _label(diff_id, "D493 audit diff ID"); self.runtime_address = _address(runtime_address, "D493 runtime address", runtime_model.RUNTIME_PREFIX); self.checks = tuple(x if isinstance(x, AuditCheck) else AuditCheck.from_mapping(_mapping(x, "D493 audit check")) for x in _sequence(checks, "D493 audit checks", MAX_CHECKS)); self.check_count = _count(check_count, "D493 audit count", MAX_CHECKS); self.passed_count = _count(passed_count, "D493 passed count", MAX_CHECKS); self.failed_count = _count(failed_count, "D493 failed count", MAX_CHECKS); self.accepted = _bool(accepted, "D493 audit acceptance"); self.content_address = _address(content_address, "D493 audit address", AUDIT_PREFIX); self._validate()
    def _validate(self) -> None:
        if self.check_count != len(self.checks) or self.check_count != MAX_CHECKS or self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(x.passed for x in self.checks) or self.accepted != (self.failed_count == 0): raise ValidationError("D493 audit counters do not replay")
        if tuple(x.ordinal for x in self.checks) != tuple(range(1, MAX_CHECKS + 1)) or tuple(x.check_id for x in self.checks) != CHECK_IDS: raise ValidationError("D493 audit checks are not canonical")
        if not self.content_address.startswith("pending:") and _address_for(self, AUDIT_PREFIX) != self.content_address: raise ValidationError("D493 audit address does not replay")
        if not _public(self.to_dict()): raise ValidationError("D493 audit crosses the public boundary")
    def to_dict(self) -> dict[str, Any]: return {"runtime_id": self.runtime_id, "diff_id": self.diff_id, "runtime_address": self.runtime_address, "checks": [x.to_dict() for x in self.checks], "check_count": self.check_count, "passed_count": self.passed_count, "failed_count": self.failed_count, "accepted": self.accepted, "content_address": self.content_address}
    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeAudit":
        value = _mapping(value, "D493 audit"); _strict(value, set(cls.FIELDS), "D493 audit"); return cls(*(value[f] for f in cls.FIELDS))

def address_audit(value: RuntimeAudit) -> str:
    if not isinstance(value, RuntimeAudit): raise ValidationError("D493 addressing requires a typed audit")
    return _address_for(value, AUDIT_PREFIX)

def _finding(ordinal: int, check_id: str, passed: bool, actual: Any, expected: Any, detail: str) -> AuditCheck:
    body = {"ordinal": ordinal, "check_id": check_id, "passed": bool(passed), "actual": canonical_json(actual), "expected": canonical_json(expected), "detail": detail, "content_address": f"pending:{CHECK_PREFIX}"}; item = AuditCheck(**body); return AuditCheck(**(body | {"content_address": address_check(item)}))

def audit_runtime(value: runtime_model.HistoryDiffRuntime, diff: diff_model.HistoryDiff | None = None) -> RuntimeAudit:
    runtime_model.verify_runtime(value)
    if diff is not None: diff_model.verify_diff(diff)
    policy = value.policy
    transition_parts = value.state_transition.split("->")
    same_state = len(transition_parts) != 2 or transition_parts[0] == transition_parts[1]
    expected_policy = (
        bool(value.diff_id and value.diff_address),
        (not policy.require_accepted) or value.accepted,
        value.item_count >= policy.minimum_items,
        value.added_count <= policy.maximum_added,
        value.removed_count <= policy.maximum_removed,
        value.changed_count <= policy.maximum_changed,
        value.direction in policy.allowed_directions,
        (not policy.require_state_change) or not same_state,
        policy.allow_unchanged or value.unchanged_count == 0,
        value.added_count + value.removed_count + value.changed_count + value.unchanged_count == value.item_count,
        policy.diff_id == value.diff_id,
        value.summary.diff_address == value.diff_address,
        runtime_model.address_policy(policy) == policy.content_address,
    )
    diff_link = diff is None or (diff.diff_id == value.diff_id and diff.content_address == value.diff_address)
    direction_link = diff is None or value.direction == diff.direction
    transition_link = diff is None or value.state_transition == diff.state_transition
    comparison_link = diff is None or (value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count, value.accepted) == (diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.accepted)
    checks = (
        _finding(1, "typed_runtime", isinstance(value, runtime_model.HistoryDiffRuntime), type(value).__name__, "HistoryDiffRuntime", "runtime uses the typed D493 model"),
        _finding(2, "diff_link", diff_link, (value.diff_id, value.diff_address), (diff.diff_id, diff.content_address) if diff is not None else "detached diff reference", "runtime binds to the exact evaluated comparison"),
        _finding(3, "check_sequence", (tuple(x.ordinal for x in value.checks), tuple(x.check_id for x in value.checks)) == (tuple(range(1, MAX_CHECKS + 1)), runtime_model.CHECK_IDS), [x.check_id for x in value.checks], runtime_model.CHECK_IDS, "checks are contiguous and in canonical order"),
        _finding(4, "counter_replay", (value.check_count, value.passed_count, value.failed_count) == (len(value.checks), sum(x.passed for x in value.checks), sum(not x.passed for x in value.checks)), (value.check_count, value.passed_count, value.failed_count), "replayed counters", "runtime counters derive from the check results"),
        _finding(5, "policy_replay", tuple(x.passed for x in value.checks[:13]) == expected_policy, tuple(x.passed for x in value.checks[:13]), expected_policy, "policy outcomes are independently recomputed from retained evidence"),
        _finding(6, "summary_replay", tuple(getattr(value.summary, f) for f in runtime_model.SUMMARY_FIELDS[:-1]) == (value.runtime_id, value.diff_id, value.diff_address, policy.content_address, value.check_count, value.passed_count, value.failed_count, value.release_ready, value.state, value.direction, value.state_transition, value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count, value.accepted), True, "runtime summary fields", "summary mirrors runtime values"),
        _finding(7, "manifest_replay", (value.manifest.runtime_id, value.manifest.diff_id, value.manifest.version, value.manifest.boundary, value.manifest.files) == (value.runtime_id, value.diff_id, runtime_model.VERSION, runtime_model.BOUNDARY, runtime_model.FILES), value.manifest.files, runtime_model.FILES, "manifest identity and exact artifact set replay"),
        _finding(8, "disposition_replay", (value.state, value.release_ready) == (("ready", True) if all(x.passed for x in value.checks) and value.accepted else ("blocked", False)), (value.state, value.release_ready), "all checks pass and source is accepted => ready", "readiness requires the complete gate to pass"),
        _finding(9, "direction_link", direction_link, value.direction, diff.direction if diff is not None else value.summary.direction, "direction links to the compared histories"),
        _finding(10, "transition_link", transition_link, value.state_transition, diff.state_transition if diff is not None else value.summary.state_transition, "latest-state transition links to the diff"),
        _finding(11, "comparison_link", comparison_link, (value.item_count, value.added_count, value.removed_count, value.changed_count, value.unchanged_count), (diff.item_count, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count) if diff is not None else "retained comparison counters", "comparison counters and acceptance link to source diff"),
        _finding(12, "check_addresses", all(runtime_model.address_check(x) == x.content_address for x in value.checks) and runtime_model.address_checks(value.checks) == value.manifest.artifact_addresses[0], True, "replayed check addresses", "check component addresses are canonical"),
        _finding(13, "address_integrity", value.summary.diff_address == value.diff_address and policy.diff_id == value.diff_id and runtime_model.address_policy(policy) == policy.content_address, True, (value.diff_address, policy.diff_id, policy.content_address), "policy and comparison addresses are retained"),
        _finding(14, "public_boundary", _public(value.to_dict()), True, "public value", "runtime contains no local paths or private records"),
        _finding(15, "canonical_runtime", canonical_json(value.to_dict()) == canonical_json(runtime_model.runtime_from_mapping(_strict_json_loads(runtime_model.runtime_json(value))).to_dict()), True, "canonical round-trip", "runtime serialization is deterministic and strict"),
    )
    result = RuntimeAudit(value.runtime_id, value.diff_id, value.content_address, checks, len(checks), sum(x.passed for x in checks), sum(not x.passed for x in checks), all(x.passed for x in checks), f"pending:{AUDIT_PREFIX}")
    return _seal(result, address_audit)

def verify_audit(value: RuntimeAudit) -> RuntimeAudit:
    if not isinstance(value, RuntimeAudit): raise ValidationError("D493 verification requires a typed audit")
    value._validate(); return value
def audit_from_mapping(value: Mapping[str, Any]) -> RuntimeAudit: return RuntimeAudit.from_mapping(value)
def audit_json(value: RuntimeAudit) -> str: return canonical_json(verify_audit(value).to_dict())
def audit_csv(value: RuntimeAudit) -> str:
    output = io.StringIO(); writer = csv.DictWriter(output, fieldnames=CHECK_FIELDS, lineterminator="\n"); writer.writeheader(); writer.writerows(x.to_dict() for x in verify_audit(value).checks); return output.getvalue()
def render_audit_markdown(value: RuntimeAudit) -> str:
    value = verify_audit(value); lines = [f"# D493 runtime audit {value.runtime_id}", "", f"- Accepted: {str(value.accepted).lower()}", f"- Checks: {value.passed_count}/{value.check_count}", "", "| Check | Passed | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| {x.check_id} | {str(x.passed).lower()} | {x.detail} |" for x in value.checks); return "\n".join(lines) + "\n"
def check_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeAuditCheck", "type": "object", "additionalProperties": False, "required": list(CHECK_FIELDS), "properties": {f: {"type": "integer" if f == "ordinal" else "boolean" if f == "passed" else "string"} for f in CHECK_FIELDS}}
def audit_schema() -> dict[str, Any]: return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "LedgerDiffRuntimeAudit", "type": "object", "additionalProperties": False, "required": list(AUDIT_FIELDS), "properties": {f: {"type": "array" if f == "checks" else "integer" if f.endswith("count") else "boolean" if f == "accepted" else "string"} for f in AUDIT_FIELDS}}
def capabilities() -> dict[str, Any]: return {"public": True, "value_free": True, "version": VERSION, "boundary": BOUNDARY, "check_ids": CHECK_IDS, "max_checks": MAX_CHECKS, "features": ("independent policy replay", "optional exact diff lineage verification", "canonical check-address verification", "JSON CSV and Markdown projections"), "public_boundary": {"source_paths": False, "source_records": False, "payload_bytes": False, "private_metadata": False}}

__all__ = ["VERSION", "BOUNDARY", "AUDIT_PREFIX", "CHECK_PREFIX", "CHECK_IDS", "CHECK_FIELDS", "AUDIT_FIELDS", "MAX_CHECKS", "AuditCheck", "RuntimeAudit", "address_check", "address_audit", "audit_runtime", "verify_audit", "audit_from_mapping", "audit_json", "audit_csv", "render_audit_markdown", "check_schema", "audit_schema", "capabilities"]
