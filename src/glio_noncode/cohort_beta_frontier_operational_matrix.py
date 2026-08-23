"""Operational matrix for release owners, reviewers, and consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_beta_frontier_policy import CohortBetaFrontierDisposition
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationalRule:
    operation: str
    disposition: CohortBetaFrontierDisposition
    owner: str
    action: str
    evidence: tuple[str, ...]
    exit_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierOperationalMatrixReport:
    rules: tuple[CohortBetaFrontierOperationalRule, ...]
    accepted: bool
    content_address: str

    def rules_for(self, operation: str) -> tuple[CohortBetaFrontierOperationalRule, ...]:
        return tuple(item for item in self.rules if item.operation in {operation, "all"})

    def rules_for_disposition(self, disposition: CohortBetaFrontierDisposition) -> tuple[CohortBetaFrontierOperationalRule, ...]:
        return tuple(item for item in self.rules if item.disposition is disposition)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_operational_matrix() -> CohortBetaFrontierOperationalMatrixReport:
    raw = (
        ("all", CohortBetaFrontierDisposition.PUBLISH, "release owner", "emit bounded summary and receipt", ("quality gate", "replay", "claim boundary"), "manifest is ready"),
        ("all", CohortBetaFrontierDisposition.REVIEW, "operation owner", "collect missing comparator or definition evidence", ("review protocol", "source receipts", "change request"), "review decision is recorded"),
        ("all", CohortBetaFrontierDisposition.QUARANTINE, "release owner", "exclude row from target aggregate", ("context receipt", "error taxonomy", "lineage"), "context or contract is repaired"),
        ("C05", CohortBetaFrontierDisposition.PUBLISH, "cohort owner", "publish recurrence fraction with threshold receipt", ("distinct sample count", "hotspot window"), "claim ceiling remains attached"),
        ("C06", CohortBetaFrontierDisposition.PUBLISH, "cohort owner", "publish callable-space burden", ("callable bases", "background rate"), "denominator receipt is present"),
        ("C07", CohortBetaFrontierDisposition.PUBLISH, "functional owner", "publish feature convergence contrast", ("control support", "feature definition"), "matched comparator remains visible"),
        ("C08", CohortBetaFrontierDisposition.PUBLISH, "pathway owner", "publish set convergence summary", ("set version", "direction counts"), "no leading direction conflict"),
        ("C05", CohortBetaFrontierDisposition.REVIEW, "cohort owner", "request independent recurrence calibration", ("cohort transport", "callable null"), "calibration requirement is resolved"),
        ("C06", CohortBetaFrontierDisposition.REVIEW, "cohort owner", "request callable interval review", ("interval version", "background population"), "regional comparator is qualified"),
        ("C07", CohortBetaFrontierDisposition.REVIEW, "functional owner", "request matched control review", ("control selection", "feature provenance"), "control coverage is accepted"),
        ("C08", CohortBetaFrontierDisposition.REVIEW, "pathway owner", "request set transport review", ("set version", "overlap accounting"), "membership transport is accepted"),
        ("C05", CohortBetaFrontierDisposition.QUARANTINE, "release owner", "exclude foreign or non-callable recurrence", ("context key", "callable flag"), "row passes recurrence contract"),
        ("C06", CohortBetaFrontierDisposition.QUARANTINE, "release owner", "exclude foreign region or invalid denominator", ("context key", "callable bases"), "row passes burden contract"),
        ("C07", CohortBetaFrontierDisposition.QUARANTINE, "release owner", "exclude foreign or malformed feature evidence", ("context key", "support bounds"), "row passes feature contract"),
        ("C08", CohortBetaFrontierDisposition.QUARANTINE, "release owner", "exclude contradictory or foreign leading set evidence", ("direction", "set namespace"), "row passes set contract"),
    )
    rules = tuple(CohortBetaFrontierOperationalRule(operation, disposition, owner, action, evidence, exit_condition, content_hash({"operation": operation, "disposition": disposition, "owner": owner, "action": action, "evidence": evidence}, prefix="operational-rule")) for operation, disposition, owner, action, evidence, exit_condition in raw)
    return CohortBetaFrontierOperationalMatrixReport(rules, len(rules) == 15 and all(item.evidence and item.exit_condition for item in rules), content_hash(rules, prefix="operational-matrix"))


def operational_matrix_summary(report: CohortBetaFrontierOperationalMatrixReport) -> Mapping[str, Any]:
    return {"rule_count": len(report.rules), "accepted": report.accepted, "by_disposition": {disposition.value: len(report.rules_for_disposition(disposition)) for disposition in CohortBetaFrontierDisposition}, "by_operation": {operation: len(report.rules_for(operation)) for operation in ("C05", "C06", "C07", "C08")}}


__all__ = ["CohortBetaFrontierOperationalMatrixReport", "CohortBetaFrontierOperationalRule", "default_cohort_beta_frontier_operational_matrix", "operational_matrix_summary"]
