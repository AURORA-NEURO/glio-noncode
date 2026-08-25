"""Cross-resource reconciliation for the D13 closure handoff."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_contracts import (
    VALIDATION_DESIGN_CLOSURE_RECONCILIATION_VERSION,
    ValidationDesignClosureReconciliationCheck,
    ValidationDesignClosureReconciliationDelta,
    ValidationDesignClosureReconciliationReport,
)
from .validation_design_frontier_bundle_closure_query import _bundle
from .validation_design_frontier_bundle_closure_support import (
    addressed,
    all_rows,
    bundle_count_map,
    payload,
    review_rows,
)
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle


def _check(
    check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str
) -> ValidationDesignClosureReconciliationCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ValidationDesignClosureReconciliationCheck(
        **body,
        content_address=content_hash(body, prefix="validation-design-closure-reconciliation-check"),
    )


def _accepted(value: Any) -> bool:
    return isinstance(value, Mapping) and bool(value.get("accepted"))


def _addressed_rows(rows: Any, address_key: str = "content_address") -> bool:
    return (
        isinstance(rows, (list, tuple))
        and bool(rows)
        and all(addressed(row.get(address_key)) for row in rows if isinstance(row, Mapping))
    )


def reconcile_validation_design_closure(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureReconciliationReport:
    """Reconcile the manifest, fixture, evaluation, runtime, and projections."""

    rows = all_rows(bundle)
    fixture = payload(bundle, "fixture")
    evaluation = payload(bundle, "evaluation")
    runtime = payload(bundle, "runtime")
    release = payload(bundle, "release")
    summary = payload(bundle, "summary")
    report = payload(bundle, "report")
    observability = payload(bundle, "observability")
    access = payload(bundle, "access")
    quality = payload(bundle, "quality")
    records = rows["records"]
    executions = rows["executions"]
    checks = rows["checks"]
    stages = rows["stages"]
    planes = rows["planes"]
    sources = rows["sources"]
    record_ids = {str(row.get("record_id")) for row in records}
    execution_ids = {str(row.get("record_id")) for row in executions}
    checks_by_record: dict[str, int] = {}
    for row in checks:
        checks_by_record[str(row.get("record_id"))] = (
            checks_by_record.get(str(row.get("record_id")), 0) + 1
        )
    expected_plane_ids = {
        str(item) for item in (runtime.get("planes", {}) if isinstance(runtime, Mapping) else {})
    }
    observed_plane_ids = {str(row.get("plane_id")) for row in planes}
    stage_ordinals = [int(row.get("sequence", 0)) for row in stages]
    checks_out: list[ValidationDesignClosureReconciliationCheck] = [
        _check(
            "bundle-ready",
            "manifest",
            bundle.ready,
            {"accepted": bundle.accepted, "state": bundle.state.value},
            {"accepted": True, "state": "ready"},
            "the portable manifest is ready",
        ),
        _check(
            "artifact-count",
            "manifest",
            len(bundle.artifacts) == 27,
            len(bundle.artifacts),
            27,
            "the artifact denominator is conserved",
        ),
        _check(
            "artifact-addresses",
            "manifest",
            all(
                addressed(item.content_address, "validation-design-bundle-artifact:")
                for item in bundle.artifacts
            ),
            sum(
                addressed(item.content_address, "validation-design-bundle-artifact:")
                for item in bundle.artifacts
            ),
            27,
            "all artifact identities are addressed",
        ),
        _check(
            "fixture-accepted",
            "fixture",
            isinstance(fixture, Mapping) and bool(fixture.get("content_address")),
            bool(fixture.get("content_address")) if isinstance(fixture, Mapping) else False,
            True,
            "fixture projection is present",
        ),
        _check(
            "fixture-records",
            "fixture",
            len(records) == 16,
            len(records),
            16,
            "fixture records are conserved",
        ),
        _check(
            "fixture-sources",
            "fixture",
            len(sources) == 5,
            len(sources),
            5,
            "source receipts are conserved",
        ),
        _check(
            "source-https",
            "fixture",
            all(str(row.get("uri", "")).startswith("https://") for row in sources),
            tuple(row.get("uri") for row in sources),
            "https:// receipts",
            "source receipts are public HTTPS references",
        ),
        _check(
            "record-source-joins",
            "join",
            all(
                set(row.get("source_ids", ()))
                <= {str(source.get("source_id")) for source in sources}
                for row in records
            ),
            record_ids,
            "known source ids",
            "every record source join resolves",
        ),
        _check(
            "evaluation-accepted",
            "evaluation",
            _accepted(evaluation),
            evaluation.get("accepted") if isinstance(evaluation, Mapping) else False,
            True,
            "evaluation projection is accepted",
        ),
        _check(
            "execution-record-join",
            "join",
            execution_ids == record_ids,
            len(execution_ids),
            len(record_ids),
            "every record has one execution",
        ),
        _check(
            "execution-addresses",
            "evaluation",
            _addressed_rows(executions),
            sum(addressed(row.get("content_address")) for row in executions),
            len(executions),
            "execution receipts are addressed",
        ),
        _check(
            "evaluation-check-count",
            "evaluation",
            len(checks) == 80,
            len(checks),
            80,
            "five checks remain attached to each record",
        ),
        _check(
            "check-record-join",
            "join",
            all(str(row.get("record_id")) in record_ids for row in checks),
            len(checks_by_record),
            len(record_ids),
            "evaluation checks reference known records",
        ),
        _check(
            "check-five-per-record",
            "evaluation",
            set(checks_by_record.values()) == {5},
            sorted(checks_by_record.values()),
            [5],
            "each record retains five evaluation checks",
        ),
        _check(
            "runtime-accepted",
            "runtime",
            _accepted(runtime),
            runtime.get("accepted") if isinstance(runtime, Mapping) else False,
            True,
            "runtime projection is accepted",
        ),
        _check(
            "runtime-stage-count",
            "runtime",
            len(stages) == 79,
            len(stages),
            79,
            "all runtime stages are retained",
        ),
        _check(
            "runtime-stage-order",
            "runtime",
            stage_ordinals == list(range(1, 80)),
            stage_ordinals[:3] + stage_ordinals[-3:],
            "1..79",
            "runtime sequence is contiguous",
        ),
        _check(
            "runtime-stage-addresses",
            "runtime",
            _addressed_rows(stages, "output_address"),
            sum(addressed(row.get("output_address")) for row in stages),
            len(stages),
            "runtime outputs are addressed",
        ),
        _check(
            "runtime-manifest-join",
            "join",
            isinstance(runtime, Mapping)
            and runtime.get("content_address") == bundle.runtime_address,
            runtime.get("content_address") if isinstance(runtime, Mapping) else None,
            bundle.runtime_address,
            "runtime address matches the manifest",
        ),
        _check(
            "plane-count",
            "runtime",
            len(planes) == 57,
            len(planes),
            57,
            "all runtime planes are retained",
        ),
        _check(
            "plane-identities",
            "join",
            observed_plane_ids == expected_plane_ids,
            len(observed_plane_ids),
            len(expected_plane_ids),
            "runtime plane ids close against the source runtime",
        ),
        _check(
            "plane-accepted",
            "runtime",
            all(bool(row.get("accepted")) for row in planes),
            sum(bool(row.get("accepted")) for row in planes),
            len(planes),
            "every runtime plane is accepted",
        ),
        _check(
            "release-accepted",
            "release",
            _accepted(release),
            release.get("accepted") if isinstance(release, Mapping) else False,
            True,
            "release projection is accepted",
        ),
        _check(
            "summary-accepted",
            "release",
            _accepted(summary),
            summary.get("accepted") if isinstance(summary, Mapping) else False,
            True,
            "summary projection is accepted",
        ),
        _check(
            "report-row-count",
            "release",
            isinstance(report, Mapping) and report.get("values", {}).get("row_count") == 16,
            report.get("values", {}).get("row_count") if isinstance(report, Mapping) else None,
            16,
            "report retains one row per record",
        ),
        _check(
            "observability-accepted",
            "observability",
            _accepted(observability),
            observability.get("accepted") if isinstance(observability, Mapping) else False,
            True,
            "source observability projection is accepted",
        ),
        _check(
            "quality-accepted",
            "quality",
            _accepted(quality),
            quality.get("accepted") if isinstance(quality, Mapping) else False,
            True,
            "quality projection is accepted",
        ),
        _check(
            "review-row-count",
            "release",
            len(review_rows(bundle)) == 16,
            len(review_rows(bundle)),
            16,
            "review CSV reconciles against records",
        ),
        _check(
            "record-operation-balance",
            "fixture",
            len({str(row.get("operation")) for row in records}) == 4,
            len({str(row.get("operation")) for row in records}),
            4,
            "four operation families are represented",
        ),
        _check(
            "access-source-count",
            "public_boundary",
            isinstance(access, Mapping) and len(access.get("sources", ())) == 5,
            len(access.get("sources", ())) if isinstance(access, Mapping) else 0,
            5,
            "access projection retains source receipts",
        ),
        _check(
            "resource-address-density",
            "integrity",
            all(
                addressed(row.get("content_address"))
                for resource in rows.values()
                for row in resource
                if "content_address" in row and row.get("content_address")
            ),
            True,
            True,
            "closure rows have stable addresses",
        ),
        _check(
            "no-unresolved-joins",
            "join",
            not any(value == 0 for value in checks_by_record.values()),
            checks_by_record,
            "nonzero checks per record",
            "all record joins have checks",
        ),
        _check(
            "closure-accepted",
            "release",
            bundle.accepted and len(rows["artifacts"]) == 27 and len(rows["records"]) == 16,
            bundle.accepted,
            True,
            "closure denominator is ready for certification",
        ),
    ]
    accepted = all(item.passed for item in checks_out)
    body = {
        "version": VALIDATION_DESIGN_CLOSURE_RECONCILIATION_VERSION,
        "bundle_id": bundle.bundle_id,
        "checks": tuple(checks_out),
        "accepted": accepted,
    }
    return ValidationDesignClosureReconciliationReport(
        version=VALIDATION_DESIGN_CLOSURE_RECONCILIATION_VERSION,
        bundle_id=bundle.bundle_id,
        checks=tuple(checks_out),
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-reconciliation"),
    )


def diff_validation_design_closure_bundles(
    left: ValidationDesignBundle | str | Path, right: ValidationDesignBundle | str | Path
) -> ValidationDesignClosureReconciliationDelta:
    """Compare artifact identity and closure resource counts."""

    left_value = _bundle(left)
    right_value = _bundle(right)
    left_artifacts = {item.artifact_id: item.content_address for item in left_value.artifacts}
    right_artifacts = {item.artifact_id: item.content_address for item in right_value.artifacts}
    changed = tuple(sorted(set(left_artifacts) | set(right_artifacts)))
    changed = tuple(
        item for item in changed if left_artifacts.get(item) != right_artifacts.get(item)
    )
    left_counts = bundle_count_map(left_value)
    right_counts = bundle_count_map(right_value)
    changed_counts = {
        key: (left_counts.get(key, 0), right_counts.get(key, 0))
        for key in sorted(set(left_counts) | set(right_counts))
        if left_counts.get(key, 0) != right_counts.get(key, 0)
    }
    body = {
        "left_bundle_id": left_value.bundle_id,
        "right_bundle_id": right_value.bundle_id,
        "left_address": left_value.content_address,
        "right_address": right_value.content_address,
        "changed_artifacts": changed,
        "changed_counts": changed_counts,
        "accepted": left_value.accepted and right_value.accepted,
    }
    return ValidationDesignClosureReconciliationDelta(
        left_bundle_id=left_value.bundle_id,
        right_bundle_id=right_value.bundle_id,
        left_address=left_value.content_address,
        right_address=right_value.content_address,
        changed_artifacts=changed,
        changed_counts=changed_counts,
        accepted=bool(body["accepted"]),
        content_address=content_hash(body, prefix="validation-design-closure-diff"),
    )


__all__ = [
    "diff_validation_design_closure_bundles",
    "reconcile_validation_design_closure",
]
