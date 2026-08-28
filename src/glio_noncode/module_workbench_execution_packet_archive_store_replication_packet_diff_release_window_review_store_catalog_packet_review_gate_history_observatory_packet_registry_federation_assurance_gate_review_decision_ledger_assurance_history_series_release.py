"""Portable release handoffs for decision-assurance history series.

This module packages a verified history series, its policy, its evaluated
policy result, and an addressed release receipt into one deterministic
transport directory.  The package is deliberately independent of the source
filesystem: the public projection contains content addresses, bounded typed
summaries, and fixed-vocabulary release stages only.

The package has two integrity planes.  The typed release receipt proves that
the supplied series, policy, and evaluation agree and that readiness follows
the declared stage rules.  The on-disk loader then recomputes every canonical
document byte address, manifest address, nested linkage, exact file set, and
public-boundary constraint.  A separate diff projection compares two release
receipts without treating a changed address as an explanation by itself.
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
from . import module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_packet_registry_federation_assurance_gate_review_decision_ledger_assurance_history_series_policy as policy_model
from .errors import ValidationError
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

DecisionAssuranceHistorySeries = series_model.DecisionAssuranceHistorySeries
DecisionAssuranceHistorySeriesPolicy = policy_model.DecisionAssuranceHistorySeriesPolicy
DecisionAssuranceHistorySeriesPolicyEvaluation = policy_model.DecisionAssuranceHistorySeriesPolicyEvaluation

VERSION = policy_model.VERSION + "-release-v1"
BOUNDARY = series_model.BOUNDARY + "_release"
RELEASE_PREFIX = series_model.SERIES_PREFIX + "-release"
PACKAGE_PREFIX = RELEASE_PREFIX + "-package"
STAGE_PREFIX = RELEASE_PREFIX + "-stage"
DIFF_PREFIX = RELEASE_PREFIX + "-diff"
DIFF_ITEM_PREFIX = DIFF_PREFIX + "-item"
MANIFEST_PREFIX = RELEASE_PREFIX + "-manifest"
DIFF_MANIFEST_PREFIX = DIFF_PREFIX + "-manifest"
MANIFEST_NAME = "manifest.json"
SERIES_NAME = "series.json"
POLICY_NAME = "policy.json"
EVALUATION_NAME = "evaluation.json"
RELEASE_NAME = "release.json"
FILES = (MANIFEST_NAME, SERIES_NAME, POLICY_NAME, EVALUATION_NAME, RELEASE_NAME)
DIFF_NAME = "diff.json"
DIFF_FILES = (MANIFEST_NAME, DIFF_NAME)
DEFAULT_RELEASE_ID = "glio-noncode-decision-assurance-history-series-release"
DEFAULT_PACKAGE_ID = "glio-noncode-decision-assurance-history-series-release-package"
DEFAULT_DIFF_ID = "glio-noncode-decision-assurance-history-series-release-diff"
MAX_STAGES = 16
MAX_DIFF_ITEMS = 64
MAX_QUERY_ITEMS = 4096

_FORBIDDEN_KEYS = frozenset({"agent", "assistant", "author", "email", "generated_by", "language", "model", "private", "secret", "token", "user"})


class SeriesReleaseState(StrEnum):
    """Release outcome derived from required and optional stages."""

    READY = "ready"
    HOLD = "hold"
    BLOCKED = "blocked"


class SeriesReleaseDiffAction(StrEnum):
    """Set relationship for one release or stage key."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class SeriesReleaseDiffDirection(StrEnum):
    """Readiness direction inferred from two verified release receipts."""

    UNCHANGED = "unchanged"
    IMPROVED = "improved"
    REGRESSED = "regressed"
    CHANGED = "changed"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be an address")
    return value


def _count(value: Any, field: str, maximum: int = MAX_QUERY_ITEMS) -> int:
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
    unknown = set(value) - allowed
    if unknown:
        raise ValidationError(f"{field} contains unknown fields: {sorted(unknown)}")


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(str(key).casefold() not in _FORBIDDEN_KEYS and _public(key) and _public(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def _state(value: Any, field: str = "series release state") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in SeriesReleaseState}:
        raise ValidationError(f"{field} is invalid")
    return value


def _action(value: Any, field: str = "release diff action") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in SeriesReleaseDiffAction}:
        raise ValidationError(f"{field} is invalid")
    return value


def _direction(value: Any, field: str = "release diff direction") -> str:
    value = _text(value, field, 32)
    if value not in {item.value for item in SeriesReleaseDiffDirection}:
        raise ValidationError(f"{field} is invalid")
    return value


class DecisionAssuranceHistorySeriesReleaseStage:
    """One independently addressed release closure stage."""

    def __init__(self, ordinal: int, stage_id: str, kind: str, required: bool, passed: bool, detail: str, evidence_address: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.stage_id = stage_id
        self.kind = kind
        self.required = required
        self.passed = passed
        self.detail = detail
        self.evidence_address = evidence_address
        self.content_address = content_address
        self._validate()

    @property
    def state(self) -> str:
        return "passed" if self.passed else SeriesReleaseState.BLOCKED.value if self.required else SeriesReleaseState.HOLD.value

    def _validate(self) -> None:
        _count(self.ordinal, "release stage ordinal", MAX_STAGES - 1)
        _text(self.stage_id, "release stage ID", 512)
        _text(self.kind, "release stage kind", 128)
        _bool(self.required, "release stage required")
        _bool(self.passed, "release stage passed")
        _text(self.detail, "release stage detail", 1024)
        _address(self.evidence_address, "release stage evidence address")
        _address(self.content_address, "release stage address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_stage(self) != self.content_address:
            raise ValidationError("release stage address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("release stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "stage_id": self.stage_id, "kind": self.kind, "required": self.required, "passed": self.passed, "state": self.state, "detail": self.detail, "evidence_address": self.evidence_address, "content_address": self.content_address}


def address_decision_assurance_history_series_release_stage(value: DecisionAssuranceHistorySeriesReleaseStage) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=STAGE_PREFIX)


class DecisionAssuranceHistorySeriesRelease:
    """Addressed readiness receipt for one series/policy/evaluation triple."""

    def __init__(self, release_id: str, version: str, boundary: str, series_id: str, series_address: str, policy_id: str, policy_address: str, evaluation_address: str, stage_count: int, passed_count: int, warning_count: int, blocker_count: int, state: str, accepted: bool, release_ready: bool, stages: Sequence[DecisionAssuranceHistorySeriesReleaseStage], content_address: str) -> None:
        self.release_id = release_id
        self.version = version
        self.boundary = boundary
        self.series_id = series_id
        self.series_address = series_address
        self.policy_id = policy_id
        self.policy_address = policy_address
        self.evaluation_address = evaluation_address
        self.stage_count = stage_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.stages = tuple(stages)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.release_id, "series release ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("series release contract is invalid")
        _text(self.series_id, "series ID", 256)
        _address(self.series_address, "series address")
        _text(self.policy_id, "policy ID", 256)
        _address(self.policy_address, "policy address")
        _address(self.evaluation_address, "evaluation address")
        _count(self.stage_count, "release stage count", MAX_STAGES)
        _count(self.passed_count, "release passed count", MAX_STAGES)
        _count(self.warning_count, "release warning count", MAX_STAGES)
        _count(self.blocker_count, "release blocker count", MAX_STAGES)
        if self.stage_count != len(self.stages) or self.passed_count + self.warning_count + self.blocker_count != self.stage_count:
            raise ValidationError("release stage counts are not conserved")
        for ordinal, stage in enumerate(self.stages):
            if not isinstance(stage, DecisionAssuranceHistorySeriesReleaseStage) or stage.ordinal != ordinal:
                raise ValidationError("release stages must have contiguous ordinals")
            if address_decision_assurance_history_series_release_stage(stage) != stage.content_address:
                raise ValidationError("release stage address mismatch")
        expected_state = SeriesReleaseState.BLOCKED.value if self.blocker_count else SeriesReleaseState.HOLD.value if self.warning_count else SeriesReleaseState.READY.value
        if self.state != expected_state:
            raise ValidationError("series release state is invalid")
        if self.accepted != (self.blocker_count == 0) or self.release_ready != (self.blocker_count == 0 and self.warning_count == 0):
            raise ValidationError("series release readiness is invalid")
        _address(self.content_address, "series release address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release(self) != self.content_address:
            raise ValidationError("series release address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series release crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"release_id": self.release_id, "version": self.version, "boundary": self.boundary, "series_id": self.series_id, "series_address": self.series_address, "policy_id": self.policy_id, "policy_address": self.policy_address, "evaluation_address": self.evaluation_address, "stage_count": self.stage_count, "passed_count": self.passed_count, "warning_count": self.warning_count, "blocker_count": self.blocker_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_stages:
            body["stages"] = [stage.to_dict() for stage in self.stages]
        return body


def address_decision_assurance_history_series_release(value: DecisionAssuranceHistorySeriesRelease) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RELEASE_PREFIX)


def _release_stage(ordinal: int, kind: str, required: bool, passed: bool, detail: str, evidence_address: str) -> DecisionAssuranceHistorySeriesReleaseStage:
    body = {"ordinal": ordinal, "stage_id": f"{RELEASE_PREFIX}:{kind}", "kind": kind, "required": required, "passed": passed, "detail": detail, "evidence_address": evidence_address, "content_address": "pending:release-stage"}
    provisional = DecisionAssuranceHistorySeriesReleaseStage(**body)
    body["content_address"] = address_decision_assurance_history_series_release_stage(provisional)
    return DecisionAssuranceHistorySeriesReleaseStage(**body)


def build_decision_assurance_history_series_release(series: DecisionAssuranceHistorySeries, policy: DecisionAssuranceHistorySeriesPolicy, evaluation: DecisionAssuranceHistorySeriesPolicyEvaluation | None = None, *, release_id: str = DEFAULT_RELEASE_ID) -> DecisionAssuranceHistorySeriesRelease:
    series_model.verify_decision_assurance_history_series(series)
    policy_model.verify_decision_assurance_history_series_policy(policy)
    selected_evaluation = evaluation or policy_model.evaluate_decision_assurance_history_series_policy(series, policy)
    policy_model.verify_decision_assurance_history_series_policy_evaluation(selected_evaluation)
    if selected_evaluation.series_address != series.content_address or selected_evaluation.policy.content_address != policy.content_address:
        raise ValidationError("series release inputs are not linked")
    replay = series_model.replay_decision_assurance_history_series(series)
    series_replayed = replay.accepted and replay.release_ready
    stages = (
        _release_stage(0, "series-replay", True, series_replayed, "series replay independently reconstructs its retained observations", series.content_address),
        _release_stage(1, "policy-verification", True, policy_model.address_decision_assurance_history_series_policy(policy) == policy.content_address, "policy address and bounded rule contract are valid", policy.content_address),
        _release_stage(2, "evaluation-verification", True, policy_model.address_decision_assurance_history_series_policy_evaluation(selected_evaluation) == selected_evaluation.content_address, "policy evaluation checks and receipt are valid", selected_evaluation.content_address),
        _release_stage(3, "component-linkage", True, selected_evaluation.series_address == series.content_address and selected_evaluation.policy.content_address == policy.content_address, "series, policy, and evaluation addresses agree", selected_evaluation.content_address),
        _release_stage(4, "evaluation-acceptance", True, selected_evaluation.accepted, "required policy rules contain no blockers", selected_evaluation.content_address),
        _release_stage(5, "evaluation-release-readiness", False, selected_evaluation.release_ready, "all required and optional policy rules are ready", selected_evaluation.content_address),
        _release_stage(6, "public-boundary", True, _public(series.to_dict()) and _public(policy.to_dict()) and _public(selected_evaluation.to_dict()), "all transported projections remain public and path-free", series.content_address),
        _release_stage(7, "transport-contract", True, tuple(FILES) == (MANIFEST_NAME, SERIES_NAME, POLICY_NAME, EVALUATION_NAME, RELEASE_NAME), "release package has a fixed five-file contract", selected_evaluation.content_address),
    )
    passed = sum(stage.passed for stage in stages)
    warning = sum(not stage.passed and not stage.required for stage in stages)
    blocker = sum(not stage.passed and stage.required for stage in stages)
    state = SeriesReleaseState.BLOCKED.value if blocker else SeriesReleaseState.HOLD.value if warning else SeriesReleaseState.READY.value
    body = {"release_id": release_id, "version": VERSION, "boundary": BOUNDARY, "series_id": series.series_id, "series_address": series.content_address, "policy_id": policy.policy_id, "policy_address": policy.content_address, "evaluation_address": selected_evaluation.content_address, "stage_count": len(stages), "passed_count": passed, "warning_count": warning, "blocker_count": blocker, "state": state, "accepted": blocker == 0, "release_ready": blocker == 0 and warning == 0, "stages": stages, "content_address": "pending:series-release"}
    provisional = DecisionAssuranceHistorySeriesRelease(**body)
    body["content_address"] = address_decision_assurance_history_series_release(provisional)
    return DecisionAssuranceHistorySeriesRelease(**body)


def verify_decision_assurance_history_series_release(value: DecisionAssuranceHistorySeriesRelease) -> DecisionAssuranceHistorySeriesRelease:
    if not isinstance(value, DecisionAssuranceHistorySeriesRelease):
        raise ValidationError("series release verification requires a typed release")
    value._validate()
    if address_decision_assurance_history_series_release(value) != value.content_address:
        raise ValidationError("series release address mismatch")
    return value


def decision_assurance_history_series_release_stage_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseStage:
    body = dict(_mapping(value, "series release stage"))
    _strict(body, {"ordinal", "stage_id", "kind", "required", "passed", "state", "detail", "evidence_address", "content_address"}, "series release stage")
    if body.get("state") != ("passed" if body.get("passed") else SeriesReleaseState.BLOCKED.value if body.get("required") else SeriesReleaseState.HOLD.value):
        raise ValidationError("series release stage state is invalid")
    body.pop("state")
    stage = DecisionAssuranceHistorySeriesReleaseStage(**body)
    if address_decision_assurance_history_series_release_stage(stage) != stage.content_address:
        raise ValidationError("series release stage address mismatch")
    return stage


def decision_assurance_history_series_release_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesRelease:
    body = dict(_mapping(value, "series release"))
    _strict(body, {"release_id", "version", "boundary", "series_id", "series_address", "policy_id", "policy_address", "evaluation_address", "stage_count", "passed_count", "warning_count", "blocker_count", "state", "accepted", "release_ready", "stages", "content_address"}, "series release")
    body["stages"] = tuple(decision_assurance_history_series_release_stage_from_mapping(item) for item in _mapping_sequence(body["stages"], "series release stages"))
    return verify_decision_assurance_history_series_release(DecisionAssuranceHistorySeriesRelease(**body))


class DecisionAssuranceHistorySeriesReleasePackage:
    """Complete typed bundle carried by the five-file release transport."""

    def __init__(self, package_id: str, version: str, boundary: str, series: DecisionAssuranceHistorySeries, policy: DecisionAssuranceHistorySeriesPolicy, evaluation: DecisionAssuranceHistorySeriesPolicyEvaluation, release: DecisionAssuranceHistorySeriesRelease, content_address: str) -> None:
        self.package_id = package_id
        self.version = version
        self.boundary = boundary
        self.series = series
        self.policy = policy
        self.evaluation = evaluation
        self.release = release
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.package_id, "series release package ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("series release package contract is invalid")
        series_model.verify_decision_assurance_history_series(self.series)
        policy_model.verify_decision_assurance_history_series_policy(self.policy)
        policy_model.verify_decision_assurance_history_series_policy_evaluation(self.evaluation)
        verify_decision_assurance_history_series_release(self.release)
        if self.evaluation.series_address != self.series.content_address or self.evaluation.policy.content_address != self.policy.content_address:
            raise ValidationError("series release package component linkage is invalid")
        if self.release.series_address != self.series.content_address or self.release.policy_address != self.policy.content_address or self.release.evaluation_address != self.evaluation.content_address:
            raise ValidationError("series release package receipt linkage is invalid")
        _address(self.content_address, "series release package address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_package(self) != self.content_address:
            raise ValidationError("series release package address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("series release package crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "version": self.version, "boundary": self.boundary, "series_id": self.series.series_id, "series_address": self.series.content_address, "policy_id": self.policy.policy_id, "policy_address": self.policy.content_address, "evaluation_address": self.evaluation.content_address, "release_id": self.release.release_id, "release_address": self.release.content_address, "state": self.release.state, "accepted": self.release.accepted, "release_ready": self.release.release_ready, "content_address": self.content_address}

    def to_dict(self) -> dict[str, Any]:
        return {"package_id": self.package_id, "version": self.version, "boundary": self.boundary, "series": self.series.to_dict(), "policy": self.policy.to_dict(), "evaluation": self.evaluation.to_dict(), "release": self.release.to_dict(), "content_address": self.content_address}


def address_decision_assurance_history_series_release_package(value: DecisionAssuranceHistorySeriesReleasePackage) -> str:
    return content_hash(value.summary() | {"content_address": None}, prefix=PACKAGE_PREFIX)


def build_decision_assurance_history_series_release_package(series: DecisionAssuranceHistorySeries, policy: DecisionAssuranceHistorySeriesPolicy | None = None, evaluation: DecisionAssuranceHistorySeriesPolicyEvaluation | None = None, *, package_id: str = DEFAULT_PACKAGE_ID, release_id: str = DEFAULT_RELEASE_ID) -> DecisionAssuranceHistorySeriesReleasePackage:
    selected_policy = policy or policy_model.default_decision_assurance_history_series_policy()
    selected_evaluation = evaluation or policy_model.evaluate_decision_assurance_history_series_policy(series, selected_policy)
    release = build_decision_assurance_history_series_release(series, selected_policy, selected_evaluation, release_id=release_id)
    body = {"package_id": package_id, "version": VERSION, "boundary": BOUNDARY, "series": series, "policy": selected_policy, "evaluation": selected_evaluation, "release": release, "content_address": "pending:series-release-package"}
    provisional = DecisionAssuranceHistorySeriesReleasePackage(**body)
    body["content_address"] = address_decision_assurance_history_series_release_package(provisional)
    return DecisionAssuranceHistorySeriesReleasePackage(**body)


def verify_decision_assurance_history_series_release_package(value: DecisionAssuranceHistorySeriesReleasePackage) -> DecisionAssuranceHistorySeriesReleasePackage:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleasePackage):
        raise ValidationError("series release package verification requires a typed package")
    value._validate()
    if address_decision_assurance_history_series_release_package(value) != value.content_address:
        raise ValidationError("series release package address mismatch")
    return value


def build_decision_assurance_history_series_release_package_from_directories(series_directory: str | Path, evaluation_directory: str | Path | None = None, *, package_id: str = DEFAULT_PACKAGE_ID, release_id: str = DEFAULT_RELEASE_ID, policy_id: str | None = None) -> DecisionAssuranceHistorySeriesReleasePackage:
    series = series_model.load_decision_assurance_history_series(series_directory)
    if evaluation_directory is None:
        selected_policy = policy_model.default_decision_assurance_history_series_policy(policy_id=policy_id or policy_model.DEFAULT_POLICY_ID)
        evaluation = policy_model.evaluate_decision_assurance_history_series_policy(series, selected_policy)
    else:
        evaluation = policy_model.load_decision_assurance_history_series_policy_evaluation(evaluation_directory)
        selected_policy = evaluation.policy
        if policy_id is not None and selected_policy.policy_id != policy_id:
            raise ValidationError("series release policy ID does not match evaluation")
    return build_decision_assurance_history_series_release_package(series, selected_policy, evaluation, package_id=package_id, release_id=release_id)


def _csv_text(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def decision_assurance_history_series_release_json(value: DecisionAssuranceHistorySeriesRelease) -> str:
    return canonical_json(verify_decision_assurance_history_series_release(value).to_dict())


def decision_assurance_history_series_release_csv(value: DecisionAssuranceHistorySeriesRelease) -> str:
    value = verify_decision_assurance_history_series_release(value)
    return _csv_text([stage.to_dict() for stage in value.stages], ("ordinal", "stage_id", "kind", "required", "passed", "state", "detail", "evidence_address", "content_address"))


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


def render_decision_assurance_history_series_release_markdown(value: DecisionAssuranceHistorySeriesRelease) -> str:
    value = verify_decision_assurance_history_series_release(value)
    return _markdown("Decision Assurance History Series Release", value.summary(), [stage.to_dict() for stage in value.stages])


def decision_assurance_history_series_release_package_json(value: DecisionAssuranceHistorySeriesReleasePackage) -> str:
    return canonical_json(verify_decision_assurance_history_series_release_package(value).to_dict())


def decision_assurance_history_series_release_package_csv(value: DecisionAssuranceHistorySeriesReleasePackage) -> str:
    value = verify_decision_assurance_history_series_release_package(value)
    return _csv_text([value.summary()], ("package_id", "series_id", "series_address", "policy_id", "policy_address", "evaluation_address", "release_id", "release_address", "state", "accepted", "release_ready", "content_address"))


def render_decision_assurance_history_series_release_package_markdown(value: DecisionAssuranceHistorySeriesReleasePackage) -> str:
    value = verify_decision_assurance_history_series_release_package(value)
    return _markdown("Decision Assurance History Series Release Package", value.summary(), [value.release.summary()])


class SeriesReleaseQuery:
    """Bounded query over a release receipt."""

    RESOURCES = ("summary", "stages", "failed", "passed", "warnings", "blockers")

    def __init__(self, resource: str = "summary", *, offset: int = 0, limit: int = 50, text: str | None = None) -> None:
        self.resource = _text(resource, "release query resource", 32)
        if self.resource not in self.RESOURCES:
            raise ValidationError("release query resource is invalid")
        self.offset = _count(offset, "release query offset")
        self.limit = _count(limit, "release query limit", 512)
        if self.limit < 1:
            raise ValidationError("release query limit must be positive")
        self.text = None if text is None else _text(text, "release query text", 512)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "offset": self.offset, "limit": self.limit, "text": self.text}


class SeriesReleaseQueryResult:
    """Addressed deterministic page over release stages."""

    def __init__(self, release_address: str, query: SeriesReleaseQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.release_address = release_address
        self.query = query
        self.total_count = total_count
        self.returned_count = returned_count
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.release_address, "release query release address")
        _count(self.total_count, "release query total")
        _count(self.returned_count, "release query returned", self.total_count)
        if self.returned_count != len(self.items):
            raise ValidationError("release query returned count is invalid")
        _address(self.content_address, "release query address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_query(self) != self.content_address:
            raise ValidationError("release query address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"release_address": self.release_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "content_address": self.content_address}


def address_decision_assurance_history_series_release_query(value: SeriesReleaseQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=RELEASE_PREFIX + "-query")


def query_decision_assurance_history_series_release(value: DecisionAssuranceHistorySeriesRelease, query: SeriesReleaseQuery | None = None, **kwargs: Any) -> SeriesReleaseQueryResult:
    verify_decision_assurance_history_series_release(value)
    if query is not None and kwargs:
        raise ValidationError("release query cannot combine typed query and keyword filters")
    selected = query or SeriesReleaseQuery(**kwargs)
    if selected.resource == "summary":
        rows = [value.summary()]
    else:
        rows = [stage.to_dict() for stage in value.stages]
        if selected.resource == "failed":
            rows = [row for row in rows if not row["passed"]]
        elif selected.resource == "passed":
            rows = [row for row in rows if row["passed"]]
        elif selected.resource == "warnings":
            rows = [row for row in rows if not row["passed"] and not row["required"]]
        elif selected.resource == "blockers":
            rows = [row for row in rows if not row["passed"] and row["required"]]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    total = len(rows)
    page = rows[selected.offset : selected.offset + selected.limit]
    body = {"release_address": value.content_address, "query": selected, "total_count": total, "returned_count": len(page), "items": page, "content_address": "pending:release-query"}
    provisional = SeriesReleaseQueryResult(**body)
    body["content_address"] = address_decision_assurance_history_series_release_query(provisional)
    return SeriesReleaseQueryResult(**body)


def decision_assurance_history_series_release_query_json(value: SeriesReleaseQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_history_series_release_query_csv(value: SeriesReleaseQueryResult) -> str:
    fields = ("ordinal", "stage_id", "kind", "required", "passed", "state", "detail", "evidence_address", "content_address")
    return _csv_text(value.items, fields)


def render_decision_assurance_history_series_release_query_markdown(value: SeriesReleaseQueryResult) -> str:
    return _markdown("Decision Assurance History Series Release Query", {"release_address": value.release_address, "resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def decision_assurance_history_series_release_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release", "type": "object", "additionalProperties": False, "properties": {"release_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "series_id": {"type": "string"}, "series_address": {"type": "string"}, "policy_id": {"type": "string"}, "policy_address": {"type": "string"}, "evaluation_address": {"type": "string"}, "stage_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "passed_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "warning_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "blocker_count": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "state": {"enum": [item.value for item in SeriesReleaseState]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "stages": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["release_id", "version", "boundary", "series_id", "series_address", "policy_id", "policy_address", "evaluation_address", "stage_count", "state", "accepted", "release_ready", "stages", "content_address"]}


def decision_assurance_history_series_release_stage_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Stage", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_STAGES}, "stage_id": {"type": "string"}, "kind": {"type": "string"}, "required": {"type": "boolean"}, "passed": {"type": "boolean"}, "state": {"enum": ["passed", "hold", "blocked"]}, "detail": {"type": "string"}, "evidence_address": {"type": "string"}, "content_address": {"type": "string"}}, "required": ["ordinal", "stage_id", "kind", "required", "passed", "state", "detail", "evidence_address", "content_address"]}


def decision_assurance_history_series_release_package_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Package", "type": "object", "additionalProperties": False, "properties": {"package_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "series": {"type": "object"}, "policy": {"type": "object"}, "evaluation": {"type": "object"}, "release": {"$ref": "#/definitions/release"}, "content_address": {"type": "string"}}, "required": ["package_id", "version", "boundary", "series", "policy", "evaluation", "release", "content_address"], "definitions": {"release": {"$ref": "#/definitions/release-body"}, "release-body": {"type": "object", "required": ["release_id", "series_address", "policy_address", "evaluation_address", "content_address"]}}}


def decision_assurance_history_series_release_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": list(SeriesReleaseQuery.RESOURCES)}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 512}, "text": {"type": ["string", "null"]}}, "required": ["resource", "offset", "limit"]}


def decision_assurance_history_series_release_diff_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Diff", "type": "object", "additionalProperties": False, "properties": {"diff_id": {"type": "string"}, "version": {"const": VERSION}, "boundary": {"const": BOUNDARY}, "baseline_address": {"type": "string"}, "candidate_address": {"type": "string"}, "item_count": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS}, "added_count": {"type": "integer", "minimum": 0}, "removed_count": {"type": "integer", "minimum": 0}, "unchanged_count": {"type": "integer", "minimum": 0}, "changed_count": {"type": "integer", "minimum": 0}, "improved_count": {"type": "integer", "minimum": 0}, "regressed_count": {"type": "integer", "minimum": 0}, "state": {"enum": [item.value for item in SeriesReleaseDiffDirection]}, "accepted": {"type": "boolean"}, "release_ready": {"type": "boolean"}, "items": {"type": "array"}, "content_address": {"type": "string"}}, "required": ["diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "state", "accepted", "release_ready", "items", "content_address"]}


def decision_assurance_history_series_release_diff_item_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Diff Item", "type": "object", "additionalProperties": False, "properties": {"ordinal": {"type": "integer", "minimum": 0, "maximum": MAX_DIFF_ITEMS}, "key": {"type": "string"}, "action": {"enum": [item.value for item in SeriesReleaseDiffAction]}, "direction": {"enum": [item.value for item in SeriesReleaseDiffDirection]}, "baseline_value": {}, "candidate_value": {}, "detail": {"type": "string"}, "content_address": {"type": "string"}}, "required": ["ordinal", "key", "action", "direction", "detail", "content_address"]}


def decision_assurance_history_series_release_diff_query_schema() -> dict[str, Any]:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Decision Assurance History Series Release Diff Query", "type": "object", "additionalProperties": False, "properties": {"resource": {"enum": list(SeriesReleaseDiffQuery.RESOURCES)}, "offset": {"type": "integer", "minimum": 0}, "limit": {"type": "integer", "minimum": 1, "maximum": 512}, "text": {"type": ["string", "null"]}}, "required": ["resource", "offset", "limit"]}


def capabilities() -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "release": {"stages": ["series-replay", "policy-verification", "evaluation-verification", "component-linkage", "evaluation-acceptance", "evaluation-release-readiness", "public-boundary", "transport-contract"], "states": [item.value for item in SeriesReleaseState]}, "package": {"files": list(FILES), "exact_file_set": True, "canonical_json": True, "atomic_write": True, "offline_load": True}, "query": {"resources": list(SeriesReleaseQuery.RESOURCES), "pagination": True, "text_filter": True}, "diff": {"actions": [item.value for item in SeriesReleaseDiffAction], "directions": [item.value for item in SeriesReleaseDiffDirection], "maximum_items": MAX_DIFF_ITEMS}}


class DecisionAssuranceHistorySeriesReleaseDiffItem:
    """One deterministic change record between two release receipts."""

    def __init__(self, ordinal: int, key: str, action: str, direction: str, baseline_value: Mapping[str, Any] | None, candidate_value: Mapping[str, Any] | None, detail: str, content_address: str) -> None:
        self.ordinal = ordinal
        self.key = key
        self.action = action
        self.direction = direction
        self.baseline_value = None if baseline_value is None else dict(baseline_value)
        self.candidate_value = None if candidate_value is None else dict(candidate_value)
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "release diff item ordinal", MAX_DIFF_ITEMS - 1)
        _text(self.key, "release diff item key", 256)
        _action(self.action)
        _direction(self.direction)
        if self.baseline_value is not None and not _public(self.baseline_value) or self.candidate_value is not None and not _public(self.candidate_value):
            raise ValidationError("release diff item crosses the public boundary")
        _text(self.detail, "release diff item detail", 1024)
        _address(self.content_address, "release diff item address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_diff_item(self) != self.content_address:
            raise ValidationError("release diff item address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"ordinal": self.ordinal, "key": self.key, "action": self.action, "direction": self.direction, "baseline_value": self.baseline_value, "candidate_value": self.candidate_value, "detail": self.detail, "content_address": self.content_address}


def address_decision_assurance_history_series_release_diff_item(value: DecisionAssuranceHistorySeriesReleaseDiffItem) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_ITEM_PREFIX)


class DecisionAssuranceHistorySeriesReleaseDiff:
    """Addressed comparison of two release receipts."""

    def __init__(self, diff_id: str, version: str, boundary: str, baseline_address: str, candidate_address: str, item_count: int, added_count: int, removed_count: int, unchanged_count: int, changed_count: int, improved_count: int, regressed_count: int, state: str, accepted: bool, release_ready: bool, items: Sequence[DecisionAssuranceHistorySeriesReleaseDiffItem], content_address: str) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.baseline_address = baseline_address
        self.candidate_address = candidate_address
        self.item_count = item_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.improved_count = improved_count
        self.regressed_count = regressed_count
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.items = tuple(items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "release diff ID", 256)
        if self.version != VERSION or self.boundary != BOUNDARY:
            raise ValidationError("release diff contract is invalid")
        _address(self.baseline_address, "release diff baseline address")
        _address(self.candidate_address, "release diff candidate address")
        _count(self.item_count, "release diff item count", MAX_DIFF_ITEMS)
        for count, field in ((self.added_count, "added count"), (self.removed_count, "removed count"), (self.unchanged_count, "unchanged count"), (self.changed_count, "changed count"), (self.improved_count, "improved count"), (self.regressed_count, "regressed count")):
            _count(count, field, MAX_DIFF_ITEMS)
        if self.item_count != len(self.items) or self.added_count + self.removed_count + self.unchanged_count + self.changed_count != self.item_count:
            raise ValidationError("release diff counts are not conserved")
        for ordinal, item in enumerate(self.items):
            if not isinstance(item, DecisionAssuranceHistorySeriesReleaseDiffItem) or item.ordinal != ordinal:
                raise ValidationError("release diff item ordinals are invalid")
            if address_decision_assurance_history_series_release_diff_item(item) != item.content_address:
                raise ValidationError("release diff item address mismatch")
        _direction(self.state, "release diff state")
        if self.accepted != (self.state != SeriesReleaseDiffDirection.REGRESSED.value) or self.release_ready != (self.state in {SeriesReleaseDiffDirection.UNCHANGED.value, SeriesReleaseDiffDirection.IMPROVED.value}):
            raise ValidationError("release diff readiness is invalid")
        _address(self.content_address, "release diff address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_diff(self) != self.content_address:
            raise ValidationError("release diff address mismatch")
        if not _public(self.to_dict()):
            raise ValidationError("release diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {"diff_id": self.diff_id, "version": self.version, "boundary": self.boundary, "baseline_address": self.baseline_address, "candidate_address": self.candidate_address, "item_count": self.item_count, "added_count": self.added_count, "removed_count": self.removed_count, "unchanged_count": self.unchanged_count, "changed_count": self.changed_count, "improved_count": self.improved_count, "regressed_count": self.regressed_count, "state": self.state, "accepted": self.accepted, "release_ready": self.release_ready, "content_address": self.content_address}

    def to_dict(self, *, include_items: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_items:
            body["items"] = [item.to_dict() for item in self.items]
        return body


def address_decision_assurance_history_series_release_diff(value: DecisionAssuranceHistorySeriesReleaseDiff) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX)


def _release_records(value: DecisionAssuranceHistorySeriesRelease) -> dict[str, Mapping[str, Any]]:
    return {"release": value.summary(), **{f"stage:{stage.kind}": stage.to_dict() for stage in value.stages}}


def _record_ready(value: Mapping[str, Any]) -> bool:
    return bool(value.get("release_ready", value.get("passed", False)))


def _diff_direction(action: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> str:
    if action == SeriesReleaseDiffAction.UNCHANGED.value:
        return SeriesReleaseDiffDirection.UNCHANGED.value
    if action == SeriesReleaseDiffAction.ADDED.value:
        return SeriesReleaseDiffDirection.IMPROVED.value if candidate is not None and _record_ready(candidate) else SeriesReleaseDiffDirection.CHANGED.value
    if action == SeriesReleaseDiffAction.REMOVED.value:
        return SeriesReleaseDiffDirection.REGRESSED.value if baseline is not None and _record_ready(baseline) else SeriesReleaseDiffDirection.CHANGED.value
    if baseline is not None and candidate is not None:
        before = _record_ready(baseline)
        after = _record_ready(candidate)
        if not before and after:
            return SeriesReleaseDiffDirection.IMPROVED.value
        if before and not after:
            return SeriesReleaseDiffDirection.REGRESSED.value
    return SeriesReleaseDiffDirection.CHANGED.value


def _diff_item(ordinal: int, key: str, action: str, baseline: Mapping[str, Any] | None, candidate: Mapping[str, Any] | None) -> DecisionAssuranceHistorySeriesReleaseDiffItem:
    direction = _diff_direction(action, baseline, candidate)
    detail = f"{key} is {action}"
    body = {"ordinal": ordinal, "key": key, "action": action, "direction": direction, "baseline_value": baseline, "candidate_value": candidate, "detail": detail, "content_address": "pending:release-diff-item"}
    provisional = DecisionAssuranceHistorySeriesReleaseDiffItem(**body)
    body["content_address"] = address_decision_assurance_history_series_release_diff_item(provisional)
    return DecisionAssuranceHistorySeriesReleaseDiffItem(**body)


def build_decision_assurance_history_series_release_diff(baseline: DecisionAssuranceHistorySeriesRelease, candidate: DecisionAssuranceHistorySeriesRelease, *, diff_id: str = DEFAULT_DIFF_ID) -> DecisionAssuranceHistorySeriesReleaseDiff:
    verify_decision_assurance_history_series_release(baseline)
    verify_decision_assurance_history_series_release(candidate)
    baseline_records = _release_records(baseline)
    candidate_records = _release_records(candidate)
    keys = tuple(sorted(set(baseline_records) | set(candidate_records)))
    if len(keys) > MAX_DIFF_ITEMS:
        raise ValidationError("series release diff is larger than the bounded item limit")
    items = []
    for ordinal, key in enumerate(keys):
        left = baseline_records.get(key)
        right = candidate_records.get(key)
        action = SeriesReleaseDiffAction.UNCHANGED.value if left == right else SeriesReleaseDiffAction.CHANGED.value if left is not None and right is not None else SeriesReleaseDiffAction.ADDED.value if right is not None else SeriesReleaseDiffAction.REMOVED.value
        items.append(_diff_item(ordinal, key, action, left, right))
    added = sum(item.action == SeriesReleaseDiffAction.ADDED.value for item in items)
    removed = sum(item.action == SeriesReleaseDiffAction.REMOVED.value for item in items)
    unchanged = sum(item.action == SeriesReleaseDiffAction.UNCHANGED.value for item in items)
    changed = sum(item.action == SeriesReleaseDiffAction.CHANGED.value for item in items)
    improved = sum(item.direction == SeriesReleaseDiffDirection.IMPROVED.value for item in items)
    regressed = sum(item.direction == SeriesReleaseDiffDirection.REGRESSED.value for item in items)
    directions = {item.direction for item in items}
    release_direction = next(item.direction for item in items if item.key == "release")
    state = release_direction if release_direction in {item.value for item in SeriesReleaseDiffDirection if item != SeriesReleaseDiffDirection.CHANGED} else SeriesReleaseDiffDirection.CHANGED.value if SeriesReleaseDiffDirection.CHANGED.value in directions else SeriesReleaseDiffDirection.UNCHANGED.value
    body = {"diff_id": diff_id, "version": VERSION, "boundary": BOUNDARY, "baseline_address": baseline.content_address, "candidate_address": candidate.content_address, "item_count": len(items), "added_count": added, "removed_count": removed, "unchanged_count": unchanged, "changed_count": changed, "improved_count": improved, "regressed_count": regressed, "state": state, "accepted": state != SeriesReleaseDiffDirection.REGRESSED.value, "release_ready": state in {SeriesReleaseDiffDirection.UNCHANGED.value, SeriesReleaseDiffDirection.IMPROVED.value}, "items": tuple(items), "content_address": "pending:series-release-diff"}
    provisional = DecisionAssuranceHistorySeriesReleaseDiff(**body)
    body["content_address"] = address_decision_assurance_history_series_release_diff(provisional)
    return DecisionAssuranceHistorySeriesReleaseDiff(**body)


def verify_decision_assurance_history_series_release_diff(value: DecisionAssuranceHistorySeriesReleaseDiff) -> DecisionAssuranceHistorySeriesReleaseDiff:
    if not isinstance(value, DecisionAssuranceHistorySeriesReleaseDiff):
        raise ValidationError("series release diff verification requires a typed diff")
    value._validate()
    if address_decision_assurance_history_series_release_diff(value) != value.content_address:
        raise ValidationError("series release diff address mismatch")
    return value


def decision_assurance_history_series_release_diff_item_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseDiffItem:
    body = dict(_mapping(value, "series release diff item"))
    _strict(body, {"ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"}, "series release diff item")
    item = DecisionAssuranceHistorySeriesReleaseDiffItem(**body)
    if address_decision_assurance_history_series_release_diff_item(item) != item.content_address:
        raise ValidationError("series release diff item address mismatch")
    return item


def decision_assurance_history_series_release_diff_from_mapping(value: Mapping[str, Any]) -> DecisionAssuranceHistorySeriesReleaseDiff:
    body = dict(_mapping(value, "series release diff"))
    _strict(body, {"diff_id", "version", "boundary", "baseline_address", "candidate_address", "item_count", "added_count", "removed_count", "unchanged_count", "changed_count", "improved_count", "regressed_count", "state", "accepted", "release_ready", "items", "content_address"}, "series release diff")
    body["items"] = tuple(decision_assurance_history_series_release_diff_item_from_mapping(item) for item in _mapping_sequence(body["items"], "series release diff items"))
    return verify_decision_assurance_history_series_release_diff(DecisionAssuranceHistorySeriesReleaseDiff(**body))


def build_decision_assurance_history_series_release_diff_from_directories(baseline_directory: str | Path, candidate_directory: str | Path, *, diff_id: str = DEFAULT_DIFF_ID) -> DecisionAssuranceHistorySeriesReleaseDiff:
    return build_decision_assurance_history_series_release_diff(load_decision_assurance_history_series_release_package(baseline_directory).release, load_decision_assurance_history_series_release_package(candidate_directory).release, diff_id=diff_id)


def decision_assurance_history_series_release_diff_json(value: DecisionAssuranceHistorySeriesReleaseDiff) -> str:
    return canonical_json(verify_decision_assurance_history_series_release_diff(value).to_dict())


def decision_assurance_history_series_release_diff_csv(value: DecisionAssuranceHistorySeriesReleaseDiff) -> str:
    value = verify_decision_assurance_history_series_release_diff(value)
    return _csv_text([item.to_dict() for item in value.items], ("ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"))


def render_decision_assurance_history_series_release_diff_markdown(value: DecisionAssuranceHistorySeriesReleaseDiff) -> str:
    value = verify_decision_assurance_history_series_release_diff(value)
    return _markdown("Decision Assurance History Series Release Diff", value.summary(), [item.to_dict() for item in value.items])


class SeriesReleaseDiffQuery:
    """Bounded query over release-diff records."""

    RESOURCES = ("summary", "items", "added", "removed", "unchanged", "changed", "improved", "regressed")

    def __init__(self, resource: str = "summary", *, offset: int = 0, limit: int = 50, text: str | None = None) -> None:
        self.resource = _text(resource, "release diff query resource", 32)
        if self.resource not in self.RESOURCES:
            raise ValidationError("release diff query resource is invalid")
        self.offset = _count(offset, "release diff query offset")
        self.limit = _count(limit, "release diff query limit", 512)
        if self.limit < 1:
            raise ValidationError("release diff query limit must be positive")
        self.text = None if text is None else _text(text, "release diff query text", 512)

    def to_dict(self) -> dict[str, Any]:
        return {"resource": self.resource, "offset": self.offset, "limit": self.limit, "text": self.text}


class SeriesReleaseDiffQueryResult:
    """Addressed deterministic page over release-diff items."""

    def __init__(self, diff_address: str, query: SeriesReleaseDiffQuery, total_count: int, returned_count: int, items: Sequence[Mapping[str, Any]], content_address: str) -> None:
        self.diff_address = diff_address
        self.query = query
        self.total_count = total_count
        self.returned_count = returned_count
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.diff_address, "release diff query diff address")
        _count(self.total_count, "release diff query total")
        _count(self.returned_count, "release diff query returned", self.total_count)
        if self.returned_count != len(self.items):
            raise ValidationError("release diff query returned count is invalid")
        _address(self.content_address, "release diff query address")
        if not self.content_address.startswith("pending:") and address_decision_assurance_history_series_release_diff_query(self) != self.content_address:
            raise ValidationError("release diff query address mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {"diff_address": self.diff_address, "query": self.query.to_dict(), "total_count": self.total_count, "returned_count": self.returned_count, "items": list(self.items), "content_address": self.content_address}


def address_decision_assurance_history_series_release_diff_query(value: SeriesReleaseDiffQueryResult) -> str:
    return content_hash(value.to_dict() | {"content_address": None}, prefix=DIFF_PREFIX + "-query")


def query_decision_assurance_history_series_release_diff(value: DecisionAssuranceHistorySeriesReleaseDiff, query: SeriesReleaseDiffQuery | None = None, **kwargs: Any) -> SeriesReleaseDiffQueryResult:
    verify_decision_assurance_history_series_release_diff(value)
    if query is not None and kwargs:
        raise ValidationError("release diff query cannot combine typed query and keyword filters")
    selected = query or SeriesReleaseDiffQuery(**kwargs)
    if selected.resource == "summary":
        rows = [value.summary()]
    else:
        rows = [item.to_dict() for item in value.items]
        if selected.resource != "items":
            rows = [row for row in rows if row["action"] == selected.resource or row["direction"] == selected.resource]
    if selected.text:
        needle = selected.text.casefold()
        rows = [row for row in rows if needle in canonical_json(row).casefold()]
    total = len(rows)
    page = rows[selected.offset : selected.offset + selected.limit]
    body = {"diff_address": value.content_address, "query": selected, "total_count": total, "returned_count": len(page), "items": page, "content_address": "pending:release-diff-query"}
    provisional = SeriesReleaseDiffQueryResult(**body)
    body["content_address"] = address_decision_assurance_history_series_release_diff_query(provisional)
    return SeriesReleaseDiffQueryResult(**body)


def decision_assurance_history_series_release_diff_query_json(value: SeriesReleaseDiffQueryResult) -> str:
    return canonical_json(value.to_dict())


def decision_assurance_history_series_release_diff_query_csv(value: SeriesReleaseDiffQueryResult) -> str:
    return _csv_text(value.items, ("ordinal", "key", "action", "direction", "baseline_value", "candidate_value", "detail", "content_address"))


def render_decision_assurance_history_series_release_diff_query_markdown(value: SeriesReleaseDiffQueryResult) -> str:
    return _markdown("Decision Assurance History Series Release Diff Query", {"diff_address": value.diff_address, "resource": value.query.resource, "total_count": value.total_count, "returned_count": value.returned_count}, value.items)


def _file_address(name: str, raw: bytes, *, prefix: str = RELEASE_PREFIX + "-file") -> str:
    return content_hash({"name": name, "byte_address": hash_bytes(raw)}, prefix=prefix)


def _manifest_artifacts(raws: Mapping[str, bytes], *, prefix: str = RELEASE_PREFIX + "-file") -> list[dict[str, Any]]:
    return [{"name": name, "bytes": len(raw), "byte_address": hash_bytes(raw), "file_address": _file_address(name, raw, prefix=prefix)} for name, raw in raws.items()]


def _manifest_body(value: DecisionAssuranceHistorySeriesReleasePackage, raws: Mapping[str, bytes]) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "package_id": value.package_id, "release_id": value.release.release_id, "package_address": value.content_address, "series_address": value.series.content_address, "policy_address": value.policy.content_address, "evaluation_address": value.evaluation.content_address, "release_address": value.release.content_address, "artifact_count": len(raws), "files": list(FILES), "artifacts": _manifest_artifacts(raws), "manifest_address": None}


def _manifest_address(value: Mapping[str, Any], *, prefix: str = MANIFEST_PREFIX) -> str:
    return content_hash(dict(value), prefix=prefix)


def write_decision_assurance_history_series_release_package(value: DecisionAssuranceHistorySeriesReleasePackage, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_history_series_release_package(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("series release package destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    raws = {SERIES_NAME: canonical_bytes(value.series.to_dict()), POLICY_NAME: canonical_bytes(value.policy.to_dict()), EVALUATION_NAME: canonical_bytes(value.evaluation.to_dict()), RELEASE_NAME: canonical_bytes(value.release.to_dict())}
    manifest = _manifest_body(value, raws)
    manifest["manifest_address"] = _manifest_address(manifest)
    manifest_raw = canonical_bytes(manifest)
    temporary = Path(tempfile.mkdtemp(prefix=f".{PACKAGE_PREFIX}-", dir=str(destination.parent)))
    try:
        for name, raw in raws.items():
            (temporary / name).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(manifest_raw)
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("series release package destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("series release package destination already exists")
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


def _check_manifest_artifact(manifest: Mapping[str, Any], source: Path, name: str, *, prefix: str = RELEASE_PREFIX + "-file") -> bytes:
    artifacts = _mapping_sequence(manifest.get("artifacts"), "series release manifest artifacts")
    artifact = next((item for item in artifacts if item.get("name") == name), None)
    if artifact is None:
        raise ValidationError(f"series release manifest is missing {name}")
    path = source / name
    if path.is_symlink() or not path.is_file():
        raise ValidationError(f"series release artifact {name} must be a regular file")
    raw = path.read_bytes()
    byte_address = hash_bytes(raw)
    if artifact.get("bytes") != len(raw) or artifact.get("byte_address") != byte_address or artifact.get("file_address") != _file_address(name, raw, prefix=prefix):
        raise ValidationError(f"series release artifact {name} address mismatch")
    return raw


def load_decision_assurance_history_series_release_package(directory: str | Path) -> DecisionAssuranceHistorySeriesReleasePackage:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("series release package input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(FILES):
        raise ValidationError("series release package file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "series release manifest")
    _strict(manifest, {"version", "boundary", "package_id", "release_id", "package_address", "series_address", "policy_address", "evaluation_address", "release_address", "artifact_count", "files", "artifacts", "manifest_address"}, "series release manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 4 or tuple(manifest["files"]) != FILES:
        raise ValidationError("series release manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}):
        raise ValidationError("series release manifest address mismatch")
    documents = {name: _check_manifest_artifact(manifest, source, name) for name in (SERIES_NAME, POLICY_NAME, EVALUATION_NAME, RELEASE_NAME)}
    series = series_model.decision_assurance_history_series_from_mapping(json.loads(documents[SERIES_NAME].decode("utf-8")))
    selected_policy = policy_model.decision_assurance_history_series_policy_from_mapping(json.loads(documents[POLICY_NAME].decode("utf-8")))
    evaluation = policy_model.decision_assurance_history_series_policy_evaluation_from_mapping(json.loads(documents[EVALUATION_NAME].decode("utf-8")))
    release = decision_assurance_history_series_release_from_mapping(json.loads(documents[RELEASE_NAME].decode("utf-8")))
    if manifest["package_id"] == "" or manifest["release_id"] != release.release_id or manifest["series_address"] != series.content_address or manifest["policy_address"] != selected_policy.content_address or manifest["evaluation_address"] != evaluation.content_address or manifest["release_address"] != release.content_address:
        raise ValidationError("series release manifest linkage is invalid")
    body = {"package_id": manifest["package_id"], "version": VERSION, "boundary": BOUNDARY, "series": series, "policy": selected_policy, "evaluation": evaluation, "release": release, "content_address": "pending:loaded-series-release-package"}
    package = DecisionAssuranceHistorySeriesReleasePackage(**body)
    if manifest["package_address"] != address_decision_assurance_history_series_release_package(package):
        raise ValidationError("series release package address mismatch")
    body["content_address"] = manifest["package_address"]
    return verify_decision_assurance_history_series_release_package(DecisionAssuranceHistorySeriesReleasePackage(**body))


def verify_decision_assurance_history_series_release_package_directory(directory: str | Path) -> DecisionAssuranceHistorySeriesReleasePackage:
    return load_decision_assurance_history_series_release_package(directory)


def _diff_manifest_body(value: DecisionAssuranceHistorySeriesReleaseDiff, raw: bytes) -> dict[str, Any]:
    return {"version": VERSION, "boundary": BOUNDARY, "diff_id": value.diff_id, "baseline_address": value.baseline_address, "candidate_address": value.candidate_address, "diff_address": value.content_address, "artifact_count": 1, "files": list(DIFF_FILES), "artifacts": _manifest_artifacts({DIFF_NAME: raw}, prefix=DIFF_PREFIX + "-file"), "manifest_address": None}


def write_decision_assurance_history_series_release_diff(value: DecisionAssuranceHistorySeriesReleaseDiff, directory: str | Path, *, overwrite: bool = False) -> Path:
    verify_decision_assurance_history_series_release_diff(value)
    destination = Path(directory)
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())) and not overwrite:
        raise ValidationError("series release diff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_bytes(value.to_dict())
    manifest = _diff_manifest_body(value, raw)
    manifest["manifest_address"] = _manifest_address(manifest, prefix=DIFF_MANIFEST_PREFIX)
    temporary = Path(tempfile.mkdtemp(prefix=f".{DIFF_PREFIX}-", dir=str(destination.parent)))
    try:
        (temporary / DIFF_NAME).write_bytes(raw)
        (temporary / MANIFEST_NAME).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("series release diff destination is not a directory")
            if any(destination.iterdir()):
                if not overwrite:
                    raise ValidationError("series release diff destination already exists")
                shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_decision_assurance_history_series_release_diff(directory: str | Path) -> DecisionAssuranceHistorySeriesReleaseDiff:
    source = Path(directory)
    if source.is_symlink() or not source.is_dir():
        raise ValidationError("series release diff input must be a directory")
    children = tuple(source.iterdir())
    if any(item.is_symlink() for item in children) or {item.name for item in children} != set(DIFF_FILES):
        raise ValidationError("series release diff file set is invalid")
    manifest = _read_json(source / MANIFEST_NAME, "series release diff manifest")
    _strict(manifest, {"version", "boundary", "diff_id", "baseline_address", "candidate_address", "diff_address", "artifact_count", "files", "artifacts", "manifest_address"}, "series release diff manifest")
    if manifest["version"] != VERSION or manifest["boundary"] != BOUNDARY or manifest["artifact_count"] != 1 or tuple(manifest["files"]) != DIFF_FILES:
        raise ValidationError("series release diff manifest contract is invalid")
    if manifest["manifest_address"] != _manifest_address({**manifest, "manifest_address": None}, prefix=DIFF_MANIFEST_PREFIX):
        raise ValidationError("series release diff manifest address mismatch")
    raw = _check_manifest_artifact(manifest, source, DIFF_NAME, prefix=DIFF_PREFIX + "-file")
    value = decision_assurance_history_series_release_diff_from_mapping(json.loads(raw.decode("utf-8")))
    if manifest["diff_id"] != value.diff_id or manifest["baseline_address"] != value.baseline_address or manifest["candidate_address"] != value.candidate_address or manifest["diff_address"] != value.content_address:
        raise ValidationError("series release diff manifest linkage is invalid")
    return verify_decision_assurance_history_series_release_diff(value)


def verify_decision_assurance_history_series_release_diff_directory(directory: str | Path) -> DecisionAssuranceHistorySeriesReleaseDiff:
    return load_decision_assurance_history_series_release_diff(directory)


__all__ = [
    "BOUNDARY", "DEFAULT_DIFF_ID", "DEFAULT_PACKAGE_ID", "DEFAULT_RELEASE_ID", "DIFF_FILES", "DIFF_NAME", "FILES", "MANIFEST_NAME", "MAX_DIFF_ITEMS", "MAX_QUERY_ITEMS", "MAX_STAGES", "PACKAGE_PREFIX", "POLICY_NAME", "RELEASE_NAME", "RELEASE_PREFIX", "SERIES_NAME", "STAGE_PREFIX", "DecisionAssuranceHistorySeriesRelease", "DecisionAssuranceHistorySeriesReleaseDiff", "DecisionAssuranceHistorySeriesReleaseDiffItem", "DecisionAssuranceHistorySeriesReleasePackage", "DecisionAssuranceHistorySeriesReleaseStage", "SeriesReleaseDiffAction", "SeriesReleaseDiffDirection", "SeriesReleaseDiffQuery", "SeriesReleaseDiffQueryResult", "SeriesReleaseQuery", "SeriesReleaseQueryResult", "SeriesReleaseState", "address_decision_assurance_history_series_release", "address_decision_assurance_history_series_release_diff", "address_decision_assurance_history_series_release_diff_item", "address_decision_assurance_history_series_release_diff_query", "address_decision_assurance_history_series_release_package", "address_decision_assurance_history_series_release_query", "address_decision_assurance_history_series_release_stage", "build_decision_assurance_history_series_release", "build_decision_assurance_history_series_release_diff", "build_decision_assurance_history_series_release_diff_from_directories", "build_decision_assurance_history_series_release_package", "build_decision_assurance_history_series_release_package_from_directories", "capabilities", "decision_assurance_history_series_release_csv", "decision_assurance_history_series_release_diff_csv", "decision_assurance_history_series_release_diff_from_mapping", "decision_assurance_history_series_release_diff_item_from_mapping", "decision_assurance_history_series_release_diff_item_schema", "decision_assurance_history_series_release_diff_json", "decision_assurance_history_series_release_diff_query_csv", "decision_assurance_history_series_release_diff_query_json", "decision_assurance_history_series_release_diff_query_schema", "decision_assurance_history_series_release_diff_schema", "decision_assurance_history_series_release_from_mapping", "decision_assurance_history_series_release_json", "decision_assurance_history_series_release_package_csv", "decision_assurance_history_series_release_package_json", "decision_assurance_history_series_release_package_schema", "decision_assurance_history_series_release_query_csv", "decision_assurance_history_series_release_query_json", "decision_assurance_history_series_release_query_schema", "decision_assurance_history_series_release_schema", "decision_assurance_history_series_release_stage_from_mapping", "decision_assurance_history_series_release_stage_schema", "load_decision_assurance_history_series_release_diff", "load_decision_assurance_history_series_release_package", "query_decision_assurance_history_series_release", "query_decision_assurance_history_series_release_diff", "render_decision_assurance_history_series_release_diff_markdown", "render_decision_assurance_history_series_release_markdown", "render_decision_assurance_history_series_release_diff_query_markdown", "render_decision_assurance_history_series_release_package_markdown", "render_decision_assurance_history_series_release_query_markdown", "verify_decision_assurance_history_series_release", "verify_decision_assurance_history_series_release_diff", "verify_decision_assurance_history_series_release_diff_directory", "verify_decision_assurance_history_series_release_package", "verify_decision_assurance_history_series_release_package_directory", "write_decision_assurance_history_series_release_diff", "write_decision_assurance_history_series_release_package",
]
