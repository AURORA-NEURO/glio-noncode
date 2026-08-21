"""Context-qualified variant, element, and gene link graph construction.

Domain 10 provides transparent baselines for coordinate overlap, nearest-gene
assignment, cCRE element identity, and enhancer-gene evidence consensus.  A
link is a candidate relationship with declared evidence, not a causal or
clinical conclusion.  Missing, context-mismatched, tied, and single-source
paths remain visible in the graph state.
"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .models import CandidateElement, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable


class LinkType(StrEnum):
    """Evidence or baseline method used to create a candidate link."""

    COORDINATE_OVERLAP = "coordinate_overlap"
    NEAREST_GENE = "nearest_gene"
    CCRE_ASSIGNMENT = "ccre_assignment"
    CONTACT = "contact"
    COACCESSIBILITY = "coaccessibility"
    QTL = "qtl"
    PERTURBATION = "perturbation"
    CONSENSUS = "consensus"


class LinkState(StrEnum):
    """Candidate-link state with explicit abstention and transport boundaries."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSENT = "absent"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class LinkIssue:
    """A quarantined gene or link-evidence row."""

    code: str
    message: str
    source_line: int | None = None
    raw_hash: str | None = None
    severity: str = "error"
    remediation: str = "Inspect the source row and preserve its evidence boundary."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GeneFeature:
    """A source-scoped gene interval used only for nearest-gene baseline work."""

    gene_id: str
    symbol: str
    chromosome: str
    start: int
    end: int
    genome_build: str
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    strand: str = "."
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "gene_id",
            "symbol",
            "chromosome",
            "genome_build",
            "context_key",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"gene {name} is required")
        if self.start < 1 or self.end < self.start:
            raise ValidationError("gene coordinates must satisfy 1 <= start <= end")

    def overlaps(self, variant: VariantIdentity) -> bool:
        return (
            normalize_chromosome(self.chromosome) == normalize_chromosome(variant.chromosome)
            and self.start <= variant.end
            and variant.start <= self.end
        )

    def distance_to(self, variant: VariantIdentity) -> int:
        if self.overlaps(variant):
            return 0
        if self.end < variant.start:
            return variant.start - self.end
        return self.start - variant.end

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GeneFeatureBatch:
    """Gene parser output with input receipt and malformed-row accounting."""

    source_id: str
    input_hash: str
    genes: tuple[GeneFeature, ...]
    issues: tuple[LinkIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class GeneFeatureParser:
    """Parse a small, loss-accounted gene interval interchange format."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: str | None = None,
        default_genome_build: str = "GRCh38",
    ) -> GeneFeatureBatch:
        if not source_id.strip():
            raise ValidationError("gene source_id is required")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("gene input must not be empty")
        first = next(line.strip() for line in text.splitlines() if line.strip())
        selected = input_format or ("json" if first.startswith(("{", "[")) else "tsv")
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValidationError(f"invalid gene JSON: {exc}") from exc
            rows = payload.get("genes", payload) if isinstance(payload, Mapping) else payload
            if not isinstance(rows, list):
                raise ValidationError("gene JSON must contain a genes list")
            json_mode = True
        elif selected == "tsv":
            reader = csv.DictReader(io.StringIO(text), delimiter="\t")
            if not reader.fieldnames:
                raise ValidationError("gene TSV requires a header")
            rows = tuple(reader)
            json_mode = False
        else:
            raise ValidationError(f"unsupported gene format: {selected}")
        genes: list[GeneFeature] = []
        issues: list[LinkIssue] = []
        for index, row in enumerate(rows, start=1 if json_mode else 2):
            if not isinstance(row, Mapping):
                issues.append(LinkIssue("invalid_gene_row", "row must be an object"))
                continue
            raw_hash = content_hash(row)
            try:
                start = int(self._value(row, "start", "gene_start"))
                end = int(self._value(row, "end", "gene_end"))
                if start < 0 or end <= start:
                    raise ValidationError("gene input interval must be 0-based half-open")
                genes.append(
                    GeneFeature(
                        gene_id=str(self._value(row, "gene_id", "id")),
                        symbol=str(
                            self._value(row, "symbol", "gene_symbol", default="unspecified")
                        ),
                        chromosome=normalize_chromosome(
                            str(self._value(row, "chromosome", "chrom"))
                        ),
                        start=start + 1,
                        end=end,
                        genome_build=str(
                            self._value(row, "genome_build", "build", default=default_genome_build)
                        ),
                        context_key=str(self._value(row, "context_key", "context")),
                        source_id=source_id,
                        source_version=str(
                            self._value(row, "source_version", "version", default="unspecified")
                        ),
                        raw_hash=raw_hash,
                        strand=str(self._value(row, "strand", default=".")),
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    LinkIssue(
                        "invalid_gene_row",
                        str(exc),
                        None if json_mode else index,
                        raw_hash,
                    )
                )
        body = {
            "source_id": source_id,
            "input_hash": content_hash(text),
            "genes": tuple(genes),
            "issues": tuple(issues),
        }
        return GeneFeatureBatch(
            source_id=source_id,
            input_hash=content_hash(text),
            genes=tuple(genes),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
        for name in names:
            value = row.get(name)
            if value is not None and value != "":
                return value
        if default is not None:
            return default
        raise ValidationError(f"gene field is required: {names[0]}")


@dataclass(frozen=True, slots=True)
class LinkEvidence:
    """One evidence path supplied to the enhancer-gene consensus linker."""

    evidence_id: str
    variant_id: str
    element_id: str
    gene_id: str
    link_type: LinkType
    context_key: str
    source_id: str
    source_version: str
    raw_hash: str
    support: float
    confidence: float
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
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"link evidence {name} is required")
        for name in ("support", "confidence"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValidationError(f"link evidence {name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CandidateLink:
    """A graph edge with method, uncertainty, and source lineage."""

    link_id: str
    variant_id: str
    element_id: str
    gene_id: str | None
    link_type: LinkType
    context_key: str
    state: LinkState
    support: float | None
    uncertainty: float
    distance_bp: int | None
    evidence_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    alternatives: tuple[str, ...]
    reason: str
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in ("link_id", "variant_id", "element_id", "context_key", "reason"):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"candidate link {name} is required")
        if self.support is not None and not 0.0 <= self.support <= 1.0:
            raise ValidationError("candidate link support must be between 0 and 1")
        if not 0.0 <= self.uncertainty <= 1.0:
            raise ValidationError("candidate link uncertainty must be between 0 and 1")
        if not self.evidence_ids and self.state in {
            LinkState.SUPPORTED,
            LinkState.PARTIAL,
        }:
            raise ValidationError("supported candidate links require evidence IDs")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CandidateLinkGraph:
    """A deterministic graph slice for one context and optional variant set."""

    context_key: str
    state: LinkState
    links: tuple[CandidateLink, ...]
    variant_ids: tuple[str, ...]
    element_ids: tuple[str, ...]
    gene_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _graph(
    context: ReferenceContext,
    links: Iterable[CandidateLink],
    *,
    state: LinkState | None = None,
    warnings: Iterable[str] = (),
    variant_ids: Iterable[str] = (),
) -> CandidateLinkGraph:
    values = tuple(
        sorted(
            links,
            key=lambda item: (
                item.variant_id,
                item.element_id,
                item.gene_id or "",
                item.link_type.value,
                item.link_id,
            ),
        )
    )
    states = tuple(item.state for item in values)
    if state is None:
        if not values:
            state = LinkState.ABSTAINED
        elif LinkState.CONTRADICTORY in states:
            state = LinkState.CONTRADICTORY
        elif LinkState.OUT_OF_DOMAIN in states:
            state = LinkState.OUT_OF_DOMAIN
        elif LinkState.ABSTAINED in states:
            state = LinkState.ABSTAINED
        elif LinkState.AMBIGUOUS in states:
            state = LinkState.AMBIGUOUS
        elif all(item == LinkState.SUPPORTED for item in states):
            state = LinkState.SUPPORTED
        else:
            state = LinkState.PARTIAL
    warning_values = tuple(dict.fromkeys(str(item) for item in warnings))
    if not values and not warning_values:
        warning_values = ("No candidate links were produced; this is not negative evidence.",)
    body = {
        "context_key": context.key,
        "state": state,
        "links": values,
        "warnings": warning_values,
        "variant_ids": tuple(sorted(set(variant_ids) | {item.variant_id for item in values})),
    }
    return CandidateLinkGraph(
        context_key=context.key,
        state=state,
        links=values,
        variant_ids=tuple(sorted(set(variant_ids) | {item.variant_id for item in values})),
        element_ids=tuple(sorted({item.element_id for item in values})),
        gene_ids=tuple(sorted({item.gene_id for item in values if item.gene_id})),
        warnings=warning_values,
        content_address=content_hash(body),
    )


def _new_link(
    *,
    variant_id: str,
    element_id: str,
    gene_id: str | None,
    link_type: LinkType,
    context: ReferenceContext,
    state: LinkState,
    support: float | None,
    uncertainty: float,
    distance_bp: int | None,
    evidence_ids: Iterable[str],
    source_ids: Iterable[str],
    alternatives: Iterable[str] = (),
    reason: str,
) -> CandidateLink:
    evidence = tuple(sorted(set(evidence_ids)))
    sources = tuple(sorted(set(source_ids)))
    body = {
        "variant_id": variant_id,
        "element_id": element_id,
        "gene_id": gene_id,
        "link_type": link_type,
        "context": context,
        "state": state,
        "support": support,
        "uncertainty": uncertainty,
        "distance_bp": distance_bp,
        "evidence_ids": evidence,
        "source_ids": sources,
        "alternatives": tuple(sorted(set(alternatives))),
        "reason": reason,
    }
    return CandidateLink(
        link_id=content_hash(body, prefix="link"),
        variant_id=variant_id,
        element_id=element_id,
        gene_id=gene_id,
        link_type=link_type,
        context_key=context.key,
        state=state,
        support=None if support is None else round(support, 9),
        uncertainty=round(uncertainty, 9),
        distance_bp=distance_bp,
        evidence_ids=evidence,
        source_ids=sources,
        alternatives=tuple(sorted(set(alternatives))),
        reason=reason,
        limitations=(
            "This is a research candidate relationship, not proof of enhancer activity "
            "or causality.",
            "External calibration, matched negative controls, transport, and OOD "
            "evaluation remain required.",
        ),
        content_address=content_hash(body),
    )


class CoordinateOverlapLinker:
    """Create variant-to-element candidates from exact interval overlap."""

    def link(
        self,
        variant: VariantIdentity,
        elements: Iterable[CandidateElement],
        context: ReferenceContext,
    ) -> CandidateLinkGraph:
        values = tuple(elements)
        compatible = tuple(
            element
            for element in values
            if element.context.key == context.key
            and normalize_chromosome(element.chromosome) == normalize_chromosome(variant.chromosome)
        )
        overlaps = tuple(
            element
            for element in compatible
            if element.start <= variant.end and variant.start <= element.end
        )
        other_context_overlap = any(
            normalize_chromosome(element.chromosome) == normalize_chromosome(variant.chromosome)
            and element.start <= variant.end
            and variant.start <= element.end
            for element in values
            if element.context.key != context.key
        )
        if not overlaps:
            state = LinkState.OUT_OF_DOMAIN if other_context_overlap else LinkState.ABSENT
            warning = (
                "overlapping elements exist only in another context"
                if other_context_overlap
                else "no context-matched element overlaps the variant"
            )
            return _graph(
                context,
                (),
                state=state,
                warnings=(warning,),
                variant_ids=(variant.variant_id,),
            )
        links = tuple(
            _new_link(
                variant_id=variant.variant_id,
                element_id=element.element_id,
                gene_id=element.target_genes[0] if len(element.target_genes) == 1 else None,
                link_type=LinkType.COORDINATE_OVERLAP,
                context=context,
                state=LinkState.SUPPORTED,
                support=1.0,
                uncertainty=0.35,
                distance_bp=0,
                evidence_ids=(f"overlap:{variant.variant_id}:{element.element_id}",),
                source_ids=(element.source_id,),
                alternatives=element.target_genes[1:],
                reason="variant interval overlaps a context-matched candidate element",
            )
            for element in overlaps
        )
        return _graph(context, links, variant_ids=(variant.variant_id,))


class NearestGeneBaseline:
    """Create a transparent nearest-gene baseline without causal interpretation."""

    def __init__(self, *, max_distance_bp: int | None = None) -> None:
        if max_distance_bp is not None and max_distance_bp < 0:
            raise ValidationError("max_distance_bp must be non-negative")
        self.max_distance_bp = max_distance_bp

    def link(
        self,
        variant: VariantIdentity,
        genes: Iterable[GeneFeature],
        context: ReferenceContext,
    ) -> CandidateLinkGraph:
        compatible = tuple(
            gene
            for gene in genes
            if gene.context_key == context.key
            and gene.genome_build == variant.genome_build
            and normalize_chromosome(gene.chromosome) == normalize_chromosome(variant.chromosome)
        )
        if not compatible:
            return _graph(
                context,
                (),
                state=LinkState.ABSTAINED,
                warnings=("no context-matched gene intervals were supplied",),
                variant_ids=(variant.variant_id,),
            )
        distances = tuple((gene, gene.distance_to(variant)) for gene in compatible)
        nearest_distance = min(distance for _, distance in distances)
        if self.max_distance_bp is not None and nearest_distance > self.max_distance_bp:
            return _graph(
                context,
                (),
                state=LinkState.ABSTAINED,
                warnings=("nearest gene exceeds the declared baseline distance window",),
                variant_ids=(variant.variant_id,),
            )
        nearest = tuple(gene for gene, distance in distances if distance == nearest_distance)
        state = LinkState.SUPPORTED if len(nearest) == 1 else LinkState.AMBIGUOUS
        alternatives = tuple(gene.gene_id for gene in nearest)
        support = 1.0 / (1.0 + nearest_distance / 1000.0)
        links = tuple(
            _new_link(
                variant_id=variant.variant_id,
                element_id=f"nearest-gene:{variant.variant_id}",
                gene_id=gene.gene_id,
                link_type=LinkType.NEAREST_GENE,
                context=context,
                state=state,
                support=support,
                uncertainty=0.5 if len(nearest) == 1 else 0.9,
                distance_bp=nearest_distance,
                evidence_ids=(f"gene-distance:{variant.variant_id}:{gene.gene_id}",),
                source_ids=(gene.source_id,),
                alternatives=tuple(item for item in alternatives if item != gene.gene_id),
                reason="nearest-gene distance baseline; distance is not a regulatory mechanism",
            )
            for gene in nearest
        )
        return _graph(context, links, state=state, variant_ids=(variant.variant_id,))


@dataclass(frozen=True, slots=True)
class CcreAssignment:
    """cCRE assignment result retaining every overlapping element candidate."""

    variant_id: str
    context_key: str
    state: LinkState
    element_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CcreElementAssigner:
    """Assign variant overlap to cCRE elements without selecting a hidden winner."""

    def assign(
        self,
        variant: VariantIdentity,
        elements: Iterable[CandidateElement],
        context: ReferenceContext,
    ) -> CcreAssignment:
        values = tuple(elements)
        ccre = tuple(
            element
            for element in values
            if element.element_type.lower() in {"ccre", "candidate_cis_regulatory_element"}
        )
        matched = tuple(
            element
            for element in ccre
            if element.context.key == context.key
            and normalize_chromosome(element.chromosome) == normalize_chromosome(variant.chromosome)
            and element.start <= variant.end
            and variant.start <= element.end
        )
        out_of_domain = any(
            element.context.key != context.key
            and normalize_chromosome(element.chromosome) == normalize_chromosome(variant.chromosome)
            and element.start <= variant.end
            and variant.start <= element.end
            for element in ccre
        )
        if not matched:
            state = LinkState.OUT_OF_DOMAIN if out_of_domain else LinkState.ABSENT
            reason = (
                "cCRE overlap exists only in another context"
                if out_of_domain
                else "no context-matched cCRE overlaps the variant"
            )
        else:
            state = LinkState.SUPPORTED if len(matched) == 1 else LinkState.AMBIGUOUS
            reason = (
                "one context-matched cCRE assigned"
                if len(matched) == 1
                else "multiple context-matched cCREs remain assigned"
            )
        body = {
            "variant_id": variant.variant_id,
            "context": context,
            "state": state,
            "elements": tuple(element.element_id for element in matched),
            "out_of_domain": out_of_domain,
        }
        return CcreAssignment(
            variant_id=variant.variant_id,
            context_key=context.key,
            state=state,
            element_ids=tuple(element.element_id for element in matched),
            source_ids=tuple(sorted({element.source_id for element in matched})),
            reason=reason,
            content_address=content_hash(body),
        )


class EnhancerGeneConsensusLinker:
    """Combine independent element-gene evidence paths with visible dependence."""

    def link(
        self,
        evidence: Iterable[LinkEvidence],
        context: ReferenceContext,
        *,
        variant_id: str | None = None,
    ) -> CandidateLinkGraph:
        values = tuple(
            item
            for item in evidence
            if (variant_id is None or item.variant_id == variant_id)
        )
        context_rows = tuple(item for item in values if item.context_key == context.key)
        other_context = bool(values) and not context_rows
        groups: dict[tuple[str, str, str], list[LinkEvidence]] = defaultdict(list)
        for item in context_rows:
            groups[(item.variant_id, item.element_id, item.gene_id)].append(item)
        links: list[CandidateLink] = []
        for (group_variant, element_id, gene_id), rows in sorted(groups.items()):
            contradictory = any(row.state == LinkState.CONTRADICTORY for row in rows)
            methods = tuple(sorted({row.link_type.value for row in rows}))
            alternatives = tuple(
                sorted(
                    {
                        other_gene
                        for other_variant, other_element, other_gene in groups
                        if other_variant == group_variant
                        and other_element == element_id
                        and other_gene != gene_id
                    }
                )
            )
            weighted_support = sum(row.support * row.confidence for row in rows)
            total_confidence = sum(row.confidence for row in rows)
            support = weighted_support / total_confidence if total_confidence else None
            confidence = fmean(row.confidence for row in rows) if rows else 0.0
            if contradictory:
                state = LinkState.CONTRADICTORY
                support = None
                uncertainty = 1.0
                reason = "contradictory evidence paths remain in the consensus group"
            elif len(methods) >= 2:
                state = LinkState.SUPPORTED
                uncertainty = min(1.0, 1.0 - confidence + 0.05)
                reason = "multiple declared evidence methods support the element-gene candidate"
            else:
                state = LinkState.PARTIAL
                uncertainty = min(1.0, 1.0 - confidence + 0.15)
                reason = "only one evidence method supports the element-gene candidate"
            links.append(
                _new_link(
                    variant_id=group_variant,
                    element_id=element_id,
                    gene_id=gene_id,
                    link_type=LinkType.CONSENSUS,
                    context=context,
                    state=state,
                    support=support,
                    uncertainty=uncertainty,
                    distance_bp=None,
                    evidence_ids=(row.evidence_id for row in rows),
                    source_ids=(row.source_id for row in rows),
                    alternatives=alternatives,
                    reason=reason + f"; methods={','.join(methods)}",
                )
            )
        if not links:
            state = LinkState.OUT_OF_DOMAIN if other_context else LinkState.ABSTAINED
            warning = (
                "link evidence exists only outside the target context"
                if other_context
                else "no enhancer-gene evidence was supplied"
            )
            return _graph(
                context,
                (),
                state=state,
                warnings=(warning,),
                variant_ids=(variant_id,) if variant_id else (),
            )
        return _graph(context, links, variant_ids=(variant_id,) if variant_id else ())


__all__ = [
    "CandidateLink",
    "CandidateLinkGraph",
    "CcreAssignment",
    "CcreElementAssigner",
    "CoordinateOverlapLinker",
    "EnhancerGeneConsensusLinker",
    "GeneFeature",
    "GeneFeatureBatch",
    "GeneFeatureParser",
    "LinkEvidence",
    "LinkIssue",
    "LinkState",
    "LinkType",
    "NearestGeneBaseline",
]
