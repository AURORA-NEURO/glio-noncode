"""Independent assurance for catalog packet review decisions."""

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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_FINDING_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
    + "-finding"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DOCUMENT = "assurance.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_FINDINGS = 16
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_CHECKS = 24


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceSeverity(
    StrEnum
):
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFindingState(
    StrEnum
):
    PASSED = "passed"
    FAILED = "failed"


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


def _count(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValidationError(f"{field} is outside its bounded range")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_FINDING_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding:
    def __init__(
        self,
        *,
        ordinal: int,
        kind: str,
        severity: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "assurance finding ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_FINDINGS
            - 1,
        )
        _text(self.kind, "assurance finding kind", 256)
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceSeverity
        }:
            raise ValidationError("assurance finding severity is invalid")
        _bool(self.passed, "assurance finding passed flag")
        _text(self.detail, "assurance finding detail")
        _address(self.content_address, "assurance finding content address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance finding crosses the public boundary")

    @property
    def state(self) -> str:
        return "passed" if self.passed else "failed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "severity": self.severity,
            "state": self.state,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck:
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
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "assurance check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "assurance check kind", 256)
        _bool(self.passed, "assurance check passed flag")
        _text(self.detail, "assurance check detail")
        _address(self.content_address, "assurance check content address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance check crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "kind": self.kind,
            "state": "passed" if self.passed else "failed",
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceVerification:
    def __init__(
        self,
        *,
        assurance_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.assurance_address = assurance_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.assurance_address, "assurance verification assurance address")
        _count(
            self.check_count,
            "assurance verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("assurance verification checks are not conserved")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("assurance verification counts are not conserved")
        _count(self.passed_count, "assurance verification passed count", self.check_count)
        _count(self.failed_count, "assurance verification failed count", self.check_count)
        _bool(self.accepted, "assurance verification accepted flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("assurance verification acceptance is not conserved")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("assurance verification check address is invalid")
        _address(self.content_address, "assurance verification content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "assurance_address": self.assurance_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance:
    def __init__(
        self,
        *,
        assurance_id: str,
        version: str,
        boundary: str,
        review_address: str,
        diff_address: str | None,
        review_state: str,
        review_release_ready: bool,
        review_accepted: bool,
        finding_count: int,
        passed_count: int,
        failed_count: int,
        blocker_count: int,
        warning_count: int,
        accepted: bool,
        release_ready: bool,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.review_address = review_address
        self.diff_address = diff_address
        self.review_state = review_state
        self.review_release_ready = review_release_ready
        self.review_accepted = review_accepted
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.blocker_count = blocker_count
        self.warning_count = warning_count
        self.accepted = accepted
        self.release_ready = release_ready
        self.findings = tuple(findings)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "assurance ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION
        ):
            raise ValidationError("assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_BOUNDARY
        ):
            raise ValidationError("assurance boundary is invalid")
        _address(self.review_address, "assurance review address")
        _address(self.diff_address, "assurance diff address", optional=True)
        if self.review_state not in {"ready", "held", "blocked"}:
            raise ValidationError("assurance review state is invalid")
        _bool(self.review_release_ready, "assurance review release-ready flag")
        _bool(self.review_accepted, "assurance review accepted flag")
        _count(
            self.finding_count,
            "assurance finding count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_FINDINGS,
        )
        if self.finding_count != len(self.findings) or self.finding_count == 0:
            raise ValidationError("assurance findings are not conserved")
        for ordinal, finding in enumerate(self.findings):
            if (
                finding.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_finding(
                    finding
                )
                != finding.content_address
            ):
                raise ValidationError("assurance finding address is invalid")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.findings),
            sum(not item.passed for item in self.findings),
        ):
            raise ValidationError("assurance finding pass counts are not conserved")
        if (self.blocker_count, self.warning_count) != (
            sum(not item.passed and item.severity == "blocker" for item in self.findings),
            sum(not item.passed and item.severity == "warning" for item in self.findings),
        ):
            raise ValidationError("assurance severity counts are not conserved")
        for value, field in (
            (self.passed_count, "assurance passed count"),
            (self.failed_count, "assurance failed count"),
            (self.blocker_count, "assurance blocker count"),
            (self.warning_count, "assurance warning count"),
        ):
            _count(value, field, self.finding_count)
        _bool(self.accepted, "assurance accepted flag")
        _bool(self.release_ready, "assurance release-ready flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("assurance acceptance is not conserved")
        if self.release_ready != (
            self.accepted and self.review_state == "ready" and self.review_release_ready
        ):
            raise ValidationError("assurance readiness is not conserved")
        _address(self.content_address, "assurance content address")
        if not _public(self.to_dict()):
            raise ValidationError("assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "review_address": self.review_address,
            "diff_address": self.diff_address,
            "review_state": self.review_state,
            "review_release_ready": self.review_release_ready,
            "review_accepted": self.review_accepted,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "accepted": self.accepted,
            "release_ready": self.release_ready,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def _finding(
    ordinal: int, kind: str, severity: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "severity": severity,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding(
        **body, content_address="pending:finding"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_finding(
            provisional
        ),
    )


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_check(
            provisional
        ),
    )


def _review_policy(
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> bool:
    return all(
        (
            entry.decision != "promote"
            or (
                entry.diff_accepted
                and entry.diff_release_ready
                and entry.right_state == "ready"
                and entry.right_release_ready
            )
        )
        and (entry.decision == "promote" or entry.action_required)
        for entry in review.entries
    )


def _findings(
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding,
    ...,
]:
    review_receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
        review, diff=diff
    )
    findings = [
        _finding(
            0,
            "review-structure",
            "blocker",
            review_receipt.accepted,
            True,
            review_receipt.accepted,
            "review chain and entry addresses are independently verified",
        ),
        _finding(
            1,
            "decision-policy",
            "blocker",
            _review_policy(review),
            True,
            _review_policy(review),
            "promotion and required-action rules are recomputed",
        ),
        _finding(
            2,
            "head-conservation",
            "blocker",
            review.head_address == review.entries[-1].content_address,
            review.entries[-1].content_address,
            review.head_address,
            "review head equals the final entry address",
        ),
        _finding(
            3,
            "readiness-classification",
            "warning",
            review.release_ready == (review.state == "ready"),
            review.state == "ready",
            review.release_ready,
            "review readiness follows its state",
        ),
        _finding(
            4,
            "public-boundary",
            "blocker",
            _public(review.to_dict()),
            True,
            _public(review.to_dict()),
            "review projection contains only public fields",
        ),
    ]
    if diff is not None:
        diff_receipt = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
            diff
        )
        head = review.entries[-1]
        findings.extend(
            (
                _finding(
                    5,
                    "diff-structure",
                    "blocker",
                    True,
                    diff_receipt.accepted,
                    diff_receipt.accepted,
                    "supplied packet diff is independently verified",
                ),
                _finding(
                    6,
                    "diff-linkage",
                    "blocker",
                    head.diff_address == diff.content_address
                    and head.left_packet_address == diff.left_packet_address
                    and head.right_packet_address == diff.right_packet_address,
                    diff.content_address,
                    head.diff_address,
                    "review head retains the supplied packet transition",
                ),
                _finding(
                    7,
                    "diff-readiness",
                    "warning",
                    head.diff_release_ready == diff.release_ready
                    and head.diff_accepted == diff.accepted,
                    (diff.accepted, diff.release_ready),
                    (head.diff_accepted, head.diff_release_ready),
                    "review head retains diff acceptance and readiness",
                ),
            )
        )
    return tuple(findings)


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    *,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
    assurance_id: str = "glio-noncode-review-store-catalog-packet-review-assurance",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance:
    if not isinstance(
        review,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    ):
        raise ValidationError("packet review assurance requires a typed review")
    if diff is not None and not isinstance(
        diff,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    ):
        raise ValidationError("packet review assurance diff must be typed")
    findings = _findings(review, diff)
    body = {
        "assurance_id": _text(assurance_id, "assurance ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_BOUNDARY,
        "review_address": review.content_address,
        "diff_address": None if diff is None else diff.content_address,
        "review_state": review.state,
        "review_release_ready": review.release_ready,
        "review_accepted": review.accepted,
        "finding_count": len(findings),
        "passed_count": sum(item.passed for item in findings),
        "failed_count": sum(not item.passed for item in findings),
        "blocker_count": sum(not item.passed and item.severity == "blocker" for item in findings),
        "warning_count": sum(not item.passed and item.severity == "warning" for item in findings),
        "accepted": all(item.passed for item in findings),
        "release_ready": all(item.passed for item in findings)
        and review.state == "ready"
        and review.release_ready,
        "findings": findings,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance(
        **body, content_address="pending:assurance"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_from_directories(
    left_directory: str | Path,
    right_directory: str | Path,
    **kwargs: Any,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories,
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories,
    )

    diff = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories(
        left_directory,
        right_directory,
        diff_id=kwargs.pop("diff_id", "glio-noncode-review-store-catalog-packet-diff"),
    )
    review = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories(
        left_directory,
        right_directory,
        diff_id=diff.diff_id,
        review_id=kwargs.pop("review_id", "glio-noncode-review-store-catalog-packet-review"),
        decision=kwargs.pop("decision", None),
        decision_id=kwargs.pop(
            "decision_id", "glio-noncode-review-store-catalog-packet-decision-0"
        ),
        detail=kwargs.pop("detail", None),
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        review, diff=diff, **kwargs
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    *,
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview
    | None = None,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    ):
        raise ValidationError("packet review assurance verification requires a typed assurance")
    expected_findings = _findings(review, diff) if review is not None else value.findings
    checks = [
        _check(
            0,
            "aggregate-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                value
            )
            == value.content_address,
            value.content_address,
            value.content_address,
            "assurance address is recomputed",
        ),
        _check(
            1,
            "finding-conservation",
            value.finding_count == len(value.findings)
            and value.finding_count == len(expected_findings),
            (value.finding_count, len(expected_findings)),
            (len(value.findings), len(expected_findings)),
            "finding count and independent finding set are conserved",
        ),
        _check(
            2,
            "finding-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_finding(
                    item
                )
                == item.content_address
                for item in value.findings
            ),
            True,
            tuple(item.content_address for item in value.findings),
            "finding addresses are recomputed",
        ),
        _check(
            3,
            "finding-content",
            [item.to_dict() for item in value.findings]
            == [item.to_dict() for item in expected_findings],
            [item.to_dict() for item in expected_findings],
            [item.to_dict() for item in value.findings],
            "independent findings match the recorded evidence",
        ),
        _check(
            4,
            "count-conservation",
            value.passed_count + value.failed_count == value.finding_count
            and value.blocker_count + value.warning_count <= value.failed_count,
            value.finding_count,
            (value.passed_count + value.failed_count, value.blocker_count + value.warning_count),
            "pass and severity counts are conserved",
        ),
        _check(
            5,
            "acceptance-classification",
            value.accepted == (value.failed_count == 0),
            value.failed_count == 0,
            value.accepted,
            "assurance acceptance follows finding failures",
        ),
        _check(
            6,
            "readiness-classification",
            value.release_ready
            == (value.accepted and value.review_state == "ready" and value.review_release_ready),
            value.review_state == "ready" and value.review_release_ready,
            value.release_ready,
            "assurance readiness follows accepted ready review evidence",
        ),
        _check(
            7,
            "public-boundary",
            _public(value.to_dict()),
            True,
            _public(value.to_dict()),
            "assurance projection remains public",
        ),
    ]
    if review is not None:
        checks.append(
            _check(
                8,
                "review-link",
                value.review_address == review.content_address,
                review.content_address,
                value.review_address,
                "assurance retains the supplied review address",
            )
        )
    body = {
        "assurance_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_verification(
            provisional
        ),
    )


def _finding_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding:
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFinding(
        ordinal=value["ordinal"],
        kind=value["kind"],
        severity=value["severity"],
        passed=value["passed"],
        expected=value["expected"],
        observed=value["observed"],
        detail=value["detail"],
        content_address=value["content_address"],
    )


def _assurance_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance:
    body = dict(value)
    body["findings"] = tuple(_finding_from_dict(item) for item in body.pop("findings"))
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance(
        **body
    )


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        value
    ).accepted:
        raise ValidationError("cannot persist an unverified packet review assurance")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("packet review assurance destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        manifest_body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION,
            "assurance": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
                + "-bytes",
            ),
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError(
                    "packet review assurance destination is not a regular directory"
                )
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _read_json(path: Path, field: str) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{field} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ValidationError(f"{field} must be canonical JSON object")
    return value


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("packet review assurance directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("packet review assurance files do not match the published set")
    manifest = _read_json(
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MANIFEST,
        "packet review assurance manifest",
    )
    if (
        set(manifest)
        != {"manifest_version", "assurance", "byte_count", "byte_address", "manifest_address"}
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION
    ):
        raise ValidationError("packet review assurance manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
        + "-manifest",
    ):
        raise ValidationError("packet review assurance manifest address mismatch")
    document_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DOCUMENT
    )
    document = document_path.read_bytes()
    if (
        len(document) != manifest["byte_count"]
        or hash_bytes(
            document,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_PREFIX
            + "-bytes",
        )
        != manifest["byte_address"]
    ):
        raise ValidationError("packet review assurance document bytes do not match the manifest")
    document_value = _read_json(document_path, "packet review assurance document")
    if document_value != manifest["assurance"]:
        raise ValidationError("packet review assurance manifest document diverges")
    assurance = _assurance_from_dict(document_value)
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        assurance
    ).accepted:
        raise ValidationError("packet review assurance verification failed")
    return assurance


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
            "severity",
            "state",
            "passed",
            "expected",
            "observed",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for finding in value.findings:
        row = finding.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        value
    )
    lines = [
        "# Catalog Packet Review Assurance",
        "",
        f"- state: `{value.review_state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- blockers: `{value.blocker_count}`",
        f"- warnings: `{value.warning_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | Severity | State | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.kind}` | `{item.severity}` | `{item.state}` | {item.detail} |"
        for item in value.findings
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    *,
    resource: str = "findings",
    severity: str | None = None,
    passed: bool | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        value
    )
    if resource not in {"summary", "findings", "checks"}:
        raise ValidationError("packet review assurance query resource is invalid")
    if severity is not None and severity not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceSeverity
    }:
        raise ValidationError("packet review assurance query severity is invalid")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet review assurance query passed filter is invalid")
    if kind is not None:
        kind = _text(kind, "packet review assurance query kind", 256)
    if text is not None:
        text = _text(text, "packet review assurance query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("packet review assurance query bounds are invalid")
    if resource == "summary":
        rows = [value.summary()]
    elif resource == "checks":
        rows = [
            item.to_dict()
            for item in verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                value
            ).checks
        ]
    else:
        rows = [item.to_dict() for item in value.findings]
        if severity is not None:
            rows = [row for row in rows if row["severity"] == severity]
        if passed is not None:
            rows = [row for row in rows if row["passed"] == passed]
        if kind is not None:
            rows = [row for row in rows if row["kind"] == kind]
    if text is not None:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "query": {
            "resource": resource,
            "severity": severity,
            "passed": passed,
            "kind": kind,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "assurance": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet review assurance query must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("packet review assurance query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
            "severity",
            "state",
            "passed",
            "expected",
            "observed",
            "detail",
            "content_address",
        ),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in value.get("items", []):
        row = dict(item)
        row["expected"] = canonical_json(row.get("expected"))
        row["observed"] = canonical_json(row.get("observed"))
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query(
        value
    )
    lines = [
        "# Catalog Packet Review Assurance Query",
        "",
        f"- resource: `{value['query']['resource']}`",
        f"- total: `{value['total']}`",
        f"- address: `{value['content_address']}`",
        "",
        "| # | Kind | Severity | State | Detail |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('kind', '')}` | `{row.get('severity', '')}` | `{row.get('state', '')}` | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_BOUNDARY,
        "severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceSeverity
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssuranceFindingState
        ],
        "resources": ["summary", "findings", "checks"],
        "exact_files": ["manifest.json", "assurance.json"],
        "max_findings": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_MAX_FINDINGS,
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_VERSION,
        "operations": ["build", "verify", "write", "load", "query", "json", "csv", "markdown"],
        "independent_recomputation": True,
        "atomic_write": True,
        "canonical_json": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "findings", "checks"],
        "filters": ["severity", "passed", "kind", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "findings", "checks"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }
