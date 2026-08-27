"""Independent assurance for durable review-store catalogs.

The catalog verifier proves that a typed catalog is internally well formed.
This module deliberately recomputes the important relationships again and
emits an addressed finding receipt.  It is useful at the release boundary
because a catalog can be accepted while held for readiness, whereas a broken
member, broken journal, or broken public projection must fail closed.
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
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_from_directories,
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation,
)
from .serialization import canonical_json, content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_FINDING_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance-finding"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_QUERY_PREFIX = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_PREFIX
    + "-query"
)
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_MAX_FINDINGS = (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
    + 16
)


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceSeverity(
    StrEnum
):
    PASS = "pass"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceState(
    StrEnum
):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurancePlane(
    StrEnum
):
    CATALOG = "catalog"
    ENTRIES = "entries"
    OPERATIONS = "operations"
    WINDOWS = "windows"
    HYDRATION = "hydration"
    READINESS = "readiness"
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


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _count(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_MAX_FINDINGS,
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


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_FINDING_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding:
    """One independently recomputed catalog assurance finding."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        plane: str,
        kind: str,
        severity: str,
        passed: bool,
        expected: Any,
        observed: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.plane = plane
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.expected = expected
        self.observed = observed
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "catalog assurance finding ordinal")
        _text(self.finding_id, "catalog assurance finding ID", 256)
        if self.plane not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurancePlane
        }:
            raise ValidationError("catalog assurance finding plane is invalid")
        _text(self.kind, "catalog assurance finding kind", 256)
        if self.severity not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceSeverity
        }:
            raise ValidationError("catalog assurance finding severity is invalid")
        _bool(self.passed, "catalog assurance finding passed flag")
        _text(self.detail, "catalog assurance finding detail")
        _text(self.remediation, "catalog assurance finding remediation")
        _address(self.content_address, "catalog assurance finding address")
        if self.passed and self.severity != "pass":
            raise ValidationError("passed catalog findings must have pass severity")
        if not self.passed and self.severity == "pass":
            raise ValidationError("failed catalog findings cannot have pass severity")
        if not _public(self.to_dict()):
            raise ValidationError("catalog assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "plane": self.plane,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "expected": self.expected,
            "observed": self.observed,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> str:
    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    """Addressed catalog assurance with conserved findings and counts."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        catalog_id: str,
        catalog_address: str,
        entry_count: int,
        operation_count: int,
        hydrated_store_count: int,
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding,
            ...,
        ],
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.catalog_id = catalog_id
        self.catalog_address = catalog_address
        self.entry_count = entry_count
        self.operation_count = operation_count
        self.hydrated_store_count = hydrated_store_count
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.findings = tuple(findings)
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "catalog assurance ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_VERSION
        ):
            raise ValidationError("catalog assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_BOUNDARY
        ):
            raise ValidationError("catalog assurance boundary is invalid")
        _text(self.catalog_id, "catalog assurance catalog ID", 256)
        _address(self.catalog_address, "catalog assurance catalog address")
        _count(
            self.entry_count,
            "catalog assurance entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
        )
        _count(
            self.operation_count,
            "catalog assurance operation count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
        )
        _count(self.hydrated_store_count, "catalog assurance hydrated store count")
        _count(self.finding_count, "catalog assurance finding count")
        if self.finding_count != len(self.findings) or self.finding_count == 0:
            raise ValidationError("catalog assurance findings must be non-empty and conserved")
        for ordinal, finding in enumerate(self.findings):
            if finding.ordinal != ordinal:
                raise ValidationError("catalog assurance finding ordinals are not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_finding(
                    finding
                )
                != finding.content_address
            ):
                raise ValidationError("catalog assurance finding address mismatch")
        passed = sum(item.passed for item in self.findings)
        warning = sum(not item.passed and item.severity == "warning" for item in self.findings)
        blocker = sum(not item.passed and item.severity == "blocker" for item in self.findings)
        if (self.passed_count, self.warning_count, self.blocker_count) != (
            passed,
            warning,
            blocker,
        ):
            raise ValidationError("catalog assurance finding counts do not conserve")
        _count(self.passed_count, "catalog assurance passed count")
        _count(self.warning_count, "catalog assurance warning count")
        _count(self.blocker_count, "catalog assurance blocker count")
        if self.state not in {
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceState
        }:
            raise ValidationError("catalog assurance state is invalid")
        _bool(self.release_ready, "catalog assurance release-ready flag")
        _bool(self.accepted, "catalog assurance accepted flag")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("catalog assurance acceptance does not conserve")
        expected_state = (
            "blocked" if self.blocker_count else "warning" if self.warning_count else "passed"
        )
        if self.state != expected_state:
            raise ValidationError("catalog assurance state does not follow findings")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("catalog assurance readiness does not conserve")
        _address(self.content_address, "catalog assurance content address")
        if not _public(self.to_dict()):
            raise ValidationError("catalog assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "entry_count": self.entry_count,
            "operation_count": self.operation_count,
            "hydrated_store_count": self.hydrated_store_count,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def _finding(
    ordinal: int,
    *,
    plane: str,
    kind: str,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
    remediation: str,
    severity: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding:
    if severity is None:
        severity = "pass" if passed else "blocker"
    body = {
        "ordinal": ordinal,
        "finding_id": f"review-store-catalog-assurance-{ordinal}-{kind}",
        "plane": plane,
        "kind": kind,
        "severity": severity,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
        "remediation": remediation,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding(
        **body, content_address="pending:finding"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceFinding(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_finding(
            provisional
        ),
    )


def _catalog_member_address_ok(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> bool:
    return all(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_entry(
            entry
        )
        == entry.content_address
        for entry in catalog.entries
    )


def _catalog_operation_address_ok(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> bool:
    return all(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_operation(
            operation
        )
        == operation.content_address
        for operation in catalog.operations
    )


def _journal_ok(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
) -> bool:
    if not catalog.operations or catalog.operations[0].kind != "genesis":
        return False
    if catalog.operations[0].previous_operation_address is not None:
        return False
    registrations = catalog.operations[1:]
    if len(registrations) != len(catalog.entries):
        return False
    entry_by_id = {entry.store_id: entry for entry in catalog.entries}
    for ordinal, operation in enumerate(catalog.operations):
        if operation.ordinal != ordinal or not operation.accepted:
            return False
        if (
            ordinal
            and operation.previous_operation_address
            != catalog.operations[ordinal - 1].content_address
        ):
            return False
    return all(
        operation.kind == "register"
        and operation.output_address
        == entry_by_id.get(operation.operation_id.removeprefix("register-")).content_address
        if operation.operation_id.removeprefix("register-") in entry_by_id
        else False
        for operation in registrations
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    stores: Sequence[Any] | None = None,
    assurance_id: str = "glio-noncode-review-store-catalog-assurance",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    """Recompute catalog integrity, hydration, readiness, and public safety."""

    if not isinstance(
        catalog,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("catalog assurance requires a typed catalog")
    verification = verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        catalog, stores=stores
    )
    hydrated = tuple(stores if stores is not None else getattr(catalog, "stores", ()))
    hydrated_by_id = {str(getattr(store, "store_id", "")): store for store in hydrated}
    hydrated_ok = (
        not hydrated
        or len(hydrated) == len(hydrated_by_id) == len(catalog.entries)
        and all(
            getattr(hydrated_by_id.get(entry.store_id), "content_address", None)
            == entry.store_address
            for entry in catalog.entries
        )
    )
    ids = tuple(entry.store_id for entry in catalog.entries)
    store_addresses = tuple(entry.store_address for entry in catalog.entries)
    windows = tuple(entry.window_address for entry in catalog.entries)
    checks_ok = all(
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_check(
            check
        )
        == check.content_address
        for check in catalog.checks
    )
    member_acceptance = bool(catalog.entries) and all(entry.accepted for entry in catalog.entries)
    acceptance_expected = (
        bool(catalog.entries)
        and member_acceptance
        and all(operation.accepted for operation in catalog.operations)
        and all(check.passed for check in catalog.checks)
    )
    findings = (
        _finding(
            0,
            plane="catalog",
            kind="catalog-address",
            passed=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
                catalog
            )
            == catalog.content_address,
            expected="recomputed catalog address",
            observed=catalog.content_address,
            detail="catalog aggregate address is recomputed independently",
            remediation="rebuild the catalog from canonical entries and operations",
        ),
        _finding(
            1,
            plane="catalog",
            kind="version-boundary",
            passed=catalog.version
            == MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION
            and bool(catalog.boundary),
            expected=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
            observed={"version": catalog.version, "boundary": catalog.boundary},
            detail="catalog version and boundary remain on the published contract",
            remediation="rebuild with the published catalog contract",
        ),
        _finding(
            2,
            plane="entries",
            kind="entry-conservation",
            passed=catalog.entry_count == len(catalog.entries)
            and tuple(entry.ordinal for entry in catalog.entries)
            == tuple(range(len(catalog.entries)))
            and len(ids) == len(set(ids)),
            expected={
                "count": catalog.entry_count,
                "contiguous_ordinals": True,
                "unique_ids": True,
            },
            observed={"count": len(catalog.entries), "unique_ids": len(set(ids))},
            detail="entry count, ordinals, and store IDs are conserved",
            remediation="rebuild entries with contiguous ordinals and unique store IDs",
        ),
        _finding(
            3,
            plane="entries",
            kind="entry-addresses",
            passed=_catalog_member_address_ok(catalog)
            and len(store_addresses) == len(set(store_addresses))
            and all(":" in address for address in store_addresses),
            expected="unique addressed catalog entries and stores",
            observed={
                "entry_count": len(catalog.entries),
                "store_address_count": len(set(store_addresses)),
            },
            detail="entry and member addresses are independently recomputed",
            remediation="rebuild the catalog entry address chain",
        ),
        _finding(
            4,
            plane="operations",
            kind="operation-conservation",
            passed=catalog.operation_count == len(catalog.operations)
            and catalog.operation_count == catalog.entry_count + 1
            and _catalog_operation_address_ok(catalog),
            expected={"operation_count": catalog.entry_count + 1, "addressed": True},
            observed={
                "operation_count": len(catalog.operations),
                "addressed": _catalog_operation_address_ok(catalog),
            },
            detail="genesis plus one registration operation is conserved",
            remediation="rebuild the append-only registration journal",
        ),
        _finding(
            5,
            plane="operations",
            kind="journal-linkage",
            passed=_journal_ok(catalog),
            expected="genesis followed by linked registration operations",
            observed={
                "operation_count": len(catalog.operations),
                "append_only": catalog.append_only,
            },
            detail="journal predecessors and registration outputs point to catalog entries",
            remediation="repair operation predecessors and registration output links",
        ),
        _finding(
            6,
            plane="entries",
            kind="member-acceptance",
            passed=member_acceptance,
            expected=True,
            observed=member_acceptance,
            detail="every catalog member is an accepted durable review store",
            remediation="review or remove rejected member stores before cataloging",
        ),
        _finding(
            7,
            plane="windows",
            kind="window-reconciliation",
            passed=bool(catalog.entries) and all(":" in window for window in windows),
            expected="one content address per member evidence window",
            observed={"distinct_windows": len(set(windows)), "member_count": len(windows)},
            detail="evidence-window references are retained for downstream federation",
            remediation="rebuild entries with their addressed evidence windows",
        ),
        _finding(
            8,
            plane="hydration",
            kind="hydrated-members",
            passed=hydrated_ok,
            expected="provided stores match catalog member addresses",
            observed={"provided": bool(hydrated), "hydrated_count": len(hydrated_by_id)},
            detail="optional hydrated stores reconcile to catalog addresses",
            remediation="hydrate exactly the stores declared by the catalog",
        ),
        _finding(
            9,
            plane="catalog",
            kind="catalog-verification",
            passed=verification.accepted and checks_ok,
            expected=True,
            observed={
                "verification_accepted": verification.accepted,
                "checks_addressed": checks_ok,
            },
            detail="the catalog verifier and recomputed check addresses agree",
            remediation="repair failed catalog checks before release evaluation",
        ),
        _finding(
            10,
            plane="catalog",
            kind="acceptance-conservation",
            passed=catalog.accepted == acceptance_expected,
            expected=acceptance_expected,
            observed=catalog.accepted,
            detail="catalog acceptance follows member, journal, and check evidence",
            remediation="rebuild the aggregate after changing any catalog evidence",
        ),
        _finding(
            11,
            plane="readiness",
            kind="release-readiness",
            passed=catalog.release_ready,
            expected=True,
            observed={"release_ready": catalog.release_ready, "state": catalog.state},
            detail="catalog is ready for release federation",
            remediation="resolve held member stores before release closure",
            severity="pass"
            if catalog.release_ready
            else "warning"
            if catalog.entries and catalog.accepted
            else "blocker",
        ),
        _finding(
            12,
            plane="public",
            kind="public-boundary",
            passed=_public(catalog.to_dict()),
            expected=True,
            observed=True,
            detail="catalog assurance output contains only deterministic public fields",
            remediation="remove identity, attribution, private, or machine-specific fields",
        ),
    )
    body = {
        "assurance_id": _text(assurance_id, "catalog assurance ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_BOUNDARY,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "entry_count": catalog.entry_count,
        "operation_count": catalog.operation_count,
        "hydrated_store_count": len(hydrated_by_id),
        "finding_count": len(findings),
        "passed_count": sum(item.passed for item in findings),
        "warning_count": sum(not item.passed and item.severity == "warning" for item in findings),
        "blocker_count": sum(not item.passed and item.severity == "blocker" for item in findings),
        "state": "blocked"
        if any(not item.passed and item.severity == "blocker" for item in findings)
        else "warning"
        if any(not item.passed for item in findings)
        else "passed",
        "release_ready": all(item.passed for item in findings),
        "accepted": not any(not item.passed and item.severity == "blocker" for item in findings),
        "findings": findings,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance(
        **body, content_address="pending:assurance"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_from_directory(
    directory: str | Path,
    *,
    assurance_id: str = "glio-noncode-review-store-catalog-assurance",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            directory
        ),
        assurance_id=assurance_id,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_from_directories(
    directories: Sequence[str | Path],
    *,
    catalog_id: str = "glio-noncode-review-store-catalog",
    assurance_id: str = "glio-noncode-review-store-catalog-assurance",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    catalog = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_from_directories(
        directories, catalog_id=catalog_id
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        catalog, stores=getattr(catalog, "stores", ()), assurance_id=assurance_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    ):
        raise ValidationError("catalog assurance verification requires a typed assurance")
    for finding in value.findings:
        if (
            address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_finding(
                finding
            )
            != finding.content_address
        ):
            raise ValidationError("catalog assurance finding address mismatch")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
            value
        )
        != value.content_address
    ):
        raise ValidationError("catalog assurance address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "plane",
        "kind",
        "severity",
        "passed",
        "expected",
        "observed",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for finding in value.findings:
        row = finding.to_dict()
        row["expected"] = canonical_json(row["expected"])
        row["observed"] = canonical_json(row["observed"])
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Assurance",
        "",
        f"- state: `{value.state}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- findings: `{value.finding_count}`; passed: `{value.passed_count}`; warnings: `{value.warning_count}`; blockers: `{value.blocker_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Plane | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {item.ordinal} | {item.plane} | {item.kind} | {item.severity} | {str(item.passed).lower()} | {item.detail} |"
        for item in value.findings
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurance,
    *,
    plane: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance(
        value
    )
    if plane is not None and plane not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurancePlane
    }:
        raise ValidationError("catalog assurance query plane is invalid")
    if severity is not None and severity not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceSeverity
    }:
        raise ValidationError("catalog assurance query severity is invalid")
    if kind is not None:
        kind = _text(kind, "catalog assurance query kind", 256)
    if text is not None:
        text = _text(text, "catalog assurance query text")
    if passed is not None and not isinstance(passed, bool):
        raise ValidationError("catalog assurance query passed filter is invalid")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValidationError("catalog assurance query offset is invalid")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 512:
        raise ValidationError("catalog assurance query limit is invalid")
    rows = [finding.to_dict() for finding in value.findings]
    if plane is not None:
        rows = [row for row in rows if row["plane"] == plane]
    if kind is not None:
        rows = [row for row in rows if row["kind"] == kind]
    if severity is not None:
        rows = [row for row in rows if row["severity"] == severity]
    if passed is not None:
        rows = [row for row in rows if row["passed"] is passed]
    if text is not None:
        folded = text.casefold()
        rows = [row for row in rows if folded in canonical_json(row).casefold()]
    body = {
        "query": {
            "plane": plane,
            "kind": kind,
            "severity": severity,
            "passed": passed,
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
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_QUERY_PREFIX,
        )
    }


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not isinstance(value.get("content_address"), str):
        raise ValidationError("catalog assurance query response must be addressed")
    body = {key: item for key, item in value.items() if key != "content_address"}
    if (
        content_hash(
            body,
            prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_QUERY_PREFIX,
        )
        != value["content_address"]
    ):
        raise ValidationError("catalog assurance query address mismatch")
    return dict(value)


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_json(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
        value
    )
    return canonical_json(value) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_csv(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "finding_id",
        "plane",
        "kind",
        "severity",
        "passed",
        "detail",
        "remediation",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in value.get("items", []):
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_markdown(
    value: Mapping[str, Any],
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query(
        value
    )
    lines = [
        "# Durable Review-Store Catalog Assurance Query",
        "",
        f"- rows: `{value.get('total')}`",
        f"- address: `{value.get('content_address')}`",
        "",
        "| # | Plane | Kind | Severity | Passed | Detail |",
        "|---:|---|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | {row.get('plane', '')} | {row.get('kind', '')} | {row.get('severity', '')} | {str(row.get('passed', '')).lower()} | {row.get('detail', '')} |"
        for row in value.get("items", [])
        if isinstance(row, Mapping)
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_BOUNDARY,
        "planes": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssurancePlane
        ],
        "severities": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceSeverity
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogAssuranceState
        ],
        "max_findings": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_MAX_FINDINGS,
        "independent": True,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_VERSION,
        "operations": ["build", "verify", "query", "json", "csv", "markdown"],
        "recomputes_catalog_links": True,
        "supports_optional_hydration": True,
        "distinguishes_held_from_blocked": True,
        "fail_closed_on_blockers": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "filters": ["plane", "kind", "severity", "passed", "text", "offset", "limit"],
        "bounded": True,
        "identity_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_assurance_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_ASSURANCE_QUERY_PREFIX
        + "-v1",
        "resources": ["findings", "summary"],
        "filters": ["plane", "kind", "severity", "passed", "text", "offset", "limit"],
        "bounded": True,
        "addressed_receipts": True,
        "identity_free": True,
    }
