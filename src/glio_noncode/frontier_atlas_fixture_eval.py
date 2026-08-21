"""Deterministic execution and sanitized receipts for C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_atlas_contracts import (
    FrontierAtlasContractRegistry,
    default_frontier_atlas_contracts,
)
from .frontier_atlas_public_data import (
    FRONTIER_ATLAS_CONTEXT_KEY,
    FrontierAtlasFixture,
    FrontierAtlasOperation,
    FrontierAtlasRecord,
    FrontierAtlasRole,
    build_frontier_atlas_catalog,
    default_frontier_atlas_fixture,
)
from .frontier_context_alpha import (
    AtlasEvidenceTierAdjudicator,
    AtlasSnapshotPublisher,
    InsulatorBoundaryAtlas,
    RegulatoryHotspotAtlas,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class FrontierAtlasCheck:
    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasExecutionReceipt:
    record_id: str
    capability_id: str
    operation: FrontierAtlasOperation
    role: FrontierAtlasRole
    context_key: str
    adapter_state: str
    primary_count: int
    secondary_count: int
    observed_issue_codes: tuple[str, ...]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    check_ids: tuple[str, ...]
    summary: dict[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "capability_id",
            "context_key",
            "adapter_state",
            "expected_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.primary_count < 0 or self.secondary_count < 0:
            raise ValidationError("frontier atlas receipt counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.adapter_state == self.expected_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FrontierAtlasEvaluationReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[FrontierAtlasExecutionReceipt, ...]
    checks: tuple[FrontierAtlasCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(item.role is FrontierAtlasRole.POSITIVE for item in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(item.role is FrontierAtlasRole.CONTROL for item in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _rows(record: FrontierAtlasRecord) -> list[dict[str, Any]]:
    payload = json.loads(str(record.payload["input_text"]))
    rows = payload.get("records", ())
    if not isinstance(rows, list):
        raise ValidationError("frontier atlas fixture input must contain a records list")
    return rows


def _context_issue(rows: list[dict[str, Any]], context_key: str, code: str) -> tuple[str, ...]:
    return (code,) if any(row.get("context_key") not in {None, context_key} for row in rows) else ()


def _execute_boundary(
    record: FrontierAtlasRecord, rows: list[dict[str, Any]]
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    issues = list(_context_issue(rows, record.context_key, "boundary_context_mismatch"))
    if issues:
        return (
            "out_of_domain",
            0,
            0,
            tuple(issues),
            {
                "state": "out_of_domain",
                "observation_count": 0,
                "strong_boundary_ids": (),
                "review_ids": (),
                "issue_codes": tuple(issues),
            },
        )
    report = InsulatorBoundaryAtlas().build(
        rows,
        context_key=record.context_key,
        source_id=str(payload["source_id"]),
        minimum_support=float(payload["minimum_support"]),
    )
    issues.extend(issue.code for observation in report.observations for issue in observation.issues)
    issues.extend(
        "boundary_low_support"
        for observation in report.observations
        if observation.boundary_support < float(payload["minimum_support"])
    )
    state = "accepted" if report.strong_boundary_ids and not report.review_ids else "review"
    summary = {
        "state": state,
        "observation_count": len(report.observations),
        "strong_boundary_ids": report.strong_boundary_ids,
        "review_ids": report.review_ids,
        "issue_codes": tuple(dict.fromkeys(issues)),
    }
    return (
        state,
        len(report.observations),
        len(report.strong_boundary_ids),
        tuple(dict.fromkeys(issues)),
        summary,
    )


def _execute_hotspot(
    record: FrontierAtlasRecord, rows: list[dict[str, Any]]
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    issues = list(_context_issue(rows, record.context_key, "hotspot_context_mismatch"))
    if issues:
        return (
            "out_of_domain",
            0,
            0,
            tuple(issues),
            {
                "state": "out_of_domain",
                "observation_count": 0,
                "supported_ids": (),
                "review_ids": (),
                "issue_codes": tuple(issues),
            },
        )
    report = RegulatoryHotspotAtlas().build(
        rows,
        context_key=record.context_key,
        minimum_support_count=int(payload["minimum_support_count"]),
        minimum_concordance=float(payload["minimum_concordance"]),
    )
    issues.extend(issue.code for observation in report.observations for issue in observation.issues)
    state = "accepted" if report.supported_ids and not report.review_ids else "review"
    summary = {
        "state": state,
        "observation_count": len(report.observations),
        "supported_ids": report.supported_ids,
        "review_ids": report.review_ids,
        "issue_codes": tuple(dict.fromkeys(issues)),
    }
    return (
        state,
        len(report.observations),
        len(report.supported_ids),
        tuple(dict.fromkeys(issues)),
        summary,
    )


def _execute_tier(
    record: FrontierAtlasRecord, rows: list[dict[str, Any]]
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    issues = list(_context_issue(rows, record.context_key, "tier_context_mismatch"))
    if issues:
        return (
            "out_of_domain",
            0,
            0,
            tuple(issues),
            {
                "state": "out_of_domain",
                "decision_count": 0,
                "high_confidence_ids": (),
                "review_ids": (),
                "issue_codes": tuple(issues),
            },
        )
    report = AtlasEvidenceTierAdjudicator().adjudicate(
        rows,
        context_key=record.context_key,
        high_source_count=int(payload["high_source_count"]),
        high_consistency=float(payload["high_consistency"]),
        medium_consistency=float(payload["medium_consistency"]),
    )
    issues.extend(issue.code for decision in report.decisions for issue in decision.issues)
    issues.extend(
        "low_evidence_tier" for decision in report.decisions if decision.evidence_tier == "low"
    )
    state = "accepted" if report.decisions and not report.review_ids else "review"
    summary = {
        "state": state,
        "decision_count": len(report.decisions),
        "high_confidence_ids": report.high_confidence_ids,
        "review_ids": report.review_ids,
        "evidence_tiers": tuple(decision.evidence_tier for decision in report.decisions),
        "issue_codes": tuple(dict.fromkeys(issues)),
    }
    return (
        state,
        len(report.decisions),
        len(report.high_confidence_ids),
        tuple(dict.fromkeys(issues)),
        summary,
    )


def _execute_snapshot(
    record: FrontierAtlasRecord, rows: list[dict[str, Any]]
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    required = ("snapshot_id", "atlas_type", "version", "schema_version")
    if any(field not in payload for field in required):
        issues = ("snapshot_metadata_invalid",)
        return (
            "invalid",
            0,
            0,
            issues,
            {
                "state": "invalid",
                "record_count": 0,
                "records_address": None,
                "snapshot_address": None,
                "issue_codes": issues,
            },
        )
    context_issues = _context_issue(rows, record.context_key, "snapshot_context_mismatch")
    if context_issues:
        return (
            "out_of_domain",
            0,
            0,
            context_issues,
            {
                "state": "out_of_domain",
                "record_count": 0,
                "records_address": None,
                "snapshot_address": None,
                "issue_codes": context_issues,
            },
        )
    if not rows:
        issues = ("empty_snapshot_records",)
        return (
            "abstained",
            0,
            0,
            issues,
            {
                "state": "abstained",
                "record_count": 0,
                "records_address": None,
                "snapshot_address": None,
                "issue_codes": issues,
            },
        )
    try:
        snapshot = AtlasSnapshotPublisher().publish(
            rows,
            snapshot_id=str(payload["snapshot_id"]),
            atlas_type=str(payload["atlas_type"]),
            version=str(payload["version"]),
            context_key=record.context_key,
            schema_version=str(payload["schema_version"]),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        issues = ("snapshot_metadata_invalid",)
        return (
            "invalid",
            len(rows),
            0,
            issues,
            {
                "state": "invalid",
                "record_count": len(rows),
                "records_address": None,
                "snapshot_address": None,
                "issue_codes": issues,
            },
        )
    summary = {
        "state": "published",
        "record_count": snapshot.record_count,
        "records_address": snapshot.records_address,
        "snapshot_address": snapshot.snapshot_address,
        "schema_version": snapshot.schema_version,
        "issue_codes": (),
    }
    return "published", snapshot.record_count, 1, (), summary


def _execute(record: FrontierAtlasRecord) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    rows = _rows(record)
    if record.operation is FrontierAtlasOperation.BOUNDARY_ATLAS:
        return _execute_boundary(record, rows)
    if record.operation is FrontierAtlasOperation.HOTSPOT_ATLAS:
        return _execute_hotspot(record, rows)
    if record.operation is FrontierAtlasOperation.EVIDENCE_TIER:
        return _execute_tier(record, rows)
    if record.operation is FrontierAtlasOperation.SNAPSHOT_PUBLISH:
        return _execute_snapshot(record, rows)
    raise ValidationError(f"unsupported frontier atlas operation: {record.operation}")


def evaluate_frontier_atlas_fixture(
    fixture: FrontierAtlasFixture | None = None,
    *,
    contracts: FrontierAtlasContractRegistry | None = None,
) -> FrontierAtlasEvaluationReport:
    """Execute all C13-C16 positive and control records."""

    selected = fixture or default_frontier_atlas_fixture()
    registry = contracts or default_frontier_atlas_contracts()
    catalog = build_frontier_atlas_catalog(selected)
    checks: list[FrontierAtlasCheck] = []
    receipts: list[FrontierAtlasExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(FrontierAtlasCheck(check_id, record_id, passed, detail, content_hash(body)))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == FRONTIER_ATLAS_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "fixture-address",
        "fixture",
        selected.content_address
        == content_hash(
            {key: value for key, value in selected.to_dict().items() if key != "content_address"}
        ),
        "fixture address verifies",
    )
    add(
        "catalog-address",
        "fixture",
        catalog.content_address
        == content_hash(
            {
                "fixture_id": selected.fixture_id,
                "fixture_version": selected.fixture_version,
                "source_ids": catalog.source_ids,
                "record_ids": catalog.record_ids,
                "operations": catalog.operations,
            }
        ),
        "catalog address verifies",
    )
    for record in selected.records:
        contract = registry.by_operation(record.operation)
        missing = contract.validate_payload(record.payload)
        add(
            f"{record.record_id}:contract",
            record.record_id,
            not missing,
            "contract-required fields are present",
        )
        try:
            state, primary, secondary, issue_codes, summary = _execute(record)
            execution_error = None
        except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            state, primary, secondary, issue_codes, summary = (
                "invalid",
                0,
                0,
                ("execution_error",),
                {
                    "state": "invalid",
                    "issue_codes": ("execution_error",),
                    "error_type": type(exc).__name__,
                },
            )
            execution_error = str(exc)
        check_ids = [f"{record.record_id}:contract"]
        state_id = f"{record.record_id}:state"
        add(
            state_id,
            record.record_id,
            state == record.expected_state and execution_error is None,
            "adapter state matches fixture expectation",
        )
        check_ids.append(state_id)
        issue_id = f"{record.record_id}:issues"
        add(
            issue_id,
            record.record_id,
            not set(record.expected_issue_codes) - set(issue_codes),
            "expected issue floors are visible",
        )
        check_ids.append(issue_id)
        role_id = f"{record.record_id}:role"
        positive_states = {"accepted", "published"}
        add(
            role_id,
            record.record_id,
            (record.role is FrontierAtlasRole.POSITIVE) == (state in positive_states),
            "positive and control roles agree with expected state",
        )
        check_ids.append(role_id)
        context_id = f"{record.record_id}:context"
        add(
            context_id,
            record.record_id,
            record.context_key == selected.context_key,
            "record declares the fixture context",
        )
        check_ids.append(context_id)
        summary_id = f"{record.record_id}:summary"
        add(
            summary_id,
            record.record_id,
            summary.get("state") == state and primary >= 0 and secondary >= 0,
            "sanitized summary is internally consistent",
        )
        check_ids.append(summary_id)
        address_id = f"{record.record_id}:receipt-address"
        check_ids.append(address_id)
        body = {
            "record_id": record.record_id,
            "capability_id": contract.capability_id,
            "operation": record.operation,
            "role": record.role,
            "context_key": record.context_key,
            "adapter_state": state,
            "primary_count": primary,
            "secondary_count": secondary,
            "observed_issue_codes": tuple(issue_codes),
            "expected_state": record.expected_state,
            "expected_issue_codes": record.expected_issue_codes,
            "check_ids": tuple(check_ids),
            "summary": summary,
        }
        receipt = FrontierAtlasExecutionReceipt(**body, content_address=content_hash(body))
        add(
            address_id,
            record.record_id,
            receipt.content_address
            == content_hash(
                {key: value for key, value in receipt.to_dict().items() if key != "content_address"}
            ),
            "receipt address verifies",
        )
        receipts.append(receipt)
    add(
        "positive-count",
        "fixture",
        sum(item.role is FrontierAtlasRole.POSITIVE for item in receipts) == 4,
        "four positive records execute",
    )
    add(
        "control-count",
        "fixture",
        sum(item.role is FrontierAtlasRole.CONTROL for item in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-balance",
        "fixture",
        {item.operation for item in receipts} == set(FrontierAtlasOperation),
        "all operations execute",
    )
    add(
        "sanitized-receipts",
        "fixture",
        all(not {"input_text", "payload", "records"} & set(item.summary) for item in receipts),
        "receipts exclude input payloads",
    )
    add(
        "positive-state-floor",
        "fixture",
        all(
            item.adapter_state in {"accepted", "published"}
            for item in receipts
            if item.role is FrontierAtlasRole.POSITIVE
        ),
        "positive states remain accepted or published",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "catalog_address": catalog.content_address,
        "receipts": receipts,
        "checks": checks,
    }
    return FrontierAtlasEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "FrontierAtlasCheck",
    "FrontierAtlasEvaluationReport",
    "FrontierAtlasExecutionReceipt",
    "evaluate_frontier_atlas_fixture",
]
