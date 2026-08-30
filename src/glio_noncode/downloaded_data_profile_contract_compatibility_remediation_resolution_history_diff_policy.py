"""Policy-governed release review over value-free remediation-history diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from typing import Any

from . import downloaded_data_ingestion as ingestion_model
from . import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as diff_model,
)
from .errors import ValidationError
from .serialization import canonical_json, content_hash

VERSION = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-v1"
BOUNDARY = "public_downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy"
POLICY_PREFIX = "glio-noncode-download-profile-contract-compatibility-remediation-resolution-history-diff-policy"
EVALUATION_PREFIX = POLICY_PREFIX + "-evaluation"
RULE_PREFIX = EVALUATION_PREFIX + "-rule"
DEFAULT_POLICY_ID = POLICY_PREFIX
STATES = ("eligible", "review", "blocked")
DECISIONS = ("promote", "hold", "block")
RULE_IDS = ("direction-allowed", "candidate-ready", "added-limit", "removed-limit", "changed-limit", "improved-delta", "regressed-delta", "entry-total", "state-transition", "public-boundary")
POLICY_FIELDS = ("policy_id", "allowed_directions", "require_candidate_ready", "max_added_count", "max_removed_count", "max_changed_count", "max_improved_delta", "max_regressed_delta", "require_state_progression", "content_address")
RULE_FIELDS = ("ordinal", "rule_id", "passed", "observed", "limit", "detail", "content_address")
EVALUATION_FIELDS = ("evaluation_id", "version", "boundary", "policy_id", "policy_address", "policy", "diff_id", "diff_address", "left_entry_count", "right_entry_count", "direction", "candidate_release_ready", "added_count", "removed_count", "changed_count", "unchanged_count", "improved_delta", "regressed_delta", "state_transition", "state", "decision", "accepted", "release_ready", "rules", "rule_count", "passed_rule_count", "failed_rule_count", "content_address")
MAX_RULES = len(RULE_IDS)


def _text(value: Any, field: str, maximum: int = 4096, *, required: bool = True) -> str:
    if not isinstance(value, str) or len(value) > maximum or (required and not value) or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{field} must be bounded public text")
    return value


def _label(value: Any, field: str, *, required: bool = True) -> str:
    value = _text(value, field, 256, required=required)
    if value and (value.strip() != value or any(char.isspace() for char in value) or "/" in value or "\\" in value or '"' in value):
        raise ValidationError(f"{field} must be a compact label")
    return value


def _address(value: Any, field: str, prefix: str | None = None) -> str:
    value = _text(value, field, 2048)
    if "/" in value or "\\" in value or '"' in value or ":" not in value or (prefix is not None and not value.startswith(prefix + ":")):
        raise ValidationError(f"{field} has an unsupported address")
    return value


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside its bound")
    return value


def _signed(value: Any, field: str, bound: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < -bound or value > bound:
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


def _ordered_labels(value: Any, field: str, allowed: Sequence[str]) -> tuple[str, ...]:
    labels = tuple(_label(item, field) for item in _sequence(value, field, len(allowed)))
    if not labels or len(set(labels)) != len(labels) or any(item not in allowed for item in labels) or tuple(sorted(labels, key=allowed.index)) != labels:
        raise ValidationError(f"{field} contains unsupported or unordered labels")
    return labels


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in ingestion_model.FORBIDDEN_PUBLIC_KEYS and _public(child) for key, child in value.items())
    if isinstance(value, (tuple, list)):
        return all(_public(child) for child in value)
    return True


def _strict(value: Mapping[str, Any], allowed: set[str], field: str) -> None:
    if set(value) != allowed:
        raise ValidationError(f"{field} contains unknown or missing fields")


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (tuple, list)):
        return "|".join(_display(item) for item in value)
    return str(value)


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy:
    """Explicit bounded thresholds for a history-diff release review."""

    FIELDS = POLICY_FIELDS

    def __init__(self, policy_id: str, allowed_directions: Sequence[str], require_candidate_ready: bool, max_added_count: int, max_removed_count: int, max_changed_count: int, max_improved_delta: int, max_regressed_delta: int, require_state_progression: bool, content_address: str) -> None:
        self.policy_id = _label(policy_id, "history diff policy ID")
        self.allowed_directions = _ordered_labels(allowed_directions, "history diff policy allowed directions", diff_model.DIRECTIONS)
        self.require_candidate_ready = _bool(require_candidate_ready, "history diff policy candidate readiness requirement")
        self.max_added_count = _count(max_added_count, "history diff policy maximum added count", diff_model.MAX_ITEMS)
        self.max_removed_count = _count(max_removed_count, "history diff policy maximum removed count", diff_model.MAX_ITEMS)
        self.max_changed_count = _count(max_changed_count, "history diff policy maximum changed count", diff_model.MAX_ITEMS)
        self.max_improved_delta = _count(max_improved_delta, "history diff policy maximum improved delta", diff_model.MAX_ITEMS)
        self.max_regressed_delta = _count(max_regressed_delta, "history diff policy maximum regressed delta", diff_model.MAX_ITEMS)
        self.require_state_progression = _bool(require_state_progression, "history diff policy state progression requirement")
        self.content_address = _address(content_address, "history diff policy address", POLICY_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_policy(self) != self.content_address:
            raise ValidationError("history diff policy address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy:
        value = _mapping(value, "history diff policy")
        _strict(value, set(cls.FIELDS), "history diff policy")
        return cls(*(value[field] for field in cls.FIELDS))


def address_policy(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy):
        raise ValidationError("history diff policy address requires a typed policy")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=POLICY_PREFIX)


def default_policy(*, policy_id: str = DEFAULT_POLICY_ID, allowed_directions: Sequence[str] = ("improved", "unchanged"), require_candidate_ready: bool = True, max_added_count: int = diff_model.MAX_ITEMS, max_removed_count: int = 0, max_changed_count: int = 0, max_improved_delta: int = diff_model.MAX_ITEMS, max_regressed_delta: int = 0, require_state_progression: bool = True) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy:
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy(policy_id, allowed_directions, require_candidate_ready, max_added_count, max_removed_count, max_changed_count, max_improved_delta, max_regressed_delta, require_state_progression, POLICY_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy(provisional.policy_id, provisional.allowed_directions, provisional.require_candidate_ready, provisional.max_added_count, provisional.max_removed_count, provisional.max_changed_count, provisional.max_improved_delta, provisional.max_regressed_delta, provisional.require_state_progression, address_policy(provisional))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule:
    FIELDS = RULE_FIELDS

    def __init__(self, ordinal: int, rule_id: str, passed: bool, observed: str, limit: str, detail: str, content_address: str) -> None:
        self.ordinal = _count(ordinal, "history diff policy rule ordinal", MAX_RULES)
        if self.ordinal < 1:
            raise ValidationError("history diff policy rule ordinal must be positive")
        self.rule_id = _label(rule_id, "history diff policy rule ID")
        if self.rule_id not in RULE_IDS:
            raise ValidationError("history diff policy rule ID is unsupported")
        self.passed = _bool(passed, "history diff policy rule result")
        self.observed = _text(observed, "history diff policy observed value", 1024)
        self.limit = _text(limit, "history diff policy rule limit", 1024)
        self.detail = _text(detail, "history diff policy rule detail", 1024)
        self.content_address = _address(content_address, "history diff policy rule address", RULE_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy rule crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_rule(self) != self.content_address:
            raise ValidationError("history diff policy rule address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.FIELDS}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule:
        value = _mapping(value, "history diff policy rule")
        _strict(value, set(cls.FIELDS), "history diff policy rule")
        return cls(*(value[field] for field in cls.FIELDS))


def address_rule(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule):
        raise ValidationError("history diff policy rule address requires a typed rule")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RULE_PREFIX)


def _rule_inputs_for_values(left_entry_count: int, right_entry_count: int, direction: str, candidate_release_ready: bool, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, improved_delta: int, regressed_delta: int, state_transition: str, policy: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy, public_ok: bool = True) -> tuple[tuple[str, bool, str, str, str], ...]:
    direction_passed = direction in policy.allowed_directions
    ready_passed = not policy.require_candidate_ready or candidate_release_ready
    state_passed = not policy.require_state_progression or direction_passed
    return (
        ("direction-allowed", direction_passed, direction, "|".join(policy.allowed_directions), "candidate direction is allowed by policy"),
        ("candidate-ready", ready_passed, _display(candidate_release_ready), _display(policy.require_candidate_ready), "candidate release readiness satisfies policy"),
        ("added-limit", added_count <= policy.max_added_count, _display(added_count), _display(policy.max_added_count), "added snapshot count is within policy"),
        ("removed-limit", removed_count <= policy.max_removed_count, _display(removed_count), _display(policy.max_removed_count), "removed snapshot count is within policy"),
        ("changed-limit", changed_count <= policy.max_changed_count, _display(changed_count), _display(policy.max_changed_count), "changed snapshot count is within policy"),
        ("improved-delta", improved_delta <= policy.max_improved_delta, _display(improved_delta), _display(policy.max_improved_delta), "improved transition delta is within policy"),
        ("regressed-delta", regressed_delta <= policy.max_regressed_delta, _display(regressed_delta), _display(policy.max_regressed_delta), "regressed transition delta is within policy"),
        ("entry-total", left_entry_count == removed_count + changed_count + unchanged_count and right_entry_count == added_count + changed_count + unchanged_count, f"{left_entry_count}->{right_entry_count}", "conserved", "baseline and candidate entry totals are conserved"),
        ("state-transition", state_passed, state_transition, _display(policy.require_state_progression), "history state transition follows the allowed direction"),
        ("public-boundary", public_ok and _public(policy.to_dict()), "public", "public", "diff and policy contain only public value-free metadata"),
    )


def _rule_inputs(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, policy: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy) -> tuple[tuple[str, bool, str, str, str], ...]:
    values = _rule_inputs_for_values(diff.left_entry_count, diff.right_entry_count, diff.direction, diff.right_release_ready, diff.added_count, diff.removed_count, diff.changed_count, diff.unchanged_count, diff.improved_delta, diff.regressed_delta, diff.state_transition, policy, _public(diff.to_dict()))
    entry_total = ("entry-total", diff.left_entry_count == diff.removed_count + diff.changed_count + diff.unchanged_count and diff.right_entry_count == diff.added_count + diff.changed_count + diff.unchanged_count, f"{diff.left_entry_count}->{diff.right_entry_count}", "conserved", "baseline and candidate entry totals are conserved")
    return values[:7] + (entry_total,) + values[8:]


def _rule(value: tuple[str, bool, str, str, str], ordinal: int) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule:
    rule_id, passed, observed, limit, detail = value
    body = {"ordinal": ordinal, "rule_id": rule_id, "passed": passed, "observed": observed, "limit": limit, "detail": detail, "content_address": RULE_PREFIX + ":pending"}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule(**body)
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule(**(body | {"content_address": address_rule(provisional)}))


class DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation:
    FIELDS = EVALUATION_FIELDS

    def __init__(self, evaluation_id: str, version: str, boundary: str, policy_id: str, policy_address: str, policy: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy | Mapping[str, Any], diff_id: str, diff_address: str, left_entry_count: int, right_entry_count: int, direction: str, candidate_release_ready: bool, added_count: int, removed_count: int, changed_count: int, unchanged_count: int, improved_delta: int, regressed_delta: int, state_transition: str, state: str, decision: str, accepted: bool, release_ready: bool, rules: Sequence[DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule | Mapping[str, Any]], rule_count: int, passed_rule_count: int, failed_rule_count: int, content_address: str) -> None:
        self.evaluation_id = _label(evaluation_id, "history diff policy evaluation ID")
        self.version = _text(version, "history diff policy evaluation version")
        self.boundary = _text(boundary, "history diff policy evaluation boundary", 512)
        self.policy_id = _label(policy_id, "history diff policy evaluation policy ID")
        self.policy_address = _address(policy_address, "history diff policy evaluation policy address", POLICY_PREFIX)
        self.policy = policy if isinstance(policy, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy.from_mapping(policy)
        self.diff_id = _label(diff_id, "history diff policy evaluation diff ID")
        self.diff_address = _address(diff_address, "history diff policy evaluation diff address", diff_model.DIFF_PREFIX)
        self.left_entry_count = _count(left_entry_count, "history diff policy evaluation left entry count", diff_model.MAX_ITEMS)
        self.right_entry_count = _count(right_entry_count, "history diff policy evaluation right entry count", diff_model.MAX_ITEMS)
        self.direction = _label(direction, "history diff policy evaluation direction")
        if self.direction not in diff_model.DIRECTIONS:
            raise ValidationError("history diff policy evaluation direction is unsupported")
        self.candidate_release_ready = _bool(candidate_release_ready, "history diff policy evaluation candidate readiness")
        for field in ("added_count", "removed_count", "changed_count"):
            setattr(self, field, _count(locals()[field], f"history diff policy evaluation {field}", diff_model.MAX_ITEMS))
        self.unchanged_count = _count(unchanged_count, "history diff policy evaluation unchanged count", diff_model.MAX_ITEMS)
        self.improved_delta = _signed(improved_delta, "history diff policy evaluation improved delta", diff_model.MAX_ITEMS)
        self.regressed_delta = _signed(regressed_delta, "history diff policy evaluation regressed delta", diff_model.MAX_ITEMS)
        self.state_transition = _label(state_transition, "history diff policy evaluation state transition")
        self.state = _label(state, "history diff policy evaluation state")
        if self.state not in STATES:
            raise ValidationError("history diff policy evaluation state is unsupported")
        self.decision = _label(decision, "history diff policy evaluation decision")
        if self.decision not in DECISIONS:
            raise ValidationError("history diff policy evaluation decision is unsupported")
        self.accepted = _bool(accepted, "history diff policy evaluation acceptance")
        self.release_ready = _bool(release_ready, "history diff policy evaluation release readiness")
        self.rules = tuple(item if isinstance(item, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule) else DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule.from_mapping(item) for item in _sequence(rules, "history diff policy evaluation rules", MAX_RULES))
        self.rule_count = _count(rule_count, "history diff policy evaluation rule count", MAX_RULES)
        self.passed_rule_count = _count(passed_rule_count, "history diff policy evaluation passed rule count", MAX_RULES)
        self.failed_rule_count = _count(failed_rule_count, "history diff policy evaluation failed rule count", MAX_RULES)
        self.content_address = _address(content_address, "history diff policy evaluation address", EVALUATION_PREFIX)
        self._validate()

    def _validate(self) -> None:
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("history diff policy evaluation version or boundary is not current")
        if (self.policy_id, self.policy_address) != (self.policy.policy_id, self.policy.content_address):
            raise ValidationError("history diff policy evaluation policy linkage does not replay")
        if len(self.rules) != self.rule_count or tuple(item.ordinal for item in self.rules) != tuple(range(1, self.rule_count + 1)) or tuple(item.rule_id for item in self.rules) != RULE_IDS:
            raise ValidationError("history diff policy evaluation rules are incomplete or unordered")
        if self.passed_rule_count != sum(item.passed for item in self.rules) or self.failed_rule_count != self.rule_count - self.passed_rule_count:
            raise ValidationError("history diff policy evaluation rule counts do not replay")
        expected_rules = _rule_inputs_for_values(self.left_entry_count, self.right_entry_count, self.direction, self.candidate_release_ready, self.added_count, self.removed_count, self.changed_count, self.unchanged_count, self.improved_delta, self.regressed_delta, self.state_transition, self.policy, True)
        if tuple((rule.rule_id, rule.passed, rule.observed, rule.limit, rule.detail) for rule in self.rules) != tuple((item[0], item[1], item[2], item[3], item[4]) for item in expected_rules):
            raise ValidationError("history diff policy evaluation rules do not replay")
        if self.accepted != (self.state == "eligible") or self.release_ready != (self.accepted and self.decision == "promote"):
            raise ValidationError("history diff policy evaluation readiness does not replay")
        if self.decision != {"eligible": "promote", "review": "hold", "blocked": "block"}[self.state]:
            raise ValidationError("history diff policy evaluation decision does not replay")
        if not _public(self.to_dict()):
            raise ValidationError("history diff policy evaluation crosses the public boundary")
        if not self.content_address.endswith(":pending") and address_evaluation(self) != self.content_address:
            raise ValidationError("history diff policy evaluation address does not replay")

    def to_dict(self) -> dict[str, Any]:
        return {"evaluation_id": self.evaluation_id, "version": self.version, "boundary": self.boundary, "policy_id": self.policy_id, "policy_address": self.policy_address, "policy": self.policy.to_dict(), "diff_id": self.diff_id, "diff_address": self.diff_address, "left_entry_count": self.left_entry_count, "right_entry_count": self.right_entry_count, "direction": self.direction, "candidate_release_ready": self.candidate_release_ready, "added_count": self.added_count, "removed_count": self.removed_count, "changed_count": self.changed_count, "unchanged_count": self.unchanged_count, "improved_delta": self.improved_delta, "regressed_delta": self.regressed_delta, "state_transition": self.state_transition, "state": self.state, "decision": self.decision, "accepted": self.accepted, "release_ready": self.release_ready, "rules": tuple(item.to_dict() for item in self.rules), "rule_count": self.rule_count, "passed_rule_count": self.passed_rule_count, "failed_rule_count": self.failed_rule_count, "content_address": self.content_address}

    def summary(self) -> dict[str, Any]:
        return {field: self.to_dict()[field] for field in self.FIELDS if field != "rules"}

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation:
        value = _mapping(value, "history diff policy evaluation")
        _strict(value, set(cls.FIELDS), "history diff policy evaluation")
        return cls(*(value[field] for field in cls.FIELDS))


def address_evaluation(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) -> str:
    if not isinstance(value, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation):
        raise ValidationError("history diff policy evaluation address requires a typed evaluation")
    return content_hash(value.to_dict() | {"content_address": None}, prefix=EVALUATION_PREFIX)


def evaluate(diff: diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff, *, policy: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy | None = None, evaluation_id: str = EVALUATION_PREFIX) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation:
    if not isinstance(diff, diff_model.DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiff):
        raise ValidationError("history diff policy evaluation requires a typed diff")
    policy = default_policy() if policy is None else policy
    if not isinstance(policy, DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy):
        raise ValidationError("history diff policy must be typed")
    rules = tuple(_rule(item, ordinal) for ordinal, item in enumerate(_rule_inputs(diff, policy), 1))
    passed = sum(item.passed for item in rules)
    hard_failure = not rules[0].passed or not rules[1].passed or not rules[8].passed
    soft_failure = any(not item.passed for item in rules[2:8])
    state = "blocked" if hard_failure else "review" if soft_failure else "eligible"
    decision = {"eligible": "promote", "review": "hold", "blocked": "block"}[state]
    body = {"evaluation_id": evaluation_id, "version": VERSION, "boundary": BOUNDARY, "policy_id": policy.policy_id, "policy_address": policy.content_address, "policy": policy, "diff_id": diff.diff_id, "diff_address": diff.content_address, "left_entry_count": diff.left_entry_count, "right_entry_count": diff.right_entry_count, "direction": diff.direction, "candidate_release_ready": diff.right_release_ready, "added_count": diff.added_count, "removed_count": diff.removed_count, "changed_count": diff.changed_count, "unchanged_count": diff.unchanged_count, "improved_delta": diff.improved_delta, "regressed_delta": diff.regressed_delta, "state_transition": diff.state_transition, "state": state, "decision": decision, "accepted": state == "eligible", "release_ready": state == "eligible", "rules": rules, "rule_count": len(rules), "passed_rule_count": passed, "failed_rule_count": len(rules) - passed}
    provisional = DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation(**body, content_address=EVALUATION_PREFIX + ":pending")
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation(**body, content_address=address_evaluation(provisional))


def policy_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy.from_mapping(value)


def evaluation_from_mapping(value: Mapping[str, Any]) -> DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation:
    return DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation.from_mapping(value)


def evaluation_json(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) -> str:
    return canonical_json(evaluation_from_mapping(value.to_dict()).to_dict())


def evaluation_csv(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) -> str:
    value = evaluation_from_mapping(value.to_dict())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(RULE_FIELDS)
    writer.writerows(tuple(item.to_dict()[field] for field in RULE_FIELDS) for item in value.rules)
    return stream.getvalue()


def render_evaluation_markdown(value: DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation) -> str:
    value = evaluation_from_mapping(value.to_dict())
    lines = ["# Downloaded Data Profile Contract Compatibility Remediation Resolution History Diff Policy Evaluation", "", f"- Decision: `{value.decision}`", f"- State: `{value.state}`", f"- Direction: `{value.direction}`", f"- Rules: `{value.passed_rule_count}/{value.rule_count}`", f"- Diff: `{value.diff_address}`", f"- Address: `{value.content_address}`", "", "| # | rule | passed | observed | limit |", "| ---: | --- | ---: | --- | --- |"]
    lines.extend(f"| {item.ordinal} | `{item.rule_id}` | `{item.passed}` | `{item.observed}` | `{item.limit}` |" for item in value.rules)
    return "\n".join(lines) + "\n"


def policy_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy", "type": "object", "additionalProperties": False, "required": list(POLICY_FIELDS), "properties": {"policy_id": {"type": "string"}, "allowed_directions": {"type": "array", "items": {"enum": list(diff_model.DIRECTIONS)}, "minItems": 1, "maxItems": len(diff_model.DIRECTIONS)}, "require_candidate_ready": {"type": "boolean"}, "max_added_count": {"type": "integer", "minimum": 0}, "max_removed_count": {"type": "integer", "minimum": 0}, "max_changed_count": {"type": "integer", "minimum": 0}, "max_improved_delta": {"type": "integer", "minimum": 0}, "max_regressed_delta": {"type": "integer", "minimum": 0}, "require_state_progression": {"type": "boolean"}, "content_address": {"type": "string"}}}


def rule_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy rule", "type": "object", "additionalProperties": False, "required": list(RULE_FIELDS), "properties": {"ordinal": {"type": "integer", "minimum": 1, "maximum": MAX_RULES}, "rule_id": {"enum": list(RULE_IDS)}, "passed": {"type": "boolean"}, "observed": {"type": "string"}, "limit": {"type": "string"}, "detail": {"type": "string"}, "content_address": {"type": "string"}}}


def evaluation_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Downloaded data profile contract compatibility remediation resolution history diff policy evaluation", "type": "object", "additionalProperties": False, "required": list(EVALUATION_FIELDS), "properties": {"evaluation_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "policy_id": {"type": "string"}, "policy_address": {"type": "string"}, "diff_id": {"type": "string"}, "diff_address": {"type": "string"}, "direction": {"enum": list(diff_model.DIRECTIONS)}, "candidate_release_ready": {"type": "boolean"}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "improved_delta": {"type": "integer"}, "regressed_delta": {"type": "integer"}, "state_transition": {"type": "string"}, "state": {"enum": list(STATES)}, "decision": {"enum": list(DECISIONS)}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "rules": {"type": "array", "items": rule_schema(), "minItems": MAX_RULES, "maxItems": MAX_RULES}, "rule_count": {"type": "integer", "minimum": MAX_RULES, "maximum": MAX_RULES}, "passed_rule_count": {"type": "integer", "minimum": 0, "maximum": MAX_RULES}, "failed_rule_count": {"type": "integer", "minimum": 0, "maximum": MAX_RULES}, "content_address": {"type": "string"}}}


def capabilities() -> dict[str, Any]:
    return {"public": True, "independent": True, "value_free": True, "version": VERSION, "states": STATES, "decisions": DECISIONS, "rule_ids": RULE_IDS, "operations": ("default_policy", "evaluate", "policy_from_mapping", "evaluation_from_mapping", "evaluation_json", "evaluation_csv", "render_evaluation_markdown"), "limits": {"max_rules": MAX_RULES}}


__all__ = ["BOUNDARY", "DECISIONS", "DEFAULT_POLICY_ID", "EVALUATION_FIELDS", "EVALUATION_PREFIX", "MAX_RULES", "POLICY_FIELDS", "POLICY_PREFIX", "RULE_FIELDS", "RULE_IDS", "RULE_PREFIX", "STATES", "VERSION", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicy", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyEvaluation", "DownloadedDataProfileContractCompatibilityRemediationResolutionHistoryDiffPolicyRule", "address_evaluation", "address_policy", "address_rule", "capabilities", "default_policy", "evaluate", "evaluation_csv", "evaluation_from_mapping", "evaluation_json", "evaluation_schema", "policy_from_mapping", "policy_schema", "render_evaluation_markdown", "rule_schema"]
