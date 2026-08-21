"""Scientific-beta adapters and linkers for variant-element-gene evidence.

The beta link plane accepts activity-by-contact, coaccessibility, molecular-QTL,
and allele-specific records as separate evidence paths. It reuses the existing
candidate graph contract, preserving method identity, exact context, source
versions, alternatives, contradiction, and single-method partial states.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from math import log10
from typing import Any

from .errors import ValidationError
from .link_graph import (
    CandidateLinkGraph,
    EnhancerGeneConsensusLinker,
    LinkEvidence,
    LinkState,
    LinkType,
)
from .models import ReferenceContext
from .serialization import content_hash, jsonable, require_non_empty


class LinkGraphBetaDirection(StrEnum):
    GAIN = "gain"
    LOSS = "loss"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class LinkGraphBetaIssue:
    """Quarantined link-evidence row with raw provenance."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "link graph beta issue code")
        require_non_empty(self.message, "link graph beta issue message")
        require_non_empty(self.raw_hash, "link graph beta issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("link graph beta issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ActivityByContactLinkObservation:
    """One activity-by-contact variant-element-gene evidence row."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    activity_signal: float
    contact_signal: float
    contact_scale: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    confidence: float = 1.0
    replicate_id: str | None = None
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.activity_signal < 0 or self.contact_signal < 0 or self.contact_scale <= 0:
            raise ValidationError(
                "activity/contact signals must be non-negative and scale positive"
            )
        if not 0 <= self.confidence <= 1:
            raise ValidationError("activity-by-contact confidence must be between zero and one")

    @property
    def support(self) -> float:
        return min(1.0, self.activity_signal) * min(1.0, self.contact_signal / self.contact_scale)

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["support"] = self.support
        return payload


@dataclass(frozen=True, slots=True)
class ActivityByContactBatch:
    source_id: str
    input_hash: str
    observations: tuple[ActivityByContactLinkObservation, ...]
    issues: tuple[LinkGraphBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        payload = jsonable(self)
        payload["observations"] = tuple(observation.to_dict() for observation in self.observations)
        return payload


class ActivityByContactLinkAdapter:
    """Parse activity-by-contact rows while retaining component measurements."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
        contact_scale: float = 10.0,
    ) -> ActivityByContactBatch:
        rows, json_mode = _rows(text, input_format, "observations")
        if contact_scale <= 0:
            raise ValidationError("contact_scale must be positive")
        observations: list[ActivityByContactLinkObservation] = []
        issues: list[LinkGraphBetaIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(
                    LinkGraphBetaIssue(
                        "invalid_activity_contact_row",
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
                observations.append(
                    ActivityByContactLinkObservation(
                        evidence_id=str(
                            _value(row, "evidence_id", "link_id", default=f"{source_id}:{index}")
                        ),
                        variant_id=str(_value(row, "variant_id", "variant")),
                        element_id=str(
                            _value(row, "element_id", "enhancer_id", "regulatory_element_id")
                        ),
                        gene_id=str(_value(row, "gene_id", "promoter_id", "gene")),
                        activity_signal=float(
                            _value(row, "activity_signal", "activity", "activity_score")
                        ),
                        contact_signal=float(
                            _value(row, "contact_signal", "contact", "contact_score")
                        ),
                        contact_scale=float(_value(row, "contact_scale", default=contact_scale)),
                        context_key=str(_value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            _value(row, "source_version", "version", default=source_version)
                        ),
                        raw_hash=raw_hash,
                        confidence=float(_value(row, "confidence", default=1.0)),
                        replicate_id=_optional_text(row, "replicate_id", "replicate"),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LinkGraphBetaIssue(
                        "invalid_activity_contact_row",
                        str(exc),
                        raw_hash,
                        row_number=index,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        input_hash = content_hash(text)
        return ActivityByContactBatch(
            source_id=source_id,
            input_hash=input_hash,
            observations=tuple(observations),
            issues=tuple(issues),
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "input_hash": input_hash,
                    "observations": observations,
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class CoaccessibilityObservation:
    """One coaccessibility evidence path for a variant-element-gene candidate."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    score: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    confidence: float = 1.0
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.score <= 1 or not 0 <= self.confidence <= 1:
            raise ValidationError("coaccessibility score/confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularQtlObservation:
    """One molecular-QTL evidence path with optional p/q-value metadata."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    effect_size: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    q_value: float | None = None
    p_value: float | None = None
    support: float | None = None
    confidence: float = 1.0
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        for name in ("q_value", "p_value", "support", "confidence"):
            value = getattr(self, name)
            if value is not None and not 0 <= value <= 1:
                raise ValidationError(f"molecular-QTL {name} must be between zero and one")

    @property
    def bounded_support(self) -> float:
        if self.support is not None:
            return self.support
        value = self.q_value if self.q_value is not None else self.p_value
        if value is None:
            return 0.0
        return min(1.0, max(0.0, -log10(max(value, 1e-300)) / 10.0))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AlleleSpecificLinkObservation:
    """Allele-specific evidence path with an explicit direction."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    direction: LinkGraphBetaDirection
    support: float
    confidence: float
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    link_type: LinkType = LinkType.CONTACT
    state: LinkState = LinkState.SUPPORTED
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "variant_id",
            "element_id",
            "gene_id",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 0 <= self.support <= 1 or not 0 <= self.confidence <= 1:
            raise ValidationError("allele-specific support/confidence must be between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CoaccessibilityLinker:
    """Convert exact-context coaccessibility paths into candidate graph links."""

    def link(
        self,
        observations: Iterable[CoaccessibilityObservation | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(_coerce_coaccessibility(value) for value in observations)
        evidence = tuple(
            LinkEvidence(
                evidence_id=value.evidence_id,
                variant_id=value.variant_id,
                element_id=value.element_id,
                gene_id=value.gene_id,
                link_type=LinkType.COACCESSIBILITY,
                context_key=value.context_key,
                source_id=value.source_id,
                source_version=value.source_version,
                raw_hash=value.raw_hash,
                support=value.score,
                confidence=value.confidence,
                state=value.state,
                attributes=value.attributes,
            )
            for value in values
        )
        return EnhancerGeneConsensusLinker().link(evidence, context, variant_id=variant_id)


class MolecularQtlLinker:
    """Convert molecular-QTL paths into context-qualified candidate links."""

    def link(
        self,
        observations: Iterable[MolecularQtlObservation | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(_coerce_qtl(value) for value in observations)
        evidence = tuple(
            LinkEvidence(
                evidence_id=value.evidence_id,
                variant_id=value.variant_id,
                element_id=value.element_id,
                gene_id=value.gene_id,
                link_type=LinkType.QTL,
                context_key=value.context_key,
                source_id=value.source_id,
                source_version=value.source_version,
                raw_hash=value.raw_hash,
                support=value.bounded_support,
                confidence=value.confidence,
                state=value.state,
                attributes={
                    **dict(value.attributes),
                    "effect_size": value.effect_size,
                    "p_value": value.p_value,
                    "q_value": value.q_value,
                },
            )
            for value in values
        )
        return EnhancerGeneConsensusLinker().link(evidence, context, variant_id=variant_id)


class AlleleSpecificLinkEvidenceIntegrator:
    """Integrate allele-specific paths while preserving direction conflicts."""

    def integrate(
        self,
        observations: Iterable[AlleleSpecificLinkObservation | Mapping[str, Any]],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(_coerce_allele_specific(value) for value in observations)
        groups: dict[tuple[str, str, str], set[LinkGraphBetaDirection]] = {}
        for value in values:
            if value.context_key == context.key:
                groups.setdefault((value.variant_id, value.element_id, value.gene_id), set()).add(
                    value.direction
                )
        evidence: list[LinkEvidence] = []
        for value in values:
            direction_set = groups.get((value.variant_id, value.element_id, value.gene_id), set())
            conflict = {
                LinkGraphBetaDirection.GAIN,
                LinkGraphBetaDirection.LOSS,
            }.issubset(direction_set)
            evidence.append(
                LinkEvidence(
                    evidence_id=value.evidence_id,
                    variant_id=value.variant_id,
                    element_id=value.element_id,
                    gene_id=value.gene_id,
                    link_type=value.link_type,
                    context_key=value.context_key,
                    source_id=value.source_id,
                    source_version=value.source_version,
                    raw_hash=value.raw_hash,
                    support=value.support,
                    confidence=value.confidence,
                    state=LinkState.CONTRADICTORY if conflict else value.state,
                    attributes={
                        **dict(value.attributes),
                        "allele_direction": value.direction.value,
                    },
                )
            )
        return EnhancerGeneConsensusLinker().link(
            evidence,
            context,
            variant_id=variant_id,
        )


def _rows(
    text: str,
    input_format: str | None,
    collection_key: str,
) -> tuple[tuple[Mapping[str, Any], ...], bool]:
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("link graph beta input must not be empty")
    selected = (input_format or "").lower().strip()
    if not selected:
        selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
    if selected == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid link graph beta JSON: {exc}") from exc
        rows = payload.get(collection_key, payload) if isinstance(payload, Mapping) else payload
        if isinstance(rows, Mapping):
            rows = [rows]
        if not isinstance(rows, list):
            raise ValidationError(f"link graph beta JSON must contain a {collection_key} list")
        return tuple(rows), True
    if selected == "tsv":
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
            raise ValidationError("link graph beta TSV requires a header")
        return tuple(reader), False
    raise ValidationError(f"unsupported link graph beta format: {selected}")


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    if default is not None:
        return default
    raise ValidationError(f"link graph beta field is required: {names[0]}")


def _optional_text(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return str(value)
    return None


def _coerce_coaccessibility(
    value: CoaccessibilityObservation | Mapping[str, Any],
) -> CoaccessibilityObservation:
    if isinstance(value, CoaccessibilityObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("coaccessibility observation must be a mapping")
    return CoaccessibilityObservation(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "coaccessibility-input"))),
        variant_id=str(value.get("variant_id", "")),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("promoter_id", ""))),
        score=float(value.get("score", value.get("support", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "coaccessibility-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        confidence=float(value.get("confidence", 1.0)),
        state=LinkState(str(value.get("state", LinkState.SUPPORTED.value))),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_qtl(value: MolecularQtlObservation | Mapping[str, Any]) -> MolecularQtlObservation:
    if isinstance(value, MolecularQtlObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("molecular-QTL observation must be a mapping")

    def optional_float(key: str) -> float | None:
        return None if value.get(key) in {None, ""} else float(value[key])

    return MolecularQtlObservation(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "qtl-input"))),
        variant_id=str(value.get("variant_id", "")),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("promoter_id", ""))),
        effect_size=float(value.get("effect_size", value.get("effect", 0.0))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "qtl-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        q_value=optional_float("q_value"),
        p_value=optional_float("p_value"),
        support=optional_float("support"),
        confidence=float(value.get("confidence", 1.0)),
        state=LinkState(str(value.get("state", LinkState.SUPPORTED.value))),
        attributes=dict(value.get("attributes", {})),
    )


def _coerce_allele_specific(
    value: AlleleSpecificLinkObservation | Mapping[str, Any],
) -> AlleleSpecificLinkObservation:
    if isinstance(value, AlleleSpecificLinkObservation):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("allele-specific link observation must be a mapping")
    return AlleleSpecificLinkObservation(
        evidence_id=str(value.get("evidence_id", value.get("link_id", "allele-input"))),
        variant_id=str(value.get("variant_id", "")),
        element_id=str(value.get("element_id", value.get("enhancer_id", ""))),
        gene_id=str(value.get("gene_id", value.get("promoter_id", ""))),
        direction=LinkGraphBetaDirection(
            str(value.get("direction", value.get("allele_direction", "unknown")))
        ),
        support=float(value.get("support", 0.0)),
        confidence=float(value.get("confidence", 1.0)),
        context_key=str(value.get("context_key", value.get("context", ""))),
        source_id=str(value.get("source_id", "allele-link-input")),
        source_version=str(value.get("source_version", value.get("version", "unspecified"))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
        link_type=LinkType(str(value.get("link_type", LinkType.CONTACT.value))),
        state=LinkState(str(value.get("state", LinkState.SUPPORTED.value))),
        attributes=dict(value.get("attributes", {})),
    )


__all__ = [
    "ActivityByContactBatch",
    "ActivityByContactLinkAdapter",
    "ActivityByContactLinkObservation",
    "AlleleSpecificLinkEvidenceIntegrator",
    "AlleleSpecificLinkObservation",
    "CoaccessibilityLinker",
    "CoaccessibilityObservation",
    "LinkGraphBetaDirection",
    "LinkGraphBetaIssue",
    "MolecularQtlLinker",
    "MolecularQtlObservation",
]
