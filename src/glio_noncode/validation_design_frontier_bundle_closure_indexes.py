"""Address-only indexes for the D13 validation-design closure handoff."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_contracts import (
    ValidationDesignClosureIndexAudit,
    ValidationDesignClosureIndexEntry,
    ValidationDesignClosureIndexes,
    ValidationDesignClosurePlane,
    validation_design_closure_check,
)
from .validation_design_frontier_bundle_closure_support import all_rows, bundle_count_map
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle


def _entry(
    key: Any, address: Any, resource: str, ordinal: int
) -> ValidationDesignClosureIndexEntry:
    return ValidationDesignClosureIndexEntry(
        key=str(key),
        address=str(address or ""),
        resource=resource,
        ordinal=int(ordinal),
    )


def _entries(
    rows: Iterable[Mapping[str, Any]], key: str, resource: str
) -> tuple[ValidationDesignClosureIndexEntry, ...]:
    result: list[ValidationDesignClosureIndexEntry] = []
    for ordinal, row in enumerate(rows, start=1):
        value = row.get(key)
        if value is None or value == "":
            continue
        address = row.get("content_address", "")
        if isinstance(value, (list, tuple)):
            for part in value:
                result.append(_entry(part, address, resource, ordinal))
        else:
            result.append(_entry(value, address, resource, ordinal))
    return tuple(
        sorted(result, key=lambda item: (item.key, item.resource, item.ordinal, item.address))
    )


def _dedupe(
    entries: tuple[ValidationDesignClosureIndexEntry, ...],
) -> tuple[ValidationDesignClosureIndexEntry, ...]:
    seen: set[tuple[str, str, str, int]] = set()
    output: list[ValidationDesignClosureIndexEntry] = []
    for item in entries:
        identity = (item.key, item.address, item.resource, item.ordinal)
        if identity not in seen:
            seen.add(identity)
            output.append(item)
    return tuple(output)


def build_validation_design_closure_indexes(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureIndexes:
    """Build deterministic indexes over all portable closure resources."""

    rows = all_rows(bundle)
    by_artifact_id = _entries(rows["artifacts"], "artifact_id", "artifact")
    by_path = _entries(rows["artifacts"], "relative_path", "artifact")
    by_record_id = _dedupe(
        _entries(rows["records"], "record_id", "record")
        + _entries(rows["executions"], "record_id", "execution")
    )
    by_operation = _dedupe(_entries(rows["records"], "operation", "record"))
    by_check_id = _entries(rows["checks"], "check_id", "check")
    by_stage_id = _entries(rows["stages"], "stage_id", "stage")
    by_plane_id = _entries(rows["planes"], "plane_id", "plane")
    by_issue_code = _entries(rows["issues"], "issue_code", "issue")
    by_state = _dedupe(
        _entries(rows["states"], "state", "state")
        + _entries(rows["records"], "expected_state", "record")
        + _entries(rows["records"], "observed_state", "record")
    )
    counts = bundle_count_map(bundle)
    counts["index_entries"] = sum(
        len(index)
        for index in (
            by_artifact_id,
            by_path,
            by_record_id,
            by_operation,
            by_check_id,
            by_stage_id,
            by_plane_id,
            by_issue_code,
            by_state,
        )
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": by_artifact_id,
        "by_path": by_path,
        "by_record_id": by_record_id,
        "by_operation": by_operation,
        "by_check_id": by_check_id,
        "by_stage_id": by_stage_id,
        "by_plane_id": by_plane_id,
        "by_issue_code": by_issue_code,
        "by_state": by_state,
        "resource_counts": counts,
        "accepted": bundle.accepted
        and counts["artifacts"] == 27
        and counts["records"] == 16
        and counts["checks"] == 80,
    }
    return ValidationDesignClosureIndexes(
        bundle_id=bundle.bundle_id,
        by_artifact_id=by_artifact_id,
        by_path=by_path,
        by_record_id=by_record_id,
        by_operation=by_operation,
        by_check_id=by_check_id,
        by_stage_id=by_stage_id,
        by_plane_id=by_plane_id,
        by_issue_code=by_issue_code,
        by_state=by_state,
        resource_counts=counts,
        accepted=bool(body["accepted"]),
        content_address=content_hash(body, prefix="validation-design-closure-indexes"),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> Any:
    return validation_design_closure_check(
        check_id, ValidationDesignClosurePlane.INDEX, passed, observed, required, detail
    )


def audit_validation_design_closure_indexes(
    bundle: ValidationDesignBundle,
    indexes: ValidationDesignClosureIndexes | None = None,
) -> ValidationDesignClosureIndexAudit:
    """Check index completeness, addressability, uniqueness, and source counts."""

    value = indexes or build_validation_design_closure_indexes(bundle)
    checks = []
    collections = {
        "artifact-id": value.by_artifact_id,
        "path": value.by_path,
        "record-id": value.by_record_id,
        "operation": value.by_operation,
        "check-id": value.by_check_id,
        "stage-id": value.by_stage_id,
        "plane-id": value.by_plane_id,
        "issue-code": value.by_issue_code,
        "state": value.by_state,
    }
    for name, entries in collections.items():
        checks.append(
            _check(
                f"index-{name}-nonempty",
                bool(entries),
                len(entries),
                ">0",
                f"{name} index has entries",
            )
        )
        checks.append(
            _check(
                f"index-{name}-addressed",
                all(
                    str(item.address).startswith("sha256:")
                    or str(item.address).startswith("validation-design-")
                    for item in entries
                ),
                sum(
                    str(item.address).startswith("sha256:")
                    or str(item.address).startswith("validation-design-")
                    for item in entries
                ),
                len(entries),
                f"{name} index entries carry content addresses",
            )
        )
        checks.append(
            _check(
                f"index-{name}-ordinal",
                all(item.ordinal > 0 for item in entries),
                sum(item.ordinal > 0 for item in entries),
                len(entries),
                f"{name} index entries retain positive source ordinals",
            )
        )
    checks.extend(
        (
            _check(
                "index-artifacts-conserved",
                len(value.by_artifact_id) == 27,
                len(value.by_artifact_id),
                27,
                "all artifact identities are indexed",
            ),
            _check(
                "index-paths-conserved",
                len(value.by_path) == 27,
                len(value.by_path),
                27,
                "all artifact paths are indexed",
            ),
            _check(
                "index-records-conserved",
                len({item.key for item in value.by_record_id}) == 16,
                len({item.key for item in value.by_record_id}),
                16,
                "all record identities are indexed",
            ),
            _check(
                "index-operations-conserved",
                len({item.key for item in value.by_operation}) == 4,
                len({item.key for item in value.by_operation}),
                4,
                "all operation families are indexed",
            ),
            _check(
                "index-checks-conserved",
                len(value.by_check_id) == 80,
                len(value.by_check_id),
                80,
                "all evaluation checks are indexed",
            ),
            _check(
                "index-stages-conserved",
                len(value.by_stage_id) == 79,
                len(value.by_stage_id),
                79,
                "all runtime stages are indexed",
            ),
            _check(
                "index-planes-conserved",
                len(value.by_plane_id) == 57,
                len(value.by_plane_id),
                57,
                "all runtime planes are indexed",
            ),
            _check(
                "index-accepted", value.accepted, value.accepted, True, "index projection accepted"
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return ValidationDesignClosureIndexAudit(
        bundle_id=bundle.bundle_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-index-audit"),
    )


def index_lookup(
    indexes: ValidationDesignClosureIndexes, index_name: str, key: str
) -> tuple[ValidationDesignClosureIndexEntry, ...]:
    """Resolve one key through an address-only index."""

    mapping = {
        "artifact_id": indexes.by_artifact_id,
        "path": indexes.by_path,
        "record_id": indexes.by_record_id,
        "operation": indexes.by_operation,
        "check_id": indexes.by_check_id,
        "stage_id": indexes.by_stage_id,
        "plane_id": indexes.by_plane_id,
        "issue_code": indexes.by_issue_code,
        "state": indexes.by_state,
    }
    try:
        entries = mapping[index_name.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown D13 closure index: {index_name}") from exc
    return tuple(item for item in entries if item.key == key)


__all__ = [
    "audit_validation_design_closure_indexes",
    "build_validation_design_closure_indexes",
    "index_lookup",
]
