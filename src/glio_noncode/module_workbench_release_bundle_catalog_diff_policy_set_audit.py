"""Independently audit the structure of a catalog-diff policy-set gate."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import _validate_parent, atomic_write_bytes, read_bytes
from .errors import ValidationError
from .module_workbench_release_bundle_catalog_diff_policy import (
    verify_module_workbench_release_bundle_catalog_diff_policy_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set import (
    load_module_workbench_release_bundle_catalog_diff_policy_set_gate,
    verify_module_workbench_release_bundle_catalog_diff_policy_set_gate,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_audit_contracts import (
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_BOUNDARY,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_DEFAULT_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_MAX_LIMIT,
    MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_VERSION,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck,
    address_module_workbench_release_bundle_catalog_diff_policy_set_audit,
    address_module_workbench_release_bundle_catalog_diff_policy_set_audit_check,
)
from .module_workbench_release_bundle_catalog_diff_policy_set_contracts import (
    ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
    address_module_workbench_release_bundle_catalog_diff_policy_set,
    address_module_workbench_release_bundle_catalog_diff_policy_set_gate,
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
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_audit_check(
            provisional
        ),
    )


def _nested_addresses_valid(value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate) -> bool:
    try:
        verify_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
        for gate in value.gates:
            verify_module_workbench_release_bundle_catalog_diff_policy_gate(gate)
    except ValidationError:
        return False
    return True


def audit_module_workbench_release_bundle_catalog_diff_policy_set(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    """Recompute policy-set lineage, selection, address, and boundary invariants."""

    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetGate):
        raise ValidationError("policy-set audit requires a typed policy-set gate")
    policy_ids = value.policy_set.policy_ids
    gate_ids = tuple(item.policy.policy_id for item in value.gates)
    selected = (
        any(item.accepted for item in value.gates)
        if value.policy_set.selection_mode == "any"
        else all(item.accepted for item in value.gates)
    )
    checks = tuple(
        sorted(
            (
                _check(
                    "accepted-count-conservation",
                    value.passed_policy_count + value.failed_policy_count == len(value.gates),
                    value.passed_policy_count + value.failed_policy_count,
                    len(value.gates),
                    "passed and failed policy counts conserve every nested gate",
                ),
                _check(
                    "diff-lineage-conservation",
                    all(item.diff_address == value.diff_address for item in value.gates),
                    tuple(item.diff_address for item in value.gates),
                    value.diff_address,
                    "every nested policy gate references the same catalog diff",
                ),
                _check(
                    "gate-address-replay",
                    address_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
                    == value.content_address,
                    value.content_address,
                    address_module_workbench_release_bundle_catalog_diff_policy_set_gate(value),
                    "policy-set gate address replays from its canonical projection",
                ),
                _check(
                    "gate-count-conservation",
                    len(value.gates) == len(value.policy_set.policies),
                    len(value.gates),
                    len(value.policy_set.policies),
                    "one nested gate exists for every policy",
                ),
                _check(
                    "nested-addresses",
                    _nested_addresses_valid(value),
                    "valid" if _nested_addresses_valid(value) else "invalid",
                    "valid",
                    "nested policy, check, policy-set, and gate addresses replay",
                ),
                _check(
                    "policy-order-conservation",
                    gate_ids == policy_ids,
                    gate_ids,
                    policy_ids,
                    "nested gates retain sorted policy-set order",
                ),
                _check(
                    "policy-set-address-replay",
                    address_module_workbench_release_bundle_catalog_diff_policy_set(
                        value.policy_set
                    )
                    == value.policy_set.content_address,
                    value.policy_set.content_address,
                    address_module_workbench_release_bundle_catalog_diff_policy_set(
                        value.policy_set
                    ),
                    "policy-set address replays from its canonical projection",
                ),
                _check(
                    "public-boundary",
                    not _has_forbidden_key(value.to_dict()),
                    "clean" if not _has_forbidden_key(value.to_dict()) else "forbidden-key",
                    "clean",
                    "policy-set audit input contains only public aggregate fields",
                ),
                _check(
                    "selection-replay",
                    selected == value.accepted,
                    value.accepted,
                    selected,
                    "aggregate acceptance conserves explicit any/all selection mode",
                ),
            ),
            key=lambda item: item.check_id,
        )
    )
    body = {
        "policy_set_gate_address": value.content_address,
        "diff_address": value.diff_address,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    provisional = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit(
        **body,
        content_address="pending",
    )
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit(
        **body,
        content_address=address_module_workbench_release_bundle_catalog_diff_policy_set_audit(
            provisional
        ),
    )


def verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    if not isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit):
        raise ValidationError("policy-set audit verification requires a typed audit")
    for check in value.checks:
        if (
            address_module_workbench_release_bundle_catalog_diff_policy_set_audit_check(check)
            != check.content_address
        ):
            raise ValidationError(f"policy-set audit check address mismatch: {check.check_id}")
    if (
        address_module_workbench_release_bundle_catalog_diff_policy_set_audit(value)
        != value.content_address
    ):
        raise ValidationError("policy-set audit address mismatch")
    return value


def _check_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck:
    return ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAuditCheck(
        check_id=str(value.get("check_id", "")),
        passed=value.get("passed"),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=str(value.get("detail", "")),
        content_address=str(value.get("content_address", "")),
    )


def _audit_from_mapping(
    value: Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    raw_checks = value.get("checks")
    if not isinstance(raw_checks, list) or any(
        not isinstance(item, Mapping) for item in raw_checks
    ):
        raise ValidationError("policy-set audit checks are invalid")
    result = ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit(
        policy_set_gate_address=str(value.get("policy_set_gate_address", "")),
        diff_address=str(value.get("diff_address", "")),
        checks=tuple(_check_from_mapping(item) for item in raw_checks),
        accepted=value.get("accepted"),
        content_address=str(value.get("content_address", "")),
    )
    return verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(result)


def load_module_workbench_release_bundle_catalog_diff_policy_set_audit(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    if isinstance(value, Mapping):
        return _audit_from_mapping(value)
    raw = (
        bytes(value)
        if isinstance(value, (bytes, bytearray))
        else read_bytes(value, field="policy-set audit", max_bytes=_MAX_JSON_BYTES)
    )
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse policy-set audit: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("policy-set audit must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("policy-set audit is not canonical JSON")
    return _audit_from_mapping(parsed)


def build_module_workbench_release_bundle_catalog_diff_policy_set_audit_from_path(
    value: str | Path,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    """Load a persisted gate and build its independent audit."""

    return audit_module_workbench_release_bundle_catalog_diff_policy_set(
        load_module_workbench_release_bundle_catalog_diff_policy_set_gate(value)
    )


def query_module_workbench_release_bundle_catalog_diff_policy_set_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit
    | bytes
    | bytearray
    | str
    | Path
    | Mapping[str, Any],
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if (
        offset < 0
        or limit < 1
        or limit > MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_MAX_LIMIT
    ):
        raise ValidationError("policy-set audit paging is invalid")
    audit = (
        value
        if isinstance(value, ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit)
        else load_module_workbench_release_bundle_catalog_diff_policy_set_audit(value)
    )
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(audit)
    rows = [item.to_dict() for item in audit.checks]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "audit_address": audit.content_address,
        "policy_set_gate_address": audit.policy_set_gate_address,
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
            prefix="module-workbench-release-bundle-catalog-diff-policy-set-audit-query",
        )
    }


def module_workbench_release_bundle_catalog_diff_policy_set_audit_json(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(value)
    return canonical_json(value.to_dict()) + "\n"


def write_module_workbench_release_bundle_catalog_diff_policy_set_audit(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    destination: str | Path,
    *,
    allow_existing: bool = False,
) -> ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(value)
    path = Path(destination)
    if path.exists() and not allow_existing:
        raise ValidationError("policy-set audit destination already exists")
    if path.exists() and not path.is_file():
        raise ValidationError("policy-set audit destination is not a file")
    _validate_parent(path.parent, "policy-set audit destination")
    atomic_write_bytes(
        path,
        module_workbench_release_bundle_catalog_diff_policy_set_audit_json(value).encode(_UTF8),
        field="policy-set audit destination",
    )
    return value


def module_workbench_release_bundle_catalog_diff_policy_set_audit_csv(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_release_bundle_catalog_diff_policy_set_audit(
        value, passed=passed, text=text, offset=offset, limit=limit
    )
    output = io.StringIO(newline="")
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(result["items"])
    return output.getvalue()


def render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown(
    value: ModuleWorkbenchReleaseBundleCatalogDiffPolicySetAudit,
) -> str:
    verify_module_workbench_release_bundle_catalog_diff_policy_set_audit(value)
    lines = [
        "# Module Workbench Release Bundle Catalog Diff Policy Set Audit",
        "",
        f"- Audit: `{value.content_address}`",
        f"- Policy-set gate: `{value.policy_set_gate_address}`",
        f"- Passed / failed: **{value.passed_count} / {value.failed_count}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        "",
        "| Check | Passed | Observed | Required | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | {str(item.passed).lower()} | "
        f"`{canonical_json(item.observed)}` | `{canonical_json(item.required)}` "
        f"| {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def module_workbench_release_bundle_catalog_diff_policy_set_audit_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_VERSION,
        "boundary": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_BOUNDARY,
        "resources": ["checks", "summary"],
        "independent": True,
        "depends_on": "public_aggregate_module_workbench_release_bundle_catalog_diff_policy_set",
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_release_bundle_catalog_diff_policy_set_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_policy_count",
        "audit_policy_order",
        "audit_diff_lineage",
        "audit_selection_replay",
        "audit_address_replay",
        "audit_public_boundary",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_audit",
    )
    return {
        "version": MODULE_WORKBENCH_RELEASE_BUNDLE_CATALOG_DIFF_POLICY_SET_AUDIT_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "independent": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "audit_module_workbench_release_bundle_catalog_diff_policy_set",
    "build_module_workbench_release_bundle_catalog_diff_policy_set_audit_from_path",
    "load_module_workbench_release_bundle_catalog_diff_policy_set_audit",
    "module_workbench_release_bundle_catalog_diff_policy_set_audit_capabilities",
    "module_workbench_release_bundle_catalog_diff_policy_set_audit_csv",
    "module_workbench_release_bundle_catalog_diff_policy_set_audit_json",
    "module_workbench_release_bundle_catalog_diff_policy_set_audit_schema",
    "query_module_workbench_release_bundle_catalog_diff_policy_set_audit",
    "render_module_workbench_release_bundle_catalog_diff_policy_set_audit_markdown",
    "verify_module_workbench_release_bundle_catalog_diff_policy_set_audit",
    "write_module_workbench_release_bundle_catalog_diff_policy_set_audit",
]
