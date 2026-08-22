"""Deterministic execution and reconciliation checks for Domain 07 fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .chromatin_alpha import (
    AlleleSpecificChromatinAnalyzer,
    BatchCellCompositionCorrector,
    ChromatinStateSegmentationAdapter,
    EpigenomicPurityDeconvolver,
)
from .chromatin_frontier_contracts import (
    ChromatinFrontierContractRegistry,
    default_chromatin_frontier_contracts,
)
from .chromatin_frontier_public_data import (
    CHROMATIN_FRONTIER_CONTEXT_KEY,
    ChromatinFrontierFixture,
    ChromatinFrontierOperation,
    ChromatinFrontierRecord,
    ChromatinFrontierRole,
    default_chromatin_frontier_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinFrontierExecutionReceipt:
    record_id: str
    operation: ChromatinFrontierOperation
    role: ChromatinFrontierRole
    context_key: str
    expected_state: str
    adapter_state: str
    primary_count: int
    secondary_count: int
    observed_issue_codes: tuple[str, ...]
    summary: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierCheck:
    check_id: str
    record_id: str | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierEvaluationReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    receipts: tuple[ChromatinFrontierExecutionReceipt, ...]
    checks: tuple[ChromatinFrontierCheck, ...]
    catalog_address: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.receipts) and all(item.passed for item in self.checks)

    @property
    def positive_count(self) -> int:
        return sum(item.role is ChromatinFrontierRole.POSITIVE for item in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(item.role is ChromatinFrontierRole.CONTROL for item in self.receipts)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _rows(record: ChromatinFrontierRecord) -> list[dict[str, Any]]:
    raw = record.payload.get("input_text", "[]")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{record.record_id} has invalid input_text") from exc
    if not isinstance(value, list):
        raise ValidationError(f"{record.record_id} input_text must contain a list")
    return [dict(item) for item in value if isinstance(item, dict)]


def _issue_codes(report: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item.code) for item in report.issues))


def _execute(
    record: ChromatinFrontierRecord,
    context_key: str,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    rows = _rows(record)
    payload = record.payload
    if record.operation is ChromatinFrontierOperation.CHROMATIN_SEGMENTATION:
        report = ChromatinStateSegmentationAdapter().segment(
            rows,
            context_key=context_key,
            low_signal=float(payload.get("low_signal", 0.25)),
            high_signal=float(payload.get("high_signal", 0.75)),
        )
        issues = _issue_codes(report)
        return (
            report.state.value,
            len(report.observations),
            len(report.segments),
            issues,
            {
                "state": report.state.value,
                "observation_count": len(report.observations),
                "segment_count": len(report.segments),
                "ambiguous_segment_ids": [
                    item.segment_id for item in report.segments if item.state.value == "ambiguous"
                ],
                "state_labels": sorted({item.state_label for item in report.segments}),
                "issue_codes": list(issues),
            },
        )
    if record.operation is ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN:
        report = AlleleSpecificChromatinAnalyzer().analyze(
            rows,
            context_key=context_key,
            ambiguity_tolerance=float(payload.get("ambiguity_tolerance", 0.3)),
            delta_threshold=float(payload.get("delta_threshold", 0.1)),
        )
        issues = _issue_codes(report)
        return (
            report.state.value,
            len(report.observations),
            len(report.results),
            issues,
            {
                "state": report.state.value,
                "variant_ids": sorted({item.variant_id for item in report.results}),
                "result_count": len(report.results),
                "directions": sorted({item.direction for item in report.results}),
                "median_deltas": [item.median_delta for item in report.results],
                "issue_codes": list(issues),
            },
        )
    if record.operation is ChromatinFrontierOperation.EPIGENOMIC_PURITY:
        report = EpigenomicPurityDeconvolver().estimate(
            rows,
            context_key=context_key,
            minimum_markers=int(payload.get("minimum_markers", 2)),
            spread_tolerance=float(payload.get("spread_tolerance", 0.2)),
        )
        issues = _issue_codes(report)
        return (
            report.state.value,
            len(report.marker_observations),
            len(report.estimates),
            issues,
            {
                "state": report.state.value,
                "marker_count": len(report.marker_observations),
                "estimate_count": len(report.estimates),
                "aggregate_purity": report.aggregate_purity,
                "purity_spread": report.purity_spread,
                "estimate_states": sorted({item.state.value for item in report.estimates}),
                "issue_codes": list(issues),
            },
        )
    if record.operation is ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION:
        offsets = payload.get("batch_offsets", {})
        target = payload.get("target_composition")
        report = BatchCellCompositionCorrector().correct(
            rows,
            context_key=context_key,
            batch_offsets=offsets if isinstance(offsets, dict) else {},
            target_composition=target if isinstance(target, dict) else None,
        )
        issues = _issue_codes(report)
        return (
            report.state.value,
            len(report.observations),
            len(report.corrections),
            issues,
            {
                "state": report.state.value,
                "observation_count": len(report.observations),
                "correction_count": len(report.corrections),
                "corrected_feature_ids": [item.feature_id for item in report.corrections],
                "corrected_signals": [item.corrected_signal for item in report.corrections],
                "issue_codes": list(issues),
            },
        )
    raise ValidationError(f"unknown chromatin frontier operation: {record.operation}")


def evaluate_chromatin_frontier_fixture(
    fixture: ChromatinFrontierFixture | None = None,
    *,
    contracts: ChromatinFrontierContractRegistry | None = None,
) -> ChromatinFrontierEvaluationReport:
    selected = fixture or default_chromatin_frontier_fixture()
    registry = contracts or default_chromatin_frontier_contracts()
    receipts: list[ChromatinFrontierExecutionReceipt] = []
    checks: list[ChromatinFrontierCheck] = []

    def add(check_id: str, record_id: str | None, passed: bool, detail: str) -> None:
        body = {
            "check_id": check_id,
            "record_id": record_id,
            "passed": passed,
            "detail": detail,
        }
        checks.append(ChromatinFrontierCheck(**body, content_address=content_hash(body)))

    for record in selected.records:
        state, primary, secondary, issues, summary = _execute(record, selected.context_key)
        body = {
            "record_id": record.record_id,
            "operation": record.operation,
            "role": record.role,
            "context_key": selected.context_key,
            "expected_state": record.expected_state,
            "adapter_state": state,
            "primary_count": primary,
            "secondary_count": secondary,
            "observed_issue_codes": issues,
            "summary": summary,
        }
        receipt = ChromatinFrontierExecutionReceipt(
            **body,
            content_address=content_hash(body),
        )
        receipts.append(receipt)
        contract = registry.by_operation(record.operation)
        add(
            f"{record.record_id}:expected-state",
            record.record_id,
            state == record.expected_state,
            "adapter state matches fixture expectation",
        )
        add(
            f"{record.record_id}:expected-issues",
            record.record_id,
            set(record.expected_issue_codes) <= set(issues),
            "expected issue floors are observed",
        )
        add(
            f"{record.record_id}:context",
            record.record_id,
            receipt.context_key == selected.context_key,
            "receipt retains exact context",
        )
        add(
            f"{record.record_id}:operation",
            record.record_id,
            receipt.operation is record.operation and contract.operation is record.operation,
            "operation contract resolves",
        )
        add(
            f"{record.record_id}:role",
            record.record_id,
            receipt.role is record.role,
            "positive or control role is retained",
        )
        add(
            f"{record.record_id}:address",
            record.record_id,
            receipt.content_address.startswith("sha256:"),
            "receipt is content addressed",
        )
        add(
            f"{record.record_id}:sanitized",
            record.record_id,
            "input_text" not in receipt.summary and "payload" not in receipt.summary,
            "receipt excludes raw input",
        )
    add(
        "fixture-context",
        None,
        selected.context_key == CHROMATIN_FRONTIER_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "record-count",
        None,
        len(receipts) == len(selected.records) == 16,
        "sixteen records execute",
    )
    add(
        "positive-floor",
        None,
        sum(item.role is ChromatinFrontierRole.POSITIVE for item in receipts) == 4,
        "four positive paths execute",
    )
    add(
        "control-floor",
        None,
        sum(item.role is ChromatinFrontierRole.CONTROL for item in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-coverage",
        None,
        {item.operation for item in receipts} == set(ChromatinFrontierOperation),
        "all operations execute",
    )
    add(
        "source-closure",
        None,
        all(
            source_id in selected.source_map()
            for item in selected.records
            for source_id in item.source_ids
        ),
        "all sources resolve",
    )
    add(
        "positive-state-floor",
        None,
        all(
            item.adapter_state in {"supported"}
            for item in receipts
            if item.role is ChromatinFrontierRole.POSITIVE
        ),
        "positive paths are supported",
    )
    add(
        "control-visibility",
        None,
        all(
            item.adapter_state != "supported"
            for item in receipts
            if item.role is ChromatinFrontierRole.CONTROL
        ),
        "controls remain visible non-success states",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "receipts": receipts,
        "checks": checks,
        "catalog_address": content_hash({"records": selected.records}),
    }
    return ChromatinFrontierEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        tuple(receipts),
        tuple(checks),
        body["catalog_address"],
        content_hash(body),
    )


__all__ = [
    "ChromatinFrontierCheck",
    "ChromatinFrontierEvaluationReport",
    "ChromatinFrontierExecutionReceipt",
    "evaluate_chromatin_frontier_fixture",
]
