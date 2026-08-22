"""Deterministic execution and checks for Domain 08 cell-state fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_contracts import (
    CellStateFrontierContractRegistry,
    default_cell_state_frontier_contracts,
)
from .cell_state_frontier_public_data import (
    CELL_STATE_FRONTIER_CONTEXT_KEY,
    CellStateFrontierFixture,
    CellStateFrontierOperation,
    CellStateFrontierRecord,
    CellStateFrontierRole,
    default_cell_state_frontier_fixture,
)
from .errors import ValidationError
from .frontier_context_alpha import (
    CellStateAbundanceUncertaintyModel,
    CellStateContextPublisher,
    CellStateOODDetector,
    SingleCellReferenceMapper,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellStateFrontierExecutionReceipt:
    record_id: str
    operation: CellStateFrontierOperation
    role: CellStateFrontierRole
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
class CellStateFrontierCheck:
    check_id: str
    record_id: str | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellStateFrontierEvaluationReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    receipts: tuple[CellStateFrontierExecutionReceipt, ...]
    checks: tuple[CellStateFrontierCheck, ...]
    catalog_address: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.receipts) and all(item.passed for item in self.checks)

    @property
    def positive_count(self) -> int:
        return sum(item.role is CellStateFrontierRole.POSITIVE for item in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(item.role is CellStateFrontierRole.CONTROL for item in self.receipts)

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


def _rows(record: CellStateFrontierRecord) -> list[dict[str, Any]]:
    raw = record.payload.get("input_text", "[]")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{record.record_id} has invalid input_text") from exc
    if not isinstance(value, list):
        raise ValidationError(f"{record.record_id} input_text must contain a list")
    return [dict(item) for item in value if isinstance(item, dict)]


def _issue_codes(items: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item.code) for item in items))


def _context_mismatch(record: CellStateFrontierRecord, rows: list[dict[str, Any]]) -> bool:
    declared = [row.get("context_key") for row in rows if row.get("context_key") is not None]
    payload_context = record.payload.get("context_key")
    if payload_context is not None:
        declared.append(payload_context)
    return any(str(value) != CELL_STATE_FRONTIER_CONTEXT_KEY for value in declared)


def _execute(
    record: CellStateFrontierRecord,
    context_key: str,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    rows = _rows(record)
    payload = record.payload
    mismatch = _context_mismatch(record, rows)
    try:
        if record.operation is CellStateFrontierOperation.ABUNDANCE_INTERVAL:
            report = CellStateAbundanceUncertaintyModel().estimate(
                rows,
                context_key=context_key,
                interval_multiplier=float(payload.get("interval_multiplier", 1.96)),
            )
            issues = _issue_codes(issue for item in report.estimates for issue in item.issues)
            state = "out_of_domain" if mismatch else (
                "supported" if report.stable_ids else "partial"
            )
            return (
                state,
                len(report.estimates),
                len(report.stable_ids),
                tuple(dict.fromkeys(("context_mismatch",) if mismatch else ())) + issues,
                {
                    "state": state,
                    "estimate_count": len(report.estimates),
                    "stable_ids": list(report.stable_ids),
                    "review_ids": list(report.review_ids),
                    "abundances": [item.abundance for item in report.estimates],
                    "intervals": [
                        [item.lower_bound, item.upper_bound] for item in report.estimates
                    ],
                    "issue_codes": list(issues),
                },
            )
        if record.operation is CellStateFrontierOperation.REFERENCE_MAPPING:
            report = SingleCellReferenceMapper().map(
                rows,
                context_key=context_key,
                minimum_score=float(payload.get("minimum_score", 0.6)),
                minimum_margin=float(payload.get("minimum_margin", 0.1)),
            )
            issues = _issue_codes(issue for item in report.mappings for issue in item.issues)
            state = "out_of_domain" if mismatch else (
                "supported" if report.mapped_ids else "partial"
            )
            return (
                state,
                len(report.mappings),
                len(report.mapped_ids),
                tuple(dict.fromkeys(("context_mismatch",) if mismatch else ())) + issues,
                {
                    "state": state,
                    "mapping_count": len(report.mappings),
                    "mapped_ids": list(report.mapped_ids),
                    "review_ids": list(report.review_ids),
                    "reference_state_ids": [
                        item.reference_state_id for item in report.mappings
                    ],
                    "margins": [item.margin for item in report.mappings],
                    "issue_codes": list(issues),
                },
            )
        if record.operation is CellStateFrontierOperation.OOD_DETECTION:
            report = CellStateOODDetector().detect(
                rows,
                context_key=context_key,
                maximum_distance=float(payload.get("maximum_distance", 3.0)),
                minimum_support=float(payload.get("minimum_support", 0.5)),
            )
            issues = _issue_codes(issue for item in report.findings for issue in item.issues)
            state = "out_of_domain" if mismatch else (
                "supported" if report.in_domain_ids else "partial"
            )
            return (
                state,
                len(report.findings),
                len(report.in_domain_ids),
                tuple(dict.fromkeys(("context_mismatch",) if mismatch else ())) + issues,
                {
                    "state": state,
                    "finding_count": len(report.findings),
                    "in_domain_ids": list(report.in_domain_ids),
                    "ood_ids": list(report.ood_ids),
                    "review_ids": list(report.review_ids),
                    "distances": [item.distance for item in report.findings],
                    "support_scores": [item.support_score for item in report.findings],
                    "issue_codes": list(issues),
                },
            )
        if record.operation is CellStateFrontierOperation.CONTEXT_PUBLICATION:
            if mismatch:
                return (
                    "out_of_domain",
                    len(payload.get("cell_ids", ())),
                    3,
                    ("context_mismatch",),
                    {
                        "state": "out_of_domain",
                        "cell_count": len(payload.get("cell_ids", ())),
                        "receipt_count": 3,
                        "envelope_address": None,
                        "issue_codes": ["context_mismatch"],
                    },
                )
            if not payload.get("cell_ids"):
                return (
                    "partial",
                    0,
                    0,
                    ("empty_cell_ids",),
                    {"state": "partial", "cell_count": 0, "receipt_count": 0, "envelope_address": None, "issue_codes": ["empty_cell_ids"]},
                )
            if not all(payload.get(name) for name in ("mapping_address", "abundance_address", "ood_address")):
                return (
                    "partial",
                    len(payload.get("cell_ids", ())),
                    2,
                    ("missing_receipt_address",),
                    {"state": "partial", "cell_count": len(payload.get("cell_ids", ())), "receipt_count": 2, "envelope_address": None, "issue_codes": ["missing_receipt_address"]},
                )
            envelope = CellStateContextPublisher().publish(
                envelope_id=record.record_id,
                context_key=context_key,
                cell_ids=tuple(payload.get("cell_ids", ())),
                mapping_address=str(payload["mapping_address"]),
                abundance_address=str(payload["abundance_address"]),
                ood_address=str(payload["ood_address"]),
            )
            return (
                "supported",
                len(envelope.cell_ids),
                3,
                (),
                {
                    "state": "supported",
                    "cell_count": len(envelope.cell_ids),
                    "receipt_count": 3,
                    "envelope_address": envelope.envelope_address,
                    "issue_codes": [],
                },
            )
    except (TypeError, ValueError, ValidationError):
        return (
            "partial",
            0,
            0,
            ("invalid_cell_state_row",),
            {"state": "partial", "primary_count": 0, "secondary_count": 0, "issue_codes": ["invalid_cell_state_row"]},
        )
    raise ValidationError(f"unknown cell state operation: {record.operation}")


def evaluate_cell_state_frontier_fixture(
    fixture: CellStateFrontierFixture | None = None,
    *,
    contracts: CellStateFrontierContractRegistry | None = None,
) -> CellStateFrontierEvaluationReport:
    selected = fixture or default_cell_state_frontier_fixture()
    registry = contracts or default_cell_state_frontier_contracts()
    receipts: list[CellStateFrontierExecutionReceipt] = []
    checks: list[CellStateFrontierCheck] = []

    def add(check_id: str, record_id: str | None, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(CellStateFrontierCheck(**body, content_address=content_hash(body)))

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
            "observed_issue_codes": tuple(dict.fromkeys(issues)),
            "summary": summary,
        }
        receipt = CellStateFrontierExecutionReceipt(**body, content_address=content_hash(body))
        receipts.append(receipt)
        contract = registry.by_operation(record.operation)
        add(f"{record.record_id}:expected-state", record.record_id, state == record.expected_state, "state matches fixture")
        add(f"{record.record_id}:expected-issues", record.record_id, set(record.expected_issue_codes) <= set(issues), "issue floor is observed")
        add(f"{record.record_id}:context", record.record_id, receipt.context_key == selected.context_key, "receipt retains context")
        add(f"{record.record_id}:operation", record.record_id, receipt.operation is record.operation and contract.operation is record.operation, "operation contract resolves")
        add(f"{record.record_id}:role", record.record_id, receipt.role is record.role, "record role is retained")
        add(f"{record.record_id}:address", record.record_id, receipt.content_address.startswith("sha256:"), "receipt is addressed")
        add(f"{record.record_id}:sanitized", record.record_id, "input_text" not in receipt.summary and "payload" not in receipt.summary, "summary excludes raw input")
    add("fixture-context", None, selected.context_key == CELL_STATE_FRONTIER_CONTEXT_KEY, "fixture context is exact")
    add("record-count", None, len(receipts) == len(selected.records) == 16, "sixteen records execute")
    add("positive-floor", None, sum(item.role is CellStateFrontierRole.POSITIVE for item in receipts) == 4, "four positive records execute")
    add("control-floor", None, sum(item.role is CellStateFrontierRole.CONTROL for item in receipts) == 12, "twelve controls execute")
    add("operation-coverage", None, {item.operation for item in receipts} == set(CellStateFrontierOperation), "all operations execute")
    add("source-closure", None, all(source_id in selected.source_map() for item in selected.records for source_id in item.source_ids), "all sources resolve")
    add("positive-state-floor", None, all(item.adapter_state == "supported" for item in receipts if item.role is CellStateFrontierRole.POSITIVE), "positive paths are supported")
    add("control-visibility", None, all(item.adapter_state != "supported" for item in receipts if item.role is CellStateFrontierRole.CONTROL), "controls remain visible")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "receipts": receipts,
        "checks": checks,
        "catalog_address": content_hash({"records": selected.records}),
    }
    return CellStateFrontierEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        tuple(receipts),
        tuple(checks),
        body["catalog_address"],
        content_hash(body),
    )


__all__ = [
    "CellStateFrontierCheck",
    "CellStateFrontierEvaluationReport",
    "CellStateFrontierExecutionReceipt",
    "evaluate_cell_state_frontier_fixture",
]
