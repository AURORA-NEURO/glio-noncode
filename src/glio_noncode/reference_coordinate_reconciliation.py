"""Cross-view reconciliation for Domain 04 coordinate evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_coordinate_bundle import (
    ReferenceCoordinateBundleBuilder,
    ReferenceCoordinateEvidenceBundle,
)
from .reference_coordinate_fixture_eval import (
    ReferenceCoordinateEvaluationReport,
    evaluate_reference_coordinate_fixture,
)
from .reference_coordinate_lineage import build_reference_coordinate_lineage
from .reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateReconciliationCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateReconciliationReport:
    fixture_id: str
    state: str
    checks: tuple[ReferenceCoordinateReconciliationCheck, ...]
    evaluation_address: str
    bundle_address: str
    lineage_address: str
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
            "check_count": len(self.checks),
        }


def reconcile_reference_coordinate_views(
    catalog: ReferenceCoordinateFixtureCatalog,
    *,
    evaluation: ReferenceCoordinateEvaluationReport | None = None,
    bundle: ReferenceCoordinateEvidenceBundle | None = None,
) -> ReferenceCoordinateReconciliationReport:
    """Compare data, evaluation, bundle, and lineage views without mutating them."""

    evaluation = evaluation or evaluate_reference_coordinate_fixture(catalog)
    bundle = bundle or ReferenceCoordinateBundleBuilder().build(catalog)
    lineage = build_reference_coordinate_lineage(catalog)
    checks: list[ReferenceCoordinateReconciliationCheck] = []

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            ReferenceCoordinateReconciliationCheck(
                check_id, bool(passed), observed, expected, message
            )
        )

    records_by_id = {record.record_id: record for record in catalog.records}
    receipts_by_id = {receipt.record_id: receipt for receipt in evaluation.receipts}
    entries_by_id = {entry.record_id: entry for entry in bundle.entries}
    add(
        "evaluation-accepted",
        evaluation.passed,
        evaluation.state,
        "accepted",
        "evaluation is accepted",
    )
    add(
        "evaluation-receipt-count",
        len(evaluation.receipts) == len(catalog.records),
        len(evaluation.receipts),
        len(catalog.records),
        "evaluation receipt count is conserved",
    )
    add(
        "evaluation-identity",
        len(receipts_by_id) == len(evaluation.receipts),
        len(receipts_by_id),
        len(evaluation.receipts),
        "evaluation receipt IDs are unique",
    )
    add(
        "evaluation-context",
        all(receipt.context_key == catalog.context_key for receipt in evaluation.receipts),
        True,
        True,
        "evaluation context matches",
    )
    add(
        "evaluation-sources",
        all(
            set(receipt.source_ids).issubset(set(catalog.source_ids))
            for receipt in evaluation.receipts
        ),
        True,
        True,
        "evaluation sources are declared",
    )
    add(
        "evaluation-operations",
        {receipt.operation.value for receipt in evaluation.receipts} == set(catalog.operation_ids),
        tuple(sorted({receipt.operation.value for receipt in evaluation.receipts})),
        catalog.operation_ids,
        "all operation receipts are present",
    )
    add(
        "evaluation-states",
        all(
            receipts_by_id[record.record_id].state == record.expected_state
            for record in catalog.records
        ),
        True,
        True,
        "evaluation states match records",
    )
    add(
        "evaluation-issues",
        all(
            receipts_by_id[record.record_id].issue_codes == record.expected_issue_codes
            for record in catalog.records
        ),
        True,
        True,
        "evaluation issue codes match records",
    )
    add(
        "record-addresses",
        all(
            entries_by_id.get(record.record_id, None) is None
            or entries_by_id[record.record_id].record_address == record.content_address
            for record in catalog.records
        ),
        True,
        True,
        "bundle entries retain record addresses",
    )
    add(
        "bundle-membership",
        set(entries_by_id).issubset(set(records_by_id)),
        tuple(sorted(entries_by_id)),
        "fixture record IDs",
        "bundle entries belong to fixture",
    )
    add(
        "bundle-context",
        all(entry.context_key == catalog.context_key for entry in bundle.entries),
        True,
        True,
        "bundle context matches",
    )
    add(
        "bundle-receipts",
        all(
            entry.receipt_address == receipts_by_id[entry.record_id].content_address
            for entry in bundle.entries
        ),
        True,
        True,
        "bundle receipt addresses match evaluation",
    )
    add(
        "bundle-address",
        bundle.content_address.startswith("sha256:"),
        bundle.content_address,
        "sha256:<address>",
        "bundle is addressed",
    )
    add(
        "bundle-sanitized",
        "chain_text" not in str(bundle.to_dict()).lower(),
        True,
        True,
        "bundle has no raw chain payload",
    )
    lineage_audit = lineage.audit(catalog)
    add(
        "lineage-accepted",
        lineage_audit.passed,
        lineage_audit.state,
        "accepted",
        "lineage audit is accepted",
    )
    add(
        "lineage-node-count",
        len(lineage.nodes) == len(catalog.source_receipts) + 1 + 2 * len(catalog.records),
        len(lineage.nodes),
        len(catalog.source_receipts) + 1 + 2 * len(catalog.records),
        "lineage node count is conserved",
    )
    add(
        "lineage-edge-count",
        len(lineage.edges) == len(catalog.source_receipts) + 2 * len(catalog.records),
        len(lineage.edges),
        len(catalog.source_receipts) + 2 * len(catalog.records),
        "lineage edge count is conserved",
    )
    add(
        "lineage-context",
        lineage.context_key == catalog.context_key,
        lineage.context_key,
        catalog.context_key,
        "lineage context matches",
    )
    add(
        "lineage-address",
        lineage.content_address.startswith("sha256:"),
        lineage.content_address,
        "sha256:<address>",
        "lineage is addressed",
    )
    add(
        "positive-publishing",
        all(entry.state == "supported" for entry in bundle.entries if entry.role == "positive"),
        True,
        True,
        "positive entries remain supported",
    )
    add(
        "control-review",
        all(entry.state != "supported" for entry in bundle.entries if entry.role == "control"),
        True,
        True,
        "control entries remain reviewable",
    )
    add(
        "raw-record-boundary",
        all("payload" not in str(record.payload).lower() for record in catalog.records),
        True,
        True,
        "raw payload is confined to the input catalog",
    )
    add(
        "source-set",
        set(catalog.source_ids) == {source.source_id for source in catalog.source_receipts},
        catalog.source_ids,
        "declared source IDs",
        "source set is closed",
    )
    add(
        "address-chain",
        all(receipt.content_address.startswith("sha256:") for receipt in evaluation.receipts)
        and bundle.content_address.startswith("sha256:")
        and lineage.content_address.startswith("sha256:"),
        True,
        True,
        "all cross-view artifacts are addressed",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {
        "fixture_id": catalog.fixture_id,
        "state": state,
        "checks": checks,
        "evaluation_address": evaluation.content_address,
        "bundle_address": bundle.content_address,
        "lineage_address": lineage.content_address,
    }
    return ReferenceCoordinateReconciliationReport(
        fixture_id=catalog.fixture_id,
        state=state,
        checks=tuple(checks),
        evaluation_address=evaluation.content_address,
        bundle_address=bundle.content_address,
        lineage_address=lineage.content_address,
        content_address=content_hash(body),
    )


__all__ = [
    "ReferenceCoordinateReconciliationCheck",
    "ReferenceCoordinateReconciliationReport",
    "reconcile_reference_coordinate_views",
]
