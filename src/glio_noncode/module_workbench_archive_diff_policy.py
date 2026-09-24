"""Evaluate release policy over a source-free workbench archive diff."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import read_bytes
from .errors import ValidationError
from .module_workbench_archive_diff import (
    load_module_workbench_archive_diff,
    verify_module_workbench_archive_diff_value,
)
from .module_workbench_archive_diff_contracts import ModuleWorkbenchArchiveDiff
from .module_workbench_archive_diff_policy_contracts import (
    MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_BOUNDARY,
    MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_DEFAULT_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_LIMIT,
    MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION,
    ModuleWorkbenchArchiveDiffPolicy,
    ModuleWorkbenchArchiveDiffPolicyCheck,
    ModuleWorkbenchArchiveDiffPolicyGate,
    address_module_workbench_archive_diff_policy,
    address_module_workbench_archive_diff_policy_check,
    address_module_workbench_archive_diff_policy_gate,
)
from .run_workspace import _has_forbidden_key
from .serialization import _strict_json_loads, canonical_json, content_hash

_UTF8 = "utf-8"
_MAX_JSON_BYTES = 32 * 1024 * 1024
_DEPTH_ORDER = {"blocked": 0, "starter": 1, "established": 2, "deep": 3, "comprehensive": 4}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "blocker": 3}


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} is required")
    return value


def build_module_workbench_archive_diff_policy(
    *,
    policy_id: str = "module-workbench-archive-diff-strict",
    maximum_added_count: int = 0,
    maximum_changed_count: int = 0,
    maximum_removed_count: int = 0,
    maximum_regression_count: int = 0,
    maximum_task_delta: int = 0,
    minimum_score_delta: float = 0.0,
    require_accepted_inputs: bool = True,
) -> ModuleWorkbenchArchiveDiffPolicy:
    """Build deterministic thresholds for source-free candidate admission."""

    body = {
        "policy_id": policy_id,
        "maximum_added_count": maximum_added_count,
        "maximum_changed_count": maximum_changed_count,
        "maximum_removed_count": maximum_removed_count,
        "maximum_regression_count": maximum_regression_count,
        "maximum_task_delta": maximum_task_delta,
        "minimum_score_delta": minimum_score_delta,
        "require_accepted_inputs": require_accepted_inputs,
    }
    provisional = ModuleWorkbenchArchiveDiffPolicy(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffPolicy(
        **body,
        content_address=address_module_workbench_archive_diff_policy(provisional),
    )


def default_module_workbench_archive_diff_policy() -> ModuleWorkbenchArchiveDiffPolicy:
    """Return a strict no-regression policy."""

    return build_module_workbench_archive_diff_policy()


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleWorkbenchArchiveDiffPolicyCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    provisional = ModuleWorkbenchArchiveDiffPolicyCheck(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffPolicyCheck(
        **body,
        content_address=address_module_workbench_archive_diff_policy_check(provisional),
    )


def _regression_ids(value: ModuleWorkbenchArchiveDiff) -> tuple[str, ...]:
    rows: list[str] = []
    for item in value.diff.changes:
        if item.kind.value != "changed":
            continue
        score_regressed = (
            item.previous_score is not None
            and item.current_score is not None
            and item.current_score < item.previous_score
        )
        depth_regressed = (
            item.previous_depth_band in _DEPTH_ORDER
            and item.current_depth_band in _DEPTH_ORDER
            and _DEPTH_ORDER[item.current_depth_band] < _DEPTH_ORDER[item.previous_depth_band]
        )
        risk_regressed = (
            item.previous_risk in _RISK_ORDER
            and item.current_risk in _RISK_ORDER
            and _RISK_ORDER[item.current_risk] > _RISK_ORDER[item.previous_risk]
        )
        if score_regressed or depth_regressed or risk_regressed:
            rows.append(item.module_id)
    return tuple(sorted(rows))


def evaluate_module_workbench_archive_diff_policy(
    value: ModuleWorkbenchArchiveDiff,
    policy: ModuleWorkbenchArchiveDiffPolicy | None = None,
) -> ModuleWorkbenchArchiveDiffPolicyGate:
    """Evaluate candidate changes without source, tests, or documentation."""

    if not isinstance(value, ModuleWorkbenchArchiveDiff):
        raise ValidationError("archive-diff policy requires a typed comparison")
    verify_module_workbench_archive_diff_value(value)
    selected = policy or default_module_workbench_archive_diff_policy()
    if not isinstance(selected, ModuleWorkbenchArchiveDiffPolicy):
        raise ValidationError("archive-diff policy must be typed")
    regressions = _regression_ids(value)
    checks = (
        _check(
            "accepted-inputs",
            not selected.require_accepted_inputs or value.accepted,
            value.accepted,
            True if selected.require_accepted_inputs else "not-required",
            "both archived workbench inputs are accepted when required",
        ),
        _check(
            "added-count",
            value.diff.added_count <= selected.maximum_added_count,
            value.diff.added_count,
            f"<={selected.maximum_added_count}",
            "candidate-only modules remain within the addition budget",
        ),
        _check(
            "changed-count",
            value.diff.changed_count <= selected.maximum_changed_count,
            value.diff.changed_count,
            f"<={selected.maximum_changed_count}",
            "changed modules remain within the change budget",
        ),
        _check(
            "classification-conservation",
            sum(
                (
                    value.diff.added_count,
                    value.diff.changed_count,
                    value.diff.removed_count,
                    value.diff.unchanged_count,
                )
            )
            == len(value.diff.changes),
            len(value.diff.changes),
            sum(
                (
                    value.diff.added_count,
                    value.diff.changed_count,
                    value.diff.removed_count,
                    value.diff.unchanged_count,
                )
            ),
            "diff classification counts conserve every module row",
        ),
        _check(
            "minimum-score-delta",
            value.diff.score_delta >= selected.minimum_score_delta,
            value.diff.score_delta,
            f">={selected.minimum_score_delta}",
            "aggregate score movement reaches the configured floor",
        ),
        _check(
            "regression-count",
            len(regressions) <= selected.maximum_regression_count,
            len(regressions),
            f"<={selected.maximum_regression_count}",
            "changed modules do not exceed the regression budget",
        ),
        _check(
            "removed-count",
            value.diff.removed_count <= selected.maximum_removed_count,
            value.diff.removed_count,
            f"<={selected.maximum_removed_count}",
            "baseline-only modules remain within the removal budget",
        ),
        _check(
            "task-delta",
            abs(value.diff.task_delta) <= selected.maximum_task_delta,
            value.diff.task_delta,
            f"abs(delta)<={selected.maximum_task_delta}",
            "planned task count remains within the configured drift budget",
        ),
        _check(
            "public-boundary",
            not _has_forbidden_key(value.to_dict())
            and not _has_forbidden_key(selected.to_dict()),
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
    provisional = ModuleWorkbenchArchiveDiffPolicyGate(**body, content_address="pending")
    return ModuleWorkbenchArchiveDiffPolicyGate(
        **body,
        content_address=address_module_workbench_archive_diff_policy_gate(provisional),
    )


def verify_module_workbench_archive_diff_policy(
    value: ModuleWorkbenchArchiveDiffPolicy,
) -> ModuleWorkbenchArchiveDiffPolicy:
    if not isinstance(value, ModuleWorkbenchArchiveDiffPolicy):
        raise ValidationError("archive-diff policy verification requires a typed policy")
    if address_module_workbench_archive_diff_policy(value) != value.content_address:
        raise ValidationError("archive-diff policy address mismatch")
    return value


def verify_module_workbench_archive_diff_policy_gate(
    value: ModuleWorkbenchArchiveDiffPolicyGate,
) -> ModuleWorkbenchArchiveDiffPolicyGate:
    if not isinstance(value, ModuleWorkbenchArchiveDiffPolicyGate):
        raise ValidationError("archive-diff gate verification requires a typed gate")
    verify_module_workbench_archive_diff_policy(value.policy)
    for check in value.checks:
        if address_module_workbench_archive_diff_policy_check(check) != check.content_address:
            raise ValidationError(f"archive-diff policy check address mismatch: {check.check_id}")
    if address_module_workbench_archive_diff_policy_gate(value) != value.content_address:
        raise ValidationError("archive-diff policy gate address mismatch")
    return value


def _policy_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchArchiveDiffPolicy:
    return verify_module_workbench_archive_diff_policy(
        ModuleWorkbenchArchiveDiffPolicy(
            policy_id=str(value.get("policy_id", "")),
            maximum_added_count=value.get("maximum_added_count"),
            maximum_changed_count=value.get("maximum_changed_count"),
            maximum_removed_count=value.get("maximum_removed_count"),
            maximum_regression_count=value.get("maximum_regression_count"),
            maximum_task_delta=value.get("maximum_task_delta"),
            minimum_score_delta=value.get("minimum_score_delta"),
            require_accepted_inputs=value.get("require_accepted_inputs"),
            content_address=str(value.get("content_address", "")),
        )
    )


def _gate_from_mapping(value: Mapping[str, Any]) -> ModuleWorkbenchArchiveDiffPolicyGate:
    raw_policy = value.get("policy")
    raw_checks = value.get("checks")
    if not isinstance(raw_policy, Mapping) or not isinstance(raw_checks, list):
        raise ValidationError("archive-diff policy gate payload is invalid")
    checks = tuple(
        ModuleWorkbenchArchiveDiffPolicyCheck(
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
    return verify_module_workbench_archive_diff_policy_gate(
        ModuleWorkbenchArchiveDiffPolicyGate(
            diff_address=str(value.get("diff_address", "")),
            policy=_policy_from_mapping(raw_policy),
            checks=checks,
            accepted=value.get("accepted"),
            content_address=str(value.get("content_address", "")),
        )
    )


def load_module_workbench_archive_diff_policy_gate(
    value: bytes | bytearray | str | Path | Mapping[str, Any],
) -> ModuleWorkbenchArchiveDiffPolicyGate:
    """Load an exact canonical gate document."""

    if isinstance(value, Mapping):
        return _gate_from_mapping(value)
    raw = bytes(value) if isinstance(value, (bytes, bytearray)) else read_bytes(value, field="archive-diff policy gate", max_bytes=_MAX_JSON_BYTES)
    try:
        parsed = _strict_json_loads(raw.decode(_UTF8))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(f"cannot parse archive-diff policy gate: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise ValidationError("archive-diff policy gate must be a JSON object")
    if raw != (canonical_json(parsed) + "\n").encode(_UTF8):
        raise ValidationError("archive-diff policy gate is not canonical JSON")
    return _gate_from_mapping(parsed)


def query_module_workbench_archive_diff_policy(
    value: ModuleWorkbenchArchiveDiffPolicyGate | bytes | bytearray | str | Path | Mapping[str, Any],
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_MAX_LIMIT:
        raise ValidationError("archive-diff policy paging is invalid")
    gate = value if isinstance(value, ModuleWorkbenchArchiveDiffPolicyGate) else load_module_workbench_archive_diff_policy_gate(value)
    verify_module_workbench_archive_diff_policy_gate(gate)
    rows = [item.to_dict() for item in gate.checks]
    if passed is not None:
        rows = [item for item in rows if item["passed"] is passed]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "gate_address": gate.content_address,
        "diff_address": gate.diff_address,
        "policy_address": gate.policy_address,
        "query": {"passed": passed, "text": text},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": gate.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-workbench-archive-diff-policy-query")}


def module_workbench_archive_diff_policy_json(value: ModuleWorkbenchArchiveDiffPolicyGate) -> str:
    verify_module_workbench_archive_diff_policy_gate(value)
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_archive_diff_policy_csv(
    value: ModuleWorkbenchArchiveDiffPolicyGate,
    *,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_DEFAULT_LIMIT,
) -> str:
    result = query_module_workbench_archive_diff_policy(
        value,
        passed=passed,
        text=text,
        offset=offset,
        limit=limit,
    )
    rows = result["items"]
    fields = ("check_id", "passed", "observed", "required", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def render_module_workbench_archive_diff_policy_markdown(
    value: ModuleWorkbenchArchiveDiffPolicyGate,
) -> str:
    verify_module_workbench_archive_diff_policy_gate(value)
    lines = [
        "# Module Workbench Archive Diff Policy",
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
        f"| `{item.check_id}` | {str(item.passed).lower()} | `{item.observed}` | `{item.required}` | {item.detail} |"
        for item in value.checks
    )
    return "\n".join(lines) + "\n"


def module_workbench_archive_diff_policy_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION,
        "boundary": MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_BOUNDARY,
        "resources": ["checks", "summary"],
        "thresholds": [
            "maximum_added_count",
            "maximum_changed_count",
            "maximum_removed_count",
            "maximum_regression_count",
            "maximum_task_delta",
            "minimum_score_delta",
            "require_accepted_inputs",
        ],
        "depends_on": "public_aggregate_module_workbench_archive_diff",
        "source_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_archive_diff_policy_capabilities() -> dict[str, Any]:
    operations = (
        "build_policy",
        "evaluate_added_budget",
        "evaluate_changed_budget",
        "evaluate_removed_budget",
        "evaluate_regression_budget",
        "evaluate_score_delta",
        "evaluate_task_delta",
        "evaluate_accepted_inputs",
        "query_checks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_addresses",
    )
    return {
        "version": MODULE_WORKBENCH_ARCHIVE_DIFF_POLICY_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "source_free": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_archive_diff_policy",
    "default_module_workbench_archive_diff_policy",
    "evaluate_module_workbench_archive_diff_policy",
    "load_module_workbench_archive_diff_policy_gate",
    "module_workbench_archive_diff_policy_capabilities",
    "module_workbench_archive_diff_policy_csv",
    "module_workbench_archive_diff_policy_json",
    "module_workbench_archive_diff_policy_schema",
    "query_module_workbench_archive_diff_policy",
    "render_module_workbench_archive_diff_policy_markdown",
    "verify_module_workbench_archive_diff_policy",
    "verify_module_workbench_archive_diff_policy_gate",
]
