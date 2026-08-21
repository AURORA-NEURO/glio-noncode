"""External-alpha causal-evidence sensitivity and adjudication contracts.

This module adds four bounded evidence operations to Domain 11:

* ``MediationSensitivityAnalyzer`` performs leave-one-source-out sensitivity
  checks around the typed scientific-beta mediator result.
* ``ConfoundingChecklistAdjudicator`` turns declared confounder checks into a
  versioned checklist while retaining unresolved and missing items.
* ``EvidenceDependenceCorrector`` groups correlated evidence paths before a
  descriptive support summary is made.
* ``NegativeEvidenceIntegrator`` keeps negative controls and positive paths
  separate, exposing measured-negative and contradictory states.

These are research evidence controls, not causal identification procedures.
They do not produce calibrated posteriors, diagnoses, treatment guidance, or
actionability decisions. Exact context and source lineage are release gates.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean
from typing import Any

from .causal_beta import (
    CausalBetaState,
    CausalEvidenceDirection,
    CausalMediatorEvidence,
    ElementToGeneCausalMediator,
    GeneToStateCausalMediator,
    MediatorKind,
    SequenceToElementCausalMediator,
)
from .causal_reasoning import CausalState
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class ConfounderDisposition(StrEnum):
    """Adjudication status for one declared confounder."""

    ADDRESSED = "addressed"
    UNRESOLVED = "unresolved"
    MISSING = "missing"
    OUT_OF_DOMAIN = "out_of_domain"
    NOT_APPLICABLE = "not_applicable"


class DependenceMethod(StrEnum):
    """Evidence-dependence correction policy."""

    DECLARED_GROUP = "declared_group"
    SOURCE = "source"
    METHOD_FAMILY = "method_family"


class NegativeEvidencePolarity(StrEnum):
    """Polarity of an evidence or control observation."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEGATIVE_CONTROL = "negative_control"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CausalAlphaIssue:
    """Quarantined alpha row with raw provenance and remediation."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    remediation: str = "Inspect the row, context, and source lineage before retrying."
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "causal alpha issue code")
        require_non_empty(self.message, "causal alpha issue message")
        require_non_empty(self.raw_hash, "causal alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("causal alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MediationLeaveOneOut:
    """One leave-one-source-out mediator rerun."""

    omitted_source_id: str
    remaining_evidence_ids: tuple[str, ...]
    state: CausalBetaState
    support_proxy: float | None
    absolute_delta_from_base: float | None
    source_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MediationSensitivityResult:
    """Sensitivity summary around one typed mediator edge."""

    mediator_kind: MediatorKind
    source_node: str
    target_node: str
    context_key: str
    model_id: str
    model_version: str
    base_state: CausalBetaState
    sensitivity_state: CausalBetaState
    base_support_proxy: float | None
    maximum_absolute_delta: float | None
    robustness_tolerance: float
    robust_to_source_omission: bool | None
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    leave_one_out: tuple[MediationLeaveOneOut, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MediationSensitivityReport:
    """Sensitivity report with input and output receipts."""

    input_hash: str
    result: MediationSensitivityResult
    issues: tuple[CausalAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class MediationSensitivityAnalyzer:
    """Evaluate source-omission sensitivity around a beta mediator result."""

    def analyze(
        self,
        evidence: Iterable[CausalMediatorEvidence | Mapping[str, Any]],
        *,
        mediator_kind: MediatorKind,
        source_node: str,
        target_node: str,
        context_key: str,
        model_id: str,
        model_version: str,
        minimum_sources: int = 2,
        robustness_tolerance: float = 0.20,
    ) -> MediationSensitivityReport:
        values = tuple(_coerce_mediator(item) for item in evidence)
        input_hash = content_hash(values)
        if minimum_sources < 1:
            raise ValidationError("minimum_sources must be positive")
        if not 0 <= robustness_tolerance <= 1:
            raise ValidationError("robustness_tolerance must be between zero and one")
        engine = _mediator_engine(mediator_kind)
        base = engine.evaluate(
            values,
            source_node=source_node,
            target_node=target_node,
            context_key=context_key,
            model_id=model_id,
            model_version=model_version,
            minimum_sources=minimum_sources,
        )
        exact = tuple(
            item
            for item in values
            if item.mediator_kind == mediator_kind
            and item.source_node == source_node
            and item.target_node == target_node
            and item.context_key == context_key
        )
        source_ids = tuple(sorted({item.source_id for item in exact}))
        leave_one_out: list[MediationLeaveOneOut] = []
        for source_id in source_ids:
            remaining = tuple(item for item in values if item.source_id != source_id)
            rerun = engine.evaluate(
                remaining,
                source_node=source_node,
                target_node=target_node,
                context_key=context_key,
                model_id=model_id,
                model_version=model_version,
                minimum_sources=minimum_sources,
            )
            delta = (
                abs(base.support - rerun.support)
                if base.support is not None and rerun.support is not None
                else None
            )
            omitted = tuple(item.evidence_id for item in exact if item.source_id != source_id)
            leave_one_out.append(
                MediationLeaveOneOut(
                    omitted_source_id=source_id,
                    remaining_evidence_ids=omitted,
                    state=rerun.state,
                    support_proxy=rerun.support,
                    absolute_delta_from_base=None if delta is None else round(delta, 9),
                    source_ids=tuple(
                        sorted(
                            {
                                item.source_id
                                for item in remaining
                                if item.context_key == context_key
                            }
                        )
                    ),
                    content_address=content_hash(
                        {
                            "omitted_source_id": source_id,
                            "remaining_evidence_ids": omitted,
                            "state": rerun.state,
                            "support": rerun.support,
                            "delta": delta,
                        }
                    ),
                )
            )
        deltas = tuple(
            item.absolute_delta_from_base
            for item in leave_one_out
            if item.absolute_delta_from_base is not None
        )
        maximum = max(deltas) if deltas else None
        robust = None if maximum is None else maximum <= robustness_tolerance
        state = base.state
        if state == CausalBetaState.SUPPORTED and robust is False:
            state = CausalBetaState.PARTIAL
        reason = (
            "mediator has no exact-context evidence for source-omission sensitivity"
            if not exact
            else "source-omission sensitivity was evaluated against the declared tolerance"
        )
        result = MediationSensitivityResult(
            mediator_kind=mediator_kind,
            source_node=source_node,
            target_node=target_node,
            context_key=context_key,
            model_id=model_id,
            model_version=model_version,
            base_state=base.state,
            sensitivity_state=state,
            base_support_proxy=base.support,
            maximum_absolute_delta=None if maximum is None else round(maximum, 9),
            robustness_tolerance=robustness_tolerance,
            robust_to_source_omission=robust,
            evidence_ids=tuple(item.evidence_id for item in exact),
            source_ids=source_ids,
            leave_one_out=tuple(leave_one_out),
            reason=reason,
            limitations=(
                "Leave-one-source-out sensitivity is a bounded stress test, not a causal "
                "identification result.",
                "Source independence, model calibration, negative controls, transport, and "
                "OOD validation remain.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "base": base,
                    "state": state,
                    "leave_one_out": leave_one_out,
                }
            ),
        )
        return MediationSensitivityReport(
            input_hash=input_hash,
            result=result,
            issues=(),
            warnings=(
                "Sensitivity depends on the declared source grouping and model version.",
                "A robust result does not establish a causal effect or clinical interpretation.",
            ),
            content_address=content_hash({"input_hash": input_hash, "result": result}),
        )


@dataclass(frozen=True, slots=True)
class ConfounderObservation:
    """One declared confounder check."""

    observation_id: str
    confounder_id: str
    label: str
    status: str
    severity: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    addressed: bool | None = None
    adjustment_method: str | None = None
    notes: str = ""
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "confounder_id",
            "label",
            "status",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.severity <= 1:
            raise ValidationError("confounder severity must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ConfounderAdjudication:
    """Adjudicated state for a confounder ID."""

    confounder_id: str
    label: str
    disposition: ConfounderDisposition
    severity: float | None
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    adjustment_methods: tuple[str, ...]
    reason: str
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ConfoundingAdjudicationReport:
    """Confounder checklist output."""

    input_hash: str
    context_key: str | None
    state: CausalState
    adjudications: tuple[ConfounderAdjudication, ...]
    missing_confounder_ids: tuple[str, ...]
    unresolved_confounder_ids: tuple[str, ...]
    issues: tuple[CausalAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ConfoundingChecklistAdjudicator:
    """Adjudicate declared confounder checks without hiding unresolved items."""

    def assess(
        self,
        observations: Iterable[ConfounderObservation | Mapping[str, Any]],
        *,
        context_key: str | None = None,
        required_confounder_ids: Iterable[str] = (),
    ) -> ConfoundingAdjudicationReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        issues: list[CausalAlphaIssue] = []
        parsed: list[ConfounderObservation] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_confounder(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CausalAlphaIssue(
                        "invalid_confounder_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if context_key and item.context_key != context_key:
                mismatch = True
                issues.append(
                    CausalAlphaIssue(
                        "context_mismatch",
                        "confounder observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        groups: dict[str, list[ConfounderObservation]] = defaultdict(list)
        for item in parsed:
            groups[item.confounder_id].append(item)
        required = tuple(
            dict.fromkeys(str(item) for item in required_confounder_ids if str(item).strip())
        )
        all_ids = tuple(sorted(set(groups) | set(required)))
        adjudications: list[ConfounderAdjudication] = []
        for confounder_id in all_ids:
            rows = groups.get(confounder_id, [])
            label = rows[0].label if rows else confounder_id
            if not rows:
                disposition = ConfounderDisposition.MISSING
                reason = "required confounder has no exact-context checklist observation"
                severity = None
            else:
                dispositions = {_confounder_disposition(item) for item in rows}
                if ConfounderDisposition.UNRESOLVED in dispositions:
                    disposition = ConfounderDisposition.UNRESOLVED
                    reason = (
                        "one or more exact-context observations leave the confounder unresolved"
                    )
                elif ConfounderDisposition.ADDRESSED in dispositions:
                    disposition = ConfounderDisposition.ADDRESSED
                    reason = "declared adjustment or measurement addresses the confounder"
                elif ConfounderDisposition.NOT_APPLICABLE in dispositions:
                    disposition = ConfounderDisposition.NOT_APPLICABLE
                    reason = "the source explicitly marked this confounder not applicable"
                else:
                    disposition = ConfounderDisposition.UNRESOLVED
                    reason = "confounder status is unknown or insufficiently adjudicated"
                severity = round(max(item.severity for item in rows), 9)
            adjudications.append(
                ConfounderAdjudication(
                    confounder_id=confounder_id,
                    label=label,
                    disposition=disposition,
                    severity=severity,
                    observation_ids=tuple(sorted(item.observation_id for item in rows)),
                    source_ids=tuple(sorted({item.source_id for item in rows})),
                    adjustment_methods=tuple(
                        sorted({item.adjustment_method for item in rows if item.adjustment_method})
                    ),
                    reason=reason,
                    raw_hashes=tuple(sorted(item.raw_hash for item in rows)),
                    content_address=content_hash(
                        {
                            "confounder_id": confounder_id,
                            "disposition": disposition,
                            "observation_ids": tuple(sorted(item.observation_id for item in rows)),
                            "reason": reason,
                        }
                    ),
                )
            )
        missing = tuple(
            item.confounder_id
            for item in adjudications
            if item.disposition == ConfounderDisposition.MISSING
        )
        unresolved = tuple(
            item.confounder_id
            for item in adjudications
            if item.disposition == ConfounderDisposition.UNRESOLVED
        )
        if not adjudications:
            state = CausalState.OUT_OF_DOMAIN if mismatch else CausalState.ABSTAINED
        elif unresolved or missing or any(issue.severity == "error" for issue in issues):
            state = CausalState.PARTIAL
        elif all(
            item.disposition
            in {ConfounderDisposition.ADDRESSED, ConfounderDisposition.NOT_APPLICABLE}
            for item in adjudications
        ):
            state = CausalState.SUPPORTED
        else:
            state = CausalState.PARTIAL
        return ConfoundingAdjudicationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            adjudications=tuple(adjudications),
            missing_confounder_ids=missing,
            unresolved_confounder_ids=unresolved,
            issues=tuple(issues),
            warnings=(
                "A completed checklist does not prove absence of unmeasured confounding.",
                "Adjustment methods and source versions remain attached for review.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "adjudications": adjudications,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class DependenceObservation:
    """Evidence path annotated with a declared dependence group."""

    evidence_id: str
    edge_id: str
    method_family: str
    dependence_group: str
    support: float
    uncertainty: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    state: CausalState = CausalState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "edge_id",
            "method_family",
            "dependence_group",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1 or not 0 <= self.uncertainty <= 1:
            raise ValidationError("dependence support/uncertainty must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DependenceCorrectionResult:
    """One corrected edge summary with all dependence groups visible."""

    edge_id: str
    context_key: str
    state: CausalState
    correction_method: DependenceMethod
    raw_evidence_count: int
    independent_group_count: int
    dependence_groups: Mapping[str, tuple[str, ...]]
    selected_evidence_ids: tuple[str, ...]
    duplicate_evidence_ids: tuple[str, ...]
    corrected_support: float | None
    uncertainty: float
    source_ids: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DependenceCorrectionReport:
    """Dependence-correction outputs for one or more edges."""

    input_hash: str
    context_key: str
    state: CausalState
    results: tuple[DependenceCorrectionResult, ...]
    issues: tuple[CausalAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EvidenceDependenceCorrector:
    """Collapse repeated paths within declared dependence groups."""

    def correct(
        self,
        observations: Iterable[DependenceObservation | Mapping[str, Any]],
        *,
        context_key: str,
        edge_id: str | None = None,
        correction_method: DependenceMethod = DependenceMethod.DECLARED_GROUP,
        minimum_independent_groups: int = 2,
    ) -> DependenceCorrectionReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if minimum_independent_groups < 1:
            raise ValidationError("minimum_independent_groups must be positive")
        parsed: list[DependenceObservation] = []
        issues: list[CausalAlphaIssue] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_dependence(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CausalAlphaIssue(
                        "invalid_dependence_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if edge_id and item.edge_id != edge_id:
                continue
            if item.context_key != context_key:
                mismatch = True
                issues.append(
                    CausalAlphaIssue(
                        "context_mismatch",
                        "dependence observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        groups: dict[str, list[DependenceObservation]] = defaultdict(list)
        for item in parsed:
            group = _dependence_group(item, correction_method)
            groups[(item.edge_id, group)].append(item)
        results: list[DependenceCorrectionResult] = []
        for row_edge_id, edge_values in _group_by_edge(groups).items():
            by_group: dict[str, list[DependenceObservation]] = defaultdict(list)
            for item in edge_values:
                by_group[_dependence_group(item, correction_method)].append(item)
            selected: list[DependenceObservation] = []
            duplicate_ids: list[str] = []
            group_ids: dict[str, tuple[str, ...]] = {}
            for group, group_values in sorted(by_group.items()):
                group_ids[group] = tuple(sorted(item.evidence_id for item in group_values))
                best = max(
                    group_values,
                    key=lambda item: (item.support * (1 - item.uncertainty), item.evidence_id),
                )
                selected.append(best)
                duplicate_ids.extend(item.evidence_id for item in group_values if item != best)
            contradictory = any(item.state == CausalState.CONTRADICTORY for item in edge_values)
            scores = [item.support * (1 - item.uncertainty) for item in selected]
            corrected = fmean(scores) if scores and not contradictory else None
            if contradictory:
                state = CausalState.CONTRADICTORY
                reason = "contradictory evidence remains after dependence grouping"
            elif not selected:
                state = CausalState.ABSTAINED
                reason = "no exact-context evidence remains after filtering"
            elif len(selected) >= minimum_independent_groups:
                state = CausalState.SUPPORTED
                reason = "one representative path per declared dependence group was retained"
            else:
                state = CausalState.PARTIAL
                reason = "evidence is present but independent dependence groups are insufficient"
            uncertainty = (
                min(
                    1.0,
                    fmean(item.uncertainty for item in selected)
                    + (0.15 if len(selected) < minimum_independent_groups else 0.0),
                )
                if selected
                else 1.0
            )
            results.append(
                DependenceCorrectionResult(
                    edge_id=row_edge_id,
                    context_key=context_key,
                    state=state,
                    correction_method=correction_method,
                    raw_evidence_count=len(edge_values),
                    independent_group_count=len(selected),
                    dependence_groups=group_ids,
                    selected_evidence_ids=tuple(sorted(item.evidence_id for item in selected)),
                    duplicate_evidence_ids=tuple(sorted(duplicate_ids)),
                    corrected_support=None if corrected is None else round(corrected, 9),
                    uncertainty=round(uncertainty, 9),
                    source_ids=tuple(sorted({item.source_id for item in edge_values})),
                    reason=reason,
                    limitations=(
                        "Dependence groups are declared evidence metadata and require validation.",
                        "The corrected support is a dependence-adjusted proxy, not a posterior "
                        "or causal effect.",
                    ),
                    content_address=content_hash(
                        {
                            "edge_id": row_edge_id,
                            "context_key": context_key,
                            "state": state,
                            "groups": group_ids,
                            "selected": tuple(sorted(item.evidence_id for item in selected)),
                            "corrected": corrected,
                        }
                    ),
                )
            )
        if results:
            states = {item.state for item in results}
            if CausalState.CONTRADICTORY in states:
                state = CausalState.CONTRADICTORY
            elif CausalState.PARTIAL in states:
                state = CausalState.PARTIAL
            elif all(item.state == CausalState.SUPPORTED for item in results):
                state = CausalState.SUPPORTED
            else:
                state = CausalState.ABSTAINED
        else:
            state = CausalState.OUT_OF_DOMAIN if mismatch else CausalState.ABSTAINED
        return DependenceCorrectionReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Dependence correction relies on declared grouping and retains excluded paths "
                "for review.",
                "Independent source count is not a guarantee of causal identification.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class NegativeEvidenceObservation:
    """Positive path, negative control, or measured-negative observation."""

    evidence_id: str
    edge_id: str
    polarity: NegativeEvidencePolarity
    strength: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    negative_control: bool = False
    assay_label: str = "unspecified"
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "edge_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
            "assay_label",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.strength <= 1:
            raise ValidationError("negative evidence strength must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NegativeEvidenceIntegrationResult:
    """Integrated positive/negative evidence for one causal edge."""

    edge_id: str
    context_key: str
    state: CausalState
    positive_evidence_ids: tuple[str, ...]
    negative_evidence_ids: tuple[str, ...]
    negative_control_ids: tuple[str, ...]
    positive_strength: float | None
    negative_strength: float | None
    negative_coverage: float | None
    integrated_support_proxy: float | None
    source_ids: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NegativeEvidenceIntegrationReport:
    """Negative-evidence outputs for one or more edges."""

    input_hash: str
    context_key: str
    state: CausalState
    results: tuple[NegativeEvidenceIntegrationResult, ...]
    issues: tuple[CausalAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class NegativeEvidenceIntegrator:
    """Integrate negative controls without treating them as absent data."""

    def integrate(
        self,
        observations: Iterable[NegativeEvidenceObservation | Mapping[str, Any]],
        *,
        context_key: str,
        edge_id: str | None = None,
        minimum_negative_controls: int = 1,
    ) -> NegativeEvidenceIntegrationReport:
        values = tuple(observations)
        input_hash = content_hash(values)
        if minimum_negative_controls < 0:
            raise ValidationError("minimum_negative_controls cannot be negative")
        parsed: list[NegativeEvidenceObservation] = []
        issues: list[CausalAlphaIssue] = []
        mismatch = False
        for row_number, value in enumerate(values, start=1):
            try:
                item = _coerce_negative(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CausalAlphaIssue(
                        "invalid_negative_evidence_row",
                        str(exc),
                        content_hash(value),
                        row_number=row_number,
                        severity="error",
                    )
                )
                continue
            if edge_id and item.edge_id != edge_id:
                continue
            if item.context_key != context_key:
                mismatch = True
                issues.append(
                    CausalAlphaIssue(
                        "context_mismatch",
                        "negative-evidence observation is outside the requested context",
                        item.raw_hash,
                        row_number=row_number,
                        source_id=item.source_id,
                        severity="warning",
                    )
                )
                continue
            parsed.append(item)
        grouped: dict[str, list[NegativeEvidenceObservation]] = defaultdict(list)
        for item in parsed:
            grouped[item.edge_id].append(item)
        results: list[NegativeEvidenceIntegrationResult] = []
        for row_edge_id, edge_values in sorted(grouped.items()):
            positives = tuple(
                item for item in edge_values if item.polarity == NegativeEvidencePolarity.POSITIVE
            )
            negatives = tuple(
                item
                for item in edge_values
                if item.polarity
                in {NegativeEvidencePolarity.NEGATIVE, NegativeEvidencePolarity.NEGATIVE_CONTROL}
                or item.negative_control
            )
            controls = tuple(
                item
                for item in negatives
                if item.negative_control
                or item.polarity == NegativeEvidencePolarity.NEGATIVE_CONTROL
            )
            positive_strength = fmean(item.strength for item in positives) if positives else None
            negative_strength = fmean(item.strength for item in negatives) if negatives else None
            coverage = (
                min(1.0, len(controls) / minimum_negative_controls)
                if minimum_negative_controls
                else 1.0
            )
            if positives and negatives:
                state = CausalState.CONTRADICTORY
                integrated = None
                reason = "positive and negative or control paths coexist for the same edge"
            elif negatives:
                state = CausalState.MEASURED_NEGATIVE
                integrated = None
                reason = (
                    "negative evidence is retained as measured-negative, not converted to "
                    "absent evidence"
                )
            elif positives:
                state = CausalState.PARTIAL
                integrated = positive_strength
                reason = "positive evidence is present but no negative-control path was supplied"
            else:
                state = CausalState.ABSTAINED
                integrated = None
                reason = "no positive or negative path was available"
            results.append(
                NegativeEvidenceIntegrationResult(
                    edge_id=row_edge_id,
                    context_key=context_key,
                    state=state,
                    positive_evidence_ids=tuple(sorted(item.evidence_id for item in positives)),
                    negative_evidence_ids=tuple(sorted(item.evidence_id for item in negatives)),
                    negative_control_ids=tuple(sorted(item.evidence_id for item in controls)),
                    positive_strength=None
                    if positive_strength is None
                    else round(positive_strength, 9),
                    negative_strength=None
                    if negative_strength is None
                    else round(negative_strength, 9),
                    negative_coverage=round(coverage, 9),
                    integrated_support_proxy=None if integrated is None else round(integrated, 9),
                    source_ids=tuple(sorted({item.source_id for item in edge_values})),
                    reason=reason,
                    limitations=(
                        "Negative controls and measured-negative paths do not prove absence of "
                        "a mechanism.",
                        "Control design, sensitivity, sampling, and assay power require "
                        "external review.",
                    ),
                    content_address=content_hash(
                        {
                            "edge_id": row_edge_id,
                            "context_key": context_key,
                            "state": state,
                            "positive": tuple(sorted(item.evidence_id for item in positives)),
                            "negative": tuple(sorted(item.evidence_id for item in negatives)),
                            "coverage": coverage,
                        }
                    ),
                )
            )
        if results:
            states = {item.state for item in results}
            state = (
                CausalState.CONTRADICTORY
                if CausalState.CONTRADICTORY in states
                else CausalState.MEASURED_NEGATIVE
                if all(item == CausalState.MEASURED_NEGATIVE for item in states)
                else CausalState.PARTIAL
            )
        else:
            state = CausalState.OUT_OF_DOMAIN if mismatch else CausalState.ABSTAINED
        return NegativeEvidenceIntegrationReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=tuple(results),
            issues=tuple(issues),
            warnings=(
                "Negative evidence is an assay-bound observation, not proof of no causal path.",
                "Contradictory positive and negative paths remain visible for adjudication.",
            ),
            content_address=content_hash(
                {
                    "input_hash": input_hash,
                    "context_key": context_key,
                    "state": state,
                    "results": results,
                }
            ),
        )


def _mediator_engine(kind: MediatorKind) -> Any:
    try:
        return {
            MediatorKind.SEQUENCE_TO_ELEMENT: SequenceToElementCausalMediator(),
            MediatorKind.ELEMENT_TO_GENE: ElementToGeneCausalMediator(),
            MediatorKind.GENE_TO_STATE: GeneToStateCausalMediator(),
        }[kind]
    except KeyError as exc:
        raise ValidationError(f"unsupported mediator kind: {kind}") from exc


def _coerce_mediator(value: CausalMediatorEvidence | Mapping[str, Any]) -> CausalMediatorEvidence:
    if isinstance(value, CausalMediatorEvidence):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("causal alpha mediator evidence must be a mapping")
    return CausalMediatorEvidence(
        evidence_id=str(value.get("evidence_id", value.get("id", "causal-alpha-input"))),
        mediator_kind=MediatorKind(
            str(value.get("mediator_kind", value.get("kind", "sequence_to_element")))
        ),
        source_node=str(value.get("source_node", value.get("source", ""))),
        target_node=str(value.get("target_node", value.get("target", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        support=float(value.get("support", value.get("score", 0.0))),
        uncertainty=float(value.get("uncertainty", 1.0)),
        source_id=str(value.get("source_id", "causal-alpha-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        direction=CausalEvidenceDirection(
            str(value.get("direction", CausalEvidenceDirection.SUPPORTS.value))
        ),
        sensitivity=_optional_float(value, "sensitivity"),
        negative_control=bool(value.get("negative_control", False)),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_confounder(value: ConfounderObservation | Mapping[str, Any]) -> ConfounderObservation:
    if isinstance(value, ConfounderObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("confounder observation must be a mapping")
    addressed = value.get("addressed")
    if addressed is not None:
        addressed = bool(addressed)
    return ConfounderObservation(
        observation_id=str(value.get("observation_id", value.get("id", "confounder-input"))),
        confounder_id=str(value.get("confounder_id", value.get("id", ""))),
        label=str(value.get("label", value.get("name", value.get("confounder_id", "")))),
        status=str(value.get("status", "unknown")),
        severity=float(value.get("severity", 1.0)),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "confounder-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        addressed=addressed,
        adjustment_method=_optional_text(value, "adjustment_method", "method"),
        notes=str(value.get("notes", "")),
        attributes=dict(value.get("attributes", {})),
    )


def _confounder_disposition(item: ConfounderObservation) -> ConfounderDisposition:
    if item.addressed is True:
        return ConfounderDisposition.ADDRESSED
    if item.addressed is False:
        return ConfounderDisposition.UNRESOLVED
    normalized = item.status.strip().lower().replace("-", "_")
    if normalized in {"addressed", "adjusted", "controlled", "measured", "resolved"}:
        return ConfounderDisposition.ADDRESSED
    if normalized in {"not_applicable", "na", "n_a"}:
        return ConfounderDisposition.NOT_APPLICABLE
    return ConfounderDisposition.UNRESOLVED


def _coerce_dependence(value: DependenceObservation | Mapping[str, Any]) -> DependenceObservation:
    if isinstance(value, DependenceObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("dependence observation must be a mapping")
    return DependenceObservation(
        evidence_id=str(value.get("evidence_id", value.get("id", "dependence-input"))),
        edge_id=str(value.get("edge_id", value.get("edge", ""))),
        method_family=str(value.get("method_family", value.get("method", "unspecified"))),
        dependence_group=str(value.get("dependence_group", value.get("group", ""))),
        support=float(value.get("support", value.get("score", 0.0))),
        uncertainty=float(value.get("uncertainty", 1.0)),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "dependence-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        state=CausalState(str(value.get("state", CausalState.SUPPORTED.value))),
        attributes=dict(value.get("attributes", {})),
    )


def _dependence_group(item: DependenceObservation, method: DependenceMethod) -> str:
    if method == DependenceMethod.SOURCE:
        return f"source:{item.source_id}"
    if method == DependenceMethod.METHOD_FAMILY:
        return f"method:{item.method_family}"
    return item.dependence_group


def _group_by_edge(
    groups: Mapping[tuple[str, str], list[DependenceObservation]],
) -> dict[str, list[DependenceObservation]]:
    result: dict[str, list[DependenceObservation]] = defaultdict(list)
    for (edge_id, _group), values in groups.items():
        result[edge_id].extend(values)
    return result


def _coerce_negative(
    value: NegativeEvidenceObservation | Mapping[str, Any],
) -> NegativeEvidenceObservation:
    if isinstance(value, NegativeEvidenceObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("negative evidence observation must be a mapping")
    try:
        polarity = NegativeEvidencePolarity(
            str(
                value.get(
                    "polarity", value.get("direction", NegativeEvidencePolarity.UNKNOWN.value)
                )
            )
        )
    except ValueError as exc:
        raise ValidationError(
            f"unsupported negative-evidence polarity: {value.get('polarity')}"
        ) from exc
    return NegativeEvidenceObservation(
        evidence_id=str(value.get("evidence_id", value.get("id", "negative-input"))),
        edge_id=str(value.get("edge_id", value.get("edge", ""))),
        polarity=polarity,
        strength=float(value.get("strength", value.get("support", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "negative-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        negative_control=bool(value.get("negative_control", False)),
        assay_label=str(value.get("assay_label", value.get("assay", "unspecified"))),
        attributes=dict(value.get("attributes", {})),
    )


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    value = _optional_text(row, *names)
    return None if value is None else float(value)


__all__ = [
    "CausalAlphaIssue",
    "ConfounderAdjudication",
    "ConfounderDisposition",
    "ConfounderObservation",
    "ConfoundingChecklistAdjudicator",
    "ConfoundingAdjudicationReport",
    "DependenceCorrectionReport",
    "DependenceCorrectionResult",
    "DependenceMethod",
    "DependenceObservation",
    "EvidenceDependenceCorrector",
    "MediationLeaveOneOut",
    "MediationSensitivityAnalyzer",
    "MediationSensitivityReport",
    "MediationSensitivityResult",
    "NegativeEvidenceIntegrationReport",
    "NegativeEvidenceIntegrationResult",
    "NegativeEvidenceIntegrator",
    "NegativeEvidenceObservation",
    "NegativeEvidencePolarity",
]
