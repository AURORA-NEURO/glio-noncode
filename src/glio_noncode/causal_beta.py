"""Scientific-beta causal mediator and counterfactual contracts.

The causal beta layer decomposes a regulatory-driver hypothesis into typed
sequence-to-element, element-to-gene, and gene-to-state mediator evidence. It
retains negative evidence and source disagreement, and its allele-state
simulator reports measured reference/alternate deltas rather than asserting a
causal effect or clinical interpretation.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean, median
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


class CausalBetaState(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"


class MediatorKind(StrEnum):
    SEQUENCE_TO_ELEMENT = "sequence_to_element"
    ELEMENT_TO_GENE = "element_to_gene"
    GENE_TO_STATE = "gene_to_state"


class CausalEvidenceDirection(StrEnum):
    SUPPORTS = "supports"
    AGAINST = "against"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class CausalBetaIssue:
    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "causal beta issue code")
        require_non_empty(self.message, "causal beta issue message")
        require_non_empty(self.raw_hash, "causal beta issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("causal beta issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalMediatorEvidence:
    """One directional mediator evidence path."""

    evidence_id: str
    mediator_kind: MediatorKind
    source_node: str
    target_node: str
    context_key: str
    support: float
    uncertainty: float
    source_id: str
    source_version: str
    raw_hash: str
    direction: CausalEvidenceDirection = CausalEvidenceDirection.SUPPORTS
    sensitivity: float | None = None
    negative_control: bool = False
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "source_node",
            "target_node",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1 or not 0 <= self.uncertainty <= 1:
            raise ValidationError(
                "causal mediator support/uncertainty must be between zero and one"
            )
        if self.sensitivity is not None and not 0 <= self.sensitivity <= 1:
            raise ValidationError("causal mediator sensitivity must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalMediatorBatch:
    source_id: str
    input_hash: str
    evidence: tuple[CausalMediatorEvidence, ...]
    issues: tuple[CausalBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CausalMediatorEvidenceParser:
    """Parse generic mediator evidence with row-level quarantine."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> CausalMediatorBatch:
        rows, json_mode = _rows(text, input_format, "evidence")
        evidence: list[CausalMediatorEvidence] = []
        issues: list[CausalBetaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    CausalBetaIssue(
                        "invalid_causal_evidence_row",
                        "row must be an object",
                        content_hash(row),
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            raw_hash = content_hash(row)
            try:
                evidence.append(
                    CausalMediatorEvidence(
                        evidence_id=str(
                            _value(row, "evidence_id", "id", default=f"{source_id}:{index}")
                        ),
                        mediator_kind=MediatorKind(str(_value(row, "mediator_kind", "kind"))),
                        source_node=str(_value(row, "source_node", "source")),
                        target_node=str(_value(row, "target_node", "target")),
                        context_key=str(_value(row, "context_key", "context")),
                        support=float(_value(row, "support", "score")),
                        uncertainty=float(_value(row, "uncertainty", default=1.0)),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        direction=CausalEvidenceDirection(
                            str(
                                _value(
                                    row, "direction", default=CausalEvidenceDirection.SUPPORTS.value
                                )
                            )
                        ),
                        sensitivity=_optional_float(row, "sensitivity"),
                        negative_control=bool(row.get("negative_control", False)),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    CausalBetaIssue(
                        "invalid_causal_evidence_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return CausalMediatorBatch(
            source_id=source_id,
            input_hash=input_hash,
            evidence=tuple(evidence),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "evidence": evidence,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class CausalMediatorResult:
    mediator_kind: MediatorKind
    source_node: str
    target_node: str
    context_key: str
    model_id: str
    model_version: str
    state: CausalBetaState
    support: float | None
    uncertainty: float
    sensitivity: float | None
    evidence_ids: tuple[str, ...]
    negative_evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_versions: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class _CausalMediatorEngine:
    def __init__(self, kind: MediatorKind) -> None:
        self.kind = kind

    def evaluate(
        self,
        evidence: Iterable[CausalMediatorEvidence | Mapping[str, Any]],
        *,
        source_node: str,
        target_node: str,
        context_key: str,
        model_id: str,
        model_version: str,
        minimum_sources: int = 2,
    ) -> CausalMediatorResult:
        require_non_empty(source_node, "source_node")
        require_non_empty(target_node, "target_node")
        require_non_empty(context_key, "context_key")
        require_non_empty(model_id, "model_id")
        require_non_empty(model_version, "model_version")
        if minimum_sources < 1:
            raise ValidationError("minimum_sources must be positive")
        values = tuple(_coerce_evidence(value) for value in evidence)
        kind_values = tuple(value for value in values if value.mediator_kind == self.kind)
        pair_values = tuple(
            value
            for value in kind_values
            if value.source_node == source_node and value.target_node == target_node
        )
        exact = tuple(value for value in pair_values if value.context_key == context_key)
        if not exact:
            state = CausalBetaState.OUT_OF_DOMAIN if pair_values else CausalBetaState.ABSTAINED
            reason = (
                "mediator evidence exists only for another context"
                if pair_values
                else "no matching mediator evidence was supplied"
            )
            return self._result(
                source_node,
                target_node,
                context_key,
                model_id,
                model_version,
                state,
                None,
                1.0,
                None,
                (),
                (),
                (),
                (),
                reason,
            )
        positive = tuple(
            value for value in exact if value.direction == CausalEvidenceDirection.SUPPORTS
        )
        negative = tuple(
            value
            for value in exact
            if value.direction == CausalEvidenceDirection.AGAINST or value.negative_control
        )
        if positive and negative:
            state = CausalBetaState.CONTRADICTORY
            support = None
            uncertainty = 1.0
            reason = "supporting and against/negative-control mediator evidence coexist"
        elif not positive:
            state = CausalBetaState.PARTIAL
            support = 0.0
            uncertainty = 1.0
            reason = "only against or negative-control mediator evidence was supplied"
        else:
            confidence = tuple(1 - value.uncertainty for value in positive)
            denominator = sum(confidence)
            support = (
                sum(value.support * (1 - value.uncertainty) for value in positive) / denominator
                if denominator
                else None
            )
            source_count = len({value.source_id for value in positive})
            uncertainty = min(
                1.0,
                fmean(value.uncertainty for value in positive)
                + (0.2 if source_count < minimum_sources else 0.0),
            )
            state = (
                CausalBetaState.SUPPORTED
                if source_count >= minimum_sources
                else CausalBetaState.PARTIAL
            )
            reason = (
                "independent source paths support the declared mediator"
                if state == CausalBetaState.SUPPORTED
                else "mediator support is present but does not meet the independent-source minimum"
            )
        sensitivities = tuple(value.sensitivity for value in exact if value.sensitivity is not None)
        return self._result(
            source_node,
            target_node,
            context_key,
            model_id,
            model_version,
            state,
            round(support, 9) if support is not None else None,
            round(uncertainty, 9),
            round(median(sensitivities), 9) if sensitivities else None,
            tuple(value.evidence_id for value in exact),
            tuple(value.evidence_id for value in negative),
            tuple(sorted({value.source_id for value in exact})),
            tuple(sorted({value.source_version for value in exact})),
            reason,
        )

    def _result(
        self,
        source_node: str,
        target_node: str,
        context_key: str,
        model_id: str,
        model_version: str,
        state: CausalBetaState,
        support: float | None,
        uncertainty: float,
        sensitivity: float | None,
        evidence_ids: tuple[str, ...],
        negative_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        source_versions: tuple[str, ...],
        reason: str,
    ) -> CausalMediatorResult:
        return CausalMediatorResult(
            mediator_kind=self.kind,
            source_node=source_node,
            target_node=target_node,
            context_key=context_key,
            model_id=model_id,
            model_version=model_version,
            state=state,
            support=support,
            uncertainty=uncertainty,
            sensitivity=sensitivity,
            evidence_ids=evidence_ids,
            negative_evidence_ids=negative_ids,
            source_ids=source_ids,
            source_versions=source_versions,
            reason=reason,
            warnings=(
                "Mediator support is a bounded evidence summary, not a causal probability "
                "or clinical claim.",
                "Negative controls and against-direction evidence remain attached and are "
                "not treated as missing.",
                "Calibration, sensitivity analysis, transport, and external validation "
                "remain required.",
            ),
            content_address=content_hash(
                {
                    "kind": self.kind,
                    "source_node": source_node,
                    "target_node": target_node,
                    "context_key": context_key,
                    "model_id": model_id,
                    "model_version": model_version,
                    "state": state,
                    "support": support,
                    "uncertainty": uncertainty,
                    "sensitivity": sensitivity,
                    "evidence_ids": evidence_ids,
                    "negative_ids": negative_ids,
                }
            ),
        )


class SequenceToElementCausalMediator:
    """Evaluate sequence-to-element mediator evidence."""

    _ENGINE = _CausalMediatorEngine(MediatorKind.SEQUENCE_TO_ELEMENT)

    def evaluate(
        self, evidence: Iterable[CausalMediatorEvidence | Mapping[str, Any]], **kwargs: Any
    ) -> CausalMediatorResult:
        return self._ENGINE.evaluate(evidence, **kwargs)


class ElementToGeneCausalMediator:
    """Evaluate element-to-gene mediator evidence."""

    _ENGINE = _CausalMediatorEngine(MediatorKind.ELEMENT_TO_GENE)

    def evaluate(
        self, evidence: Iterable[CausalMediatorEvidence | Mapping[str, Any]], **kwargs: Any
    ) -> CausalMediatorResult:
        return self._ENGINE.evaluate(evidence, **kwargs)


class GeneToStateCausalMediator:
    """Evaluate gene-to-state mediator evidence."""

    _ENGINE = _CausalMediatorEngine(MediatorKind.GENE_TO_STATE)

    def evaluate(
        self, evidence: Iterable[CausalMediatorEvidence | Mapping[str, Any]], **kwargs: Any
    ) -> CausalMediatorResult:
        return self._ENGINE.evaluate(evidence, **kwargs)


@dataclass(frozen=True, slots=True)
class CounterfactualAlleleStateObservation:
    """Measured or declared state value for one allele."""

    observation_id: str
    allele: str
    state_id: str
    value: float
    uncertainty: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "observation_id",
            "allele",
            "state_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.allele not in {"reference", "alternate"}:
            raise ValidationError("counterfactual allele must be reference or alternate")
        if not 0 <= self.uncertainty <= 1:
            raise ValidationError("counterfactual uncertainty must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CounterfactualAlleleStateResult:
    state_id: str
    context_key: str
    model_id: str
    model_version: str
    state: CausalBetaState
    reference_value: float | None
    alternate_value: float | None
    delta_alternate_minus_reference: float | None
    sensitivity: float | None
    reference_observation_ids: tuple[str, ...]
    alternate_observation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reason: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CounterfactualAlleleStateSimulator:
    """Compare declared reference/alternate state observations transparently."""

    def simulate(
        self,
        observations: Iterable[CounterfactualAlleleStateObservation | Mapping[str, Any]],
        *,
        state_id: str,
        context_key: str,
        model_id: str,
        model_version: str,
        ambiguity_tolerance: float = 0.20,
    ) -> CounterfactualAlleleStateResult:
        for name, value in (
            ("state_id", state_id),
            ("context_key", context_key),
            ("model_id", model_id),
            ("model_version", model_version),
        ):
            require_non_empty(value, name)
        if ambiguity_tolerance < 0:
            raise ValidationError("ambiguity_tolerance cannot be negative")
        values = tuple(_coerce_counterfactual(value) for value in observations)
        state_values = tuple(value for value in values if value.state_id == state_id)
        exact = tuple(value for value in state_values if value.context_key == context_key)
        if not exact:
            state = CausalBetaState.OUT_OF_DOMAIN if state_values else CausalBetaState.ABSTAINED
            return self._result(
                state_id,
                context_key,
                model_id,
                model_version,
                state,
                None,
                None,
                None,
                None,
                (),
                (),
                (),
                "reference and alternate state observations are not available in the exact context",
            )
        reference = tuple(value for value in exact if value.allele == "reference")
        alternate = tuple(value for value in exact if value.allele == "alternate")
        ref_values = tuple(value.value for value in reference)
        alt_values = tuple(value.value for value in alternate)
        if not ref_values or not alt_values:
            state = CausalBetaState.PARTIAL
            reason = "only one allele has a declared state observation"
        elif (
            max(ref_values) - min(ref_values) > ambiguity_tolerance
            or max(alt_values) - min(alt_values) > ambiguity_tolerance
        ):
            state = CausalBetaState.AMBIGUOUS
            reason = "replicate or model observations disagree beyond the declared tolerance"
        else:
            state = CausalBetaState.SUPPORTED
            reason = "reference and alternate state observations support a descriptive delta"
        reference_value = median(ref_values) if ref_values else None
        alternate_value = median(alt_values) if alt_values else None
        delta = (
            alternate_value - reference_value
            if reference_value is not None and alternate_value is not None
            else None
        )
        return self._result(
            state_id,
            context_key,
            model_id,
            model_version,
            state,
            reference_value,
            alternate_value,
            delta,
            abs(delta) if delta is not None else None,
            tuple(value.observation_id for value in reference),
            tuple(value.observation_id for value in alternate),
            tuple(sorted({value.source_id for value in exact})),
            reason,
        )

    @staticmethod
    def _result(
        state_id: str,
        context_key: str,
        model_id: str,
        model_version: str,
        state: CausalBetaState,
        reference_value: float | None,
        alternate_value: float | None,
        delta: float | None,
        sensitivity: float | None,
        reference_ids: tuple[str, ...],
        alternate_ids: tuple[str, ...],
        source_ids: tuple[str, ...],
        reason: str,
    ) -> CounterfactualAlleleStateResult:
        return CounterfactualAlleleStateResult(
            state_id=state_id,
            context_key=context_key,
            model_id=model_id,
            model_version=model_version,
            state=state,
            reference_value=reference_value,
            alternate_value=alternate_value,
            delta_alternate_minus_reference=delta,
            sensitivity=sensitivity,
            reference_observation_ids=reference_ids,
            alternate_observation_ids=alternate_ids,
            source_ids=source_ids,
            reason=reason,
            warnings=(
                "Counterfactual delta is a descriptive allele comparison, not proof of "
                "causality or clinical effect.",
                "Reference and alternate values are retained with model/version and exact "
                "context receipts.",
                "Calibration, perturbation validation, negative controls, and unsupported "
                "allele-class gates remain required.",
            ),
            content_address=content_hash(
                {
                    "state_id": state_id,
                    "context_key": context_key,
                    "model_id": model_id,
                    "model_version": model_version,
                    "state": state,
                    "reference_value": reference_value,
                    "alternate_value": alternate_value,
                    "delta": delta,
                    "reference_ids": reference_ids,
                    "alternate_ids": alternate_ids,
                }
            ),
        )


def _rows(
    text: str, input_format: str | None, key: str
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("causal beta input must not be empty")
    selected = (input_format or "").lower().strip()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid causal beta JSON: {exc}") from exc
        rows = payload.get(key, payload) if isinstance(payload, Mapping) else payload
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError(f"causal beta JSON must contain a {key} list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("causal beta TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported causal beta format: {selected}")


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"causal beta field is required: {names[0]}")


def _optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return float(value)
    return None


def _coerce_evidence(value: CausalMediatorEvidence | Mapping[str, Any]) -> CausalMediatorEvidence:
    if isinstance(value, CausalMediatorEvidence):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("causal mediator evidence must be a mapping")
    return CausalMediatorEvidence(
        evidence_id=str(value.get("evidence_id", value.get("id", "causal-input"))),
        mediator_kind=MediatorKind(
            str(value.get("mediator_kind", value.get("kind", "sequence_to_element")))
        ),
        source_node=str(value.get("source_node", value.get("source", ""))),
        target_node=str(value.get("target_node", value.get("target", ""))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        support=float(value.get("support", value.get("score", 0.0))),
        uncertainty=float(value.get("uncertainty", 1.0)),
        source_id=str(value.get("source_id", "causal-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        direction=CausalEvidenceDirection(
            str(value.get("direction", CausalEvidenceDirection.SUPPORTS.value))
        ),
        sensitivity=_optional_float(value, "sensitivity"),
        negative_control=bool(value.get("negative_control", False)),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_counterfactual(
    value: CounterfactualAlleleStateObservation | Mapping[str, Any],
) -> CounterfactualAlleleStateObservation:
    if isinstance(value, CounterfactualAlleleStateObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("counterfactual observation must be a mapping")
    return CounterfactualAlleleStateObservation(
        observation_id=str(value.get("observation_id", value.get("id", "counterfactual-input"))),
        allele=str(value.get("allele", "")),
        state_id=str(value.get("state_id", value.get("state", ""))),
        value=float(value.get("value", value.get("score", 0.0))),
        uncertainty=float(value.get("uncertainty", 1.0)),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "counterfactual-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        attributes=dict(value.get("attributes", {})),
    )


__all__ = [
    "CausalBetaIssue",
    "CausalBetaState",
    "CausalEvidenceDirection",
    "CausalMediatorBatch",
    "CausalMediatorEvidence",
    "CausalMediatorEvidenceParser",
    "CausalMediatorResult",
    "CounterfactualAlleleStateObservation",
    "CounterfactualAlleleStateResult",
    "CounterfactualAlleleStateSimulator",
    "ElementToGeneCausalMediator",
    "GeneToStateCausalMediator",
    "MediatorKind",
    "SequenceToElementCausalMediator",
]
