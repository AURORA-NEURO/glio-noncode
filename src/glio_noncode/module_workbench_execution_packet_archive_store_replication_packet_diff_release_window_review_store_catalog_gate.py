"""Combine catalog evidence into a fail-closed release gate.

The gate is intentionally a projection over already-addressed evidence.  It
does not mutate catalogs, stores, runtimes, federations, or assurance
findings.  Structural failures are blockers; valid but not-yet-ready evidence
is accepted as held.  This makes the release boundary auditable without
confusing acceptance with release readiness.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime import (
    run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_CHECK_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate-check"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_MAX_CHECKS = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
    + 16
)


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateSeverity(
    StrEnum
):
    PASS = "pass"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"
    EMPTY = "empty"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGatePlane(
    StrEnum
):
    LINKAGE = "linkage"
    CATALOG = "catalog"
    RUNTIME = "runtime"
    FEDERATION = "federation"
    ASSURANCE = "assurance"
    PUBLIC = "public"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value.strip()


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_MAX_CHECKS,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _public(value: Any) -> bool:
    forbidden = {
        "agent",
        "assistant",
        "author",
        "email",
        "generated_by",
        "language",
        "model",
        "private",
        "secret",
        "token",
        "user",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public(item) for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck:
    """One structural or readiness decision at the catalog release boundary."""

    def __init__(
        self,
        ordinal: int,
        plane: str,
        kind: str,
        severity: str,
        passed: bool,
        required: bool,
        expected: Any,
        observed: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.required = required
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "catalog gate check ordinal")
        if self.plane not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGatePlane
        }:
            raise ValidationError("catalog gate check plane is invalid")
        _text(self.kind, "catalog gate check kind", 256)
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateSeverity
        }:
            raise ValidationError("catalog gate check severity is invalid")
        _bool(self.passed, "catalog gate check passed flag")
        _bool(self.required, "catalog gate check required flag")
        _text(self.detail, "catalog gate check detail")
        _text(self.remediation, "catalog gate check remediation")
        _address(self.content_address, "catalog gate check address")
        if self.passed and self.severity != "pass":
            raise ValidationError("passed gate checks must have pass severity")
        if not self.passed and self.severity == "pass":
            raise ValidationError("failed gate checks cannot have pass severity")
        if self.required and self.severity == "warning":
            raise ValidationError("required gate checks cannot be warnings")
        if not _public(self.to_dict()):
            raise ValidationError("catalog gate check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "plane": self.plane,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "required": self.required,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    """Fail-closed release gate over catalog, runtime, federation, and assurance."""

    def __init__(
        self,
        gate_id: str,
        version: str,
        boundary: str,
        catalog_id: str,
        catalog_address: str,
        runtime_address: str,
        federation_address: str,
        assurance_address: str,
        member_count: int,
        ready_count: int,
        check_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.gate_id = gate_id
        self.version = version
        self.boundary = boundary
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.runtime_address = runtime_address
        self.federation_address = federation_address
        self.assurance_address = assurance_address
        self.member_count = member_count
        self.ready_count = ready_count
        self.check_count = check_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "catalog gate ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_VERSION
        ):
            raise ValidationError("catalog gate version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_BOUNDARY
        ):
            raise ValidationError("catalog gate boundary is invalid")
        _text(self.catalog_id, "catalog gate catalog ID", 256)
        _address(self.catalog_address, "catalog gate catalog address")
        _address(self.runtime_address, "catalog gate runtime address")
        _address(self.federation_address, "catalog gate federation address")
        _address(self.assurance_address, "catalog gate assurance address")
        _count(
            self.member_count,
            "catalog gate member count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
        )
        _count(self.ready_count, "catalog gate ready count", self.member_count)
        _count(self.check_count, "catalog gate check count")
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("catalog gate checks must be non-empty and conserved")
        for ordinal, check in enumerate(self.checks):
            if check.ordinal != ordinal:
                raise ValidationError("catalog gate check ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("catalog gate check address mismatch")
        passed = sum(item.passed for item in self.checks)
        warning = sum(not item.passed and item.severity == "warning" for item in self.checks)
        blocker = sum(not item.passed and item.severity == "blocker" for item in self.checks)
        if (self.passed_count, self.warning_count, self.blocker_count) != (
            passed,
            warning,
            blocker,
        ):
            raise ValidationError("catalog gate check counts do not conserve")
        _count(self.passed_count, "catalog gate passed count")
        _count(self.warning_count, "catalog gate warning count")
        _count(self.blocker_count, "catalog gate blocker count")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateState
        }:
            raise ValidationError("catalog gate state is invalid")
        _bool(self.release_ready, "catalog gate release-ready flag")
        _bool(self.accepted, "catalog gate accepted flag")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("catalog gate acceptance does not conserve")
        expected_state = (
            "blocked" if self.blocker_count else "held" if self.warning_count else "ready"
        )
        if self.state != expected_state:
            raise ValidationError("catalog gate state does not follow checks")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("catalog gate readiness does not conserve")
        _address(self.content_address, "catalog gate content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "version": self.version,
            "boundary": self.boundary,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "runtime_address": self.runtime_address,
            "federation_address": self.federation_address,
            "assurance_address": self.assurance_address,
            "member_count": self.member_count,
            "ready_count": self.ready_count,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _check(
    ordinal: int,
    *,
    plane: str,
    kind: str,
    passed: bool,
    required: bool,
    expected: Any,
    observed: Any,
    detail: str,
    remediation: str,
    severity: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck:
    if severity is None:
        severity = "pass" if passed else "blocker" if required else "warning"
    body = {
        "ordinal": ordinal,
        "plane": plane,
        "kind": kind,
        "severity": severity,
        "passed": passed,
        "required": required,
        "expected": expected,
        "observed": observed,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_check(
            provisional
        ),
    )


def _checks(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    federation: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateCheck,
    ...,
]:
    catalog_link = (
        runtime.catalog_address == catalog.content_address
        and federation.catalog_address == catalog.content_address
        and assurance.catalog_address == catalog.content_address
    )
    runtime_link = runtime.content_address != "" and runtime.catalog_id == catalog.catalog_id
    runtime_structurally_reconciled = runtime.accepted or (
        catalog.accepted
        and runtime.state == "blocked"
        and runtime.blocked_count == 1
        and runtime.skipped_count == 1
    )
    federation_link = (
        federation.content_address != "" and federation.catalog_id == catalog.catalog_id
    )
    assurance_link = assurance.content_address != "" and assurance.catalog_id == catalog.catalog_id
    return (
        _check(
            0,
            plane="linkage",
            kind="catalog-linkage",
            passed=catalog_link,
            required=True,
            expected=catalog.content_address,
            observed={
                "runtime": runtime.catalog_address,
                "federation": federation.catalog_address,
                "assurance": assurance.catalog_address,
            },
            detail="all downstream projections reference the same catalog address",
            remediation="recompute downstream projections from the selected catalog",
        ),
        _check(
            1,
            plane="linkage",
            kind="runtime-linkage",
            passed=runtime_link,
            required=True,
            expected=catalog.catalog_id,
            observed=runtime.catalog_id,
            detail="runtime identifies the selected catalog",
            remediation="run the catalog runtime for this catalog",
        ),
        _check(
            2,
            plane="linkage",
            kind="federation-linkage",
            passed=federation_link,
            required=True,
            expected=catalog.catalog_id,
            observed=federation.catalog_id,
            detail="federation identifies the selected catalog",
            remediation="rebuild federation from this catalog",
        ),
        _check(
            3,
            plane="linkage",
            kind="assurance-linkage",
            passed=assurance_link,
            required=True,
            expected=catalog.catalog_id,
            observed=assurance.catalog_id,
            detail="assurance identifies the selected catalog",
            remediation="recompute catalog assurance",
        ),
        _check(
            4,
            plane="catalog",
            kind="catalog-accepted",
            passed=catalog.accepted,
            required=True,
            expected=True,
            observed=catalog.accepted,
            detail="catalog structure and journal are accepted",
            remediation="repair catalog checks or member acceptance",
        ),
        _check(
            5,
            plane="runtime",
            kind="runtime-reconciled",
            passed=runtime_structurally_reconciled,
            required=True,
            expected="completed runtime or one readiness hold",
            observed={
                "state": runtime.state,
                "accepted": runtime.accepted,
                "completed": runtime.completed_count,
                "blocked": runtime.blocked_count,
                "skipped": runtime.skipped_count,
            },
            detail="catalog runtime either closed or stopped only at the readiness boundary",
            remediation="resolve structural runtime blockers before release evaluation",
        ),
        _check(
            6,
            plane="federation",
            kind="federation-accepted",
            passed=federation.accepted,
            required=True,
            expected=True,
            observed=federation.accepted,
            detail="federation policy accepted the selected member collection",
            remediation="resolve blocked members, unknown selections, or policy conflicts",
        ),
        _check(
            7,
            plane="assurance",
            kind="assurance-accepted",
            passed=assurance.accepted,
            required=True,
            expected=True,
            observed=assurance.accepted,
            detail="independent catalog assurance found no blockers",
            remediation="repair blocker findings before release evaluation",
        ),
        _check(
            8,
            plane="catalog",
            kind="catalog-release-ready",
            passed=catalog.release_ready,
            required=False,
            expected=True,
            observed=catalog.release_ready,
            detail="catalog members are all release-ready",
            remediation="resolve held catalog members",
            severity="pass" if catalog.release_ready else "warning",
        ),
        _check(
            9,
            plane="runtime",
            kind="runtime-release-ready",
            passed=runtime.release_ready,
            required=False,
            expected=True,
            observed=runtime.release_ready,
            detail="catalog runtime reached release readiness",
            remediation="resolve runtime readiness holds",
            severity="pass" if runtime.release_ready else "warning",
        ),
        _check(
            10,
            plane="federation",
            kind="federation-release-ready",
            passed=federation.release_ready,
            required=False,
            expected=True,
            observed=federation.release_ready,
            detail="selected federation is ready for closure",
            remediation="meet federation ready and policy thresholds",
            severity="pass" if federation.release_ready else "warning",
        ),
        _check(
            11,
            plane="assurance",
            kind="assurance-release-ready",
            passed=assurance.release_ready,
            required=False,
            expected=True,
            observed=assurance.release_ready,
            detail="independent assurance has no warnings",
            remediation="resolve assurance warnings before release closure",
            severity="pass" if assurance.release_ready else "warning",
        ),
        _check(
            12,
            plane="federation",
            kind="member-conservation",
            passed=federation.member_count
            == federation.ready_count + federation.held_count + federation.blocked_count,
            required=True,
            expected=federation.member_count,
            observed=federation.ready_count + federation.held_count + federation.blocked_count,
            detail="federation member state counts are conserved",
            remediation="rebuild federation member counts",
        ),
        _check(
            13,
            plane="public",
            kind="public-boundary",
            passed=_public(catalog.to_dict())
            and _public(runtime.to_dict())
            and _public(federation.to_dict())
            and _public(assurance.to_dict()),
            required=True,
            expected=True,
            observed=True,
            detail="the release gate carries no identity or private metadata",
            remediation="remove forbidden fields from public projections",
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    runtime: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogRuntime,
    federation: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    *,
    gate_id: str = "glio-noncode-review-store-catalog-gate",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    """Evaluate one immutable catalog release gate."""

    for value, label, verifier in (
        (catalog, "catalog", None),
        (
            runtime,
            "catalog runtime",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime,
        ),
        (
            federation,
            "catalog federation",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
        ),
        (
            assurance,
            "catalog assurance",
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance,
        ),
    ):
        if value is None:
            raise ValidationError(f"{label} is required")
        if verifier is not None:
            verifier(value)
    checks = _checks(catalog, runtime, federation, assurance)
    body = {
        "gate_id": _text(gate_id, "catalog gate ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_BOUNDARY,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "runtime_address": runtime.content_address,
        "federation_address": federation.content_address,
        "assurance_address": assurance.content_address,
        "member_count": federation.member_count,
        "ready_count": federation.ready_count,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "warning_count": sum(not item.passed and item.severity == "warning" for item in checks),
        "blocker_count": sum(not item.passed and item.severity == "blocker" for item in checks),
        "state": "blocked"
        if any(not item.passed and item.severity == "blocker" for item in checks)
        else "held"
        if any(not item.passed for item in checks)
        else "ready",
        "release_ready": all(item.passed for item in checks),
        "accepted": not any(not item.passed and item.severity == "blocker" for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate(
        **body, content_address="pending:gate"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_from_directory(
    directory: str | Path,
    *,
    gate_id: str = "glio-noncode-review-store-catalog-gate",
    federation_id: str = "glio-noncode-review-store-catalog-federation",
    selected_window_address: str | None = None,
    store_ids: Sequence[str] | None = None,
    require_same_window: bool = True,
    require_unique_ledger: bool = True,
    minimum_members: int = 1,
    minimum_ready: int = 1,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    catalog = load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        directory
    )
    runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        catalog
    )
    federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        catalog,
        federation_id=federation_id,
        selected_window_address=selected_window_address,
        store_ids=store_ids,
        require_same_window=require_same_window,
        require_unique_ledger=require_unique_ledger,
        minimum_members=minimum_members,
        minimum_ready=minimum_ready,
    )
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        catalog
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        catalog, runtime, federation, assurance, gate_id=gate_id
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_from_directories(
    directories: Sequence[str | Path],
    *,
    gate_id: str = "glio-noncode-review-store-catalog-gate",
    catalog_id: str = "glio-noncode-review-store-catalog",
    federation_id: str = "glio-noncode-review-store-catalog-federation",
    selected_window_address: str | None = None,
    store_ids: Sequence[str] | None = None,
    require_same_window: bool = True,
    require_unique_ledger: bool = True,
    minimum_members: int = 1,
    minimum_ready: int = 1,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_from_directories,
    )

    catalog = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_from_directories(
        directories, catalog_id=catalog_id
    )
    runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_runtime(
        catalog
    )
    federation = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        catalog,
        federation_id=federation_id,
        selected_window_address=selected_window_address,
        store_ids=store_ids,
        require_same_window=require_same_window,
        require_unique_ledger=require_unique_ledger,
        minimum_members=minimum_members,
        minimum_ready=minimum_ready,
    )
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        catalog, stores=getattr(catalog, "stores", ())
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        catalog, runtime, federation, assurance, gate_id=gate_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
    ):
        raise ValidationError("catalog gate verification requires a typed gate")
    for check in value.checks:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_check(
                check
            )
            != check.content_address
        ):
            raise ValidationError("catalog gate check address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog gate address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "plane",
        "kind",
        "severity",
        "passed",
        "required",
        "expected",
        "observed",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for check in value.checks:
        row = check.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Release Gate",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- members: `{value.member_count}`; ready: `{value.ready_count}`",
        f"- checks: `{value.check_count}`; passed: `{value.passed_count}`; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Plane | Kind | Severity | Passed | Required | Detail |",
        "|---:|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.plane} | {item.kind} | {item.severity} | {str(item.passed).lower()} | {str(item.required).lower()} | {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGate,
    *,
    plane: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    passed: bool | None = None,
    required: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate(
        value
    )
    if plane is not None and plane not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGatePlane
    }:
        raise ValidationError("catalog gate query plane is invalid")
    if severity is not None and severity not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateSeverity
    }:
        raise ValidationError("catalog gate query severity is invalid")
    if kind is not None:
        kind = _text(kind, "catalog gate query kind", 256)
    if text is not None:
        text = _text(text, "catalog gate query text")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("catalog gate query passed filter is invalid")
    if required is not None and not isinstance(required, bool):
        raise ValidationError("catalog gate query required filter is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("catalog gate query offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 512:
        raise ValidationError("catalog gate query limit is invalid")
    rows = [check.to_dict() for check in value.checks]
    if plane is not None:
        rows = [row for row in rows if row["plane"] == plane]
    if kind is not None:
        rows = [row for row in rows if row["kind"] == kind]
    if severity is not None:
        rows = [row for row in rows if row["severity"] == severity]
    if passed is not None:
        rows = [row for row in rows if row["passed"] is passed]
    if required is not None:
        rows = [row for row in rows if row["required"] is required]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {
            "plane": plane,
            "kind": kind,
            "severity": severity,
            "passed": passed,
            "required": required,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "gate": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("catalog gate query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("catalog gate query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "plane",
        "kind",
        "severity",
        "passed",
        "required",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Gate Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Plane | Kind | Severity | Passed | Required | Detail |",
        "|---:|---|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('plane', '')} | {row.get('kind', '')} | {row.get('severity', '')} | {str(row.get('passed', '')).lower()} | {str(row.get('required', '')).lower()} | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_BOUNDARY,
        "planes": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGatePlane
        ],
        "severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateSeverity
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogGateState
        ],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_VERSION,
        "operations": ["build", "verify", "query", "json", "csv", "markdown"],
        "combines": ["catalog", "runtime", "federation", "assurance"],
        "accepts_held_evidence": True,
        "fail_closed_on_blockers": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_QUERY_PREFIX
        + "-v1",
        "filters": ["plane", "kind", "severity", "passed", "required", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_gate_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_GATE_QUERY_PREFIX
        + "-v1",
        "resources": ["checks", "summary"],
        "addressed_receipts": True,
        "bounded": True,
        "identity_free": True,
    }
