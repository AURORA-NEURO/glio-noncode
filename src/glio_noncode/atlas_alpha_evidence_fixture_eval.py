"""Deterministic execution receipts for Domain 05 C09-C12."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .atlas_alpha import (
    AtlasAlphaState,
    EnhancerPromoterSilencerClassifier,
    MethylationTrackHarmonizer,
    OpenChromatinTrackHarmonizer,
    SuperEnhancerCandidateAtlas,
)
from .atlas_alpha_evidence_contracts import (
    AtlasAlphaEvidenceContractRegistry,
    default_atlas_alpha_evidence_contracts,
)
from .atlas_alpha_evidence_public_data import (
    ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    AtlasAlphaEvidenceFixture,
    AtlasAlphaEvidenceOperation,
    AtlasAlphaEvidenceRecord,
    AtlasAlphaEvidenceRole,
    build_atlas_alpha_evidence_catalog,
    default_atlas_alpha_evidence_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceCheck:
    """One observable fixture assertion."""

    check_id: str
    record_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceExecutionReceipt:
    """Sanitized adapter result with no payload text."""

    record_id: str
    capability_id: str
    operation: AtlasAlphaEvidenceOperation
    role: AtlasAlphaEvidenceRole
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
            raise ValidationError("atlas alpha receipt counts cannot be negative")

    @property
    def accepted(self) -> bool:
        return self.adapter_state == self.expected_state and not set(
            self.expected_issue_codes
        ) - set(self.observed_issue_codes)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceEvaluationReport:
    """Whole-fixture report with one receipt per record."""

    fixture_id: str
    fixture_version: str
    context_key: str
    catalog_address: str
    receipts: tuple[AtlasAlphaEvidenceExecutionReceipt, ...]
    checks: tuple[AtlasAlphaEvidenceCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    @property
    def positive_count(self) -> int:
        return sum(receipt.role is AtlasAlphaEvidenceRole.POSITIVE for receipt in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(receipt.role is AtlasAlphaEvidenceRole.CONTROL for receipt in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _state(value: Any) -> str:
    return value.value if isinstance(value, AtlasAlphaState) else str(value)


def _check(check_id: str, record_id: str, passed: bool, detail: str) -> AtlasAlphaEvidenceCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
    return AtlasAlphaEvidenceCheck(check_id, record_id, passed, detail, content_hash(body))


def _rows(record: AtlasAlphaEvidenceRecord) -> list[dict[str, Any]]:
    payload = json.loads(str(record.payload["input_text"]))
    rows = payload.get("records", payload.get("observations", payload.get("elements", ())))
    if not isinstance(rows, list):
        raise ValidationError("atlas alpha fixture input must contain a records list")
    return rows


def _execute(
    record: AtlasAlphaEvidenceRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    payload = record.payload
    rows = _rows(record)
    if record.operation is AtlasAlphaEvidenceOperation.OPEN_CHROMATIN:
        result = OpenChromatinTrackHarmonizer().harmonize(
            rows,
            context_key=record.context_key,
            spread_tolerance=float(payload["spread_tolerance"]),
            minimum_signal=float(payload["minimum_signal"]),
        )
        issues = [issue.code for issue in result.issues]
        if result.state is AtlasAlphaState.AMBIGUOUS:
            issues.append("open_chromatin_signal_disagreement")
        summary = {
            "state": _state(result.state),
            "interval_count": len(result.intervals),
            "observation_count": len(result.observations),
            "replicate_counts": tuple(sorted(len(item.replicate_ids) for item in result.intervals)),
            "signal_spreads": tuple(item.signal_spread for item in result.intervals),
            "issue_codes": tuple(dict.fromkeys(issues)),
            "warning_count": len(result.warnings),
        }
        return (
            _state(result.state),
            len(result.observations),
            len(result.intervals),
            tuple(dict.fromkeys(issues)),
            summary,
        )
    if record.operation is AtlasAlphaEvidenceOperation.METHYLATION:
        result = MethylationTrackHarmonizer().harmonize(
            rows,
            context_key=record.context_key,
            spread_tolerance=float(payload["spread_tolerance"]),
        )
        issues = [issue.code for issue in result.issues]
        if result.state is AtlasAlphaState.AMBIGUOUS:
            issues.append("methylation_fraction_disagreement")
        if any(
            item.state is AtlasAlphaState.PARTIAL and item.total_count == 0
            for item in result.intervals
        ):
            issues.append("methylation_zero_coverage")
        summary = {
            "state": _state(result.state),
            "interval_count": len(result.intervals),
            "observation_count": len(result.observations),
            "coverage_totals": tuple(item.total_count for item in result.intervals),
            "fraction_spreads": tuple(item.fraction_spread for item in result.intervals),
            "issue_codes": tuple(dict.fromkeys(issues)),
            "warning_count": len(result.warnings),
        }
        return (
            _state(result.state),
            len(result.observations),
            len(result.intervals),
            tuple(dict.fromkeys(issues)),
            summary,
        )
    if record.operation is AtlasAlphaEvidenceOperation.REGULATORY_ROLE:
        result = EnhancerPromoterSilencerClassifier().classify(
            rows,
            context_key=record.context_key,
            role_threshold=float(payload["role_threshold"]),
            methylation_silencer_threshold=float(payload["methylation_silencer_threshold"]),
        )
        issues = [issue.code for issue in result.issues]
        if result.state is AtlasAlphaState.AMBIGUOUS:
            issues.append("regulatory_role_ambiguity")
        if any(item.missing_channels for item in result.classifications):
            issues.append("regulatory_role_missing_channels")
        summary = {
            "state": _state(result.state),
            "classification_count": len(result.classifications),
            "roles": tuple(item.roles for item in result.classifications),
            "missing_channels": tuple(item.missing_channels for item in result.classifications),
            "target_gene_ids": tuple(
                sorted({gene for item in result.classifications for gene in item.target_gene_ids})
            ),
            "issue_codes": tuple(dict.fromkeys(issues)),
            "warning_count": len(result.warnings),
        }
        return (
            _state(result.state),
            len(result.observations),
            len(result.classifications),
            tuple(dict.fromkeys(issues)),
            summary,
        )
    if record.operation is AtlasAlphaEvidenceOperation.SUPER_ENHANCER:
        result = SuperEnhancerCandidateAtlas().build(
            rows,
            context_key=record.context_key,
            minimum_constituents=int(payload["minimum_constituents"]),
            merge_gap_bp=int(payload["merge_gap_bp"]),
            rank_quantile=float(payload["rank_quantile"]),
        )
        issues = [issue.code for issue in result.issues]
        if not result.candidates and result.state is AtlasAlphaState.ABSTAINED:
            issues.append("no_super_enhancer_candidate")
        if any(candidate.state is AtlasAlphaState.PARTIAL for candidate in result.candidates):
            issues.append("super_enhancer_partial_activity")
        summary = {
            "state": _state(result.state),
            "constituent_count": len(result.constituents),
            "candidate_count": len(result.candidates),
            "candidate_ids": tuple(item.candidate_id for item in result.candidates),
            "target_gene_ids": tuple(
                sorted({gene for item in result.candidates for gene in item.target_gene_ids})
            ),
            "issue_codes": tuple(dict.fromkeys(issues)),
            "warning_count": len(result.warnings),
        }
        return (
            _state(result.state),
            len(result.constituents),
            len(result.candidates),
            tuple(dict.fromkeys(issues)),
            summary,
        )
    raise ValidationError(f"unsupported atlas alpha operation {record.operation}")


def evaluate_atlas_alpha_evidence_fixture(
    fixture: AtlasAlphaEvidenceFixture | None = None,
    *,
    contracts: AtlasAlphaEvidenceContractRegistry | None = None,
) -> AtlasAlphaEvidenceEvaluationReport:
    """Execute positive and control records against the existing alpha adapters."""

    selected = fixture or default_atlas_alpha_evidence_fixture()
    registry = contracts or default_atlas_alpha_evidence_contracts()
    catalog = build_atlas_alpha_evidence_catalog(selected)
    checks: list[AtlasAlphaEvidenceCheck] = []
    receipts: list[AtlasAlphaEvidenceExecutionReceipt] = []

    def add(check_id: str, record_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, record_id, passed, detail))

    add(
        "fixture-context",
        "fixture",
        selected.context_key == ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
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
        add(
            role_id,
            record.record_id,
            (record.role is AtlasAlphaEvidenceRole.POSITIVE)
            == (record.expected_state == "supported"),
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
        receipt = AtlasAlphaEvidenceExecutionReceipt(**body, content_address=content_hash(body))
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
        sum(receipt.role is AtlasAlphaEvidenceRole.POSITIVE for receipt in receipts) == 4,
        "four positive records execute",
    )
    add(
        "control-count",
        "fixture",
        sum(receipt.role is AtlasAlphaEvidenceRole.CONTROL for receipt in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-balance",
        "fixture",
        {receipt.operation for receipt in receipts} == set(AtlasAlphaEvidenceOperation),
        "every operation executes",
    )
    add(
        "sanitized-receipts",
        "fixture",
        all(
            not {"input_text", "payload", "records"} & set(receipt.summary) for receipt in receipts
        ),
        "receipts exclude input payloads",
    )
    add(
        "positive-state-floor",
        "fixture",
        all(
            receipt.adapter_state == "supported"
            for receipt in receipts
            if receipt.role is AtlasAlphaEvidenceRole.POSITIVE
        ),
        "positive records remain supported",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "catalog_address": catalog.content_address,
        "receipts": receipts,
        "checks": checks,
    }
    return AtlasAlphaEvidenceEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        catalog.content_address,
        tuple(receipts),
        tuple(checks),
        content_hash(body),
    )


__all__ = [
    "AtlasAlphaEvidenceCheck",
    "AtlasAlphaEvidenceEvaluationReport",
    "AtlasAlphaEvidenceExecutionReceipt",
    "evaluate_atlas_alpha_evidence_fixture",
]
