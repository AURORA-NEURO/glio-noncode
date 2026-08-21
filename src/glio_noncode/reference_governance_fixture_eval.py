"""Deterministic execution and sanitized receipts for Domain 04 C09–C12."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_alpha import (
    GeneAliasVersionResolver,
    LicenseUseRestrictionRegistry,
    PopulationFrequencyAdapter,
    ReferenceAlphaState,
    ReferenceSnapshotManager,
)
from .reference_governance_contracts import (
    ReferenceGovernanceContractRegistry,
    default_reference_governance_contracts,
)
from .reference_governance_public_data import (
    REFERENCE_GOVERNANCE_CONTEXT_KEY,
    ReferenceGovernanceFixture,
    ReferenceGovernanceOperation,
    ReferenceGovernanceRecord,
    ReferenceGovernanceRole,
    build_reference_governance_catalog,
    default_reference_governance_fixture,
    load_reference_governance_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceCheck:
    """One observable evaluation assertion."""

    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceExecutionReceipt:
    """Sanitized operation result retaining states, counts, and issue codes."""

    record_id: str
    capability_id: str
    operation: ReferenceGovernanceOperation
    role: ReferenceGovernanceRole
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
            raise ValidationError("governance receipt counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.adapter_state == self.expected_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceEvaluationReport:
    """Whole-fixture report with one receipt and checks per record."""

    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[ReferenceGovernanceExecutionReceipt, ...]
    checks: tuple[ReferenceGovernanceCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(receipt.role is ReferenceGovernanceRole.POSITIVE for receipt in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(receipt.role is ReferenceGovernanceRole.CONTROL for receipt in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _state_value(value: ReferenceAlphaState | str) -> str:
    return value.value if isinstance(value, ReferenceAlphaState) else str(value)


def _check(check_id: str, record_id: str, passed: bool, detail: str) -> ReferenceGovernanceCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
    return ReferenceGovernanceCheck(check_id, record_id, passed, detail, _address(body))


def _issue_codes(result: Any, extra: tuple[str, ...] = ()) -> tuple[str, ...]:
    values = list(extra)
    values.extend(issue.code for issue in getattr(result, "issues", ()))
    return tuple(dict.fromkeys(values))


def _execute_record(
    record: ReferenceGovernanceRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    """Execute one fixture payload through the corresponding typed adapter."""

    payload = record.payload
    if record.operation is ReferenceGovernanceOperation.GENE_ALIAS:
        result = GeneAliasVersionResolver().resolve(
            payload["queries"], payload["records"], assembly=payload.get("assembly")
        )
        resolution = result.resolutions[0] if result.resolutions else None
        observed = _issue_codes(
            result, tuple(issue.code for issue in (resolution.issues if resolution else ()))
        )
        summary = {
            "catalog_state": _state_value(result.state),
            "record_count": len(result.records),
            "resolution_state": _state_value(resolution.state) if resolution else "abstained",
            "match_count": len(resolution.matches) if resolution else 0,
            "issue_codes": observed,
            "versioned_ids": tuple(
                match.versioned_id for match in (resolution.matches if resolution else ())
            ),
        }
        return (
            _state_value(result.state),
            len(result.records),
            len(resolution.matches) if resolution else 0,
            observed,
            summary,
        )
    if record.operation is ReferenceGovernanceOperation.POPULATION_FREQUENCY:
        result = PopulationFrequencyAdapter().adapt(
            payload["records"],
            genome_build=payload.get("genome_build"),
            variant_id=payload.get("variant_id"),
        )
        summary = {
            "observation_count": len(result.observations),
            "summary_count": len(result.summaries),
            "adaptation_state": _state_value(result.state),
            "issue_codes": _issue_codes(result),
            "frequency_range": (
                min(
                    (
                        item.allele_frequency
                        for item in result.observations
                        if item.allele_frequency is not None
                    ),
                    default=None,
                ),
                max(
                    (
                        item.allele_frequency
                        for item in result.observations
                        if item.allele_frequency is not None
                    ),
                    default=None,
                ),
            ),
            "population_ids": tuple(sorted({item.population_id for item in result.observations})),
        }
        return (
            _state_value(result.state),
            len(result.observations),
            len(result.summaries),
            _issue_codes(result),
            summary,
        )
    if record.operation is ReferenceGovernanceOperation.REFERENCE_SNAPSHOT:
        result = ReferenceSnapshotManager().build(
            payload["resources"],
            snapshot_id=payload["snapshot_id"],
            assembly=payload["assembly"],
            source_id=payload["source_id"],
            source_version=payload.get("source_version", "unspecified"),
            expected_manifest_hash=payload.get("expected_manifest_hash"),
        )
        state = _state_value(result.state)
        if payload.get("assembly") != "GRCh38" and state == "supported":
            state = "out_of_domain"
        observed = _issue_codes(result)
        summary = {
            "resource_count": len(result.resources),
            "manifest_hash": result.manifest_hash,
            "snapshot_state": state,
            "issue_codes": observed,
            "resource_ids": tuple(resource.resource_id for resource in result.resources),
            "license_ids": tuple(resource.license_id for resource in result.resources),
        }
        return state, len(result.resources), len(result.issues), observed, summary
    if record.operation is ReferenceGovernanceOperation.LICENSE_RESTRICTION:
        result = LicenseUseRestrictionRegistry().evaluate(
            payload["resources"],
            payload["restrictions"],
            requested_use=payload["requested_use"],
            redistribution=bool(payload.get("redistribution", False)),
            commercial=bool(payload.get("commercial", False)),
            as_of=payload.get("as_of"),
        )
        summary = {
            "decision_count": len(result.decisions),
            "allowed_count": sum(decision.allowed for decision in result.decisions),
            "missing_resource_ids": result.missing_resource_ids,
            "evaluation_state": _state_value(result.state),
            "issue_codes": _issue_codes(result),
            "attribution_count": sum(decision.needs_attribution for decision in result.decisions),
        }
        return (
            _state_value(result.state),
            len(result.decisions),
            len(result.missing_resource_ids),
            _issue_codes(result),
            summary,
        )
    raise ValidationError(f"unsupported governance operation: {record.operation}")


def evaluate_reference_governance_fixture(
    fixture: ReferenceGovernanceFixture | None = None,
    *,
    contracts: ReferenceGovernanceContractRegistry | None = None,
) -> ReferenceGovernanceEvaluationReport:
    """Execute every positive and review record against the existing adapters."""

    selected = fixture or default_reference_governance_fixture()
    registry = contracts or default_reference_governance_contracts()
    catalog = build_reference_governance_catalog(selected)
    checks: list[ReferenceGovernanceCheck] = []
    receipts: list[ReferenceGovernanceExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, record_id, passed, detail))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == REFERENCE_GOVERNANCE_CONTEXT_KEY,
        "fixture uses the exact governance context",
    )
    add(
        "fixture-address",
        "fixture",
        selected.content_address
        == _address(
            {key: value for key, value in selected.to_dict().items() if key != "content_address"}
        ),
        "fixture address verifies",
    )
    catalog_body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "source_ids": catalog.source_ids,
        "record_ids": catalog.record_ids,
        "operations": catalog.operations,
    }
    add(
        "catalog-address",
        "fixture",
        catalog.content_address == _address(catalog_body),
        "catalog address verifies",
    )
    for record in selected.records:
        contract = registry.by_operation(record.operation)
        missing = contract.validate_payload(record.payload)
        add(
            f"{record.record_id}:contract",
            record.record_id,
            not missing,
            "required execution fields are present",
        )
        try:
            state, primary, secondary, issue_codes, summary = _execute_record(record)
            execution_error = None
        except (TypeError, ValueError, ValidationError, KeyError, json.JSONDecodeError) as exc:
            state, primary, secondary, issue_codes, summary = (
                "invalid",
                0,
                0,
                ("execution_error",),
                {"error_type": type(exc).__name__},
            )
            execution_error = str(exc)
        check_ids = [f"{record.record_id}:contract"]
        state_check = f"{record.record_id}:state"
        add(
            state_check,
            record.record_id,
            state == record.expected_state and execution_error is None,
            "adapter state matches the fixture expectation",
        )
        check_ids.append(state_check)
        issue_check = f"{record.record_id}:issues"
        add(
            issue_check,
            record.record_id,
            set(record.expected_issue_codes) <= set(issue_codes),
            "expected issue codes remain visible",
        )
        check_ids.append(issue_check)
        count_check = f"{record.record_id}:counts"
        add(
            count_check,
            record.record_id,
            primary >= 0 and secondary >= 0,
            "sanitized counts are non-negative",
        )
        check_ids.append(count_check)
        role_check = f"{record.record_id}:role"
        role_ok = (record.role is ReferenceGovernanceRole.POSITIVE and state == "supported") or (
            record.role is ReferenceGovernanceRole.CONTROL and state != "supported"
        )
        add(
            role_check,
            record.record_id,
            role_ok,
            "positive and control role boundaries are respected",
        )
        check_ids.append(role_check)
        summary_check = f"{record.record_id}:summary"
        summary_ok = all(key in summary for key in ("issue_codes",))
        add(
            summary_check,
            record.record_id,
            summary_ok,
            "sanitized summary retains operational dimensions",
        )
        check_ids.append(summary_check)
        receipt_body = {
            "record_id": record.record_id,
            "capability_id": contract.capability_id,
            "operation": record.operation,
            "role": record.role,
            "context_key": selected.context_key,
            "adapter_state": state,
            "primary_count": primary,
            "secondary_count": secondary,
            "observed_issue_codes": issue_codes,
            "expected_state": record.expected_state,
            "expected_issue_codes": record.expected_issue_codes,
            "check_ids": tuple(check_ids),
            "summary": summary,
        }
        receipt = ReferenceGovernanceExecutionReceipt(
            **receipt_body, content_address=_address(receipt_body)
        )
        address_check = f"{record.record_id}:address"
        prior = tuple(check.passed for check in checks if check.record_id == record.record_id)
        add(
            address_check,
            record.record_id,
            receipt.accepted == all(prior),
            "receipt acceptance agrees with record checks",
        )
        check_ids.append(address_check)
        receipts.append(receipt)
    add(
        "receipt-count",
        "fixture",
        len(receipts) == len(selected.records),
        "one receipt is emitted per record",
    )
    add(
        "positive-count",
        "fixture",
        sum(item.role is ReferenceGovernanceRole.POSITIVE for item in receipts) == 4,
        "four positives are executed",
    )
    add(
        "control-count",
        "fixture",
        sum(item.role is ReferenceGovernanceRole.CONTROL for item in receipts) == 12,
        "twelve controls are executed",
    )
    add(
        "operation-coverage",
        "fixture",
        {item.operation for item in receipts} == set(ReferenceGovernanceOperation),
        "all four operation families execute",
    )
    add(
        "source-free-output",
        "fixture",
        all(
            "records" not in receipt.summary and "restrictions" not in receipt.summary
            for receipt in receipts
        ),
        "receipts do not copy input collections",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "catalog_address": catalog.content_address,
        "receipts": receipts,
        "checks": checks,
    }
    return ReferenceGovernanceEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        _address(body),
    )


def evaluate_reference_governance_fixture_file(
    path: str | Path,
) -> ReferenceGovernanceEvaluationReport:
    """Evaluate a JSON descriptor from disk."""

    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return evaluate_reference_governance_fixture(load_reference_governance_fixture(payload))


__all__ = [
    "ReferenceGovernanceCheck",
    "ReferenceGovernanceEvaluationReport",
    "ReferenceGovernanceExecutionReceipt",
    "evaluate_reference_governance_fixture",
    "evaluate_reference_governance_fixture_file",
]
