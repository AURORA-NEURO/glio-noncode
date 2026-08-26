"""Configurable acceptance policies for public mission-plan releases.

The release builder proves that a public mission plan is packaged correctly.
This module adds a second, intentionally separate decision layer: consumers
can state operational limits and evaluate a release against those limits
without importing planner internals.  A policy is data, an evaluation is an
addressed receipt, and every failed rule is retained as a stable explanation.

Policy evaluation is fail-closed for malformed input and fail-safe for
unknown optional fields.  It never accepts raw request text, routing
identifiers, producer metadata, model metadata, programming-language
metadata, or identity fields.  It does not authorize execution or imply
clinical suitability; it only evaluates the public release contract.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .mission_plan_release import (
    MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS,
    MissionPlanOfflineRelease,
    MissionPlanReleaseBundle,
    build_mission_plan_release,
    load_mission_plan_release,
)
from .mission_runtime_public import MissionPlanPublicReceipt, build_public_mission_plan
from .serialization import canonical_json, content_hash, jsonable


MISSION_PLAN_RELEASE_POLICY_VERSION = "mission-plan-release-policy-v1"
MISSION_PLAN_RELEASE_POLICY_SCHEMA_VERSION = "mission-plan-release-policy-schema-v1"
MISSION_PLAN_RELEASE_POLICY_CAPABILITIES_VERSION = "mission-plan-release-policy-capabilities-v1"
MISSION_PLAN_RELEASE_POLICY_MAX_KINDS = 32
MISSION_PLAN_RELEASE_POLICY_MAX_ARTIFACTS = 32
MISSION_PLAN_RELEASE_POLICY_MAX_CHECKS = 32

_FORBIDDEN_POLICY_KEYS = frozenset(
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
        "model_version",
        "patient",
        "producer",
        "programming_language",
        "request",
        "raw_request",
        "secret",
        "subject",
        "token",
        "tool_id",
    }
)


def _text(value: Any, field: str, *, maximum: int = 160) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    normalized = str(value).strip()
    if not normalized:
        raise ValidationError(f"{field} must not be empty")
    if len(normalized) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return normalized


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _nonnegative_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or number < 0:
        raise ValidationError(f"{field} must be finite and non-negative")
    return number


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if number <= 0:
        raise ValidationError(f"{field} must be positive")
    return number


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if number < 0:
        raise ValidationError(f"{field} must be non-negative")
    return number


def _string_tuple(value: Any, field: str, *, maximum: int) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the maximum item count")
    normalized = tuple(_text(item, f"{field}[{index}]") for index, item in enumerate(value))
    if len(normalized) != len(set(normalized)):
        raise ValidationError(f"{field} must contain unique values")
    return normalized


def _safe_artifact_name(value: Any, field: str) -> str:
    name = _text(value, field, maximum=180)
    path = Path(name)
    if path.name != name or name in {".", "..", "manifest.json"} or "/" in name or "\\" in name:
        raise ValidationError(f"{field} must be a plain artifact filename")
    return name


def _private_key_paths(value: Any, path: str = "") -> tuple[str, ...]:
    if isinstance(value, Mapping):
        paths: list[str] = []
        for key, child_value in value.items():
            key_text = str(key)
            child_path = f"{path}.{key_text}" if path else key_text
            if key_text.casefold() in _FORBIDDEN_POLICY_KEYS:
                paths.append(child_path)
            paths.extend(_private_key_paths(child_value, child_path))
        return tuple(paths)
    if isinstance(value, (list, tuple)):
        paths: list[str] = []
        for index, child_value in enumerate(value):
            paths.extend(_private_key_paths(child_value, f"{path}[{index}]"))
        return tuple(paths)
    return ()


@dataclass(frozen=True, slots=True)
class MissionPlanReleasePolicy:
    """Bounded, serializable requirements for accepting a release."""

    policy_id: str = "default-public-release"
    required_step_kinds: tuple[str, ...] = ()
    forbidden_step_kinds: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = tuple(sorted(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS))
    require_boundary_accepted: bool = True
    require_release_accepted: bool = True
    require_all_deterministic: bool = False
    fail_on_warnings: bool = False
    max_step_count: int | None = None
    max_optional_steps: int | None = None
    max_dependency_depth: int | None = None
    max_total_cpu: float | None = None
    max_peak_memory_gb: float | None = None
    max_total_storage_gb: float | None = None
    max_seconds: float | None = None
    minimum_check_count: int = 1

    def __post_init__(self) -> None:
        _text(self.policy_id, "policy_id", maximum=96)
        if len(self.required_step_kinds) > MISSION_PLAN_RELEASE_POLICY_MAX_KINDS:
            raise ValidationError("required step kind count exceeds the bound")
        if len(self.forbidden_step_kinds) > MISSION_PLAN_RELEASE_POLICY_MAX_KINDS:
            raise ValidationError("forbidden step kind count exceeds the bound")
        if set(self.required_step_kinds) & set(self.forbidden_step_kinds):
            raise ValidationError("a step kind cannot be required and forbidden")
        if len(self.required_artifacts) > MISSION_PLAN_RELEASE_POLICY_MAX_ARTIFACTS:
            raise ValidationError("required artifact count exceeds the bound")
        if len(self.required_artifacts) != len(set(self.required_artifacts)):
            raise ValidationError("required artifacts must be unique")
        for item in self.required_step_kinds + self.forbidden_step_kinds:
            _text(item, "policy step kind", maximum=96)
        for item in self.required_artifacts:
            _safe_artifact_name(item, "required artifact")
        for field in (
            "require_boundary_accepted",
            "require_release_accepted",
            "require_all_deterministic",
            "fail_on_warnings",
        ):
            _bool(getattr(self, field), f"policy.{field}")
        for field in ("max_step_count", "max_optional_steps", "max_dependency_depth"):
            value = getattr(self, field)
            if value is not None:
                if field == "max_optional_steps":
                    _nonnegative_int(value, f"policy.{field}")
                else:
                    _positive_int(value, f"policy.{field}")
        for field in (
            "max_total_cpu",
            "max_peak_memory_gb",
            "max_total_storage_gb",
            "max_seconds",
        ):
            value = getattr(self, field)
            if value is not None:
                _nonnegative_number(value, f"policy.{field}")
        _nonnegative_int(self.minimum_check_count, "policy.minimum_check_count")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "MissionPlanReleasePolicy":
        """Parse a public policy mapping with strict types and bounds."""

        if not isinstance(value, Mapping):
            raise ValidationError("mission plan release policy must be an object")
        body = dict(value)
        private_paths = _private_key_paths(body)
        if private_paths:
            raise ValidationError("policy contains restricted fields: " + ", ".join(private_paths[:8]))
        allowed = {
            "policy_id",
            "required_step_kinds",
            "forbidden_step_kinds",
            "required_artifacts",
            "require_boundary_accepted",
            "require_release_accepted",
            "require_all_deterministic",
            "fail_on_warnings",
            "max_step_count",
            "max_optional_steps",
            "max_dependency_depth",
            "max_total_cpu",
            "max_peak_memory_gb",
            "max_total_storage_gb",
            "max_seconds",
            "minimum_check_count",
        }
        unknown = sorted(set(body) - allowed)
        if unknown:
            raise ValidationError("policy contains unsupported fields: " + ", ".join(unknown[:8]))
        kwargs: dict[str, Any] = {
            "policy_id": body.get("policy_id", "default-public-release"),
            "required_step_kinds": _string_tuple(
                body.get("required_step_kinds", ()),
                "required_step_kinds",
                maximum=MISSION_PLAN_RELEASE_POLICY_MAX_KINDS,
            ),
            "forbidden_step_kinds": _string_tuple(
                body.get("forbidden_step_kinds", ()),
                "forbidden_step_kinds",
                maximum=MISSION_PLAN_RELEASE_POLICY_MAX_KINDS,
            ),
            "required_artifacts": tuple(
                _safe_artifact_name(item, "required_artifacts item")
                for item in _string_tuple(
                    body.get("required_artifacts", tuple(sorted(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS))),
                    "required_artifacts",
                    maximum=MISSION_PLAN_RELEASE_POLICY_MAX_ARTIFACTS,
                )
            ),
            "require_boundary_accepted": body.get("require_boundary_accepted", True),
            "require_release_accepted": body.get("require_release_accepted", True),
            "require_all_deterministic": body.get("require_all_deterministic", False),
            "fail_on_warnings": body.get("fail_on_warnings", False),
            "max_step_count": body.get("max_step_count"),
            "max_optional_steps": body.get("max_optional_steps"),
            "max_dependency_depth": body.get("max_dependency_depth"),
            "max_total_cpu": body.get("max_total_cpu"),
            "max_peak_memory_gb": body.get("max_peak_memory_gb"),
            "max_total_storage_gb": body.get("max_total_storage_gb"),
            "max_seconds": body.get("max_seconds"),
            "minimum_check_count": body.get("minimum_check_count", 1),
        }
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            {
                "policy_version": MISSION_PLAN_RELEASE_POLICY_VERSION,
                "policy_id": self.policy_id,
                "required_step_kinds": list(self.required_step_kinds),
                "forbidden_step_kinds": list(self.forbidden_step_kinds),
                "required_artifacts": list(self.required_artifacts),
                "require_boundary_accepted": self.require_boundary_accepted,
                "require_release_accepted": self.require_release_accepted,
                "require_all_deterministic": self.require_all_deterministic,
                "fail_on_warnings": self.fail_on_warnings,
                "max_step_count": self.max_step_count,
                "max_optional_steps": self.max_optional_steps,
                "max_dependency_depth": self.max_dependency_depth,
                "max_total_cpu": self.max_total_cpu,
                "max_peak_memory_gb": self.max_peak_memory_gb,
                "max_total_storage_gb": self.max_total_storage_gb,
                "max_seconds": self.max_seconds,
                "minimum_check_count": self.minimum_check_count,
            }
        )


def default_mission_plan_release_policy() -> MissionPlanReleasePolicy:
    """Return the permissive public-contract baseline policy."""

    return MissionPlanReleasePolicy()


@dataclass(frozen=True, slots=True)
class MissionPlanReleasePolicyCheck:
    """One deterministic policy rule result."""

    check_id: str
    category: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        _text(self.check_id, "policy_check.check_id", maximum=128)
        _text(self.category, "policy_check.category", maximum=64)
        _bool(self.passed, "policy_check.passed")
        _text(self.detail, "policy_check.detail", maximum=400)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MissionPlanReleasePolicyEvaluation:
    """Addressed policy evaluation for one public release."""

    policy_version: str
    policy: MissionPlanReleasePolicy
    release_id: str
    plan_id: str
    plan_address: str
    checks: tuple[MissionPlanReleasePolicyCheck, ...]
    accepted: bool
    content_address: str

    def __post_init__(self) -> None:
        if self.policy_version != MISSION_PLAN_RELEASE_POLICY_VERSION:
            raise ValidationError("policy evaluation version is invalid")
        _text(self.release_id, "policy_evaluation.release_id")
        _text(self.plan_id, "policy_evaluation.plan_id")
        _text(self.plan_address, "policy_evaluation.plan_address")
        if len(self.checks) > MISSION_PLAN_RELEASE_POLICY_MAX_CHECKS:
            raise ValidationError("policy check count exceeds the bound")
        ids = [item.check_id for item in self.checks]
        if len(ids) != len(set(ids)):
            raise ValidationError("policy check IDs must be unique")

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_count(self) -> int:
        return len(self.checks) - self.passed_check_count

    def to_dict(self) -> dict[str, Any]:
        body = {
            "policy_version": self.policy_version,
            "policy": self.policy.to_dict(),
            "release_id": self.release_id,
            "plan_id": self.plan_id,
            "plan_address": self.plan_address,
            "check_count": len(self.checks),
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "checks": self.checks,
            "accepted": self.accepted,
        }
        return jsonable(body | {"content_address": self.content_address})


def _as_bundle(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
) -> MissionPlanReleaseBundle:
    if isinstance(value, MissionPlanReleaseBundle):
        return value
    if isinstance(value, MissionPlanOfflineRelease):
        return build_mission_plan_release(value.receipt, release_id=value.release_id)
    if isinstance(value, MissionPlanPublicReceipt):
        return build_mission_plan_release(value)
    if isinstance(value, (str, Path)):
        offline = load_mission_plan_release(value)
        return build_mission_plan_release(offline.receipt, release_id=offline.release_id)
    body = dict(value)
    if "receipt" in body:
        receipt = body["receipt"]
        if not isinstance(receipt, Mapping):
            raise ValidationError("release policy receipt must be an object")
        return build_mission_plan_release(
            MissionPlanPublicReceipt.from_mapping(receipt),
            release_id=None if body.get("release_id") is None else str(body["release_id"]),
        )
    if "steps" in body and "content_address" in body:
        return build_mission_plan_release(MissionPlanPublicReceipt.from_mapping(body))
    return build_mission_plan_release(build_public_mission_plan(body))


def _dependency_depth(receipt: MissionPlanPublicReceipt) -> int:
    depths: dict[str, int] = {}
    for step in receipt.steps:
        if any(item not in depths for item in step.depends_on):
            raise ValidationError(f"release policy cannot order dependencies for step {step.step_id}")
        depths[step.step_id] = 1 + max((depths[item] for item in step.depends_on), default=0)
    return max(depths.values(), default=0)


def _policy_check(
    check_id: str,
    category: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
) -> MissionPlanReleasePolicyCheck:
    body = {
        "check_id": check_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }
    return MissionPlanReleasePolicyCheck(
        **body,
        content_address=content_hash(body, prefix="mission-plan-release-policy-check"),
    )


def evaluate_mission_plan_release_policy(
    value: MissionPlanReleaseBundle | MissionPlanOfflineRelease | MissionPlanPublicReceipt | Mapping[str, Any] | str | Path,
    policy: MissionPlanReleasePolicy | Mapping[str, Any] | None = None,
) -> MissionPlanReleasePolicyEvaluation:
    """Evaluate a release against a bounded public policy."""

    bundle = _as_bundle(value)
    selected_policy = (
        default_mission_plan_release_policy()
        if policy is None
        else policy
        if isinstance(policy, MissionPlanReleasePolicy)
        else MissionPlanReleasePolicy.from_mapping(policy)
    )
    receipt = bundle.receipt
    kinds = tuple(item.kind for item in receipt.steps)
    kind_set = set(kinds)
    optional_count = sum(item.optional for item in receipt.steps)
    dependency_depth = _dependency_depth(receipt)
    artifact_names = tuple(item.filename for item in bundle.artifacts)
    checks = (
        _policy_check(
            "release.accepted",
            "release",
            (not selected_policy.require_release_accepted) or bundle.accepted,
            bundle.accepted,
            True if selected_policy.require_release_accepted else "not_required",
            "The packaged public release must be accepted by its release checks.",
        ),
        _policy_check(
            "public.boundary",
            "boundary",
            (not selected_policy.require_boundary_accepted) or receipt.boundary_accepted,
            receipt.boundary_accepted,
            True if selected_policy.require_boundary_accepted else "not_required",
            "The public receipt must remain inside the published boundary.",
        ),
        _policy_check(
            "workflow.required_kinds",
            "workflow",
            set(selected_policy.required_step_kinds).issubset(kind_set),
            sorted(kind_set),
            list(selected_policy.required_step_kinds),
            "Every required workflow kind must be present.",
        ),
        _policy_check(
            "workflow.forbidden_kinds",
            "workflow",
            not (kind_set & set(selected_policy.forbidden_step_kinds)),
            sorted(kind_set & set(selected_policy.forbidden_step_kinds)),
            list(selected_policy.forbidden_step_kinds),
            "No forbidden workflow kind may be present.",
        ),
        _policy_check(
            "workflow.deterministic",
            "workflow",
            (not selected_policy.require_all_deterministic) or all(item.deterministic for item in receipt.steps),
            all(item.deterministic for item in receipt.steps),
            True if selected_policy.require_all_deterministic else "not_required",
            "All workflow steps must be deterministic when the policy requires it.",
        ),
        _policy_check(
            "workflow.step_count",
            "workflow",
            selected_policy.max_step_count is None or receipt.step_count <= selected_policy.max_step_count,
            receipt.step_count,
            selected_policy.max_step_count if selected_policy.max_step_count is not None else "unbounded",
            "Workflow size must remain within the configured maximum.",
        ),
        _policy_check(
            "workflow.optional_step_count",
            "workflow",
            selected_policy.max_optional_steps is None or optional_count <= selected_policy.max_optional_steps,
            optional_count,
            selected_policy.max_optional_steps if selected_policy.max_optional_steps is not None else "unbounded",
            "Optional workflow steps must remain within the configured maximum.",
        ),
        _policy_check(
            "workflow.dependency_depth",
            "workflow",
            selected_policy.max_dependency_depth is None or dependency_depth <= selected_policy.max_dependency_depth,
            dependency_depth,
            selected_policy.max_dependency_depth if selected_policy.max_dependency_depth is not None else "unbounded",
            "Dependency depth must remain within the configured maximum.",
        ),
        _policy_check(
            "resources.total_cpu",
            "resources",
            selected_policy.max_total_cpu is None or receipt.total_cpu <= selected_policy.max_total_cpu,
            receipt.total_cpu,
            selected_policy.max_total_cpu if selected_policy.max_total_cpu is not None else "unbounded",
            "Total CPU demand must remain within the configured maximum.",
        ),
        _policy_check(
            "resources.peak_memory_gb",
            "resources",
            selected_policy.max_peak_memory_gb is None or receipt.peak_memory_gb <= selected_policy.max_peak_memory_gb,
            receipt.peak_memory_gb,
            selected_policy.max_peak_memory_gb if selected_policy.max_peak_memory_gb is not None else "unbounded",
            "Peak memory demand must remain within the configured maximum.",
        ),
        _policy_check(
            "resources.total_storage_gb",
            "resources",
            selected_policy.max_total_storage_gb is None or receipt.total_storage_gb <= selected_policy.max_total_storage_gb,
            receipt.total_storage_gb,
            selected_policy.max_total_storage_gb if selected_policy.max_total_storage_gb is not None else "unbounded",
            "Total storage demand must remain within the configured maximum.",
        ),
        _policy_check(
            "resources.max_seconds",
            "resources",
            selected_policy.max_seconds is None or receipt.max_seconds <= selected_policy.max_seconds,
            receipt.max_seconds,
            selected_policy.max_seconds if selected_policy.max_seconds is not None else "unbounded",
            "Runtime demand must remain within the configured maximum.",
        ),
        _policy_check(
            "integrity.minimum_checks",
            "integrity",
            len(bundle.checks) >= selected_policy.minimum_check_count,
            len(bundle.checks),
            selected_policy.minimum_check_count,
            "The release must contain the configured minimum number of integrity checks.",
        ),
        _policy_check(
            "integrity.required_artifacts",
            "integrity",
            set(selected_policy.required_artifacts).issubset(set(artifact_names)),
            list(artifact_names),
            list(selected_policy.required_artifacts),
            "Every required artifact must be present in the release.",
        ),
        _policy_check(
            "integrity.warnings",
            "integrity",
            (not selected_policy.fail_on_warnings) or receipt.warning_count == 0,
            receipt.warning_count,
            0 if selected_policy.fail_on_warnings else "allowed",
            "Warnings are rejected only when the policy explicitly requires zero warnings.",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {
        "policy_version": MISSION_PLAN_RELEASE_POLICY_VERSION,
        "policy": selected_policy.to_dict(),
        "release_id": bundle.release_id,
        "plan_id": receipt.plan_id,
        "plan_address": receipt.content_address,
        "checks": checks,
        "accepted": accepted,
    }
    return MissionPlanReleasePolicyEvaluation(
        policy_version=MISSION_PLAN_RELEASE_POLICY_VERSION,
        policy=selected_policy,
        release_id=bundle.release_id,
        plan_id=receipt.plan_id,
        plan_address=receipt.content_address,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="mission-plan-release-policy-evaluation"),
    )


def mission_plan_release_policy_json(value: MissionPlanReleasePolicyEvaluation) -> str:
    """Render an evaluation as canonical JSON."""

    return canonical_json(value.to_dict()) + "\n"


def mission_plan_release_policy_csv(value: MissionPlanReleasePolicyEvaluation) -> str:
    """Render one row per rule for spreadsheets and automation."""

    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
            "check_id",
            "category",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        )
    )
    for item in value.checks:
        writer.writerow(
            (
                item.check_id,
                item.category,
                item.passed,
                canonical_json(item.observed),
                canonical_json(item.expected),
                item.detail,
                item.content_address,
            )
        )
    return output.getvalue()


def mission_plan_release_policy_markdown(value: MissionPlanReleasePolicyEvaluation) -> str:
    """Render a human-readable policy decision table."""

    lines = [
        "# Mission plan release policy evaluation",
        "",
        f"- Policy: `{value.policy.policy_id}`",
        f"- Release: `{value.release_id}`",
        f"- Plan: `{value.plan_id}`",
        f"- Accepted: `{value.accepted}`",
        f"- Passed: `{value.passed_check_count}/{len(value.checks)}`",
        "",
        "| Check | Category | Result | Observed | Expected |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.category}` | `{'pass' if item.passed else 'fail'}` | "
        f"`{canonical_json(item.observed)}` | `{canonical_json(item.expected)}` |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def mission_plan_release_policy_export_payloads(
    value: MissionPlanReleasePolicyEvaluation,
) -> dict[str, str]:
    """Return deterministic policy evaluation projections."""

    return {
        "mission-plan-release-policy.json": mission_plan_release_policy_json(value),
        "mission-plan-release-policy.csv": mission_plan_release_policy_csv(value),
        "mission-plan-release-policy.md": mission_plan_release_policy_markdown(value),
    }


def mission_plan_release_policy_schema() -> dict[str, Any]:
    """Return the versioned policy and evaluation contract."""

    return {
        "version": MISSION_PLAN_RELEASE_POLICY_SCHEMA_VERSION,
        "policy_version": MISSION_PLAN_RELEASE_POLICY_VERSION,
        "policy_fields": [
            "policy_id",
            "required_step_kinds",
            "forbidden_step_kinds",
            "required_artifacts",
            "require_boundary_accepted",
            "require_release_accepted",
            "require_all_deterministic",
            "fail_on_warnings",
            "max_step_count",
            "max_optional_steps",
            "max_dependency_depth",
            "max_total_cpu",
            "max_peak_memory_gb",
            "max_total_storage_gb",
            "max_seconds",
            "minimum_check_count",
        ],
        "check_fields": [
            "check_id",
            "category",
            "passed",
            "observed",
            "expected",
            "detail",
            "content_address",
        ],
        "categories": ["release", "boundary", "workflow", "resources", "integrity"],
        "max_kinds": MISSION_PLAN_RELEASE_POLICY_MAX_KINDS,
        "max_artifacts": MISSION_PLAN_RELEASE_POLICY_MAX_ARTIFACTS,
        "max_checks": MISSION_PLAN_RELEASE_POLICY_MAX_CHECKS,
        "timestamp_free": True,
        "boundary": {
            "routing_metadata": False,
            "producer_metadata": False,
            "model_metadata": False,
            "programming_language_metadata": False,
            "raw_request_payload": False,
        },
    }


def mission_plan_release_policy_capabilities() -> dict[str, Any]:
    """Return the public policy evaluator capability declaration."""

    return {
        "version": MISSION_PLAN_RELEASE_POLICY_CAPABILITIES_VERSION,
        "configurable_limits": True,
        "workflow_kind_gates": True,
        "determinism_gate": True,
        "resource_gates": True,
        "artifact_gates": True,
        "boundary_gate": True,
        "warning_gate": True,
        "addressed_checks": True,
        "timestamp_free": True,
        "json_export": True,
        "markdown_export": True,
        "csv_export": True,
        "read_only": True,
        "execution_authorization": False,
        "clinical_interpretation": False,
    }


__all__ = [
    "MISSION_PLAN_RELEASE_POLICY_CAPABILITIES_VERSION",
    "MISSION_PLAN_RELEASE_POLICY_MAX_ARTIFACTS",
    "MISSION_PLAN_RELEASE_POLICY_MAX_CHECKS",
    "MISSION_PLAN_RELEASE_POLICY_MAX_KINDS",
    "MISSION_PLAN_RELEASE_POLICY_SCHEMA_VERSION",
    "MISSION_PLAN_RELEASE_POLICY_VERSION",
    "MissionPlanReleasePolicy",
    "MissionPlanReleasePolicyCheck",
    "MissionPlanReleasePolicyEvaluation",
    "default_mission_plan_release_policy",
    "evaluate_mission_plan_release_policy",
    "mission_plan_release_policy_capabilities",
    "mission_plan_release_policy_csv",
    "mission_plan_release_policy_export_payloads",
    "mission_plan_release_policy_json",
    "mission_plan_release_policy_markdown",
    "mission_plan_release_policy_schema",
]
