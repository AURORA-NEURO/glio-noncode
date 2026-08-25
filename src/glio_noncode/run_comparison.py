"""Replay-gated dossier history and semantic run comparison projections.

The persisted run pointer always identifies the latest dossier.  This module
keeps the immutable addresses of earlier dossier snapshots visible and offers a
bounded comparison plane for review transitions, evidence changes, and
validation-route changes.  Every projection is deterministic and remains
research-use-only; it describes differences without making a clinical claim.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .errors import StoreError, ValidationError
from .models import Dossier
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash

RUN_HISTORY_VERSION = "run-history-v1"
RUN_HISTORY_MAX_SNAPSHOTS = 1_000
DOSSIER_COMPARISON_VERSION = "dossier-comparison-v1"
DOSSIER_COMPARISON_MAX_CHANGES = 5_000


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    """Integrity and summary metadata for one immutable dossier snapshot."""

    index: int
    dossier_address: str
    is_current: bool
    exists: bool
    address_valid: bool
    identity_valid: bool
    run_id: str
    case_id: str
    dossier_id: str
    created_at: str
    event_head: str
    status: str
    review_state: str | None
    hypothesis_count: int
    evidence_count: int
    experiment_count: int
    warning_count: int
    warnings: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return (
            self.exists
            and self.address_valid
            and self.identity_valid
            and bool(self.run_id)
            and self.run_id != "unknown"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "dossier_address": self.dossier_address,
            "is_current": self.is_current,
            "exists": self.exists,
            "address_valid": self.address_valid,
            "identity_valid": self.identity_valid,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "dossier_id": self.dossier_id,
            "created_at": self.created_at,
            "event_head": self.event_head,
            "status": self.status,
            "review_state": self.review_state,
            "hypothesis_count": self.hypothesis_count,
            "evidence_count": self.evidence_count,
            "experiment_count": self.experiment_count,
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class RunHistory:
    """Addressed snapshot history for one run and its integrity closure."""

    run_id: str
    case_id: str
    current_dossier_address: str
    current_snapshot_index: int
    snapshots: tuple[RunSnapshot, ...]
    replay_accepted: bool
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    @property
    def snapshot_count(self) -> int:
        return len(self.snapshots)

    def to_dict(self) -> dict[str, Any]:
        return {
            "history_version": RUN_HISTORY_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "current_dossier_address": self.current_dossier_address,
            "current_snapshot_index": self.current_snapshot_index,
            "snapshot_count": self.snapshot_count,
            "snapshots": [item.to_dict() for item in self.snapshots],
            "replay_accepted": self.replay_accepted,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ComparisonCheck:
    """One explicit comparison precondition or completeness observation."""

    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ComparisonChange:
    """One added, removed, or field-level changed public record."""

    change_type: str
    key: str
    changed_fields: tuple[str, ...]
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    before_address: str | None
    after_address: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type,
            "key": self.key,
            "changed_fields": list(self.changed_fields),
            "before": self.before,
            "after": self.after,
            "before_address": self.before_address,
            "after_address": self.after_address,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class ComparisonDimension:
    """Bounded diff for one dossier plane."""

    name: str
    source_count: int
    target_count: int
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    truncated: bool
    changes: tuple[ComparisonChange, ...]
    content_address: str

    @property
    def change_count(self) -> int:
        return self.added_count + self.removed_count + self.changed_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_count": self.source_count,
            "target_count": self.target_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "change_count": self.change_count,
            "truncated": self.truncated,
            "changes": [item.to_dict() for item in self.changes],
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class DossierComparison:
    """Complete semantic comparison with integrity and public-boundary checks."""

    source_run_id: str
    target_run_id: str
    source_snapshot_index: int | None
    target_snapshot_index: int | None
    source_dossier_address: str
    target_dossier_address: str
    source_case_id: str
    target_case_id: str
    source_status: str
    target_status: str
    same_case: bool
    checks: tuple[ComparisonCheck, ...]
    metadata: ComparisonDimension
    dimensions: tuple[ComparisonDimension, ...]
    summary: dict[str, Any]
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def changed(self) -> bool:
        return bool(self.metadata.change_count or any(item.change_count for item in self.dimensions))

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_version": DOSSIER_COMPARISON_VERSION,
            "source_run_id": self.source_run_id,
            "target_run_id": self.target_run_id,
            "source_snapshot_index": self.source_snapshot_index,
            "target_snapshot_index": self.target_snapshot_index,
            "source_dossier_address": self.source_dossier_address,
            "target_dossier_address": self.target_dossier_address,
            "source_case_id": self.source_case_id,
            "target_case_id": self.target_case_id,
            "source_status": self.source_status,
            "target_status": self.target_status,
            "same_case": self.same_case,
            "changed": self.changed,
            "checks": [item.to_dict() for item in self.checks],
            "failed_check_ids": list(self.failed_check_ids),
            "metadata": self.metadata.to_dict(),
            "dimensions": {item.name: item.to_dict() for item in self.dimensions},
            "summary": self.summary,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> ComparisonCheck:
    body = {
        "check_id": check_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ComparisonCheck(**body, content_address=content_hash(body, prefix="comparison-check"))


def _snapshot_rows(raw: dict[str, Any], field: str) -> tuple[dict[str, Any], ...]:
    values = raw.get(field, ())
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(dict(item) for item in values if isinstance(item, dict))


def _review_state(raw: dict[str, Any]) -> str | None:
    review = raw.get("review")
    return str(review.get("state")) if isinstance(review, dict) and review.get("state") else None


def _snapshot_from_record(
    index: int,
    address: str,
    raw: dict[str, Any] | None,
    *,
    current_address: str,
    expected_run_id: str,
    expected_case_id: str,
    warnings: list[str],
) -> RunSnapshot:
    if raw is None:
        warnings.append(f"snapshot {index} is missing: {address}")
        body = {
            "index": index,
            "dossier_address": address,
            "is_current": address == current_address,
            "exists": False,
            "address_valid": False,
            "identity_valid": False,
            "run_id": "unknown",
            "case_id": "",
            "dossier_id": "",
            "created_at": "",
            "event_head": "",
            "status": "",
            "review_state": None,
            "hypothesis_count": 0,
            "evidence_count": 0,
            "experiment_count": 0,
            "warning_count": 0,
            "warnings": ("stored dossier object is missing",),
        }
        return RunSnapshot(
            **body,
            content_address=content_hash(body, prefix="run-snapshot"),
        )

    payload = {key: value for key, value in raw.items() if key != "content_address"}
    address_valid = content_hash(payload) == raw.get("content_address") == address
    run_id = str(raw.get("run_id", "unknown"))
    case_id = str(raw.get("case_id", ""))
    identity_valid = run_id == expected_run_id and case_id == expected_case_id
    if not identity_valid:
        warnings.append(f"snapshot {index} identity does not match run: {address}")
    try:
        Dossier.from_dict(raw)
    except (KeyError, TypeError, ValueError):
        address_valid = False
        warnings.append(f"snapshot {index} cannot be rehydrated: {address}")
    if not address_valid:
        warnings.append(f"snapshot {index} content address mismatch: {address}")
    dossier_warnings = tuple(str(item) for item in raw.get("warnings", ()))
    body = {
        "index": index,
        "dossier_address": address,
        "is_current": address == current_address,
        "exists": True,
        "address_valid": address_valid,
        "identity_valid": identity_valid,
        "run_id": run_id,
        "case_id": case_id,
        "dossier_id": str(raw.get("dossier_id", "")),
        "created_at": str(raw.get("created_at", "")),
        "event_head": str(raw.get("event_head", "")),
        "status": str(raw.get("status", "")),
        "review_state": _review_state(raw),
        "hypothesis_count": len(raw.get("hypotheses", ())),
        "evidence_count": len(raw.get("evidence", ())),
        "experiment_count": len(raw.get("experiments", ())),
        "warning_count": len(dossier_warnings),
        "warnings": dossier_warnings,
    }
    return RunSnapshot(**body, content_address=content_hash(body, prefix="run-snapshot"))


def build_run_history(runtime: CaseRuntime, run_id: str) -> RunHistory:
    """Load every indexed dossier snapshot and verify each immutable address."""

    run_record = runtime.get_run(run_id)
    inspection = inspect_run(runtime, run_id)
    current_address = str(run_record.get("dossier_address", ""))
    raw_history = run_record.get("dossier_history")
    if raw_history is None:
        addresses = [current_address]
    elif isinstance(raw_history, (list, tuple)):
        addresses = [str(item) for item in raw_history if str(item)]
    else:
        raise ValidationError("dossier_history must be an array")
    if current_address and current_address not in addresses:
        addresses.append(current_address)
    if not addresses:
        raise ValidationError("run does not identify a dossier snapshot")
    if len(addresses) > RUN_HISTORY_MAX_SNAPSHOTS:
        raise ValidationError(f"run history exceeds {RUN_HISTORY_MAX_SNAPSHOTS} snapshots")

    warnings = list(inspection.replay.warnings)
    unique_history = len(set(addresses)) == len(addresses)
    if not unique_history:
        warnings.append("dossier history contains duplicate snapshot addresses")
    expected_run_id = str(run_record.get("run_id", run_id))
    expected_case_id = str(inspection.dossier_record.get("case_id", ""))
    snapshots: list[RunSnapshot] = []
    for index, address in enumerate(addresses):
        try:
            stored = runtime.store.store.get(address)
        except StoreError:
            stored = None
        snapshots.append(
            _snapshot_from_record(
                index,
                address,
                stored if isinstance(stored, dict) else None,
                current_address=current_address,
                expected_run_id=expected_run_id,
                expected_case_id=expected_case_id,
                warnings=warnings,
            )
        )
    current_indices = [item.index for item in snapshots if item.dossier_address == current_address]
    current_index = current_indices[-1] if current_indices else len(snapshots) - 1
    accepted = inspection.accepted and unique_history and all(item.accepted for item in snapshots)
    body = {
        "run_id": str(run_record.get("run_id", run_id)),
        "case_id": str(inspection.dossier_record.get("case_id", "")),
        "current_dossier_address": current_address,
        "current_snapshot_index": current_index,
        "snapshots": tuple(snapshots),
        "replay_accepted": inspection.accepted,
        "accepted": accepted,
        "warnings": tuple(dict.fromkeys(warnings)),
    }
    return RunHistory(
        **body,
        content_address=content_hash(body, prefix="run-history"),
    )


def _selected_snapshot(history: RunHistory, index: int | None) -> RunSnapshot:
    selected_index = history.current_snapshot_index if index is None else index
    if selected_index < 0 or selected_index >= len(history.snapshots):
        raise ValueError(f"snapshot index must be between 0 and {len(history.snapshots) - 1}")
    selected = history.snapshots[selected_index]
    if not selected.accepted:
        raise ValidationError(f"snapshot {selected_index} fails content-address verification")
    return selected


def _load_snapshot(runtime: CaseRuntime, snapshot: RunSnapshot) -> Dossier:
    raw = runtime.store.store.get(snapshot.dossier_address)
    if not isinstance(raw, dict):
        raise ValidationError("stored dossier snapshot must be an object")
    dossier = Dossier.from_dict(raw)
    if dossier.content_address != snapshot.dossier_address:
        raise ValidationError("stored dossier snapshot address changed during load")
    return dossier


def _semantic_metadata(dossier: Dossier) -> dict[str, Any]:
    return {
        "status": dossier.status.value,
        "research_use_only": dossier.research_use_only,
        "policy_version": dossier.policy_version,
        "warnings": list(dossier.warnings),
        "review": dossier.review.to_dict() if dossier.review is not None else None,
        "source_receipt_count": len(dossier.source_receipts),
        "source_bundle_addresses": list(dossier.source_bundle_addresses),
    }


def _row_key(dimension: str, row: dict[str, Any]) -> str:
    if dimension == "hypotheses":
        return "variant={};element={};gene={};state={}".format(
            row.get("variant_id", ""),
            row.get("element_id", ""),
            row.get("gene_id", ""),
            row.get("state_id", ""),
        )
    if dimension == "evidence":
        return str(row.get("evidence_id") or canonical_json({
            "edge_id": row.get("edge_id", ""),
            "source_id": row.get("source_id", ""),
            "channel": row.get("channel", ""),
        }))
    if dimension == "experiments":
        return str(row.get("option_id") or canonical_json({
            "assay": row.get("assay", ""),
            "tests_edges": row.get("tests_edges", ()),
        }))
    return str(row.get("field", ""))


def _index_rows(dimension: str, rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[_row_key(dimension, row)].append(row)
    indexed: dict[str, dict[str, Any]] = {}
    for base_key in sorted(grouped):
        values = grouped[base_key]
        for ordinal, row in enumerate(values, start=1):
            key = base_key if len(values) == 1 else f"{base_key}#duplicate-{ordinal}"
            indexed[key] = row
    return indexed


def _row_address(dimension: str, row: dict[str, Any] | None) -> str | None:
    if row is None:
        return None
    return content_hash(row, prefix=f"comparison-{dimension}-row")


def _make_change(
    change_type: str,
    key: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    *,
    dimension: str,
) -> ComparisonChange:
    before_fields = set(before or {})
    after_fields = set(after or {})
    changed_fields = tuple(
        sorted(
            field
            for field in before_fields | after_fields
            if (before or {}).get(field) != (after or {}).get(field)
        )
    )
    body = {
        "change_type": change_type,
        "key": key,
        "changed_fields": changed_fields,
        "before": before,
        "after": after,
        "before_address": _row_address(dimension, before),
        "after_address": _row_address(dimension, after),
    }
    return ComparisonChange(
        **body,
        content_address=content_hash(body, prefix="comparison-change"),
    )


def _build_dimension(
    name: str,
    source_rows: tuple[dict[str, Any], ...],
    target_rows: tuple[dict[str, Any], ...],
    *,
    change_limit: int,
) -> ComparisonDimension:
    source = _index_rows(name, source_rows)
    target = _index_rows(name, target_rows)
    changes: list[ComparisonChange] = []
    added_count = removed_count = changed_count = unchanged_count = 0
    for key in sorted(set(source) | set(target)):
        before = source.get(key)
        after = target.get(key)
        if before is None:
            change_type = "added"
            added_count += 1
        elif after is None:
            change_type = "removed"
            removed_count += 1
        elif canonical_json(before) != canonical_json(after):
            change_type = "changed"
            changed_count += 1
        else:
            unchanged_count += 1
            continue
        if len(changes) < change_limit:
            changes.append(_make_change(change_type, key, before, after, dimension=name))
    truncated = len(changes) < added_count + removed_count + changed_count
    body = {
        "name": name,
        "source_count": len(source_rows),
        "target_count": len(target_rows),
        "added_count": added_count,
        "removed_count": removed_count,
        "changed_count": changed_count,
        "unchanged_count": unchanged_count,
        "truncated": truncated,
        "changes": tuple(changes),
    }
    return ComparisonDimension(**body, content_address=content_hash(body, prefix="comparison-dimension"))


def _build_metadata_dimension(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    change_limit: int,
) -> ComparisonDimension:
    fields = tuple(sorted(set(source) | set(target)))
    changed_fields = tuple(field for field in fields if source.get(field) != target.get(field))
    changes: list[ComparisonChange] = []
    for field in changed_fields:
        before = {"field": field, "value": source.get(field)}
        after = {"field": field, "value": target.get(field)}
        if len(changes) < change_limit:
            changes.append(_make_change("changed", field, before, after, dimension="metadata"))
    body = {
        "name": "metadata",
        "source_count": len(source),
        "target_count": len(target),
        "added_count": 0,
        "removed_count": 0,
        "changed_count": len(changed_fields),
        "unchanged_count": len(fields) - len(changed_fields),
        "truncated": len(changes) < len(changed_fields),
        "changes": tuple(changes),
    }
    return ComparisonDimension(**body, content_address=content_hash(body, prefix="comparison-dimension"))


def build_dossier_comparison(
    source_dossier: Dossier,
    target_dossier: Dossier,
    *,
    source_run_id: str | None = None,
    target_run_id: str | None = None,
    source_snapshot_index: int | None = None,
    target_snapshot_index: int | None = None,
    source_integrity: bool = True,
    target_integrity: bool = True,
    change_limit: int = DOSSIER_COMPARISON_MAX_CHANGES,
) -> DossierComparison:
    """Compare two typed dossiers without requiring persisted storage."""

    if change_limit < 1 or change_limit > DOSSIER_COMPARISON_MAX_CHANGES:
        raise ValueError(f"change_limit must be between 1 and {DOSSIER_COMPARISON_MAX_CHANGES}")
    source_id = source_run_id or source_dossier.run_id
    target_id = target_run_id or target_dossier.run_id
    source_rows = source_dossier.to_dict()
    target_rows = target_dossier.to_dict()
    metadata = _build_metadata_dimension(
        _semantic_metadata(source_dossier),
        _semantic_metadata(target_dossier),
        change_limit=change_limit,
    )
    dimensions = tuple(
        _build_dimension(
            name,
            _snapshot_rows(source_rows, name),
            _snapshot_rows(target_rows, name),
            change_limit=change_limit,
        )
        for name in ("hypotheses", "evidence", "experiments")
    )
    same_case = source_dossier.case_id == target_dossier.case_id
    warnings: list[str] = []
    if not same_case:
        warnings.append("source and target dossiers belong to different cases")
    if not source_integrity:
        warnings.append("source run failed replay integrity")
    if not target_integrity:
        warnings.append("target run failed replay integrity")
    all_dimensions = (metadata,) + dimensions
    complete = not any(item.truncated for item in all_dimensions)
    checks = (
        _check("source-integrity", source_integrity, source_integrity, True, "source dossier passed replay verification"),
        _check("target-integrity", target_integrity, target_integrity, True, "target dossier passed replay verification"),
        _check("same-case", same_case, {"source": source_dossier.case_id, "target": target_dossier.case_id}, True, "comparison requires one case identity"),
        _check("comparison-complete", complete, complete, True, "all semantic changes fit within the bounded comparison projection"),
    )
    public_body = {
        "source_run_id": source_id,
        "target_run_id": target_id,
        "source_case_id": source_dossier.case_id,
        "target_case_id": target_dossier.case_id,
        "metadata": metadata.to_dict(),
        "dimensions": [item.to_dict() for item in dimensions],
        "warnings": tuple(warnings),
    }
    boundary_check = _check(
        "public-boundary",
        not contains_private_key(public_body),
        not contains_private_key(public_body),
        True,
        "comparison projection contains no private projection key",
    )
    checks += (boundary_check,)
    accepted = all(item.passed for item in checks)
    summary = {
        "metadata_change_count": metadata.change_count,
        "hypothesis_added_count": dimensions[0].added_count,
        "hypothesis_removed_count": dimensions[0].removed_count,
        "hypothesis_changed_count": dimensions[0].changed_count,
        "evidence_added_count": dimensions[1].added_count,
        "evidence_removed_count": dimensions[1].removed_count,
        "evidence_changed_count": dimensions[1].changed_count,
        "experiment_added_count": dimensions[2].added_count,
        "experiment_removed_count": dimensions[2].removed_count,
        "experiment_changed_count": dimensions[2].changed_count,
        "changed": bool(metadata.change_count or any(item.change_count for item in dimensions)),
        "complete": complete,
    }
    body = {
        "comparison_version": DOSSIER_COMPARISON_VERSION,
        "source_run_id": source_id,
        "target_run_id": target_id,
        "source_snapshot_index": source_snapshot_index,
        "target_snapshot_index": target_snapshot_index,
        "source_dossier_address": source_dossier.content_address,
        "target_dossier_address": target_dossier.content_address,
        "source_case_id": source_dossier.case_id,
        "target_case_id": target_dossier.case_id,
        "source_status": source_dossier.status.value,
        "target_status": target_dossier.status.value,
        "same_case": same_case,
        "checks": [item.to_dict() for item in checks],
        "metadata": metadata.to_dict(),
        "dimensions": [item.to_dict() for item in dimensions],
        "summary": summary,
        "warnings": tuple(warnings),
        "accepted": accepted,
    }
    return DossierComparison(
        source_run_id=source_id,
        target_run_id=target_id,
        source_snapshot_index=source_snapshot_index,
        target_snapshot_index=target_snapshot_index,
        source_dossier_address=source_dossier.content_address,
        target_dossier_address=target_dossier.content_address,
        source_case_id=source_dossier.case_id,
        target_case_id=target_dossier.case_id,
        source_status=source_dossier.status.value,
        target_status=target_dossier.status.value,
        same_case=same_case,
        checks=checks,
        metadata=metadata,
        dimensions=dimensions,
        summary=summary,
        warnings=tuple(warnings),
        accepted=accepted,
        content_address=content_hash(body, prefix="dossier-comparison"),
    )


def compare_persisted_runs(
    runtime: CaseRuntime,
    source_run_id: str,
    target_run_id: str,
    *,
    source_snapshot: int | None = None,
    target_snapshot: int | None = None,
    change_limit: int = DOSSIER_COMPARISON_MAX_CHANGES,
) -> DossierComparison:
    """Compare replay-verified current or historical snapshots from two runs."""

    source_history = build_run_history(runtime, source_run_id)
    target_history = source_history if source_run_id == target_run_id else build_run_history(runtime, target_run_id)
    source_selected = _selected_snapshot(source_history, source_snapshot)
    target_selected = _selected_snapshot(target_history, target_snapshot)
    source_dossier = _load_snapshot(runtime, source_selected)
    target_dossier = _load_snapshot(runtime, target_selected)
    return build_dossier_comparison(
        source_dossier,
        target_dossier,
        source_run_id=source_run_id,
        target_run_id=target_run_id,
        source_snapshot_index=source_selected.index,
        target_snapshot_index=target_selected.index,
        source_integrity=source_history.accepted,
        target_integrity=target_history.accepted,
        change_limit=change_limit,
    )


def compare_run_snapshots(
    runtime: CaseRuntime,
    run_id: str,
    source_snapshot: int,
    target_snapshot: int,
    *,
    change_limit: int = DOSSIER_COMPARISON_MAX_CHANGES,
) -> DossierComparison:
    """Compare two explicitly selected snapshots from one run."""

    return compare_persisted_runs(
        runtime,
        run_id,
        run_id,
        source_snapshot=source_snapshot,
        target_snapshot=target_snapshot,
        change_limit=change_limit,
    )


__all__ = [
    "DOSSIER_COMPARISON_MAX_CHANGES",
    "DOSSIER_COMPARISON_VERSION",
    "RUN_HISTORY_MAX_SNAPSHOTS",
    "RUN_HISTORY_VERSION",
    "ComparisonChange",
    "ComparisonCheck",
    "ComparisonDimension",
    "DossierComparison",
    "RunHistory",
    "RunSnapshot",
    "build_dossier_comparison",
    "build_run_history",
    "compare_persisted_runs",
    "compare_run_snapshots",
]
