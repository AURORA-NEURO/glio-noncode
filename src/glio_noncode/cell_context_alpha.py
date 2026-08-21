"""Deep context-prior contracts for Domain 08.

These adapters keep spatial niche, core/margin territory, recurrence phase,
and treatment-induced state evidence separate. Each is a bounded descriptive
prior over declared observations. Exact context, subject identity, source
receipts, candidate alternatives, and disagreement remain attached; no prior
is a diagnosis, prognosis, treatment recommendation, or cell-state truth.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class CellContextAlphaState(StrEnum):
    """Evidence state shared by context-alpha priors."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class CellContextAlphaIssue:
    """Row-addressable context-prior issue."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpatialNichePriorResult:
    """One spatial niche candidate ranked within a subject/context."""

    subject_id: str
    context_key: str
    niche_id: str
    median_support: float | None
    minimum_support: float | None
    maximum_support: float | None
    support_spread: float | None
    rank: int
    score_margin_to_next: float | None
    observation_count: int
    sample_ids: tuple[str, ...]
    state: CellContextAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpatialNichePriorReport:
    """Spatial niche candidates and issues."""

    input_hash: str
    context_key: str | None
    state: CellContextAlphaState
    results: tuple[SpatialNichePriorResult, ...]
    issues: tuple[CellContextAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SpatialNichePrior:
    """Rank declared spatial niche observations without collapsing candidates."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        ambiguity_margin: float = 0.1,
    ) -> SpatialNichePriorReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[CellContextAlphaIssue] = []
        parsed: list[dict[str, Any]] = []
        context_mismatch = False
        if ambiguity_margin < 0:
            issue = CellContextAlphaIssue(
                "invalid_spatial_parameter",
                "ambiguity margin must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, CellContextAlphaState.INVALID, (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            item = _parse_common(row, row_number, context_key, "spatial_niche", issues)
            if item is None:
                if (
                    isinstance(row, Mapping)
                    and _context(row)
                    and context_key
                    and _context(row) != context_key
                ):
                    context_mismatch = True
                continue
            try:
                item["niche_id"] = str(_value(row, "niche_id", "niche", "candidate_id"))
                item["support"] = float(_value(row, "support", "score", "confidence"))
                item["sample_id"] = str(_value(row, "sample_id", "sample", default="unspecified"))
                if item["support"] < 0 or item["support"] > 1:
                    raise ValidationError("spatial niche support must be between zero and one")
                parsed.append(item)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_spatial_niche_row", str(exc)))
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in parsed:
            groups[(item["subject_id"], item["context_key"], item["niche_id"])].append(item)
        by_subject: dict[
            tuple[str, str], list[tuple[str, float, float | None, list[dict[str, Any]]]]
        ] = defaultdict(list)
        for (subject_id, row_context, niche_id), group in groups.items():
            supports = [item["support"] for item in group]
            by_subject[(subject_id, row_context)].append(
                (
                    niche_id,
                    float(median(supports)),
                    max(supports) - min(supports) if len(supports) > 1 else 0.0,
                    group,
                )
            )
        results: list[SpatialNichePriorResult] = []
        for (subject_id, row_context), candidates in by_subject.items():
            ranked = sorted(candidates, key=lambda item: (-item[1], item[0]))
            for index, (niche_id, score, spread, group) in enumerate(ranked, start=1):
                next_score = ranked[index][1] if index < len(ranked) else None
                margin = None if next_score is None else round(score - next_score, 9)
                state = (
                    CellContextAlphaState.AMBIGUOUS
                    if margin is not None and margin <= ambiguity_margin
                    else CellContextAlphaState.PARTIAL
                    if len(group) < 2
                    else CellContextAlphaState.SUPPORTED
                )
                body = {
                    "subject_id": subject_id,
                    "context_key": row_context,
                    "niche_id": niche_id,
                    "rank": index,
                    "score": score,
                }
                results.append(
                    SpatialNichePriorResult(
                        subject_id=subject_id,
                        context_key=row_context,
                        niche_id=niche_id,
                        median_support=round(score, 9),
                        minimum_support=round(min(item["support"] for item in group), 9),
                        maximum_support=round(max(item["support"] for item in group), 9),
                        support_spread=round(spread, 9),
                        rank=index,
                        score_margin_to_next=margin,
                        observation_count=len(group),
                        sample_ids=tuple(sorted({item["sample_id"] for item in group})),
                        state=state,
                        source_ids=tuple(sorted({item["source_id"] for item in group})),
                        raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
                        content_address=content_hash(body | {"state": state}),
                    )
                )
        state = _aggregate_state(results, issues, context_mismatch)
        return self._report(input_hash, context_key, state, tuple(results), tuple(issues))

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: CellContextAlphaState,
        results: tuple[SpatialNichePriorResult, ...],
        issues: tuple[CellContextAlphaIssue, ...],
    ) -> SpatialNichePriorReport:
        return SpatialNichePriorReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=results,
            issues=issues,
            warnings=(
                "Spatial niche rankings are descriptive context priors, not cell-state truth.",
                "Close candidates remain ambiguous rather than being silently selected.",
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class CoreMarginTerritoryResult:
    """Core-versus-margin territory evidence for one subject/context."""

    subject_id: str
    context_key: str
    core_score: float | None
    margin_score: float | None
    core_margin_delta: float | None
    territory_label: str
    state: CellContextAlphaState
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CoreMarginTerritoryReport:
    """Core/margin territory results and issues."""

    input_hash: str
    context_key: str | None
    state: CellContextAlphaState
    results: tuple[CoreMarginTerritoryResult, ...]
    issues: tuple[CellContextAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CoreMarginTerritoryPrior:
    """Resolve declared core/margin scores without inventing territory labels."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        ambiguity_tolerance: float = 0.1,
    ) -> CoreMarginTerritoryReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[CellContextAlphaIssue] = []
        parsed: list[dict[str, Any]] = []
        context_mismatch = False
        if ambiguity_tolerance < 0:
            issue = CellContextAlphaIssue(
                "invalid_core_margin_parameter",
                "ambiguity tolerance must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, CellContextAlphaState.INVALID, (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            item = _parse_common(row, row_number, context_key, "core_margin", issues)
            if item is None:
                if (
                    isinstance(row, Mapping)
                    and _context(row)
                    and context_key
                    and _context(row) != context_key
                ):
                    context_mismatch = True
                continue
            try:
                item["core"] = _optional_float(_value(row, "core_score", "core", default=None))
                item["margin"] = _optional_float(
                    _value(row, "margin_score", "margin", default=None)
                )
                item["observation_id"] = str(
                    _value(row, "observation_id", "id", default=f"row-{row_number}")
                )
                if item["core"] is None and item["margin"] is None:
                    raise ValidationError("core or margin score is required")
                if any(
                    value is not None and not 0 <= value <= 1
                    for value in (item["core"], item["margin"])
                ):
                    raise ValidationError("core and margin scores must be between zero and one")
                parsed.append(item)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_core_margin_row", str(exc)))
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in parsed:
            groups[(item["subject_id"], item["context_key"])].append(item)
        results: list[CoreMarginTerritoryResult] = []
        for (subject_id, row_context), group in sorted(groups.items()):
            core_values = [item["core"] for item in group if item["core"] is not None]
            margin_values = [item["margin"] for item in group if item["margin"] is not None]
            core_score = float(median(core_values)) if core_values else None
            margin_score = float(median(margin_values)) if margin_values else None
            delta = (
                None if core_score is None or margin_score is None else core_score - margin_score
            )
            label = (
                "unknown"
                if delta is None
                else "core"
                if delta > ambiguity_tolerance
                else "margin"
                if delta < -ambiguity_tolerance
                else "mixed"
            )
            state = (
                CellContextAlphaState.PARTIAL
                if delta is None
                else CellContextAlphaState.AMBIGUOUS
                if abs(delta) <= ambiguity_tolerance
                else CellContextAlphaState.SUPPORTED
            )
            body = {
                "subject_id": subject_id,
                "context_key": row_context,
                "core": core_score,
                "margin": margin_score,
            }
            results.append(
                CoreMarginTerritoryResult(
                    subject_id=subject_id,
                    context_key=row_context,
                    core_score=None if core_score is None else round(core_score, 9),
                    margin_score=None if margin_score is None else round(margin_score, 9),
                    core_margin_delta=None if delta is None else round(delta, 9),
                    territory_label=label,
                    state=state,
                    observation_ids=tuple(sorted(item["observation_id"] for item in group)),
                    source_ids=tuple(sorted({item["source_id"] for item in group})),
                    raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return self._report(
            input_hash,
            context_key,
            _aggregate_state(results, issues, context_mismatch),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: CellContextAlphaState,
        results: tuple[CoreMarginTerritoryResult, ...],
        issues: tuple[CellContextAlphaIssue, ...],
    ) -> CoreMarginTerritoryReport:
        return CoreMarginTerritoryReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=results,
            issues=issues,
            warnings=(
                (
                    "Core/margin labels summarize declared territory scores and are not invasive "
                    "localization claims."
                ),
                "Missing one-sided scores remain partial rather than being imputed.",
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class RecurrenceStatePriorResult:
    """One recurrence-phase candidate for a subject/context."""

    subject_id: str
    context_key: str
    phase: str
    median_support: float | None
    support_spread: float | None
    rank: int
    phase_margin_to_next: float | None
    observation_count: int
    state: CellContextAlphaState
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RecurrenceStatePriorReport:
    """Recurrence-state candidates and issues."""

    input_hash: str
    context_key: str | None
    state: CellContextAlphaState
    results: tuple[RecurrenceStatePriorResult, ...]
    issues: tuple[CellContextAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RecurrenceStatePrior:
    """Rank declared primary/recurrence/progression phase observations."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        ambiguity_margin: float = 0.1,
    ) -> RecurrenceStatePriorReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[CellContextAlphaIssue] = []
        parsed: list[dict[str, Any]] = []
        context_mismatch = False
        for row_number, row in enumerate(values, start=1):
            item = _parse_common(row, row_number, context_key, "recurrence", issues)
            if item is None:
                if (
                    isinstance(row, Mapping)
                    and _context(row)
                    and context_key
                    and _context(row) != context_key
                ):
                    context_mismatch = True
                continue
            try:
                item["phase"] = str(_value(row, "phase", "recurrence_state", "state"))
                item["support"] = float(_value(row, "support", "score", "confidence"))
                if not 0 <= item["support"] <= 1:
                    raise ValidationError("recurrence support must be between zero and one")
                parsed.append(item)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_recurrence_row", str(exc)))
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in parsed:
            groups[(item["subject_id"], item["context_key"], item["phase"])].append(item)
        by_subject: dict[tuple[str, str], list[tuple[str, float, float, list[dict[str, Any]]]]] = (
            defaultdict(list)
        )
        for (subject_id, row_context, phase), group in groups.items():
            scores = [item["support"] for item in group]
            by_subject[(subject_id, row_context)].append(
                (
                    phase,
                    float(median(scores)),
                    max(scores) - min(scores) if len(scores) > 1 else 0.0,
                    group,
                )
            )
        results: list[RecurrenceStatePriorResult] = []
        for (subject_id, row_context), candidates in by_subject.items():
            ranked = sorted(candidates, key=lambda item: (-item[1], item[0]))
            for index, (phase, score, spread, group) in enumerate(ranked, start=1):
                next_score = ranked[index][1] if index < len(ranked) else None
                margin = None if next_score is None else round(score - next_score, 9)
                state = (
                    CellContextAlphaState.AMBIGUOUS
                    if margin is not None and margin <= ambiguity_margin
                    else CellContextAlphaState.PARTIAL
                    if len(group) < 2
                    else CellContextAlphaState.SUPPORTED
                )
                body = {
                    "subject_id": subject_id,
                    "context_key": row_context,
                    "phase": phase,
                    "rank": index,
                    "score": score,
                }
                results.append(
                    RecurrenceStatePriorResult(
                        subject_id=subject_id,
                        context_key=row_context,
                        phase=phase,
                        median_support=round(score, 9),
                        support_spread=round(spread, 9),
                        rank=index,
                        phase_margin_to_next=margin,
                        observation_count=len(group),
                        state=state,
                        source_ids=tuple(sorted({item["source_id"] for item in group})),
                        raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
                        content_address=content_hash(body | {"state": state}),
                    )
                )
        return self._report(
            input_hash,
            context_key,
            _aggregate_state(results, issues, context_mismatch),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: CellContextAlphaState,
        results: tuple[RecurrenceStatePriorResult, ...],
        issues: tuple[CellContextAlphaIssue, ...],
    ) -> RecurrenceStatePriorReport:
        return RecurrenceStatePriorReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=results,
            issues=issues,
            warnings=(
                (
                    "Recurrence phase rankings preserve primary, recurrence, and progression "
                    "alternatives."
                ),
                "A recurrence prior is not a prognosis or treatment-response claim.",
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


@dataclass(frozen=True, slots=True)
class TreatmentInducedStateResult:
    """Pre/post-treatment state evidence for one subject and treatment."""

    subject_id: str
    context_key: str
    treatment_id: str
    state_id: str
    baseline_support: float | None
    post_treatment_support: float | None
    support_delta: float | None
    induction_label: str
    treatment_phase: str
    state: CellContextAlphaState
    observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    raw_hashes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TreatmentInducedStatePriorReport:
    """Treatment-induced state results and issues."""

    input_hash: str
    context_key: str | None
    state: CellContextAlphaState
    results: tuple[TreatmentInducedStateResult, ...]
    issues: tuple[CellContextAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TreatmentInducedStatePrior:
    """Compare declared baseline and post-treatment state support."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str | None = None,
        induction_threshold: float = 0.1,
    ) -> TreatmentInducedStatePriorReport:
        values = tuple(records)
        input_hash = content_hash(values)
        issues: list[CellContextAlphaIssue] = []
        parsed: list[dict[str, Any]] = []
        context_mismatch = False
        if induction_threshold < 0:
            issue = CellContextAlphaIssue(
                "invalid_treatment_parameter",
                "induction threshold must be non-negative",
                input_hash,
                severity="error",
            )
            return self._report(
                input_hash, context_key, CellContextAlphaState.INVALID, (), (issue,)
            )
        for row_number, row in enumerate(values, start=1):
            item = _parse_common(row, row_number, context_key, "treatment", issues)
            if item is None:
                if (
                    isinstance(row, Mapping)
                    and _context(row)
                    and context_key
                    and _context(row) != context_key
                ):
                    context_mismatch = True
                continue
            try:
                item["treatment_id"] = str(_value(row, "treatment_id", "treatment", "exposure_id"))
                item["state_id"] = str(_value(row, "state_id", "state", "candidate_id"))
                item["baseline"] = _optional_score(
                    _value(row, "baseline_support", "baseline", default=None)
                )
                item["post"] = _optional_score(
                    _value(row, "post_treatment_support", "post_support", "post", default=None)
                )
                item["phase"] = str(_value(row, "treatment_phase", "phase", default="unspecified"))
                if item["baseline"] is None or item["post"] is None:
                    raise ValidationError("baseline and post-treatment support are required")
                parsed.append(item)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(_issue(row, row_number, "invalid_treatment_induced_row", str(exc)))
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for item in parsed:
            groups[
                (item["subject_id"], item["context_key"], item["treatment_id"], item["state_id"])
            ].append(item)
        results: list[TreatmentInducedStateResult] = []
        for key, group in sorted(groups.items()):
            baseline = float(median([item["baseline"] for item in group]))
            post = float(median([item["post"] for item in group]))
            delta = post - baseline
            label = (
                "induced"
                if delta > induction_threshold
                else "reduced"
                if delta < -induction_threshold
                else "stable"
            )
            state = (
                CellContextAlphaState.SUPPORTED
                if len(group) >= 1
                else CellContextAlphaState.PARTIAL
            )
            body = {
                "subject_id": key[0],
                "context_key": key[1],
                "treatment_id": key[2],
                "state_id": key[3],
                "delta": delta,
            }
            results.append(
                TreatmentInducedStateResult(
                    subject_id=key[0],
                    context_key=key[1],
                    treatment_id=key[2],
                    state_id=key[3],
                    baseline_support=round(baseline, 9),
                    post_treatment_support=round(post, 9),
                    support_delta=round(delta, 9),
                    induction_label=label,
                    treatment_phase=group[0]["phase"],
                    state=state,
                    observation_ids=tuple(sorted(item["observation_id"] for item in group)),
                    source_ids=tuple(sorted({item["source_id"] for item in group})),
                    raw_hashes=tuple(sorted(item["raw_hash"] for item in group)),
                    content_address=content_hash(body | {"state": state}),
                )
            )
        return self._report(
            input_hash,
            context_key,
            _aggregate_state(results, issues, context_mismatch),
            tuple(results),
            tuple(issues),
        )

    @staticmethod
    def _report(
        input_hash: str,
        context_key: str | None,
        state: CellContextAlphaState,
        results: tuple[TreatmentInducedStateResult, ...],
        issues: tuple[CellContextAlphaIssue, ...],
    ) -> TreatmentInducedStatePriorReport:
        return TreatmentInducedStatePriorReport(
            input_hash=input_hash,
            context_key=context_key,
            state=state,
            results=results,
            issues=issues,
            warnings=(
                (
                    "Treatment-induced labels describe pre/post support changes and do not "
                    "establish resistance or response."
                ),
                (
                    "Treatment exposures and state candidates remain context-qualified and "
                    "source-accounted."
                ),
            ),
            content_address=content_hash(
                {"input_hash": input_hash, "state": state, "results": results, "issues": issues}
            ),
        )


def _parse_common(
    row: Any,
    row_number: int,
    context_key: str | None,
    domain: str,
    issues: list[CellContextAlphaIssue],
) -> dict[str, Any] | None:
    if not isinstance(row, Mapping):
        issues.append(
            CellContextAlphaIssue(
                "row_not_object",
                f"{domain} row must be an object",
                content_hash({"row": row}),
                row_number,
                severity="error",
            )
        )
        return None
    row_context = _context(row)
    if context_key and row_context and row_context != context_key:
        issues.append(
            _issue(
                row,
                row_number,
                "context_mismatch",
                f"{domain} row is outside the requested context",
            )
        )
        return None
    try:
        return {
            "subject_id": str(
                _value(row, "subject_id", "subject", "case_id", default="unspecified")
            ),
            "context_key": row_context or context_key or "unspecified",
            "observation_id": str(_value(row, "observation_id", "id", default=f"row-{row_number}")),
            "source_id": _source_id(row),
            "source_version": _source_version(row),
            "raw_hash": _raw_hash(row),
        }
    except (TypeError, ValueError, ValidationError) as exc:
        issues.append(_issue(row, row_number, f"invalid_{domain}_row", str(exc)))
        return None


def _aggregate_state(
    results: Sequence[Any], issues: Sequence[CellContextAlphaIssue], context_mismatch: bool
) -> CellContextAlphaState:
    if context_mismatch and not results:
        return CellContextAlphaState.OUT_OF_DOMAIN
    if any(item.state == CellContextAlphaState.AMBIGUOUS for item in results):
        return CellContextAlphaState.AMBIGUOUS
    if issues or any(item.state == CellContextAlphaState.PARTIAL for item in results):
        return CellContextAlphaState.PARTIAL
    if not results:
        return CellContextAlphaState.ABSTAINED
    return CellContextAlphaState.SUPPORTED


def _issue(
    row: Mapping[str, Any], row_number: int, code: str, message: str
) -> CellContextAlphaIssue:
    return CellContextAlphaIssue(
        code,
        message,
        _raw_hash(row),
        row_number,
        source_id=_source_id(row),
        severity="error",
        raw_record=dict(row),
    )


_MISSING = object()


def _value(row: Mapping[str, Any], *keys: str, default: Any = _MISSING) -> Any:
    for key in keys:
        if key not in row:
            continue
        value = row[key]
        if value is not None and value != "":
            return value
    if default is not _MISSING:
        return default
    raise ValidationError(f"missing required field; expected one of {keys}")


def _optional_float(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and value in {"", "."}):
        return None
    return float(value)


def _optional_score(value: Any) -> float | None:
    parsed = _optional_float(value)
    if parsed is None:
        return None
    if not 0 <= parsed <= 1:
        raise ValidationError("support score must be between zero and one")
    return parsed


def _context(row: Mapping[str, Any]) -> str | None:
    value = row.get("context_key", row.get("context"))
    return str(value) if value not in {None, "", "."} else None


def _source_id(row: Mapping[str, Any]) -> str:
    return str(row.get("source_id", row.get("source", "unspecified"))) or "unspecified"


def _source_version(row: Mapping[str, Any]) -> str:
    return str(row.get("source_version", row.get("version", "unspecified"))) or "unspecified"


def _raw_hash(row: Mapping[str, Any]) -> str:
    return content_hash(dict(row))


__all__ = [
    "CellContextAlphaIssue",
    "CellContextAlphaState",
    "CoreMarginTerritoryPrior",
    "CoreMarginTerritoryReport",
    "CoreMarginTerritoryResult",
    "RecurrenceStatePrior",
    "RecurrenceStatePriorReport",
    "RecurrenceStatePriorResult",
    "SpatialNichePrior",
    "SpatialNichePriorReport",
    "SpatialNichePriorResult",
    "TreatmentInducedStatePrior",
    "TreatmentInducedStatePriorReport",
    "TreatmentInducedStateResult",
]
