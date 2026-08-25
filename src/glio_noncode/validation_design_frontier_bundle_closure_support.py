"""Shared deterministic projections for the D13 closure handoff.

The closure layer deliberately consumes the already-materialized offline bundle
instead of importing the producer runtime.  This keeps every downstream view
portable, bounded, and independently testable while preserving the exact-byte
identity of the original handoff.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash, jsonable
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle

_DIRECT_IDENTITY_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "participant_id",
        "individual_id",
        "medical_record_number",
        "medical_record_no",
        "phone_number",
        "phone",
        "email_address",
    }
)


def payload(bundle: ValidationDesignBundle, artifact_id: str) -> Any:
    """Decode one hydrated JSON artifact, returning an empty object if absent."""

    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None or artifact.media_type != "application/json":
        return {}
    try:
        value = json.loads(artifact.payload)
    except json.JSONDecodeError:
        return {}
    return value


def csv_payload(bundle: ValidationDesignBundle, artifact_id: str) -> str:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    return artifact.payload if artifact is not None and artifact.payload is not None else ""


def artifact_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "resource": "artifact",
            "artifact_id": item.artifact_id,
            "relative_path": item.relative_path,
            "media_type": item.media_type,
            "kind": item.kind.value,
            "byte_count": item.byte_count,
            "line_count": item.line_count,
            "content_address": item.content_address,
        }
        for item in bundle.artifacts
    )


def record_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    fixture = payload(bundle, "fixture")
    evaluation = payload(bundle, "evaluation")
    records = fixture.get("records", []) if isinstance(fixture, Mapping) else []
    executions = evaluation.get("executions", []) if isinstance(evaluation, Mapping) else []
    execution_by_id = {
        str(item.get("record_id")): item
        for item in executions
        if isinstance(item, Mapping) and item.get("record_id") is not None
    }
    rows: list[dict[str, Any]] = []
    for ordinal, item in enumerate(records, start=1):
        if not isinstance(item, Mapping):
            continue
        record_id = str(item.get("record_id", ""))
        execution = execution_by_id.get(record_id, {})
        issue_codes = tuple(sorted(str(code) for code in execution.get("issue_codes", ()) or ()))
        rows.append(
            {
                "resource": "record",
                "ordinal": ordinal,
                "record_id": record_id,
                "capability": item.get("capability"),
                "operation": item.get("operation"),
                "role": item.get("role"),
                "expected_state": item.get("expected_state"),
                "observed_state": execution.get("observed_state"),
                "expected_issue_codes": tuple(
                    sorted(str(code) for code in item.get("expected_issue_codes", ()) or ())
                ),
                "issue_codes": issue_codes,
                "source_ids": tuple(
                    sorted(str(source) for source in item.get("source_ids", ()) or ())
                ),
                "content_address": execution.get(
                    "content_address", item.get("content_address", "")
                ),
            }
        )
    return tuple(
        sorted(rows, key=lambda row: (str(row.get("operation")), str(row.get("record_id"))))
    )


def execution_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    evaluation = payload(bundle, "evaluation")
    executions = evaluation.get("executions", []) if isinstance(evaluation, Mapping) else []
    return tuple(
        {
            "resource": "execution",
            "record_id": item.get("record_id"),
            "capability": item.get("capability"),
            "operation": item.get("operation"),
            "role": item.get("role"),
            "expected_state": item.get("expected_state"),
            "observed_state": item.get("observed_state"),
            "issue_codes": tuple(sorted(str(code) for code in item.get("issue_codes", ()) or ())),
            "content_address": item.get("content_address"),
        }
        for item in executions
        if isinstance(item, Mapping)
    )


def check_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    evaluation = payload(bundle, "evaluation")
    checks = evaluation.get("checks", []) if isinstance(evaluation, Mapping) else []
    rows: list[dict[str, Any]] = []
    for ordinal, item in enumerate(checks, start=1):
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "resource": "check",
                "ordinal": ordinal,
                "check_id": item.get("check_id"),
                "record_id": item.get("record_id"),
                "plane": item.get("plane"),
                "passed": bool(item.get("passed")),
                "detail": item.get("detail"),
                "content_address": item.get("content_address"),
            }
        )
    return tuple(rows)


def source_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    fixture = payload(bundle, "fixture")
    sources = fixture.get("sources", []) if isinstance(fixture, Mapping) else []
    return tuple(
        {"resource": "source", "ordinal": ordinal, **dict(item)}
        for ordinal, item in enumerate(sources, start=1)
        if isinstance(item, Mapping)
    )


def stage_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    runtime = payload(bundle, "runtime")
    stages = runtime.get("stages", []) if isinstance(runtime, Mapping) else []
    return tuple(
        {"resource": "stage", **dict(item)} for item in stages if isinstance(item, Mapping)
    )


def plane_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    runtime = payload(bundle, "runtime")
    planes = runtime.get("planes", {}) if isinstance(runtime, Mapping) else {}
    if not isinstance(planes, Mapping):
        return ()
    rows: list[dict[str, Any]] = []
    for ordinal, (plane_id, value) in enumerate(sorted(planes.items()), start=1):
        if isinstance(value, Mapping):
            rows.append(
                {
                    "resource": "plane",
                    "ordinal": ordinal,
                    "plane_id": plane_id,
                    "accepted": bool(value.get("accepted")),
                    "content_address": value.get("content_address", ""),
                    "value_keys": tuple(
                        sorted(
                            str(key)
                            for key in value.get("values", {})
                            if isinstance(value.get("values"), Mapping)
                        )
                    ),
                }
            )
        else:
            rows.append(
                {
                    "resource": "plane",
                    "ordinal": ordinal,
                    "plane_id": plane_id,
                    "accepted": bool(value),
                    "content_address": "",
                    "value_keys": (),
                }
            )
    return tuple(rows)


def operation_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    rows = record_rows(bundle)
    by_operation: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_operation.setdefault(str(row.get("operation", "")), []).append(row)
    return tuple(
        {
            "resource": "operation",
            "operation": operation,
            "record_count": len(items),
            "record_ids": tuple(str(item.get("record_id")) for item in items),
            "content_address": content_hash(
                {
                    "operation": operation,
                    "record_ids": tuple(str(item.get("record_id")) for item in items),
                },
                prefix="validation-design-closure-operation",
            ),
        }
        for operation, items in sorted(by_operation.items())
    )


def issue_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    rows = record_rows(bundle)
    index: dict[str, list[str]] = {}
    for row in rows:
        for code in row.get("issue_codes", ()):
            index.setdefault(str(code), []).append(str(row.get("record_id")))
    return tuple(
        {
            "resource": "issue",
            "issue_code": code,
            "record_count": len(record_ids),
            "record_ids": tuple(sorted(record_ids)),
            "content_address": content_hash(
                {"issue_code": code, "record_ids": tuple(sorted(record_ids))},
                prefix="validation-design-closure-issue",
            ),
        }
        for code, record_ids in sorted(index.items())
    )


def state_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    rows = record_rows(bundle)
    states: Counter[str] = Counter()
    for row in rows:
        states[str(row.get("observed_state", "unknown"))] += 1
    return tuple(
        {
            "resource": "state",
            "state": state,
            "record_count": count,
            "content_address": content_hash(
                {"state": state, "record_count": count}, prefix="validation-design-closure-state"
            ),
        }
        for state, count in sorted(states.items())
    )


def review_rows(bundle: ValidationDesignBundle) -> tuple[dict[str, Any], ...]:
    text = csv_payload(bundle, "review-csv")
    if not text:
        return ()
    reader = csv.DictReader(io.StringIO(text))
    return tuple(
        {"resource": "review", "ordinal": ordinal, **dict(row)}
        for ordinal, row in enumerate(reader, start=1)
    )


def all_rows(bundle: ValidationDesignBundle) -> dict[str, tuple[dict[str, Any], ...]]:
    """Return every stable closure resource in one deterministic map."""

    return {
        "artifacts": artifact_rows(bundle),
        "records": record_rows(bundle),
        "executions": execution_rows(bundle),
        "checks": check_rows(bundle),
        "sources": source_rows(bundle),
        "stages": stage_rows(bundle),
        "planes": plane_rows(bundle),
        "operations": operation_rows(bundle),
        "issues": issue_rows(bundle),
        "states": state_rows(bundle),
        "reviews": review_rows(bundle),
    }


def discover_keys(value: Any, prefix: str = "") -> tuple[str, ...]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            keys.add(path)
            keys.update(discover_keys(item, path))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.update(discover_keys(item, prefix))
    return tuple(sorted(keys))


def forbidden_keys(value: Any) -> tuple[str, ...]:
    discovered: set[str] = set()
    for path in discover_keys(value):
        key = path.rsplit(".", 1)[-1].casefold()
        if (
            key in _DIRECT_IDENTITY_KEYS
            or _has_forbidden_key({key: True})
            or contains_private_key({key: True})
        ):
            discovered.add(key)
    return tuple(sorted(discovered))


def safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/"):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def addressed(value: Any, prefix: str | None = None) -> bool:
    text = str(value or "")
    return bool(text) and (prefix is None or text.startswith(prefix))


def closure_address(value: Any, prefix: str) -> str:
    return content_hash(jsonable(value), prefix=prefix)


def csv_text(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = tuple(rows)
    keys = (
        tuple(sorted({str(key) for row in materialized for key in row}))
        if materialized
        else ("resource", "content_address")
    )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(keys)
    for row in materialized:
        writer.writerow(
            [
                ";".join(str(item) for item in value) if isinstance(value, (list, tuple)) else value
                for value in (row.get(key, "") for key in keys)
            ]
        )
    return output.getvalue()


def markdown_table(rows: Iterable[Mapping[str, Any]], title: str) -> str:
    materialized = tuple(rows)
    keys = (
        tuple(sorted({str(key) for row in materialized for key in row}))
        if materialized
        else ("status",)
    )
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    for row in materialized:
        values = []
        for key in keys:
            value = row.get(key, "")
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def bundle_count_map(bundle: ValidationDesignBundle) -> dict[str, int]:
    resources = all_rows(bundle)
    return {
        "artifacts": len(bundle.artifacts),
        "manifest_checks": len(bundle.checks),
        "records": len(resources["records"]),
        "executions": len(resources["executions"]),
        "checks": len(resources["checks"]),
        "sources": len(resources["sources"]),
        "stages": len(resources["stages"]),
        "planes": len(resources["planes"]),
        "operations": len(resources["operations"]),
        "issues": len(resources["issues"]),
        "states": len(resources["states"]),
        "reviews": len(resources["reviews"]),
    }


def canonical_row(value: Mapping[str, Any]) -> str:
    return canonical_json(jsonable(dict(value)))


__all__ = [
    "_DIRECT_IDENTITY_KEYS",
    "addressed",
    "all_rows",
    "artifact_rows",
    "bundle_count_map",
    "canonical_row",
    "check_rows",
    "closure_address",
    "csv_payload",
    "csv_text",
    "discover_keys",
    "execution_rows",
    "forbidden_keys",
    "issue_rows",
    "markdown_table",
    "operation_rows",
    "payload",
    "plane_rows",
    "record_rows",
    "review_rows",
    "safe_relative_path",
    "source_rows",
    "stage_rows",
    "state_rows",
]
