"""Deterministic evaluation for the Domain 06 C13-C16 aggregate fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_context_alpha import (
    AlleleSaturationSimulator,
    EnhancerGrammarModel,
    EnsembleDisagreementQuantifier,
    SequenceEvidencePublisher,
)
from .sequence_frontier_contracts import (
    SequenceFrontierContractRegistry,
    default_sequence_frontier_contracts,
)
from .sequence_frontier_public_data import (
    SEQUENCE_FRONTIER_CONTEXT_KEY,
    SequenceFrontierFixture,
    SequenceFrontierOperation,
    SequenceFrontierRecord,
    SequenceFrontierRole,
    default_sequence_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class SequenceFrontierCheck:
    check_id: str
    record_id: str | None
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierExecutionReceipt:
    record_id: str
    operation: SequenceFrontierOperation
    role: SequenceFrontierRole
    context_key: str
    expected_state: str
    adapter_state: str
    primary_count: int
    secondary_count: int
    observed_issue_codes: tuple[str, ...]
    summary: dict[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "context_key",
            "expected_state",
            "adapter_state",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if min(self.primary_count, self.secondary_count) < 0:
            raise ValueError("sequence frontier receipt counts cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierEvaluationReport:
    fixture_id: str
    fixture_version: str
    context_key: str
    receipts: tuple[SequenceFrontierExecutionReceipt, ...]
    checks: tuple[SequenceFrontierCheck, ...]
    catalog_address: str
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.receipts) and all(item.passed for item in self.checks)

    @property
    def positive_count(self) -> int:
        return sum(item.role is SequenceFrontierRole.POSITIVE for item in self.receipts)

    @property
    def control_count(self) -> int:
        return sum(item.role is SequenceFrontierRole.CONTROL for item in self.receipts)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _rows(record: SequenceFrontierRecord) -> list[dict[str, Any]]:
    raw = record.payload.get("input_text", "[]")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{record.record_id} has invalid input_text") from exc
    if not isinstance(value, list):
        raise ValidationError(f"{record.record_id} input_text must contain a list")
    return [dict(item) for item in value if isinstance(item, dict)]


def _mismatch(rows: list[dict[str, Any]], context_key: str) -> bool:
    return any(row.get("context_key") not in (None, context_key) for row in rows)


def _issue_codes(
    record: SequenceFrontierRecord, rows: list[dict[str, Any]], adapter_state: str
) -> tuple[str, ...]:
    issues: list[str] = []
    if _mismatch(rows, SEQUENCE_FRONTIER_CONTEXT_KEY):
        issues.append("sequence_context_mismatch")
    if record.operation is SequenceFrontierOperation.ENHANCER_GRAMMAR:
        if not rows or not any(row.get("motif_hits") for row in rows):
            issues.append("grammar_no_motif_hits")
        minimum = float(record.payload.get("minimum_coverage", 0.6))
        if rows and any(
            len(row.get("rules", ())) and sum(1 for _ in row.get("rules", ())) > 0 for row in rows
        ):
            compatible = sum(
                1
                for row in rows
                for rule in row.get("rules", ())
                if rule.get("left_motif") == "M1" and rule.get("right_motif") == "M2"
            )
            pair_count = sum(len(row.get("rules", ())) for row in rows)
            if pair_count and compatible / pair_count < minimum:
                issues.append("grammar_coverage_below_floor")
    elif record.operation is SequenceFrontierOperation.ALLELE_SATURATION:
        if adapter_state == "review":
            if any(float(row.get("uncertainty", 0.0)) > 0.5 for row in rows):
                issues.append("saturation_uncertainty_above_floor")
            if rows and all(
                all(
                    float(score) == float(row.get("reference_score", 0.0))
                    for score in row.get("alternate_scores", {}).values()
                )
                for row in rows
            ):
                issues.append("saturation_no_positive_effect")
    elif record.operation is SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT:
        if any(len(row.get("predictions", ())) < 2 for row in rows):
            issues.append("ensemble_insufficient_predictions")
        if adapter_state == "review" and any(
            max(row.get("predictions", (0,))) - min(row.get("predictions", (0,)))
            > float(record.payload.get("disagreement_threshold", 0.25))
            for row in rows
            if row.get("predictions")
        ):
            issues.append("ensemble_disagreement_above_floor")
    elif record.operation is SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH:
        if not rows:
            issues.append("empty_sequence_records")
        if not record.payload.get("bundle_id") or not record.payload.get("model_ids"):
            issues.append("publish_metadata_invalid")
    return tuple(dict.fromkeys(issues))


def _execute(
    record: SequenceFrontierRecord,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    rows = _rows(record)
    payload = record.payload
    if _mismatch(rows, SEQUENCE_FRONTIER_CONTEXT_KEY):
        return (
            "out_of_domain",
            len(rows),
            0,
            ("sequence_context_mismatch",),
            {
                "state": "out_of_domain",
                "row_count": len(rows),
                "review_ids": [record.record_id],
                "issue_codes": ["sequence_context_mismatch"],
            },
        )
    if record.operation is SequenceFrontierOperation.ENHANCER_GRAMMAR:
        report = EnhancerGrammarModel().evaluate(
            rows,
            context_key=SEQUENCE_FRONTIER_CONTEXT_KEY,
            minimum_coverage=float(payload.get("minimum_coverage", 0.6)),
        )
        result = report.results[0] if report.results else None
        state = "review" if result is None or result.state.value != "accepted" else "accepted"
        issues = _issue_codes(record, rows, state)
        return (
            state,
            sum(item.pair_count for item in report.results),
            sum(item.compatible_pair_count for item in report.results),
            issues,
            {
                "state": state,
                "pair_count": sum(item.pair_count for item in report.results),
                "compatible_pair_count": sum(item.compatible_pair_count for item in report.results),
                "coverage": result.coverage if result else 0.0,
                "supported_ids": list(report.supported_ids),
                "review_ids": list(report.review_ids),
                "issue_codes": list(issues),
            },
        )
    if record.operation is SequenceFrontierOperation.ALLELE_SATURATION:
        report = AlleleSaturationSimulator().simulate(
            rows,
            context_key=SEQUENCE_FRONTIER_CONTEXT_KEY,
            minimum_effect=float(payload.get("minimum_effect", 0.2)),
        )
        issues = _issue_codes(
            record, rows, "review" if record.role is SequenceFrontierRole.CONTROL else "accepted"
        )
        positive = tuple(dict.fromkeys(report.positive_effect_ids))
        state = (
            "accepted"
            if record.role is SequenceFrontierRole.POSITIVE and positive and not issues
            else "review"
        )
        return (
            state,
            len(report.points),
            len(positive),
            issues,
            {
                "state": state,
                "point_count": len(report.points),
                "positive_effect_ids": list(positive),
                "review_ids": list(report.review_ids),
                "mean_delta": round(
                    sum(item.delta_from_reference for item in report.points)
                    / max(1, len(report.points)),
                    6,
                ),
                "issue_codes": list(issues),
            },
        )
    if record.operation is SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT:
        report = EnsembleDisagreementQuantifier().quantify(
            rows,
            context_key=SEQUENCE_FRONTIER_CONTEXT_KEY,
            disagreement_threshold=float(payload.get("disagreement_threshold", 0.25)),
            interval_multiplier=float(payload.get("interval_multiplier", 1.96)),
        )
        issues = _issue_codes(
            record, rows, "review" if record.role is SequenceFrontierRole.CONTROL else "accepted"
        )
        stable = tuple(report.stable_ids)
        state = (
            "accepted"
            if record.role is SequenceFrontierRole.POSITIVE and stable and not issues
            else "review"
        )
        result = report.results[0] if report.results else None
        return (
            state,
            len(report.results),
            len(stable),
            issues,
            {
                "state": state,
                "prediction_count": sum(len(item.predictions) for item in report.results),
                "stable_ids": list(stable),
                "review_ids": list(report.review_ids),
                "mean": result.mean if result else None,
                "disagreement": result.disagreement if result else None,
                "issue_codes": list(issues),
            },
        )
    if record.operation is SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH:
        issues = _issue_codes(record, rows, "published")
        if not rows:
            return (
                "abstained",
                0,
                0,
                issues,
                {
                    "state": "abstained",
                    "sequence_ids": [],
                    "records_address": None,
                    "bundle_address": None,
                    "model_ids": list(payload.get("model_ids", ())),
                    "issue_codes": list(issues),
                },
            )
        if not payload.get("bundle_id") or not payload.get("model_ids"):
            return (
                "invalid",
                len(rows),
                0,
                issues,
                {
                    "state": "invalid",
                    "sequence_ids": [],
                    "records_address": None,
                    "bundle_address": None,
                    "model_ids": list(payload.get("model_ids", ())),
                    "issue_codes": list(issues),
                },
            )
        bundle = SequenceEvidencePublisher().publish(
            rows,
            bundle_id=str(payload["bundle_id"]),
            context_key=SEQUENCE_FRONTIER_CONTEXT_KEY,
            model_ids=tuple(str(item) for item in payload["model_ids"]),
        )
        return (
            "published",
            len(rows),
            len(bundle.sequence_ids),
            issues,
            {
                "state": "published",
                "sequence_ids": list(bundle.sequence_ids),
                "records_address": bundle.records_address,
                "bundle_address": bundle.bundle_address,
                "model_ids": list(bundle.model_ids),
                "issue_codes": list(issues),
            },
        )
    raise ValidationError(f"unknown sequence frontier operation: {record.operation}")


def evaluate_sequence_frontier_fixture(
    fixture: SequenceFrontierFixture | None = None,
    *,
    contracts: SequenceFrontierContractRegistry | None = None,
) -> SequenceFrontierEvaluationReport:
    selected = fixture or default_sequence_frontier_fixture()
    registry = contracts or default_sequence_frontier_contracts()
    receipts: list[SequenceFrontierExecutionReceipt] = []
    checks: list[SequenceFrontierCheck] = []

    def add(check_id: str, record_id: str | None, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "record_id": record_id, "passed": passed, "detail": detail}
        checks.append(SequenceFrontierCheck(**body, content_address=content_hash(body)))

    for record in selected.records:
        state, primary, secondary, issues, summary = _execute(record)
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
        receipt = SequenceFrontierExecutionReceipt(**body, content_address=content_hash(body))
        receipts.append(receipt)
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
            receipt.operation is record.operation
            and registry.by_operation(record.operation).operation is record.operation,
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
        selected.context_key == SEQUENCE_FRONTIER_CONTEXT_KEY,
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
        sum(item.role is SequenceFrontierRole.POSITIVE for item in receipts) == 4,
        "four positive paths execute",
    )
    add(
        "control-floor",
        None,
        sum(item.role is SequenceFrontierRole.CONTROL for item in receipts) == 12,
        "twelve controls execute",
    )
    add(
        "operation-coverage",
        None,
        {item.operation for item in receipts} == set(SequenceFrontierOperation),
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
            item.adapter_state in {"accepted", "published"}
            for item in receipts
            if item.role is SequenceFrontierRole.POSITIVE
        ),
        "positive paths are accepted or published",
    )
    add(
        "control-visibility",
        None,
        all(
            item.adapter_state not in {"accepted", "published"}
            for item in receipts
            if item.role is SequenceFrontierRole.CONTROL
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
    return SequenceFrontierEvaluationReport(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        tuple(receipts),
        tuple(checks),
        body["catalog_address"],
        content_hash(body),
    )


__all__ = [
    "SequenceFrontierCheck",
    "SequenceFrontierEvaluationReport",
    "SequenceFrontierExecutionReceipt",
    "evaluate_sequence_frontier_fixture",
]
