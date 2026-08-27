"""Policy-governed runtime closure for the packet-review history observatory."""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_STAGE_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
    + "-stage"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
    + "-policy"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
    + "-policy-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_REPORT_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
    + "-report"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DOCUMENT = "runtime.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES = 8
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS = 16

# The long public names below keep the product's established store-catalog
# namespace.  These compact aliases make the runtime implementation readable
# while preserving one canonical public vocabulary at the module boundary.
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_STAGE_PREFIX = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_STAGE_PREFIX
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_REPORT_PREFIX = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_REPORT_PREFIX
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX


Observatory = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatory
ObservatoryCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryCheck


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageName(
    StrEnum
):
    LOAD = "load"
    VERIFY = "verify"
    POLICY = "policy"
    PROJECT = "project"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageState(
    StrEnum
):
    PASSED = "passed"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    value = _text(value, field, 512)
    if ":" not in value:
        raise ValidationError(f"{field} must be addressed")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(value: Any, field: str, maximum: int, *, positive: bool = False) -> int:
    lower = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or not lower <= value <= maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _public(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).casefold()
            if lowered in {"agent", "language", "model", "user"} or lowered.endswith(
                ("_agent", "_language", "_model", "_user")
            ):
                return False
            if not _public(item):
                return False
    elif isinstance(value, (tuple, list)):
        return all(_public(item) for item in value)
    return True


def _json_value(value: Any, field: str) -> Any:
    try:
        result = json.loads(canonical_json(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be canonical JSON data") from exc
    if not _public(result):
        raise ValidationError(f"{field} crosses the public boundary")
    return result


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy:
    """Bounded release policy for a longitudinal observatory."""

    def __init__(
        self,
        *,
        policy_id: str,
        version: str,
        minimum_observations: int,
        maximum_regressions: int,
        maximum_blocked_observations: int,
        maximum_changed_transitions: int,
        require_latest_release_ready: bool,
        require_all_observations_accepted: bool,
        allow_mixed_state: bool,
        content_address: str,
    ) -> None:
        self.policy_id = policy_id
        self.version = version
        self.minimum_observations = minimum_observations
        self.maximum_regressions = maximum_regressions
        self.maximum_blocked_observations = maximum_blocked_observations
        self.maximum_changed_transitions = maximum_changed_transitions
        self.require_latest_release_ready = require_latest_release_ready
        self.require_all_observations_accepted = require_all_observations_accepted
        self.allow_mixed_state = allow_mixed_state
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.policy_id, "observatory runtime policy ID", 256)
        expected = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION
        if self.version != expected:
            raise ValidationError("observatory runtime policy version is invalid")
        _count(
            self.minimum_observations,
            "minimum observations",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
            positive=True,
        )
        _count(
            self.maximum_regressions,
            "maximum regressions",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
        )
        _count(
            self.maximum_blocked_observations,
            "maximum blocked observations",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_OBSERVATIONS,
        )
        _count(
            self.maximum_changed_transitions,
            "maximum changed transitions",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
        )
        for value, field in (
            (self.require_latest_release_ready, "require latest release-ready"),
            (self.require_all_observations_accepted, "require accepted observations"),
            (self.allow_mixed_state, "allow mixed state"),
        ):
            _bool(value, field)
        _address(self.content_address, "observatory runtime policy address")
        if not _public(self.to_dict()):
            raise ValidationError("observatory runtime policy crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "minimum_observations": self.minimum_observations,
            "maximum_regressions": self.maximum_regressions,
            "maximum_blocked_observations": self.maximum_blocked_observations,
            "maximum_changed_transitions": self.maximum_changed_transitions,
            "require_latest_release_ready": self.require_latest_release_ready,
            "require_all_observations_accepted": self.require_all_observations_accepted,
            "allow_mixed_state": self.allow_mixed_state,
            "content_address": self.content_address,
        }


ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicy = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy


def default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
    *,
    policy_id: str = "glio-noncode-observatory-release-policy",
    minimum_observations: int = 1,
    maximum_regressions: int = 0,
    maximum_blocked_observations: int = 0,
    maximum_changed_transitions: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_MAX_TRANSITIONS,
    require_latest_release_ready: bool = True,
    require_all_observations_accepted: bool = True,
    allow_mixed_state: bool = False,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy:
    body = {
        "policy_id": _text(policy_id, "observatory runtime policy ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
        "minimum_observations": minimum_observations,
        "maximum_regressions": maximum_regressions,
        "maximum_blocked_observations": maximum_blocked_observations,
        "maximum_changed_transitions": maximum_changed_transitions,
        "require_latest_release_ready": require_latest_release_ready,
        "require_all_observations_accepted": require_all_observations_accepted,
        "allow_mixed_state": allow_mixed_state,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy(
        **body, content_address="pending:policy"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy(
                    provisional
                )
            }
        )
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_CHECK_PREFIX,
    )


address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_check = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_check


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck:
    """One independently addressed policy result."""

    def __init__(
        self,
        *,
        ordinal: int,
        kind: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.passed = passed
        self.expected = _json_value(expected, "policy check expected")
        self.observed = _json_value(observed, "policy check observed")
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "policy check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS
            - 1,
        )
        _text(self.kind, "policy check kind", 128)
        _bool(self.passed, "policy check passed")
        _text(self.detail, "policy check detail")
        _address(self.content_address, "policy check address")
        if not _public(self.to_dict()):
            raise ValidationError("policy check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck


def _policy_check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": bool(passed),
        "expected": _json_value(expected, "policy expected"),
        "observed": _json_value(observed, "policy observed"),
        "detail": _text(detail, "policy detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck(
        **body, content_address="pending:policy-check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_check(
                    provisional
                )
            }
        )
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_evaluation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX
        + "-evaluation",
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation:
    """A fail-closed evaluation of policy against observatory rollups."""

    def __init__(
        self,
        *,
        policy_address: str,
        observatory_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        check_count: int,
        passed_count: int,
        failed_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.policy_address = policy_address
        self.observatory_address = observatory_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.policy_address, "policy evaluation policy address")
        _address(self.observatory_address, "policy evaluation observatory address")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeState
        }:
            raise ValidationError("policy evaluation state is invalid")
        _bool(self.accepted, "policy evaluation accepted")
        _bool(self.release_ready, "policy evaluation release-ready")
        _count(
            self.check_count,
            "policy evaluation check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS,
            positive=True,
        )
        _count(self.passed_count, "policy evaluation passed count", self.check_count)
        _count(self.failed_count, "policy evaluation failed count", self.check_count)
        if (
            self.check_count != len(self.checks)
            or self.passed_count + self.failed_count != self.check_count
            or self.accepted != (self.failed_count == 0)
        ):
            raise ValidationError("policy evaluation counts are not conserved")
        if self.release_ready and (not self.accepted or self.state != "ready"):
            raise ValidationError("policy evaluation release projection is invalid")
        for ordinal, item in enumerate(self.checks):
            if (
                item.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_check(
                    item
                )
                != item.content_address
            ):
                raise ValidationError("policy checks are not contiguous and addressed")
        _address(self.content_address, "policy evaluation address")
        if not _public(self.to_dict()):
            raise ValidationError("policy evaluation crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_address": self.policy_address,
            "observatory_address": self.observatory_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }

    def summary(self) -> dict[str, Any]:
        body = self.to_dict()
        body.pop("checks", None)
        return body


ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation


def evaluate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy(
    observatory: Observatory,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation:
    if not isinstance(observatory, Observatory):
        raise ValidationError("policy evaluation requires a typed observatory")
    policy = (
        policy
        or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy()
    )
    if not isinstance(
        policy,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicy,
    ):
        raise ValidationError("policy evaluation requires a typed policy")
    rollup = observatory.rollup
    checks = tuple(
        _policy_check(ordinal, kind, passed, expected, observed, detail)
        for ordinal, (kind, passed, expected, observed, detail) in enumerate(
            (
                (
                    "minimum-observations",
                    observatory.observation_count >= policy.minimum_observations,
                    policy.minimum_observations,
                    observatory.observation_count,
                    "observation count meets the minimum",
                ),
                (
                    "observatory-accepted",
                    observatory.accepted,
                    True,
                    observatory.accepted,
                    "observatory integrity is accepted",
                ),
                (
                    "accepted-observations",
                    not policy.require_all_observations_accepted
                    or rollup.accepted_count == observatory.observation_count,
                    observatory.observation_count
                    if policy.require_all_observations_accepted
                    else "not-required",
                    rollup.accepted_count,
                    "observation acceptance requirement is satisfied",
                ),
                (
                    "latest-release-ready",
                    not policy.require_latest_release_ready or observatory.release_ready,
                    True if policy.require_latest_release_ready else "not-required",
                    observatory.release_ready,
                    "latest observation release readiness is satisfied",
                ),
                (
                    "regression-budget",
                    rollup.regressed_count <= policy.maximum_regressions,
                    policy.maximum_regressions,
                    rollup.regressed_count,
                    "regression count is within policy",
                ),
                (
                    "blocked-budget",
                    rollup.blocked_count <= policy.maximum_blocked_observations,
                    policy.maximum_blocked_observations,
                    rollup.blocked_count,
                    "blocked observation count is within policy",
                ),
                (
                    "changed-transition-budget",
                    rollup.changed_count <= policy.maximum_changed_transitions,
                    policy.maximum_changed_transitions,
                    rollup.changed_count,
                    "changed transition count is within policy",
                ),
                (
                    "mixed-state-policy",
                    policy.allow_mixed_state or observatory.state != "mixed",
                    False if not policy.allow_mixed_state else "not-required",
                    observatory.state,
                    "mixed-state policy is satisfied",
                ),
            )
        )
    )
    accepted = all(item.passed for item in checks)
    release_ready = accepted and observatory.release_ready
    state = "ready" if release_ready else "held" if accepted else "blocked"
    body = {
        "policy_address": policy.content_address,
        "observatory_address": observatory.content_address,
        "state": state,
        "accepted": accepted,
        "release_ready": release_ready,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation(
        **body, content_address="pending:evaluation"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_evaluation(
                    provisional
                )
            }
        )
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage:
    """One deterministic runtime stage receipt."""

    def __init__(
        self,
        *,
        ordinal: int,
        name: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.name = name
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "runtime stage ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES
            - 1,
        )
        if self.name not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageName
        }:
            raise ValidationError("runtime stage name is invalid")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageState
        }:
            raise ValidationError("runtime stage state is invalid")
        _address(self.input_address, "runtime stage input address", optional=True)
        _address(self.output_address, "runtime stage output address", optional=True)
        _text(self.detail, "runtime stage detail")
        _address(self.content_address, "runtime stage address")
        if self.state == "passed" and self.output_address is None:
            raise ValidationError("passed runtime stage requires an output address")
        if not _public(self.to_dict()):
            raise ValidationError("runtime stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "name": self.name,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def _stage(
    ordinal: int,
    name: str,
    state: str,
    input_address: str | None,
    output_address: str | None,
    detail: str,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage:
    body = {
        "ordinal": ordinal,
        "name": name,
        "state": state,
        "input_address": input_address,
        "output_address": output_address,
        "detail": _text(detail, "stage detail"),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage(
        **body, content_address="pending:stage"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_stage(
                    provisional
                )
            }
        )
    )


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_report(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_REPORT_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport:
    """A complete stage, verification, policy, and release projection."""

    def __init__(
        self,
        *,
        runtime_id: str,
        version: str,
        boundary: str,
        observatory_address: str,
        policy_address: str,
        state: str,
        accepted: bool,
        release_ready: bool,
        stage_count: int,
        stages: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage,
            ...,
        ],
        verification: Mapping[str, Any],
        policy_evaluation: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation,
        content_address: str,
    ) -> None:
        self.runtime_id = runtime_id
        self.version = version
        self.boundary = boundary
        self.observatory_address = observatory_address
        self.policy_address = policy_address
        self.state = state
        self.accepted = accepted
        self.release_ready = release_ready
        self.stage_count = stage_count
        self.stages = tuple(stages)
        self.verification = dict(verification)
        self.policy_evaluation = policy_evaluation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.runtime_id, "runtime ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION
            or self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_BOUNDARY
        ):
            raise ValidationError("runtime version or boundary is invalid")
        _address(self.observatory_address, "runtime observatory address")
        _address(self.policy_address, "runtime policy address")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeState
        }:
            raise ValidationError("runtime state is invalid")
        _bool(self.accepted, "runtime accepted")
        _bool(self.release_ready, "runtime release-ready")
        _count(
            self.stage_count,
            "runtime stage count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES,
            positive=True,
        )
        if len(self.stages) != self.stage_count:
            raise ValidationError("runtime stage count is not conserved")
        for ordinal, item in enumerate(self.stages):
            if (
                not isinstance(
                    item,
                    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage,
                )
                or item.ordinal != ordinal
            ):
                raise ValidationError("runtime stages are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_stage(
                    item
                )
                != item.content_address
            ):
                raise ValidationError("runtime stage address is invalid")
        if not _public(self.verification):
            raise ValidationError("runtime verification crosses the public boundary")
        if not isinstance(
            self.policy_evaluation,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation,
        ):
            raise ValidationError("runtime policy evaluation must be typed")
        if (
            self.accepted != self.policy_evaluation.accepted
            or self.release_ready != self.policy_evaluation.release_ready
            or self.state != self.policy_evaluation.state
        ):
            raise ValidationError("runtime terminal projection is not conserved")
        _address(self.content_address, "runtime report address")
        if not _public(self.to_dict()):
            raise ValidationError("runtime report crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "boundary": self.boundary,
            "observatory_address": self.observatory_address,
            "policy_address": self.policy_address,
            "state": self.state,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "stage_count": self.stage_count,
            "verification": self.verification,
            "policy_evaluation": self.policy_evaluation.summary(),
            "content_address": self.content_address,
        }

    def to_dict(
        self, *, include_stages: bool = True, include_policy_checks: bool = True
    ) -> dict[str, Any]:
        body = self.summary()
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        if include_policy_checks:
            body["policy_evaluation"]["checks"] = [
                item.to_dict() for item in self.policy_evaluation.checks
            ]
        return body


def run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
    observatory: Observatory,
    *,
    policy: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicy
    | None = None,
    runtime_id: str = "glio-noncode-observatory-runtime",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport:
    if not isinstance(observatory, Observatory):
        raise ValidationError("observatory runtime requires a typed observatory")
    policy = (
        policy
        or default_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy()
    )
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory(
        observatory
    )
    verification_summary = verification.summary()
    stages = [
        _stage(
            0, "load", "passed", None, observatory.content_address, "observatory input accepted"
        ),
        _stage(
            1,
            "verify",
            "passed" if verification.accepted else "blocked",
            observatory.content_address,
            verification.content_address if verification.accepted else None,
            "independent observatory verification completed",
        ),
    ]
    evaluation = evaluate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy(
        observatory, policy
    )
    stages.append(
        _stage(
            2,
            "policy",
            "passed" if evaluation.accepted else "blocked",
            verification.content_address,
            evaluation.content_address,
            "release policy evaluated against conserved rollups",
        )
    )
    stages.append(
        _stage(
            3,
            "project",
            "passed" if evaluation.accepted else "blocked",
            evaluation.content_address,
            observatory.content_address,
            "terminal release projection prepared",
        )
    )
    stages.append(
        _stage(
            4,
            "complete",
            "passed" if evaluation.accepted else "blocked",
            observatory.content_address,
            evaluation.content_address,
            "runtime closure completed",
        )
    )
    body = {
        "runtime_id": _text(runtime_id, "runtime ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_BOUNDARY,
        "observatory_address": observatory.content_address,
        "policy_address": policy.content_address,
        "state": evaluation.state,
        "accepted": evaluation.accepted,
        "release_ready": evaluation.release_ready,
        "stage_count": len(stages),
        "stages": tuple(stages),
        "verification": verification_summary,
        "policy_evaluation": evaluation,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport(
        **body, content_address="pending:runtime"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport(
        **(
            body
            | {
                "content_address": address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_report(
                    provisional
                )
            }
        )
    )


def _stage_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage(
        **dict(value)
    )


def _policy_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicy:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicy(
        **dict(value)
    )


def _policy_check_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyCheck(
        **dict(value)
    )


def _policy_evaluation_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation:
    body = dict(value)
    checks = tuple(_policy_check_from_dict(item) for item in body.pop("checks"))
    body.pop("check_count", None)
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation(
        **(body | {"check_count": len(checks), "checks": checks})
    )


def runtime_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport:
    if not isinstance(value, Mapping):
        raise ValidationError("runtime mapping must be an object")
    body = dict(value)
    try:
        stages = tuple(_stage_from_dict(item) for item in body.pop("stages"))
        policy_evaluation = _policy_evaluation_from_dict(body.pop("policy_evaluation"))
        body.pop("stage_count", None)
        return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport(
            **(
                body
                | {
                    "stage_count": len(stages),
                    "stages": stages,
                    "policy_evaluation": policy_evaluation,
                }
            )
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError("runtime mapping structure is invalid") from exc


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
    ):
        raise ValidationError("runtime write requires a typed report")
    if not value.accepted:
        raise ValidationError("cannot persist a blocked runtime report")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("runtime destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
            "runtime": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
                + "-bytes",
            ),
        }
        manifest = body | {
            "manifest_address": content_hash(
                body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("runtime destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("runtime directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("runtime files do not match the published set")
    manifest_raw = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MANIFEST
    ).read_bytes()
    document_raw = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DOCUMENT
    ).read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        document = json.loads(document_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("runtime files are not valid JSON") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(document, dict)
        or canonical_bytes(manifest) != manifest_raw
        or canonical_bytes(document) != document_raw
    ):
        raise ValidationError("runtime files must be canonical JSON objects")
    if (
        set(manifest)
        != {"manifest_version", "runtime", "byte_count", "byte_address", "manifest_address"}
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION
    ):
        raise ValidationError("runtime manifest structure is invalid")
    body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
        + "-manifest",
    ):
        raise ValidationError("runtime manifest address mismatch")
    if (
        manifest["runtime"] != document
        or manifest["byte_count"] != len(document_raw)
        or manifest["byte_address"]
        != hash_bytes(
            document_raw,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_PREFIX
            + "-bytes",
        )
    ):
        raise ValidationError("runtime document does not match the manifest")
    return runtime_from_mapping(document)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "name",
            "state",
            "input_address",
            "output_address",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.stages:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
) -> str:
    lines = [
        "# Packet-review gate history observatory runtime",
        "",
        f"- State: `{value.state}`",
        f"- Accepted: `{str(value.accepted).lower()}`",
        f"- Release ready: `{str(value.release_ready).lower()}`",
        "",
        "## Stages",
        "",
        "| # | Stage | State | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.name}` | `{item.state}` | {item.detail} |"
        for item in value.stages
    )
    lines.extend(
        [
            "",
            "## Policy",
            "",
            f"- Policy state: `{value.policy_evaluation.state}`",
            f"- Passed checks: `{value.policy_evaluation.passed_count}/{value.policy_evaluation.check_count}`",
            "",
            "| # | Check | Passed | Detail |",
            "|---:|---|---|---|",
        ]
    )
    lines.extend(
        f"| {item.ordinal} | `{item.kind}` | `{str(item.passed).lower()}` | {item.detail} |"
        for item in value.policy_evaluation.checks
    )
    return "\n".join(lines) + "\n"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery:
    """Bounded runtime query parameters."""

    def __init__(
        self,
        *,
        resource: str = "summary",
        stage: str | None = None,
        state: str | None = None,
        passed: bool | None = None,
        text: str | None = None,
        offset: int = 0,
        limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DEFAULT_LIMIT,
    ) -> None:
        self.resource = _text(resource, "runtime query resource", 32)
        if self.resource not in {"summary", "stages", "policy-checks"}:
            raise ValidationError("runtime query resource is invalid")
        self.stage = None if stage is None else _text(stage, "runtime query stage", 32)
        self.state = None if state is None else _text(state, "runtime query state", 32)
        self.passed = passed
        if passed is not None:
            _bool(passed, "runtime query passed")
        self.text = None if text is None else _text(text, "runtime query text", 256)
        _count(
            offset,
            "runtime query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES
            + MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS,
        )
        _count(
            limit,
            "runtime query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DEFAULT_LIMIT
            * 4,
            positive=True,
        )
        self.offset = offset
        self.limit = limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "stage": self.stage,
            "state": self.state,
            "passed": self.passed,
            "text": self.text,
            "offset": self.offset,
            "limit": self.limit,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult:
    """An addressed runtime query page."""

    def __init__(
        self,
        *,
        runtime_address: str,
        query: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery,
        total: int,
        offset: int,
        limit: int,
        items: tuple[Mapping[str, Any], ...],
        content_address: str,
    ) -> None:
        self.runtime_address = runtime_address
        self.query = query
        self.total = total
        self.offset = offset
        self.limit = limit
        self.items = tuple(dict(item) for item in items)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.runtime_address, "runtime query runtime address")
        if not isinstance(
            self.query,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery,
        ):
            raise ValidationError("runtime query must be typed")
        _count(
            self.total,
            "runtime query total",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES
            + MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS
            + 1,
        )
        _count(
            self.offset,
            "runtime query offset",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_STAGES
            + MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_MAX_POLICY_CHECKS,
        )
        _count(
            self.limit,
            "runtime query limit",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_DEFAULT_LIMIT
            * 4,
            positive=True,
        )
        if len(self.items) > self.limit or self.offset > self.total:
            raise ValidationError("runtime query page is not bounded")
        if not all(_public(item) for item in self.items):
            raise ValidationError("runtime query items cross the public boundary")
        _address(self.content_address, "runtime query address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "runtime_address": self.runtime_address,
            "query": self.query.to_dict(),
            "total": self.total,
            "offset": self.offset,
            "limit": self.limit,
            "items": list(self.items),
            "content_address": self.content_address,
        }


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
    query: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery
    | None = None,
    **kwargs: Any,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport,
    ):
        raise ValidationError("runtime query requires a typed report")
    query = (
        query
        or ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery(
            **kwargs
        )
    )
    if query.resource == "summary":
        candidates = (value.summary(),)
    elif query.resource == "stages":
        candidates = tuple(item.to_dict() for item in value.stages)
    else:
        candidates = tuple(item.to_dict() for item in value.policy_evaluation.checks)

    def matches(item: Mapping[str, Any]) -> bool:
        return (
            (query.stage is None or item.get("name") == query.stage)
            and (query.state is None or item.get("state") == query.state)
            and (query.passed is None or item.get("passed") == query.passed)
            and (query.text is None or query.text.casefold() in canonical_json(item).casefold())
        )

    filtered = tuple(item for item in candidates if matches(item))
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult(
        runtime_address=value.content_address,
        query=query,
        total=len(filtered),
        offset=query.offset,
        limit=query.limit,
        items=filtered[query.offset : query.offset + query.limit],
        content_address="pending:query",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult(
        runtime_address=provisional.runtime_address,
        query=provisional.query,
        total=provisional.total,
        offset=provisional.offset,
        limit=provisional.limit,
        items=provisional.items,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query(
            provisional
        ),
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult,
) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult,
) -> str:
    output = io.StringIO(newline="")
    fieldnames = tuple(sorted({str(key) for item in value.items for key in item})) or ("value",)
    writer = csv.DictWriter(
        output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for item in value.items:
        writer.writerow(
            {
                key: canonical_json(item[key])
                if isinstance(item.get(key), (dict, list, tuple))
                else item.get(key, "")
                for key in fieldnames
            }
        )
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult,
) -> str:
    lines = [
        "# Packet-review gate history observatory runtime query",
        "",
        f"- Resource: `{value.query.resource}`",
        f"- Total: `{value.total}`",
        "",
    ]
    if value.items:
        keys = tuple(sorted({str(key) for item in value.items for key in item}))
        lines.extend(["| " + " | ".join(keys) + " |", "|" + "|".join("---" for _ in keys) + "|"])
        lines.extend(
            "| " + " | ".join(f"`{item.get(key, '')}`" for key in keys) + " |"
            for item in value.items
        )
    else:
        lines.append("No matching items.")
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_BOUNDARY,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeState
        ],
        "stage_names": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageName
        ],
        "stage_states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStageState
        ],
        "exact_files": ["manifest.json", "runtime.json"],
        "resources": ["summary", "stages", "policy-checks"],
        "bounded": True,
        "policy_governed": True,
        "fail_closed": True,
        "canonical_json": True,
        "atomic_write": True,
        "identity_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_VERSION,
        "operations": [
            "default-policy",
            "evaluate-policy",
            "run",
            "write",
            "load",
            "query",
            "json",
            "csv",
            "markdown",
        ],
        "ordered_stages": True,
        "policy_checks": True,
        "independent_observatory_verification": True,
        "release_projection": True,
        "bounded": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "stages", "policy-checks"],
        "filters": ["stage", "state", "passed", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "stages", "policy-checks"],
        "filters": ["stage", "state", "passed", "text", "offset", "limit"],
        "bounded": True,
        "deterministic": True,
        "addressed_receipts": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX
        + "-v1",
        "fields": [
            "minimum_observations",
            "maximum_regressions",
            "maximum_blocked_observations",
            "maximum_changed_transitions",
            "require_latest_release_ready",
            "require_all_observations_accepted",
            "allow_mixed_state",
        ],
        "bounded": True,
        "addressed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_CATALOG_PACKET_REVIEW_GATE_HISTORY_OBSERVATORY_RUNTIME_POLICY_PREFIX
        + "-v1",
        "operations": ["default", "evaluate"],
        "bounded_thresholds": True,
        "fail_closed": True,
        "identity_free": True,
    }


# Canonical public aliases retain the same store-catalog namespace as the
# adjacent packet-review modules.
ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeStage = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeStage
ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeReport = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeReport
ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeQuery = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQuery
ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimeQueryResult
ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewCatalogPacketReviewGateHistoryObservatoryRuntimePolicyEvaluation
evaluate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy = evaluate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy
address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_evaluation = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_evaluation
address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_stage = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_stage
address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_report = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_report
address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query = address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query
query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime = query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime
run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime
write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime = write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime
load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_json = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_json
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_csv = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_csv
render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_markdown
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_json = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_json
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_csv = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_csv
render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_markdown = render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_markdown
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_capabilities
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_query_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_query_capabilities
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_schema = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_schema
module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_history_observatory_runtime_policy_capabilities = module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_catalog_packet_review_gate_history_observatory_runtime_policy_capabilities
