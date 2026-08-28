"""Independently assure the release-registry federation review decision ledger.

The review ledger is an operational record, not a self-authenticating release
decision.  This boundary recomputes its important invariants without trusting
the ledger's own validator as the source of truth.  It produces a portable,
public, path-free assurance report and a second release gate.  The source
review queue remains authoritative: resolving a warning locally cannot turn a
source gate that was not ready into a promotable release.

The durable assurance bundle contains exactly ``manifest.json``,
``assurance.json``, and ``gate.json``.  Assurance diffs contain exactly
``manifest.json`` and ``diff.json``.  All JSON is canonical and all records are
content addressed.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import assurance_history_series_release_registry_federation_gate_review as decision_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

FederationReviewDecisionLedger = decision_model.FederationReviewDecisionLedger
FederationReviewItem = decision_model.FederationReviewItem
FederationReviewDecision = decision_model.FederationReviewDecision
FederationReviewReplayItem = decision_model.FederationReviewReplayItem

VERSION = decision_model.VERSION + "-assurance-v1"
BOUNDARY = "public_release_registry_federation_gate_review_decision_ledger_assurance"
ASSURANCE_PREFIX = decision_model.LEDGER_PREFIX + "-assurance"
FINDING_PREFIX = ASSURANCE_PREFIX + "-finding"
GATE_PREFIX = ASSURANCE_PREFIX + "-gate"
CHECK_PREFIX = GATE_PREFIX + "-check"
QUERY_PREFIX = ASSURANCE_PREFIX + "-query"
MANIFEST_PREFIX = ASSURANCE_PREFIX + "-manifest"
DIFF_PREFIX = ASSURANCE_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
DIFF_QUERY_PREFIX = DIFF_PREFIX + "-query"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"

MANIFEST_NAME = "manifest.json"
ASSURANCE_NAME = "assurance.json"
GATE_NAME = "gate.json"
DIFF_NAME = "diff.json"
FILES = (MANIFEST_NAME, ASSURANCE_NAME, GATE_NAME)
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)

DEFAULT_ASSURANCE_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance"
DEFAULT_GATE_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance-gate"
DEFAULT_DIFF_ID = "glio-noncode-release-registry-federation-gate-review-decision-ledger-assurance-diff"
MAX_FINDINGS = 32
MAX_CHECKS = 32
MAX_DIFF_ITEMS = MAX_FINDINGS + MAX_CHECKS
MAX_QUERY_ITEMS = 4096
DEFAULT_LIMIT = 50

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class AssuranceSeverity(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BLOCKER = "blocker"


class AssuranceState(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class GateState(StrEnum):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"


class AssurancePlane(StrEnum):
    LEDGER = "ledger"
    QUEUE = "queue"
    ENTRIES = "entries"
    POLICY = "policy"
    REPLAY = "replay"
    SOURCE = "source"
    PUBLIC = "public"
    PERSISTENCE = "persistence"


class DiffAction(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class DiffState(StrEnum):
    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 2048)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    return None if value is None else _address(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0) or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _mapping_sequence(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return tuple(_mapping(item, field) for item in value)


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _enum(value: Any, field: str, enum_type: type[StrEnum]) -> str:
    value = _text(value, field, 64)
    if value not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is invalid")
    return value


def _severity(value: Any, field: str = "assurance severity") -> str:
    return _enum(value, field, AssuranceSeverity)


def _state(value: Any, field: str = "assurance state") -> str:
    return _enum(value, field, AssuranceState)


def _gate_state(value: Any, field: str = "gate state") -> str:
    return _enum(value, field, GateState)


def _plane(value: Any, field: str = "assurance plane") -> str:
    return _enum(value, field, AssurancePlane)


def _diff_action(value: Any, field: str = "diff action") -> str:
    return _enum(value, field, DiffAction)


class DecisionLedgerAssuranceFinding:
    """One independently recomputed invariant of a review decision ledger."""

    def __init__(self, ordinal: int, finding_id: str, plane: str, kind: str, severity: str, required: bool, passed: bool, detail: str, remediation: str, evidence_address: str, content_address: str) -> None:
        self.ordinal, self.finding_id, self.plane, self.kind = ordinal, finding_id, plane, kind
        self.severity, self.required, self.passed = severity, required, passed
        self.detail, self.remediation, self.evidence_address = detail, remediation, evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "assurance finding ordinal", MAX_FINDINGS - 1)
        _text(self.finding_id, "assurance finding ID", 256)
        _plane(self.plane)
        _text(self.kind, "assurance finding kind", 128)
        severity = _severity(self.severity)
        _bool(self.required, "assurance finding required")
        _bool(self.passed, "assurance finding passed")
        if self.passed and severity != AssuranceSeverity.PASS.value:
            raise ValidationError("passed assurance findings must have pass severity")
        if not self.passed and severity == AssuranceSeverity.PASS.value:
            raise ValidationError("failed assurance findings cannot have pass severity")
        if not self.passed and self.required and severity != AssuranceSeverity.BLOCKER.value:
            raise ValidationError("required failed assurance findings must be blockers")
        if not self.passed and not self.required and severity != AssuranceSeverity.WARNING.value:
            raise ValidationError("optional failed assurance findings must be warnings")
        _text(self.detail, "assurance finding detail", 2048)
        _text(self.remediation, "assurance finding remediation", 2048)
        _address(self.evidence_address, "assurance finding evidence address")
        _address(self.content_address, "assurance finding address")
        if not self.content_address.startswith("pending:") and address_finding(self) != self.content_address:
            raise ValidationError("assurance finding address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "finding_id": self.finding_id, "plane": self.plane, "kind": self.kind, "severity": self.severity, "required": self.required, "passed": self.passed, "detail": self.detail, "remediation": self.remediation, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_finding(value: DecisionLedgerAssuranceFinding) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=FINDING_PREFIX)


class DecisionLedgerAssurance:
    """Addressed independent finding report for one decision ledger."""

    def __init__(self, assurance_id: str, version: str, boundary: str, ledger_id: str, ledger_address: str, queue_address: str, finding_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, findings: Sequence[DecisionLedgerAssuranceFinding], content_address: str) -> None:
        self.assurance_id, self.version, self.boundary = assurance_id, version, boundary
        self.ledger_id, self.ledger_address, self.queue_address = ledger_id, ledger_address, queue_address
        self.finding_count, self.passed_count = finding_count, passed_count
        self.warning_count, self.blocker_count = warning_count, blocker_count
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.findings, self.content_address = tuple(findings), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "assurance ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision ledger assurance contract is invalid")
        _text(self.ledger_id, "assurance ledger ID", 256)
        _address(self.ledger_address, "assurance ledger address")
        _address(self.queue_address, "assurance queue address")
        _count(self.finding_count, "assurance finding count", MAX_FINDINGS, positive=True)
        if self.finding_count != len(self.findings):
            raise ValidationError("assurance finding count is not conserved")
        for count, field in ((self.passed_count, "passed count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count")):
            _count(count, f"assurance {field}", MAX_FINDINGS)
        if self.passed_count + self.warning_count + self.blocker_count != self.finding_count:
            raise ValidationError("assurance severity counts are not conserved")
        for ordinal, finding in enumerate(self.findings):
            if not isinstance(finding, DecisionLedgerAssuranceFinding) or finding.ordinal != ordinal:
                raise ValidationError("assurance finding ordinals are not contiguous")
            if address_finding(finding) != finding.content_address:
                raise ValidationError("assurance finding address mismatch")
        expected = AssuranceState.BLOCKED.value if self.blocker_count else AssuranceState.WARNING.value if self.warning_count else AssuranceState.PASSED.value
        if self.state != expected or self.accepted != (self.blocker_count == 0) or self.release_ready != (self.state == AssuranceState.PASSED.value):
            raise ValidationError("assurance state or readiness is invalid")
        _address(self.content_address, "assurance address")
        if not self.content_address.startswith("pending:") and address_assurance(self) != self.content_address:
            raise ValidationError("assurance address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"assurance_id": self.assurance_id, "version": self.version, "boundary": self.boundary, "ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "queue_address": self.queue_address, "finding_count": self.finding_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [finding.to_dict() for finding in self.findings]
        return body


def address_assurance(value: DecisionLedgerAssurance) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ASSURANCE_PREFIX)


class DecisionLedgerGateCheck:
    """One independent release-gate check over the ledger and assurance."""

    def __init__(self, ordinal: int, check_id: str, plane: str, kind: str, required: bool, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal, self.check_id, self.plane, self.kind = ordinal, check_id, plane, kind
        self.required, self.passed, self.detail = required, passed, detail
        self.evidence_address, self.content_address = evidence_address, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "gate check ordinal", MAX_CHECKS - 1)
        _text(self.check_id, "gate check ID", 256)
        _plane(self.plane)
        _text(self.kind, "gate check kind", 128)
        _bool(self.required, "gate check required")
        _bool(self.passed, "gate check passed")
        _text(self.detail, "gate check detail", 2048)
        _address(self.evidence_address, "gate check evidence address")
        _address(self.content_address, "gate check address")
        if not self.content_address.startswith("pending:") and address_check(self) != self.content_address:
            raise ValidationError("gate check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "plane": self.plane, "kind": self.kind, "required": self.required, "passed": self.passed, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_check(value: DecisionLedgerGateCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DecisionLedgerReleaseGate:
    """Second-stage promote, hold, or block decision."""

    def __init__(self, gate_id: str, version: str, boundary: str, ledger_id: str, ledger_address: str, assurance_address: str, source_accepted: bool, source_release_ready: bool, check_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, checks: Sequence[DecisionLedgerGateCheck], content_address: str) -> None:
        self.gate_id, self.version, self.boundary = gate_id, version, boundary
        self.ledger_id, self.ledger_address, self.assurance_address = ledger_id, ledger_address, assurance_address
        self.source_accepted, self.source_release_ready = source_accepted, source_release_ready
        self.check_count, self.passed_count, self.warning_count, self.blocker_count = check_count, passed_count, warning_count, blocker_count
        self.state, self.accepted, self.release_ready = state, accepted, release_ready
        self.checks, self.content_address = tuple(checks), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "gate ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("decision ledger gate contract is invalid")
        _text(self.ledger_id, "gate ledger ID", 256)
        _address(self.ledger_address, "gate ledger address")
        _address(self.assurance_address, "gate assurance address")
        _bool(self.source_accepted, "gate source accepted")
        _bool(self.source_release_ready, "gate source release-ready")
        _count(self.check_count, "gate check count", MAX_CHECKS, positive=True)
        if self.check_count != len(self.checks):
            raise ValidationError("gate check count is not conserved")
        for count, field in ((self.passed_count, "passed count"), (self.warning_count, "warning count"), (self.blocker_count, "blocker count")):
            _count(count, f"gate {field}", MAX_CHECKS)
        if self.passed_count + self.warning_count + self.blocker_count != self.check_count:
            raise ValidationError("gate result counts are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionLedgerGateCheck) or check.ordinal != ordinal or address_check(check) != check.content_address:
                raise ValidationError("gate checks are invalid")
        required_failures = sum(not check.passed and check.required for check in self.checks)
        optional_failures = sum(not check.passed and not check.required for check in self.checks)
        expected = GateState.BLOCK.value if required_failures else GateState.HOLD.value if optional_failures else GateState.PROMOTE.value
        if self.state != expected or self.accepted != (required_failures == 0) or self.release_ready != (self.state == GateState.PROMOTE.value):
            raise ValidationError("gate state or readiness is invalid")
        _address(self.content_address, "gate address")
        if not self.content_address.startswith("pending:") and address_gate(self) != self.content_address:
            raise ValidationError("gate address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("decision ledger gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"gate_id": self.gate_id, "version": self.version, "boundary": self.boundary, "ledger_id": self.ledger_id, "ledger_address": self.ledger_address, "assurance_address": self.assurance_address, "source_accepted": self.source_accepted, "source_release_ready": self.source_release_ready, "check_count": self.check_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [check.to_dict() for check in self.checks]
        return body


def address_gate(value: DecisionLedgerReleaseGate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=GATE_PREFIX)


class DecisionLedgerAssuranceGate:
    """Assurance report plus its independent release gate."""

    def __init__(self, assurance: DecisionLedgerAssurance, gate: DecisionLedgerReleaseGate, content_address: str) -> None:
        self.assurance, self.gate, self.content_address = assurance, gate, content_address
        self._validate()

    def _validate(self) -> None:
        verify_assurance(self.assurance)
        verify_gate(self.gate)
        if self.gate.assurance_address != self.assurance.content_address or self.gate.ledger_address != self.assurance.ledger_address or self.gate.ledger_id != self.assurance.ledger_id:
            raise ValidationError("assurance and gate linkage is invalid")
        _address(self.content_address, "assurance gate address")
        if not self.content_address.startswith("pending:") and address_assurance_gate(self) != self.content_address:
            raise ValidationError("assurance gate address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"assurance": self.assurance.summary(), "gate": self.gate.summary(), "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return {"assurance": self.assurance.to_dict(), "gate": self.gate.to_dict(), "content_address": self.content_address}


def address_assurance_gate(value: DecisionLedgerAssuranceGate) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=ASSURANCE_PREFIX + "-gate-bundle")


def _safe(operation: Callable[[], bool]) -> bool:
    try:
        return bool(operation())
    except Exception:
        return False


def _item_by_id(ledger: FederationReviewDecisionLedger) -> dict[str, FederationReviewItem]:
    return {item.item_id: item for item in ledger.items}


def _expected_counters(ledger: FederationReviewDecisionLedger) -> dict[str, int]:
    return {action.value: sum(entry.action == action.value for entry in ledger.entries) for action in decision_model.ReviewAction}


def _next_state(item: FederationReviewItem, current: str, action: str, evidence_address: str) -> str:
    """Independent copy of the transition policy used for assurance replay."""
    if action == decision_model.ReviewAction.ACKNOWLEDGE.value:
        if current in {decision_model.ReviewItemState.CLEAR.value, decision_model.ReviewItemState.RESOLVED.value, decision_model.ReviewItemState.WAIVED.value}:
            raise ValidationError("acknowledge requires an open item")
        return decision_model.ReviewItemState.ACKNOWLEDGED.value
    if action == decision_model.ReviewAction.REMEDIATE.value:
        if evidence_address == decision_model.NO_EVIDENCE or current in {decision_model.ReviewItemState.CLEAR.value, decision_model.ReviewItemState.RESOLVED.value, decision_model.ReviewItemState.WAIVED.value}:
            raise ValidationError("remediation policy failed")
        return decision_model.ReviewItemState.RESOLVED.value
    if action == decision_model.ReviewAction.WAIVE.value:
        if item.required or evidence_address == decision_model.NO_EVIDENCE or current in {decision_model.ReviewItemState.CLEAR.value, decision_model.ReviewItemState.RESOLVED.value, decision_model.ReviewItemState.WAIVED.value}:
            raise ValidationError("waiver policy failed")
        return decision_model.ReviewItemState.WAIVED.value
    if action == decision_model.ReviewAction.ESCALATE.value:
        if current in {decision_model.ReviewItemState.CLEAR.value, decision_model.ReviewItemState.RESOLVED.value, decision_model.ReviewItemState.WAIVED.value}:
            raise ValidationError("escalation policy failed")
        return decision_model.ReviewItemState.ESCALATED.value
    if action == decision_model.ReviewAction.REOPEN.value:
        if current not in {decision_model.ReviewItemState.ACKNOWLEDGED.value, decision_model.ReviewItemState.RESOLVED.value, decision_model.ReviewItemState.WAIVED.value, decision_model.ReviewItemState.ESCALATED.value}:
            raise ValidationError("reopen policy failed")
        return decision_model.ReviewItemState.BLOCKED.value if item.required else decision_model.ReviewItemState.OPEN.value
    raise ValidationError("unknown decision action")


def _replay_states(ledger: FederationReviewDecisionLedger) -> tuple[dict[str, Any], ...]:
    items = [{"ordinal": item.ordinal, "item_id": item.item_id, "item_address": item.content_address, "initial_state": item.state, "state": item.state, "last_action": None, "last_decision_address": None} for item in ledger.items]
    by_id = {item["item_id"]: item for item in items}
    source_items = _item_by_id(ledger)
    for entry in ledger.entries:
        current = by_id.get(entry.item_id)
        source = source_items.get(entry.item_id)
        if current is None or source is None or current["item_address"] != entry.item_address:
            raise ValidationError("replay item linkage failed")
        current["state"] = _next_state(source, current["state"], entry.action, entry.evidence_address)
        current["last_action"] = entry.action
        current["last_decision_address"] = entry.content_address
    return tuple(items)


def _replay_summary(ledger: FederationReviewDecisionLedger, states: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {state.value: sum(item["state"] == state.value for item in states) for state in decision_model.ReviewItemState}
    source_accepted = ledger.replay.source_accepted
    source_ready = ledger.replay.source_release_ready
    active = any(item["state"] in {decision_model.ReviewItemState.OPEN.value, decision_model.ReviewItemState.ACKNOWLEDGED.value, decision_model.ReviewItemState.ESCALATED.value} for item in states)
    state = decision_model.ReviewQueueState.BLOCKED.value if not source_accepted or counts[decision_model.ReviewItemState.BLOCKED.value] else decision_model.ReviewQueueState.REVIEW.value if not source_ready or active else decision_model.ReviewQueueState.CLEAR.value
    return {"queue_address": ledger.queue_address, "gate_address": ledger.gate_address, "source_accepted": source_accepted, "source_release_ready": source_ready, "entry_count": len(ledger.entries), "item_count": len(states), "clear_count": counts[decision_model.ReviewItemState.CLEAR.value], "open_count": counts[decision_model.ReviewItemState.OPEN.value], "blocked_count": counts[decision_model.ReviewItemState.BLOCKED.value], "acknowledged_count": counts[decision_model.ReviewItemState.ACKNOWLEDGED.value], "resolved_count": counts[decision_model.ReviewItemState.RESOLVED.value], "waived_count": counts[decision_model.ReviewItemState.WAIVED.value], "escalated_count": counts[decision_model.ReviewItemState.ESCALATED.value], "state": state, "accepted": source_accepted, "release_ready": source_ready and state == decision_model.ReviewQueueState.CLEAR.value}


def _check_finding(ordinal: int, ledger: FederationReviewDecisionLedger, kind: str, plane: str, passed: bool, required: bool, detail: str, remediation: str) -> DecisionLedgerAssuranceFinding:
    body = {"ordinal": ordinal, "finding_id": f"{ledger.ledger_id}:assurance:{ordinal}", "plane": plane, "kind": kind, "severity": AssuranceSeverity.PASS.value if passed else AssuranceSeverity.BLOCKER.value if required else AssuranceSeverity.WARNING.value, "required": required, "passed": passed, "detail": detail, "remediation": remediation, "evidence_address": ledger.content_address}
    provisional = DecisionLedgerAssuranceFinding(**body, content_address="pending:finding")
    return DecisionLedgerAssuranceFinding(**body, content_address=address_finding(provisional))


def build_assurance(ledger: FederationReviewDecisionLedger, *, assurance_id: str = DEFAULT_ASSURANCE_ID) -> DecisionLedgerAssurance:
    if not isinstance(ledger, FederationReviewDecisionLedger):
        raise ValidationError("decision ledger assurance requires a typed ledger")
    items = tuple(ledger.items)
    entries = tuple(ledger.entries)
    item_ids = {getattr(item, "item_id", None) for item in items}
    item_addresses = {getattr(item, "content_address", None) for item in items}
    expected = _expected_counters(ledger)
    findings = [
        _check_finding(0, ledger, "ledger-address", AssurancePlane.LEDGER.value, _safe(lambda: decision_model.address_ledger(ledger) == ledger.content_address), True, "ledger content address recomputes from its public projection", "rebuild the ledger with canonical content addressing"),
        _check_finding(1, ledger, "ledger-contract", AssurancePlane.LEDGER.value, _safe(lambda: ledger.version == decision_model.VERSION and ledger.boundary == decision_model.BOUNDARY and ledger.entry_count == len(entries)), True, "ledger version, boundary, and entry count are conserved", "restore the current decision-ledger contract and counts"),
        _check_finding(2, ledger, "queue-linkage", AssurancePlane.QUEUE.value, _safe(lambda: bool(ledger.queue_address and ledger.gate_address and ledger.assurance_address and ledger.replay.queue_address == ledger.queue_address and ledger.replay.gate_address == ledger.gate_address and ledger.entry_count == len(entries))), True, "queue, source gate, source assurance, and replay links are retained", "restore source addresses and the frozen queue relationship"),
        _check_finding(3, ledger, "item-addresses", AssurancePlane.QUEUE.value, _safe(lambda: all(decision_model.address_review_item(item) == item.content_address for item in items) and len(item_ids) == len(items) and len(item_addresses) == len(items)), True, "every frozen review item has a unique recomputed address", "regenerate the immutable queue-item snapshot"),
        _check_finding(4, ledger, "entry-chain", AssurancePlane.ENTRIES.value, _safe(lambda: all(entry.ordinal == ordinal and decision_model.address_decision(entry) == entry.content_address and entry.previous_address == (decision_model.INITIAL_HEAD if ordinal == 0 else entries[ordinal - 1].content_address) for ordinal, entry in enumerate(entries)) and ledger.head_address == (decision_model.INITIAL_HEAD if not entries else entries[-1].content_address)), True, "decision addresses, ordinals, previous heads, and terminal head form one chain", "repair the append-only entry ancestry"),
        _check_finding(5, ledger, "entry-item-linkage", AssurancePlane.ENTRIES.value, _safe(lambda: all(entry.item_id in item_ids and entry.item_address in item_addresses and next(item for item in items if item.item_id == entry.item_id).content_address == entry.item_address for entry in entries)), True, "each decision targets exactly one retained item identity", "append decisions only against the frozen item snapshot"),
        _check_finding(6, ledger, "action-counters", AssurancePlane.LEDGER.value, _safe(lambda: ledger.acknowledge_count == expected[decision_model.ReviewAction.ACKNOWLEDGE.value] and ledger.remediate_count == expected[decision_model.ReviewAction.REMEDIATE.value] and ledger.waive_count == expected[decision_model.ReviewAction.WAIVE.value] and ledger.escalate_count == expected[decision_model.ReviewAction.ESCALATE.value] and ledger.reopen_count == expected[decision_model.ReviewAction.REOPEN.value] and ledger.entry_count == sum(expected.values())), True, "action counters equal the append-only entry sequence", "recompute action counters from the canonical entries"),
        _check_finding(7, ledger, "evidence-policy", AssurancePlane.POLICY.value, _safe(lambda: all((entry.action in {decision_model.ReviewAction.REMEDIATE.value, decision_model.ReviewAction.WAIVE.value}) == (entry.evidence_address != decision_model.NO_EVIDENCE) for entry in entries)), True, "remediation and waiver decisions carry evidence while other actions do not", "apply the evidence policy before appending a decision"),
        _check_finding(8, ledger, "transition-policy", AssurancePlane.POLICY.value, _safe(lambda: _transition_policy_passes(ledger)), True, "every action is legal for the preceding replay state", "replay and correct invalid action transitions"),
        _check_finding(9, ledger, "replay-projection", AssurancePlane.REPLAY.value, _safe(lambda: _replay_policy_passes(ledger)), True, "independent replay reproduces item states, counts, and readiness", "recompute the replay projection from entries"),
        _check_finding(10, ledger, "source-authority", AssurancePlane.SOURCE.value, _safe(lambda: ledger.accepted == ledger.replay.source_accepted and ledger.release_ready == ledger.replay.source_release_ready and ledger.replay.accepted == ledger.replay.source_accepted), True, "ledger acceptance preserves source acceptance and cannot override source readiness", "use a verified source gate for promotion"),
        _check_finding(11, ledger, "closure-readiness", AssurancePlane.POLICY.value, _safe(lambda: ledger.release_ready == (ledger.replay.source_release_ready and ledger.state == decision_model.ReviewQueueState.CLEAR.value)), False, "promotion requires both source readiness and a clear replay state", "resolve active review states or supply a ready source gate"),
        _check_finding(12, ledger, "public-boundary", AssurancePlane.PUBLIC.value, _safe(lambda: _public(ledger.to_dict())), True, "ledger projections contain no private identity or language attributes", "remove forbidden metadata from the public projection"),
        _check_finding(13, ledger, "replay-addresses", AssurancePlane.REPLAY.value, _safe(lambda: all(decision_model.address_replay_item(item) == item.content_address for item in ledger.replay.items) and decision_model.address_replay(ledger.replay) == ledger.replay.content_address), True, "replay item and replay snapshot addresses recompute", "regenerate replay content addresses"),
    ]
    passed = sum(item.passed for item in findings)
    warnings = sum(not item.passed and not item.required for item in findings)
    blockers = sum(not item.passed and item.required for item in findings)
    state = AssuranceState.BLOCKED.value if blockers else AssuranceState.WARNING.value if warnings else AssuranceState.PASSED.value
    body = {"assurance_id": _text(assurance_id, "assurance ID", 256), "version": VERSION, "boundary": BOUNDARY, "ledger_id": ledger.ledger_id, "ledger_address": ledger.content_address, "queue_address": ledger.queue_address, "finding_count": len(findings), "passed_count": passed, "warning_count": warnings, "blocker_count": blockers, "state": state, "accepted": blockers == 0, "release_ready": state == AssuranceState.PASSED.value, "findings": tuple(findings)}
    provisional = DecisionLedgerAssurance(**body, content_address="pending:assurance")
    body["content_address"] = address_assurance(provisional)
    return DecisionLedgerAssurance(**body)


def _transition_policy_passes(ledger: FederationReviewDecisionLedger) -> bool:
    states = {item.item_id: item.state for item in ledger.items}
    items = _item_by_id(ledger)
    for entry in ledger.entries:
        item = items.get(entry.item_id)
        if item is None or item.content_address != entry.item_address:
            return False
        states[entry.item_id] = _next_state(item, states[entry.item_id], entry.action, entry.evidence_address)
    return True


def _replay_policy_passes(ledger: FederationReviewDecisionLedger) -> bool:
    states = _replay_states(ledger)
    expected = _replay_summary(ledger, states)
    replay = ledger.replay
    actual = replay.summary()
    if any(actual.get(key) != value for key, value in expected.items()):
        return False
    actual_rows = tuple(item.to_dict() | {"content_address": None} for item in replay.items)
    expected_rows = tuple(item | {"content_address": None} for item in states)
    return actual_rows == expected_rows


def _check_gate(ordinal: int, gate_id: str, kind: str, plane: str, passed: bool, required: bool, detail: str, evidence_address: str) -> DecisionLedgerGateCheck:
    body = {"ordinal": ordinal, "check_id": f"{gate_id}:check:{ordinal}", "plane": plane, "kind": kind, "required": required, "passed": passed, "detail": detail, "evidence_address": evidence_address}
    provisional = DecisionLedgerGateCheck(**body, content_address="pending:check")
    return DecisionLedgerGateCheck(**body, content_address=address_check(provisional))


def build_gate(ledger: FederationReviewDecisionLedger, assurance: DecisionLedgerAssurance, *, gate_id: str = DEFAULT_GATE_ID) -> DecisionLedgerReleaseGate:
    if not isinstance(ledger, FederationReviewDecisionLedger) or not isinstance(assurance, DecisionLedgerAssurance):
        raise ValidationError("decision ledger gate requires typed ledger and assurance")
    verify_assurance(assurance)
    checks = (
        _check_gate(0, gate_id, "assurance-accepted", AssurancePlane.LEDGER.value, assurance.accepted, True, "independent assurance has no blocker findings", assurance.content_address),
        _check_gate(1, gate_id, "assurance-release-ready", AssurancePlane.LEDGER.value, assurance.release_ready, True, "independent assurance is warning-free", assurance.content_address),
        _check_gate(2, gate_id, "source-accepted", AssurancePlane.SOURCE.value, ledger.replay.source_accepted, True, "source gate acceptance remains authoritative", ledger.content_address),
        _check_gate(3, gate_id, "source-release-ready", AssurancePlane.SOURCE.value, ledger.replay.source_release_ready, False, "source gate readiness is required for promotion", ledger.content_address),
        _check_gate(4, gate_id, "ledger-clear", AssurancePlane.REPLAY.value, ledger.state == decision_model.ReviewQueueState.CLEAR.value, False, "ledger replay has no active review state", ledger.replay.content_address),
        _check_gate(5, gate_id, "no-open-items", AssurancePlane.REPLAY.value, ledger.replay.open_count == 0 and ledger.replay.acknowledged_count == 0, False, "no item remains open or acknowledged", ledger.replay.content_address),
        _check_gate(6, gate_id, "no-blocked-items", AssurancePlane.REPLAY.value, ledger.replay.blocked_count == 0, True, "no required blocker remains in replay", ledger.replay.content_address),
        _check_gate(7, gate_id, "no-escalated-items", AssurancePlane.REPLAY.value, ledger.replay.escalated_count == 0, False, "no item remains escalated", ledger.replay.content_address),
        _check_gate(8, gate_id, "head-continuity", AssurancePlane.ENTRIES.value, ledger.head_address == (decision_model.INITIAL_HEAD if not ledger.entries else ledger.entries[-1].content_address), True, "decision head is terminal and continuous", ledger.content_address),
        _check_gate(9, gate_id, "public-boundary", AssurancePlane.PUBLIC.value, _public(ledger.to_dict()) and _public(assurance.to_dict()), True, "ledger and assurance are public projections", assurance.content_address),
    )
    passed = sum(item.passed for item in checks)
    warnings = sum(not item.passed and not item.required for item in checks)
    blockers = sum(not item.passed and item.required for item in checks)
    state = GateState.BLOCK.value if blockers else GateState.HOLD.value if warnings else GateState.PROMOTE.value
    body = {"gate_id": _text(gate_id, "gate ID", 256), "version": VERSION, "boundary": BOUNDARY, "ledger_id": ledger.ledger_id, "ledger_address": ledger.content_address, "assurance_address": assurance.content_address, "source_accepted": ledger.replay.source_accepted, "source_release_ready": ledger.replay.source_release_ready, "check_count": len(checks), "passed_count": passed, "warning_count": warnings, "blocker_count": blockers, "state": state, "accepted": blockers == 0, "release_ready": state == GateState.PROMOTE.value, "checks": checks}
    provisional = DecisionLedgerReleaseGate(**body, content_address="pending:gate")
    body["content_address"] = address_gate(provisional)
    return DecisionLedgerReleaseGate(**body)


def build_assurance_gate(ledger: FederationReviewDecisionLedger, *, assurance_id: str = DEFAULT_ASSURANCE_ID, gate_id: str = DEFAULT_GATE_ID) -> DecisionLedgerAssuranceGate:
    assurance = build_assurance(ledger, assurance_id=assurance_id)
    gate = build_gate(ledger, assurance, gate_id=gate_id)
    provisional = DecisionLedgerAssuranceGate(assurance, gate, "pending:bundle")
    return DecisionLedgerAssuranceGate(assurance, gate, address_assurance_gate(provisional))


def build_assurance_gate_from_directory(directory: str | Path, *, assurance_id: str = DEFAULT_ASSURANCE_ID, gate_id: str = DEFAULT_GATE_ID) -> DecisionLedgerAssuranceGate:
    return build_assurance_gate(decision_model.load_decision_ledger(directory), assurance_id=assurance_id, gate_id=gate_id)


def verify_assurance(value: DecisionLedgerAssurance) -> DecisionLedgerAssurance:
    if not isinstance(value, DecisionLedgerAssurance):
        raise ValidationError("assurance verification requires a typed assurance")
    value._validate()
    return value


def verify_gate(value: DecisionLedgerReleaseGate) -> DecisionLedgerReleaseGate:
    if not isinstance(value, DecisionLedgerReleaseGate):
        raise ValidationError("gate verification requires a typed gate")
    value._validate()
    return value


def verify_assurance_gate(value: DecisionLedgerAssuranceGate) -> DecisionLedgerAssuranceGate:
    if not isinstance(value, DecisionLedgerAssuranceGate):
        raise ValidationError("assurance gate verification requires a typed bundle")
    value._validate()
    return value


def verify_assurance_gate_against_ledger(value: DecisionLedgerAssuranceGate, ledger: FederationReviewDecisionLedger) -> DecisionLedgerAssuranceGate:
    """Prove that a persisted assurance gate belongs to one exact ledger."""
    verify_assurance_gate(value)
    if not isinstance(ledger, FederationReviewDecisionLedger):
        raise ValidationError("assurance comparison requires a typed ledger")
    if value.gate.ledger_id != ledger.ledger_id or value.gate.ledger_address != ledger.content_address:
        raise ValidationError("assurance gate does not reference the supplied ledger")
    expected = build_assurance_gate(ledger, assurance_id=value.assurance.assurance_id, gate_id=value.gate.gate_id)
    if value.assurance.to_dict() != expected.assurance.to_dict() or value.gate.to_dict() != expected.gate.to_dict() or value.content_address != expected.content_address:
        raise ValidationError("assurance gate projection does not match the supplied ledger")
    return value


def finding_from_mapping(value: Mapping[str, Any]) -> DecisionLedgerAssuranceFinding:
    body = dict(_mapping(value, "assurance finding"))
    fields = {"ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address"}
    _strict(body, fields, "assurance finding")
    if set(body) != fields:
        raise ValidationError("assurance finding is missing required fields")
    return DecisionLedgerAssuranceFinding(**body)


def assurance_from_mapping(value: Mapping[str, Any]) -> DecisionLedgerAssurance:
    body = dict(_mapping(value, "decision ledger assurance"))
    fields = {"assurance_id", "version", "boundary", "ledger_id", "ledger_address", "queue_address", "finding_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "findings", "content_address"}
    _strict(body, fields, "decision ledger assurance")
    findings = tuple(finding_from_mapping(item) for item in _mapping_sequence(body.pop("findings"), "assurance findings"))
    return verify_assurance(DecisionLedgerAssurance(**body, findings=findings))


def check_from_mapping(value: Mapping[str, Any]) -> DecisionLedgerGateCheck:
    body = dict(_mapping(value, "gate check"))
    fields = {"ordinal", "check_id", "plane", "kind", "required", "passed", "detail", "evidence_address", "content_address"}
    _strict(body, fields, "gate check")
    if set(body) != fields:
        raise ValidationError("gate check is missing required fields")
    return DecisionLedgerGateCheck(**body)


def gate_from_mapping(value: Mapping[str, Any]) -> DecisionLedgerReleaseGate:
    body = dict(_mapping(value, "decision ledger gate"))
    fields = {"gate_id", "version", "boundary", "ledger_id", "ledger_address", "assurance_address", "source_accepted", "source_release_ready", "check_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "checks", "content_address"}
    _strict(body, fields, "decision ledger gate")
    checks = tuple(check_from_mapping(item) for item in _mapping_sequence(body.pop("checks"), "gate checks"))
    return verify_gate(DecisionLedgerReleaseGate(**body, checks=checks))


def assurance_gate_from_mapping(value: Mapping[str, Any]) -> DecisionLedgerAssuranceGate:
    body = dict(_mapping(value, "decision ledger assurance gate"))
    _strict(body, {"assurance", "gate", "content_address"}, "decision ledger assurance gate")
    assurance = assurance_from_mapping(_mapping(body.pop("assurance"), "assurance"))
    gate = gate_from_mapping(_mapping(body.pop("gate"), "gate"))
    return verify_assurance_gate(DecisionLedgerAssuranceGate(assurance, gate, **body))


class AssuranceQuery:
    RESOURCES = ("summary", "findings", "blockers", "warnings", "checks", "failed")

    def __init__(self, resource: str = "summary", *, severity: str | None = None, passed: bool | None = None, required: bool | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "assurance query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("assurance query resource is invalid")
        self.severity = _severity(severity) if severity is not None else None
        self.passed = _bool(passed, "assurance query passed") if passed is not None else None
        self.required = _bool(required, "assurance query required") if required is not None else None
        self.plane = _plane(plane, "assurance query plane") if plane is not None else None
        self.text = _text(text, "assurance query text", 256).casefold() if text is not None else None
        self.offset, self.limit = _count(offset, "assurance query offset"), _count(limit, "assurance query limit", positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("assurance query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "severity": self.severity, "passed": self.passed, "required": self.required, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


class AssuranceQueryResult:
    def __init__(self, query: AssuranceQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query, self.total_count = query, _count(total_count, "assurance query total count")
        self.items, self.returned_count = tuple(dict(item) for item in items), len(items)
        _count(self.returned_count, "assurance query returned count")
        if self.returned_count > self.total_count:
            raise ValidationError("assurance query returned more records than matched")
        self.source_address = _address(source_address, "assurance query source address")
        self.content_address = "pending:query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=QUERY_PREFIX + "-result")
        if not _public(self.to_dict()):
            raise ValidationError("assurance query crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _matches(record: Mapping[str, Any], query: AssuranceQuery) -> bool:
    return (query.severity is None or record.get("severity") == query.severity) and (query.passed is None or record.get("passed") == query.passed) and (query.required is None or record.get("required") == query.required) and (query.plane is None or record.get("plane") == query.plane) and (query.text is None or query.text in canonical_json(record).casefold())


def query_assurance(value: DecisionLedgerAssuranceGate, query: AssuranceQuery | None = None, **kwargs: Any) -> AssuranceQueryResult:
    verify_assurance_gate(value)
    selected = query if query is not None else AssuranceQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records = (value.assurance.summary() | {"gate_state": value.gate.state, "gate_release_ready": value.gate.release_ready},)
    elif selected.resource in {"findings", "blockers", "warnings", "failed"}:
        records = tuple(item.to_dict() for item in value.assurance.findings)
        if selected.resource == "blockers":
            records = tuple(item for item in records if item["severity"] == AssuranceSeverity.BLOCKER.value)
        elif selected.resource == "warnings":
            records = tuple(item for item in records if item["severity"] == AssuranceSeverity.WARNING.value)
        elif selected.resource == "failed":
            records = tuple(item for item in records if not item["passed"])
    else:
        records = tuple(item.to_dict() for item in value.gate.checks)
    matched = tuple(item for item in records if _matches(item, selected))
    return AssuranceQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


class DiffItem:
    """Stable semantic comparison of one assurance finding or gate check."""

    def __init__(self, ordinal: int, action: str, key: str, plane: str, kind: str, baseline_severity: str | None, candidate_severity: str | None, baseline_required: bool | None, candidate_required: bool | None, baseline_passed: bool | None, candidate_passed: bool | None, baseline_address: str | None, candidate_address: str | None, detail: str, content_address: str) -> None:
        self.ordinal, self.action, self.key, self.plane, self.kind = ordinal, action, key, plane, kind
        self.baseline_severity, self.candidate_severity = baseline_severity, candidate_severity
        self.baseline_required, self.candidate_required = baseline_required, candidate_required
        self.baseline_passed, self.candidate_passed = baseline_passed, candidate_passed
        self.baseline_address, self.candidate_address = baseline_address, candidate_address
        self.detail, self.content_address = detail, content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "diff item ordinal", MAX_DIFF_ITEMS - 1)
        _diff_action(self.action)
        _text(self.key, "diff item key", 256)
        _plane(self.plane, "diff item plane")
        _text(self.kind, "diff item kind", 128)
        for item, field in ((self.baseline_severity, "baseline severity"), (self.candidate_severity, "candidate severity")):
            if item is not None:
                _severity(item, field)
        for item, field in ((self.baseline_required, "baseline required"), (self.candidate_required, "candidate required"), (self.baseline_passed, "baseline passed"), (self.candidate_passed, "candidate passed")):
            if item is not None:
                _bool(item, field)
        for item, field in ((self.baseline_address, "baseline address"), (self.candidate_address, "candidate address")):
            if item is not None:
                _address(item, field)
        _text(self.detail, "diff item detail", 2048)
        _address(self.content_address, "diff item address")
        if self.action == DiffAction.ADDED.value and self.candidate_address is None or self.action == DiffAction.REMOVED.value and self.baseline_address is None or self.action in {DiffAction.UNCHANGED.value, DiffAction.CHANGED.value} and (self.baseline_address is None or self.candidate_address is None):
            raise ValidationError("diff item does not carry the required snapshot addresses")
        if not _public(self.to_dict()):
            raise ValidationError("diff item crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "action": self.action, "key": self.key, "plane": self.plane, "kind": self.kind, "baseline_severity": self.baseline_severity, "candidate_severity": self.candidate_severity, "baseline_required": self.baseline_required, "candidate_required": self.candidate_required, "baseline_passed": self.baseline_passed, "candidate_passed": self.candidate_passed, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "detail": self.detail, "content_address": self.content_address}


def address_diff_item(value: DiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class AssuranceDiff:
    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, baseline_ledger_address: str, candidate_ledger_address: str, baseline_state: str, candidate_state: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state: str, items: Sequence[DiffItem], content_address: str) -> None:
        self.diff_id, self.version, self.boundary = diff_id, version, boundary
        self.baseline_address, self.candidate_address = baseline_address, candidate_address
        self.baseline_ledger_address, self.candidate_ledger_address = baseline_ledger_address, candidate_ledger_address
        self.baseline_state, self.candidate_state = baseline_state, candidate_state
        self.item_count, self.added_count, self.removed_count = item_count, added_count, removed_count
        self.unchanged_count, self.changed_count = unchanged_count, changed_count
        self.improved_count, self.regressed_count = improved_count, regressed_count
        self.state, self.items, self.content_address = state, tuple(items), content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("assurance diff contract is invalid")
        for item, field in ((self.baseline_address, "baseline address"), (self.candidate_address, "candidate address"), (self.baseline_ledger_address, "baseline ledger address"), (self.candidate_ledger_address, "candidate ledger address")):
            _address(item, field)
        _state(self.baseline_state, "baseline state")
        _state(self.candidate_state, "candidate state")
        _count(self.item_count, "diff item count", MAX_DIFF_ITEMS)
        if self.item_count != len(self.items):
            raise ValidationError("diff item count is not conserved")
        counters = {action.value: 0 for action in DiffAction}
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, DiffItem) or item.ordinal != ordinal or address_diff_item(item) != item.content_address:
                raise ValidationError("diff items are invalid")
            counters[item.action] += 1
        if (self.added_count, self.removed_count, self.unchanged_count, self.changed_count) != tuple(counters[item.value] for item in DiffAction):
            raise ValidationError("diff action counts are not conserved")
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count")):
            _count(count, f"diff {field}", MAX_DIFF_ITEMS)
        if self.improved_count + self.regressed_count > self.item_count:
            raise ValidationError("diff outcome counts exceed item count")
        expected = DiffState.UNCHANGED.value if not self.items or all(item.action == DiffAction.UNCHANGED.value for item in self.items) else DiffState.IMPROVED.value if self.improved_count and not self.regressed_count else DiffState.REGRESSED.value if self.regressed_count and not self.improved_count else DiffState.CHANGED.value
        if self.state != expected:
            raise ValidationError("diff state is invalid")
        _address(self.content_address, "diff address")
        if not self.content_address.startswith("pending:") and address_diff(self) != self.content_address:
            raise ValidationError("diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("assurance diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "baseline_ledger_address": self.baseline_ledger_address, "candidate_ledger_address": self.candidate_ledger_address, "baseline_state": self.baseline_state, "candidate_state": self.candidate_state, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state": self.state, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_diff(value: AssuranceDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _records(value: DecisionLedgerAssuranceGate) -> dict[str, Mapping[str, Any]]:
    records: dict[str, Mapping[str, Any]] = {}
    for finding in value.assurance.findings:
        key = f"assurance:{finding.plane}:{finding.kind}"
        records[key] = {"plane": finding.plane, "kind": finding.kind, "severity": finding.severity, "required": finding.required, "passed": finding.passed, "address": finding.content_address}
    for check in value.gate.checks:
        key = f"gate:{check.plane}:{check.kind}"
        records[key] = {"plane": check.plane, "kind": check.kind, "severity": AssuranceSeverity.PASS.value if check.passed else AssuranceSeverity.BLOCKER.value if check.required else AssuranceSeverity.WARNING.value, "required": check.required, "passed": check.passed, "address": check.content_address}
    return records


def _score(record: Mapping[str, Any] | None) -> int | None:
    if record is None:
        return None
    if record.get("passed") is True:
        return 2
    return 0 if record.get("required") is True or record.get("severity") == AssuranceSeverity.BLOCKER.value else 1


def _diff_item(ordinal: int, key: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> tuple[DiffItem, int, int]:
    source = candidate or baseline
    if source is None:
        raise ValidationError("diff item has no snapshot source")
    if baseline is None:
        action, detail = DiffAction.ADDED.value, "record appears in the candidate assurance gate"
    elif candidate is None:
        action, detail = DiffAction.REMOVED.value, "record is absent from the candidate assurance gate"
    else:
        left = tuple(baseline.get(field) for field in ("plane", "kind", "severity", "required", "passed"))
        right = tuple(candidate.get(field) for field in ("plane", "kind", "severity", "required", "passed"))
        action, detail = (DiffAction.UNCHANGED.value, "record is unchanged") if left == right else (DiffAction.CHANGED.value, "record severity, requirement, or pass state changed")
    body = {"ordinal": ordinal, "action": action, "key": key, "plane": source["plane"], "kind": source["kind"], "baseline_severity": baseline.get("severity") if baseline else None, "candidate_severity": candidate.get("severity") if candidate else None, "baseline_required": baseline.get("required") if baseline else None, "candidate_required": candidate.get("required") if candidate else None, "baseline_passed": baseline.get("passed") if baseline else None, "candidate_passed": candidate.get("passed") if candidate else None, "baseline_address": baseline.get("address") if baseline else None, "candidate_address": candidate.get("address") if candidate else None, "detail": detail}
    provisional = DiffItem(**body, content_address="pending:diff-item")
    item = DiffItem(**body, content_address=address_diff_item(provisional))
    before, after = _score(baseline), _score(candidate)
    improved = int((before is None and after is not None and after > 0) or (before is not None and after is None and before == 0) or (before is not None and after is not None and after > before))
    regressed = int((before is None and after == 0) or (before is not None and after is None and before > 0) or (before is not None and after is not None and after < before))
    return item, improved, regressed


def build_diff(baseline: DecisionLedgerAssuranceGate, candidate: DecisionLedgerAssuranceGate, *, diff_id: str = DEFAULT_DIFF_ID) -> AssuranceDiff:
    verify_assurance_gate(baseline)
    verify_assurance_gate(candidate)
    left, right = _records(baseline), _records(candidate)
    items, improved, regressed = [], 0, 0
    for ordinal, key in enumerate(sorted(set(left) | set(right))):
        item, item_improved, item_regressed = _diff_item(ordinal, key, left.get(key), right.get(key))
        items.append(item)
        improved += item_improved
        regressed += item_regressed
    counts = {action.value: sum(item.action == action.value for item in items) for action in DiffAction}
    state = DiffState.UNCHANGED.value if not items or all(item.action == DiffAction.UNCHANGED.value for item in items) else DiffState.IMPROVED.value if improved and not regressed else DiffState.REGRESSED.value if regressed and not improved else DiffState.CHANGED.value
    body = {"diff_id": _text(diff_id, "diff ID", 256), "version": VERSION, "boundary": BOUNDARY, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "baseline_ledger_address": baseline.gate.ledger_address, "candidate_ledger_address": candidate.gate.ledger_address, "baseline_state": baseline.assurance.state, "candidate_state": candidate.assurance.state, "item_count": len(items), "added_count": counts[DiffAction.ADDED.value], "removed_count": counts[DiffAction.REMOVED.value], "unchanged_count": counts[DiffAction.UNCHANGED.value], "changed_count": counts[DiffAction.CHANGED.value], "improved_count": improved, "regressed_count": regressed, "state": state, "items": tuple(items)}
    provisional = AssuranceDiff(**body, content_address="pending:diff")
    body["content_address"] = address_diff(provisional)
    return AssuranceDiff(**body)


def verify_diff(value: AssuranceDiff) -> AssuranceDiff:
    if not isinstance(value, AssuranceDiff):
        raise ValidationError("diff verification requires a typed diff")
    value._validate()
    return value


def diff_item_from_mapping(value: Mapping[str, Any]) -> DiffItem:
    body = dict(_mapping(value, "assurance diff item"))
    fields = {"ordinal", "action", "key", "plane", "kind", "baseline_severity", "candidate_severity", "baseline_required", "candidate_required", "baseline_passed", "candidate_passed", "baseline_address", "candidate_address", "detail", "content_address"}
    _strict(body, fields, "assurance diff item")
    return DiffItem(**body)


def diff_from_mapping(value: Mapping[str, Any]) -> AssuranceDiff:
    body = dict(_mapping(value, "assurance diff"))
    fields = {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "baseline_ledger_address", "candidate_ledger_address", "baseline_state", "candidate_state", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "items", "content_address"}
    _strict(body, fields, "assurance diff")
    items = tuple(diff_item_from_mapping(item) for item in _mapping_sequence(body.pop("items"), "assurance diff items"))
    return verify_diff(AssuranceDiff(**body, items=items))


class DiffQuery:
    RESOURCES = ("summary", "actions", "added", "removed", "changed", "unchanged", "improved", "regressed")

    def __init__(self, resource: str = "summary", *, action: str | None = None, plane: str | None = None, text: str | None = None, offset: int = 0, limit: int = DEFAULT_LIMIT) -> None:
        self.resource = _text(resource, "diff query resource", 64)
        if self.resource not in self.RESOURCES:
            raise ValidationError("diff query resource is invalid")
        self.action = _diff_action(action, "diff query action") if action is not None else None
        self.plane = _plane(plane, "diff query plane") if plane is not None else None
        self.text = _text(text, "diff query text", 256).casefold() if text is not None else None
        self.offset, self.limit = _count(offset, "diff query offset"), _count(limit, "diff query limit", positive=True)
        if self.offset + self.limit > MAX_QUERY_ITEMS:
            raise ValidationError("diff query window is too large")

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "action": self.action, "plane": self.plane, "text": self.text, "offset": self.offset, "limit": self.limit}


class DiffQueryResult:
    def __init__(self, query: DiffQuery, total_count: int, items: Sequence[Mapping[str, Any]], source_address: str) -> None:
        self.query, self.total_count = query, _count(total_count, "diff query total count")
        self.items, self.returned_count = tuple(dict(item) for item in items), len(items)
        _count(self.returned_count, "diff query returned count")
        if self.returned_count > self.total_count:
            raise ValidationError("diff query returned more records than matched")
        self.source_address = _address(source_address, "diff query source address")
        self.content_address = "pending:diff-query"
        self.content_address = content_hash(self.to_dict() | {"content_address": None}, prefix=DIFF_QUERY_PREFIX + "-result")

    def to_dict(self) -> dict[str, Any]:
        return {"query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "source_address": self.source_address, "content_address": self.content_address}


def _outcome(item: Mapping[str, Any]) -> str | None:
    before, after = _score({"passed": item.get("baseline_passed"), "required": item.get("baseline_required"), "severity": item.get("baseline_severity")}) if item.get("baseline_address") else None, _score({"passed": item.get("candidate_passed"), "required": item.get("candidate_required"), "severity": item.get("candidate_severity")}) if item.get("candidate_address") else None
    if before is None and after is None or before == after:
        return None
    if before is None:
        return "improved" if after and after > 0 else "regressed"
    if after is None:
        return "improved" if before == 0 else "regressed"
    return "improved" if after > before else "regressed"


def query_diff(value: AssuranceDiff, query: DiffQuery | None = None, **kwargs: Any) -> DiffQueryResult:
    verify_diff(value)
    selected = query if query is not None else DiffQuery(**kwargs)
    if query is not None and kwargs:
        raise ValidationError("query object and keyword filters cannot be combined")
    if selected.resource == "summary":
        records = (value.summary(),)
    else:
        records = tuple(item.to_dict() for item in value.items)
        if selected.resource in {item.value for item in DiffAction}:
            records = tuple(item for item in records if item["action"] == selected.resource)
        elif selected.resource in {"improved", "regressed"}:
            records = tuple(item for item in records if _outcome(item) == selected.resource)
    matched = tuple(item for item in records if (selected.action is None or item.get("action") == selected.action) and (selected.plane is None or item.get("plane") == selected.plane) and (selected.text is None or selected.text in canonical_json(item).casefold()))
    return DiffQueryResult(selected, len(matched), matched[selected.offset : selected.offset + selected.limit], value.content_address)


def assurance_json(value: DecisionLedgerAssurance) -> str:
    verify_assurance(value)
    return canonical_json(value.to_dict())


def gate_json(value: DecisionLedgerReleaseGate) -> str:
    verify_gate(value)
    return canonical_json(value.to_dict())


def assurance_gate_json(value: DecisionLedgerAssuranceGate) -> str:
    verify_assurance_gate(value)
    return canonical_json(value.to_dict())


def query_json(value: AssuranceQueryResult) -> str:
    return canonical_json(value.to_dict())


def diff_json(value: AssuranceDiff) -> str:
    verify_diff(value)
    return canonical_json(value.to_dict())


def diff_query_json(value: DiffQueryResult) -> str:
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field) for field in fields} for row in rows)
    return output.getvalue()


def assurance_csv(value: DecisionLedgerAssurance) -> str:
    verify_assurance(value)
    return _csv_text([item.to_dict() for item in value.findings], ("ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address"))


def gate_csv(value: DecisionLedgerReleaseGate) -> str:
    verify_gate(value)
    return _csv_text([item.to_dict() for item in value.checks], ("ordinal", "check_id", "plane", "kind", "required", "passed", "detail", "evidence_address", "content_address"))


def query_csv(value: AssuranceQueryResult) -> str:
    return _csv_text(value.items, tuple(sorted({key for item in value.items for key in item}))) if value.items else ""


def diff_csv(value: AssuranceDiff) -> str:
    verify_diff(value)
    return _csv_text([item.to_dict() for item in value.items], ("ordinal", "action", "key", "plane", "kind", "baseline_severity", "candidate_severity", "baseline_required", "candidate_required", "baseline_passed", "candidate_passed", "baseline_address", "candidate_address", "detail", "content_address"))


def diff_query_csv(value: DiffQueryResult) -> str:
    return _csv_text(value.items, tuple(sorted({key for item in value.items for key in item}))) if value.items else ""


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    lines.extend(f"- {key}: `{summary[key]}`" for key in sorted(summary))
    lines.extend(["", "## Records", ""])
    if not rows:
        lines.append("No records.")
        return "\n".join(lines) + "\n"
    fields = tuple(sorted({key for row in rows for key in row}))
    lines.extend(("| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
    lines.extend("| " + " | ".join(str(row.get(field, "")).replace("|", "\\|").replace("\n", " ") for field in fields) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def render_assurance_markdown(value: DecisionLedgerAssurance) -> str:
    verify_assurance(value)
    return _markdown("Release-Registry Review Decision Ledger Assurance", value.summary(), [item.to_dict() for item in value.findings])


def render_gate_markdown(value: DecisionLedgerReleaseGate) -> str:
    verify_gate(value)
    return _markdown("Release-Registry Review Decision Ledger Gate", value.summary(), [item.to_dict() for item in value.checks])


def render_assurance_gate_markdown(value: DecisionLedgerAssuranceGate) -> str:
    verify_assurance_gate(value)
    rows = [{"record": "finding", **item.to_dict()} for item in value.assurance.findings] + [{"record": "check", **item.to_dict()} for item in value.gate.checks]
    return _markdown("Release-Registry Review Decision Ledger Assurance Gate", {"assurance_state": value.assurance.state, "gate_state": value.gate.state, "release_ready": value.gate.release_ready, "ledger_address": value.gate.ledger_address}, rows)


def render_query_markdown(value: AssuranceQueryResult) -> str:
    return _markdown("Release-Registry Review Decision Ledger Assurance Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def render_diff_markdown(value: AssuranceDiff) -> str:
    verify_diff(value)
    return _markdown("Release-Registry Review Decision Ledger Assurance Diff", value.summary(), [item.to_dict() for item in value.items])


def render_diff_query_markdown(value: DiffQueryResult) -> str:
    return _markdown("Release-Registry Review Decision Ledger Assurance Diff Query", {"resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def assurance_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance", "type": "object", "additionalProperties": False, "properties": {"assurance_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "ledger_address": {"type": "string"}, "finding_count": {"type": "integer", "minimum": 1, "maximum": MAX_FINDINGS}, "state": {"enum": [item.value for item in AssuranceState]}, "release_ready": {"type": "boolean"}, "findings": {"type": "array", "maxItems": MAX_FINDINGS}, "content_address": {"type": "string"}}, "required": ["assurance_id", "version", "boundary", "ledger_address", "finding_count", "state", "release_ready", "content_address"]}


def gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Gate", "type": "object", "additionalProperties": False, "properties": {"gate_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "ledger_address": {"type": "string"}, "assurance_address": {"type": "string"}, "check_count": {"type": "integer", "minimum": 1, "maximum": MAX_CHECKS}, "state": {"enum": [item.value for item in GateState]}, "release_ready": {"type": "boolean"}, "checks": {"type": "array", "maxItems": MAX_CHECKS}, "content_address": {"type": "string"}}, "required": ["gate_id", "version", "boundary", "ledger_address", "assurance_address", "check_count", "state", "release_ready", "content_address"]}


def assurance_gate_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Gate Bundle", "type": "object", "additionalProperties": False, "properties": {"assurance": {"type": "object"}, "gate": {"type": "object"}, "content_address": {"type": "string"}}, "required": ["assurance", "gate", "content_address"]}


def finding_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Finding", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0}, "finding_id": {"type": "string"}, "plane": {"enum": [item.value for item in AssurancePlane]}, "kind": {"type": "string"}, "severity": {"enum": [item.value for item in AssuranceSeverity]}, "required": {"type": "boolean"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "remediation": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}, "required": ["ordinal", "finding_id", "plane", "kind", "severity", "required", "passed", "detail", "remediation", "evidence_address", "content_address"]}


def check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Gate Check", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0}, "check_id": {"type": "string"}, "plane": {"enum": [item.value for item in AssurancePlane]}, "kind": {"type": "string"}, "required": {"type": "boolean"}, "passed": {"type": "boolean"}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}, "required": ["ordinal", "check_id", "plane", "kind", "required", "passed", "detail", "evidence_address", "content_address"]}


def query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": list(AssuranceQuery.RESOURCES)}, "severity": {"type": ["string", "null"]}, "passed": {"type": ["boolean", "null"]}, "required": {"type": ["boolean", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Diff", "type": "object", "additionalProperties": False, "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS}, "state": {"enum": [item.value for item in DiffState]}, "items": {"type": "array", "maxItems": MAX_DIFF_ITEMS}, "content_address": {"type": "string"}}, "required": ["diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "state", "content_address"]}


def diff_item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Diff Item", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0}, "action": {"enum": [item.value for item in DiffAction]}, "key": {"type": "string"}, "plane": {"enum": [item.value for item in AssurancePlane]}, "kind": {"type": "string"}, "baseline_passed": {"type": ["boolean", "null"]}, "candidate_passed": {"type": ["boolean", "null"]}, "content_address": {"type": "string"}}, "required": ["ordinal", "action", "key", "plane", "kind", "content_address"]}


def diff_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Release-Registry Review Decision Ledger Assurance Diff Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": list(DiffQuery.RESOURCES)}, "action": {"type": ["string", "null"]}, "plane": {"type": ["string", "null"]}, "text": {"type": ["string", "null"]}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1}}, "required": ["resource", "offset", "limit"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "assurance": {"findings": 14, "severities": [item.value for item in AssuranceSeverity], "states": [item.value for item in AssuranceState], "planes": [item.value for item in AssurancePlane]}, "gate": {"checks": 10, "states": [item.value for item in GateState], "source_authoritative": True}, "persistence": {"files": list(FILES), "diff_files": list(DIFF_FILES), "canonical_json": True, "atomic_write": True}, "queries": {"resources": list(AssuranceQuery.RESOURCES), "pagination": True, "filters": ["severity", "passed", "required", "plane", "text"]}, "diff": {"maximum_items": MAX_DIFF_ITEMS, "actions": [item.value for item in DiffAction], "states": [item.value for item in DiffState], "query_resources": list(DiffQuery.RESOURCES)}}


def _manifest_body(value: DecisionLedgerAssuranceGate, assurance_raw: bytes, gate_raw: bytes) -> dict[str, Any]:
    artifacts = []
    for name, raw in ((ASSURANCE_NAME, assurance_raw), (GATE_NAME, gate_raw)):
        byte_address = hash_bytes(raw)
        artifacts.append({"name": name, "bytes": len(raw), "byte_address": byte_address, "file_address": content_hash({"name": name, "byte_address": byte_address}, prefix=ASSURANCE_PREFIX + "-file")})
    return {"version": VERSION, "boundary": BOUNDARY, "ledger_id": value.gate.ledger_id, "ledger_address": value.gate.ledger_address, "assurance_address": value.assurance.content_address, "gate_address": value.gate.content_address, "artifact_count": 2, "files": list(FILES), "artifacts": artifacts, "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_assurance_gate(value: DecisionLedgerAssuranceGate, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_assurance_gate(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("assurance gate destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    assurance_raw, gate_raw = canonical_bytes(value.assurance.to_dict()), canonical_bytes(value.gate.to_dict())
    manifest = _manifest_body(value, assurance_raw, gate_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-ledger-assurance-", dir=str(destination.parent)))
    try:
        (temporary / ASSURANCE_NAME).write_bytes(assurance_raw)
        (temporary / GATE_NAME).write_bytes(gate_raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if not destination.is_dir() or not overwrite:
                raise ValidationError("assurance gate destination cannot be replaced")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"{field} must be a regular file")
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is invalid JSON") from exc
    if canonical_bytes(value) != raw:
        raise ValidationError(f"{field} is not canonical JSON")
    return dict(_mapping(value, field))


def _check_artifact(manifest: Mapping[str, Any], path: Path, name: str) -> None:
    artifact = next((item for item in _mapping_sequence(manifest.get("artifacts"), "assurance artifacts") if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"assurance manifest is missing {name}")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address:
        raise ValidationError(f"assurance {name} bytes are not addressed")
    if artifact.get("file_address") != content_hash({"name": name, "byte_address": byte_address}, prefix=ASSURANCE_PREFIX + "-file"):
        raise ValidationError(f"assurance {name} file address is invalid")


def load_assurance_gate(directory: str | Path) -> DecisionLedgerAssuranceGate:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir() or any(item.is_symlink() for item in source.iterdir()) or {item.name for item in source.iterdir()} != set(FILES):
        raise ValidationError("assurance gate file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "assurance manifest")
    fields = {"version", "boundary", "ledger_id", "ledger_address", "assurance_address", "gate_address", "artifact_count", "files", "artifacts", "manifest_address"}
    _strict(manifest, fields, "assurance manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES or len(manifest["artifacts"]) != 2 or manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("assurance manifest contract is invalid")
    _check_artifact(manifest, source / ASSURANCE_NAME, ASSURANCE_NAME)
    _check_artifact(manifest, source / GATE_NAME, GATE_NAME)
    assurance = assurance_from_mapping(_read_json(source / ASSURANCE_NAME, "assurance report"))
    gate = gate_from_mapping(_read_json(source / GATE_NAME, "assurance gate"))
    provisional = DecisionLedgerAssuranceGate(assurance, gate, "pending:bundle")
    value = DecisionLedgerAssuranceGate(assurance, gate, address_assurance_gate(provisional))
    if manifest["ledger_id"] != gate.ledger_id or manifest["ledger_address"] != gate.ledger_address or manifest["assurance_address"] != assurance.content_address or manifest["gate_address"] != gate.content_address:
        raise ValidationError("assurance manifest linkage is invalid")
    return verify_assurance_gate(value)


def _diff_manifest_body(value: AssuranceDiff, raw: bytes) -> dict[str, Any]:
    byte_address = hash_bytes(raw)
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "artifact_count": 1, "files": list(DIFF_FILES), "artifact": {"name": DIFF_NAME, "bytes": len(raw), "byte_address": byte_address, "file_address": content_hash({"name": DIFF_NAME, "byte_address": byte_address}, prefix=DIFF_PREFIX + "-file")}, "manifest_address": None}


def _diff_manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=DIFF_MANIFEST_PREFIX)


def write_diff(value: AssuranceDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_diff(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("assurance diff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(value.to_dict())
    manifest = _diff_manifest_body(value, raw)
    manifest["manifest_address"] = _diff_manifest_address(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=".glio-ledger-assurance-diff-", dir=str(destination.parent)))
    try:
        (temporary / DIFF_NAME).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if not destination.is_dir() or not overwrite:
                raise ValidationError("assurance diff destination cannot be replaced")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_diff(directory: str | Path) -> AssuranceDiff:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir() or any(item.is_symlink() for item in source.iterdir()) or {item.name for item in source.iterdir()} != set(DIFF_FILES):
        raise ValidationError("assurance diff file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "assurance diff manifest")
    fields = {"version", "boundary", "diff_id", "baseline_address", "candidate_address", "artifact_count", "files", "artifact", "manifest_address"}
    _strict(manifest, fields, "assurance diff manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 1 or tuple(manifest["files"]) != DIFF_FILES or manifest["manifest_address"] != _diff_manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("assurance diff manifest contract is invalid")
    artifact = _mapping(manifest["artifact"], "assurance diff artifact")
    raw = (source / DIFF_NAME).read_bytes()
    if artifact.get("name") != DIFF_NAME or artifact.get("bytes") != len(raw) or artifact.get("byte_address") != hash_bytes(raw) or artifact.get("file_address") != content_hash({"name": DIFF_NAME, "byte_address": hash_bytes(raw)}, prefix=DIFF_PREFIX + "-file"):
        raise ValidationError("assurance diff artifact is invalid")
    value = diff_from_mapping(_read_json(source / DIFF_NAME, "assurance diff"))
    if value.diff_id != manifest["diff_id"] or value.baseline_address != manifest["baseline_address"] or value.candidate_address != manifest["candidate_address"]:
        raise ValidationError("assurance diff manifest linkage is invalid")
    return verify_diff(value)


__all__ = [
    "ASSURANCE_NAME", "AssuranceDiff", "AssuranceQuery", "AssuranceQueryResult", "AssurancePlane", "AssuranceSeverity", "AssuranceState", "BOUNDARY", "DIFF_FILES", "DIFF_NAME", "DiffAction", "DiffItem", "DiffQuery", "DiffQueryResult", "DiffState", "FILES", "GATE_NAME", "GateState", "DecisionLedgerAssurance", "DecisionLedgerAssuranceFinding", "DecisionLedgerAssuranceGate", "DecisionLedgerGateCheck", "DecisionLedgerReleaseGate", "DEFAULT_ASSURANCE_ID", "DEFAULT_DIFF_ID", "DEFAULT_GATE_ID", "address_assurance", "address_assurance_gate", "address_check", "address_diff", "address_diff_item", "address_finding", "assurance_csv", "assurance_from_mapping", "assurance_gate_from_mapping", "assurance_gate_json", "assurance_gate_schema", "assurance_json", "assurance_schema", "build_assurance", "build_assurance_gate", "build_assurance_gate_from_directory", "build_diff", "capabilities", "check_from_mapping", "check_schema", "diff_csv", "diff_from_mapping", "diff_item_from_mapping", "diff_item_schema", "diff_json", "diff_query_csv", "diff_query_json", "diff_query_schema", "diff_schema", "finding_from_mapping", "finding_schema", "gate_from_mapping", "gate_json", "gate_schema", "load_assurance_gate", "load_diff", "query_assurance", "query_csv", "query_diff", "query_json", "render_assurance_gate_markdown", "render_assurance_markdown", "render_diff_markdown", "render_diff_query_markdown", "render_gate_markdown", "render_query_markdown", "verify_assurance", "verify_assurance_gate", "verify_assurance_gate_against_ledger", "verify_diff", "verify_gate", "write_assurance_gate", "write_diff",
]
