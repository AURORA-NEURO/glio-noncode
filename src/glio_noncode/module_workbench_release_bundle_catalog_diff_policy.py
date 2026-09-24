"""Evaluate strict and release policy over a catalog comparison."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff import (
    verify_module_workbench_release_bundle_catalog_diff_value,
)
from .module_workbench_release_bundle_catalog_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiff,
)
from .module_workbench_release_bundle_catalog_diff_policy_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicy,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
    address_module_workbench_release_bundle_catalog_diff_policy,
    address_module_workbench_release_bundle_catalog_diff_policy_check,
    address_module_workbench_release_bundle_catalog_diff_policy_gate,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value


def build_module_workbench_release_bundle_catalog_diff_policy(
    *,
    policy_id: str = "module-workbench-release-bundle-catalog-diff-strict",
    maximum_added_count: int = 0,
    maximum_changed_count: int = 0,
    maximum_removed_count: int = 0,
    allowed_directions: tuple[str, ...] = ("improved", "unchanged"),
    allowed_state_transitions: tuple[str, ...] = (
        "blocked_to_accepted",
        "unchanged",
    ),
    require_accepted_catalogs: bool = True,
    allow_unchanged: bool = True,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicy:
    body = {
        "policy_id": policy_id,
        "maximum_added_count": maximum_added_count,
        "maximum_changed_count": maximum_changed_count,
        "maximum_removed_count": maximum_removed_count,
        "allowed_directions": tuple(sorted(allowed_directions)),
        "allowed_state_transitions": tuple(sorted(allowed_state_transitions)),
        "require_accepted_catalogs": require_accepted_catalogs,
        "allow_unchanged": allow_unchanged,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicy(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicy(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy(provisional),
    )


def default_module_workbench_release_bundle_catalog_diff_policy() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicy
):
    """Return strict no-change admission with explicit recovery transitions."""

    return build_module_workbench_release_bundle_catalog_diff_policy()


def release_module_workbench_release_bundle_catalog_diff_policy() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicy
):
    """Return a release policy allowing one removal and recovery to accepted."""

    return build_module_workbench_release_bundle_catalog_diff_policy(
        policy_id="module-workbench-release-bundle-catalog-diff-release",
        maximum_added_count=0,
        maximum_changed_count=0,
        maximum_removed_count=1,
        allowed_directions=("changed", "improved", "unchanged"),
        allowed_state_transitions=("blocked_to_accepted", "unchanged"),
        require_accepted_catalogs=False,
        allow_unchanged=True,
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_check(
            provisional
        ),
    )


def evaluate_module_workbench_release_bundle_catalog_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiff,
    policy: ModuleWorkbenchReleaseBundleCatalogDiffPolicy | None = None,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    """Evaluate catalog changes while preserving blocked decisions as evidence."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiff):
        raise ValidationError("catalog-diff policy requires a typed comparison")
    verify_module_workbench_release_bundle_catalog_diff_value(value)
    selected = policy or default_module_workbench_release_bundle_catalog_diff_policy()
    if not isinstance(selected, ModuleWorkbenchReleaseBundleCatalogDiffPolicy):
        raise ValidationError("catalog-diff policy must be typed")
    checks = (
        _check(
            "accepted-catalogs",
            not selected.require_accepted_catalogs
            or (
                value.previous_catalog_state == "accepted"
                and value.current_catalog_state == "accepted"
            ),
            (value.previous_catalog_state, value.current_catalog_state),
            "accepted/accepted" if selected.require_accepted_catalogs else "not-required",
            "both compared catalogs are accepted when required",
        ),
        _check(
            "added-count",
            value.added_count <= selected.maximum_added_count,
            value.added_count,
            f"<={selected.maximum_added_count}",
            "candidate-only bundles remain within the addition budget",
        ),
        _check(
            "changed-count",
            value.changed_count <= selected.maximum_changed_count,
            value.changed_count,
            f"<={selected.maximum_changed_count}",
            "changed bundle references remain within the change budget",
        ),
        _check(
            "classification-conservation",
            value.added_count + value.changed_count + value.removed_count + value.unchanged_count
            == len(value.changes),
            len(value.changes),
            value.added_count + value.changed_count + value.removed_count + value.unchanged_count,
            "classification counts conserve every compared bundle identity",
        ),
        _check(
            "direction",
            value.direction.value in selected.allowed_directions,
            value.direction.value,
            selected.allowed_directions,
            "aggregate direction is admitted by the policy",
        ),
        _check(
            "removed-count",
            value.removed_count <= selected.maximum_removed_count,
            value.removed_count,
            f"<={selected.maximum_removed_count}",
            "baseline-only bundles remain within the removal budget",
        ),
        _check(
            "state-transition",
            value.state_transition.value in selected.allowed_state_transitions,
            value.state_transition.value,
            selected.allowed_state_transitions,
            "aggregate catalog transition is admitted by the policy",
        ),
        _check(
            "unchanged-control",
            selected.allow_unchanged or value.unchanged_count == 0,
            value.unchanged_count,
            "allowed" if selected.allow_unchanged else 0,
            "unchanged bundle references follow the policy control",
        ),
        _check(
            "public-boundary",
            not _has_forbidden_key(value.to_dict()) and not _has_forbidden_key(selected.to_dict()),
            "clean"
            if not _has_forbidden_key(value.to_dict())
            and not _has_forbidden_key(selected.to_dict())
            else "forbidden-key",
            "clean",
            "policy and comparison contain only public aggregate fields",
        ),
    )
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "diff_address": value.content_address,
        "policy": selected,
        "checks": ordered,
        "accepted": all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_gate(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicy,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicy:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicy):
        raise ValidationError("catalog-diff policy verification requires a typed policy")
    if address_module_workbench_release_bundle_catalog_diff_policy(value) != value.content_address:
        raise ValidationError("catalog-diff policy address mismatch")
    return value


def verify_module_workbench_release_bundle_catalog_diff_policy_gate(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate):
        raise ValidationError("catalog-diff gate verification requires a typed gate")
    verify_module_workbench_release_bundle_catalog_diff_policy(value.policy)
    for check in value.checks:
        if (
            address_module_workbench_release_bundle_catalog_diff_policy_check(check)
            != check.content_address
        ):
            raise ValidationError(f"catalog-diff policy check address mismatch: {check.check_id}")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_gate(value)
        != value.content_address
    ):
        raise ValidationError("catalog-diff policy gate address mismatch")
    return value


def _policy_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicy:
    return verify_module_workbench_release_bundle_catalog_diff_policy(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicy(
            policy_id=str(value.get("policy_id", "")),
            maximum_added_count=value.get("maximum_added_count"),
            maximum_changed_count=value.get("maximum_changed_count"),
            maximum_removed_count=value.get("maximum_removed_count"),
            allowed_directions=tuple(value.get("allowed_directions", ())),
            allowed_state_transitions=tuple(value.get("allowed_state_transitions", ())),
            require_accepted_catalogs=value.get("require_accepted_catalogs"),
            allow_unchanged=value.get("allow_unchanged"),
            content_address=str(value.get("content_address", "")),
        )
    )


def _gate_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    raw_policy = value.get("policy")
    raw_checks = value.get("checks")
    if not isinstance(raw_policy, Mapping) or not isinstance(raw_checks, list):
        raise ValidationError("catalog-diff policy gate payload is invalid")
    checks = tuple(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicyCheck(
            check_id=str(item.get("check_id", "")),
            passed=item.get("passed"),
            observed=item.get("observed"),
            required=item.get("required"),
            detail=str(item.get("detail", "")),
            content_address=str(item.get("content_address", "")),
        )
        for item in raw_checks
        if isinstance(item, Mapping)
    )
    return verify_module_workbench_release_bundle_catalog_diff_policy_gate(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate(
            diff_address=str(value.get("diff_address", "")),
            policy=_policy_from_mapping(raw_policy),
            checks=checks,
            accepted=value.get("accepted"),
            content_address=str(value.get("content_address", "")),
        )
    )


def load_module_workbench_release_bundle_catalog_diff_policy_gate(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    if isinstance(value, Mapping):
        return _gate_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="catalog-diff policy gate", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse catalog-diff policy gate: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("catalog-diff policy gate must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("catalog-diff policy gate is not canonical JSON")
    return _gate_from_mapping(parsed)


def query_module_workbench_release_bundle_catalog_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate
    | bytes
    | bytearray
    | str
    | Path
    | Mapping[str, Any],
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_MAX_LIMIT
    ):
        raise ValidationError("catalog-diff policy paging is invalid")
    gate = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate)
        else load_module_workbench_release_bundle_catalog_diff_policy_gate(value)
    )
    verify_module_workbench_release_bundle_catalog_diff_policy_gate(gate)
    rows = [item.to_dict() for item in gate.checks]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "gate_address": gate.content_address,
        "diff_address": gate.diff_address,
        "policy_address": gate.policy_address,
        "passed": passed,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": gate.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix="module-workbench-release-bundle-catalog-diff-policy-query",
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_gate(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate:
    verify_module_workbench_release_bundle_catalog_diff_policy_gate(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("catalog-diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("catalog-diff policy destination is not a file")
    _validate_parent(path.parent, "catalog-diff policy destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_json(value).encode(_UTF8),
        field="catalog-diff policy destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy(
        value, passed=passed, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicyGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_gate(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy",
        "",
        f"- Gate: `{value.content_address}`",
        f"- Diff: `{value.diff_address}`",
        f"- Policy: `{value.policy.policy_id}`",
        f"- Passed / failed: **{value.passed_count} / {value.failed_count}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        "",
        "| Check | Passed | Observed | Required | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | {str(item.passed).lower()} | `{item.observed}` "
        f"| `{item.required}` | {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_BOUNDARY,
        "resources": ["checks", "summary"],
        "thresholds": [
            "maximum_added_count",
            "maximum_changed_count",
            "maximum_removed_count",
            "allowed_directions",
            "allowed_state_transitions",
            "require_accepted_catalogs",
            "allow_unchanged",
        ],
        "depends_on": "public_aggregate_module_workbench_release_bundle_catalog_diff",
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_policy",
        "evaluate_added_budget",
        "evaluate_changed_budget",
        "evaluate_removed_budget",
        "evaluate_direction",
        "evaluate_state_transition",
        "evaluate_accepted_catalogs",
        "evaluate_unchanged_control",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy",
    "default_module_workbench_release_bundle_catalog_diff_policy",
    "evaluate_module_workbench_release_bundle_catalog_diff_policy",
    "load_module_workbench_release_bundle_catalog_diff_policy_gate",
    "module_workbench_release_bundle_catalog_diff_policy_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_csv",
    "module_workbench_release_bundle_catalog_diff_policy_json",
    "module_workbench_release_bundle_catalog_diff_policy_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy",
    "release_module_workbench_release_bundle_catalog_diff_policy",
    "render_module_workbench_release_bundle_catalog_diff_policy_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy",
    "verify_module_workbench_release_bundle_catalog_diff_policy_gate",
    "write_module_workbench_release_bundle_catalog_diff_policy",
]
