"""Adversarial coverage for the bounded dossier quality surface."""

from __future__ import annotations

import math
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import glio_noncode.quality as quality_module
from glio_noncode.errors import ValidationError
from glio_noncode.evidence import EvidenceGraph
from glio_noncode.models import (
    Dossier,
    EvidenceState,
    ReviewDecision,
    ReviewState,
    SupportLevel,
)
from glio_noncode.quality import (
    MAX_QUALITY_EVIDENCE_CLAIMS,
    MAX_QUALITY_METRICS,
    QUALITY_METRIC_IDS,
    QualityBand,
    QualityEvaluator,
    QualityLimits,
    QualityMetric,
    QualityReport,
    QualityThresholds,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash
from glio_noncode.validation import ContractValidator, ReleaseGate

from .helpers import fixture_manifest


def _rehash(dossier: Dossier) -> Dossier:
    pending = replace(dossier, content_address="pending")
    body = pending.to_dict()
    body.pop("content_address")
    return replace(pending, content_address=content_hash(body))


def _accepted_review(dossier: Dossier) -> ReviewDecision:
    return ReviewDecision(
        review_id="review-quality-hardening",
        case_id=dossier.case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=tuple(
            hypothesis.hypothesis_id for hypothesis in dossier.hypotheses
        ),
        rationale="Reviewed every hypothesis and evidence claim for research-only release.",
        checked_claim_ids=tuple(claim.evidence_id for claim in dossier.evidence),
    )


def _released_dossier(directory: str) -> Dossier:
    runtime = CaseRuntime(directory)
    draft = runtime.evaluate(fixture_manifest())
    return runtime.review(draft, _accepted_review(draft))


def _support_level(score: float) -> SupportLevel:
    if score >= 0.72:
        return SupportLevel.HIGH
    if score >= 0.45:
        return SupportLevel.MODERATE
    if score > 0.0:
        return SupportLevel.LOW
    return SupportLevel.UNKNOWN


def _with_active_negative(released: Dossier) -> Dossier:
    template = released.evidence[0]
    negative = replace(
        template,
        evidence_id="quality-active-negative",
        state=EvidenceState.MEASURED_NEGATIVE,
        score=1.0,
        summary="Measured negative evidence retained for quality review.",
        depends_on=(),
        supersedes=None,
    )
    evidence = released.evidence + (negative,)
    graph = EvidenceGraph()
    graph.extend(evidence)
    hypotheses = []
    for hypothesis in released.hypotheses:
        edges = []
        contains_negative = False
        for edge in hypothesis.edges:
            if edge.edge_id == negative.edge_id:
                aggregate = graph.aggregate(edge)
                edge = replace(
                    edge,
                    support=aggregate.score,
                    uncertainty=aggregate.uncertainty,
                    context_fit=aggregate.context_support,
                    support_level=_support_level(aggregate.score),
                    claim_ids=(
                        aggregate.supported_claim_ids
                        + aggregate.negative_claim_ids
                        + aggregate.missing_claim_ids
                    ),
                )
                contains_negative = True
            edges.append(edge)
        hypotheses.append(
            replace(
                hypothesis,
                edges=tuple(edges),
                negative_evidence=(
                    hypothesis.negative_evidence + (negative.evidence_id,)
                    if contains_negative
                    else hypothesis.negative_evidence
                ),
            )
        )
    assert released.review is not None
    review = replace(
        released.review,
        checked_claim_ids=released.review.checked_claim_ids + (negative.evidence_id,),
    )
    candidate = _rehash(
        replace(
            released,
            evidence=evidence,
            hypotheses=tuple(hypotheses),
            review=review,
        )
    )
    assert ContractValidator().validate_dossier(candidate).valid
    assert ReleaseGate().check(candidate).valid
    return candidate


def _with_equivalent_supersession(released: Dossier) -> Dossier:
    old = released.evidence[0]
    historical = replace(
        old,
        state=EvidenceState.MEASURED_NEGATIVE,
        score=0.0,
        summary="Historical negative evidence superseded by the active claim.",
    )
    active = replace(
        old,
        evidence_id="quality-replacement-supported",
        supersedes=old.evidence_id,
    )
    evidence = (historical,) + released.evidence[1:] + (active,)
    graph = EvidenceGraph()
    graph.extend(evidence)
    hypotheses = []
    for hypothesis in released.hypotheses:
        edges = []
        for edge in hypothesis.edges:
            if edge.edge_id == old.edge_id:
                aggregate = graph.aggregate(edge)
                edge = replace(
                    edge,
                    support=aggregate.score,
                    uncertainty=aggregate.uncertainty,
                    context_fit=aggregate.context_support,
                    support_level=_support_level(aggregate.score),
                    claim_ids=(
                        aggregate.supported_claim_ids
                        + aggregate.negative_claim_ids
                        + aggregate.missing_claim_ids
                    ),
                )
            edges.append(edge)
        hypotheses.append(replace(hypothesis, edges=tuple(edges)))
    assert released.review is not None
    review = replace(
        released.review,
        checked_claim_ids=released.review.checked_claim_ids + (active.evidence_id,),
    )
    candidate = _rehash(
        replace(
            released,
            evidence=evidence,
            hypotheses=tuple(hypotheses),
            review=review,
        )
    )
    assert ContractValidator().validate_dossier(candidate).valid
    assert ReleaseGate().check(candidate).valid
    return candidate


def _with_correlated_supported_fanout(released: Dossier) -> Dossier:
    original = next(claim for claim in released.evidence if claim.state is EvidenceState.SUPPORTED)
    clones = tuple(
        replace(
            original,
            evidence_id=f"quality-correlated-clone-{index:02d}",
            depends_on=(),
            supersedes=None,
        )
        for index in range(50)
    )
    evidence = released.evidence + clones
    graph = EvidenceGraph()
    graph.extend(evidence)
    hypotheses = []
    for hypothesis in released.hypotheses:
        edges = []
        for edge in hypothesis.edges:
            if edge.edge_id == original.edge_id:
                aggregate = graph.aggregate(edge)
                edge = replace(
                    edge,
                    support=aggregate.score,
                    uncertainty=aggregate.uncertainty,
                    context_fit=aggregate.context_support,
                    support_level=_support_level(aggregate.score),
                    claim_ids=(
                        aggregate.supported_claim_ids
                        + aggregate.negative_claim_ids
                        + aggregate.missing_claim_ids
                    ),
                )
            edges.append(edge)
        hypotheses.append(replace(hypothesis, edges=tuple(edges)))
    assert released.review is not None
    review = replace(
        released.review,
        checked_claim_ids=(
            released.review.checked_claim_ids + tuple(clone.evidence_id for clone in clones)
        ),
    )
    candidate = _rehash(
        replace(
            released,
            evidence=evidence,
            hypotheses=tuple(hypotheses),
            review=review,
        )
    )
    assert ContractValidator().validate_dossier(candidate).valid
    assert ReleaseGate().check(candidate).valid
    return candidate


def _with_correlated_negative_padding(released: Dossier) -> Dossier:
    original = next(
        claim
        for claim in released.evidence
        if claim.state in {EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY}
    )
    clones = tuple(
        replace(
            original,
            evidence_id=f"quality-negative-padding-{index}",
            payload={"documented": True},
            depends_on=(),
            supersedes=None,
        )
        for index in range(2)
    )
    evidence = released.evidence + clones
    graph = EvidenceGraph()
    graph.extend(evidence)
    hypotheses = []
    for hypothesis in released.hypotheses:
        edges = []
        affected = False
        for edge in hypothesis.edges:
            if edge.edge_id == original.edge_id:
                aggregate = graph.aggregate(edge)
                edge = replace(
                    edge,
                    support=aggregate.score,
                    uncertainty=aggregate.uncertainty,
                    context_fit=aggregate.context_support,
                    support_level=_support_level(aggregate.score),
                    claim_ids=(
                        aggregate.supported_claim_ids
                        + aggregate.negative_claim_ids
                        + aggregate.missing_claim_ids
                    ),
                )
                affected = True
            edges.append(edge)
        hypotheses.append(
            replace(
                hypothesis,
                edges=tuple(edges),
                negative_evidence=(
                    hypothesis.negative_evidence + tuple(clone.evidence_id for clone in clones)
                    if affected
                    else hypothesis.negative_evidence
                ),
            )
        )
    assert released.review is not None
    review = replace(
        released.review,
        checked_claim_ids=(
            released.review.checked_claim_ids + tuple(clone.evidence_id for clone in clones)
        ),
    )
    candidate = _rehash(
        replace(
            released,
            evidence=evidence,
            hypotheses=tuple(hypotheses),
            review=review,
        )
    )
    assert ContractValidator().validate_dossier(candidate).valid
    assert ReleaseGate().check(candidate).valid
    return candidate


def _metric(
    metric_id: str,
    *,
    value: float | None = 1.0,
    band: QualityBand = QualityBand.PASS,
) -> QualityMetric:
    targets = {
        "evidence_coverage": "higher is better",
        "context_specificity": "higher is better",
        "uncertainty_transparency": "higher is better",
        "review_burden": "lower is better",
        "negative_evidence_visibility": "higher is better",
    }
    rationales = {
        "evidence_coverage": "share of typed hypothesis edges with active supported evidence",
        "context_specificity": (
            "share of evidence-bearing typed edges whose active claims exactly match "
            "hypothesis context"
        ),
        "uncertainty_transparency": (
            "share of hypotheses carrying an explicit bounded uncertainty field"
        ),
        "review_burden": "number of candidates shown to a reviewer",
        "negative_evidence_visibility": (
            "share of negative-evidence edges whose active negative claims all retain documentation"
        ),
    }
    return QualityMetric(
        metric_id,
        value,
        targets.get(metric_id, "higher is better"),
        band,
        rationales.get(metric_id, f"rationale for {metric_id}"),
    )


def _complete_metrics() -> tuple[QualityMetric, ...]:
    return tuple(_metric(metric_id) for metric_id in QUALITY_METRIC_IDS)


def _report(
    metrics: tuple[QualityMetric, ...],
    release_ready: bool,
    limitations: tuple[str, ...] | None = None,
    *,
    release_gate_valid: bool = True,
    release_gate_issue_codes: tuple[str, ...] | None = None,
    thresholds: QualityThresholds | None = None,
) -> QualityReport:
    gate_codes = (
        (("release_status_required",) if not release_gate_valid else ())
        if release_gate_issue_codes is None
        else release_gate_issue_codes
    )
    sorted_gate_codes = tuple(sorted(gate_codes))
    if limitations is None:
        expected_limitations = [
            "These are internal quality signals, not external scientific validation.",
            (
                "Thresholds must be preregistered and evaluated on held-out data before claims "
                "are made."
            ),
        ]
        unknown = tuple(item.metric_id for item in metrics if item.band is QualityBand.UNKNOWN)
        failed = tuple(item.metric_id for item in metrics if item.band is QualityBand.FAIL)
        if unknown:
            expected_limitations.append(
                "Unknown required metrics block release readiness: " + ", ".join(unknown) + "."
            )
        if failed:
            expected_limitations.append(
                "Quality metrics below their failure thresholds block release readiness: "
                + ", ".join(failed)
                + "."
            )
        if not release_gate_valid:
            expected_limitations.append(
                "The authoritative release gate did not pass: " + ", ".join(sorted_gate_codes) + "."
            )
        elif gate_codes:
            expected_limitations.append(
                "Authoritative release gate warnings remain visible: "
                + ", ".join(sorted_gate_codes)
                + "."
            )
        limitations = tuple(expected_limitations)
    return QualityReport(
        dossier_address="sha256:" + "1" * 64,
        thresholds=QualityThresholds() if thresholds is None else thresholds,
        release_gate_valid=release_gate_valid,
        release_gate_issue_codes=gate_codes,
        release_policy_version="research-boundary-2026.09",
        metrics=metrics,
        release_ready=release_ready,
        limitations=limitations,
    )


class QualityContractTests(unittest.TestCase):
    def test_metric_rejects_boolean_nonfinite_and_inconsistent_unknown_values(self) -> None:
        for value in (True, False, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                QualityMetric("metric", value, "higher is better", QualityBand.PASS, "reason")
        with self.assertRaisesRegex(ValidationError, "without a value"):
            QualityMetric("metric", None, "higher is better", QualityBand.PASS, "reason")
        with self.assertRaisesRegex(ValidationError, "must not carry"):
            QualityMetric("metric", 1.0, "higher is better", QualityBand.UNKNOWN, "reason")

    def test_signed_zero_is_normalized_before_canonical_serialization(self) -> None:
        metric = QualityMetric(
            "metric",
            -0.0,
            "higher is better",
            QualityBand.PASS,
            "reason",
        )
        thresholds = QualityThresholds(evidence_coverage=-0.0)

        self.assertEqual(math.copysign(1.0, metric.value), 1.0)  # type: ignore[arg-type]
        self.assertEqual(math.copysign(1.0, thresholds.evidence_coverage), 1.0)
        self.assertEqual(
            thresholds.content_address,
            QualityThresholds(evidence_coverage=0.0).content_address,
        )

    def test_metric_identity_target_band_and_text_are_exact(self) -> None:
        invalid_values: tuple[tuple[object, object, object], ...] = (
            ("Upper", "higher is better", QualityBand.PASS),
            ("space separated", "higher is better", QualityBand.PASS),
            ("metric", "maximize", QualityBand.PASS),
            ("metric", "higher is better", "pass"),
        )
        for metric_id, target, band in invalid_values:
            with self.subTest(metric_id=metric_id, target=target, band=band):
                with self.assertRaises(ValidationError):
                    QualityMetric(
                        metric_id,  # type: ignore[arg-type]
                        1.0,
                        target,  # type: ignore[arg-type]
                        band,  # type: ignore[arg-type]
                        "reason",
                    )
        with self.assertRaises(ValidationError):
            QualityMetric("metric", 1.0, "higher is better", QualityBand.PASS, "x" * 4_097)

    def test_metric_and_report_parsers_reject_non_utf8_unicode_as_validation_errors(self) -> None:
        metric_record = _metric("evidence_coverage").to_dict()
        metric_record["rationale"] = "\ud800"
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            QualityMetric.from_dict(metric_record)

        report_record = _report(_complete_metrics(), True).to_dict()
        metrics = report_record["metrics"]
        self.assertIsInstance(metrics, list)
        metrics[0]["rationale"] = "\ud800"  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "valid UTF-8"):
            QualityReport.from_dict(report_record)

    def test_report_requires_exact_containers_boolean_and_unique_metric_ids(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must be a tuple"):
            QualityReport(
                "sha256:" + "1" * 64,
                QualityThresholds(),
                True,
                (),
                "research-boundary-2026.09",
                list(_complete_metrics()),  # type: ignore[arg-type]
                False,
                (),
            )
        with self.assertRaisesRegex(ValidationError, "must be a boolean"):
            QualityReport(
                "sha256:" + "1" * 64,
                QualityThresholds(),
                True,
                (),
                "research-boundary-2026.09",
                _complete_metrics(),
                0,  # type: ignore[arg-type]
                (),
            )
        with self.assertRaisesRegex(ValidationError, "must be a tuple"):
            QualityReport(
                "sha256:" + "1" * 64,
                QualityThresholds(),
                True,
                (),
                "research-boundary-2026.09",
                _complete_metrics(),
                True,
                [],  # type: ignore[arg-type]
            )
        with self.assertRaisesRegex(ValidationError, "must be unique"):
            _report(_complete_metrics() + (_complete_metrics()[0],), False, ())

    def test_gate_issue_codes_are_bounded_identifiers_sorted_and_unique(self) -> None:
        report = _report(
            _complete_metrics(),
            True,
            release_gate_issue_codes=("z_warning", "a_warning"),
        )
        self.assertEqual(report.release_gate_issue_codes, ("a_warning", "z_warning"))
        with self.assertRaisesRegex(ValidationError, "must be unique"):
            _report(
                _complete_metrics(),
                True,
                (),
                release_gate_issue_codes=("same_warning", "same_warning"),
            )
        with self.assertRaisesRegex(ValidationError, "lowercase ASCII identifier"):
            _report(
                _complete_metrics(),
                True,
                (),
                release_gate_issue_codes=("Bad-Warning",),
            )

    def test_ready_report_requires_every_known_metric_and_no_unknown_or_failure(self) -> None:
        with self.assertRaisesRegex(ValidationError, "identities must be exact"):
            _report((_metric("custom"),), False, ())
        unknown = tuple(
            _metric(metric_id, value=None, band=QualityBand.UNKNOWN)
            if metric_id == "context_specificity"
            else _metric(metric_id)
            for metric_id in QUALITY_METRIC_IDS
        )
        with self.assertRaisesRegex(ValidationError, "does not match"):
            _report(unknown, True, ())
        failed = tuple(
            _metric(metric_id, value=0.0, band=QualityBand.FAIL)
            if metric_id == "evidence_coverage"
            else _metric(metric_id)
            for metric_id in QUALITY_METRIC_IDS
        )
        with self.assertRaisesRegex(ValidationError, "does not match"):
            _report(failed, True, ())
        with self.assertRaisesRegex(ValidationError, "does not match"):
            _report(_complete_metrics(), True, (), release_gate_valid=False)
        with self.assertRaisesRegex(ValidationError, "does not match"):
            _report(_complete_metrics(), False)
        with self.assertRaisesRegex(ValidationError, "canonical decision summary"):
            _report(_complete_metrics(), True, ())

    def test_report_recomputes_metric_semantics_from_embedded_thresholds(self) -> None:
        baseline = _complete_metrics()
        forged_values = (
            replace(baseline[0], value=999.0),
            replace(baseline[0], target="lower is better"),
            replace(baseline[0], rationale="arbitrary rationale"),
            replace(baseline[0], band=QualityBand.FAIL),
        )
        expected_messages = ("proportion", "target", "rationale", "band")
        for forged, expected in zip(forged_values, expected_messages, strict=True):
            with self.subTest(expected=expected), self.assertRaisesRegex(ValidationError, expected):
                _report((forged,) + baseline[1:], False, ())

    def test_report_rejects_noncanonical_release_policy_version(self) -> None:
        with self.assertRaisesRegex(ValidationError, "release_policy_version is not canonical"):
            QualityReport(
                dossier_address="sha256:" + "1" * 64,
                thresholds=QualityThresholds(),
                release_gate_valid=True,
                release_gate_issue_codes=(),
                release_policy_version="invented-policy",
                metrics=_complete_metrics(),
                release_ready=True,
                limitations=("bounded",),
            )

    def test_report_order_address_and_round_trip_are_deterministic(self) -> None:
        report = _report(tuple(reversed(_complete_metrics())), True)
        second = _report(_complete_metrics(), True)

        self.assertEqual(tuple(item.metric_id for item in report.metrics), QUALITY_METRIC_IDS)
        self.assertEqual(report.content_address, second.content_address)
        self.assertEqual(QualityReport.from_dict(report.to_dict()), report)

    def test_report_address_binds_subject_threshold_snapshot_and_gate_decision(self) -> None:
        baseline = _report(_complete_metrics(), True)
        other_subject = QualityReport(
            dossier_address="sha256:" + "2" * 64,
            thresholds=QualityThresholds(),
            release_gate_valid=True,
            release_gate_issue_codes=(),
            release_policy_version="research-boundary-2026.09",
            metrics=_complete_metrics(),
            release_ready=True,
            limitations=baseline.limitations,
        )
        other_thresholds = _report(
            _complete_metrics(),
            True,
            thresholds=QualityThresholds(evidence_coverage=0.80),
        )
        other_gate = _report(
            _complete_metrics(),
            False,
            release_gate_valid=False,
        )

        self.assertNotEqual(baseline.content_address, other_subject.content_address)
        self.assertNotEqual(baseline.content_address, other_thresholds.content_address)
        self.assertNotEqual(baseline.content_address, other_gate.content_address)

    def test_report_parser_rejects_extra_fields_integer_values_and_address_tampering(self) -> None:
        report = _report(_complete_metrics(), True)
        extra = report.to_dict() | {"unexpected": True}
        with self.assertRaisesRegex(ValidationError, "fields must be exact"):
            QualityReport.from_dict(extra)

        integer_value = report.to_dict()
        metrics = integer_value["metrics"]
        self.assertIsInstance(metrics, list)
        metrics[0]["value"] = 1  # type: ignore[index]
        with self.assertRaisesRegex(ValidationError, "must be a float"):
            QualityReport.from_dict(integer_value)

        bad_address = report.to_dict()
        bad_address["content_address"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValidationError, "does not match"):
            QualityReport.from_dict(bad_address)

        oversized = report.to_dict()
        oversized["metrics"] = oversized["metrics"] * (MAX_QUALITY_METRICS + 1)  # type: ignore[operator]
        with self.assertRaisesRegex(ValidationError, "cardinality ceiling"):
            QualityReport.from_dict(oversized)

    def test_report_detects_post_construction_mutation(self) -> None:
        report = _report(_complete_metrics(), True)
        object.__setattr__(report.metrics[0], "value", 0.5)
        with self.assertRaisesRegex(ValidationError, "band|content_address"):
            report.to_dict()

    def test_report_cardinality_and_text_are_bounded(self) -> None:
        metrics = tuple(_metric(f"metric_{index}") for index in range(MAX_QUALITY_METRICS + 1))
        with self.assertRaisesRegex(ValidationError, "maximum"):
            _report(metrics, False, ())
        with self.assertRaisesRegex(ValidationError, "must be unique"):
            _report(_complete_metrics(), True, ("same", "same"))


class QualityConfigurationTests(unittest.TestCase):
    def test_limits_are_downward_only_and_reject_booleans(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must be an integer"):
            QualityLimits(max_metrics=True)
        with self.assertRaisesRegex(ValidationError, "must be positive"):
            QualityLimits(max_metrics=0)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            QualityLimits(max_metrics=MAX_QUALITY_METRICS + 1)
        with self.assertRaisesRegex(ValidationError, "safety ceiling"):
            QualityLimits(max_evidence_claims=MAX_QUALITY_EVIDENCE_CLAIMS + 1)

    def test_public_ceiling_rebinding_cannot_expand_the_hard_limit(self) -> None:
        with patch.object(quality_module, "MAX_QUALITY_METRICS", 10**9):
            with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                QualityLimits(max_metrics=MAX_QUALITY_METRICS + 1)

    def test_mutated_or_replaced_evaluator_configuration_fails_closed(self) -> None:
        evaluator = QualityEvaluator()
        object.__setattr__(evaluator.limits, "max_metrics", 10**9)
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                evaluator.evaluate(dossier)

        evaluator = QualityEvaluator()
        evaluator.thresholds = object()  # type: ignore[assignment]
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            with self.assertRaisesRegex(ValidationError, "exact QualityThresholds"):
                evaluator.evaluate(dossier)

    def test_thresholds_reject_booleans_nonfinite_and_out_of_range_values(self) -> None:
        invalid: tuple[dict[str, object], ...] = (
            {"evidence_coverage": True},
            {"context_specificity": float("nan")},
            {"uncertainty_transparency": 1.01},
            {"review_burden": 0.0},
            {"higher_watch_fraction": 0.0},
            {"lower_watch_multiplier": 0.99},
        )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(ValidationError):
                QualityThresholds(**values)  # type: ignore[arg-type]

    def test_threshold_snapshot_round_trips_and_detects_mutation(self) -> None:
        thresholds = QualityThresholds(context_specificity=0.8)
        self.assertEqual(QualityThresholds.from_dict(thresholds.to_dict()), thresholds)

        object.__setattr__(thresholds, "context_specificity", 0.7)
        with self.assertRaisesRegex(ValidationError, "content_address"):
            thresholds.to_dict()

        forged_address = QualityThresholds()
        object.__setattr__(forged_address, "content_address", "sha256:" + "0" * 64)
        with self.assertRaisesRegex(ValidationError, "content_address"):
            forged_address.to_dict()

    def test_stricter_preregistered_threshold_changes_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = _released_dossier(directory)
            report = QualityEvaluator(thresholds=QualityThresholds(review_burden=0.5)).evaluate(
                dossier
            )

        burden = next(item for item in report.metrics if item.metric_id == "review_burden")
        self.assertIs(burden.band, QualityBand.FAIL)
        self.assertFalse(report.release_ready)

    def test_configured_work_and_output_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            with self.assertRaisesRegex(ValidationError, "validation_limit_exceeded"):
                QualityEvaluator(limits=QualityLimits(max_evidence_claims=1)).evaluate(dossier)
            with self.assertRaisesRegex(ValidationError, "metric slots"):
                QualityEvaluator(limits=QualityLimits(max_metrics=4)).evaluate(dossier)
            with self.assertRaisesRegex(ValidationError, "characters"):
                QualityEvaluator(limits=QualityLimits(max_text_characters=20)).evaluate(dossier)

    def test_gate_code_output_cap_does_not_truncate_authoritative_gate_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = _with_active_negative(_released_dossier(directory))
        policy_violations = _rehash(
            replace(
                dossier,
                warnings=(
                    "diagnosis",
                    "treatment recommendation",
                    "pathogenicity claim",
                ),
            )
        )

        default_report = QualityEvaluator().evaluate(policy_violations)
        capped_report = QualityEvaluator(limits=QualityLimits(max_gate_issue_codes=1)).evaluate(
            policy_violations
        )

        self.assertFalse(default_report.release_gate_valid)
        self.assertEqual(default_report.release_gate_issue_codes, ("policy_violation",))
        self.assertEqual(capped_report.to_dict(), default_report.to_dict())
        self.assertTrue(capped_report.verify(policy_violations))

        with tempfile.TemporaryDirectory() as directory:
            draft = CaseRuntime(directory).evaluate(fixture_manifest())
        draft_with_policy_violation = _rehash(replace(draft, warnings=("diagnosis",)))
        with self.assertRaisesRegex(ValidationError, "configured maximum"):
            QualityEvaluator(limits=QualityLimits(max_gate_issue_codes=1)).evaluate(
                draft_with_policy_violation
            )


class QualityEvaluationTests(unittest.TestCase):
    def test_draft_is_measurable_but_never_release_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            report = QualityEvaluator().evaluate(dossier)

        self.assertEqual(tuple(item.metric_id for item in report.metrics), QUALITY_METRIC_IDS)
        self.assertEqual(sum(item.value is not None for item in report.metrics), 4)
        self.assertFalse(report.release_ready)
        self.assertFalse(report.release_gate_valid)
        self.assertTrue(any("release_status_required" in item for item in report.limitations))

    def test_complete_released_dossier_can_be_quality_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = _with_active_negative(_released_dossier(directory))
            report = QualityEvaluator().evaluate(dossier)

        self.assertTrue(dossier.is_releasable)
        self.assertTrue(report.release_gate_valid)
        self.assertEqual(report.dossier_address, dossier.content_address)
        self.assertEqual(report.thresholds, QualityThresholds())
        self.assertEqual(report.release_policy_version, "research-boundary-2026.09")
        self.assertTrue(report.release_ready)
        self.assertTrue(
            all(item.band in {QualityBand.PASS, QualityBand.WATCH} for item in report.metrics)
        )

    def test_absent_negative_evidence_is_unknown_instead_of_vacuously_passing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = _released_dossier(directory)
            report = QualityEvaluator().evaluate(dossier)

        negative = next(
            item for item in report.metrics if item.metric_id == "negative_evidence_visibility"
        )
        self.assertIsNone(negative.value)
        self.assertIs(negative.band, QualityBand.UNKNOWN)
        self.assertTrue(report.release_gate_valid)
        self.assertFalse(report.release_ready)

    def test_incomplete_released_review_is_rejected_before_quality_claims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            released = _released_dossier(directory)
        self.assertIsNotNone(released.review)
        assert released.review is not None
        partial = replace(
            released.review,
            checked_claim_ids=released.review.checked_claim_ids[:-1],
        )
        incomplete = _rehash(replace(released, review=partial))

        self.assertFalse(incomplete.is_releasable)
        with self.assertRaisesRegex(ValidationError, "incomplete_claim_review"):
            QualityEvaluator().evaluate(incomplete)

    def test_structurally_invalid_dossier_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
        duplicated = _rehash(replace(dossier, evidence=dossier.evidence + (dossier.evidence[0],)))

        with self.assertRaisesRegex(ValidationError, "duplicate_evidence_id"):
            QualityEvaluator().evaluate(duplicated)

    def test_untrusted_payload_context_score_cannot_change_typed_context_metric(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            released = _with_active_negative(_released_dossier(directory))
        baseline = QualityEvaluator().evaluate(released)
        claim = released.evidence[0]
        changed_claim = replace(claim, payload={**claim.payload, "context_match": {"score": True}})
        changed = _rehash(replace(released, evidence=(changed_claim,) + released.evidence[1:]))

        report = QualityEvaluator().evaluate(changed)
        context_metric = next(
            item for item in report.metrics if item.metric_id == "context_specificity"
        )
        baseline_context = next(
            item for item in baseline.metrics if item.metric_id == "context_specificity"
        )
        self.assertEqual(context_metric, baseline_context)
        self.assertEqual(context_metric.value, 1.0)
        self.assertTrue(report.release_ready)

    def test_orphan_and_superseded_ledger_claims_do_not_change_active_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            released = _released_dossier(directory)
        orphan = replace(
            released.evidence[0],
            evidence_id="quality-orphan-supported",
            edge_id="quality-orphan-edge",
            depends_on=(),
            supersedes=None,
        )
        assert released.review is not None
        orphan_dossier = _rehash(
            replace(
                released,
                evidence=released.evidence + (orphan,),
                review=replace(
                    released.review,
                    checked_claim_ids=released.review.checked_claim_ids + (orphan.evidence_id,),
                ),
            )
        )
        superseded = _with_equivalent_supersession(released)
        self.assertTrue(ContractValidator().validate_dossier(orphan_dossier).valid)
        self.assertTrue(ReleaseGate().check(orphan_dossier).valid)

        baseline = QualityEvaluator().evaluate(released)
        orphan_report = QualityEvaluator().evaluate(orphan_dossier)
        superseded_report = QualityEvaluator().evaluate(superseded)
        self.assertEqual(baseline.metrics, orphan_report.metrics)
        self.assertEqual(baseline.metrics, superseded_report.metrics)
        self.assertEqual(baseline.release_ready, orphan_report.release_ready)
        self.assertEqual(baseline.release_ready, superseded_report.release_ready)

    def test_correlated_same_channel_claim_fanout_does_not_inflate_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            released = _with_active_negative(_released_dossier(directory))
        fanout = _with_correlated_supported_fanout(released)

        baseline = QualityEvaluator().evaluate(released)
        fanout_report = QualityEvaluator().evaluate(fanout)
        self.assertGreater(len(fanout.evidence), len(released.evidence))
        self.assertEqual(baseline.metrics, fanout_report.metrics)
        self.assertEqual(baseline.release_ready, fanout_report.release_ready)
        self.assertNotEqual(baseline.content_address, fanout_report.content_address)

    def test_documented_negative_padding_cannot_hide_an_undocumented_negative(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            released = _with_active_negative(_released_dossier(directory))
        negative_index = next(
            index
            for index, claim in enumerate(released.evidence)
            if claim.state in {EvidenceState.MEASURED_NEGATIVE, EvidenceState.CONTRADICTORY}
        )
        negative = replace(released.evidence[negative_index], payload={})
        evidence = list(released.evidence)
        evidence[negative_index] = negative
        undocumented = _rehash(replace(released, evidence=tuple(evidence)))
        self.assertTrue(ContractValidator().validate_dossier(undocumented).valid)
        self.assertTrue(ReleaseGate().check(undocumented).valid)
        padded = _with_correlated_negative_padding(undocumented)

        baseline = QualityEvaluator().evaluate(undocumented)
        padded_report = QualityEvaluator().evaluate(padded)
        visibility = next(
            metric
            for metric in baseline.metrics
            if metric.metric_id == "negative_evidence_visibility"
        )
        self.assertEqual(visibility.value, 0.0)
        self.assertIs(visibility.band, QualityBand.FAIL)
        self.assertEqual(baseline.metrics, padded_report.metrics)
        self.assertFalse(padded_report.release_ready)

    def test_exact_dossier_type_is_required(self) -> None:
        with self.assertRaisesRegex(ValidationError, "exact Dossier"):
            QualityEvaluator().evaluate(object())  # type: ignore[arg-type]

    def test_repeated_evaluation_has_identical_order_and_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            first = QualityEvaluator().evaluate(dossier)
            second = QualityEvaluator().evaluate(dossier)

        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.content_address, second.content_address)
        self.assertTrue(first.verify(dossier))

    def test_self_addressed_report_is_only_trusted_after_subject_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = _with_active_negative(_released_dossier(directory))

        forged_metrics = (
            _metric("evidence_coverage", value=0.75),
            *_complete_metrics()[1:],
        )
        forged = replace(
            _report(forged_metrics, True),
            dossier_address=dossier.content_address,
        )
        expected = QualityEvaluator().evaluate(dossier)

        self.assertEqual(QualityReport.from_dict(forged.to_dict()), forged)
        self.assertNotEqual(forged.metrics, expected.metrics)
        self.assertFalse(forged.verify(dossier))
        self.assertTrue(expected.verify(dossier))

        object.__setattr__(expected, "content_address", "sha256:" + "0" * 64)
        with patch.object(QualityEvaluator, "evaluate", side_effect=AssertionError) as evaluate:
            self.assertFalse(expected.verify(dossier))
            evaluate.assert_not_called()

    def test_evaluation_address_changes_for_subject_or_threshold_even_when_bands_do_not(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
        changed_subject = _rehash(
            replace(dossier, warnings=dossier.warnings + ("Distinct subject-bound warning.",))
        )
        baseline = QualityEvaluator().evaluate(dossier)
        subject_report = QualityEvaluator().evaluate(changed_subject)
        threshold_report = QualityEvaluator(
            thresholds=QualityThresholds(evidence_coverage=0.8)
        ).evaluate(dossier)

        self.assertEqual(
            tuple(item.band for item in baseline.metrics),
            tuple(item.band for item in subject_report.metrics),
        )
        self.assertEqual(
            tuple(item.band for item in baseline.metrics),
            tuple(item.band for item in threshold_report.metrics),
        )
        self.assertNotEqual(baseline.content_address, subject_report.content_address)
        self.assertNotEqual(baseline.content_address, threshold_report.content_address)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
