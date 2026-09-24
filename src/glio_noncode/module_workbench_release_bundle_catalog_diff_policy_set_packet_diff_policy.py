"""Evaluate release policy over portable policy-set packet diffs."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff import (
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyCheck,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    *,
    policy_id: str = ("module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-strict"),
    maximum_changed_count: int = 16,
    allowed_directions: tuple[str, ...] = ("improved", "unchanged"),
    allowed_state_transitions: tuple[str, ...] = (
        "blocked_to_accepted",
        "unchanged",
    ),
    require_previous_accepted: bool = False,
    require_current_accepted: bool = True,
    allow_unchanged: bool = True,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy:
    body = {
        "policy_id": policy_id,
        "maximum_changed_count": maximum_changed_count,
        "allowed_directions": tuple(sorted(allowed_directions)),
        "allowed_state_transitions": tuple(sorted(allowed_state_transitions)),
        "require_previous_accepted": require_previous_accepted,
        "require_current_accepted": require_current_accepted,
        "allow_unchanged": allow_unchanged,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
                provisional
            )
        ),
    )


def default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy
):
    """Return a recovery-focused policy for accepted candidate packets."""

    return build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy()


def release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy() -> (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy
):
    """Return a broad policy for retaining any valid packet-diff evidence."""

    return build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
        policy_id=("module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-release"),
        maximum_changed_count=512,
        allowed_directions=("changed", "improved", "regressed", "unchanged"),
        allowed_state_transitions=(
            "accepted_to_blocked",
            "blocked_to_accepted",
            "changed",
            "unchanged",
        ),
        require_previous_accepted=False,
        require_current_accepted=False,
        allow_unchanged=True,
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyCheck(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_check(
                provisional
            )
        ),
    )


def evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff,
    policy: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy | None = None,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate:
    """Evaluate packet-diff admission while retaining every failed check."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiff):
        raise ValidationError("packet-diff policy requires a typed comparison")
    verification = verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff(value)
    if not verification.accepted:
        raise ValidationError("packet-diff policy requires a valid comparison")
    selected = (
        policy
        or default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy()
    )
    if not isinstance(
        selected,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy,
    ):
        raise ValidationError("packet-diff policy must be typed")
    change_addresses_valid = all(
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_change(item)
        == item.content_address
        for item in value.changes
    )
    public_clean = not _has_forbidden_key(value.to_dict()) and not _has_forbidden_key(
        selected.to_dict()
    )
    checks = (
        _check(
            "address-lineage",
            all(
                bool(item)
                for item in (
                    value.previous_packet_address,
                    value.current_packet_address,
                    value.previous_gate_address,
                    value.current_gate_address,
                    value.previous_audit_address,
                    value.current_audit_address,
                )
            ),
            "present",
            "present",
            "both packet lineages retain packet, gate, and audit addresses",
        ),
        _check(
            "change-addresses",
            change_addresses_valid,
            "valid" if change_addresses_valid else "invalid",
            "valid",
            "every packet-diff field delta address replays",
        ),
        _check(
            "changed-count",
            value.changed_count <= selected.maximum_changed_count,
            value.changed_count,
            f"<={selected.maximum_changed_count}",
            "packet-diff field changes remain within the configured budget",
        ),
        _check(
            "current-state",
            not selected.require_current_accepted or value.current_accepted,
            value.current_accepted,
            True if selected.require_current_accepted else "not-required",
            "candidate packet acceptance follows the policy requirement",
        ),
        _check(
            "direction",
            value.direction.value in selected.allowed_directions,
            value.direction.value,
            selected.allowed_directions,
            "packet-diff direction is admitted by the policy",
        ),
        _check(
            "previous-state",
            not selected.require_previous_accepted or value.previous_accepted,
            value.previous_accepted,
            True if selected.require_previous_accepted else "not-required",
            "baseline packet acceptance follows the policy requirement",
        ),
        _check(
            "public-boundary",
            public_clean,
            "clean" if public_clean else "forbidden-key",
            "clean",
            "policy and packet comparison contain only public aggregate fields",
        ),
        _check(
            "state-transition",
            value.state_transition.value in selected.allowed_state_transitions,
            value.state_transition.value,
            selected.allowed_state_transitions,
            "packet-diff state transition is admitted by the policy",
        ),
        _check(
            "unchanged-control",
            selected.allow_unchanged or value.changed_count > 0,
            value.changed_count,
            "allowed" if selected.allow_unchanged else ">0",
            "unchanged packet comparisons follow the policy control",
        ),
    )
    ordered = tuple(sorted(checks, key=lambda item: item.check_id))
    body = {
        "diff_address": value.content_address,
        "policy": selected,
        "checks": ordered,
        "accepted": all(item.passed for item in ordered),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
                provisional
            )
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy:
    if not isinstance(
        value,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy,
    ):
        raise ValidationError("packet-diff policy verification requires a typed policy")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(value)
        != value.content_address
    ):
        raise ValidationError("packet-diff policy address mismatch")
    return value


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate:
    if not isinstance(
        value,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    ):
        raise ValidationError("packet-diff policy gate verification requires a typed gate")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(value.policy)
    for check in value.checks:
        if (
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_check(
                check
            )
            != check.content_address
        ):
            raise ValidationError(f"packet-diff policy check address mismatch: {check.check_id}")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
            value
        )
        != value.content_address
    ):
        raise ValidationError("packet-diff policy gate address mismatch")
    return value


def _policy_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy:
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicy(
            policy_id=str(value.get("policy_id", "")),
            maximum_changed_count=value.get("maximum_changed_count"),
            allowed_directions=tuple(value.get("allowed_directions", ())),
            allowed_state_transitions=tuple(value.get("allowed_state_transitions", ())),
            require_previous_accepted=value.get("require_previous_accepted"),
            require_current_accepted=value.get("require_current_accepted"),
            allow_unchanged=value.get("allow_unchanged"),
            content_address=str(value.get("content_address", "")),
        )
    )


def _gate_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate:
    raw_policy = value.get("policy")
    raw_checks = value.get("checks")
    if not isinstance(raw_policy, Mapping) or not isinstance(raw_checks, list):
        raise ValidationError("packet-diff policy gate payload is invalid")
    checks = tuple(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyCheck(
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
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate(
            diff_address=str(value.get("diff_address", "")),
            policy=_policy_from_mapping(raw_policy),
            checks=checks,
            accepted=value.get("accepted"),
            content_address=str(value.get("content_address", "")),
        )
    )


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate:
    if isinstance(value, Mapping):
        return _gate_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="packet-diff policy gate", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet-diff policy gate: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("packet-diff policy gate must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("packet-diff policy gate is not canonical JSON")
    return _gate_from_mapping(parsed)


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate
    | bytes
    | bytearray
    | str
    | Path
    | Mapping[str, Any],
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = (
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_DEFAULT_LIMIT
    ),
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_MAX_LIMIT
    ):
        raise ValidationError("packet-diff policy paging is invalid")
    gate = (
        value
        if isinstance(
            value,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
        )
        else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
            value
        )
    )
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(gate)
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
            prefix=(
                "module-workbench-release-bundle-catalog-diff-policy-set-packet-diff-policy-query"
            ),
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-diff policy destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-diff policy destination is not a file")
    _validate_parent(path.parent, "packet-diff policy destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json(
            value
        ).encode(_UTF8),
        field="packet-diff policy destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = (
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_DEFAULT_LIMIT
    ),
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
        value,
        passed=passed,
        text=text,
        offset=offset,
        limit=limit,
    )
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy-Set Packet Diff Policy",
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
        "| "
        f"`{item.check_id}` | {str(item.passed).lower()} | "
        f"`{canonical_json(item.observed)}` | `{canonical_json(item.required)}` | "
        f"{item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_schema() -> dict[
    str, Any
]:
    return {
        "version": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_VERSION
        ),
        "boundary": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_BOUNDARY
        ),
        "resources": ["checks", "summary"],
        "thresholds": [
            "maximum_changed_count",
            "allowed_directions",
            "allowed_state_transitions",
            "require_previous_accepted",
            "require_current_accepted",
            "allow_unchanged",
        ],
        "depends_on": (
            "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff"
        ),
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_capabilities() -> (
    dict[str, Any]
):
    operations = (
        "build_policy",
        "evaluate_changed_budget",
        "evaluate_direction",
        "evaluate_state_transition",
        "evaluate_previous_state",
        "evaluate_current_state",
        "evaluate_unchanged_control",
        "verify_change_addresses",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_VERSION
        ),
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "default_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "evaluate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "release_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
]
