"""Cross-view reconciliation for annotation evaluation, bundle, and lineage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .reference_annotation_bundle import ReferenceAnnotationBundle
from .reference_annotation_fixture_eval import ReferenceAnnotationEvaluationReport
from .reference_annotation_lineage import ReferenceAnnotationLineageGraph
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    ReferenceAnnotationRole,
    default_reference_annotation_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReconciliationCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReconciliationReport:
    fixture_id: str
    context_key: str
    checks: tuple[ReferenceAnnotationReconciliationCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def reconcile_reference_annotation_views(
    report: ReferenceAnnotationEvaluationReport,
    bundle: ReferenceAnnotationBundle,
    lineage: ReferenceAnnotationLineageGraph,
    *,
    fixture: ReferenceAnnotationFixture | None = None,
) -> ReferenceAnnotationReconciliationReport:
    selected = fixture or default_reference_annotation_fixture()
    checks: list[ReferenceAnnotationReconciliationCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(
            ReferenceAnnotationReconciliationCheck(check_id, passed, detail, _address(body))
        )

    eval_ids = {receipt.record_id for receipt in report.receipts}
    bundle_ids = {entry.record_id for entry in bundle.entries}
    lineage_record_ids = {node.node_id for node in lineage.nodes if node.kind.value == "record"}
    lineage_result_ids = {
        node.node_id.removeprefix("result:")
        for node in lineage.nodes
        if node.kind.value == "result"
    }
    add(
        "fixture-id",
        report.fixture_id == selected.fixture_id == bundle.fixture_id,
        "all views name the same fixture",
    )
    add(
        "fixture-version",
        report.fixture_version == selected.fixture_version == bundle.fixture_version,
        "all views retain the same fixture version",
    )
    add(
        "context-key",
        report.context_key == bundle.context_key == lineage.context_key == selected.context_key,
        "all views retain exact context",
    )
    add("evaluation-accepted", report.accepted, "evaluation report is accepted")
    add("lineage-accepted", lineage.audit.accepted, "lineage audit is accepted")
    add(
        "record-closure",
        eval_ids == {record.record_id for record in selected.records} == lineage_record_ids,
        "evaluation, fixture, and lineage record sets agree",
    )
    add(
        "result-closure",
        eval_ids == lineage_result_ids,
        "every evaluation receipt has one lineage result",
    )
    add(
        "bundle-accepted-state",
        bundle.published is False or all(entry.state == "supported" for entry in bundle.entries),
        "published mode cannot contain review entries",
    )
    add("bundle-record-subset", bundle_ids <= eval_ids, "bundle entries are evaluation receipts")
    add(
        "bundle-source-closure",
        all(
            set(entry.source_ids) <= {source.source_id for source in selected.sources}
            for entry in bundle.entries
        ),
        "bundle source IDs close over fixture sources",
    )
    add(
        "positive-state",
        all(
            receipt.resolution_state == "supported"
            for receipt in report.receipts
            if receipt.role is ReferenceAnnotationRole.POSITIVE
        ),
        "positive results remain supported",
    )
    add(
        "control-state",
        all(
            receipt.resolution_state != "supported"
            for receipt in report.receipts
            if receipt.role is ReferenceAnnotationRole.CONTROL
        ),
        "controls remain non-publishable",
    )
    add(
        "bundle-entry-addresses",
        all(entry.content_address for entry in bundle.entries),
        "bundle entries retain addresses",
    )
    add(
        "lineage-node-addresses",
        all(node.content_address for node in lineage.nodes),
        "lineage nodes retain addresses",
    )
    add(
        "shared-boundary",
        bundle.evidence_boundary == selected.evidence_boundary,
        "bundle retains fixture evidence boundary",
    )
    add(
        "bundle-count",
        len(bundle.entries) <= len(report.receipts),
        "bundle does not invent receipts",
    )
    add(
        "operation-closure",
        {receipt.operation for receipt in report.receipts}
        == {entry.operation for entry in bundle.entries}
        or not bundle.entries,
        "bundle operation projection is closed",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "context_key": selected.context_key,
        "checks": checks,
    }
    return ReferenceAnnotationReconciliationReport(
        selected.fixture_id, selected.context_key, tuple(checks), _address(body)
    )


__all__ = [
    "ReferenceAnnotationReconciliationCheck",
    "ReferenceAnnotationReconciliationReport",
    "reconcile_reference_annotation_views",
]
