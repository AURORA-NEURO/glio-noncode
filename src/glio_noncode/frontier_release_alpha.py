"""Deep validation, evidence lifecycle, workbench, and deployment controls.

This module completes the frontier expansion for domains D13-D16. The
implementations are deterministic and local-first: they calculate declared
research metrics, retain all gating inputs, and produce reviewable receipts
without silently claiming clinical validity or scientific certainty.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    FrontierIssue,
    FrontierState,
    _address,
    _bounded,
    _context,
    _float,
    _mapping,
    _required_text,
    _text,
    _tuple_text,
)
from .serialization import canonical_json, content_hash, jsonable, require_non_empty


class FrontierReleaseState(StrEnum):
    """Additional states for lifecycle and deployment decisions."""

    READY = "ready"
    HOLD = "hold"
    DENIED = "denied"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"
    ABSTAINED = "abstained"


def _now_text(value: Any = None) -> str:
    if value is not None and _text(value, field="timestamp"):
        return _text(value, field="timestamp")
    return "unspecified"


def _bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "allow", "allowed", "pass", "passed"}:
            return True
        if lowered in {"false", "no", "0", "deny", "denied", "fail", "failed"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise ValidationError(f"{field} must be boolean")


@dataclass(frozen=True, slots=True)
class OffTargetRiskResult:
    target_id: str
    context_key: str
    on_target_score: float
    maximum_off_target_score: float
    weighted_off_target_score: float
    specificity: float
    risk_tier: str
    off_target_count: int
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class OffTargetRiskReport:
    results: tuple[OffTargetRiskResult, ...]
    low_risk_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class OffTargetRiskEstimator:
    """Estimate off-target burden from supplied candidate alignments."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        review_threshold: float = 0.25,
        blocking_threshold: float = 0.6,
    ) -> OffTargetRiskReport:
        context_key = require_non_empty(context_key, "context_key")
        review_threshold = _bounded(review_threshold, field="review_threshold")
        blocking_threshold = _bounded(blocking_threshold, field="blocking_threshold")
        results: list[OffTargetRiskResult] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"off-target record {index}")
            target_id = (
                _text(row.get("target_id", row.get("id")), field="target_id") or f"target:{index}"
            )
            on_target = _bounded(row.get("on_target_score", 0.0), field="on_target_score")
            candidates = tuple(
                _mapping(item, label="off-target candidate")
                for item in row.get("off_targets", row.get("candidates", ()))
            )
            scores = tuple(
                _bounded(item.get("score", 0.0), field="off_target_score") for item in candidates
            )
            weights = tuple(
                max(0.0, _float(item.get("weight", 1.0), field="off_target_weight"))
                for item in candidates
            )
            total_weight = sum(weights)
            weighted = sum(
                score * weight for score, weight in zip(scores, weights, strict=True)
            ) / max(1.0, total_weight)
            maximum = max(scores, default=0.0)
            specificity = round(max(0.0, on_target - maximum), 6)
            issues: list[FrontierIssue] = []
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "off_target_context_mismatch",
                        "target context differs from requested context",
                        "blocking",
                        "context_key",
                        target_id,
                    )
                )
            if maximum >= blocking_threshold:
                issues.append(
                    FrontierIssue(
                        "off_target_risk_high",
                        "maximum off-target score exceeds blocking threshold",
                        "blocking",
                        record_id=target_id,
                    )
                )
            elif weighted >= review_threshold:
                issues.append(
                    FrontierIssue(
                        "off_target_risk_review",
                        "weighted off-target burden exceeds review threshold",
                        "review",
                        record_id=target_id,
                    )
                )
            risk_tier = (
                "high"
                if maximum >= blocking_threshold
                else "review"
                if weighted >= review_threshold
                else "low"
            )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            results.append(
                OffTargetRiskResult(
                    target_id,
                    context_key,
                    on_target,
                    maximum,
                    round(weighted, 6),
                    specificity,
                    risk_tier,
                    len(scores),
                    state,
                    tuple(issues),
                )
            )
        low = tuple(item.target_id for item in results if item.state == FrontierState.ACCEPTED)
        review = tuple(item.target_id for item in results if item.state != FrontierState.ACCEPTED)
        return OffTargetRiskReport(tuple(results), low, review, _address(results))


@dataclass(frozen=True, slots=True)
class ValueOfInformationExperiment:
    experiment_id: str
    context_key: str
    cost: float
    information_gain: float
    risk_reduction: float
    value_score: float
    prerequisites: tuple[str, ...]
    selected: bool
    selection_reason: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValueOfInformationPlan:
    plan_id: str
    context_key: str
    budget: float
    selected_ids: tuple[str, ...]
    total_cost: float
    total_information_gain: float
    total_risk_reduction: float
    experiments: tuple[ValueOfInformationExperiment, ...]
    content_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ValidationValueOfInformationOptimizer:
    """Select feasible validation experiments by transparent value density."""

    def optimize(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        plan_id: str,
        context_key: str,
        budget: float,
        maximum_experiments: int | None = None,
    ) -> ValueOfInformationPlan:
        plan_id = require_non_empty(plan_id, "plan_id")
        context_key = require_non_empty(context_key, "context_key")
        budget = _float(budget, field="budget")
        if budget < 0:
            raise ValidationError("budget must not be negative")
        if maximum_experiments is not None and maximum_experiments < 1:
            raise ValidationError("maximum_experiments must be positive")
        parsed: list[dict[str, Any]] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"VOI experiment {index}")
            experiment_id = (
                _text(row.get("experiment_id", row.get("id")), field="experiment_id")
                or f"experiment:{index}"
            )
            cost = _float(row.get("cost", 0.0), field="cost")
            information = _bounded(row.get("information_gain", 0.0), field="information_gain")
            risk = _bounded(row.get("risk_reduction", 0.0), field="risk_reduction")
            if cost <= 0:
                raise ValidationError(f"{experiment_id} cost must be positive")
            prerequisites = _tuple_text(row.get("prerequisites", ()), field="prerequisites")
            parsed.append(
                {
                    "id": experiment_id,
                    "cost": cost,
                    "information": information,
                    "risk": risk,
                    "prerequisites": prerequisites,
                }
            )
        parsed.sort(
            key=lambda item: (-(item["information"] + item["risk"]) / item["cost"], item["id"])
        )
        selected: set[str] = set()
        remaining = budget
        chosen: list[dict[str, Any]] = []
        for item in parsed:
            if maximum_experiments is not None and len(chosen) >= maximum_experiments:
                break
            missing = tuple(dep for dep in item["prerequisites"] if dep not in selected)
            if missing:
                continue
            if item["cost"] <= remaining:
                selected.add(item["id"])
                chosen.append(item)
                remaining -= item["cost"]
        experiments = tuple(
            ValueOfInformationExperiment(
                item["id"],
                context_key,
                round(item["cost"], 6),
                round(item["information"], 6),
                round(item["risk"], 6),
                round((item["information"] + item["risk"]) / item["cost"], 6),
                item["prerequisites"],
                item["id"] in selected,
                "selected_by_value_density"
                if item["id"] in selected
                else "not_selected_within_constraints",
                FrontierState.ACCEPTED if item["id"] in selected else FrontierState.REVIEW,
            )
            for item in parsed
        )
        selected_ids = tuple(item["id"] for item in chosen)
        payload = {"plan_id": plan_id, "context_key": context_key, "experiments": experiments}
        return ValueOfInformationPlan(
            plan_id,
            context_key,
            budget,
            selected_ids,
            round(sum(item["cost"] for item in chosen), 6),
            round(sum(item["information"] for item in chosen), 6),
            round(sum(item["risk"] for item in chosen), 6),
            experiments,
            _address(payload),
            FrontierState.ACCEPTED if selected_ids else FrontierState.REVIEW,
        )


@dataclass(frozen=True, slots=True)
class ExperimentPackage:
    package_id: str
    context_key: str
    experiment_ids: tuple[str, ...]
    control_ids: tuple[str, ...]
    protocol_ids: tuple[str, ...]
    files: Mapping[str, Mapping[str, Any]]
    manifest_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ExperimentPackageExporter:
    """Export validation package manifests with hashes for every declared file."""

    def export(
        self,
        payload: Mapping[str, Any],
        *,
        package_id: str,
        context_key: str,
        schema_version: str = "validation-package-v1",
    ) -> ExperimentPackage:
        package_id = require_non_empty(package_id, "package_id")
        context_key = require_non_empty(context_key, "context_key")
        data = _mapping(payload, label="experiment package")
        experiments = tuple(
            _mapping(item, label="experiment") for item in data.get("experiments", ())
        )
        controls = tuple(_mapping(item, label="control") for item in data.get("controls", ()))
        protocols = tuple(_mapping(item, label="protocol") for item in data.get("protocols", ()))
        if not experiments:
            raise ValidationError("experiment package must contain experiments")
        experiment_ids = tuple(
            sorted(
                {
                    _required_text(item.get("experiment_id", item.get("id")), field="experiment_id")
                    for item in experiments
                }
            )
        )
        control_ids = tuple(
            sorted(
                {
                    _required_text(item.get("control_id", item.get("id")), field="control_id")
                    for item in controls
                }
            )
        )
        protocol_ids = tuple(
            sorted(
                {
                    _required_text(item.get("protocol_id", item.get("id")), field="protocol_id")
                    for item in protocols
                }
            )
        )
        files: dict[str, Mapping[str, Any]] = {}
        for name, rows in (
            ("experiments.json", experiments),
            ("controls.json", controls),
            ("protocols.json", protocols),
        ):
            if rows:
                content = jsonable(rows)
                files[name] = {
                    "content": content,
                    "content_address": content_hash(content),
                    "schema_version": schema_version,
                }
        manifest = {
            "package_id": package_id,
            "context_key": context_key,
            "experiment_ids": experiment_ids,
            "control_ids": control_ids,
            "protocol_ids": protocol_ids,
            "files": files,
            "schema_version": schema_version,
        }
        return ExperimentPackage(
            package_id,
            context_key,
            experiment_ids,
            control_ids,
            protocol_ids,
            files,
            _address(manifest),
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class ClaimUpdate:
    claim_id: str
    context_key: str
    previous_state: str
    new_state: str
    result_id: str
    evidence_address: str
    changed_fields: tuple[str, ...]
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ClaimUpdateReport:
    updates: tuple[ClaimUpdate, ...]
    updated_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ResultIngestionClaimUpdater:
    """Ingest declared experiment results and update claims with receipts."""

    def update(
        self,
        claims: Iterable[Mapping[str, Any]],
        results: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> ClaimUpdateReport:
        context_key = require_non_empty(context_key, "context_key")
        claim_map = {
            _required_text(item.get("claim_id", item.get("id")), field="claim_id"): _mapping(
                item, label="claim"
            )
            for item in claims
        }
        updates: list[ClaimUpdate] = []
        for index, raw in enumerate(results, start=1):
            result = _mapping(raw, label=f"result {index}")
            claim_id = _required_text(result.get("claim_id"), field="claim_id")
            result_id = (
                _text(result.get("result_id", result.get("id")), field="result_id")
                or f"result:{index}"
            )
            evidence_address = _required_text(
                result.get("evidence_address", _address(result)), field="evidence_address"
            )
            prior = claim_map.get(claim_id)
            issues: list[FrontierIssue] = []
            if prior is None:
                issues.append(
                    FrontierIssue(
                        "unknown_claim",
                        "result references a claim absent from the claim set",
                        "review",
                        "claim_id",
                        claim_id,
                    )
                )
                previous_state = "unknown"
            else:
                previous_state = (
                    _text(prior.get("state", "unclassified"), field="previous_state")
                    or "unclassified"
                )
            result_state = (
                _text(
                    result.get("claim_state", result.get("status", "needs_review")),
                    field="claim_state",
                )
                or "needs_review"
            )
            changed = tuple(
                sorted(
                    field
                    for field in ("state", "effect_direction", "effect_size", "evidence_address")
                    if prior is None
                    or prior.get(field)
                    != result.get(field, evidence_address if field == "evidence_address" else None)
                )
            )
            if _context(result, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "result_context_mismatch",
                        "result context differs from requested context",
                        "blocking",
                        "context_key",
                        result_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            updates.append(
                ClaimUpdate(
                    claim_id,
                    context_key,
                    previous_state,
                    result_state,
                    result_id,
                    evidence_address,
                    changed,
                    state,
                    tuple(issues),
                )
            )
        updated = tuple(item.claim_id for item in updates if item.state == FrontierState.ACCEPTED)
        review = tuple(item.claim_id for item in updates if item.state != FrontierState.ACCEPTED)
        return ClaimUpdateReport(tuple(updates), updated, review, _address(updates))


@dataclass(frozen=True, slots=True)
class ReclassificationDecision:
    claim_id: str
    context_key: str
    previous_classification: str
    proposed_classification: str
    evidence_score: float
    required_score: float
    reviewer_ids: tuple[str, ...]
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReclassificationReport:
    decisions: tuple[ReclassificationDecision, ...]
    accepted_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReclassificationEngine:
    """Reclassify evidence claims from declared scores and reviewer gates."""

    def reclassify(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_reviewers: int = 2,
        classification_thresholds: Mapping[str, float] | None = None,
    ) -> ReclassificationReport:
        context_key = require_non_empty(context_key, "context_key")
        if minimum_reviewers < 1:
            raise ValidationError("minimum_reviewers must be positive")
        thresholds = {
            str(key): _bounded(value, field=f"threshold:{key}")
            for key, value in (
                classification_thresholds or {"supported": 0.75, "suggestive": 0.5}
            ).items()
        }
        decisions: list[ReclassificationDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"reclassification {index}")
            claim_id = (
                _text(row.get("claim_id", row.get("id")), field="claim_id") or f"claim:{index}"
            )
            previous = (
                _text(row.get("classification", "unclassified"), field="classification")
                or "unclassified"
            )
            score = _bounded(row.get("evidence_score", 0.0), field="evidence_score")
            reviewers = _tuple_text(row.get("reviewer_ids", ()), field="reviewer_ids")
            ordered = sorted(thresholds.items(), key=lambda item: (-item[1], item[0]))
            proposed = next(
                (name for name, threshold in ordered if score >= threshold), "insufficient"
            )
            issues: list[FrontierIssue] = []
            if len(reviewers) < minimum_reviewers:
                issues.append(
                    FrontierIssue(
                        "insufficient_reviewers",
                        "reclassification lacks the required independent reviewers",
                        "review",
                        record_id=claim_id,
                    )
                )
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "reclassification_context_mismatch",
                        "claim context differs from request",
                        "blocking",
                        "context_key",
                        claim_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            decisions.append(
                ReclassificationDecision(
                    claim_id,
                    context_key,
                    previous,
                    proposed,
                    score,
                    thresholds.get(proposed, 1.0),
                    reviewers,
                    state,
                    tuple(issues),
                )
            )
        accepted = tuple(
            item.claim_id for item in decisions if item.state == FrontierState.ACCEPTED
        )
        review = tuple(item.claim_id for item in decisions if item.state != FrontierState.ACCEPTED)
        return ReclassificationReport(tuple(decisions), accepted, review, _address(decisions))


@dataclass(frozen=True, slots=True)
class SupersessionDecision:
    record_id: str
    context_key: str
    status: str
    supersedes: tuple[str, ...]
    superseded_by: str | None
    effective_at: str
    reason: str
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SupersessionReport:
    decisions: tuple[SupersessionDecision, ...]
    active_ids: tuple[str, ...]
    deprecated_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DeprecationSupersessionManager:
    """Manage claim supersession with cycle and missing-target detection."""

    def manage(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> SupersessionReport:
        context_key = require_non_empty(context_key, "context_key")
        rows = tuple(_mapping(item, label="supersession record") for item in records)
        identifiers = {
            _required_text(row.get("record_id", row.get("id")), field="record_id") for row in rows
        }
        decisions: list[SupersessionDecision] = []
        for raw in rows:
            record_id = _required_text(raw.get("record_id", raw.get("id")), field="record_id")
            supersedes = _tuple_text(raw.get("supersedes", ()), field="supersedes")
            successor = _text(raw.get("superseded_by"), field="superseded_by") or None
            status = _text(raw.get("status", "active"), field="status").lower() or "active"
            reason = _required_text(raw.get("reason", "unspecified"), field="reason")
            issues: list[FrontierIssue] = []
            if successor == record_id:
                issues.append(
                    FrontierIssue(
                        "self_supersession",
                        "record cannot supersede itself",
                        "blocking",
                        "superseded_by",
                        record_id,
                    )
                )
            if successor and successor not in identifiers:
                issues.append(
                    FrontierIssue(
                        "missing_successor",
                        "superseded-by target is absent",
                        "review",
                        "superseded_by",
                        record_id,
                    )
                )
            if any(item not in identifiers for item in supersedes):
                issues.append(
                    FrontierIssue(
                        "missing_predecessor",
                        "one or more superseded records are absent",
                        "review",
                        "supersedes",
                        record_id,
                    )
                )
            if _context(raw, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "supersession_context_mismatch",
                        "record context differs from request",
                        "blocking",
                        "context_key",
                        record_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            decisions.append(
                SupersessionDecision(
                    record_id,
                    context_key,
                    status,
                    supersedes,
                    successor,
                    _now_text(raw.get("effective_at")),
                    reason,
                    state,
                    tuple(issues),
                )
            )
        by_id = {item.record_id: item for item in decisions}
        for item in decisions:
            seen: set[str] = set()
            current = item.superseded_by
            cycle = False
            while current:
                if current in seen or current == item.record_id:
                    cycle = True
                    break
                seen.add(current)
                current = by_id.get(current).superseded_by if by_id.get(current) else None
            if cycle:
                issue = FrontierIssue(
                    "supersession_cycle",
                    "supersession graph contains a cycle",
                    "blocking",
                    "superseded_by",
                    item.record_id,
                )
                decisions[decisions.index(item)] = SupersessionDecision(
                    item.record_id,
                    item.context_key,
                    item.status,
                    item.supersedes,
                    item.superseded_by,
                    item.effective_at,
                    item.reason,
                    FrontierState.REVIEW,
                    item.issues + (issue,),
                )
        active = tuple(
            item.record_id
            for item in decisions
            if item.status == "active" and item.state == FrontierState.ACCEPTED
        )
        deprecated = tuple(
            item.record_id for item in decisions if item.status in {"deprecated", "superseded"}
        )
        return SupersessionReport(tuple(decisions), active, deprecated, _address(decisions))


@dataclass(frozen=True, slots=True)
class ReproducibilityBundle:
    bundle_id: str
    context_key: str
    section_addresses: Mapping[str, str]
    item_counts: Mapping[str, int]
    manifest_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AuditReproducibilityBundleBuilder:
    """Build a sorted audit bundle from evidence, review, and release sections."""

    def build(
        self,
        sections: Mapping[str, Iterable[Mapping[str, Any]] | Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        required_sections: Sequence[str] = ("evidence", "review", "release"),
    ) -> ReproducibilityBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        required = tuple(
            require_non_empty(str(item), "required_section") for item in required_sections
        )
        addresses: dict[str, str] = {}
        counts: dict[str, int] = {}
        for section in required:
            if section not in sections:
                raise ValidationError(f"reproducibility bundle is missing section: {section}")
            raw = sections[section]
            value: Any
            if isinstance(raw, Mapping):
                value = dict(raw)
                count = len(raw)
            else:
                value = tuple(dict(_mapping(item, label=f"{section} item")) for item in raw)
                count = len(value)
            addresses[section] = _address(value)
            counts[section] = count
        manifest = {
            "bundle_id": bundle_id,
            "context_key": context_key,
            "section_addresses": addresses,
            "item_counts": counts,
        }
        return ReproducibilityBundle(
            bundle_id, context_key, addresses, counts, _address(manifest), FrontierState.PUBLISHED
        )


@dataclass(frozen=True, slots=True)
class SignedDossier:
    dossier_id: str
    context_key: str
    key_id: str
    audience: tuple[str, ...]
    expires_at: str | None
    payload: Mapping[str, Any]
    payload_address: str
    signature: str
    dossier_address: str
    state: FrontierState

    def signing_body(self) -> dict[str, Any]:
        return {
            "dossier_id": self.dossier_id,
            "context_key": self.context_key,
            "key_id": self.key_id,
            "audience": self.audience,
            "expires_at": self.expires_at,
            "payload": self.payload,
            "payload_address": self.payload_address,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DossierVerification:
    valid_signature: bool
    payload_address_matches: bool
    expired: bool
    audience_allowed: bool
    state: FrontierReleaseState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SignedDossierPublisher:
    """Publish and verify HMAC-signed research dossiers."""

    @staticmethod
    def _signature(body: Mapping[str, Any], secret: str) -> str:
        import hashlib
        import hmac

        return hmac.new(
            secret.encode("utf-8"), canonical_json(body).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def publish(
        self,
        payload: Mapping[str, Any],
        *,
        dossier_id: str,
        context_key: str,
        key_id: str,
        signing_secret: str,
        audience: Sequence[str] = (),
        expires_at: str | None = None,
    ) -> SignedDossier:
        dossier_id = require_non_empty(dossier_id, "dossier_id")
        context_key = require_non_empty(context_key, "context_key")
        key_id = require_non_empty(key_id, "key_id")
        signing_secret = require_non_empty(signing_secret, "signing_secret")
        normalized = jsonable(dict(_mapping(payload, label="dossier payload")))
        payload_address = _address(normalized)
        audience_tuple = tuple(
            sorted({require_non_empty(str(item), "audience") for item in audience})
        )
        body = {
            "dossier_id": dossier_id,
            "context_key": context_key,
            "key_id": key_id,
            "audience": audience_tuple,
            "expires_at": expires_at,
            "payload": normalized,
            "payload_address": payload_address,
        }
        signature = self._signature(body, signing_secret)
        address = _address({"body": body, "signature": signature})
        return SignedDossier(
            dossier_id,
            context_key,
            key_id,
            audience_tuple,
            expires_at,
            normalized,
            payload_address,
            signature,
            address,
            FrontierState.PUBLISHED,
        )

    def verify(
        self,
        dossier: Mapping[str, Any],
        *,
        signing_secret: str,
        audience: str | None = None,
        now: str | None = None,
    ) -> DossierVerification:
        signing_secret = require_non_empty(signing_secret, "signing_secret")
        raw = _mapping(dossier, label="signed dossier")
        payload = _mapping(raw.get("payload", {}), label="dossier payload")
        body = {
            "dossier_id": raw.get("dossier_id"),
            "context_key": raw.get("context_key"),
            "key_id": raw.get("key_id"),
            "audience": tuple(raw.get("audience", ())),
            "expires_at": raw.get("expires_at"),
            "payload": payload,
            "payload_address": raw.get("payload_address"),
        }
        expected = self._signature(body, signing_secret)
        actual = _text(raw.get("signature"), field="signature")
        valid_signature = hmac_compare(expected, actual)
        payload_matches = _address(payload) == _text(
            raw.get("payload_address"), field="payload_address"
        )
        expires_at = _text(raw.get("expires_at"), field="expires_at") or None
        expired = bool(expires_at and now and now >= expires_at)
        audiences = set(_tuple_text(raw.get("audience", ()), field="audience"))
        allowed = audience is None or audience in audiences
        issues: list[FrontierIssue] = []
        if not valid_signature:
            issues.append(
                FrontierIssue(
                    "invalid_dossier_signature", "dossier signature does not verify", "blocking"
                )
            )
        if not payload_matches:
            issues.append(
                FrontierIssue(
                    "dossier_payload_hash_mismatch",
                    "payload address does not match payload",
                    "blocking",
                )
            )
        if expired:
            issues.append(
                FrontierIssue(
                    "dossier_expired", "dossier expiry is before verification time", "review"
                )
            )
        if not allowed:
            issues.append(
                FrontierIssue(
                    "dossier_audience_denied", "requested audience is not listed", "blocking"
                )
            )
        state = FrontierReleaseState.READY if not issues else FrontierReleaseState.DENIED
        return DossierVerification(
            valid_signature, payload_matches, expired, allowed, state, tuple(issues)
        )


def hmac_compare(expected: str, actual: str) -> bool:
    import hmac

    return hmac.compare_digest(expected, actual)


@dataclass(frozen=True, slots=True)
class ReviewFormFieldResult:
    field_id: str
    label: str
    value: Any
    required: bool
    valid: bool
    issue: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuredReviewResult:
    form_id: str
    context_key: str
    reviewer_id: str
    fields: tuple[ReviewFormFieldResult, ...]
    valid: bool
    completion: float
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class StructuredReviewForm:
    """Validate structured reviewer forms against a declared field schema."""

    def evaluate(
        self,
        schema: Iterable[Mapping[str, Any]],
        response: Mapping[str, Any],
        *,
        form_id: str,
        context_key: str,
        reviewer_id: str,
    ) -> StructuredReviewResult:
        form_id = require_non_empty(form_id, "form_id")
        context_key = require_non_empty(context_key, "context_key")
        reviewer_id = require_non_empty(reviewer_id, "reviewer_id")
        data = _mapping(response, label="review response")
        fields: list[ReviewFormFieldResult] = []
        for index, raw in enumerate(schema, start=1):
            item = _mapping(raw, label=f"form field {index}")
            field_id = (
                _text(item.get("field_id", item.get("id")), field="field_id") or f"field:{index}"
            )
            label = _text(item.get("label", field_id), field="label") or field_id
            required = bool(item.get("required", False))
            value = data.get(field_id)
            valid = value is not None and (not isinstance(value, str) or bool(value.strip()))
            issue = None if valid or not required else "required_field_missing"
            if valid and "choices" in item and value not in item["choices"]:
                valid = False
                issue = "value_not_in_declared_choices"
            fields.append(ReviewFormFieldResult(field_id, label, value, required, valid, issue))
        completion = round(sum(item.valid for item in fields) / max(1, len(fields)), 6)
        valid = all(item.valid for item in fields if item.required)
        state = FrontierState.ACCEPTED if valid else FrontierState.REVIEW
        return StructuredReviewResult(
            form_id,
            context_key,
            reviewer_id,
            tuple(fields),
            valid,
            completion,
            state,
            _address(fields),
        )


@dataclass(frozen=True, slots=True)
class ReportSection:
    section_id: str
    title: str
    order: int
    content: Any
    content_address: str
    line_count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ExportedReport:
    report_id: str
    context_key: str
    format: str
    sections: tuple[ReportSection, ...]
    report_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ExportReportBuilder:
    """Build deterministic JSON, Markdown, or CSV-oriented report sections."""

    def build(
        self,
        sections: Iterable[Mapping[str, Any]],
        *,
        report_id: str,
        context_key: str,
        format: str = "json",
    ) -> ExportedReport:
        report_id = require_non_empty(report_id, "report_id")
        context_key = require_non_empty(context_key, "context_key")
        format = require_non_empty(format, "format").lower()
        if format not in {"json", "markdown", "csv"}:
            raise ValidationError("format must be json, markdown, or csv")
        output: list[ReportSection] = []
        for index, raw in enumerate(sections, start=1):
            row = _mapping(raw, label=f"report section {index}")
            section_id = (
                _text(row.get("section_id", row.get("id")), field="section_id")
                or f"section:{index}"
            )
            title = _text(row.get("title", section_id), field="title") or section_id
            order = int(row.get("order", index))
            content = jsonable(row.get("content", row.get("records", ())))
            if format == "markdown":
                rendered = {"markdown": f"## {title}\n\n{canonical_json(content)}"}
            elif format == "csv":
                rendered = {"rows": content}
            else:
                rendered = {"content": content}
            line_count = len(canonical_json(rendered).splitlines())
            output.append(
                ReportSection(section_id, title, order, rendered, _address(rendered), line_count)
            )
        ordered = tuple(sorted(output, key=lambda item: (item.order, item.section_id)))
        address = _address(
            {
                "report_id": report_id,
                "context_key": context_key,
                "format": format,
                "sections": ordered,
            }
        )
        return ExportedReport(
            report_id, context_key, format, ordered, address, FrontierState.PUBLISHED
        )


@dataclass(frozen=True, slots=True)
class SearchResult:
    record_id: str
    record_type: str
    title: str
    matched_fields: tuple[str, ...]
    score: float
    command: str | None

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SearchPaletteReport:
    query: str
    results: tuple[SearchResult, ...]
    commands: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class GlobalSearchCommandPalette:
    """Search structured research records and declared commands deterministically."""

    def search(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        query: str,
        commands: Sequence[str] = (),
        record_type: str | None = None,
        maximum_results: int = 20,
    ) -> SearchPaletteReport:
        query = _text(query, field="query").lower()
        if not query:
            raise ValidationError("query must not be empty")
        if maximum_results < 1:
            raise ValidationError("maximum_results must be positive")
        found: list[SearchResult] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"search record {index}")
            identifier = (
                _text(row.get("record_id", row.get("id")), field="record_id") or f"record:{index}"
            )
            kind = (
                _text(row.get("record_type", row.get("type", "record")), field="record_type")
                or "record"
            )
            if record_type and kind != record_type:
                continue
            matched: list[str] = []
            score = 0.0
            for field, value in row.items():
                text = _text(value, field=str(field)).lower()
                if query in text:
                    matched.append(str(field))
                    score += 2.0 if str(field) in {"record_id", "id", "title", "name"} else 1.0
            if matched:
                found.append(
                    SearchResult(
                        identifier,
                        kind,
                        _text(row.get("title", identifier), field="title") or identifier,
                        tuple(sorted(matched)),
                        round(score, 6),
                        None,
                    )
                )
        command_matches = tuple(sorted(command for command in commands if query in command.lower()))
        found.extend(
            SearchResult(f"command:{command}", "command", command, ("command",), 3.0, command)
            for command in command_matches
        )
        found.sort(key=lambda item: (-item.score, item.record_type, item.record_id))
        return SearchPaletteReport(
            query,
            tuple(found[:maximum_results]),
            command_matches,
            _address(found[:maximum_results]),
        )


@dataclass(frozen=True, slots=True)
class AccessibilityFinding:
    surface_id: str
    criterion: str
    passed: bool
    severity: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AccessibilityReport:
    surface_id: str
    findings: tuple[AccessibilityFinding, ...]
    pass_count: int
    fail_count: int
    score: float
    state: FrontierState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class AccessibilityHumanFactorsLayer:
    """Evaluate declared accessibility and human-factors checks."""

    _criteria = ("keyboard", "label", "focus_order", "contrast", "motion", "reading_order")

    def evaluate(
        self,
        surface: Mapping[str, Any],
        *,
        surface_id: str,
        required_criteria: Sequence[str] | None = None,
    ) -> AccessibilityReport:
        surface_id = require_non_empty(surface_id, "surface_id")
        data = _mapping(surface, label="accessibility surface")
        criteria = tuple(required_criteria or self._criteria)
        findings: list[AccessibilityFinding] = []
        for criterion in criteria:
            criterion = require_non_empty(str(criterion), "criterion")
            passed = _bool(data.get(criterion, False), field=criterion)
            findings.append(
                AccessibilityFinding(
                    surface_id,
                    criterion,
                    passed,
                    "blocking" if not passed else "info",
                    "criterion passed" if passed else "criterion requires remediation",
                )
            )
        passed_count = sum(item.passed for item in findings)
        fail_count = len(findings) - passed_count
        score = round(passed_count / max(1, len(findings)), 6)
        state = FrontierState.ACCEPTED if fail_count == 0 else FrontierState.REVIEW
        return AccessibilityReport(
            surface_id, tuple(findings), passed_count, fail_count, score, state, _address(findings)
        )


@dataclass(frozen=True, slots=True)
class SecurityPolicyDecision:
    request_id: str
    context_key: str
    subject_id: str
    action: str
    allowed: bool
    reasons: tuple[str, ...]
    matched_policies: tuple[str, ...]
    state: FrontierReleaseState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SecurityPolicyReport:
    decisions: tuple[SecurityPolicyDecision, ...]
    allowed_ids: tuple[str, ...]
    denied_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PrivacySecurityPolicyEngine:
    """Apply deny-by-default privacy, role, network, and retention policies."""

    def evaluate(
        self,
        requests: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        policies: Mapping[str, Mapping[str, Any]],
    ) -> SecurityPolicyReport:
        context_key = require_non_empty(context_key, "context_key")
        policy_map = {
            str(key): _mapping(value, label=f"policy {key}") for key, value in policies.items()
        }
        decisions: list[SecurityPolicyDecision] = []
        for index, raw in enumerate(requests, start=1):
            row = _mapping(raw, label=f"security request {index}")
            request_id = (
                _text(row.get("request_id", row.get("id")), field="request_id")
                or f"request:{index}"
            )
            subject = _required_text(row.get("subject_id"), field="subject_id")
            action = _required_text(row.get("action"), field="action")
            roles = set(_tuple_text(row.get("roles", ()), field="roles"))
            required_role = _text(row.get("required_role"), field="required_role") or None
            sensitive = bool(row.get("sensitive", False))
            network = bool(row.get("network", False))
            retention_days = int(row.get("retention_days", 0))
            reasons: list[str] = []
            matched: list[str] = []
            for policy_id, policy in sorted(policy_map.items()):
                actions = set(_tuple_text(policy.get("actions", ()), field="actions"))
                if actions and action not in actions and "*" not in actions:
                    continue
                matched.append(policy_id)
                allowed_roles = set(_tuple_text(policy.get("roles", ()), field="policy_roles"))
                if allowed_roles and not roles.intersection(allowed_roles):
                    reasons.append(f"role_not_allowed:{policy_id}")
                if required_role and required_role not in roles:
                    reasons.append(f"required_role_missing:{required_role}")
                if sensitive and not bool(policy.get("sensitive_access", False)):
                    reasons.append(f"sensitive_access_denied:{policy_id}")
                if network and not bool(policy.get("network_access", False)):
                    reasons.append(f"network_access_denied:{policy_id}")
                maximum_retention = int(policy.get("maximum_retention_days", 0))
                if maximum_retention and retention_days > maximum_retention:
                    reasons.append(f"retention_exceeded:{policy_id}")
            if _context(row, context_key) != context_key:
                reasons.append("context_mismatch")
            if not matched:
                reasons.append("no_matching_policy")
            allowed = bool(matched) and not reasons
            decisions.append(
                SecurityPolicyDecision(
                    request_id,
                    context_key,
                    subject,
                    action,
                    allowed,
                    tuple(sorted(set(reasons))),
                    tuple(matched),
                    FrontierReleaseState.READY if allowed else FrontierReleaseState.DENIED,
                )
            )
        allowed_ids = tuple(item.request_id for item in decisions if item.allowed)
        denied_ids = tuple(item.request_id for item in decisions if not item.allowed)
        return SecurityPolicyReport(tuple(decisions), allowed_ids, denied_ids, _address(decisions))


@dataclass(frozen=True, slots=True)
class DeploymentArtifact:
    artifact_id: str
    version: str
    digest: str
    size_bytes: int
    required_runtime: str
    local_only: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LocalDeploymentBundle:
    bundle_id: str
    platform: str
    runtime_version: str
    artifacts: tuple[DeploymentArtifact, ...]
    services: tuple[Mapping[str, Any], ...]
    environment_requirements: Mapping[str, str]
    offline: bool
    manifest_address: str
    state: FrontierReleaseState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LocalDeploymentBundleBuilder:
    """Assemble an offline-capable deployment manifest with artifact digests."""

    def build(
        self,
        payload: Mapping[str, Any],
        *,
        bundle_id: str,
        platform: str,
        runtime_version: str,
        offline: bool = True,
    ) -> LocalDeploymentBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        platform = require_non_empty(platform, "platform")
        runtime_version = require_non_empty(runtime_version, "runtime_version")
        data = _mapping(payload, label="deployment bundle")
        artifacts: list[DeploymentArtifact] = []
        for index, raw in enumerate(data.get("artifacts", ()), start=1):
            row = _mapping(raw, label=f"deployment artifact {index}")
            artifacts.append(
                DeploymentArtifact(
                    _required_text(row.get("artifact_id", row.get("id")), field="artifact_id"),
                    _required_text(row.get("version"), field="version"),
                    _required_text(row.get("digest"), field="digest"),
                    int(row.get("size_bytes", 0)),
                    _required_text(
                        row.get("required_runtime", runtime_version), field="required_runtime"
                    ),
                    bool(row.get("local_only", offline)),
                )
            )
        services = tuple(
            dict(_mapping(item, label="deployment service")) for item in data.get("services", ())
        )
        env_raw = data.get("environment_requirements", {})
        env = {
            str(key): _required_text(value, field=f"environment:{key}")
            for key, value in _mapping(env_raw, label="environment_requirements").items()
        }
        if not artifacts or not services:
            raise ValidationError("deployment bundle requires artifacts and services")
        manifest = {
            "bundle_id": bundle_id,
            "platform": platform,
            "runtime_version": runtime_version,
            "artifacts": artifacts,
            "services": services,
            "environment_requirements": env,
            "offline": offline,
        }
        state = (
            FrontierReleaseState.READY
            if all(item.digest.startswith("sha256:") for item in artifacts)
            else FrontierReleaseState.HOLD
        )
        return LocalDeploymentBundle(
            bundle_id,
            platform,
            runtime_version,
            tuple(artifacts),
            services,
            env,
            offline,
            _address(manifest),
            state,
        )


@dataclass(frozen=True, slots=True)
class FederatedAssignment:
    task_id: str
    site_id: str
    eligible: bool
    reason: str
    privacy_cost: int
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FederatedExecutionPlan:
    plan_id: str
    context_key: str
    assignments: tuple[FederatedAssignment, ...]
    eligible_task_ids: tuple[str, ...]
    denied_task_ids: tuple[str, ...]
    aggregate_address: str
    state: FrontierReleaseState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FederatedExecutionCoordinator:
    """Coordinate site-local tasks under locality, privacy, and availability gates."""

    def coordinate(
        self,
        tasks: Iterable[Mapping[str, Any]],
        sites: Iterable[Mapping[str, Any]],
        *,
        plan_id: str,
        context_key: str,
        privacy_budget: int,
        minimum_site_count: int = 1,
    ) -> FederatedExecutionPlan:
        plan_id = require_non_empty(plan_id, "plan_id")
        context_key = require_non_empty(context_key, "context_key")
        if privacy_budget < 0 or minimum_site_count < 1:
            raise ValidationError(
                "privacy_budget and minimum_site_count must be nonnegative/positive"
            )
        site_rows = tuple(_mapping(item, label="federated site") for item in sites)
        assignments: list[FederatedAssignment] = []
        for index, raw in enumerate(tasks, start=1):
            task = _mapping(raw, label=f"federated task {index}")
            task_id = _text(task.get("task_id", task.get("id")), field="task_id") or f"task:{index}"
            required_sites = set(_tuple_text(task.get("site_ids", ()), field="site_ids"))
            task_cost = int(task.get("privacy_cost", 0))
            for site in site_rows:
                site_id = _required_text(site.get("site_id", site.get("id")), field="site_id")
                if required_sites and site_id not in required_sites:
                    continue
                reasons: list[str] = []
                if not bool(site.get("available", True)):
                    reasons.append("site_unavailable")
                if context_key not in set(
                    _tuple_text(
                        site.get("supported_contexts", (context_key,)), field="supported_contexts"
                    )
                ):
                    reasons.append("context_not_supported")
                if task_cost > privacy_budget:
                    reasons.append("privacy_budget_exceeded")
                if int(site.get("sample_count", 0)) < int(task.get("minimum_sample_count", 0)):
                    reasons.append("sample_count_below_minimum")
                eligible = not reasons
                assignments.append(
                    FederatedAssignment(
                        task_id,
                        site_id,
                        eligible,
                        "eligible" if eligible else ";".join(sorted(reasons)),
                        task_cost,
                        FrontierState.ACCEPTED if eligible else FrontierState.REVIEW,
                    )
                )
        grouped: dict[str, list[FederatedAssignment]] = {}
        for assignment in assignments:
            grouped.setdefault(assignment.task_id, []).append(assignment)
        eligible_tasks = tuple(
            task_id
            for task_id, rows in sorted(grouped.items())
            if sum(row.eligible for row in rows) >= minimum_site_count
        )
        denied_tasks = tuple(
            task_id for task_id in sorted(grouped) if task_id not in eligible_tasks
        )
        aggregate = _address(
            {
                "plan_id": plan_id,
                "context_key": context_key,
                "assignments": assignments,
                "eligible_tasks": eligible_tasks,
            }
        )
        return FederatedExecutionPlan(
            plan_id,
            context_key,
            tuple(assignments),
            eligible_tasks,
            denied_tasks,
            aggregate,
            FrontierReleaseState.READY if not denied_tasks else FrontierReleaseState.HOLD,
        )


@dataclass(frozen=True, slots=True)
class ReleaseRollbackDecision:
    release_id: str
    current_version: str
    requested_version: str
    action: str
    checks: Mapping[str, bool]
    failed_checks: tuple[str, ...]
    previous_version: str | None
    state: FrontierReleaseState
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ReleaseRollbackController:
    """Release or roll back versions using explicit health and integrity gates."""

    def decide(
        self,
        *,
        release_id: str,
        current_version: str,
        requested_version: str,
        checks: Mapping[str, Any],
        action: str = "release",
        previous_version: str | None = None,
        required_checks: Sequence[str] = ("tests", "integrity", "compatibility", "policy"),
    ) -> ReleaseRollbackDecision:
        release_id = require_non_empty(release_id, "release_id")
        current_version = require_non_empty(current_version, "current_version")
        requested_version = require_non_empty(requested_version, "requested_version")
        action = require_non_empty(action, "action").lower()
        if action not in {"release", "rollback"}:
            raise ValidationError("action must be release or rollback")
        normalized = {
            require_non_empty(str(key), "check"): _bool(value, field=str(key))
            for key, value in checks.items()
        }
        required = tuple(require_non_empty(str(item), "required_check") for item in required_checks)
        failed = tuple(item for item in required if not normalized.get(item, False))
        if action == "rollback" and previous_version is None:
            failed = failed + ("previous_version_missing",)
        if action == "release" and requested_version == current_version:
            failed = failed + ("version_already_current",)
        state = (
            FrontierReleaseState.RELEASED
            if action == "release" and not failed
            else FrontierReleaseState.ROLLED_BACK
            if action == "rollback" and not failed
            else FrontierReleaseState.DENIED
        )
        address = _address(
            {
                "release_id": release_id,
                "current_version": current_version,
                "requested_version": requested_version,
                "action": action,
                "checks": normalized,
                "failed_checks": failed,
                "previous_version": previous_version,
            }
        )
        return ReleaseRollbackDecision(
            release_id,
            current_version,
            requested_version,
            action,
            normalized,
            failed,
            previous_version,
            state,
            address,
        )


def run_release_frontier_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> Any:
    """Run one D13-D16 frontier operation from a JSON payload."""

    operation = require_non_empty(operation, "operation")
    data = _mapping(payload, label="payload")
    context = context_key or _text(data.get("context_key"), field="context_key")
    if operation == "estimate-off-target-risk":
        return OffTargetRiskEstimator().estimate(
            data.get("records", ()),
            context_key=context,
            review_threshold=_float(data.get("review_threshold", 0.25), field="review_threshold"),
            blocking_threshold=_float(
                data.get("blocking_threshold", 0.6), field="blocking_threshold"
            ),
        )
    if operation == "optimize-validation-voi":
        return ValidationValueOfInformationOptimizer().optimize(
            data.get("records", ()),
            plan_id=_required_text(data.get("plan_id"), field="plan_id"),
            context_key=context,
            budget=_float(data.get("budget"), field="budget"),
            maximum_experiments=int(data["maximum_experiments"])
            if data.get("maximum_experiments") is not None
            else None,
        )
    if operation == "export-experiment-package":
        return ExperimentPackageExporter().export(
            data,
            package_id=_required_text(data.get("package_id"), field="package_id"),
            context_key=context,
            schema_version=_text(
                data.get("schema_version", "validation-package-v1"), field="schema_version"
            )
            or "validation-package-v1",
        )
    if operation == "ingest-result-update-claims":
        return ResultIngestionClaimUpdater().update(
            data.get("claims", ()), data.get("results", ()), context_key=context
        )
    if operation == "reclassify-evidence":
        return ReclassificationEngine().reclassify(
            data.get("records", ()),
            context_key=context,
            minimum_reviewers=int(data.get("minimum_reviewers", 2)),
            classification_thresholds=data.get("classification_thresholds"),
        )
    if operation == "manage-deprecation-supersession":
        return DeprecationSupersessionManager().manage(data.get("records", ()), context_key=context)
    if operation == "build-audit-reproducibility-bundle":
        return AuditReproducibilityBundleBuilder().build(
            data.get("sections", {}),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            required_sections=_tuple_text(
                data.get("required_sections", ("evidence", "review", "release")),
                field="required_sections",
            ),
        )
    if operation == "publish-signed-dossier":
        return SignedDossierPublisher().publish(
            data.get("payload", {}),
            dossier_id=_required_text(data.get("dossier_id"), field="dossier_id"),
            context_key=context,
            key_id=_required_text(data.get("key_id"), field="key_id"),
            signing_secret=_required_text(data.get("signing_secret"), field="signing_secret"),
            audience=_tuple_text(data.get("audience", ()), field="audience"),
            expires_at=_text(data.get("expires_at"), field="expires_at") or None,
        )
    if operation == "verify-signed-dossier":
        return SignedDossierPublisher().verify(
            data.get("dossier", data),
            signing_secret=_required_text(data.get("signing_secret"), field="signing_secret"),
            audience=_text(data.get("audience"), field="audience") or None,
            now=_text(data.get("now"), field="now") or None,
        )
    if operation == "evaluate-structured-review":
        return StructuredReviewForm().evaluate(
            data.get("schema", ()),
            data.get("response", {}),
            form_id=_required_text(data.get("form_id"), field="form_id"),
            context_key=context,
            reviewer_id=_required_text(data.get("reviewer_id"), field="reviewer_id"),
        )
    if operation == "build-export-report":
        return ExportReportBuilder().build(
            data.get("sections", ()),
            report_id=_required_text(data.get("report_id"), field="report_id"),
            context_key=context,
            format=_text(data.get("format", "json"), field="format") or "json",
        )
    if operation == "search-command-palette":
        return GlobalSearchCommandPalette().search(
            data.get("records", ()),
            query=_required_text(data.get("query"), field="query"),
            commands=_tuple_text(data.get("commands", ()), field="commands"),
            record_type=_text(data.get("record_type"), field="record_type") or None,
            maximum_results=int(data.get("maximum_results", 20)),
        )
    if operation == "evaluate-accessibility-human-factors":
        return AccessibilityHumanFactorsLayer().evaluate(
            data.get("surface", {}),
            surface_id=_required_text(data.get("surface_id"), field="surface_id"),
            required_criteria=_tuple_text(
                data.get("required_criteria", ()), field="required_criteria"
            )
            or None,
        )
    if operation == "evaluate-privacy-security-policy":
        return PrivacySecurityPolicyEngine().evaluate(
            data.get("requests", ()),
            context_key=context,
            policies=_mapping(data.get("policies", {}), label="policies"),
        )
    if operation == "build-local-deployment-bundle":
        return LocalDeploymentBundleBuilder().build(
            data,
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            platform=_required_text(data.get("platform"), field="platform"),
            runtime_version=_required_text(data.get("runtime_version"), field="runtime_version"),
            offline=bool(data.get("offline", True)),
        )
    if operation == "coordinate-federated-execution":
        return FederatedExecutionCoordinator().coordinate(
            data.get("tasks", ()),
            data.get("sites", ()),
            plan_id=_required_text(data.get("plan_id"), field="plan_id"),
            context_key=context,
            privacy_budget=int(data.get("privacy_budget", 0)),
            minimum_site_count=int(data.get("minimum_site_count", 1)),
        )
    if operation == "decide-release-rollback":
        return ReleaseRollbackController().decide(
            release_id=_required_text(data.get("release_id"), field="release_id"),
            current_version=_required_text(data.get("current_version"), field="current_version"),
            requested_version=_required_text(
                data.get("requested_version"), field="requested_version"
            ),
            checks=_mapping(data.get("checks", {}), label="checks"),
            action=_text(data.get("action", "release"), field="action") or "release",
            previous_version=_text(data.get("previous_version"), field="previous_version") or None,
            required_checks=_tuple_text(
                data.get("required_checks", ("tests", "integrity", "compatibility", "policy")),
                field="required_checks",
            ),
        )
    raise ValidationError(f"unknown release frontier operation: {operation}")


RELEASE_FRONTIER_OPERATIONS = (
    "estimate-off-target-risk",
    "optimize-validation-voi",
    "export-experiment-package",
    "ingest-result-update-claims",
    "reclassify-evidence",
    "manage-deprecation-supersession",
    "build-audit-reproducibility-bundle",
    "publish-signed-dossier",
    "verify-signed-dossier",
    "evaluate-structured-review",
    "build-export-report",
    "search-command-palette",
    "evaluate-accessibility-human-factors",
    "evaluate-privacy-security-policy",
    "build-local-deployment-bundle",
    "coordinate-federated-execution",
    "decide-release-rollback",
)
