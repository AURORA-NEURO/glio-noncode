"""Policy-gated handoff decisions for public mission-plan release catalogs.

Catalog construction, semantic auditing, and aggregate reporting are useful
inputs but are not themselves a consumer-facing handoff decision.  This
module composes those immutable projections with an explicit threshold policy.
Every rule is retained as an addressed check, including failures, so a caller
can explain why a catalog is accepted or held without reopening planner state.

The gate is intentionally public and descriptive.  It accepts only catalog
rows and their aggregate projections, never executes a workflow, never grants
clinical authorization, and never copies request, routing, attribution,
language, model, producer, identity, or subject metadata.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
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
from .mission_plan_release_catalog_audit import (
    MissionPlanReleaseCatalogAudit,
    build_mission_plan_release_catalog_audit,
)
from .mission_plan_release_catalog_report import (
    MissionPlanReleaseCatalogReport,
    build_mission_plan_release_catalog_report,
)
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_CATALOG_GATE_VERSION = "mission-plan-release-catalog-gate-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION = "mission-plan-release-catalog-gate-policy-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_SCHEMA_VERSION = "mission-plan-release-catalog-gate-schema-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_CAPABILITIES_VERSION = "mission-plan-release-catalog-gate-capabilities-v1"
MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_CHECKS = 32
MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_KINDS = 32
MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_STATES = 16
MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_DECISIONS = 16

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "contact",
        "email",
        "generated_by",
        "identity",
        "language",
        "model",
        "model_id",
        "patient",
        "producer",
        "programming_language",
        "raw_request",
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


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): child for key, child in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if parsed < 0:
        raise ValidationError(f"{field} must be non-negative")
    return parsed


def _positive_int(value: Any, field: str) -> int:
    parsed = _nonnegative_int(value, field)
    if parsed == 0:
        raise ValidationError(f"{field} must be positive")
    return parsed


def _string_tuple(value: Any, field: str, *, maximum: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the maximum item count")
    normalized = tuple(_text(item, f"{field}[{index}]", maximum=96) for index, item in enumerate(value))
    if len(normalized) != len(set(normalized)):
        raise ValidationError(f"{field} must contain unique values")
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
class MissionPlanReleaseCatalogGatePolicy:
    """Explicit bounded thresholds for accepting a public catalog."""

    policy_id: str = "default-mission-plan-release-catalog-gate"
    minimum_entry_count: int = 1
    maximum_entry_count: int = 256
    require_all_accepted: bool = True
    required_states: tuple[str, ...] = ()
    required_decisions: tuple[str, ...] = ()
    required_workflow_kinds: tuple[str, ...] = ()
    maximum_total_step_count: int | None = None
    maximum_total_optional_step_count: int | None = None
    maximum_total_artifact_count: int | None = None
    maximum_total_check_count: int | None = None
    maximum_total_warning_count: int | None = None
    minimum_gate_check_count: int = 1
    require_catalog_audit: bool = True
    require_catalog_report: bool = True

    def __post_init__(self) -> None:
        _text(self.policy_id, "catalog_gate_policy.policy_id", maximum=96)
        if self.minimum_entry_count < 0 or self.maximum_entry_count < 0:
            raise ValidationError("catalog gate entry bounds must be non-negative")
        if self.minimum_entry_count > self.maximum_entry_count:
            raise ValidationError("catalog gate minimum entries exceed maximum entries")
        for field in (
            "minimum_entry_count",
            "maximum_entry_count",
            "minimum_gate_check_count",
        ):
            _nonnegative_int(getattr(self, field), f"catalog_gate_policy.{field}")
        for field in (
            "maximum_total_step_count",
            "maximum_total_optional_step_count",
            "maximum_total_artifact_count",
            "maximum_total_check_count",
            "maximum_total_warning_count",
        ):
            value = getattr(self, field)
            if value is not None:
                _nonnegative_int(value, f"catalog_gate_policy.{field}")
        for field in ("require_all_accepted", "require_catalog_audit", "require_catalog_report"):
            _bool(getattr(self, field), f"catalog_gate_policy.{field}")
        if len(self.required_states) > MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_STATES:
            raise ValidationError("catalog gate required state count exceeds the bound")
        if len(self.required_decisions) > MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_DECISIONS:
            raise ValidationError("catalog gate required decision count exceeds the bound")
        for field in ("required_states", "required_decisions", "required_workflow_kinds"):
            values = getattr(self, field)
            if len(values) > MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_KINDS:
                raise ValidationError(f"catalog gate {field} exceeds the bound")
            if tuple(values) != tuple(sorted(set(values))):
                raise ValidationError(f"catalog gate {field} must be unique and sorted")
            for item in values:
                _text(item, f"catalog_gate_policy.{field}", maximum=96)

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict(), prefix="mission-plan-release-catalog-gate-policy")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGatePolicy":
        body = _mapping(value, "catalog gate policy")
        if _private_paths(body):
            raise ValidationError("catalog gate policy contains restricted metadata")
        allowed = {
            "policy_version",
            "policy_id",
            "minimum_entry_count",
            "maximum_entry_count",
            "require_all_accepted",
            "required_states",
            "required_decisions",
            "required_workflow_kinds",
            "maximum_total_step_count",
            "maximum_total_optional_step_count",
            "maximum_total_artifact_count",
            "maximum_total_check_count",
            "maximum_total_warning_count",
            "minimum_gate_check_count",
            "require_catalog_audit",
            "require_catalog_report",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate policy contains unsupported fields: {sorted(unknown)}")
        if body.get("policy_version", MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION) != MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION:
            raise ValidationError("catalog gate policy version is invalid")
        kwargs: dict[str, Any] = {
            "policy_id": body.get("policy_id", "default-mission-plan-release-catalog-gate"),
            "minimum_entry_count": _nonnegative_int(body.get("minimum_entry_count", 1), "minimum_entry_count"),
            "maximum_entry_count": _nonnegative_int(body.get("maximum_entry_count", 256), "maximum_entry_count"),
            "require_all_accepted": body.get("require_all_accepted", True),
            "required_states": _string_tuple(body.get("required_states", ()), "required_states", maximum=MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_STATES),
            "required_decisions": _string_tuple(body.get("required_decisions", ()), "required_decisions", maximum=MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_DECISIONS),
            "required_workflow_kinds": _string_tuple(body.get("required_workflow_kinds", ()), "required_workflow_kinds", maximum=MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_KINDS),
            "minimum_gate_check_count": _nonnegative_int(body.get("minimum_gate_check_count", 1), "minimum_gate_check_count"),
            "require_catalog_audit": body.get("require_catalog_audit", True),
            "require_catalog_report": body.get("require_catalog_report", True),
        }
        for field in (
            "maximum_total_step_count",
            "maximum_total_optional_step_count",
            "maximum_total_artifact_count",
            "maximum_total_check_count",
            "maximum_total_warning_count",
        ):
            value = body.get(field)
            kwargs[field] = None if value is None else _nonnegative_int(value, field)
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "policy_version": MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION,
                "policy_id": self.policy_id,
                "minimum_entry_count": self.minimum_entry_count,
                "maximum_entry_count": self.maximum_entry_count,
                "require_all_accepted": self.require_all_accepted,
                "required_states": list(self.required_states),
                "required_decisions": list(self.required_decisions),
                "required_workflow_kinds": list(self.required_workflow_kinds),
                "maximum_total_step_count": self.maximum_total_step_count,
                "maximum_total_optional_step_count": self.maximum_total_optional_step_count,
                "maximum_total_artifact_count": self.maximum_total_artifact_count,
                "maximum_total_check_count": self.maximum_total_check_count,
                "maximum_total_warning_count": self.maximum_total_warning_count,
                "minimum_gate_check_count": self.minimum_gate_check_count,
                "require_catalog_audit": self.require_catalog_audit,
                "require_catalog_report": self.require_catalog_report,
            }
        )


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGateCheck:
    """One stable catalog-gate rule result."""

    check_id: str
    category: str
    accepted: bool
    observed: Any
    expected: Any
    message: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "catalog_gate_check.check_id", maximum=128)
        _text(self.category, "catalog_gate_check.category", maximum=64)
        _bool(self.accepted, "catalog_gate_check.accepted")
        _text(self.message, "catalog_gate_check.message", maximum=400)
        _text(self.content_address, "catalog_gate_check.content_address")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGateCheck":
        body = _mapping(value, "catalog gate check")
        allowed = {"check_id", "category", "accepted", "observed", "expected", "message", "content_address"}
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate check contains unsupported fields: {sorted(unknown)}")
        check = cls(
            check_id=_text(body.get("check_id"), "catalog_gate_check.check_id", maximum=128),
            category=_text(body.get("category"), "catalog_gate_check.category", maximum=64),
            accepted=_bool(body.get("accepted"), "catalog_gate_check.accepted"),
            observed=body.get("observed"),
            expected=body.get("expected"),
            message=_text(body.get("message"), "catalog_gate_check.message", maximum=400),
            content_address=_text(body.get("content_address"), "catalog_gate_check.content_address"),
        )
        expected = {key: getattr(check, key) for key in ("check_id", "category", "accepted", "observed", "expected", "message")}
        if check.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate-check"):
            raise ValidationError("catalog gate check content address does not reconcile")
        return check

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleaseCatalogGate:
    """Addressed policy decision over one public release catalog."""

    gate_version: str
    catalog_id: str
    catalog_address: str
    policy: MissionPlanReleaseCatalogGatePolicy
    report_address: str | None
    audit_address: str | None
    checks: tuple[MissionPlanReleaseCatalogGateCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.gate_version != MISSION_PLAN_RELEASE_CATALOG_GATE_VERSION:
            raise ValidationError("catalog gate version is invalid")
        _text(self.catalog_id, "catalog_gate.catalog_id", maximum=96)
        _text(self.catalog_address, "catalog_gate.catalog_address")
        _text(self.content_address, "catalog_gate.content_address")
        if self.report_address is not None:
            _text(self.report_address, "catalog_gate.report_address")
        if self.audit_address is not None:
            _text(self.audit_address, "catalog_gate.audit_address")
        if len(self.checks) > MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_CHECKS:
            raise ValidationError("catalog gate check count exceeds the bound")
        identifiers = tuple(item.check_id for item in self.checks)
        if len(identifiers) != len(set(identifiers)):
            raise ValidationError("catalog gate check IDs must be unique")

    @property
    def passed_check_count(self) -> int:
        return sum(item.accepted for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.accepted)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleaseCatalogGate":
        body = _mapping(value, "mission plan release catalog gate")
        allowed = {
            "gate_version",
            "catalog_id",
            "catalog_address",
            "policy",
            "policy_address",
            "report_address",
            "audit_address",
            "check_count",
            "passed_check_count",
            "failed_check_count",
            "failed_check_ids",
            "checks",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(f"catalog gate contains unsupported fields: {sorted(unknown)}")
        raw_checks = body.get("checks", ())
        if not isinstance(raw_checks, (list, tuple)):
            raise ValidationError("catalog gate checks must be an array")
        checks = tuple(MissionPlanReleaseCatalogGateCheck.from_mapping(item) for item in raw_checks)
        policy_value = body.get("policy")
        if not isinstance(policy_value, Mapping):
            raise ValidationError("catalog gate policy must be an object")
        gate = cls(
            gate_version=_text(body.get("gate_version"), "catalog_gate.gate_version"),
            catalog_id=_text(body.get("catalog_id"), "catalog_gate.catalog_id", maximum=96),
            catalog_address=_text(body.get("catalog_address"), "catalog_gate.catalog_address"),
            policy=MissionPlanReleaseCatalogGatePolicy.from_mapping(policy_value),
            report_address=None if body.get("report_address") is None else _text(body.get("report_address"), "catalog_gate.report_address"),
            audit_address=None if body.get("audit_address") is None else _text(body.get("audit_address"), "catalog_gate.audit_address"),
            checks=checks,
            accepted=_bool(body.get("accepted"), "catalog_gate.accepted"),
            content_address=_text(body.get("content_address"), "catalog_gate.content_address"),
        )
        if body.get("policy_address") != gate.policy.content_address:
            raise ValidationError("catalog gate policy address does not reconcile")
        if body.get("check_count") != len(gate.checks):
            raise ValidationError("catalog gate check count does not reconcile")
        if body.get("passed_check_count") != gate.passed_check_count:
            raise ValidationError("catalog gate passed check count does not reconcile")
        if body.get("failed_check_count") != gate.failed_check_count:
            raise ValidationError("catalog gate failed check count does not reconcile")
        if tuple(body.get("failed_check_ids", ())) != gate.failed_check_ids:
            raise ValidationError("catalog gate failed check IDs do not reconcile")
        expected = _gate_address_body(gate)
        if gate.content_address != content_hash(expected, prefix="mission-plan-release-catalog-gate"):
            raise ValidationError("catalog gate content address does not reconcile")
        if gate.accepted != all(item.accepted for item in gate.checks):
            raise ValidationError("catalog gate acceptance does not reconcile")
        if _private_paths(gate.to_dict()):
            raise ValidationError("catalog gate contains restricted metadata")
        return gate

    def to_dict(self) -> dict[str, Any]:
        body = {
            "gate_version": self.gate_version,
            "catalog_id": self.catalog_id,
            "catalog_address": self.catalog_address,
            "policy": self.policy.to_dict(),
            "policy_address": self.policy.content_address,
            "report_address": self.report_address,
            "audit_address": self.audit_address,
            "check_count": len(self.checks),
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "failed_check_ids": list(self.failed_check_ids),
            "checks": self.checks,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _gate_address_body(gate: MissionPlanReleaseCatalogGate) -> dict[str, Any]:
    return {
        "gate_version": gate.gate_version,
        "catalog_id": gate.catalog_id,
        "catalog_address": gate.catalog_address,
        "policy": gate.policy.to_dict(),
        "policy_address": gate.policy.content_address,
        "report_address": gate.report_address,
        "audit_address": gate.audit_address,
        "checks": gate.checks,
        "accepted": gate.accepted,
    }


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
    body = _mapping(value, "catalog gate source")
    if isinstance(body.get("catalog"), Mapping):
        body = _mapping(body["catalog"], "catalog gate catalog")
    return MissionPlanReleaseCatalog.from_mapping(body)


def _check(
    check_id: str,
    category: str,
    accepted: bool,
    observed: Any,
    expected: Any,
    message: str,
) -> MissionPlanReleaseCatalogGateCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "accepted": bool(accepted),
        "observed": observed,
        "expected": expected,
        "message": message,
    }
    return MissionPlanReleaseCatalogGateCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate-check"),
    )


def _threshold_check(
    check_id: str,
    observed: int,
    threshold: int | None,
    message: str,
) -> MissionPlanReleaseCatalogGateCheck:
    return _check(
        check_id,
        "threshold",
        threshold is None or observed <= threshold,
        observed,
        "unbounded" if threshold is None else threshold,
        message,
    )


def build_mission_plan_release_catalog_gate(
    value: MissionPlanReleaseCatalog | MissionPlanReleaseCatalogBundle | MissionPlanReleaseCatalogOffline | Mapping[str, Any] | str | Path,
    policy: MissionPlanReleaseCatalogGatePolicy | Mapping[str, Any] | None = None,
) -> MissionPlanReleaseCatalogGate:
    """Evaluate a public catalog against explicit, bounded handoff policy."""

    catalog = _as_catalog(value)
    selected_policy = (
        policy
        if isinstance(policy, MissionPlanReleaseCatalogGatePolicy)
        else MissionPlanReleaseCatalogGatePolicy.from_mapping(policy or {})
    )
    report: MissionPlanReleaseCatalogReport | None = None
    audit: MissionPlanReleaseCatalogAudit | None = None
    if selected_policy.require_catalog_report:
        report = build_mission_plan_release_catalog_report(catalog)
    if selected_policy.require_catalog_audit:
        audit = build_mission_plan_release_catalog_audit(catalog)
    checks: list[MissionPlanReleaseCatalogGateCheck] = []
    checks.append(_check(
        "catalog.accepted",
        "acceptance",
        catalog.accepted,
        catalog.accepted,
        True,
        "The source catalog must be accepted before handoff.",
    ))
    if selected_policy.require_catalog_report:
        if report is None:  # pragma: no cover - defensive branch
            raise ValidationError("catalog report was not built")
        checks.extend(
            (
                _check(
                    "catalog.report.accepted",
                    "acceptance",
                    report.accepted,
                    report.accepted,
                    True,
                    "The aggregate catalog report must be accepted.",
                ),
                _check(
                    "catalog.report.address",
                    "address",
                    report.catalog_address == catalog.content_address,
                    report.catalog_address,
                    catalog.content_address,
                    "The report must describe this exact catalog address.",
                ),
                _check(
                    "catalog.report.counts",
                    "reconciliation",
                    report.entry_count == catalog.entry_count
                    and report.accepted_entry_count == catalog.accepted_entry_count
                    and report.rejected_entry_count == catalog.rejected_entry_count,
                    {
                        "entries": report.entry_count,
                        "accepted": report.accepted_entry_count,
                        "rejected": report.rejected_entry_count,
                    },
                    {
                        "entries": catalog.entry_count,
                        "accepted": catalog.accepted_entry_count,
                        "rejected": catalog.rejected_entry_count,
                    },
                    "Report entry counters must reconcile with the catalog.",
                ),
            )
        )
    if selected_policy.require_catalog_audit:
        if audit is None:  # pragma: no cover - defensive branch
            raise ValidationError("catalog audit was not built")
        checks.extend(
            (
                _check(
                    "catalog.audit.accepted",
                    "acceptance",
                    audit.accepted,
                    audit.accepted,
                    True,
                    "The independent catalog semantic audit must be accepted.",
                ),
                _check(
                    "catalog.audit.address",
                    "address",
                    audit.catalog_address == catalog.content_address,
                    audit.catalog_address,
                    catalog.content_address,
                    "The audit must describe this exact catalog address.",
                ),
                _check(
                    "catalog.audit.failed_checks",
                    "reconciliation",
                    audit.failed_check_count == 0,
                    audit.failed_check_count,
                    0,
                    "The semantic audit may not retain failed checks.",
                ),
            )
        )
    checks.extend(
        (
            _check(
                "policy.entry_count.minimum",
                "threshold",
                catalog.entry_count >= selected_policy.minimum_entry_count,
                catalog.entry_count,
                selected_policy.minimum_entry_count,
                "Catalog entry count must meet the minimum threshold.",
            ),
            _threshold_check(
                "policy.entry_count.maximum",
                catalog.entry_count,
                selected_policy.maximum_entry_count,
                "Catalog entry count must not exceed the maximum threshold.",
            ),
        )
    )
    if report is not None:
        checks.append(_check(
            "policy.accepted_entries",
            "acceptance",
            not selected_policy.require_all_accepted or report.accepted_entry_count == report.entry_count,
            report.accepted_entry_count == report.entry_count,
            True,
            "All catalog entries must be accepted when required by policy.",
        ))
        state_counts = report.state_counts
        decision_counts = report.decision_counts
        workflow_counts = report.workflow_counts
        for state in selected_policy.required_states:
            checks.append(_check(
                f"policy.required_state.{state}",
                "coverage",
                state_counts.get(state, 0) > 0,
                state_counts.get(state, 0),
                ">0",
                "Required release state must be represented in the catalog.",
            ))
        for decision in selected_policy.required_decisions:
            checks.append(_check(
                f"policy.required_decision.{decision}",
                "coverage",
                decision_counts.get(decision, 0) > 0,
                decision_counts.get(decision, 0),
                ">0",
                "Required release decision must be represented in the catalog.",
            ))
        for workflow_kind in selected_policy.required_workflow_kinds:
            checks.append(_check(
                f"policy.required_workflow.{workflow_kind}",
                "coverage",
                workflow_counts.get(workflow_kind, 0) > 0,
                workflow_counts.get(workflow_kind, 0),
                ">0",
                "Required workflow kind must be represented in the catalog.",
            ))
        checks.extend(
            (
                _threshold_check("policy.total_steps", report.total_step_count, selected_policy.maximum_total_step_count, "Total steps must remain within policy."),
                _threshold_check("policy.total_optional_steps", report.total_optional_step_count, selected_policy.maximum_total_optional_step_count, "Total optional steps must remain within policy."),
                _threshold_check("policy.total_artifacts", report.total_artifact_count, selected_policy.maximum_total_artifact_count, "Total artifacts must remain within policy."),
                _threshold_check("policy.total_checks", report.total_check_count, selected_policy.maximum_total_check_count, "Total checks must remain within policy."),
                _threshold_check("policy.total_warnings", report.total_warning_count, selected_policy.maximum_total_warning_count, "Total warnings must remain within policy."),
            )
        )
    checks.append(_check(
        "policy.public_boundary",
        "boundary",
        not bool(_private_paths({"catalog": catalog.to_dict(), "report": None if report is None else report.to_dict(), "audit": None if audit is None else audit.to_dict()})),
        (),
        (),
        "Catalog gate projections must remain inside the public boundary.",
    ))
    if len(checks) < selected_policy.minimum_gate_check_count:
        checks.append(_check(
            "policy.minimum_gate_checks",
            "threshold",
            False,
            len(checks),
            selected_policy.minimum_gate_check_count,
            "The gate must expose at least the configured number of checks.",
        ))
    if len(checks) > MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_CHECKS:
        raise ValidationError("catalog gate policy produced too many checks")
    accepted = all(item.accepted for item in checks)
    body = {
        "gate_version": MISSION_PLAN_RELEASE_CATALOG_GATE_VERSION,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "policy": selected_policy.to_dict(),
        "policy_address": selected_policy.content_address,
        "report_address": None if report is None else report.content_address,
        "audit_address": None if audit is None else audit.content_address,
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return MissionPlanReleaseCatalogGate(
        gate_version=body["gate_version"],
        catalog_id=body["catalog_id"],
        catalog_address=body["catalog_address"],
        policy=selected_policy,
        report_address=body["report_address"],
        audit_address=body["audit_address"],
        checks=body["checks"],
        accepted=body["accepted"],
        content_address=content_hash(body, prefix="mission-plan-release-catalog-gate"),
    )


def mission_plan_release_catalog_gate_json(
    gate: MissionPlanReleaseCatalogGate | Mapping[str, Any],
) -> str:
    """Return canonical JSON for a catalog-gate decision."""

    value = gate if isinstance(gate, MissionPlanReleaseCatalogGate) else MissionPlanReleaseCatalogGate.from_mapping(gate)
    return canonical_json(value.to_dict())


def mission_plan_release_catalog_gate_csv(
    gate: MissionPlanReleaseCatalogGate | Mapping[str, Any],
) -> str:
    """Return stable check-level CSV for a catalog-gate decision."""

    value = gate if isinstance(gate, MissionPlanReleaseCatalogGate) else MissionPlanReleaseCatalogGate.from_mapping(gate)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("check_id", "category", "accepted", "observed", "expected", "message", "content_address"))
    for item in value.checks:
        writer.writerow((item.check_id, item.category, str(item.accepted).lower(), canonical_json(item.observed), canonical_json(item.expected), item.message, item.content_address))
    return output.getvalue()


def mission_plan_release_catalog_gate_markdown(
    gate: MissionPlanReleaseCatalogGate | Mapping[str, Any],
) -> str:
    """Return a deterministic review report retaining every gate failure."""

    value = gate if isinstance(gate, MissionPlanReleaseCatalogGate) else MissionPlanReleaseCatalogGate.from_mapping(gate)
    lines = [
        "# Mission plan release catalog gate",
        "",
        f"- Catalog: `{value.catalog_id}`",
        f"- Catalog address: `{value.catalog_address}`",
        f"- Policy: `{value.policy.policy_id}`",
        f"- Policy address: `{value.policy.content_address}`",
        f"- Report address: `{value.report_address or 'not-required'}`",
        f"- Audit address: `{value.audit_address or 'not-required'}`",
        f"- Checks: {len(value.checks)}",
        f"- Passed: {value.passed_check_count}",
        f"- Failed: {value.failed_check_count}",
        f"- Accepted: {str(value.accepted).lower()}",
        "",
        "## Checks",
        "",
        "| Check | Category | Accepted | Observed | Expected | Message |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {item.check_id} | {item.category} | {str(item.accepted).lower()} | {canonical_json(item.observed)} | {canonical_json(item.expected)} | {item.message} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_catalog_gate_export_payloads(
    gate: MissionPlanReleaseCatalogGate | Mapping[str, Any],
) -> dict[str, str]:
    """Return every deterministic gate projection."""

    value = gate if isinstance(gate, MissionPlanReleaseCatalogGate) else MissionPlanReleaseCatalogGate.from_mapping(gate)
    return {
        "mission-plan-release-catalog-gate.json": mission_plan_release_catalog_gate_json(value),
        "mission-plan-release-catalog-gate.csv": mission_plan_release_catalog_gate_csv(value),
        "mission-plan-release-catalog-gate.md": mission_plan_release_catalog_gate_markdown(value),
    }


def mission_plan_release_catalog_gate_schema() -> dict[str, Any]:
    """Describe the public catalog-gate contract."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_SCHEMA_VERSION,
        "gate_version": MISSION_PLAN_RELEASE_CATALOG_GATE_VERSION,
        "policy_version": MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION,
        "max_checks": MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_CHECKS,
        "check_fields": ["check_id", "category", "accepted", "observed", "expected", "message", "content_address"],
        "policy_fields": [
            "policy_id",
            "minimum_entry_count",
            "maximum_entry_count",
            "require_all_accepted",
            "required_states",
            "required_decisions",
            "required_workflow_kinds",
            "maximum_total_step_count",
            "maximum_total_optional_step_count",
            "maximum_total_artifact_count",
            "maximum_total_check_count",
            "maximum_total_warning_count",
            "minimum_gate_check_count",
            "require_catalog_audit",
            "require_catalog_report",
        ],
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "identity_metadata": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
        },
    }


def mission_plan_release_catalog_gate_capabilities() -> dict[str, Any]:
    """Describe supported gate operations and non-capabilities."""

    return {
        "version": MISSION_PLAN_RELEASE_CATALOG_GATE_CAPABILITIES_VERSION,
        "threshold_policy": True,
        "acceptance_requirement": True,
        "state_coverage": True,
        "decision_coverage": True,
        "workflow_coverage": True,
        "aggregate_resource_limits": True,
        "audit_composition": True,
        "report_composition": True,
        "address_reconstruction": True,
        "failure_visibility": True,
        "strict_mapping_hydration": True,
        "verified_offline_input": True,
        "read_only": True,
        "timestamp_free": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "handler_execution": False,
        "clinical_authorization": False,
        "boundary": {
            "raw_request_payload": False,
            "routing_metadata": False,
            "attribution": False,
            "language_metadata": False,
            "model_metadata": False,
            "producer_metadata": False,
            "identity_metadata": False,
        },
    }


__all__ = [
    "MISSION_PLAN_RELEASE_CATALOG_GATE_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_MAX_CHECKS",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_POLICY_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_CATALOG_GATE_VERSION",
    "MissionPlanReleaseCatalogGate",
    "MissionPlanReleaseCatalogGateCheck",
    "MissionPlanReleaseCatalogGatePolicy",
    "build_mission_plan_release_catalog_gate",
    "mission_plan_release_catalog_gate_capabilities",
    "mission_plan_release_catalog_gate_csv",
    "mission_plan_release_catalog_gate_export_payloads",
    "mission_plan_release_catalog_gate_json",
    "mission_plan_release_catalog_gate_markdown",
    "mission_plan_release_catalog_gate_schema",
]
