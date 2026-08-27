"""Release gate above catalog packet diffs, reviews, and assurance."""

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
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance,
)
from .serialization import canonical_bytes, canonical_json, content_hash, hash_bytes

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_CHECK_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
    + "-check"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERIFICATION_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
    + "-verification"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MANIFEST = "manifest.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DOCUMENT = "gate.json"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MAX_CHECKS = 20


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateDecision(
    StrEnum
):
    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"
    SUPERSEDE = "supersede"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateState(
    StrEnum
):
    READY = "ready"
    HELD = "held"
    BLOCKED = "blocked"


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
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
    elif isinstance(value, (list, tuple)):
        return all(_public(item) for item in value)
    return True


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_CHECK_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck:
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
            "gate check ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MAX_CHECKS
            - 1,
        )
        _text(self.kind, "gate check kind", 256)
        _bool(self.passed, "gate check passed flag")
        _text(self.detail, "gate check detail")
        _address(self.content_address, "gate check content address")
        if not _public(self.to_dict()):
            raise ValidationError("gate check crosses the public boundary")

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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_verification(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateVerification,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERIFICATION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateVerification:
    def __init__(
        self,
        *,
        gate_address: str,
        check_count: int,
        passed_count: int,
        failed_count: int,
        accepted: bool,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.gate_address = gate_address
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.accepted = accepted
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _address(self.gate_address, "gate verification gate address")
        _count(
            self.check_count,
            "gate verification check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("gate verification checks are not conserved")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("gate verification counts are not conserved")
        _count(self.passed_count, "gate verification passed count", self.check_count)
        _count(self.failed_count, "gate verification failed count", self.check_count)
        _bool(self.accepted, "gate verification accepted flag")
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("gate verification acceptance is not conserved")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("gate verification check address is invalid")
        _address(self.content_address, "gate verification content address")

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_address": self.gate_address,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "accepted": self.accepted,
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate:
    def __init__(
        self,
        *,
        gate_id: str,
        version: str,
        boundary: str,
        diff_address: str,
        review_address: str,
        assurance_address: str,
        decision: str,
        diff_accepted: bool,
        review_accepted: bool,
        assurance_accepted: bool,
        review_state: str,
        assurance_release_ready: bool,
        state: str,
        release_ready: bool,
        accepted: bool,
        check_count: int,
        passed_count: int,
        failed_count: int,
        checks: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.gate_id = gate_id
        self.version = version
        self.boundary = boundary
        self.diff_address = diff_address
        self.review_address = review_address
        self.assurance_address = assurance_address
        self.decision = decision
        self.diff_accepted = diff_accepted
        self.review_accepted = review_accepted
        self.assurance_accepted = assurance_accepted
        self.review_state = review_state
        self.assurance_release_ready = assurance_release_ready
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.check_count = check_count
        self.passed_count = passed_count
        self.failed_count = failed_count
        self.checks = tuple(checks)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.gate_id, "gate ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION
        ):
            raise ValidationError("gate version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_BOUNDARY
        ):
            raise ValidationError("gate boundary is invalid")
        for value, field in (
            (self.diff_address, "gate diff address"),
            (self.review_address, "gate review address"),
            (self.assurance_address, "gate assurance address"),
        ):
            _address(value, field)
        if self.decision not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateDecision
        }:
            raise ValidationError("gate decision is invalid")
        for value, field in (
            (self.diff_accepted, "gate diff accepted"),
            (self.review_accepted, "gate review accepted"),
            (self.assurance_accepted, "gate assurance accepted"),
            (self.assurance_release_ready, "gate assurance release-ready"),
        ):
            _bool(value, field)
        if self.review_state not in {"ready", "held", "blocked"}:
            raise ValidationError("gate review state is invalid")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateState
        }:
            raise ValidationError("gate state is invalid")
        _bool(self.state == "ready", "gate ready state")
        _bool(self.release_ready, "gate release-ready")
        _bool(self.accepted, "gate accepted")
        _count(
            self.check_count,
            "gate check count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MAX_CHECKS,
        )
        if self.check_count != len(self.checks) or self.check_count == 0:
            raise ValidationError("gate checks are not conserved")
        if (self.passed_count, self.failed_count) != (
            sum(item.passed for item in self.checks),
            sum(not item.passed for item in self.checks),
        ):
            raise ValidationError("gate check counts are not conserved")
        _count(self.passed_count, "gate passed count", self.check_count)
        _count(self.failed_count, "gate failed count", self.check_count)
        if self.accepted != (self.failed_count == 0):
            raise ValidationError("gate acceptance does not follow checks")
        if self.release_ready != (
            self.accepted
            and self.decision == "promote"
            and self.review_state == "ready"
            and self.assurance_release_ready
        ):
            raise ValidationError("gate readiness does not follow release evidence")
        expected_state = (
            "blocked" if not self.accepted else "ready" if self.release_ready else "held"
        )
        if self.state != expected_state:
            raise ValidationError("gate state does not follow acceptance and readiness")
        for ordinal, check in enumerate(self.checks):
            if (
                check.ordinal != ordinal
                or address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
                    check
                )
                != check.content_address
            ):
                raise ValidationError("gate check address is invalid")
        _address(self.content_address, "gate content address")
        if not _public(self.to_dict()):
            raise ValidationError("gate crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "version": self.version,
            "boundary": self.boundary,
            "diff_address": self.diff_address,
            "review_address": self.review_address,
            "assurance_address": self.assurance_address,
            "decision": self.decision,
            "diff_accepted": self.diff_accepted,
            "review_accepted": self.review_accepted,
            "assurance_accepted": self.assurance_accepted,
            "review_state": self.review_state,
            "assurance_release_ready": self.assurance_release_ready,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "check_count": self.check_count,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_checks: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_checks:
            body["checks"] = [item.to_dict() for item in self.checks]
        return body


def _check(
    ordinal: int, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
            provisional
        ),
    )


def _decision(
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
) -> str:
    return review.entries[-1].decision


def _state(*, accepted: bool, release_ready: bool) -> str:
    return "blocked" if not accepted else "ready" if release_ready else "held"


def _checks_for(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck,
    ...,
]:
    decision = _decision(review)
    components_accepted = diff.accepted and review.accepted and assurance.accepted
    closure = decision != "block" and (
        decision != "promote"
        or (
            diff.accepted
            and diff.release_ready
            and review.release_ready
            and assurance.release_ready
        )
    )
    release_ready = (
        components_accepted
        and closure
        and decision == "promote"
        and review.state == "ready"
        and assurance.release_ready
    )
    accepted = components_accepted and closure
    expected_state = _state(accepted=accepted, release_ready=release_ready)
    return (
        _check(
            0,
            "diff-link",
            diff.content_address == assurance.diff_address
            and review.entries[-1].diff_address == diff.content_address,
            diff.content_address,
            (assurance.diff_address, review.entries[-1].diff_address),
            "gate retains the verified packet transition",
        ),
        _check(
            1,
            "review-link",
            review.content_address == assurance.review_address,
            review.content_address,
            assurance.review_address,
            "gate retains the verified packet review",
        ),
        _check(
            2,
            "component-addresses",
            all(
                ":" in value
                for value in (
                    diff.content_address,
                    review.content_address,
                    assurance.content_address,
                )
            ),
            True,
            (diff.content_address, review.content_address, assurance.content_address),
            "all release inputs are addressed",
        ),
        _check(
            3,
            "component-acceptance",
            components_accepted,
            True,
            (diff.accepted, review.accepted, assurance.accepted),
            "all structural inputs are accepted",
        ),
        _check(
            4,
            "decision-closure",
            closure,
            "promote only when ready; hold or supersede with action; block is not releasable",
            decision,
            "review decision is closed by the release policy",
        ),
        _check(
            5,
            "state-classification",
            expected_state == _state(accepted=accepted, release_ready=release_ready),
            expected_state,
            expected_state,
            "gate state follows component acceptance and readiness",
        ),
        _check(
            6,
            "readiness-classification",
            release_ready
            == (
                accepted
                and decision == "promote"
                and review.state == "ready"
                and assurance.release_ready
            ),
            release_ready,
            release_ready,
            "gate readiness follows promotion and independent assurance",
        ),
        _check(
            7,
            "public-boundary",
            _public(
                {
                    "diff_address": diff.content_address,
                    "review_address": review.content_address,
                    "assurance_address": assurance.content_address,
                    "decision": decision,
                    "state": expected_state,
                }
            ),
            True,
            True,
            "gate projection contains only public fields",
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
    *,
    gate_id: str = "glio-noncode-review-store-catalog-packet-review-gate",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate:
    if (
        not isinstance(
            diff,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff,
        )
        or not isinstance(
            review,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview,
        )
        or not isinstance(
            assurance,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance,
        )
    ):
        raise ValidationError("packet review gate requires typed diff, review, and assurance")
    checks = _checks_for(diff, review, assurance)
    accepted = all(item.passed for item in checks)
    release_ready = (
        accepted
        and _decision(review) == "promote"
        and review.state == "ready"
        and assurance.release_ready
    )
    body = {
        "gate_id": _text(gate_id, "gate ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_BOUNDARY,
        "diff_address": diff.content_address,
        "review_address": review.content_address,
        "assurance_address": assurance.content_address,
        "decision": _decision(review),
        "diff_accepted": diff.accepted,
        "review_accepted": review.accepted,
        "assurance_accepted": assurance.accepted,
        "review_state": review.state,
        "assurance_release_ready": assurance.release_ready,
        "state": _state(accepted=accepted, release_ready=release_ready),
        "release_ready": release_ready,
        "accepted": accepted,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate(
        **body, content_address="pending:gate"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_from_directories(
    left_directory: str | Path, right_directory: str | Path, **kwargs: Any
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate:
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff_from_directories,
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_from_directories,
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance import (
        build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance,
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
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
        review,
        diff=diff,
        assurance_id=kwargs.pop(
            "assurance_id", "glio-noncode-review-store-catalog-packet-review-assurance"
        ),
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        diff, review, assurance, **kwargs
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    *,
    diff: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketDiff
    | None = None,
    review: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReview
    | None = None,
    assurance: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewAssurance
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateVerification:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    ):
        raise ValidationError("packet review gate verification requires a typed gate")
    expected_checks = (
        _checks_for(diff, review, assurance)
        if diff is not None and review is not None and assurance is not None
        else value.checks
    )
    component_checks = []
    if diff is not None:
        component_checks.append(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_diff(
                diff
            ).accepted
        )
    if review is not None:
        component_checks.append(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review(
                review
            ).accepted
        )
    if assurance is not None:
        component_checks.append(
            verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_assurance(
                assurance
            ).accepted
        )
    checks = [
        _check(
            0,
            "aggregate-address",
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
                value
            )
            == value.content_address,
            value.content_address,
            value.content_address,
            "gate address is recomputed",
        ),
        _check(
            1,
            "check-conservation",
            value.check_count == len(value.checks) and value.check_count == len(expected_checks),
            (value.check_count, len(expected_checks)),
            (len(value.checks), len(expected_checks)),
            "gate check count is conserved",
        ),
        _check(
            2,
            "check-addresses",
            all(
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_check(
                    item
                )
                == item.content_address
                for item in value.checks
            ),
            True,
            tuple(item.content_address for item in value.checks),
            "gate check addresses are recomputed",
        ),
        _check(
            3,
            "check-content",
            [item.to_dict() for item in value.checks]
            == [item.to_dict() for item in expected_checks],
            [item.to_dict() for item in expected_checks],
            [item.to_dict() for item in value.checks],
            "gate checks match independent policy recomputation",
        ),
        _check(
            4,
            "count-conservation",
            value.passed_count + value.failed_count == value.check_count,
            value.check_count,
            value.passed_count + value.failed_count,
            "gate pass and fail counts are conserved",
        ),
        _check(
            5,
            "acceptance-classification",
            value.accepted == (value.failed_count == 0),
            value.failed_count == 0,
            value.accepted,
            "gate acceptance follows failed checks",
        ),
        _check(
            6,
            "readiness-classification",
            value.release_ready
            == (
                value.accepted
                and value.decision == "promote"
                and value.review_state == "ready"
                and value.assurance_release_ready
            ),
            True,
            value.release_ready,
            "gate readiness follows decision closure",
        ),
        _check(
            7,
            "state-classification",
            value.state == _state(accepted=value.accepted, release_ready=value.release_ready),
            _state(accepted=value.accepted, release_ready=value.release_ready),
            value.state,
            "gate state follows acceptance and readiness",
        ),
        _check(
            8,
            "component-links",
            not component_checks or all(component_checks),
            True,
            component_checks,
            "supplied components independently verify",
        ),
    ]
    body = {
        "gate_address": value.content_address,
        "check_count": len(checks),
        "passed_count": sum(item.passed for item in checks),
        "failed_count": sum(not item.passed for item in checks),
        "accepted": all(item.passed for item in checks),
        "checks": tuple(checks),
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateVerification(
        **body, content_address="pending:verification"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateVerification(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_verification(
            provisional
        ),
    )


def _gate_from_dict(
    value: Mapping[str, Any],
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate:
    body = dict(value)
    body["checks"] = tuple(
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateCheck(
            ordinal=item["ordinal"],
            kind=item["kind"],
            passed=item["passed"],
            expected=item["expected"],
            observed=item["observed"],
            detail=item["detail"],
            content_address=item["content_address"],
        )
        for item in body.pop("checks")
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate(
        **body
    )


def write_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    destination: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        value
    ).accepted:
        raise ValidationError("cannot persist an unverified packet review gate")
    destination = Path(destination)
    if destination.exists() and not overwrite:
        raise ValidationError("packet review gate destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{destination.name}-", dir=destination.parent))
    try:
        document = canonical_bytes(value.to_dict())
        manifest_body = {
            "manifest_version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION,
            "gate": value.to_dict(),
            "byte_count": len(document),
            "byte_address": hash_bytes(
                document,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
                + "-bytes",
            ),
        }
        manifest = manifest_body | {
            "manifest_address": content_hash(
                manifest_body,
                prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
                + "-manifest",
            )
        }
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DOCUMENT
        ).write_bytes(document)
        (
            temporary
            / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MANIFEST
        ).write_bytes(canonical_bytes(manifest))
        if destination.exists():
            if destination.is_symlink() or not destination.is_dir():
                raise ValidationError("packet review gate destination is not a regular directory")
            shutil.rmtree(destination)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    directory: str | Path,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate:
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValidationError("packet review gate directory is invalid")
    expected = {
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MANIFEST,
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DOCUMENT,
    }
    children = tuple(directory.iterdir())
    if (
        any(item.is_symlink() or not item.is_file() for item in children)
        or {item.name for item in children} != expected
    ):
        raise ValidationError("packet review gate files do not match the published set")
    manifest_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MANIFEST
    )
    document_path = (
        directory
        / MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DOCUMENT
    )
    manifest_raw = manifest_path.read_bytes()
    document_raw = document_path.read_bytes()
    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
        document = json.loads(document_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("packet review gate files are not valid JSON") from exc
    if (
        not isinstance(manifest, dict)
        or not isinstance(document, dict)
        or canonical_bytes(manifest) != manifest_raw
        or canonical_bytes(document) != document_raw
    ):
        raise ValidationError("packet review gate files must be canonical JSON objects")
    if (
        set(manifest)
        != {"manifest_version", "gate", "byte_count", "byte_address", "manifest_address"}
        or manifest.get("manifest_version")
        != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION
    ):
        raise ValidationError("packet review gate manifest structure is invalid")
    manifest_body = {key: item for key, item in manifest.items() if key != "manifest_address"}
    if manifest["manifest_address"] != content_hash(
        manifest_body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
        + "-manifest",
    ):
        raise ValidationError("packet review gate manifest address mismatch")
    if (
        manifest["gate"] != document
        or manifest["byte_count"] != len(document_raw)
        or manifest["byte_address"]
        != hash_bytes(
            document_raw,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_PREFIX
            + "-bytes",
        )
    ):
        raise ValidationError("packet review gate document does not match the manifest")
    gate = _gate_from_dict(document)
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        gate
    ).accepted:
        raise ValidationError("packet review gate verification failed")
    return gate


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
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
    for check in value.checks:
        row = check.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        value
    )
    lines = [
        "# Catalog Packet Review Gate",
        "",
        f"- decision: `{value.decision}`",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Kind | State | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | `{item.kind}` | `{str(item.passed).lower()}` | {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGate,
    *,
    resource: str = "checks",
    kind: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate(
        value
    )
    if resource not in {"summary", "checks"}:
        raise ValidationError("packet review gate query resource is invalid")
    if kind is not None:
        kind = _text(kind, "packet review gate query kind", 256)
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("packet review gate query passed filter is invalid")
    if text is not None:
        text = _text(text, "packet review gate query text")
    if (
        isinstance(offset, bool)
        or not isinstance(offset, int)
        or offset < 0
        or isinstance(limit, bool)
        or not isinstance(limit, int)
        or not 1 <= limit <= 512
    ):
        raise ValidationError("packet review gate query bounds are invalid")
    rows = [value.summary()] if resource == "summary" else [item.to_dict() for item in value.checks]
    if resource == "checks" and kind is not None:
        rows = [row for row in rows if row["kind"] == kind]
    if resource == "checks" and passed is not None:
        rows = [row for row in rows if row["passed"] == passed]
    if text is not None:
        rows = [row for row in rows if text.casefold() in canonical_json(row).casefold()]
    body = {
        "query": {"resource": resource, "kind": kind, "passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "gate": value.summary(),
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("packet review gate query must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("packet review gate query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
        value
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=(
            "ordinal",
            "kind",
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


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query(
        value
    )
    lines = [
        "# Catalog Packet Review Gate Query",
        "",
        f"- resource: `{value['query']['resource']}`",
        f"- total: `{value['total']}`",
        f"- address: `{value['content_address']}`",
        "",
        "| # | Kind | State | Detail |",
        "|---:|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('kind', '')}` | `{row.get('state', '')}` | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_BOUNDARY,
        "decisions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateDecision
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogPacketReviewGateState
        ],
        "resources": ["summary", "checks"],
        "exact_files": ["manifest.json", "gate.json"],
        "max_checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_MAX_CHECKS,
        "bounded": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_VERSION,
        "operations": ["build", "verify", "write", "load", "query", "json", "csv", "markdown"],
        "independent_component_links": True,
        "decision_closure": True,
        "atomic_write": True,
        "canonical_json": True,
        "fail_closed": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "checks"],
        "filters": ["kind", "passed", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_packet_review_gate_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_PACKET_REVIEW_GATE_QUERY_PREFIX
        + "-v1",
        "resources": ["summary", "checks"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }
