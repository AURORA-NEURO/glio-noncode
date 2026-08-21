"""External-alpha evidence lifecycle review contracts.

Domain 14 external-alpha adds the operational records that sit around an
immutable evidence graph: blinded adjudication packets, append-only reviewer
comments and change logs, research-only release decisions, and evidence delta
reports.  Every surface retains exact context, content addresses, source
receipts, and unresolved conditions.  A release decision is a review record;
it is never a clinical, treatment, efficacy, or causal authorization.

The module deliberately keeps adjudication inputs separate from their source
labels.  Blinded cases expose evidence digests and masked receipts while the
workflow retains an internal mapping needed to reconcile a later decision.
Review comments and changes are immutable snapshots that can be appended to a
new snapshot without mutating an earlier review record.  Delta detection
compares historical graph content rather than averaging or promoting changed
claims.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .evidence_lifecycle import (
    EvidenceCitation,
    EvidenceGraphSnapshot,
    LifecycleState,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from .serialization import content_hash, jsonable, require_non_empty, utc_now


class LifecycleAlphaState(StrEnum):
    """State for an external-alpha lifecycle review artifact."""

    READY_FOR_REVIEW = "ready_for_review"
    ADJUDICATED = "adjudicated"
    REVIEW_REQUIRED = "review_required"
    SPLIT_DECISION = "split_decision"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class AdjudicationVerdict(StrEnum):
    """Permitted blinded reviewer verdicts."""

    SUPPORTS = "supports"
    AGAINST = "against"
    ABSTAIN = "abstain"
    INCONCLUSIVE = "inconclusive"


class CommentState(StrEnum):
    """Append-only review comment disposition."""

    OPEN = "open"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"
    SUPERSEDED = "superseded"


class ReleaseDecision(StrEnum):
    """Research dossier release decisions."""

    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REJECTED = "rejected"


class EvidenceDeltaKind(StrEnum):
    """Change classes emitted by the evidence delta detector."""

    CLAIM_ADDED = "claim_added"
    CLAIM_REMOVED = "claim_removed"
    CLAIM_CHANGED = "claim_changed"
    CITATION_ADDED = "citation_added"
    CITATION_REMOVED = "citation_removed"
    CITATION_CHANGED = "citation_changed"
    GRAPH_STATE_CHANGED = "graph_state_changed"
    CONTEXT_CHANGED = "context_changed"


@dataclass(frozen=True, slots=True)
class LifecycleAlphaIssue:
    """Quarantined lifecycle row with a deterministic raw receipt."""

    code: str
    message: str
    raw_hash: str
    severity: str = "warning"
    row_number: int | None = None
    context_key: str | None = None
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "lifecycle alpha issue code")
        require_non_empty(self.message, "lifecycle alpha issue message")
        require_non_empty(self.raw_hash, "lifecycle alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("lifecycle alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BlindedAdjudicationObservation:
    """One source-bearing evidence bundle prepared for masking."""

    observation_id: str
    claim_id: str
    edge_id: str
    context_key: str
    evidence_digest: str
    source_ids: tuple[str, ...]
    source_versions: Mapping[str, str]
    source_receipt_hash: str
    raw_hash: str
    summary: str = ""
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "claim_id",
            "edge_id",
            "context_key",
            "evidence_digest",
            "source_receipt_hash",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("blinded adjudication observation requires source IDs")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("blinded adjudication source IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BlindedAdjudicationCase:
    """Masked case presented to reviewers.

    The private claim and source fields are retained only for reconciliation;
    ``to_dict`` intentionally omits them so exported packets remain blinded.
    """

    case_id: str
    workflow_id: str
    blind_token: str
    position: int
    context_key: str
    evidence_digest: str
    masked_claim_receipt: str
    masked_source_receipt: str
    required_decisions: int
    instructions: tuple[str, ...]
    _claim_id: str = field(repr=False)
    _source_ids: tuple[str, ...] = field(repr=False)
    _edge_id: str = field(repr=False)

    def __post_init__(self) -> None:
        for name in (
            "case_id",
            "workflow_id",
            "blind_token",
            "evidence_digest",
            "masked_claim_receipt",
            "masked_source_receipt",
            "_claim_id",
            "_edge_id",
        ):
            require_non_empty(str(getattr(self, name)), name.removeprefix("_"))
        if self.position < 1 or self.required_decisions < 1:
            raise ValidationError("blinded case position and required_decisions must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "workflow_id": self.workflow_id,
            "blind_token": self.blind_token,
            "position": self.position,
            "context_key": self.context_key,
            "evidence_digest": self.evidence_digest,
            "masked_claim_receipt": self.masked_claim_receipt,
            "masked_source_receipt": self.masked_source_receipt,
            "required_decisions": self.required_decisions,
            "instructions": list(self.instructions),
        }


@dataclass(frozen=True, slots=True)
class BlindedAdjudicationPlan:
    """Content-addressed blinded review packet."""

    workflow_id: str
    context_key: str
    state: LifecycleAlphaState
    cases: tuple[BlindedAdjudicationCase, ...]
    reviewer_tokens: tuple[str, ...]
    required_decisions: int
    randomization_seed: str
    issues: tuple[LifecycleAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> BlindedAdjudicationPlan:
        """Rehydrate an exported masked packet for decision reconciliation."""

        if not isinstance(raw, Mapping):
            raise ValidationError("blinded adjudication plan must be a mapping")
        cases: list[BlindedAdjudicationCase] = []
        for index, value in enumerate(raw.get("cases", ()), start=1):
            if not isinstance(value, Mapping):
                raise ValidationError("blinded adjudication case must be a mapping")
            claim_receipt = str(value.get("masked_claim_receipt", f"masked-claim:{index}"))
            cases.append(
                BlindedAdjudicationCase(
                    case_id=str(value.get("case_id", f"case-{index}")),
                    workflow_id=str(
                        value.get("workflow_id", raw.get("workflow_id", "blinded-review"))
                    ),
                    blind_token=str(value.get("blind_token", f"blind-{index}")),
                    position=int(value.get("position", index)),
                    context_key=str(value.get("context_key", raw.get("context_key", ""))),
                    evidence_digest=str(value.get("evidence_digest", "masked-evidence")),
                    masked_claim_receipt=claim_receipt,
                    masked_source_receipt=str(value.get("masked_source_receipt", "masked-source")),
                    required_decisions=int(
                        value.get("required_decisions", raw.get("required_decisions", 1))
                    ),
                    instructions=tuple(str(item) for item in value.get("instructions", ())),
                    _claim_id=claim_receipt,
                    _source_ids=(),
                    _edge_id="masked-edge",
                )
            )
        return cls(
            workflow_id=str(raw.get("workflow_id", "blinded-review")),
            context_key=str(raw.get("context_key", "")),
            state=LifecycleAlphaState(
                str(raw.get("state", LifecycleAlphaState.READY_FOR_REVIEW.value))
            ),
            cases=tuple(cases),
            reviewer_tokens=tuple(str(item) for item in raw.get("reviewer_tokens", ())),
            required_decisions=int(raw.get("required_decisions", 1)),
            randomization_seed=str(raw.get("randomization_seed", "seed-1")),
            issues=tuple(
                LifecycleAlphaIssue(
                    code=str(item.get("code", "plan_issue")),
                    message=str(item.get("message", "exported plan issue")),
                    raw_hash=str(item.get("raw_hash", content_hash(item))),
                    severity=str(item.get("severity", "warning")),
                    row_number=(
                        None if item.get("row_number") is None else int(item["row_number"])
                    ),
                    context_key=(
                        None if item.get("context_key") is None else str(item["context_key"])
                    ),
                    raw_record=dict(item.get("raw_record", {})),
                )
                for item in raw.get("issues", ())
                if isinstance(item, Mapping)
            ),
            warnings=tuple(str(item) for item in raw.get("warnings", ())),
            content_address=str(raw.get("content_address", content_hash(dict(raw)))),
        )

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        for key in ("_claim_id", "_source_ids", "_edge_id"):
            payload.pop(key, None)
        payload["cases"] = [case.to_dict() for case in self.cases]
        return payload


@dataclass(frozen=True, slots=True)
class BlindedAdjudicationDecision:
    """One decision submitted against a masked case."""

    decision_id: str
    case_id: str
    reviewer_token: str
    verdict: AdjudicationVerdict
    confidence: float
    rationale: str
    context_key: str
    raw_hash: str
    submitted_at: str

    def __post_init__(self) -> None:
        for name in (
            "decision_id",
            "case_id",
            "reviewer_token",
            "rationale",
            "context_key",
            "raw_hash",
            "submitted_at",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.confidence <= 1:
            raise ValidationError("adjudication decision confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BlindedCaseAdjudication:
    """Reconciled masked-case decision summary without unmasking evidence."""

    case_id: str
    state: LifecycleAlphaState
    verdicts: tuple[AdjudicationVerdict, ...]
    decision_ids: tuple[str, ...]
    agreement: float
    decision_count: int
    required_decisions: int
    unresolved_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BlindedAdjudicationResult:
    """Adjudication output that keeps source labels masked."""

    workflow_id: str
    context_key: str
    state: LifecycleAlphaState
    plan_address: str
    cases: tuple[BlindedCaseAdjudication, ...]
    decisions: tuple[BlindedAdjudicationDecision, ...]
    unresolved_case_ids: tuple[str, ...]
    issues: tuple[LifecycleAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class BlindedAdjudicationWorkflow:
    """Plan and reconcile blinded, exact-context evidence adjudication."""

    def plan(
        self,
        observations: Iterable[BlindedAdjudicationObservation | Mapping[str, Any]],
        *,
        workflow_id: str = "blinded-review",
        context_key: str,
        reviewer_count: int = 2,
        required_decisions: int | None = None,
        randomization_seed: str = "seed-1",
    ) -> BlindedAdjudicationPlan:
        require_non_empty(workflow_id, "workflow_id")
        require_non_empty(context_key, "context_key")
        require_non_empty(randomization_seed, "randomization_seed")
        if reviewer_count < 1:
            raise ValidationError("reviewer_count must be positive")
        decisions_required = required_decisions or reviewer_count
        if decisions_required < 1 or decisions_required > reviewer_count:
            raise ValidationError("required_decisions must be within reviewer_count")
        values = tuple(observations)
        issues: list[LifecycleAlphaIssue] = []
        parsed: list[BlindedAdjudicationObservation] = []
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_blinded_observation(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LifecycleAlphaIssue(
                        "invalid_blinded_observation",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if item.context_key != context_key:
                issues.append(
                    LifecycleAlphaIssue(
                        "context_mismatch",
                        "blinded observation is outside the requested graph context",
                        item.raw_hash,
                        severity="warning",
                        row_number=row_number,
                        context_key=item.context_key,
                    )
                )
                continue
            parsed.append(item)
        if len({item.claim_id for item in parsed}) != len(parsed):
            issues.append(
                LifecycleAlphaIssue(
                    "duplicate_claim_id",
                    "one blinded packet cannot contain duplicate claim IDs",
                    content_hash(parsed),
                    severity="error",
                )
            )
        reviewer_tokens = tuple(
            content_hash(
                {"workflow_id": workflow_id, "reviewer": index, "seed": randomization_seed},
                prefix="reviewer",
            )
            for index in range(1, reviewer_count + 1)
        )
        ordered = sorted(
            parsed,
            key=lambda item: content_hash(
                {
                    "seed": randomization_seed,
                    "claim_id": item.claim_id,
                    "observation": item.observation_id,
                },
                prefix="order",
            ),
        )
        cases: list[BlindedAdjudicationCase] = []
        for position, item in enumerate(ordered, start=1):
            blind_token = content_hash(
                {"workflow": workflow_id, "claim": item.claim_id, "seed": randomization_seed},
                prefix="blind",
            )
            cases.append(
                BlindedAdjudicationCase(
                    case_id=content_hash(
                        {"workflow": workflow_id, "token": blind_token}, prefix="case"
                    ),
                    workflow_id=workflow_id,
                    blind_token=blind_token,
                    position=position,
                    context_key=context_key,
                    evidence_digest=item.evidence_digest,
                    masked_claim_receipt=content_hash(item.claim_id, prefix="masked-claim"),
                    masked_source_receipt=content_hash(
                        item.source_receipt_hash, prefix="masked-source"
                    ),
                    required_decisions=decisions_required,
                    instructions=(
                        "Review the evidence digest and declared record without using "
                        "source identity.",
                        "Record supports, against, abstain, or inconclusive with a rationale.",
                        "A blinded verdict is an adjudication input and not a causal conclusion.",
                    ),
                    _claim_id=item.claim_id,
                    _source_ids=item.source_ids,
                    _edge_id=item.edge_id,
                )
            )
        state = (
            LifecycleAlphaState.PARTIAL
            if cases and any(issue.severity == "error" for issue in issues)
            else LifecycleAlphaState.READY_FOR_REVIEW
            if cases
            else LifecycleAlphaState.OUT_OF_DOMAIN
            if any(issue.code == "context_mismatch" for issue in issues)
            else LifecycleAlphaState.ABSTAINED
        )
        return BlindedAdjudicationPlan(
            workflow_id=workflow_id,
            context_key=context_key,
            state=state,
            cases=tuple(cases),
            reviewer_tokens=reviewer_tokens,
            required_decisions=decisions_required,
            randomization_seed=randomization_seed,
            issues=tuple(issues),
            warnings=(
                "Masking hides source labels from the exported packet but does not remove "
                "source-dependent bias from the underlying evidence.",
                "Reviewer decisions require domain adjudication and do not promote a claim "
                "beyond its evidence.",
            ),
            content_address=content_hash(
                {
                    "workflow_id": workflow_id,
                    "context_key": context_key,
                    "state": state,
                    "cases": cases,
                    "reviewer_tokens": reviewer_tokens,
                    "required_decisions": decisions_required,
                }
            ),
        )

    def adjudicate(
        self,
        plan: BlindedAdjudicationPlan,
        decisions: Iterable[BlindedAdjudicationDecision | Mapping[str, Any]],
    ) -> BlindedAdjudicationResult:
        case_index = {case.case_id: case for case in plan.cases}
        token_set = set(plan.reviewer_tokens)
        issues: list[LifecycleAlphaIssue] = list(plan.issues)
        parsed: list[BlindedAdjudicationDecision] = []
        for row_number, value in enumerate(tuple(decisions), start=1):
            try:
                item = _coerce_decision(value, context_key=plan.context_key)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LifecycleAlphaIssue(
                        "invalid_adjudication_decision",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            case = case_index.get(item.case_id)
            if case is None:
                issues.append(
                    LifecycleAlphaIssue(
                        "unknown_case_id",
                        "decision references a case outside the blinded plan",
                        item.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if item.reviewer_token not in token_set:
                issues.append(
                    LifecycleAlphaIssue(
                        "unknown_reviewer_token",
                        "decision reviewer token is not assigned to the blinded plan",
                        item.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            parsed.append(item)
        by_case: dict[str, list[BlindedAdjudicationDecision]] = defaultdict(list)
        for item in parsed:
            by_case[item.case_id].append(item)
        summaries: list[BlindedCaseAdjudication] = []
        unresolved: list[str] = []
        for case in plan.cases:
            rows = by_case.get(case.case_id, [])
            verdicts = tuple(item.verdict for item in rows)
            distinct = set(verdicts) - {
                AdjudicationVerdict.ABSTAIN,
                AdjudicationVerdict.INCONCLUSIVE,
            }
            agreement = 1.0 if len(distinct) <= 1 else 0.0
            reasons: list[str] = []
            if len(rows) < case.required_decisions:
                reasons.append("required_decision_count_not_met")
            if len({item.reviewer_token for item in rows}) != len(rows):
                reasons.append("duplicate_reviewer_decision")
            if len(distinct) > 1:
                reasons.append("support_and_against_verdicts_disagree")
            if any(
                item.verdict in {AdjudicationVerdict.ABSTAIN, AdjudicationVerdict.INCONCLUSIVE}
                for item in rows
            ):
                reasons.append("one_or_more_reviewers_abstained_or_found_inconclusive")
            if reasons:
                state = (
                    LifecycleAlphaState.SPLIT_DECISION
                    if len(distinct) > 1
                    else LifecycleAlphaState.REVIEW_REQUIRED
                )
                unresolved.append(case.case_id)
            else:
                state = LifecycleAlphaState.ADJUDICATED
            summaries.append(
                BlindedCaseAdjudication(
                    case_id=case.case_id,
                    state=state,
                    verdicts=verdicts,
                    decision_ids=tuple(item.decision_id for item in rows),
                    agreement=agreement,
                    decision_count=len(rows),
                    required_decisions=case.required_decisions,
                    unresolved_reasons=tuple(reasons),
                )
            )
        if not plan.cases:
            state = LifecycleAlphaState.ABSTAINED
        elif any(item.state == LifecycleAlphaState.SPLIT_DECISION for item in summaries):
            state = LifecycleAlphaState.SPLIT_DECISION
        elif unresolved:
            state = LifecycleAlphaState.REVIEW_REQUIRED
        elif any(issue.severity == "error" for issue in issues):
            state = LifecycleAlphaState.PARTIAL
        else:
            state = LifecycleAlphaState.ADJUDICATED
        return BlindedAdjudicationResult(
            workflow_id=plan.workflow_id,
            context_key=plan.context_key,
            state=state,
            plan_address=plan.content_address,
            cases=tuple(summaries),
            decisions=tuple(parsed),
            unresolved_case_ids=tuple(unresolved),
            issues=tuple(issues),
            warnings=(
                "Adjudication agreement is descriptive and is not calibrated reviewer reliability.",
                "Case unmasking and claim reclassification require an explicit downstream "
                "review decision.",
            ),
            content_address=content_hash(
                {
                    "workflow_id": plan.workflow_id,
                    "context_key": plan.context_key,
                    "plan_address": plan.content_address,
                    "state": state,
                    "cases": summaries,
                    "decisions": parsed,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ReviewerComment:
    """One review comment retained in an append-only log."""

    comment_id: str
    review_id: str
    target_type: str
    target_id: str
    context_key: str
    author_role: str
    text: str
    state: CommentState
    raw_hash: str
    created_at: str
    parent_comment_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "comment_id",
            "review_id",
            "target_type",
            "target_id",
            "context_key",
            "author_role",
            "text",
            "raw_hash",
            "created_at",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewerChange:
    """One before/after transition attached to a review target."""

    change_id: str
    review_id: str
    target_type: str
    target_id: str
    context_key: str
    actor_role: str
    action: str
    before_hash: str
    after_hash: str
    rationale: str
    raw_hash: str
    created_at: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "change_id",
            "review_id",
            "target_type",
            "target_id",
            "context_key",
            "actor_role",
            "action",
            "before_hash",
            "after_hash",
            "rationale",
            "raw_hash",
            "created_at",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.before_hash == self.after_hash:
            raise ValidationError("review change before_hash and after_hash must differ")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReviewerCommentChangeLog:
    """Immutable review comments and change transitions."""

    review_id: str
    context_key: str
    state: LifecycleAlphaState
    comments: tuple[ReviewerComment, ...]
    changes: tuple[ReviewerChange, ...]
    issues: tuple[LifecycleAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReviewerCommentChangeLogger:
    """Build or append immutable reviewer comment and change logs."""

    def record(
        self,
        comments: Iterable[ReviewerComment | Mapping[str, Any]] = (),
        changes: Iterable[ReviewerChange | Mapping[str, Any]] = (),
        *,
        review_id: str = "review-1",
        context_key: str,
    ) -> ReviewerCommentChangeLog:
        require_non_empty(review_id, "review_id")
        require_non_empty(context_key, "context_key")
        parsed_comments, parsed_changes, issues = self._parse(comments, changes, context_key)
        state = self._state(parsed_comments, parsed_changes, issues, context_key)
        return self._result(review_id, context_key, state, parsed_comments, parsed_changes, issues)

    def append(
        self,
        previous: ReviewerCommentChangeLog,
        comments: Iterable[ReviewerComment | Mapping[str, Any]] = (),
        changes: Iterable[ReviewerChange | Mapping[str, Any]] = (),
    ) -> ReviewerCommentChangeLog:
        additions_comments, additions_changes, additions_issues = self._parse(
            comments, changes, previous.context_key
        )
        all_comments = previous.comments + additions_comments
        all_changes = previous.changes + additions_changes
        issues = previous.issues + additions_issues
        duplicate_ids = _duplicates(
            [item.comment_id for item in all_comments] + [item.change_id for item in all_changes]
        )
        if duplicate_ids:
            issues += (
                LifecycleAlphaIssue(
                    "duplicate_log_id",
                    "append would duplicate an existing comment or change ID",
                    content_hash(duplicate_ids),
                    severity="error",
                ),
            )
        state = self._state(all_comments, all_changes, issues, previous.context_key)
        return self._result(
            previous.review_id,
            previous.context_key,
            state,
            all_comments,
            all_changes,
            issues,
        )

    def _parse(
        self,
        comments: Iterable[ReviewerComment | Mapping[str, Any]],
        changes: Iterable[ReviewerChange | Mapping[str, Any]],
        context_key: str,
    ) -> tuple[
        tuple[ReviewerComment, ...], tuple[ReviewerChange, ...], tuple[LifecycleAlphaIssue, ...]
    ]:
        issues: list[LifecycleAlphaIssue] = []
        parsed_comments: list[ReviewerComment] = []
        parsed_changes: list[ReviewerChange] = []
        for row_number, value in enumerate(tuple(comments), start=1):
            try:
                item = _coerce_comment(value, context_key=context_key)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LifecycleAlphaIssue(
                        "invalid_comment",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if item.context_key != context_key:
                issues.append(
                    LifecycleAlphaIssue(
                        "context_mismatch",
                        "comment is outside the review context",
                        item.raw_hash,
                        row_number=row_number,
                        context_key=item.context_key,
                    )
                )
                continue
            parsed_comments.append(item)
        for row_number, value in enumerate(tuple(changes), start=1):
            try:
                item = _coerce_change(value, context_key=context_key)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LifecycleAlphaIssue(
                        "invalid_change",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if item.context_key != context_key:
                issues.append(
                    LifecycleAlphaIssue(
                        "context_mismatch",
                        "change is outside the review context",
                        item.raw_hash,
                        row_number=row_number,
                        context_key=item.context_key,
                    )
                )
                continue
            parsed_changes.append(item)
        ids = [item.comment_id for item in parsed_comments] + [
            item.change_id for item in parsed_changes
        ]
        for duplicate in _duplicates(ids):
            issues.append(
                LifecycleAlphaIssue(
                    "duplicate_log_id",
                    f"duplicate review log ID: {duplicate}",
                    content_hash(duplicate),
                    severity="error",
                )
            )
        return tuple(parsed_comments), tuple(parsed_changes), tuple(issues)

    @staticmethod
    def _state(
        comments: Iterable[ReviewerComment],
        changes: Iterable[ReviewerChange],
        issues: Iterable[LifecycleAlphaIssue],
        context_key: str,
    ) -> LifecycleAlphaState:
        items = tuple(comments) + tuple(changes)
        issue_values = tuple(issues)
        if not items and any(
            issue.context_key and issue.context_key != context_key for issue in issue_values
        ):
            return LifecycleAlphaState.OUT_OF_DOMAIN
        if any(issue.severity == "error" for issue in issue_values):
            return LifecycleAlphaState.PARTIAL
        return LifecycleAlphaState.READY_FOR_REVIEW if items else LifecycleAlphaState.ABSTAINED

    @staticmethod
    def _result(
        review_id: str,
        context_key: str,
        state: LifecycleAlphaState,
        comments: tuple[ReviewerComment, ...],
        changes: tuple[ReviewerChange, ...],
        issues: tuple[LifecycleAlphaIssue, ...],
    ) -> ReviewerCommentChangeLog:
        return ReviewerCommentChangeLog(
            review_id=review_id,
            context_key=context_key,
            state=state,
            comments=comments,
            changes=changes,
            issues=issues,
            warnings=(
                "Comments and changes record reviewer process; they do not validate the "
                "underlying claim.",
                "An append-only log does not by itself establish reviewer independence or "
                "completeness.",
            ),
            content_address=content_hash(
                {
                    "review_id": review_id,
                    "context_key": context_key,
                    "state": state,
                    "comments": comments,
                    "changes": changes,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class ReleaseGateObservation:
    """One explicit gate used by a research-only release decision."""

    gate_id: str
    label: str
    passed: bool
    blocking: bool
    context_key: str
    evidence_hash: str
    reason: str
    source_id: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "gate_id",
            "label",
            "context_key",
            "evidence_hash",
            "reason",
            "source_id",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReleaseDecisionRecord:
    """Research-only release gate result with explicit conditions."""

    release_id: str
    graph_id: str
    graph_version: int
    graph_address: str
    context_key: str
    state: LifecycleAlphaState
    decision: ReleaseDecision
    gate_ids: tuple[str, ...]
    failed_gate_ids: tuple[str, ...]
    blocking_gate_ids: tuple[str, ...]
    required_roles: tuple[str, ...]
    completed_roles: tuple[str, ...]
    missing_roles: tuple[str, ...]
    conditions: tuple[str, ...]
    reviewer_ids: tuple[str, ...]
    comment_log_address: str | None
    decision_reason: str
    research_use_only: bool
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.release_id, "release_id")
        require_non_empty(self.graph_id, "graph_id")
        require_non_empty(self.graph_address, "graph_address")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.decision_reason, "decision_reason")
        if self.graph_version < 1:
            raise ValidationError("release graph_version must be positive")
        if not self.research_use_only:
            raise ValidationError("release decision must be research_use_only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReleaseDecisionRecorder:
    """Evaluate explicit gates without silently promoting a dossier."""

    def record(
        self,
        graph: EvidenceGraphSnapshot | Mapping[str, Any],
        gates: Iterable[ReleaseGateObservation | Mapping[str, Any]],
        *,
        release_id: str = "release-1",
        required_roles: Iterable[str] = (),
        completed_roles: Iterable[str] = (),
        reviewer_ids: Iterable[str] = (),
        comment_log_address: str | None = None,
        requested_decision: ReleaseDecision | str | None = None,
    ) -> ReleaseDecisionRecord:
        snapshot = _coerce_graph(graph)
        values = tuple(gates)
        parsed: list[ReleaseGateObservation] = []
        failed: list[str] = []
        blocking: list[str] = []
        context_mismatch = False
        for _row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_gate(value, context_key=snapshot.context_key)
            except (TypeError, ValueError, ValidationError):
                continue
            if item.context_key != snapshot.context_key:
                context_mismatch = True
                continue
            parsed.append(item)
            if not item.passed:
                failed.append(item.gate_id)
                if item.blocking:
                    blocking.append(item.gate_id)
        required = tuple(dict.fromkeys(str(item) for item in required_roles if str(item).strip()))
        completed = tuple(dict.fromkeys(str(item) for item in completed_roles if str(item).strip()))
        missing = tuple(sorted(set(required) - set(completed)))
        conditions: list[str] = []
        if snapshot.state != LifecycleState.SUPPORTED:
            conditions.append("graph_state_requires_review")
        if snapshot.contradictory_edge_ids:
            conditions.append("contradictory_edges_require_review")
        if snapshot.orphan_claim_ids:
            conditions.append("orphan_claims_require_review")
        if failed:
            conditions.append("failed_release_gate")
        if missing:
            conditions.append("required_reviewer_role_missing")
        if context_mismatch:
            conditions.append("gate_context_mismatch")
        requested = None if requested_decision is None else ReleaseDecision(str(requested_decision))
        if requested == ReleaseDecision.REJECTED:
            decision = ReleaseDecision.REJECTED
            state = LifecycleAlphaState.REJECTED
            reason = "release was explicitly rejected by the requesting review process"
        elif requested == ReleaseDecision.CONDITIONAL:
            decision = ReleaseDecision.CONDITIONAL
            state = LifecycleAlphaState.CONDITIONAL
            reason = "release was explicitly made conditional on retained review requirements"
        elif blocking or conditions:
            decision = ReleaseDecision.REVIEW_REQUIRED
            state = LifecycleAlphaState.REVIEW_REQUIRED
            reason = "one or more graph, gate, context, or reviewer conditions remain unresolved"
        elif requested == ReleaseDecision.APPROVED:
            decision = ReleaseDecision.APPROVED
            state = LifecycleAlphaState.APPROVED
            reason = "all supplied release gates and required reviewer roles are complete"
        else:
            decision = ReleaseDecision.REVIEW_REQUIRED
            state = LifecycleAlphaState.REVIEW_REQUIRED
            reason = (
                "approval was not explicitly requested; research release remains review-required"
            )
        return ReleaseDecisionRecord(
            release_id=release_id,
            graph_id=snapshot.graph_id,
            graph_version=snapshot.graph_version,
            graph_address=snapshot.content_address,
            context_key=snapshot.context_key,
            state=state,
            decision=decision,
            gate_ids=tuple(item.gate_id for item in parsed),
            failed_gate_ids=tuple(dict.fromkeys(failed)),
            blocking_gate_ids=tuple(dict.fromkeys(blocking)),
            required_roles=required,
            completed_roles=completed,
            missing_roles=missing,
            conditions=tuple(dict.fromkeys(conditions)),
            reviewer_ids=tuple(
                dict.fromkeys(str(item) for item in reviewer_ids if str(item).strip())
            ),
            comment_log_address=comment_log_address,
            decision_reason=reason,
            research_use_only=True,
            content_address=content_hash(
                {
                    "release_id": release_id,
                    "graph_address": snapshot.content_address,
                    "context_key": snapshot.context_key,
                    "state": state,
                    "decision": decision,
                    "gate_ids": tuple(item.gate_id for item in parsed),
                    "failed_gate_ids": tuple(dict.fromkeys(failed)),
                    "missing_roles": missing,
                    "conditions": tuple(dict.fromkeys(conditions)),
                    "comment_log_address": comment_log_address,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class EvidenceDelta:
    """One historical graph change with review severity."""

    delta_id: str
    kind: EvidenceDeltaKind
    entity_id: str
    context_key: str
    before_hash: str | None
    after_hash: str | None
    severity: str
    summary: str
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("delta_id", "entity_id", "context_key", "severity", "summary"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceDeltaReport:
    """Complete before/after evidence delta report."""

    previous_graph_address: str
    current_graph_address: str
    context_key: str
    state: LifecycleAlphaState
    deltas: tuple[EvidenceDelta, ...]
    added_claim_count: int
    removed_claim_count: int
    changed_claim_count: int
    added_citation_count: int
    removed_citation_count: int
    changed_citation_count: int
    review_required: bool
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceDeltaDetector:
    """Compare immutable graph snapshots without merging away disagreement."""

    def compare(
        self,
        previous: EvidenceGraphSnapshot | Mapping[str, Any],
        current: EvidenceGraphSnapshot | Mapping[str, Any],
        *,
        expected_context_key: str | None = None,
    ) -> EvidenceDeltaReport:
        before = _coerce_graph(previous)
        after = _coerce_graph(current)
        context = expected_context_key or after.context_key
        deltas: list[EvidenceDelta] = []
        if before.context_key != after.context_key:
            deltas.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {
                            "kind": EvidenceDeltaKind.CONTEXT_CHANGED,
                            "before": before.context_key,
                            "after": after.context_key,
                        },
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.CONTEXT_CHANGED,
                    entity_id=after.graph_id,
                    context_key=context,
                    before_hash=content_hash(before.context_key),
                    after_hash=content_hash(after.context_key),
                    severity="critical",
                    summary="graph context changed between snapshots",
                    source_ids=(),
                )
            )
        self._claim_deltas(before, after, context, deltas)
        self._citation_deltas(before, after, context, deltas)
        if before.state != after.state:
            deltas.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {
                            "kind": EvidenceDeltaKind.GRAPH_STATE_CHANGED,
                            "before": before.state,
                            "after": after.state,
                        },
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.GRAPH_STATE_CHANGED,
                    entity_id=after.graph_id,
                    context_key=context,
                    before_hash=content_hash(before.state),
                    after_hash=content_hash(after.state),
                    severity="high",
                    summary=f"graph state changed from {before.state.value} to {after.state.value}",
                    source_ids=(),
                )
            )
        context_mismatch = (
            before.context_key != context
            or after.context_key != context
            or before.context_key != after.context_key
        )
        state = (
            LifecycleAlphaState.OUT_OF_DOMAIN
            if context_mismatch
            else LifecycleAlphaState.READY_FOR_REVIEW
            if not deltas
            else LifecycleAlphaState.REVIEW_REQUIRED
        )
        return EvidenceDeltaReport(
            previous_graph_address=before.content_address,
            current_graph_address=after.content_address,
            context_key=context,
            state=state,
            deltas=tuple(deltas),
            added_claim_count=sum(item.kind == EvidenceDeltaKind.CLAIM_ADDED for item in deltas),
            removed_claim_count=sum(
                item.kind == EvidenceDeltaKind.CLAIM_REMOVED for item in deltas
            ),
            changed_claim_count=sum(
                item.kind == EvidenceDeltaKind.CLAIM_CHANGED for item in deltas
            ),
            added_citation_count=sum(
                item.kind == EvidenceDeltaKind.CITATION_ADDED for item in deltas
            ),
            removed_citation_count=sum(
                item.kind == EvidenceDeltaKind.CITATION_REMOVED for item in deltas
            ),
            changed_citation_count=sum(
                item.kind == EvidenceDeltaKind.CITATION_CHANGED for item in deltas
            ),
            review_required=bool(deltas),
            warnings=(
                "A delta identifies changed evidence records; it does not decide which record "
                "is correct.",
                "Claim additions, removals, and state changes require source and reviewer "
                "reconciliation.",
            ),
            content_address=content_hash(
                {
                    "previous_graph_address": before.content_address,
                    "current_graph_address": after.content_address,
                    "context_key": context,
                    "state": state,
                    "deltas": deltas,
                }
            ),
        )

    @staticmethod
    def _claim_deltas(
        before: EvidenceGraphSnapshot,
        after: EvidenceGraphSnapshot,
        context: str,
        output: list[EvidenceDelta],
    ) -> None:
        before_map = {item.claim_id: item for item in before.claims}
        after_map = {item.claim_id: item for item in after.claims}
        for claim_id in sorted(set(after_map) - set(before_map)):
            item = after_map[claim_id]
            output.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {
                            "kind": EvidenceDeltaKind.CLAIM_ADDED,
                            "id": claim_id,
                            "after": item.raw_hash,
                        },
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.CLAIM_ADDED,
                    entity_id=claim_id,
                    context_key=context,
                    before_hash=None,
                    after_hash=content_hash(item.to_dict()),
                    severity="high",
                    summary="claim is present only in the current graph snapshot",
                    source_ids=item.source_ids,
                )
            )
        for claim_id in sorted(set(before_map) - set(after_map)):
            item = before_map[claim_id]
            output.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {
                            "kind": EvidenceDeltaKind.CLAIM_REMOVED,
                            "id": claim_id,
                            "before": item.raw_hash,
                        },
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.CLAIM_REMOVED,
                    entity_id=claim_id,
                    context_key=context,
                    before_hash=content_hash(item.to_dict()),
                    after_hash=None,
                    severity="critical",
                    summary="claim is present only in the previous graph snapshot",
                    source_ids=item.source_ids,
                )
            )
        for claim_id in sorted(set(before_map) & set(after_map)):
            old = before_map[claim_id]
            new = after_map[claim_id]
            old_hash = content_hash(old.to_dict())
            new_hash = content_hash(new.to_dict())
            if old_hash != new_hash:
                output.append(
                    EvidenceDelta(
                        delta_id=content_hash(
                            {
                                "kind": EvidenceDeltaKind.CLAIM_CHANGED,
                                "id": claim_id,
                                "before": old_hash,
                                "after": new_hash,
                            },
                            prefix="delta",
                        ),
                        kind=EvidenceDeltaKind.CLAIM_CHANGED,
                        entity_id=claim_id,
                        context_key=context,
                        before_hash=old_hash,
                        after_hash=new_hash,
                        severity="high",
                        summary="claim content, state, source, or lineage changed",
                        source_ids=tuple(sorted(set(old.source_ids) | set(new.source_ids))),
                    )
                )

    @staticmethod
    def _citation_deltas(
        before: EvidenceGraphSnapshot,
        after: EvidenceGraphSnapshot,
        context: str,
        output: list[EvidenceDelta],
    ) -> None:
        before_map = {item.citation_id: item for item in before.citations}
        after_map = {item.citation_id: item for item in after.citations}
        for citation_id in sorted(set(after_map) - set(before_map)):
            item = after_map[citation_id]
            output.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {"kind": EvidenceDeltaKind.CITATION_ADDED, "id": citation_id},
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.CITATION_ADDED,
                    entity_id=citation_id,
                    context_key=context,
                    before_hash=None,
                    after_hash=item.content_address,
                    severity="medium",
                    summary="citation is present only in the current graph snapshot",
                    source_ids=(item.source_id,),
                )
            )
        for citation_id in sorted(set(before_map) - set(after_map)):
            item = before_map[citation_id]
            output.append(
                EvidenceDelta(
                    delta_id=content_hash(
                        {"kind": EvidenceDeltaKind.CITATION_REMOVED, "id": citation_id},
                        prefix="delta",
                    ),
                    kind=EvidenceDeltaKind.CITATION_REMOVED,
                    entity_id=citation_id,
                    context_key=context,
                    before_hash=item.content_address,
                    after_hash=None,
                    severity="high",
                    summary="citation is present only in the previous graph snapshot",
                    source_ids=(item.source_id,),
                )
            )
        for citation_id in sorted(set(before_map) & set(after_map)):
            old = before_map[citation_id]
            new = after_map[citation_id]
            if old.content_address != new.content_address:
                output.append(
                    EvidenceDelta(
                        delta_id=content_hash(
                            {
                                "kind": EvidenceDeltaKind.CITATION_CHANGED,
                                "id": citation_id,
                                "before": old.content_address,
                                "after": new.content_address,
                            },
                            prefix="delta",
                        ),
                        kind=EvidenceDeltaKind.CITATION_CHANGED,
                        entity_id=citation_id,
                        context_key=context,
                        before_hash=old.content_address,
                        after_hash=new.content_address,
                        severity="high",
                        summary="citation content, version, or retrieval receipt changed",
                        source_ids=(new.source_id,),
                    )
                )


def _coerce_blinded_observation(
    value: BlindedAdjudicationObservation | Mapping[str, Any],
) -> BlindedAdjudicationObservation:
    if isinstance(value, BlindedAdjudicationObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("blinded observation must be a mapping")
    source_values = value.get("source_ids", value.get("source_id", ("declared-source",)))
    source_ids = (
        (str(source_values),)
        if isinstance(source_values, str)
        else tuple(str(item) for item in source_values)
    )
    return BlindedAdjudicationObservation(
        observation_id=str(value.get("observation_id", value.get("id", "observation"))),
        claim_id=str(value.get("claim_id", value.get("claim", ""))),
        edge_id=str(value.get("edge_id", value.get("edge", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        evidence_digest=str(
            value.get("evidence_digest", value.get("evidence_hash", content_hash(dict(value))))
        ),
        source_ids=source_ids,
        source_versions={
            str(key): str(item) for key, item in dict(value.get("source_versions", {})).items()
        },
        source_receipt_hash=str(
            value.get("source_receipt_hash", content_hash(source_ids, prefix="source-receipt"))
        ),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        summary=str(value.get("summary", "")),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_decision(
    value: BlindedAdjudicationDecision | Mapping[str, Any],
    *,
    context_key: str,
) -> BlindedAdjudicationDecision:
    if isinstance(value, BlindedAdjudicationDecision):
        if value.context_key != context_key:
            raise ValidationError("adjudication decision context does not match plan")
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("adjudication decision must be a mapping")
    return BlindedAdjudicationDecision(
        decision_id=str(value.get("decision_id", value.get("id", "decision"))),
        case_id=str(value.get("case_id", "")),
        reviewer_token=str(value.get("reviewer_token", value.get("reviewer", ""))),
        verdict=AdjudicationVerdict(str(value.get("verdict", AdjudicationVerdict.ABSTAIN.value))),
        confidence=float(value.get("confidence", 0.0)),
        rationale=str(value.get("rationale", "")),
        context_key=str(value.get("context_key", context_key)),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        submitted_at=str(value.get("submitted_at", utc_now().isoformat())),
    )


def _coerce_comment(
    value: ReviewerComment | Mapping[str, Any], *, context_key: str
) -> ReviewerComment:
    if isinstance(value, ReviewerComment):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("review comment must be a mapping")
    return ReviewerComment(
        comment_id=str(value.get("comment_id", value.get("id", "comment"))),
        review_id=str(value.get("review_id", "review-1")),
        target_type=str(value.get("target_type", "claim")),
        target_id=str(value.get("target_id", value.get("claim_id", ""))),
        context_key=str(value.get("context_key", context_key)),
        author_role=str(value.get("author_role", value.get("role", "reviewer"))),
        text=str(value.get("text", value.get("comment", ""))),
        state=CommentState(str(value.get("state", CommentState.OPEN.value))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        created_at=str(value.get("created_at", utc_now().isoformat())),
        parent_comment_id=(
            None
            if value.get("parent_comment_id") in (None, "")
            else str(value["parent_comment_id"])
        ),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_change(
    value: ReviewerChange | Mapping[str, Any], *, context_key: str
) -> ReviewerChange:
    if isinstance(value, ReviewerChange):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("review change must be a mapping")
    before = str(value.get("before_hash", ""))
    after = str(value.get("after_hash", ""))
    return ReviewerChange(
        change_id=str(value.get("change_id", value.get("id", "change"))),
        review_id=str(value.get("review_id", "review-1")),
        target_type=str(value.get("target_type", "claim")),
        target_id=str(value.get("target_id", value.get("claim_id", ""))),
        context_key=str(value.get("context_key", context_key)),
        actor_role=str(value.get("actor_role", value.get("role", "reviewer"))),
        action=str(value.get("action", "update")),
        before_hash=before,
        after_hash=after,
        rationale=str(value.get("rationale", "")),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        created_at=str(value.get("created_at", utc_now().isoformat())),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_gate(
    value: ReleaseGateObservation | Mapping[str, Any], *, context_key: str
) -> ReleaseGateObservation:
    if isinstance(value, ReleaseGateObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("release gate must be a mapping")
    return ReleaseGateObservation(
        gate_id=str(value.get("gate_id", value.get("id", "gate"))),
        label=str(value.get("label", value.get("name", "gate"))),
        passed=_as_bool(value.get("passed", False)),
        blocking=_as_bool(value.get("blocking", True)),
        context_key=str(value.get("context_key", context_key)),
        evidence_hash=str(
            value.get("evidence_hash", value.get("evidence_address", content_hash(dict(value))))
        ),
        reason=str(value.get("reason", "declared gate result")),
        source_id=str(value.get("source_id", "release-input")),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_graph(value: EvidenceGraphSnapshot | Mapping[str, Any]) -> EvidenceGraphSnapshot:
    if isinstance(value, EvidenceGraphSnapshot):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("evidence graph must be a snapshot or mapping")
    context_key = str(value.get("context_key", ""))
    claims_raw = value.get("claims", ())
    citations_raw = value.get("citations", ())
    claims = tuple(
        VersionedEvidenceClaim.from_mapping(
            item,
            fallback_id=f"claim-{index}",
            context_key=context_key,
        )
        for index, item in enumerate(claims_raw, start=1)
    )
    citations = tuple(
        EvidenceCitation.from_mapping(
            item,
            fallback_source_id=f"source-{index}",
            fallback_version="unspecified",
            fallback_row_number=index,
        )
        for index, item in enumerate(citations_raw, start=1)
    )
    return VersionedEvidenceGraphConstructor().construct(
        claims,
        citations=citations,
        graph_id=str(value.get("graph_id", "evidence-graph")),
        context_key=context_key,
        graph_version=int(value.get("graph_version", 1)),
    )


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _duplicates(values: Iterable[str]) -> tuple[str, ...]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return tuple(sorted(value for value, count in counts.items() if count > 1))


__all__ = [
    "AdjudicationVerdict",
    "BlindedAdjudicationCase",
    "BlindedAdjudicationDecision",
    "BlindedAdjudicationObservation",
    "BlindedAdjudicationPlan",
    "BlindedAdjudicationResult",
    "BlindedAdjudicationWorkflow",
    "BlindedCaseAdjudication",
    "CommentState",
    "EvidenceDelta",
    "EvidenceDeltaDetector",
    "EvidenceDeltaKind",
    "EvidenceDeltaReport",
    "LifecycleAlphaIssue",
    "LifecycleAlphaState",
    "ReleaseDecision",
    "ReleaseDecisionRecord",
    "ReleaseDecisionRecorder",
    "ReleaseGateObservation",
    "ReviewerChange",
    "ReviewerComment",
    "ReviewerCommentChangeLog",
    "ReviewerCommentChangeLogger",
]
