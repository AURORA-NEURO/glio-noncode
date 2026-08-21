"""Deep topology, regulatory-link, causal, and cohort frontier capabilities.

These D09-D12 implementations are bounded inference surfaces. They calculate
declared descriptive scores and uncertainty summaries, keep dependence and
transport assumptions visible, and publish only content-addressed research
receipts.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
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
from .serialization import jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class EcDNAContact:
    amplicon_id: str
    context_key: str
    element_id: str
    gene_id: str
    contact_score: float
    source_ids: tuple[str, ...]
    normalized_support: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EcDNAContactReport:
    contacts: tuple[EcDNAContact, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class EcDNARegulatoryContactModel:
    """Aggregate declared ecDNA regulatory contacts with source-aware support."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_contact_score: float = 0.5,
        minimum_sources: int = 1,
    ) -> EcDNAContactReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_contact_score = _bounded(minimum_contact_score, field="minimum_contact_score")
        if minimum_sources < 1:
            raise ValidationError("minimum_sources must be positive")
        contacts: list[EcDNAContact] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"ecDNA contact {index}")
            amplicon = _required_text(row.get("amplicon_id", row.get("id")), field="amplicon_id")
            element = _required_text(row.get("element_id"), field="element_id")
            gene = _required_text(row.get("gene_id"), field="gene_id")
            score = _bounded(row.get("contact_score", 0.0), field="contact_score")
            sources = tuple(
                sorted(
                    {_required_text(item, field="source_id") for item in row.get("source_ids", ())}
                )
            )
            issues: list[FrontierIssue] = []
            if len(sources) < minimum_sources:
                issues.append(
                    FrontierIssue(
                        "insufficient_ecDNA_sources",
                        "ecDNA contact lacks required source support",
                        "review",
                        record_id=amplicon,
                    )
                )
            if score < minimum_contact_score:
                issues.append(
                    FrontierIssue(
                        "weak_ecDNA_contact",
                        "ecDNA contact score is below threshold",
                        "review",
                        record_id=amplicon,
                    )
                )
            if _context(row, context_key) != context_key:
                issues.append(
                    FrontierIssue(
                        "ecDNA_context_mismatch",
                        "ecDNA contact context differs from request",
                        "blocking",
                        "context_key",
                        amplicon,
                    )
                )
            normalized = round(score * min(1.0, len(sources) / max(1, minimum_sources)), 6)
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            contacts.append(
                EcDNAContact(
                    amplicon,
                    context_key,
                    element,
                    gene,
                    score,
                    sources,
                    normalized,
                    state,
                    tuple(issues),
                )
            )
        supported = tuple(
            item.amplicon_id for item in contacts if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.amplicon_id for item in contacts if item.state != FrontierState.ACCEPTED
        )
        return EcDNAContactReport(tuple(contacts), supported, review, _address(contacts))


@dataclass(frozen=True, slots=True)
class CompartmentSwitch:
    region_id: str
    context_key: str
    previous_score: float
    current_score: float
    previous_compartment: str
    current_compartment: str
    switch_kind: str
    confidence: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CompartmentSwitchReport:
    switches: tuple[CompartmentSwitch, ...]
    switched_ids: tuple[str, ...]
    stable_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CompartmentSwitchEstimator:
    """Estimate A/B compartment transitions from paired signed scores."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        switch_threshold: float = 0.15,
    ) -> CompartmentSwitchReport:
        context_key = require_non_empty(context_key, "context_key")
        switch_threshold = _float(switch_threshold, field="switch_threshold")
        switches: list[CompartmentSwitch] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"compartment {index}")
            region_id = (
                _text(row.get("region_id", row.get("id")), field="region_id") or f"region:{index}"
            )
            previous = _float(row.get("previous_score"), field="previous_score")
            current = _float(row.get("current_score"), field="current_score")
            previous_compartment = "A" if previous >= 0 else "B"
            current_compartment = "A" if current >= 0 else "B"
            delta = current - previous
            switched = (
                previous_compartment != current_compartment and abs(delta) >= switch_threshold
            )
            confidence = round(min(1.0, abs(delta) / max(switch_threshold, 1e-9)), 6)
            kind = f"{previous_compartment}_to_{current_compartment}" if switched else "stable"
            state = (
                FrontierState.ACCEPTED if abs(delta) >= switch_threshold else FrontierState.REVIEW
            )
            switches.append(
                CompartmentSwitch(
                    region_id,
                    context_key,
                    previous,
                    current,
                    previous_compartment,
                    current_compartment,
                    kind,
                    confidence,
                    state,
                )
            )
        switched = tuple(
            item.region_id
            for item in switches
            if item.switch_kind != "stable" and item.state == FrontierState.ACCEPTED
        )
        stable = tuple(item.region_id for item in switches if item.switch_kind == "stable")
        return CompartmentSwitchReport(tuple(switches), switched, stable, _address(switches))


@dataclass(frozen=True, slots=True)
class TopologyTransport:
    path_id: str
    context_key: str
    node_ids: tuple[str, ...]
    edge_count: int
    transported_signal: float
    uncertainty: float
    effective_signal: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyTransportReport:
    transports: tuple[TopologyTransport, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TopologyUncertaintyTransportModel:
    """Transport a signal across declared topology edges with uncertainty loss."""

    def transport(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_effective_signal: float = 0.3,
    ) -> TopologyTransportReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_effective_signal = _bounded(
            minimum_effective_signal, field="minimum_effective_signal"
        )
        transports: list[TopologyTransport] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"topology path {index}")
            path_id = _text(row.get("path_id", row.get("id")), field="path_id") or f"path:{index}"
            nodes = _tuple_text(row.get("node_ids"), field="node_ids")
            edges = tuple(_mapping(item, label="topology edge") for item in row.get("edges", ()))
            signal = _bounded(row.get("signal", 0.0), field="signal")
            uncertainty = sum(
                _bounded(edge.get("uncertainty", 0.0), field="edge_uncertainty") for edge in edges
            )
            effective = round(max(0.0, signal * (1.0 - min(1.0, uncertainty))), 6)
            issues: list[FrontierIssue] = []
            if len(nodes) != len(edges) + 1 and edges:
                issues.append(
                    FrontierIssue(
                        "topology_path_disconnected",
                        "node and edge counts do not describe a contiguous path",
                        "review",
                        record_id=path_id,
                    )
                )
            if effective < minimum_effective_signal:
                issues.append(
                    FrontierIssue(
                        "weak_transported_signal",
                        "uncertainty-adjusted signal is below threshold",
                        "review",
                        record_id=path_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            transports.append(
                TopologyTransport(
                    path_id,
                    context_key,
                    nodes,
                    len(edges),
                    signal,
                    round(uncertainty, 6),
                    effective,
                    state,
                    tuple(issues),
                )
            )
        supported = tuple(
            item.path_id for item in transports if item.state == FrontierState.ACCEPTED
        )
        review = tuple(item.path_id for item in transports if item.state != FrontierState.ACCEPTED)
        return TopologyTransportReport(tuple(transports), supported, review, _address(transports))


@dataclass(frozen=True, slots=True)
class ThreeDEvidenceBundle:
    bundle_id: str
    context_key: str
    path_ids: tuple[str, ...]
    records_address: str
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ThreeDEvidencePublisher:
    """Publish 3D topology evidence with exact-context and path receipts."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        assay_ids: Sequence[str],
    ) -> ThreeDEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        assays = tuple(sorted({require_non_empty(str(item), "assay_id") for item in assay_ids}))
        normalized = tuple(dict(_mapping(row, label="3D evidence")) for row in records)
        if not normalized or not assays:
            raise ValidationError("3D evidence and assay_ids must not be empty")
        if any(_context(row, context_key) != context_key for row in normalized):
            raise ValidationError("3D evidence context does not match bundle")
        paths = tuple(
            sorted(
                {
                    _required_text(row.get("path_id", row.get("id")), field="path_id")
                    for row in normalized
                }
            )
        )
        records_address = _address(normalized)
        bundle_address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "path_ids": paths,
                "assay_ids": assays,
                "records_address": records_address,
            }
        )
        return ThreeDEvidenceBundle(
            bundle_id, context_key, paths, records_address, bundle_address, FrontierState.PUBLISHED
        )


@dataclass(frozen=True, slots=True)
class DependenceCorrectedLink:
    link_id: str
    context_key: str
    raw_support: float
    dependence_group: str
    group_size: int
    corrected_support: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DependenceCorrectionReport:
    links: tuple[DependenceCorrectedLink, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LinkEvidenceDependenceCorrector:
    """Downweight correlated link evidence by declared dependence groups."""

    def correct(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> DependenceCorrectionReport:
        context_key = require_non_empty(context_key, "context_key")
        rows = tuple(_mapping(raw, label="link evidence") for raw in records)
        groups = Counter(
            _text(
                row.get("dependence_group", row.get("source_id", "unknown")),
                field="dependence_group",
            )
            or "unknown"
            for row in rows
        )
        links: list[DependenceCorrectedLink] = []
        for index, row in enumerate(rows, start=1):
            link_id = _text(row.get("link_id", row.get("id")), field="link_id") or f"link:{index}"
            group = (
                _text(
                    row.get("dependence_group", row.get("source_id", "unknown")),
                    field="dependence_group",
                )
                or "unknown"
            )
            raw_support = _bounded(row.get("support", row.get("score", 0.0)), field="support")
            size = groups[group]
            corrected = round(raw_support / max(1, size), 6)
            state = FrontierState.ACCEPTED if corrected > 0 else FrontierState.REVIEW
            links.append(
                DependenceCorrectedLink(
                    link_id, context_key, raw_support, group, size, corrected, state
                )
            )
        return DependenceCorrectionReport(tuple(links), _address(links))


@dataclass(frozen=True, slots=True)
class TargetGeneRank:
    link_id: str
    context_key: str
    variant_id: str
    element_id: str
    gene_id: str
    component_scores: Mapping[str, float]
    total_score: float
    rank: int
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TargetGeneRankReport:
    ranks: tuple[TargetGeneRank, ...]
    top_gene_by_variant: Mapping[str, str]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TargetGeneRanker:
    """Rank candidate target genes from declared component scores."""

    def rank(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        weights: Mapping[str, float] | None = None,
    ) -> TargetGeneRankReport:
        context_key = require_non_empty(context_key, "context_key")
        weight_map = {
            str(key): _float(value, field=f"weight:{key}") for key, value in (weights or {}).items()
        }
        parsed: list[tuple[Mapping[str, Any], str, str, str, str, dict[str, float], float]] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"target link {index}")
            link_id = _text(row.get("link_id", row.get("id")), field="link_id") or f"link:{index}"
            variant = _required_text(row.get("variant_id"), field="variant_id")
            element = _required_text(row.get("element_id"), field="element_id")
            gene = _required_text(row.get("gene_id"), field="gene_id")
            raw_scores = _mapping(
                row.get("component_scores", row.get("scores", {})), label="component_scores"
            )
            scores = {
                str(key): _bounded(value, field=f"score:{key}") for key, value in raw_scores.items()
            }
            total = sum(scores[key] * weight_map.get(key, 1.0) for key in scores)
            parsed.append((row, link_id, variant, element, gene, scores, total))
        parsed.sort(key=lambda item: (item[2], -item[6], item[4], item[1]))
        ranks: list[TargetGeneRank] = []
        counts: Counter[str] = Counter()
        top: dict[str, str] = {}
        for _row, link_id, variant, element, gene, scores, total in parsed:
            counts[variant] += 1
            ranks.append(
                TargetGeneRank(
                    link_id,
                    context_key,
                    variant,
                    element,
                    gene,
                    scores,
                    round(total, 6),
                    counts[variant],
                    FrontierState.ACCEPTED if total > 0 else FrontierState.REVIEW,
                )
            )
            top.setdefault(variant, gene)
        return TargetGeneRankReport(tuple(ranks), top, _address(ranks))


@dataclass(frozen=True, slots=True)
class LinkCalibrationDecision:
    link_id: str
    context_key: str
    predicted_score: float
    observed_score: float | None
    calibration_error: float | None
    uncertainty: float
    abstained: bool
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkCalibrationReport:
    decisions: tuple[LinkCalibrationDecision, ...]
    accepted_ids: tuple[str, ...]
    abstained_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LinkCalibrationAndAbstention:
    """Calibrate link scores against optional observations and abstain on uncertainty."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        maximum_uncertainty: float = 0.25,
        maximum_calibration_error: float = 0.3,
    ) -> LinkCalibrationReport:
        context_key = require_non_empty(context_key, "context_key")
        maximum_uncertainty = _float(maximum_uncertainty, field="maximum_uncertainty")
        maximum_calibration_error = _float(
            maximum_calibration_error, field="maximum_calibration_error"
        )
        decisions: list[LinkCalibrationDecision] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"link calibration {index}")
            link_id = _text(row.get("link_id", row.get("id")), field="link_id") or f"link:{index}"
            predicted = _bounded(row.get("predicted_score", 0.0), field="predicted_score")
            observed_raw = row.get("observed_score")
            observed = (
                _bounded(observed_raw, field="observed_score") if observed_raw is not None else None
            )
            error = round(abs(predicted - observed), 6) if observed is not None else None
            uncertainty = _float(row.get("uncertainty", 0.0), field="uncertainty")
            issues: list[FrontierIssue] = []
            if uncertainty > maximum_uncertainty:
                issues.append(
                    FrontierIssue(
                        "link_uncertainty_high",
                        "link uncertainty exceeds abstention threshold",
                        "review",
                        record_id=link_id,
                    )
                )
            if error is not None and error > maximum_calibration_error:
                issues.append(
                    FrontierIssue(
                        "link_calibration_error_high",
                        "link calibration error exceeds threshold",
                        "review",
                        record_id=link_id,
                    )
                )
            abstained = bool(issues)
            state = FrontierState.REVIEW if abstained else FrontierState.ACCEPTED
            decisions.append(
                LinkCalibrationDecision(
                    link_id,
                    context_key,
                    predicted,
                    observed,
                    error,
                    uncertainty,
                    abstained,
                    state,
                    tuple(issues),
                )
            )
        accepted = tuple(item.link_id for item in decisions if not item.abstained)
        abstained = tuple(item.link_id for item in decisions if item.abstained)
        return LinkCalibrationReport(tuple(decisions), accepted, abstained, _address(decisions))


@dataclass(frozen=True, slots=True)
class LinkEvidenceBundle:
    bundle_id: str
    context_key: str
    link_ids: tuple[str, ...]
    records_address: str
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class LinkEvidencePublisher:
    """Publish variant-element-gene links with context and source receipts."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
    ) -> LinkEvidenceBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        normalized = tuple(dict(_mapping(row, label="link evidence")) for row in records)
        if not normalized:
            raise ValidationError("link evidence must not be empty")
        for row in normalized:
            _required_text(row.get("link_id", row.get("id")), field="link_id")
            _required_text(row.get("source_id"), field="source_id")
            if _context(row, context_key) != context_key:
                raise ValidationError("link evidence context does not match bundle")
        ids = tuple(
            sorted(
                {
                    _required_text(row.get("link_id", row.get("id")), field="link_id")
                    for row in normalized
                }
            )
        )
        records_address = _address(normalized)
        address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "link_ids": ids,
                "records_address": records_address,
            }
        )
        return LinkEvidenceBundle(
            bundle_id, context_key, ids, records_address, address, FrontierState.PUBLISHED
        )


@dataclass(frozen=True, slots=True)
class PosteriorDecomposition:
    hypothesis_id: str
    context_key: str
    prior: float
    likelihood: float
    measurement: float
    dependency_penalty: float
    raw_posterior: float
    normalized_posterior: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PosteriorDecompositionReport:
    components: tuple[PosteriorDecomposition, ...]
    top_hypothesis_id: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class PosteriorDecompositionEngine:
    """Decompose bounded posterior scores into named evidence components."""

    def decompose(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
    ) -> PosteriorDecompositionReport:
        context_key = require_non_empty(context_key, "context_key")
        values: list[tuple[str, float, float, float, float, float]] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"posterior {index}")
            hypothesis = (
                _text(row.get("hypothesis_id", row.get("id")), field="hypothesis_id")
                or f"hypothesis:{index}"
            )
            prior = _bounded(row.get("prior", 0.0), field="prior")
            likelihood = _bounded(row.get("likelihood", 0.0), field="likelihood")
            measurement = _bounded(row.get("measurement", 0.0), field="measurement")
            penalty = _bounded(row.get("dependency_penalty", 0.0), field="dependency_penalty")
            raw_value = max(0.0, prior * likelihood * measurement * (1.0 - penalty))
            values.append((hypothesis, prior, likelihood, measurement, penalty, raw_value))
        denominator = sum(item[5] for item in values)
        components = tuple(
            PosteriorDecomposition(
                item[0],
                context_key,
                item[1],
                item[2],
                item[3],
                item[4],
                round(item[5], 6),
                round(item[5] / denominator, 6) if denominator else 0.0,
                FrontierState.ACCEPTED if denominator else FrontierState.REVIEW,
            )
            for item in values
        )
        top = (
            max(components, key=lambda item: item.normalized_posterior).hypothesis_id
            if components and denominator
            else None
        )
        return PosteriorDecompositionReport(components, top, _address(components))


@dataclass(frozen=True, slots=True)
class DriverPosterior:
    driver_id: str
    context_key: str
    evidence_ids: tuple[str, ...]
    evidence_support: float
    prior: float
    posterior: float
    rank: int
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DriverPosteriorReport:
    posteriors: tuple[DriverPosterior, ...]
    top_driver_id: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryDriverHypothesisPosterior:
    """Rank regulatory-driver hypotheses from independent evidence support."""

    def infer(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_support: float = 0.2,
    ) -> DriverPosteriorReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_support = _bounded(minimum_support, field="minimum_support")
        values: list[tuple[str, tuple[str, ...], float, float]] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"driver hypothesis {index}")
            driver = (
                _text(row.get("driver_id", row.get("id")), field="driver_id") or f"driver:{index}"
            )
            evidence = _tuple_text(row.get("evidence_ids"), field="evidence_ids")
            support = _bounded(row.get("evidence_support", 0.0), field="evidence_support")
            prior = _bounded(row.get("prior", 0.0), field="prior")
            values.append((driver, evidence, support, prior))
        raw_scores = [item[2] * item[3] for item in values]
        denominator = sum(raw_scores)
        ranked = sorted(
            zip(values, raw_scores, strict=True), key=lambda item: (-item[1], item[0][0])
        )
        posteriors: list[DriverPosterior] = []
        for rank, ((driver, evidence, support, prior), raw_score) in enumerate(ranked, start=1):
            posteriors.append(
                DriverPosterior(
                    driver,
                    context_key,
                    evidence,
                    support,
                    prior,
                    round(raw_score / denominator, 6) if denominator else 0.0,
                    rank,
                    FrontierState.ACCEPTED
                    if support >= minimum_support and denominator
                    else FrontierState.REVIEW,
                )
            )
        top = posteriors[0].driver_id if posteriors else None
        return DriverPosteriorReport(tuple(posteriors), top, _address(posteriors))


@dataclass(frozen=True, slots=True)
class SelectivePrediction:
    prediction_id: str
    context_key: str
    score: float
    uncertainty: float
    threshold: float
    abstained: bool
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SelectivePredictionReport:
    predictions: tuple[SelectivePrediction, ...]
    accepted_ids: tuple[str, ...]
    abstained_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SelectivePredictionAndAbstention:
    """Abstain when score is weak or uncertainty is larger than the margin."""

    def evaluate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_score: float = 0.6,
        maximum_uncertainty: float = 0.25,
    ) -> SelectivePredictionReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_score = _bounded(minimum_score, field="minimum_score")
        maximum_uncertainty = _float(maximum_uncertainty, field="maximum_uncertainty")
        predictions: list[SelectivePrediction] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"selective prediction {index}")
            prediction_id = (
                _text(row.get("prediction_id", row.get("id")), field="prediction_id")
                or f"prediction:{index}"
            )
            score = _bounded(row.get("score", 0.0), field="score")
            uncertainty = _float(row.get("uncertainty", 0.0), field="uncertainty")
            threshold = max(minimum_score, uncertainty * 2.0)
            issues: list[FrontierIssue] = []
            if score < threshold:
                issues.append(
                    FrontierIssue(
                        "selective_prediction_abstention",
                        "prediction score does not exceed uncertainty-aware threshold",
                        "review",
                        record_id=prediction_id,
                    )
                )
            abstained = bool(issues) or uncertainty > maximum_uncertainty
            if uncertainty > maximum_uncertainty:
                issues.append(
                    FrontierIssue(
                        "prediction_uncertainty_high",
                        "prediction uncertainty exceeds threshold",
                        "review",
                        record_id=prediction_id,
                    )
                )
            state = FrontierState.ACCEPTED if not abstained else FrontierState.REVIEW
            predictions.append(
                SelectivePrediction(
                    prediction_id,
                    context_key,
                    score,
                    uncertainty,
                    threshold,
                    abstained,
                    state,
                    tuple(issues),
                )
            )
        accepted = tuple(item.prediction_id for item in predictions if not item.abstained)
        abstained = tuple(item.prediction_id for item in predictions if item.abstained)
        return SelectivePredictionReport(
            tuple(predictions), accepted, abstained, _address(predictions)
        )


@dataclass(frozen=True, slots=True)
class CausalDossier:
    dossier_id: str
    context_key: str
    hypothesis_ids: tuple[str, ...]
    evidence_addresses: tuple[str, ...]
    top_hypothesis_id: str | None
    dossier_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CausalDossierPublisher:
    """Publish a causal dossier manifest without upgrading it to a conclusion."""

    def publish(
        self,
        *,
        dossier_id: str,
        context_key: str,
        hypothesis_ids: Sequence[str],
        evidence_addresses: Sequence[str],
        top_hypothesis_id: str | None,
    ) -> CausalDossier:
        dossier_id = require_non_empty(dossier_id, "dossier_id")
        context_key = require_non_empty(context_key, "context_key")
        hypotheses = tuple(
            sorted({require_non_empty(str(item), "hypothesis_id") for item in hypothesis_ids})
        )
        addresses = tuple(
            sorted(
                {require_non_empty(str(item), "evidence_address") for item in evidence_addresses}
            )
        )
        if not hypotheses or not addresses:
            raise ValidationError("hypothesis_ids and evidence_addresses must not be empty")
        if top_hypothesis_id is not None and top_hypothesis_id not in hypotheses:
            raise ValidationError("top_hypothesis_id must be one of hypothesis_ids")
        address = _address(
            {
                "dossier_id": dossier_id,
                "context_key": context_key,
                "hypothesis_ids": hypotheses,
                "evidence_addresses": addresses,
                "top_hypothesis_id": top_hypothesis_id,
            }
        )
        return CausalDossier(
            dossier_id,
            context_key,
            hypotheses,
            addresses,
            top_hypothesis_id,
            address,
            FrontierState.PUBLISHED,
        )


@dataclass(frozen=True, slots=True)
class FairnessStratum:
    stratum_id: str
    context_key: str
    group_value: str
    positives: int
    total: int
    rate: float
    parity_gap: float
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FairnessStratificationReport:
    strata: tuple[FairnessStratum, ...]
    maximum_parity_gap: float
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class SubgroupFairnessStratifier:
    """Compute subgroup rates and parity gaps without suppressing small strata."""

    def stratify(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        group_field: str = "group",
        maximum_parity_gap: float = 0.2,
    ) -> FairnessStratificationReport:
        context_key = require_non_empty(context_key, "context_key")
        maximum_parity_gap = _float(maximum_parity_gap, field="maximum_parity_gap")
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"fairness record {index}")
            group = _required_text(row.get(group_field), field=group_field)
            grouped.setdefault(group, []).append(row)
        rates = {
            group: sum(bool(row.get("positive", row.get("label", 0))) for row in rows)
            / max(1, len(rows))
            for group, rows in grouped.items()
        }
        baseline = max(rates.values(), default=0.0)
        strata: list[FairnessStratum] = []
        for group in sorted(grouped):
            rows = grouped[group]
            positives = sum(bool(row.get("positive", row.get("label", 0))) for row in rows)
            rate = rates[group]
            gap = round(abs(baseline - rate), 6)
            state = FrontierState.ACCEPTED if gap <= maximum_parity_gap else FrontierState.REVIEW
            strata.append(
                FairnessStratum(
                    f"{group_field}:{group}",
                    context_key,
                    group,
                    positives,
                    len(rows),
                    round(rate, 6),
                    gap,
                    state,
                )
            )
        gaps = max((item.parity_gap for item in strata), default=0.0)
        review = tuple(item.stratum_id for item in strata if item.state != FrontierState.ACCEPTED)
        return FairnessStratificationReport(tuple(strata), gaps, review, _address(strata))


@dataclass(frozen=True, slots=True)
class TransportabilityEstimate:
    analysis_id: str
    context_key: str
    source_features: tuple[str, ...]
    target_features: tuple[str, ...]
    shared_features: tuple[str, ...]
    overlap: float
    shift_score: float
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TransportabilityReport:
    estimates: tuple[TransportabilityEstimate, ...]
    transportable_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class TransportabilityEstimator:
    """Estimate source-to-target feature overlap and declared distribution shift."""

    def estimate(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        minimum_overlap: float = 0.75,
        maximum_shift: float = 0.25,
    ) -> TransportabilityReport:
        context_key = require_non_empty(context_key, "context_key")
        minimum_overlap = _bounded(minimum_overlap, field="minimum_overlap")
        maximum_shift = _float(maximum_shift, field="maximum_shift")
        estimates: list[TransportabilityEstimate] = []
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"transportability {index}")
            analysis_id = (
                _text(row.get("analysis_id", row.get("id")), field="analysis_id")
                or f"transport:{index}"
            )
            source = set(_tuple_text(row.get("source_features"), field="source_features"))
            target = set(_tuple_text(row.get("target_features"), field="target_features"))
            shared = tuple(sorted(source & target))
            overlap = len(shared) / max(1, len(target))
            shift = _float(row.get("shift_score", 0.0), field="shift_score")
            issues: list[FrontierIssue] = []
            if overlap < minimum_overlap:
                issues.append(
                    FrontierIssue(
                        "target_feature_gap",
                        "source and target feature support overlap is low",
                        "review",
                        record_id=analysis_id,
                    )
                )
            if shift > maximum_shift:
                issues.append(
                    FrontierIssue(
                        "distribution_shift_high",
                        "declared source-target shift exceeds threshold",
                        "review",
                        record_id=analysis_id,
                    )
                )
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            estimates.append(
                TransportabilityEstimate(
                    analysis_id,
                    context_key,
                    tuple(sorted(source)),
                    tuple(sorted(target)),
                    shared,
                    round(overlap, 6),
                    shift,
                    state,
                    tuple(issues),
                )
            )
        transportable = tuple(
            item.analysis_id for item in estimates if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.analysis_id for item in estimates if item.state != FrontierState.ACCEPTED
        )
        return TransportabilityReport(tuple(estimates), transportable, review, _address(estimates))


@dataclass(frozen=True, slots=True)
class FederatedSummary:
    feature_id: str
    context_key: str
    site_count: int
    total_count: int
    weighted_mean: float
    between_site_standard_deviation: float
    privacy_floor: int
    state: FrontierState
    issues: tuple[FrontierIssue, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class FederatedSummaryReport:
    summaries: tuple[FederatedSummary, ...]
    supported_ids: tuple[str, ...]
    review_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class FederatedSummaryAnalyzer:
    """Analyze site-level summaries without requiring raw cross-site records."""

    def analyze(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        context_key: str,
        privacy_floor: int = 5,
    ) -> FederatedSummaryReport:
        context_key = require_non_empty(context_key, "context_key")
        if privacy_floor < 1:
            raise ValidationError("privacy_floor must be positive")
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        for index, raw in enumerate(records, start=1):
            row = _mapping(raw, label=f"federated summary {index}")
            feature = _required_text(row.get("feature_id", row.get("id")), field="feature_id")
            grouped.setdefault(feature, []).append(row)
        summaries: list[FederatedSummary] = []
        for feature in sorted(grouped):
            rows = grouped[feature]
            counts = [int(row.get("count", 0)) for row in rows]
            means = [_float(row.get("mean"), field="mean") for row in rows]
            total = sum(counts)
            issues: list[FrontierIssue] = []
            if any(count < privacy_floor for count in counts):
                issues.append(
                    FrontierIssue(
                        "privacy_floor_violation",
                        "a federated site summary is below the privacy floor",
                        "blocking",
                        record_id=feature,
                    )
                )
            weighted = sum(mean * count for mean, count in zip(means, counts, strict=False)) / max(
                1, total
            )
            site_mean = sum(means) / max(1, len(means))
            spread = sqrt(sum((mean - site_mean) ** 2 for mean in means) / max(1, len(means) - 1))
            state = FrontierState.ACCEPTED if not issues else FrontierState.REVIEW
            summaries.append(
                FederatedSummary(
                    feature,
                    context_key,
                    len(rows),
                    total,
                    round(weighted, 6),
                    round(spread, 6),
                    privacy_floor,
                    state,
                    tuple(issues),
                )
            )
        supported = tuple(
            item.feature_id for item in summaries if item.state == FrontierState.ACCEPTED
        )
        review = tuple(
            item.feature_id for item in summaries if item.state != FrontierState.ACCEPTED
        )
        return FederatedSummaryReport(tuple(summaries), supported, review, _address(summaries))


@dataclass(frozen=True, slots=True)
class CohortDiscoveryBundle:
    bundle_id: str
    context_key: str
    feature_ids: tuple[str, ...]
    records_address: str
    bundle_address: str
    state: FrontierState

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class CohortDiscoveryPublisher:
    """Publish cohort-discovery summaries with aggregate-only source receipts."""

    def publish(
        self,
        records: Iterable[Mapping[str, Any]],
        *,
        bundle_id: str,
        context_key: str,
        analysis_ids: Sequence[str],
    ) -> CohortDiscoveryBundle:
        bundle_id = require_non_empty(bundle_id, "bundle_id")
        context_key = require_non_empty(context_key, "context_key")
        analyses = tuple(
            sorted({require_non_empty(str(item), "analysis_id") for item in analysis_ids})
        )
        normalized = tuple(dict(_mapping(row, label="cohort discovery")) for row in records)
        if not normalized or not analyses:
            raise ValidationError("cohort records and analysis_ids must not be empty")
        if any(_context(row, context_key) != context_key for row in normalized):
            raise ValidationError("cohort record context does not match bundle")
        feature_ids = tuple(
            sorted(
                {
                    _required_text(row.get("feature_id", row.get("id")), field="feature_id")
                    for row in normalized
                }
            )
        )
        records_address = _address(normalized)
        address = _address(
            {
                "bundle_id": bundle_id,
                "context_key": context_key,
                "feature_ids": feature_ids,
                "analysis_ids": analyses,
                "records_address": records_address,
            }
        )
        return CohortDiscoveryBundle(
            bundle_id, context_key, feature_ids, records_address, address, FrontierState.PUBLISHED
        )


def run_inference_frontier_operation(
    operation: str, payload: Mapping[str, Any], *, context_key: str | None = None
) -> Any:
    """Run a D09-D12 frontier operation from a JSON payload."""

    operation = require_non_empty(operation, "operation")
    data = _mapping(payload, label="payload")
    context = context_key or _text(data.get("context_key"), field="context_key")
    if operation == "model-ecdna-contacts":
        return EcDNARegulatoryContactModel().evaluate(
            data.get("records", ()),
            context_key=context,
            minimum_contact_score=_float(
                data.get("minimum_contact_score", 0.5), field="minimum_contact_score"
            ),
            minimum_sources=int(data.get("minimum_sources", 1)),
        )
    if operation == "estimate-compartment-switch":
        return CompartmentSwitchEstimator().estimate(
            data.get("records", ()),
            context_key=context,
            switch_threshold=_float(data.get("switch_threshold", 0.15), field="switch_threshold"),
        )
    if operation == "transport-topology-uncertainty":
        return TopologyUncertaintyTransportModel().transport(
            data.get("records", ()),
            context_key=context,
            minimum_effective_signal=_float(
                data.get("minimum_effective_signal", 0.3), field="minimum_effective_signal"
            ),
        )
    if operation == "publish-3d-evidence":
        return ThreeDEvidencePublisher().publish(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            assay_ids=_tuple_text(data.get("assay_ids"), field="assay_ids"),
        )
    if operation == "correct-link-dependence":
        return LinkEvidenceDependenceCorrector().correct(
            data.get("records", ()), context_key=context
        )
    if operation == "rank-target-genes":
        return TargetGeneRanker().rank(
            data.get("records", ()), context_key=context, weights=data.get("weights")
        )
    if operation == "calibrate-link-abstention":
        return LinkCalibrationAndAbstention().evaluate(
            data.get("records", ()),
            context_key=context,
            maximum_uncertainty=_float(
                data.get("maximum_uncertainty", 0.25), field="maximum_uncertainty"
            ),
            maximum_calibration_error=_float(
                data.get("maximum_calibration_error", 0.3), field="maximum_calibration_error"
            ),
        )
    if operation == "publish-link-evidence":
        return LinkEvidencePublisher().publish(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
        )
    if operation == "decompose-posterior":
        return PosteriorDecompositionEngine().decompose(
            data.get("records", ()), context_key=context
        )
    if operation == "infer-regulatory-driver-posterior":
        return RegulatoryDriverHypothesisPosterior().infer(
            data.get("records", ()),
            context_key=context,
            minimum_support=_float(data.get("minimum_support", 0.2), field="minimum_support"),
        )
    if operation == "selective-causal-prediction":
        return SelectivePredictionAndAbstention().evaluate(
            data.get("records", ()),
            context_key=context,
            minimum_score=_float(data.get("minimum_score", 0.6), field="minimum_score"),
            maximum_uncertainty=_float(
                data.get("maximum_uncertainty", 0.25), field="maximum_uncertainty"
            ),
        )
    if operation == "publish-causal-dossier":
        return CausalDossierPublisher().publish(
            dossier_id=_required_text(data.get("dossier_id"), field="dossier_id"),
            context_key=context,
            hypothesis_ids=_tuple_text(data.get("hypothesis_ids"), field="hypothesis_ids"),
            evidence_addresses=_tuple_text(
                data.get("evidence_addresses"), field="evidence_addresses"
            ),
            top_hypothesis_id=_text(data.get("top_hypothesis_id"), field="top_hypothesis_id")
            or None,
        )
    if operation == "stratify-subgroup-fairness":
        return SubgroupFairnessStratifier().stratify(
            data.get("records", ()),
            context_key=context,
            group_field=_text(data.get("group_field", "group"), field="group_field") or "group",
            maximum_parity_gap=_float(
                data.get("maximum_parity_gap", 0.2), field="maximum_parity_gap"
            ),
        )
    if operation == "estimate-transportability":
        return TransportabilityEstimator().estimate(
            data.get("records", ()),
            context_key=context,
            minimum_overlap=_float(data.get("minimum_overlap", 0.75), field="minimum_overlap"),
            maximum_shift=_float(data.get("maximum_shift", 0.25), field="maximum_shift"),
        )
    if operation == "analyze-federated-summary":
        return FederatedSummaryAnalyzer().analyze(
            data.get("records", ()),
            context_key=context,
            privacy_floor=int(data.get("privacy_floor", 5)),
        )
    if operation == "publish-cohort-discovery":
        return CohortDiscoveryPublisher().publish(
            data.get("records", ()),
            bundle_id=_required_text(data.get("bundle_id"), field="bundle_id"),
            context_key=context,
            analysis_ids=_tuple_text(data.get("analysis_ids"), field="analysis_ids"),
        )
    raise ValidationError(f"unknown inference frontier operation: {operation}")


INFERENCE_FRONTIER_OPERATIONS = (
    "model-ecdna-contacts",
    "estimate-compartment-switch",
    "transport-topology-uncertainty",
    "publish-3d-evidence",
    "correct-link-dependence",
    "rank-target-genes",
    "calibrate-link-abstention",
    "publish-link-evidence",
    "decompose-posterior",
    "infer-regulatory-driver-posterior",
    "selective-causal-prediction",
    "publish-causal-dossier",
    "stratify-subgroup-fairness",
    "estimate-transportability",
    "analyze-federated-summary",
    "publish-cohort-discovery",
)
