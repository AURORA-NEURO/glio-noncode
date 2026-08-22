"""Deterministic adapter execution and checks for Domain 09 fixtures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_inference_alpha import (
    CompartmentSwitchEstimator,
    EcDNARegulatoryContactModel,
    ThreeDEvidencePublisher,
    TopologyUncertaintyTransportModel,
)
from .serialization import content_hash, jsonable
from .topology_frontier_contracts import (
    TopologyFrontierContractRegistry,
    default_topology_frontier_contracts,
)
from .topology_frontier_public_data import (
    TOPOLOGY_FRONTIER_CONTEXT_KEY,
    TopologyFrontierFixture,
    TopologyFrontierOperation,
    TopologyFrontierRecord,
    TopologyFrontierRole,
    default_topology_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class TopologyFrontierExecutionReceipt:
    record_id: str
    operation: TopologyFrontierOperation
    role: TopologyFrontierRole
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
class TopologyFrontierCheck:
    check_id: str
    record_id: str | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyFrontierEvaluationReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    receipts: tuple[TopologyFrontierExecutionReceipt, ...]
    checks: tuple[TopologyFrontierCheck, ...]
    catalog_address: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.receipts) and all(item.passed for item in self.checks)

    @property
    def positive_count(self) -> int:
        return sum(item.role is TopologyFrontierRole.POSITIVE for item in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(item.role is TopologyFrontierRole.CONTROL for item in self.receipts)

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


def _rows(record: TopologyFrontierRecord) -> list[Any]:
    raw = record.payload.get("input_text", "[]")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{record.record_id} has invalid input_text") from exc
    if not isinstance(value, list):
        raise ValidationError(f"{record.record_id} input_text must contain a list")
    return value


def _issue_codes(items: Any) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(item.code) for item in items))


def _context_mismatch(record: TopologyFrontierRecord, rows: list[Any]) -> bool:
    declared: list[Any] = [record.payload.get("context_key")]
    declared.extend(row.get("context_key") for row in rows if isinstance(row, dict))
    return any(value is not None and str(value) != TOPOLOGY_FRONTIER_CONTEXT_KEY for value in declared)


def _execute(
    record: TopologyFrontierRecord,
    context_key: str,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    try:
        rows = _rows(record)
        payload = record.payload
        mismatch = _context_mismatch(record, rows)
        if record.operation is TopologyFrontierOperation.ECDNA_CONTACT:
            report = EcDNARegulatoryContactModel().evaluate(
                rows,
                context_key=context_key,
                minimum_contact_score=float(payload.get("minimum_contact_score", 0.5)),
                minimum_sources=int(payload.get("minimum_sources", 1)),
            )
            issues = _issue_codes(issue for item in report.contacts for issue in item.issues)
            state = "out_of_domain" if mismatch else ("supported" if report.supported_ids else "partial")
            return state, len(report.contacts), len(report.supported_ids), tuple(dict.fromkeys((("context_mismatch",) if mismatch else ()) + issues)), {
                "state": state,
                "contact_count": len(report.contacts),
                "supported_ids": list(report.supported_ids),
                "review_ids": list(report.review_ids),
                "normalized_support": [item.normalized_support for item in report.contacts],
                "issue_codes": list(issues),
            }
        if record.operation is TopologyFrontierOperation.COMPARTMENT_SWITCH:
            report = CompartmentSwitchEstimator().estimate(
                rows,
                context_key=context_key,
                switch_threshold=float(payload.get("switch_threshold", 0.15)),
            )
            state = "out_of_domain" if mismatch else ("supported" if report.switched_ids else "partial")
            return state, len(report.switches), len(report.switched_ids), ("context_mismatch",) if mismatch else (), {
                "state": state,
                "switch_count": len(report.switches),
                "switched_ids": list(report.switched_ids),
                "stable_ids": list(report.stable_ids),
                "switch_kinds": [item.switch_kind for item in report.switches],
                "issue_codes": ["context_mismatch"] if mismatch else [],
            }
        if record.operation is TopologyFrontierOperation.TOPOLOGY_TRANSPORT:
            report = TopologyUncertaintyTransportModel().transport(
                rows,
                context_key=context_key,
                minimum_effective_signal=float(payload.get("minimum_effective_signal", 0.3)),
            )
            issues = _issue_codes(issue for item in report.transports for issue in item.issues)
            state = "out_of_domain" if mismatch else ("supported" if report.supported_ids else "partial")
            return state, len(report.transports), len(report.supported_ids), tuple(dict.fromkeys((("context_mismatch",) if mismatch else ()) + issues)), {
                "state": state,
                "transport_count": len(report.transports),
                "supported_ids": list(report.supported_ids),
                "review_ids": list(report.review_ids),
                "effective_signals": [item.effective_signal for item in report.transports],
                "issue_codes": list(issues),
            }
        if record.operation is TopologyFrontierOperation.EVIDENCE_PUBLICATION:
            if mismatch:
                return "out_of_domain", len(rows), 0, ("context_mismatch",), {
                    "state": "out_of_domain",
                    "path_count": len(rows),
                    "assay_count": 0,
                    "issue_codes": ["context_mismatch"],
                }
            if not rows:
                return "partial", 0, 0, ("empty_3d_evidence",), {
                    "state": "partial",
                    "path_count": 0,
                    "assay_count": 0,
                    "issue_codes": ["empty_3d_evidence"],
                }
            assays = tuple(payload.get("assay_ids", ()))
            if not assays:
                return "partial", len(rows), 0, ("missing_assay_ids",), {
                    "state": "partial",
                    "path_count": len(rows),
                    "assay_count": 0,
                    "issue_codes": ["missing_assay_ids"],
                }
            bundle = ThreeDEvidencePublisher().publish(
                rows,
                bundle_id=str(payload.get("bundle_id", record.record_id)),
                context_key=context_key,
                assay_ids=assays,
            )
            return "supported", len(bundle.path_ids), len(assays), (), {
                "state": "supported",
                "path_count": len(bundle.path_ids),
                "assay_count": len(assays),
                "records_address": bundle.records_address,
                "bundle_address": bundle.bundle_address,
                "issue_codes": [],
            }
    except (TypeError, ValueError, ValidationError):
        return "invalid", 0, 0, (f"invalid_{record.operation.value.removesuffix('_regulatory_contact').removesuffix('_switch').removesuffix('_transport').removesuffix('_publication')}_record",), {
            "state": "invalid",
            "primary_count": 0,
            "secondary_count": 0,
            "issue_codes": [f"invalid_{record.operation.value}_record"],
        }
    raise ValidationError(f"unknown topology operation: {record.operation}")


def evaluate_topology_frontier_fixture(
    fixture: TopologyFrontierFixture | None = None,
    *,
    contracts: TopologyFrontierContractRegistry | None = None,
) -> TopologyFrontierEvaluationReport:
    selected = fixture or default_topology_frontier_fixture()
    registry = contracts or default_topology_frontier_contracts()
    receipts: list[TopologyFrontierExecutionReceipt] = []
    checks: list[TopologyFrontierCheck] = []

    def add(check_id: str, record_id: str | None, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(TopologyFrontierCheck(**body, content_address=content_hash(body)))

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
        receipt = TopologyFrontierExecutionReceipt(**body, content_address=content_hash(body))
        receipts.append(receipt)
        contract = registry.by_operation(record.operation)
        add(f"{record.record_id}:expected-state", record.record_id, state == record.expected_state, "state matches fixture")
        add(f"{record.record_id}:expected-issues", record.record_id, set(record.expected_issue_codes) <= set(issues), "issue floor is observed")
        add(f"{record.record_id}:context", record.record_id, receipt.context_key == selected.context_key, "receipt retains context")
        add(f"{record.record_id}:operation", record.record_id, receipt.operation is record.operation and contract.operation is record.operation, "operation contract resolves")
        add(f"{record.record_id}:role", record.record_id, receipt.role is record.role, "record role is retained")
        add(f"{record.record_id}:address", record.record_id, receipt.content_address.startswith("sha256:"), "receipt is addressed")
        add(f"{record.record_id}:sanitized", record.record_id, "input_text" not in receipt.summary and "payload" not in receipt.summary, "summary excludes raw input")
    add("fixture-context", None, selected.context_key == TOPOLOGY_FRONTIER_CONTEXT_KEY, "fixture context is exact")
    add("record-count", None, len(receipts) == len(selected.records) == 16, "sixteen records execute")
    add("positive-floor", None, sum(item.role is TopologyFrontierRole.POSITIVE for item in receipts) == 4, "four positive records execute")
    add("control-floor", None, sum(item.role is TopologyFrontierRole.CONTROL for item in receipts) == 12, "twelve controls execute")
    add("operation-coverage", None, {item.operation for item in receipts} == set(TopologyFrontierOperation), "all operations execute")
    add("source-closure", None, all(source_id in selected.source_map() for item in selected.records for source_id in item.source_ids), "all sources resolve")
    add("positive-state-floor", None, all(item.adapter_state == "supported" for item in receipts if item.role is TopologyFrontierRole.POSITIVE), "positive paths are supported")
    add("control-visibility", None, all(item.adapter_state != "supported" for item in receipts if item.role is TopologyFrontierRole.CONTROL), "controls remain visible")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "receipts": receipts,
        "checks": checks,
        "catalog_address": content_hash({"records": selected.records}),
    }
    return TopologyFrontierEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        tuple(receipts),
        tuple(checks),
        body["catalog_address"],
        content_hash(body),
    )


__all__ = [
    "TopologyFrontierCheck",
    "TopologyFrontierEvaluationReport",
    "TopologyFrontierExecutionReceipt",
    "evaluate_topology_frontier_fixture",
]
