"""Shared deterministic row projections for the D15 closure layer."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from typing import Any

from .run_workspace import _has_forbidden_key
from .serialization import canonical_json, content_hash
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

_DIRECT_IDENTITY_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "author",
        "author_id",
        "author_name",
        "email",
        "email_address",
        "generated_by",
        "individual_id",
        "language",
        "medical_record_number",
        "model",
        "model_id",
        "model_name",
        "participant_id",
        "patient_id",
        "phone",
        "programming_language",
        "produced_by",
        "sample_id",
        "subject_id",
    }
)


def payload(bundle: WorkbenchReleaseOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return {}
    if artifact.media_type != "application/json":
        return artifact.payload
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return {}


def _list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping) or not isinstance(value.get(field), list):
        return []
    return [dict(item) for item in value[field] if isinstance(item, Mapping)]


def _address_rows(rows: Iterable[Mapping[str, Any]], resource: str) -> tuple[dict[str, Any], ...]:
    result = []
    for ordinal, source in enumerate(rows, start=1):
        row = dict(source)
        row["resource"] = resource
        row.setdefault(
            "content_address",
            content_hash(
                {"resource": resource, "ordinal": ordinal, "row": row},
                prefix="workbench-release-closure-row",
            ),
        )
        row["ordinal"] = ordinal
        result.append(row)
    return tuple(result)


def artifact_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
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


def record_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    fixture = payload(bundle, "fixture")
    evaluation = payload(bundle, "evaluation")
    executions = {str(item.get("record_id")): item for item in _list(evaluation, "executions")}
    rows = []
    for ordinal, record in enumerate(_list(fixture, "records"), start=1):
        record_id = str(record.get("record_id", ""))
        execution = executions.get(record_id, {})
        rows.append(
            {
                "resource": "record",
                "ordinal": ordinal,
                "record_id": record_id,
                "capability": record.get("capability"),
                "operation": record.get("operation"),
                "role": record.get("role"),
                "expected_state": record.get("expected_state"),
                "observed_state": execution.get("observed_state"),
                "accepted": not bool(execution.get("issue_codes")),
                "issue_codes": tuple(
                    sorted(str(item) for item in execution.get("issue_codes", ()) or ())
                ),
                "source_ids": tuple(
                    sorted(str(item) for item in record.get("source_ids", ()) or ())
                ),
                "content_address": execution.get(
                    "content_address", record.get("content_address", "")
                ),
            }
        )
    return tuple(
        sorted(rows, key=lambda row: (str(row.get("operation")), str(row.get("record_id"))))
    )


def execution_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "evaluation"), "executions"), "execution")


def check_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "evaluation"), "checks"), "check")


def source_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "fixture"), "sources"), "source")


def validation_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "validation"), "cells"), "validation")


def evidence_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "evidence"), "cells"), "evidence")


def view_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "view"), "rows"), "view")


def queue_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "review-queue"), "rows"), "queue")


def diagnostic_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "diagnostics"), "findings"), "diagnostic")


def stage_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "runtime"), "stages"), "stage")


def stage_index_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "stage-index"), "stages"), "stage_index")


def lineage_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    lineage = payload(bundle, "lineage")
    rows = []
    if isinstance(lineage, Mapping):
        for source_id, record_ids in sorted((lineage.get("source_to_records") or {}).items()):
            for record_id in record_ids if isinstance(record_ids, list) else ():
                rows.append(
                    {
                        "parent_id": str(source_id),
                        "child_id": str(record_id),
                        "relation": "source_to_record",
                    }
                )
        for record_id, execution_id in sorted((lineage.get("record_to_execution") or {}).items()):
            rows.append(
                {
                    "parent_id": str(record_id),
                    "child_id": str(execution_id),
                    "relation": "record_to_execution",
                }
            )
    addressed = list(_address_rows(rows, "edge"))
    for row in addressed:
        row["edge_id"] = f"{row.get('parent_id')}->{row.get('child_id')}:{row.get('relation')}"
    return tuple(addressed)


def operation_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in record_rows(bundle):
        grouped.setdefault(str(row.get("operation")), []).append(row)
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
                prefix="workbench-release-closure-operation",
            ),
        }
        for operation, items in sorted(grouped.items())
    )


def control_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "controls"), "rows"), "control")


def failure_rows(bundle: WorkbenchReleaseOfflineBundle) -> tuple[dict[str, Any], ...]:
    return _address_rows(_list(payload(bundle, "failure-injection"), "cases"), "failure")


def all_rows(bundle: WorkbenchReleaseOfflineBundle) -> dict[str, tuple[dict[str, Any], ...]]:
    return {
        "artifacts": artifact_rows(bundle),
        "records": record_rows(bundle),
        "executions": execution_rows(bundle),
        "checks": check_rows(bundle),
        "sources": source_rows(bundle),
        "validation": validation_rows(bundle),
        "evidence": evidence_rows(bundle),
        "edges": lineage_rows(bundle),
        "views": view_rows(bundle),
        "queue": queue_rows(bundle),
        "diagnostics": diagnostic_rows(bundle),
        "stages": stage_rows(bundle),
        "stage_index": stage_index_rows(bundle),
        "operations": operation_rows(bundle),
        "controls": control_rows(bundle),
        "failures": failure_rows(bundle),
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
    found: set[str] = set()
    for path in discover_keys(value):
        key = path.rsplit(".", 1)[-1].casefold()
        if key in _DIRECT_IDENTITY_KEYS or _has_forbidden_key({key: True}):
            found.add(key)
    return tuple(sorted(found))


def safe_relative_path(value: str) -> bool:
    if not value or "\\" in value or value.startswith("/"):
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def csv_text(rows: Iterable[Mapping[str, Any]]) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or (
        "resource",
        "content_address",
    )
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(fields)
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (list, tuple)):
                value = ";".join(str(item) for item in value)
            elif isinstance(value, Mapping):
                value = canonical_json(value)
            values.append(value)
        writer.writerow(values)
    return stream.getvalue()


def markdown_table(rows: Iterable[Mapping[str, Any]], title: str) -> str:
    materialized = tuple(rows)
    fields = tuple(sorted({str(key) for row in materialized for key in row})) or ("status",)
    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in materialized:
        values = []
        for field in fields:
            value = row.get(field, "")
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            values.append(str(value).replace("|", "\\|"))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def count_map(bundle: WorkbenchReleaseOfflineBundle) -> dict[str, int]:
    rows = all_rows(bundle)
    return {
        "artifacts": len(bundle.artifacts),
        "manifest_checks": len(bundle.checks),
        **{key: len(value) for key, value in rows.items()},
    }


__all__ = [
    "_DIRECT_IDENTITY_KEYS",
    "all_rows",
    "artifact_rows",
    "check_rows",
    "control_rows",
    "count_map",
    "csv_text",
    "diagnostic_rows",
    "discover_keys",
    "evidence_rows",
    "failure_rows",
    "forbidden_keys",
    "lineage_rows",
    "markdown_table",
    "operation_rows",
    "payload",
    "queue_rows",
    "record_rows",
    "safe_relative_path",
    "source_rows",
    "stage_index_rows",
    "stage_rows",
    "validation_rows",
    "view_rows",
]
