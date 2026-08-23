"""Reviewer protocol for resolving C05-C08 held paths."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from .cohort_beta_frontier_review import CohortBetaFrontierReviewQueue
from .serialization import content_hash, jsonable


class CohortBetaFrontierReviewOutcome(StrEnum):
    ACCEPT = "accept"
    RETAIN_PARTIAL = "retain_partial"
    QUARANTINE = "quarantine"
    RETURN_FOR_REPAIR = "return_for_repair"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewQuestion:
    question_id: str
    operation: str
    prompt: str
    evidence_required: tuple[str, ...]
    blocking: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewDecision:
    record_id: str
    outcome: CohortBetaFrontierReviewOutcome
    answered_questions: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    note: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierReviewProtocol:
    questions: tuple[CohortBetaFrontierReviewQuestion, ...]
    decisions: tuple[CohortBetaFrontierReviewDecision, ...]
    accepted: bool
    content_address: str

    def questions_for(self, operation: str) -> tuple[CohortBetaFrontierReviewQuestion, ...]:
        return tuple(item for item in self.questions if item.operation in {operation, "all"})

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_cohort_beta_frontier_review_questions() -> tuple[CohortBetaFrontierReviewQuestion, ...]:
    raw = (("context", "all", "Does the row exactly match the requested context?", ("context receipt",), True), ("source", "all", "Are the source receipts public and versioned?", ("source URL", "source version"), True), ("comparator", "C06", "Is callable-space and comparator accounting complete?", ("callable bases", "background rate"), True), ("comparator", "C07", "Are matched controls available and comparable?", ("control rows", "feature definition"), True), ("comparator", "C08", "Are set definitions versioned and directionally consistent?", ("set version", "direction fields"), True), ("recurrence", "C05", "Are recurrence and hotspot thresholds declared?", ("threshold receipt",), True), ("claims", "all", "Does the proposed wording stay within the claim ceiling?", ("claim boundary",), True), ("repair", "all", "Can the held row be repaired without changing its operation contract?", ("change request",), False))
    return tuple(CohortBetaFrontierReviewQuestion(question_id, operation, prompt, evidence, blocking, content_hash({"question_id": question_id, "operation": operation, "prompt": prompt}, prefix="review-question")) for question_id, operation, prompt, evidence, blocking in raw)


def build_cohort_beta_frontier_review_protocol(queue: CohortBetaFrontierReviewQueue, questions: tuple[CohortBetaFrontierReviewQuestion, ...] | None = None) -> CohortBetaFrontierReviewProtocol:
    selected = questions or default_cohort_beta_frontier_review_questions()
    decisions = []
    for item in queue.items:
        applicable = tuple(question.question_id for question in selected if question.operation in {item.operation, "all"})
        unresolved = tuple(question_id for question_id in applicable if question_id in {"context", "source", "comparator", "claims"})
        outcome = CohortBetaFrontierReviewOutcome.QUARANTINE if item.priority == 1 else CohortBetaFrontierReviewOutcome.RETAIN_PARTIAL
        decisions.append(CohortBetaFrontierReviewDecision(item.record_id, outcome, (), unresolved, "review starts with evidence collection; no state is silently promoted", content_hash({"record_id": item.record_id, "outcome": outcome, "unresolved": unresolved}, prefix="review-decision")))
    values = tuple(decisions)
    return CohortBetaFrontierReviewProtocol(selected, values, len(values) == queue.open_count and all(item.unresolved_questions for item in values), content_hash({"questions": selected, "decisions": values}, prefix="review-protocol"))


def review_protocol_summary(protocol: CohortBetaFrontierReviewProtocol) -> Mapping[str, Any]:
    return {"question_count": len(protocol.questions), "decision_count": len(protocol.decisions), "accepted": protocol.accepted, "outcomes": {outcome.value: sum(item.outcome is outcome for item in protocol.decisions) for outcome in CohortBetaFrontierReviewOutcome}}


__all__ = ["CohortBetaFrontierReviewDecision", "CohortBetaFrontierReviewOutcome", "CohortBetaFrontierReviewProtocol", "CohortBetaFrontierReviewQuestion", "build_cohort_beta_frontier_review_protocol", "default_cohort_beta_frontier_review_questions", "review_protocol_summary"]
