"""Independently audit packet-diff policy gates."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_contracts import (  # noqa: E501
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_check,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_check,
    address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 16 * 1024 * 1024


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_check(
                provisional
            )
        ),
    )


def _policy_controls_valid(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
) -> bool:
    policy = value.policy
    return (
        policy.allowed_directions == tuple(sorted(set(policy.allowed_directions)))
        and policy.allowed_state_transitions == tuple(sorted(set(policy.allowed_state_transitions)))
        and isinstance(policy.require_previous_accepted, bool)
        and isinstance(policy.require_current_accepted, bool)
        and isinstance(policy.allow_unchanged, bool)
        and policy.maximum_changed_count >= 0
    )


def audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    """Recompute gate lineage, controls, decisions, and public-boundary invariants."""

    if not isinstance(
        value,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyGate,
    ):
        raise ValidationError("packet-diff policy audit requires a typed policy gate")
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(value)
    check_ids = tuple(item.check_id for item in value.checks)
    check_addresses_valid = all(
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_check(
            item
        )
        == item.content_address
        for item in value.checks
    )
    gate_address = (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(
            value
        )
    )
    policy_address = (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
            value.policy
        )
    )
    public_clean = not _has_forbidden_key(value.to_dict())
    checks = tuple(
        sorted(
            (
                _check(
                    "accepted-count-conservation",
                    value.passed_count + value.failed_count == len(value.checks),
                    value.passed_count + value.failed_count,
                    len(value.checks),
                    "passed and failed policy checks conserve every gate check",
                ),
                _check(
                    "check-addresses",
                    check_addresses_valid,
                    "valid" if check_addresses_valid else "invalid",
                    "valid",
                    "every nested policy check address replays",
                ),
                _check(
                    "check-order-conservation",
                    check_ids == tuple(sorted(set(check_ids))),
                    check_ids,
                    tuple(sorted(set(check_ids))),
                    "policy checks retain sorted unique order",
                ),
                _check(
                    "decision-replay",
                    value.accepted == all(item.passed for item in value.checks),
                    value.accepted,
                    all(item.passed for item in value.checks),
                    "gate acceptance conserves every policy check",
                ),
                _check(
                    "diff-lineage-conservation",
                    bool(value.diff_address),
                    value.diff_address,
                    "present",
                    "policy gate retains the packet-diff address under audit",
                ),
                _check(
                    "gate-address-replay",
                    gate_address == value.content_address,
                    value.content_address,
                    gate_address,
                    "policy gate address replays from its canonical projection",
                ),
                _check(
                    "policy-address-replay",
                    policy_address == value.policy.content_address,
                    value.policy.content_address,
                    policy_address,
                    "policy address replays from its canonical projection",
                ),
                _check(
                    "policy-controls",
                    _policy_controls_valid(value),
                    "valid" if _policy_controls_valid(value) else "invalid",
                    "valid",
                    "policy choices and boolean controls retain canonical structure",
                ),
                _check(
                    "public-boundary",
                    public_clean,
                    "clean" if public_clean else "forbidden-key",
                    "clean",
                    "policy gate contains only public aggregate fields",
                ),
                _check(
                    "typed-gate-replay",
                    True,
                    "verified",
                    "verified",
                    "typed policy gate reloads before independent audit",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    body = {
        "policy_gate_address": value.content_address,
        "diff_address": value.diff_address,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit(
        **body,
        content_address=(
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
                provisional
            )
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    if not isinstance(
        value,
        ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    ):
        raise ValidationError("packet-diff policy audit verification requires a typed audit")
    for check in value.checks:
        if (
            address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_check(
                check
            )
            != check.content_address
        ):
            raise ValidationError(
                f"packet-diff policy audit check address mismatch: {check.check_id}"
            )
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
            value
        )
        != value.content_address
    ):
        raise ValidationError("packet-diff policy audit address mismatch")
    return value


def _check_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAuditCheck(
        check_id=str(value.get("check_id", "")),
        passed=value.get("passed"),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def _audit_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    raw_checks = value.get("checks")
    if not isinstance(raw_checks, list) or any(
        not isinstance(item, Mapping) for item in raw_checks
    ):
        raise ValidationError("packet-diff policy audit checks are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit(
        policy_gate_address=str(value.get("policy_gate_address", "")),
        diff_address=str(value.get("diff_address", "")),
        checks=tuple(_check_from_mapping(item) for item in raw_checks),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
        result
    )


def load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    if isinstance(value, Mapping):
        return _audit_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="packet-diff policy audit", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse packet-diff policy audit: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("packet-diff policy audit must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("packet-diff policy audit is not canonical JSON")
    return _audit_from_mapping(parsed)


def build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_from_path(  # noqa: E501
    value: str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    """Load a persisted policy gate and build its independent audit."""

    from .module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy import (
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate,
    )

    return audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy(
        load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_gate(value)
    )


def query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit
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
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_DEFAULT_LIMIT
    ),
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit
        > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_MAX_LIMIT
    ):
        raise ValidationError("packet-diff policy audit paging is invalid")
    audit = (
        value
        if isinstance(
            value,
            ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
        )
        else load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
            value
        )
    )
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(audit)
    rows = [item.to_dict() for item in audit.checks]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "audit_address": audit.content_address,
        "policy_gate_address": audit.policy_gate_address,
        "diff_address": audit.diff_address,
        "passed": passed,
        "text": text,
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": audit.accepted,
    }
    return body | {
        "content_address": content_hash(
            body,
            prefix=(
                "module-workbench-release-bundle-catalog-diff-policy-set-"
                "packet-diff-policy-audit-query"
            ),
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("packet-diff policy audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("packet-diff policy audit destination is not a file")
    _validate_parent(path.parent, "packet-diff policy audit destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json(
            value
        ).encode(_UTF8),
        field="packet-diff policy audit destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = (
        MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_DEFAULT_LIMIT
    ),
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(
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


def render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown(  # noqa: E501
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetPacketDiffPolicyAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy-Set Packet Diff Policy Audit",
        "",
        f"- Audit: `{value.content_address}`",
        f"- Policy gate: `{value.policy_gate_address}`",
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


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_schema() -> (
    dict[str, Any]
):
    return {
        "version": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_VERSION
        ),
        "boundary": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_BOUNDARY
        ),
        "resources": ["checks", "summary"],
        "independent": True,
        "depends_on": (
            "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy"
        ),
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_capabilities() -> (  # noqa: E501
    dict[str, Any]
):
    operations = (
        "audit_check_count",
        "audit_check_order",
        "audit_check_addresses",
        "audit_diff_lineage",
        "audit_policy_controls",
        "audit_decision_replay",
        "audit_gate_address",
        "audit_policy_address",
        "audit_public_boundary",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_audit",
    )
    return {
        "version": (
            MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_PACKET_DIFF_POLICY_AUDIT_VERSION
        ),
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "independent": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "audit_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy",
    "build_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_from_path",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_packet_diff_policy_audit",
]
