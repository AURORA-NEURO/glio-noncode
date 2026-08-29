"""Independent audit of observatory archive registry history documents.

The typed history model is strict and fail-fast. This companion boundary is
operator-facing: it accepts a public mapping, evaluates a fixed set of
sequence, linkage, conservation, and integrity checks, and returns a complete
or incomplete report without discarding diagnostics at the first malformed
field. It never records input paths, private attribution, timestamps,
ownership metadata, or language metadata in its public report.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

from collections.abc import Mapping, Sequence
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry as registry_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history_model
from . import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff_model
from .errors import ValidationError
from .serialization import canonical_json, content_hash


VERSION = history_model.VERSION + "-audit-v1"
BOUNDARY = history_model.BOUNDARY + "_audit"
AUDIT_PREFIX = history_model.HISTORY_PREFIX + "-audit"
AUDIT_CHECK_PREFIX = AUDIT_PREFIX + "-check"
STATES = ("complete", "incomplete")
CHECK_IDS = (
    "exact-fields",
    "public-boundary",
    "source-addresses",
    "snapshot-identities",
    "transition-identities",
    "adjacency",
    "endpoint-linkage",
    "state-conservation",
    "count-conservation",
    "registry-field-order",
    "nested-addresses",
    "content-address",
    "mapping-round-trip",
)
MAX_CHECKS = len(CHECK_IDS)
EXPECTED_FIELDS = (
    "history_id",
    "version",
    "boundary",
    "snapshot_count",
    "transition_count",
    "start_registry_address",
    "end_registry_address",
    "snapshots",
    "transitions",
    "state_counts",
    "accepted",
    "content_address",
)


def _text(value: Any, field: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a non-empty string of at most {maximum} characters")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its declared bound")
    return value


def _safe_count(value: Any, maximum: int) -> int:
    try:
        return _count(value, "history audit count", maximum)
    except ValidationError:
        return 0


def _address(value: Any, field: str, prefix: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(("/", "\\")) or "\\" in value or not value.startswith(prefix + ":"):
        raise ValidationError(f"{field} has an invalid public namespace")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be a mapping")
    return value


def _sequence(value: Any, field: str, maximum: int) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence) or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded sequence")
    return tuple(value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unsupported fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    return history_model._public(value)


def _safe_address(value: Any, prefix: str, fallback: str) -> str:
    try:
        return _address(value, "history audit evidence address", prefix)
    except ValidationError:
        return fallback


def _safe_text(value: Any, fallback: str) -> str:
    try:
        return _text(value, "history audit history ID")
    except ValidationError:
        return fallback


def _typed(value: Mapping[str, Any]) -> history_model.RegistryHistory | None:
    try:
        return history_model.history_from_mapping(value)
    except (ValidationError, KeyError, TypeError, ValueError):
        return None


class RegistryHistoryAuditCheck:
    """One independently addressed assertion over a history document."""

    def __init__(self, check_id: str, passed: bool, detail: str, evidence_address: str) -> None:
        self.check_id = _text(check_id, "registry history audit check ID", 128)
        self.passed = _bool(passed, "registry history audit check passed")
        self.detail = _text(detail, "registry history audit check detail", 1024)
        self.evidence_address = _text(evidence_address, "registry history audit evidence address", 2048)
        self.content_address = content_hash(
            {
                "check_id": self.check_id,
                "passed": self.passed,
                "detail": self.detail,
                "evidence_address": self.evidence_address,
            },
            prefix=AUDIT_CHECK_PREFIX,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "detail": self.detail,
            "evidence_address": self.evidence_address,
            "content_address": self.content_address,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> RegistryHistoryAuditCheck:
        value = _mapping(value, "registry history audit check")
        _strict(value, {"check_id", "passed", "detail", "evidence_address", "content_address"}, "registry history audit check")
        result = cls(value["check_id"], value["passed"], value["detail"], value["evidence_address"])
        if result.content_address != value["content_address"]:
            raise ValidationError("registry history audit check content address mismatch")
        return result


class RegistryHistoryAudit:
    """Public complete or incomplete report for a registry history mapping."""

    def __init__(
        self,
        history_id: str,
        history_address: str,
        start_registry_address: str,
        end_registry_address: str,
        state: str,
        complete: bool,
        accepted: bool,
        snapshot_count: int,
        transition_count: int,
        checks: Sequence[RegistryHistoryAuditCheck],
        content_address: str,
    ) -> None:
        self.history_id = history_id
        self.history_address = history_address
        self.start_registry_address = start_registry_address
        self.end_registry_address = end_registry_address
        self.state = state
        self.complete = complete
        self.accepted = accepted
        self.snapshot_count = snapshot_count
        self.transition_count = transition_count
        self.checks = tuple(checks)
        self.check_count = len(self.checks)
        self.passed_count = sum(check.passed for check in self.checks)
        self.failed_count = self.check_count - self.passed_count
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.history_id, "registry history audit history ID")
        _address(self.history_address, "registry history audit history address", history_model.HISTORY_PREFIX)
        _address(self.start_registry_address, "registry history audit start address", registry_model.REGISTRY_PREFIX)
        _address(self.end_registry_address, "registry history audit end address", registry_model.REGISTRY_PREFIX)
        if self.state not in STATES or self.complete != (self.state == "complete"):
            raise ValidationError("registry history audit state does not match completion")
        _bool(self.complete, "registry history audit complete")
        _bool(self.accepted, "registry history audit accepted")
        _count(self.snapshot_count, "registry history audit snapshot count", history_model.MAX_SNAPSHOTS)
        _count(self.transition_count, "registry history audit transition count", history_model.MAX_TRANSITIONS)
        if tuple(check.check_id for check in self.checks) != CHECK_IDS or self.check_count != MAX_CHECKS:
            raise ValidationError("registry history audit check set is invalid")
        _count(self.passed_count, "registry history audit passed count", MAX_CHECKS)
        _count(self.failed_count, "registry history audit failed count", MAX_CHECKS)
        if self.passed_count + self.failed_count != self.check_count or self.passed_count != sum(check.passed for check in self.checks):
            raise ValidationError("registry history audit counts are not conserved")
        if self.complete != (self.failed_count == 0) or self.accepted != self.complete:
            raise ValidationError("registry history audit acceptance does not match checks")
        if self.content_address.startswith("pending:"):
            _text(self.content_address, "registry history audit content address")
        else:
            _address(self.content_address, "registry history audit content address", AUDIT_PREFIX)
        if not _public(self.to_dict()) or (not self.content_address.startswith("pending:") and address_audit(self) != self.content_address):
            raise ValidationError("registry history audit address or public boundary is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_id": self.history_id,
            "history_address": self.history_address,
            "start_registry_address": self.start_registry_address,
            "end_registry_address": self.end_registry_address,
            "state": self.state,
            "complete": self.complete,
            "accepted": self.accepted,
            "snapshot_count": self.snapshot_count,
            "transition_count": self.transition_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": tuple(check.to_dict() for check in self.checks),
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        return {key: self.to_dict()[key] for key in ("history_id", "history_address", "start_registry_address", "end_registry_address", "state", "complete", "accepted", "snapshot_count", "transition_count", "check_count", "passed_count", "failed_count", "content_address")}


def address_audit(value: RegistryHistoryAudit) -> str:
    if not isinstance(value, RegistryHistoryAudit):
        raise ValidationError("registry history audit address requires a typed audit")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=AUDIT_PREFIX)


def _check(check_id: str, passed: bool, detail: str, evidence: str) -> RegistryHistoryAuditCheck:
    return RegistryHistoryAuditCheck(check_id, passed, detail, evidence)


def _audit_mapping(document: Mapping[str, Any]) -> RegistryHistoryAudit:
    fallback_history = history_model.HISTORY_PREFIX + ":unresolved"
    fallback_registry = registry_model.REGISTRY_PREFIX + ":unresolved"
    history_address = _safe_address(document.get("content_address"), history_model.HISTORY_PREFIX, fallback_history)
    history_id = _safe_text(document.get("history_id"), "unresolved-history")
    start_address = _safe_address(document.get("start_registry_address"), registry_model.REGISTRY_PREFIX, fallback_registry)
    end_address = _safe_address(document.get("end_registry_address"), registry_model.REGISTRY_PREFIX, fallback_registry)
    typed = _typed(document)
    if typed is not None:
        history_address = typed.content_address
        history_id = typed.history_id
        start_address = typed.start_registry_address
        end_address = typed.end_registry_address

    # Keep the expected field comparison explicit so audit behavior is stable
    # even if the typed model gains helper attributes in a future release.
    exact_fields = set(document) == set(EXPECTED_HISTORY_FIELDS)
    public_boundary = _public(document)
    source_addresses = False
    if typed is not None:
        try:
            _address(typed.start_registry_address, "start registry address", registry_model.REGISTRY_PREFIX)
            _address(typed.end_registry_address, "end registry address", registry_model.REGISTRY_PREFIX)
            source_addresses = all(
                _address(snapshot.registry_address, "snapshot registry address", registry_model.REGISTRY_PREFIX)
                and _address(snapshot.verification_address, "snapshot verification address", registry_model.REGISTRY_VERIFICATION_PREFIX)
                for snapshot in typed.snapshots
            ) and all(
                _address(transition.baseline_registry_address, "transition baseline registry address", registry_model.REGISTRY_PREFIX)
                and _address(transition.candidate_registry_address, "transition candidate registry address", registry_model.REGISTRY_PREFIX)
                and _address(transition.diff_address, "transition diff address", diff_model.DIFF_PREFIX)
                for transition in typed.transitions
            )
        except ValidationError:
            source_addresses = False

    snapshot_identities = False
    transition_identities = False
    adjacency = False
    endpoint_linkage = False
    state_conservation = False
    count_conservation = False
    registry_field_order = False
    nested_addresses = False
    content_address = False
    mapping_round_trip = False
    if typed is not None:
        snapshot_identities = (
            tuple(item.ordinal for item in typed.snapshots) == tuple(range(1, typed.snapshot_count + 1))
            and len({item.snapshot_address for item in typed.snapshots}) == typed.snapshot_count
            and len({item.registry_address for item in typed.snapshots}) <= typed.snapshot_count
        )
        transition_identities = (
            tuple(item.ordinal for item in typed.transitions) == tuple(range(1, typed.transition_count + 1))
            and len({item.transition_address for item in typed.transitions}) == typed.transition_count
            and len({item.diff_address for item in typed.transitions}) == typed.transition_count
        )
        adjacency = all(
            transition.baseline_ordinal == transition.ordinal and transition.candidate_ordinal == transition.ordinal + 1
            for transition in typed.transitions
        ) and typed.transition_count == typed.snapshot_count - 1
        endpoint_linkage = (
            typed.start_registry_address == typed.snapshots[0].registry_address
            and typed.end_registry_address == typed.snapshots[-1].registry_address
            and all(
                transition.baseline_registry_address == typed.snapshots[transition.baseline_ordinal - 1].registry_address
                and transition.candidate_registry_address == typed.snapshots[transition.candidate_ordinal - 1].registry_address
                for transition in typed.transitions
            )
        )
        state_conservation = (
            typed.state_counts == {state: sum(item.state == state for item in typed.transitions) for state in history_model.STATES}
            and sum(typed.state_counts.values()) == typed.transition_count
        )
        count_conservation = all(
            transition.item_count == transition.added_count + transition.removed_count + transition.changed_count + transition.unchanged_count
            and transition.item_count <= diff_model.MAX_DIFF_ITEMS
            for transition in typed.transitions
        )
        registry_field_order = all(
            tuple(field for field in diff_model.REGISTRY_FIELDS if field in transition.registry_changed_fields) == transition.registry_changed_fields
            and len(set(transition.registry_changed_fields)) == len(transition.registry_changed_fields)
            for transition in typed.transitions
        )
        nested_addresses = (
            all(history_model.address_snapshot(snapshot) == snapshot.snapshot_address for snapshot in typed.snapshots)
            and all(history_model.address_transition(transition) == transition.transition_address for transition in typed.transitions)
        )
        content_address = history_model.address_history(typed) == typed.content_address
        try:
            mapping_round_trip = history_model.history_from_mapping(typed.to_dict()).to_dict() == typed.to_dict()
        except (ValidationError, KeyError, TypeError, ValueError):
            mapping_round_trip = False

    checks = (
        _check("exact-fields", exact_fields, "history document contains exactly the declared public fields", history_address),
        _check("public-boundary", public_boundary, "history document contains no private, path, attribution, ownership, or language metadata", history_address),
        _check("source-addresses", source_addresses, "registry, verification, and transition source addresses use public namespaces", history_address),
        _check("snapshot-identities", snapshot_identities, "snapshot ordinals and snapshot addresses are ordered and unique", history_address),
        _check("transition-identities", transition_identities, "transition ordinals and diff addresses are ordered and unique", history_address),
        _check("adjacency", adjacency, "each transition joins exactly two neighboring snapshots", history_address),
        _check("endpoint-linkage", endpoint_linkage, "history endpoints and transition registry endpoints link to snapshots", history_address),
        _check("state-conservation", state_conservation, "transition state counts conserve the history sequence", history_address),
        _check("count-conservation", count_conservation, "each transition action count conserves its item count", history_address),
        _check("registry-field-order", registry_field_order, "transition registry fields use the canonical declared order", history_address),
        _check("nested-addresses", nested_addresses, "snapshot and transition content addresses reproduce", history_address),
        _check("content-address", content_address, "history content address reproduces from its public projection", history_address),
        _check("mapping-round-trip", mapping_round_trip, "typed public mapping rehydrates without projection drift", history_address),
    )
    complete = all(check.passed for check in checks)
    body = {
        "history_id": history_id,
        "history_address": history_address,
        "start_registry_address": start_address,
        "end_registry_address": end_address,
        "state": "complete" if complete else "incomplete",
        "complete": complete,
        "accepted": complete,
        "snapshot_count": typed.snapshot_count if typed is not None else _safe_count(document.get("snapshot_count", 0), history_model.MAX_SNAPSHOTS),
        "transition_count": typed.transition_count if typed is not None else _safe_count(document.get("transition_count", 0), history_model.MAX_TRANSITIONS),
        "checks": checks,
    }
    provisional = RegistryHistoryAudit(**body, content_address="pending:audit")
    return RegistryHistoryAudit(**body, content_address=address_audit(provisional))


# Kept as a separate constant so the public audit check cannot accidentally
# inherit implementation-only names from the typed model.
EXPECTED_HISTORY_FIELDS = EXPECTED_FIELDS


def audit_history(value: history_model.RegistryHistory) -> RegistryHistoryAudit:
    if not isinstance(value, history_model.RegistryHistory):
        raise ValidationError("registry history audit requires a typed history")
    history_model.verify_history(value)
    return _audit_mapping(value.to_dict())


def audit_from_mapping(value: Mapping[str, Any]) -> RegistryHistoryAudit:
    value = _mapping(value, "registry history audit input")
    if "history_address" in value and "checks" in value:
        _strict(
            value,
            {
                "history_id",
                "history_address",
                "start_registry_address",
                "end_registry_address",
                "state",
                "complete",
                "accepted",
                "snapshot_count",
                "transition_count",
                "check_count",
                "passed_count",
                "failed_count",
                "checks",
                "content_address",
            },
            "registry history audit",
        )
        checks_value = value["checks"]
        checks = tuple(RegistryHistoryAuditCheck.from_mapping(item) for item in checks_value.values()) if isinstance(checks_value, Mapping) else tuple(RegistryHistoryAuditCheck.from_mapping(item) for item in checks_value)
        result = RegistryHistoryAudit(
            value["history_id"],
            value["history_address"],
            value["start_registry_address"],
            value["end_registry_address"],
            value["state"],
            value["complete"],
            value["accepted"],
            value["snapshot_count"],
            value["transition_count"],
            checks,
            value["content_address"],
        )
        if result.check_count != value["check_count"] or result.passed_count != value["passed_count"] or result.failed_count != value["failed_count"]:
            raise ValidationError("registry history audit derived counts are not conserved")
        return result
    return _audit_mapping(value)


def audit_json(value: RegistryHistoryAudit) -> str:
    verify_audit(value)
    return canonical_json(value.to_dict())


def verify_audit(value: RegistryHistoryAudit) -> RegistryHistoryAudit:
    if not isinstance(value, RegistryHistoryAudit):
        raise ValidationError("registry history audit verification requires a typed audit")
    value._validate()
    return value


def render_audit_markdown(value: RegistryHistoryAudit) -> str:
    verify_audit(value)
    lines = [
        "# Assurance History Observatory Archive Registry History Audit",
        "",
        f"- History ID: `{value.history_id}`",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- History: `{value.history_address}`",
        f"- Snapshots: `{value.snapshot_count}`",
        f"- Transitions: `{value.transition_count}`",
        f"- Checks: `{value.passed_count}` passed, `{value.failed_count}` failed",
        f"- Content address: `{value.content_address}`",
        "",
        "| Check | Passed | Detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| `{check.check_id}` | `{str(check.passed).lower()}` | {check.detail} |" for check in value.checks)
    return "\n".join(lines) + "\n"


def check_schema() -> dict[str, Any]:
    fields = {
        "check_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "passed": {"type": "boolean"},
        "detail": {"type": "string", "minLength": 1, "maxLength": 1024},
        "evidence_address": {"type": "string"},
        "content_address": {"type": "string", "pattern": "^" + AUDIT_CHECK_PREFIX + ":"},
    }
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def audit_schema() -> dict[str, Any]:
    fields = {
        "history_id": {"type": "string"},
        "history_address": {"type": "string", "pattern": "^" + history_model.HISTORY_PREFIX + ":"},
        "start_registry_address": {"type": "string"},
        "end_registry_address": {"type": "string"},
        "state": {"type": "string", "enum": list(STATES)},
        "complete": {"type": "boolean"},
        "accepted": {"type": "boolean"},
        "snapshot_count": {"type": "integer", "minimum": 0, "maximum": history_model.MAX_SNAPSHOTS},
        "transition_count": {"type": "integer", "minimum": 0, "maximum": history_model.MAX_TRANSITIONS},
        "check_count": {"type": "integer", "minimum": MAX_CHECKS, "maximum": MAX_CHECKS},
        "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
        "failed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS},
        "checks": {"type": "array", "minItems": MAX_CHECKS, "maxItems": MAX_CHECKS, "items": check_schema()},
        "content_address": {"type": "string", "pattern": "^" + AUDIT_PREFIX + ":"},
    }
    return {"type": "object", "additionalProperties": False, "required": list(fields), "properties": fields}


def capabilities() -> dict[str, Any]:
    return {
        "version": VERSION,
        "boundary": BOUNDARY,
        "checks": CHECK_IDS,
        "states": STATES,
        "limits": {"max_checks": MAX_CHECKS, "max_snapshots": history_model.MAX_SNAPSHOTS, "max_transitions": history_model.MAX_TRANSITIONS},
        "features": (
            "public mapping audit",
            "fixed sequence and linkage check set",
            "snapshot and transition identity checks",
            "endpoint and adjacency verification",
            "state and action count conservation",
            "nested address replay",
            "content-address replay",
            "incomplete tamper diagnostics",
            "path-free JSON and Markdown projection",
        ),
        "schemas": ("check", "audit"),
    }


__all__ = [
    "AUDIT_CHECK_PREFIX",
    "AUDIT_PREFIX",
    "BOUNDARY",
    "CHECK_IDS",
    "EXPECTED_FIELDS",
    "MAX_CHECKS",
    "STATES",
    "VERSION",
    "RegistryHistoryAudit",
    "RegistryHistoryAuditCheck",
    "address_audit",
    "audit_from_mapping",
    "audit_history",
    "audit_json",
    "audit_schema",
    "capabilities",
    "check_schema",
    "render_audit_markdown",
    "verify_audit",
]
