"""Independent self-audit for public mission-plan release catalogs.

Catalog filesystem verification proves that bytes on disk match a manifest.
This module performs the complementary semantic audit on a hydrated catalog:
entry addresses, aggregate counts, canonical ordering, identity uniqueness,
acceptance totals, and the public boundary are reconciled independently of the
catalog builder.

The audit is intentionally descriptive.  It does not dereference private
sources or reopen release planners, and its projections contain no request,
routing, attribution, language, model, producer, or identity metadata.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release_catalog import (
    MissionPlanReleaseCatalog,
    MissionPlanReleaseCatalogBundle,
    MissionPlanReleaseCatalogOffline,
    load_mission_plan_release_catalog,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION = "mission-plan-release-catalog-audit-v1"
MISSION_PLAN_RELEASE_CATALOG_AUDIT_SCHEMA_VERSION = "mission-plan-release-catalog-audit-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_AUDIT_CAPABILITIES_VERSION = "mission-plan-release-catalog-audit-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_AUDIT_MAX_CHECKS = 24

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "assistant",
        "author",
        "contact",
        "email",
        "identity",
        "language",
        "model",
        "patient",
        "producer",
        "programming_language",
        "request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 180) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _private_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_KEYS:
                paths.append(child_path)
            paths.extend(_private_paths(child, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child in enumerate(value):
            paths.extend(_private_paths(child, f"{path}[{index}]"))
        return tuple(paths)
    return ()


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogAuditCheck:
    """One independent catalog semantic check."""

    check_id: str
    category: str
    accepted: bool
    observed: Any
    expected: Any
    message: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "catalog_audit_check.check_id", maximum=128)
        _text(self.category, "catalog_audit_check.category", maximum=64)
        _text(self.message, "catalog_audit_check.message", maximum=400)
        _text(self.content_address, "catalog_audit_check.content_address")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogAuditCheck":
        if not isinstance(value, Mapping):
            raise ValidationError("catalog audit check must be an object")
        body = {str(key): child for key, child in value.items()}
        allowed = {"check_id", "category", "accepted", "observed", "expected", "message", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog audit check contains unsupported fields: {sorted(unknown)}")
        check = cls(
            check_id=_text(body.get("check_id"), "catalog_audit_check.check_id", maximum=128),
            category=_text(body.get("category"), "catalog_audit_check.category", maximum=64),
            accepted=bool(body.get("accepted")),
            observed=body.get("observed"),
            expected=body.get("expected"),
            message=_text(body.get("message"), "catalog_audit_check.message", maximum=400),
            content_address=_text(body.get("content_address"), "catalog_audit_check.content_address"),
        )
        expected_address = content_hash(
            {
                "check_id": check.check_id,
                "category": check.category,
                "accepted": check.accepted,
                "observed": check.observed,
                "expected": check.expected,
                "message": check.message,
            },
            prefix="mission-plan-release-catalog-audit-check",
        )
        if check.content_address != expected_address:
            raise ValidationError("catalog audit check content address does not reconcile")
        return check


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogAudit:
    """Addressed semantic audit report for one public catalog."""

    audit_version: str
    catalog_id: str
    catalog_address: str
    checks: tuple[MissionPlanReleaseCatalogAuditCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.audit_version != MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION:
            raise ValidationError("catalog audit version is invalid")
        _text(self.catalog_id, "catalog_audit.catalog_id", maximum=96)
        _text(self.catalog_address, "catalog_audit.catalog_address")
        _text(self.content_address, "catalog_audit.content_address")
        if len(self.checks) > MISSION_PLAN_RELEASE_CATALOG_AUDIT_MAX_CHECKS:
            raise ValidationError("catalog audit check count exceeds the bound")
        identifiers = tuple(item.check_id for item in self.checks)
        if len(identifiers) != len(set(identifiers)):
            raise ValidationError("catalog audit check IDs must be unique")

    @property
    def passed_check_count(self) -> int:
        return sum(item.accepted for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogAudit":
        if not isinstance(value, Mapping):
            raise ValidationError("catalog audit must be an object")
        body = {str(key): child for key, child in value.items()}
        allowed = {
            "audit_version",
            "catalog_id",
            "catalog_address",
            "check_count",
            "passed_check_count",
            "failed_check_count",
            "checks",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog audit contains unsupported fields: {sorted(unknown)}")
        raw_checks = body.get("checks", ())
        if not isinstance(raw_checks, (list, tuple)):
            raise ValidationError("catalog audit checks must be an array")
        audit = cls(
            audit_version=_text(body.get("audit_version"), "catalog_audit.audit_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_audit.catalog_id", maximum=96),
            catalog_address=_text(body.get("catalog_address"), "catalog_audit.catalog_address"),
            checks=tuple(MissionPlanReleaseCatalogAuditCheck.from_mapping(item) for item in raw_checks),
            accepted=bool(body.get("accepted")),
            content_address=_text(body.get("content_address"), "catalog_audit.content_address"),
        )
        if body.get("check_count") != len(audit.checks):
            raise ValidationError("catalog audit check count does not reconcile")
        if body.get("passed_check_count") != audit.passed_check_count:
            raise ValidationError("catalog audit passed check count does not reconcile")
        if body.get("failed_check_count") != audit.failed_check_count:
            raise ValidationError("catalog audit failed check count does not reconcile")
        expected_address = content_hash(
            {
                "audit_version": audit.audit_version,
                "catalog_id": audit.catalog_id,
                "catalog_address": audit.catalog_address,
                "checks": audit.checks,
                "accepted": audit.accepted,
            },
            prefix="mission-plan-release-catalog-audit",
        )
        if audit.content_address != expected_address:
            raise ValidationError("catalog audit content address does not reconcile")
        if audit.accepted != all(item.accepted for item in audit.checks):
            raise ValidationError("catalog audit acceptance does not reconcile")
        if _private_paths(audit.to_dict()):
            raise ValidationError("catalog audit contains restricted metadata")
        return audit

    def to_dict(self) -> dict[str, Any]:
        body = {
            "audit_version": self.audit_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "check_count": len(self.checks),
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "checks": self.checks,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _as_catalog(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalog:
    if isinstance(value, MissionPlanReleaseCatalog):
        return value
    if isinstance(value, MissionPlanReleaseCatalogBundle):
        return value.catalog
    if isinstance(value, MissionPlanReleaseCatalogOffline):
        return value.catalog
    if isinstance(value, (str, Path)):
        return load_mission_plan_release_catalog(value).catalog
    body = dict(value)
    if "catalog" in body and isinstance(body["catalog"], Mapping):
        body = dict(body["catalog"])
    return MissionPlanReleaseCatalog.from_mapping(body)


def _check(
    check_id: str,
    category: str,
    accepted: bool,
    observed: Any,
    expected: Any,
    message: str,
) -> MissionPlanReleaseCatalogAuditCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "accepted": bool(accepted),
        "observed": observed,
        "expected": expected,
        "message": message,
    }
    return MissionPlanReleaseCatalogAuditCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-audit-check"),
    )


def build_mission_plan_release_catalog_audit(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseCatalogAudit:
    """Run independent semantic checks over a public catalog."""

    catalog = _as_catalog(value)
    entry_dicts = [item.to_dict() for item in catalog.entries]
    expected_catalog_address = content_hash(
        {
            "catalog_version": catalog.catalog_version,
            "catalog_id": catalog.catalog_id,
            "entries": catalog.entries,
            "accepted": catalog.accepted,
        },
        prefix="mission-plan-release-catalog",
    )
    release_ids = tuple(item.release_id for item in catalog.entries)
    plan_addresses = tuple(item.plan_address for item in catalog.entries)
    expected_order = tuple(sorted((item.release_id, item.plan_address) for item in catalog.entries))
    actual_order = tuple((item.release_id, item.plan_address) for item in catalog.entries)
    entry_addresses_valid = True
    invalid_entry_addresses: list[str] = []
    for item in catalog.entries:
        body = {
            "release_id": item.release_id,
            "release_address": item.release_address,
            "plan_id": item.plan_id,
            "plan_address": item.plan_address,
            "state": item.state,
            "decision": item.decision,
            "accepted": item.accepted,
            "step_count": item.step_count,
            "optional_step_count": item.optional_step_count,
            "deterministic_step_count": item.deterministic_step_count,
            "network_step_count": item.network_step_count,
            "artifact_count": item.artifact_count,
            "check_count": item.check_count,
            "warning_count": item.warning_count,
            "workflow_kinds": item.workflow_kinds,
        }
        expected_entry_address = content_hash(body, prefix="mission-plan-release-catalog-entry")
        if item.content_address != expected_entry_address:
            entry_addresses_valid = False
            invalid_entry_addresses.append(item.release_id)
    checks = (
        _check(
            "catalog.address",
            "address",
            catalog.content_address == expected_catalog_address,
            catalog.content_address,
            expected_catalog_address,
            "The catalog address must reconstruct from its published entries.",
        ),
        _check(
            "catalog.entry_addresses",
            "address",
            entry_addresses_valid,
            invalid_entry_addresses,
            "all entry addresses reconcile",
            "Every catalog entry address must reconstruct independently.",
        ),
        _check(
            "catalog.release_id_uniqueness",
            "identity",
            len(release_ids) == len(set(release_ids)),
            list(release_ids),
            "unique release IDs",
            "Release IDs must not collide inside a catalog.",
        ),
        _check(
            "catalog.plan_address_uniqueness",
            "identity",
            len(plan_addresses) == len(set(plan_addresses)),
            list(plan_addresses),
            "unique plan addresses",
            "Public plan addresses must not collide inside a catalog.",
        ),
        _check(
            "catalog.canonical_order",
            "ordering",
            actual_order == expected_order,
            list(actual_order),
            list(expected_order),
            "Catalog entries must be ordered by release ID then plan address.",
        ),
        _check(
            "catalog.entry_count",
            "counts",
            len(catalog.entries) <= 256,
            len(catalog.entries),
            "0..256",
            "Catalog entry count must remain bounded.",
        ),
        _check(
            "catalog.acceptance_counts",
            "counts",
            catalog.accepted_entry_count + catalog.rejected_entry_count == catalog.entry_count,
            {
                "accepted": catalog.accepted_entry_count,
                "rejected": catalog.rejected_entry_count,
                "total": catalog.entry_count,
            },
            "accepted + rejected = total",
            "Accepted and rejected entry counts must conserve the total.",
        ),
        _check(
            "catalog.acceptance_state",
            "acceptance",
            catalog.accepted == all(item.accepted for item in catalog.entries),
            catalog.accepted,
            all(item.accepted for item in catalog.entries),
            "Catalog acceptance must equal the entry acceptance fold.",
        ),
        _check(
            "catalog.entry_shape",
            "boundary",
            not any(_private_paths(item) for item in entry_dicts),
            [path for item in entry_dicts for path in _private_paths(item)],
            "no restricted metadata paths",
            "Catalog entries must remain inside the public boundary.",
        ),
        _check(
            "catalog.nonnegative_counts",
            "counts",
            all(
                getattr(item, field) >= 0
                for item in catalog.entries
                for field in (
                    "step_count",
                    "optional_step_count",
                    "deterministic_step_count",
                    "network_step_count",
                    "artifact_count",
                    "check_count",
                    "warning_count",
                )
            ),
            [item.release_id for item in catalog.entries if any(getattr(item, field) < 0 for field in ("step_count", "optional_step_count", "deterministic_step_count", "network_step_count", "artifact_count", "check_count", "warning_count"))],
            "all counts >= 0",
            "Catalog aggregate counters must be non-negative.",
        ),
    )
    accepted = all(item.accepted for item in checks)
    body = {
        "audit_version": MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogAudit(
        audit_version=MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION,
        catalog_id=catalog.catalog_id,
        catalog_address=catalog.content_address,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-audit"),
    )


def mission_plan_release_catalog_audit_json(value: MissionPlanReleaseCatalogAudit) -> str:
    """Render catalog audit as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_catalog_audit_csv(value: MissionPlanReleaseCatalogAudit) -> str:
    """Render one deterministic row per audit check."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("check_id", "category", "accepted", "observed", "expected", "message", "content_address"))
    for item in value.checks:
        writer.writerow(
            (
                item.check_id,
                item.category,
                item.accepted,
                canonical_json(item.observed),
                canonical_json(item.expected),
                item.message,
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_release_catalog_audit_markdown(value: MissionPlanReleaseCatalogAudit) -> str:
    """Render catalog audit as a review table."""

    lines = [
        "# Mission plan release catalog audit",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Accepted: `{value.accepted}`",
        f"- Checks: `{value.passed_check_count}/{len(value.checks)}`",
        "",
        "| Check | Category | Result | Message |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.category}` | `{'pass' if item.accepted else 'fail'}` | {item.message} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_audit_export_payloads(
    value: MissionPlanReleaseCatalogAudit,
) -> dict[str, str]:
    """Return deterministic catalog-audit projections."""

    return {
        "mission-plan-release-catalog-audit.json": mission_plan_release_catalog_audit_json(value),
        "mission-plan-release-catalog-audit.csv": mission_plan_release_catalog_audit_csv(value),
        "mission-plan-release-catalog-audit.md": mission_plan_release_catalog_audit_markdown(value),
    }


def mission_plan_release_catalog_audit_schema() -> dict[str, Any]:
    """Return the catalog audit contract."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_AUDIT_SCHEMA_VERSION,
        "audit_version": MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION,
        "check_fields": ["check_id", "category", "accepted", "observed", "expected", "message", "content_address"],
        "categories": ["address", "identity", "ordering", "counts", "acceptance", "boundary"],
        "max_checks": MISSION_PLAN_RELEASE_CATALOG_AUDIT_MAX_CHECKS,
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_catalog_audit_capabilities() -> dict[str, Any]:
    """Return catalog-audit capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_AUDIT_CAPABILITIES_VERSION,
        "catalog_address_reconstruction": True,
        "entry_address_reconstruction": True,
        "identity_collision_audit": True,
        "ordering_audit": True,
        "count_conservation": True,
        "acceptance_fold_audit": True,
        "public_boundary_audit": True,
        "verified_offline_input": True,
        "addressed_checks": True,
        "timestamp_free": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_AUDIT_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_AUDIT_MAX_CHECKS",
    "MISSION_PLAN_RELEASE_CATALOG_AUDIT_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_AUDIT_VERSION",
    "MissionPlanReleaseCatalogAudit",
    "MissionPlanReleaseCatalogAuditCheck",
    "build_mission_plan_release_catalog_audit",
    "mission_plan_release_catalog_audit_capabilities",
    "mission_plan_release_catalog_audit_csv",
    "mission_plan_release_catalog_audit_export_payloads",
    "mission_plan_release_catalog_audit_json",
    "mission_plan_release_catalog_audit_markdown",
    "mission_plan_release_catalog_audit_schema",
]
