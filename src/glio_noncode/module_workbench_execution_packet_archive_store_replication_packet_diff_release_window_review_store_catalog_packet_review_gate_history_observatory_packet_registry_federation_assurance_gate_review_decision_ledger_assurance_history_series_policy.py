"""Evaluate a public policy against a decision-assurance history series.

The history-series aggregate answers *what is present*.  This module answers
whether that aggregate is acceptable for a named operating policy.  Policy
evaluation is intentionally independent from series construction: limits are
validated, each rule receives an addressed check, optional failures become
holds, required failures become blocks, and all source addresses are retained
without copying source paths or private metadata.

The durable evaluation handoff contains exactly ``manifest.json``,
``policy.json``, and ``evaluation.json``.  Canonical bytes, byte receipts,
manifest linkage, nested policy/check addresses, and the public boundary are
verified on reload.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from . import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series as series_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

DecisionAssuranceHistorySeries = series_model.DecisionAssuranceHistorySeries

VERSION = series_model.VERSION + "-policy-v1"
BOUNDARY = "public_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_policy"
POLICY_PREFIX = series_model.SERIES_PREFIX + "-policy"
CHECK_PREFIX = POLICY_PREFIX + "-check"
EVALUATION_PREFIX = POLICY_PREFIX + "-evaluation"
MANIFEST_PREFIX = POLICY_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
POLICY_NAME = "policy.json"
EVALUATION_NAME = "evaluation.json"
FILES = (MANIFEST_NAME, POLICY_NAME, EVALUATION_NAME)
DEFAULT_POLICY_ID = "glio-noncode-observatory-registry-federation-review-decision-assurance-history-series-policy"
MAX_HISTORIES = series_model.MAX_HISTORIES
MAX_OBSERVATIONS = series_model.MAX_HISTORIES * 1024
MAX_CHECKS = 32

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class SeriesPolicyState(StrEnum):
    """Policy outcome after required and optional rules are evaluated."""

    PASSED = "passed"
    HOLD = "hold"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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
    if set(value) - allowed:
        raise ValidationError(f"{field} contains unknown fields")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str = "series policy state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in SeriesPolicyState}:
        raise ValidationError(f"{field} is invalid")
    return value


class DecisionAssuranceHistorySeriesPolicy:
    """Bounded, public policy inputs for series acceptance."""

    def __init__(self, policy_id: str, version: str, boundary: str, minimum_histories: int, minimum_observations: int, maximum_held_histories: int, maximum_blocked_histories: int, require_current_accepted: bool, require_current_release_ready: bool, allow_mixed_state: bool, content_address: str) -> None:
        self.policy_id = policy_id
        self.version = version
        self.boundary = boundary
        self.minimum_histories = minimum_histories
        self.minimum_observations = minimum_observations
        self.maximum_held_histories = maximum_held_histories
        self.maximum_blocked_histories = maximum_blocked_histories
        self.require_current_accepted = require_current_accepted
        self.require_current_release_ready = require_current_release_ready
        self.allow_mixed_state = allow_mixed_state
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.policy_id, "series policy ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("series policy contract is invalid")
        _count(self.minimum_histories, "minimum histories", MAX_HISTORIES)
        _count(self.minimum_observations, "minimum observations", MAX_OBSERVATIONS)
        _count(self.maximum_held_histories, "maximum held histories", MAX_HISTORIES)
        _count(self.maximum_blocked_histories, "maximum blocked histories", MAX_HISTORIES)
        for value, field in ((self.require_current_accepted, "require current acceptance"), (self.require_current_release_ready, "require current release readiness"), (self.allow_mixed_state, "allow mixed state")):
            _bool(value, field)
        _address(self.content_address, "series policy address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_policy(self) != self.content_address:
            raise ValidationError("series policy address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series policy crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "minimum_histories": self.minimum_histories, "minimum_observations": self.minimum_observations, "maximum_held_histories": self.maximum_held_histories, "maximum_blocked_histories": self.maximum_blocked_histories, "require_current_accepted": self.require_current_accepted, "require_current_release_ready": self.require_current_release_ready, "allow_mixed_state": self.allow_mixed_state, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return {"policy_id": self.policy_id, "version": self.version, "boundary": self.boundary, "minimum_histories": self.minimum_histories, "minimum_observations": self.minimum_observations, "maximum_held_histories": self.maximum_held_histories, "maximum_blocked_histories": self.maximum_blocked_histories, "require_current_accepted": self.require_current_accepted, "require_current_release_ready": self.require_current_release_ready, "allow_mixed_state": self.allow_mixed_state, "content_address": self.content_address}


def address_decision_assurance_history_series_policy(value: DecisionAssuranceHistorySeriesPolicy) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_decision_assurance_history_series_policy(*, policy_id: str = DEFAULT_POLICY_ID) -> DecisionAssuranceHistorySeriesPolicy:
    body = {"policy_id": policy_id, "version": VERSION, "boundary": BOUNDARY, "minimum_histories": 1, "minimum_observations": 1, "maximum_held_histories": 0, "maximum_blocked_histories": 0, "require_current_accepted": True, "require_current_release_ready": True, "allow_mixed_state": True, "content_address": "pending:series-policy"}
    provisional = DecisionAssuranceHistorySeriesPolicy(**body)
    body["content_address"] = address_decision_assurance_history_series_policy(provisional)
    return DecisionAssuranceHistorySeriesPolicy(**body)


def verify_decision_assurance_history_series_policy(value: DecisionAssuranceHistorySeriesPolicy) -> DecisionAssuranceHistorySeriesPolicy:
    if not isinstance(value, DecisionAssuranceHistorySeriesPolicy):
        raise ValidationError("series policy verification requires a typed policy")
    value._validate()
    if address_decision_assurance_history_series_policy(value) != value.content_address:
        raise ValidationError("series policy address mismatch")
    return value


def decision_assurance_history_series_policy_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesPolicy:
    body = dict(_mapping(value, "series policy"))
    _strict(body, {"policy_id", "version", "boundary", "minimum_histories", "minimum_observations", "maximum_held_histories", "maximum_blocked_histories", "require_current_accepted", "require_current_release_ready", "allow_mixed_state", "content_address"}, "series policy")
    return verify_decision_assurance_history_series_policy(DecisionAssuranceHistorySeriesPolicy(**body))


class DecisionAssuranceHistorySeriesPolicyCheck:
    """One addressed policy rule with required-versus-optional severity."""

    def __init__(self, ordinal: int, check_id: str, kind: str, passed: bool, required: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.check_id = check_id
        self.kind = kind
        self.passed = passed
        self.required = required
        self.detail = detail
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "series policy check ordinal", MAX_CHECKS)
        _text(self.check_id, "series policy check ID", 256)
        _text(self.kind, "series policy check kind", 128)
        _bool(self.passed, "series policy check passed")
        _bool(self.required, "series policy check required")
        _text(self.detail, "series policy check detail", 1024)
        _address(self.evidence_address, "series policy evidence address")
        _address(self.content_address, "series policy check address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_policy_check(self) != self.content_address:
            raise ValidationError("series policy check address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series policy check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "check_id": self.check_id, "kind": self.kind, "passed": self.passed, "required": self.required, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_decision_assurance_history_series_policy_check(value: DecisionAssuranceHistorySeriesPolicyCheck) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=CHECK_PREFIX)


class DecisionAssuranceHistorySeriesPolicyEvaluation:
    """Independent addressed evaluation of a series against a policy."""

    def __init__(self, series_address: str, series_id: str, policy: DecisionAssuranceHistorySeriesPolicy, check_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, checks: Sequence[DecisionAssuranceHistorySeriesPolicyCheck], content_address: str) -> None:
        self.series_address = series_address
        self.series_id = series_id
        self.policy = policy
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.series_address, "policy evaluation series address")
        _text(self.series_id, "policy evaluation series ID", 256)
        verify_decision_assurance_history_series_policy(self.policy)
        _count(self.check_count, "series policy evaluation check count", MAX_CHECKS)
        _count(self.passed_count, "series policy evaluation passed count", MAX_CHECKS)
        _count(self.warning_count, "series policy evaluation warning count", MAX_CHECKS)
        _count(self.blocker_count, "series policy evaluation blocker count", MAX_CHECKS)
        if self.check_count != len(self.checks) or self.passed_count + self.warning_count + self.blocker_count != self.check_count:
            raise ValidationError("series policy evaluation counts are not conserved")
        if self.passed_count != sum(check.passed for check in self.checks) or self.warning_count != sum(not check.passed and not check.required for check in self.checks) or self.blocker_count != sum(not check.passed and check.required for check in self.checks):
            raise ValidationError("series policy evaluation severities are not conserved")
        for ordinal, check in enumerate(self.checks):
            if not isinstance(check, DecisionAssuranceHistorySeriesPolicyCheck) or check.ordinal != ordinal:
                raise ValidationError("series policy checks are not contiguous")
            if address_decision_assurance_history_series_policy_check(check) != check.content_address:
                raise ValidationError("series policy check address mismatch")
        _state(self.state)
        _bool(self.accepted, "series policy evaluation accepted")
        _bool(self.release_ready, "series policy evaluation release readiness")
        if self.accepted != (self.blocker_count == 0) or self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("series policy evaluation readiness is invalid")
        _address(self.content_address, "series policy evaluation address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_policy_evaluation(self) != self.content_address:
            raise ValidationError("series policy evaluation address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series policy evaluation crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"series_address": self.series_address, "series_id": self.series_id, "policy_id": self.policy.policy_id, "policy_address": self.policy.content_address, "check_count": self.check_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return self.summary() | {"policy": self.policy.to_dict(), "checks": [check.to_dict() for check in self.checks]}


def address_decision_assurance_history_series_policy_evaluation(value: DecisionAssuranceHistorySeriesPolicyEvaluation) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=EVALUATION_PREFIX)


def _policy_check(ordinal: int, series: DecisionAssuranceHistorySeries, policy: DecisionAssuranceHistorySeriesPolicy, kind: str, passed: bool, required: bool, detail: str) -> DecisionAssuranceHistorySeriesPolicyCheck:
    body = {"ordinal": ordinal, "check_id": f"{policy.policy_id}:check:{ordinal}", "kind": kind, "passed": bool(passed), "required": required, "detail": detail, "evidence_address": series.content_address, "content_address": "pending:series-policy-check"}
    provisional = DecisionAssuranceHistorySeriesPolicyCheck(**body)
    body["content_address"] = address_decision_assurance_history_series_policy_check(provisional)
    return DecisionAssuranceHistorySeriesPolicyCheck(**body)


def evaluate_decision_assurance_history_series_policy(series: DecisionAssuranceHistorySeries, policy: DecisionAssuranceHistorySeriesPolicy | None = None) -> DecisionAssuranceHistorySeriesPolicyEvaluation:
    series_model.verify_decision_assurance_history_series(series)
    selected = policy or default_decision_assurance_history_series_policy()
    verify_decision_assurance_history_series_policy(selected)
    checks = (
        _policy_check(0, series, selected, "minimum-histories", series.history_count >= selected.minimum_histories, True, f"series contains {series.history_count} histories; minimum is {selected.minimum_histories}"),
        _policy_check(1, series, selected, "minimum-observations", series.observation_count >= selected.minimum_observations, True, f"series contains {series.observation_count} observations; minimum is {selected.minimum_observations}"),
        _policy_check(2, series, selected, "blocked-ceiling", series.blocked_history_count <= selected.maximum_blocked_histories, True, f"series contains {series.blocked_history_count} blocked histories; maximum is {selected.maximum_blocked_histories}"),
        _policy_check(3, series, selected, "held-ceiling", series.held_history_count <= selected.maximum_held_histories, False, f"series contains {series.held_history_count} held histories; maximum is {selected.maximum_held_histories}"),
        _policy_check(4, series, selected, "current-acceptance", not selected.require_current_accepted or (series.history_count > 0 and series.current_accepted_count == series.history_count), selected.require_current_accepted, f"{series.current_accepted_count} of {series.history_count} current histories are accepted"),
        _policy_check(5, series, selected, "current-release-readiness", not selected.require_current_release_ready or (series.history_count > 0 and series.current_release_ready_count == series.history_count), selected.require_current_release_ready, f"{series.current_release_ready_count} of {series.history_count} current histories are release-ready"),
        _policy_check(6, series, selected, "mixed-state", selected.allow_mixed_state or series.current_state != series_model.HistorySeriesState.MIXED.value, not selected.allow_mixed_state, f"series current state is {series.current_state}"),
        _policy_check(7, series, selected, "public-boundary", _public(series.to_dict()) and _public(selected.to_dict()), True, "series and policy contain only public fields"),
        _policy_check(8, series, selected, "aggregate-conservation", series.observation_count == sum(entry.entry_count for entry in series.entries) and series.history_count == len(series.entries), True, "series observations and history membership are conserved"),
    )
    passed = sum(check.passed for check in checks)
    warning = sum(not check.passed and not check.required for check in checks)
    blocker = sum(not check.passed and check.required for check in checks)
    state = SeriesPolicyState.BLOCKED.value if blocker else SeriesPolicyState.HOLD.value if warning else SeriesPolicyState.PASSED.value
    body = {"series_address": series.content_address, "series_id": series.series_id, "policy": selected, "check_count": len(checks), "passed_count": passed, "warning_count": warning, "blocker_count": blocker, "state": state, "accepted": blocker == 0, "release_ready": blocker == 0 and warning == 0, "checks": checks, "content_address": "pending:series-policy-evaluation"}
    provisional = DecisionAssuranceHistorySeriesPolicyEvaluation(**body)
    body["content_address"] = address_decision_assurance_history_series_policy_evaluation(provisional)
    return DecisionAssuranceHistorySeriesPolicyEvaluation(**body)


def verify_decision_assurance_history_series_policy_evaluation(value: DecisionAssuranceHistorySeriesPolicyEvaluation) -> DecisionAssuranceHistorySeriesPolicyEvaluation:
    if not isinstance(value, DecisionAssuranceHistorySeriesPolicyEvaluation):
        raise ValidationError("series policy evaluation verification requires a typed evaluation")
    value._validate()
    if address_decision_assurance_history_series_policy_evaluation(value) != value.content_address:
        raise ValidationError("series policy evaluation address mismatch")
    return value


def decision_assurance_history_series_policy_check_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesPolicyCheck:
    body = dict(_mapping(value, "series policy check"))
    _strict(body, {"ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"}, "series policy check")
    check = DecisionAssuranceHistorySeriesPolicyCheck(**body)
    if address_decision_assurance_history_series_policy_check(check) != check.content_address:
        raise ValidationError("series policy check address mismatch")
    return check


def decision_assurance_history_series_policy_evaluation_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesPolicyEvaluation:
    body = dict(_mapping(value, "series policy evaluation"))
    _strict(body, {"series_address", "series_id", "policy_id", "policy_address", "check_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "content_address", "policy", "checks"}, "series policy evaluation")
    policy = decision_assurance_history_series_policy_from_mapping(_mapping(body.pop("policy"), "series policy evaluation policy"))
    if body["policy_id"] != policy.policy_id or body["policy_address"] != policy.content_address:
        raise ValidationError("series policy evaluation policy linkage is invalid")
    body.pop("policy_id")
    body.pop("policy_address")
    checks = tuple(decision_assurance_history_series_policy_check_from_mapping(item) for item in _mapping_sequence(body.pop("checks"), "series policy evaluation checks"))
    return verify_decision_assurance_history_series_policy_evaluation(DecisionAssuranceHistorySeriesPolicyEvaluation(**body, policy=policy, checks=checks))


def decision_assurance_history_series_policy_json(value: DecisionAssuranceHistorySeriesPolicy) -> str:
    verify_decision_assurance_history_series_policy(value)
    return canonical_json(value.to_dict())


def decision_assurance_history_series_policy_evaluation_json(value: DecisionAssuranceHistorySeriesPolicyEvaluation) -> str:
    verify_decision_assurance_history_series_policy_evaluation(value)
    return canonical_json(value.to_dict())


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def decision_assurance_history_series_policy_csv(value: DecisionAssuranceHistorySeriesPolicy) -> str:
    verify_decision_assurance_history_series_policy(value)
    return _csv_text([value.to_dict()], ("policy_id", "minimum_histories", "minimum_observations", "maximum_held_histories", "maximum_blocked_histories", "require_current_accepted", "require_current_release_ready", "allow_mixed_state", "content_address"))


def decision_assurance_history_series_policy_evaluation_csv(value: DecisionAssuranceHistorySeriesPolicyEvaluation) -> str:
    verify_decision_assurance_history_series_policy_evaluation(value)
    return _csv_text([check.to_dict() for check in value.checks], ("ordinal", "check_id", "kind", "passed", "required", "detail", "evidence_address", "content_address"))


def _markdown(title: str, summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [f"# {title}", "", "## Summary", ""]
    lines.extend(f"- **{key}**: `{canonical_json(value)}`" for key, value in summary.items())
    if rows:
        fields = tuple(rows[0])
        lines.extend(("", "## Records", "", "| " + " | ".join(fields) + " |", "| " + " | ".join("---" for _ in fields) + " |"))
        lines.extend("| " + " | ".join(canonical_json(row.get(field, "")).replace("|", "\\|") for field in fields) + " |" for row in rows)
    else:
        lines.extend(("", "No records."))
    return "\n".join(lines) + "\n"


def render_decision_assurance_history_series_policy_markdown(value: DecisionAssuranceHistorySeriesPolicy) -> str:
    verify_decision_assurance_history_series_policy(value)
    return _markdown("Federation Review Decision Assurance History Series Policy", value.summary(), [value.to_dict()])


def render_decision_assurance_history_series_policy_evaluation_markdown(value: DecisionAssuranceHistorySeriesPolicyEvaluation) -> str:
    verify_decision_assurance_history_series_policy_evaluation(value)
    return _markdown("Federation Review Decision Assurance History Series Policy Evaluation", value.summary(), [check.to_dict() for check in value.checks])


def decision_assurance_history_series_policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Policy", "type": "object", "additionalProperties": False, "properties": {"policy_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "minimum_histories": {"type": "integer", "minimum": 0, "maximum": MAX_HISTORIES}, "minimum_observations": {"type": "integer", "minimum": 0, "maximum": MAX_OBSERVATIONS}, "maximum_held_histories": {"type": "integer", "minimum": 0, "maximum": MAX_HISTORIES}, "maximum_blocked_histories": {"type": "integer", "minimum": 0, "maximum": MAX_HISTORIES}, "content_address": {"type": "string"}}, "required": ["policy_id", "version", "boundary", "minimum_histories", "minimum_observations", "maximum_held_histories", "maximum_blocked_histories", "content_address"]}


def decision_assurance_history_series_policy_check_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Policy Check", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "kind": {"type": "string"}, "passed": {"type": "boolean"}, "required": {"type": "boolean"}, "content_address": {"type": "string"}}, "required": ["ordinal", "kind", "passed", "required", "content_address"]}


def decision_assurance_history_series_policy_evaluation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Federation Review Decision Assurance History Series Policy Evaluation", "type": "object", "additionalProperties": False, "properties": {"series_address": {"type": "string"}, "series_id": {"type": "string"}, "policy_id": {"type": "string"}, "policy_address": {"type": "string"}, "check_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "warning_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "blocker_count": {"type": "integer", "minimum": 0, "maximum": MAX_CHECKS}, "state": {"enum": [item.value for item in SeriesPolicyState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "policy": {"type": "object"}, "checks": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["series_address", "series_id", "policy_id", "policy_address", "check_count", "state", "accepted", "release_ready", "content_address"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "policy": {"maximum_histories": MAX_HISTORIES, "maximum_observations": MAX_OBSERVATIONS, "maximum_checks": MAX_CHECKS, "states": [item.value for item in SeriesPolicyState]}, "checks": {"count": 9, "required_rules": ["minimum-histories", "minimum-observations", "blocked-ceiling", "current-acceptance", "current-release-readiness", "public-boundary", "aggregate-conservation"], "optional_rules": ["held-ceiling", "mixed-state"]}, "persistence": {"files": list(FILES), "atomic_write": True, "canonical_json": True, "exact_file_set": True}}


def _manifest_body(value: DecisionAssuranceHistorySeriesPolicyEvaluation, policy_raw: bytes, evaluation_raw: bytes) -> dict[str, Any]:
    artifacts = [{"name": POLICY_NAME, "bytes": len(policy_raw), "byte_address": hash_bytes(policy_raw), "file_address": content_hash({"name": POLICY_NAME, "byte_address": hash_bytes(policy_raw)}, prefix=POLICY_PREFIX + "-file")}, {"name": EVALUATION_NAME, "bytes": len(evaluation_raw), "byte_address": hash_bytes(evaluation_raw), "file_address": content_hash({"name": EVALUATION_NAME, "byte_address": hash_bytes(evaluation_raw)}, prefix=POLICY_PREFIX + "-file")}]
    return {"version": VERSION, "boundary": BOUNDARY, "policy_id": value.policy.policy_id, "policy_address": value.policy.content_address, "series_address": value.series_address, "evaluation_address": value.content_address, "artifact_count": 2, "files": list(FILES), "artifacts": artifacts, "manifest_address": None}


def _manifest_address(value: Mapping[str, Any]) -> str:
    return content_hash(dict(value), prefix=MANIFEST_PREFIX)


def write_decision_assurance_history_series_policy_evaluation(value: DecisionAssuranceHistorySeriesPolicyEvaluation, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_history_series_policy_evaluation(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("series policy evaluation destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    policy_raw = canonical_bytes(value.policy.to_dict())
    evaluation_raw = canonical_bytes(value.to_dict())
    manifest = _manifest_body(value, policy_raw, evaluation_raw)
    manifest["manifest_address"] = _manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{POLICY_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / POLICY_NAME).write_bytes(policy_raw)
        (temporary / EVALUATION_NAME).write_bytes(evaluation_raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if not destination.is_dir():
                raise ValidationError("series policy evaluation destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("series policy evaluation destination already exists")
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
    artifact = next((item for item in _mapping_sequence(manifest.get("artifacts"), "policy manifest artifacts") if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"policy manifest is missing {name}")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address:
        raise ValidationError(f"series policy {name} bytes are not addressed")
    if artifact.get("file_address") != content_hash({"name": name, "byte_address": byte_address}, prefix=POLICY_PREFIX + "-file"):
        raise ValidationError(f"series policy {name} file address is invalid")


def load_decision_assurance_history_series_policy_evaluation(directory: str | Path) -> DecisionAssuranceHistorySeriesPolicyEvaluation:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("series policy evaluation input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("series policy evaluation file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "series policy manifest")
    _strict(manifest, {"version", "boundary", "policy_id", "policy_address", "series_address", "evaluation_address", "artifact_count", "files", "artifacts", "manifest_address"}, "series policy manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 2 or tuple(manifest["files"]) != FILES:
        raise ValidationError("series policy manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("series policy manifest address mismatch")
    _check_artifact(manifest, source / POLICY_NAME, POLICY_NAME)
    _check_artifact(manifest, source / EVALUATION_NAME, EVALUATION_NAME)
    policy = decision_assurance_history_series_policy_from_mapping(_read_json(source / POLICY_NAME, "series policy"))
    evaluation = decision_assurance_history_series_policy_evaluation_from_mapping(_read_json(source / EVALUATION_NAME, "series policy evaluation"))
    if policy.policy_id != manifest["policy_id"] or policy.content_address != manifest["policy_address"] or evaluation.series_address != manifest["series_address"] or evaluation.content_address != manifest["evaluation_address"] or evaluation.policy.content_address != policy.content_address:
        raise ValidationError("series policy manifest linkage is invalid")
    return verify_decision_assurance_history_series_policy_evaluation(evaluation)


__all__ = ["BOUNDARY", "CHECK_PREFIX", "DEFAULT_POLICY_ID", "EVALUATION_NAME", "FILES", "MANIFEST_NAME", "MAX_CHECKS", "MAX_HISTORIES", "MAX_OBSERVATIONS", "POLICY_NAME", "POLICY_PREFIX", "DecisionAssuranceHistorySeries", "DecisionAssuranceHistorySeriesPolicy", "DecisionAssuranceHistorySeriesPolicyCheck", "DecisionAssuranceHistorySeriesPolicyEvaluation", "SeriesPolicyState", "address_decision_assurance_history_series_policy", "address_decision_assurance_history_series_policy_check", "address_decision_assurance_history_series_policy_evaluation", "capabilities", "default_decision_assurance_history_series_policy", "decision_assurance_history_series_policy_check_from_mapping", "decision_assurance_history_series_policy_check_schema", "decision_assurance_history_series_policy_csv", "decision_assurance_history_series_policy_evaluation_csv", "decision_assurance_history_series_policy_evaluation_from_mapping", "decision_assurance_history_series_policy_evaluation_json", "decision_assurance_history_series_policy_evaluation_schema", "decision_assurance_history_series_policy_from_mapping", "decision_assurance_history_series_policy_json", "decision_assurance_history_series_policy_schema", "evaluate_decision_assurance_history_series_policy", "load_decision_assurance_history_series_policy_evaluation", "render_decision_assurance_history_series_policy_evaluation_markdown", "render_decision_assurance_history_series_policy_markdown", "verify_decision_assurance_history_series_policy", "verify_decision_assurance_history_series_policy_evaluation", "write_decision_assurance_history_series_policy_evaluation"]
