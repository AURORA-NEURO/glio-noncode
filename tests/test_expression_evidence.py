from __future__ import annotations

import json
import math
import unittest
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.expression_evidence import (
    MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
    MAX_ALLELIC_BATCH_OBSERVATIONS,
    MAX_EXACT_BINOMIAL_TRIALS,
    MAX_EXPRESSION_BATCH_OBSERVATIONS,
    AllelicCountBatch,
    AllelicCountObservation,
    AllelicDirection,
    AllelicImbalanceAnalyzer,
    AllelicImbalancePolicy,
    DispersionMethod,
    ExpectedFractionMethod,
    ExpressionBatch,
    ExpressionDirection,
    ExpressionObservation,
    ExpressionOutlierResult,
    ExpressionScale,
    PhaseStatus,
    PredictedRegulatoryEffect,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAConsequenceIntegrator,
    RNAEvidenceState,
    RobustExpressionOutlierAnalyzer,
    benjamini_hochberg,
    exact_two_sided_binomial_pvalue,
    expression_evidence_capabilities,
    expression_evidence_schema,
)

CONTEXT = "GRCh38|diffuse_glioma|adult|malignant|core|pre"


def expression(
    sample_key: str,
    value: float,
    *,
    feature_id: str = "gene:SOX2",
    scale: ExpressionScale | str = ExpressionScale.LOG2_TPM,
    context_key: str = CONTEXT,
    source_id: str = "rna-reference",
) -> ExpressionObservation:
    return ExpressionObservation(
        feature_id=feature_id,
        sample_key=sample_key,
        value=value,
        scale=scale,
        context_key=context_key,
        source_id=source_id,
        source_version="2026-08",
    )


def reference_batch(values: list[float]) -> ExpressionBatch:
    return ExpressionBatch.from_observations(
        expression(f"reference:{index}", value) for index, value in enumerate(values)
    )


def allelic(
    ref_count: int,
    alt_count: int,
    *,
    sample_key: str = "tumour:opaque-01",
    phase: PhaseStatus | str = PhaseStatus.PHASED,
    expected_alt_fraction: float | None = 0.5,
    mapping_bias: float | None = None,
    mapping_bias_flag: bool = False,
    context_key: str = CONTEXT,
    other_count: int = 0,
    ref_copy_number: float | None = None,
    alt_copy_number: float | None = None,
    purity: float | None = None,
) -> AllelicCountObservation:
    return AllelicCountObservation(
        feature_id="gene:SOX2",
        variant_id="variant:chr3-181711925-A-G",
        sample_key=sample_key,
        ref_count=ref_count,
        alt_count=alt_count,
        other_count=other_count,
        phase=phase,
        context_key=context_key,
        source_id="rna-ase",
        source_version="pipeline-4",
        expected_alt_fraction=expected_alt_fraction,
        ref_copy_number=ref_copy_number,
        alt_copy_number=alt_copy_number,
        purity=purity,
        mapping_bias=mapping_bias,
        mapping_bias_flag=mapping_bias_flag,
    )


class ExpressionContractTests(unittest.TestCase):
    def test_observation_and_batch_round_trip_canonically(self) -> None:
        first = expression("reference:1", 2.5)
        self.assertEqual(ExpressionObservation.from_json(first.to_json()), first)
        batch = ExpressionBatch((first, expression("reference:2", 3.0)))
        rebuilt = ExpressionBatch.from_mapping(batch.to_dict())
        self.assertEqual(rebuilt, batch)
        self.assertEqual(rebuilt.content_address, batch.content_address)
        self.assertEqual(rebuilt.to_json(), batch.to_json())

    def test_row_order_does_not_change_batch_address(self) -> None:
        rows = [expression("reference:2", 3.0), expression("reference:1", 2.5)]
        self.assertEqual(
            ExpressionBatch(tuple(rows)).content_address,
            ExpressionBatch(tuple(reversed(rows))).content_address,
        )
        self.assertEqual(
            ExpressionBatch(tuple(rows)).to_json(),
            ExpressionBatch(tuple(reversed(rows))).to_json(),
        )

    def test_mixed_scale_and_context_batches_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "mix scales"):
            ExpressionBatch((
                expression("reference:1", 1.0),
                expression("reference:2", 2.0, scale=ExpressionScale.TPM),
            ))
        with self.assertRaisesRegex(ValidationError, "mix contexts"):
            ExpressionBatch((
                expression("reference:1", 1.0),
                expression("reference:2", 2.0, context_key="foreign-context"),
            ))

    def test_nonfinite_values_and_invalid_keys_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaisesRegex(ValidationError, "finite"):
                expression("reference:1", value)
        with self.assertRaisesRegex(ValidationError, "sample_key"):
            expression("direct patient name", 1.0)
        with self.assertRaisesRegex(ValidationError, "source_id"):
            expression("reference:1", 1.0, source_id="bad source")

    def test_duplicate_feature_sample_key_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "duplicate"):
            ExpressionBatch((
                expression("reference:1", 1.0),
                expression("reference:1", 2.0),
            ))


class BatchBoundaryTests(unittest.TestCase):
    def test_exact_global_batch_limits_accept_one_shot_iterables(self) -> None:
        expression_batch = ExpressionBatch.from_observations(
            expression(f"reference:{index}", float(index % 101))
            for index in range(MAX_EXPRESSION_BATCH_OBSERVATIONS)
        )
        self.assertEqual(
            len(expression_batch.observations),
            MAX_EXPRESSION_BATCH_OBSERVATIONS,
        )

        allelic_batch = AllelicCountBatch.from_observations(
            allelic(10, 10, sample_key=f"tumour:{index}")
            for index in range(MAX_ALLELIC_BATCH_OBSERVATIONS)
        )
        self.assertEqual(
            len(allelic_batch.observations),
            MAX_ALLELIC_BATCH_OBSERVATIONS,
        )

    def test_endless_iterables_stop_after_limit_plus_one(self) -> None:
        expression_reads = 0

        def endless_expression_rows():
            nonlocal expression_reads
            while True:
                expression_reads += 1
                yield object()

        with self.assertRaisesRegex(
            ValidationError,
            rf"maximum of {MAX_EXPRESSION_BATCH_OBSERVATIONS} observations",
        ):
            ExpressionBatch(endless_expression_rows())  # type: ignore[arg-type]
        self.assertEqual(
            expression_reads,
            MAX_EXPRESSION_BATCH_OBSERVATIONS + 1,
        )

        allelic_reads = 0

        def endless_allelic_rows():
            nonlocal allelic_reads
            while True:
                allelic_reads += 1
                yield object()

        with self.assertRaisesRegex(
            ValidationError,
            rf"maximum of {MAX_ALLELIC_BATCH_OBSERVATIONS} observations",
        ):
            AllelicCountBatch(endless_allelic_rows())  # type: ignore[arg-type]
        self.assertEqual(allelic_reads, MAX_ALLELIC_BATCH_OBSERVATIONS + 1)

    def test_mapping_paths_check_bounds_before_materializing_rows(self) -> None:
        with self.assertRaisesRegex(
            ValidationError,
            rf"maximum of {MAX_EXPRESSION_BATCH_OBSERVATIONS} observations",
        ):
            ExpressionBatch.from_mapping(
                {"observations": [{}] * (MAX_EXPRESSION_BATCH_OBSERVATIONS + 1)}
            )
        with self.assertRaisesRegex(
            ValidationError,
            rf"maximum of {MAX_ALLELIC_BATCH_OBSERVATIONS} observations",
        ):
            AllelicCountBatch.from_mapping(
                {"observations": [{}] * (MAX_ALLELIC_BATCH_OBSERVATIONS + 1)}
            )

    def test_containers_items_and_duplicate_identities_fail_closed(self) -> None:
        invalid_containers = ("rows", b"rows", bytearray(b"rows"), {"row": 1}, 1)
        for value in invalid_containers:
            with self.subTest(batch="expression", value=type(value).__name__):
                with self.assertRaisesRegex(ValidationError, "iterable of observation"):
                    ExpressionBatch(value)  # type: ignore[arg-type]
            with self.subTest(batch="allelic", value=type(value).__name__):
                with self.assertRaisesRegex(ValidationError, "iterable of observation"):
                    AllelicCountBatch(value)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValidationError, "ExpressionObservation objects"):
            ExpressionBatch((object(),))  # type: ignore[arg-type]
        with self.assertRaisesRegex(ValidationError, "AllelicCountObservation objects"):
            AllelicCountBatch((object(),))  # type: ignore[arg-type]

        expression_row = expression("reference:duplicate", 1.0)
        with self.assertRaisesRegex(ValidationError, "duplicate feature/sample"):
            ExpressionBatch((expression_row, expression_row))
        allelic_row = allelic(10, 10)
        with self.assertRaisesRegex(ValidationError, "duplicate feature/variant/sample"):
            AllelicCountBatch((allelic_row, allelic_row))

    def test_bounded_batches_remain_analyzer_and_integrator_compatible(self) -> None:
        expression_result = RobustExpressionOutlierAnalyzer().analyze(
            expression("tumour:private", 20.0, source_id="matched-tumour"),
            reference_batch([1, 2, 3, 4, 5, 6, 7]),
        )
        allelic_result = AllelicImbalanceAnalyzer().analyze_batch(
            AllelicCountBatch((allelic(20, 80),))
        )[0]
        prediction = PredictedRegulatoryEffect(
            prediction_id="prediction:bounded-batches",
            variant_id="variant:chr3-181711925-A-G",
            feature_id="gene:SOX2",
            direction=RegulatoryDirection.GAIN,
            context_key=CONTEXT,
            source_id="sequence-model",
        )
        result = RNAConsequenceIntegrator().integrate(
            prediction,
            expression=expression_result,
            allelic=allelic_result,
        )
        self.assertEqual(result.state, RNAEvidenceState.SUPPORTED)
        rendered = json.dumps(result.public_projection(), sort_keys=True)
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("tumour:private", rendered)


class RobustExpressionOutlierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = RobustExpressionOutlierAnalyzer()

    def test_mad_outlier_support_and_opposite_direction_contradiction(self) -> None:
        references = reference_batch([1, 2, 3, 4, 5, 6, 7])
        high = expression("tumour:opaque-01", 20.0, source_id="matched-tumour")
        supported = self.analyzer.analyze(
            high, references, expected_direction=RegulatoryDirection.GAIN
        )
        contradicted = self.analyzer.analyze(
            high, references, expected_direction=RegulatoryDirection.LOSS
        )
        self.assertEqual(supported.state, RNAEvidenceState.SUPPORTED)
        self.assertEqual(contradicted.state, RNAEvidenceState.CONTRADICTORY)
        self.assertEqual(supported.direction, ExpressionDirection.UP)
        self.assertEqual(supported.dispersion_method, DispersionMethod.MAD)
        self.assertGreater(supported.robust_z or 0.0, supported.z_threshold)

    def test_non_outlier_is_a_measured_negative(self) -> None:
        result = self.analyzer.analyze(
            expression("tumour:opaque-01", 4.1, source_id="matched-tumour"),
            reference_batch([1, 2, 3, 4, 5, 6, 7]),
            expected_direction=RegulatoryDirection.GAIN,
        )
        self.assertEqual(result.state, RNAEvidenceState.MEASURED_NEGATIVE)
        self.assertIn("no_expression_outlier", result.reason_codes)

    def test_zero_mad_uses_iqr_fallback(self) -> None:
        references = reference_batch([1, 1, 1, 1, 1, 2, 3, 4, 5])
        result = self.analyzer.analyze(
            expression("tumour:opaque-01", 20, source_id="matched-tumour"), references
        )
        self.assertEqual(result.state, RNAEvidenceState.SUPPORTED)
        self.assertEqual(result.dispersion_method, DispersionMethod.IQR)
        self.assertIn("mad_zero_iqr_fallback", result.reason_codes)

    def test_zero_mad_and_iqr_abstains_instead_of_dividing_by_zero(self) -> None:
        result = self.analyzer.analyze(
            expression("tumour:opaque-01", 20, source_id="matched-tumour"),
            reference_batch([1, 1, 1, 1, 1, 1]),
        )
        self.assertEqual(result.state, RNAEvidenceState.ABSTAINED)
        self.assertIsNone(result.robust_z)
        self.assertIsNone(result.dispersion)
        self.assertIn("zero_reference_dispersion", result.reason_codes)

    def test_context_and_scale_mismatch_are_out_of_domain(self) -> None:
        target = expression("tumour:opaque-01", 10, source_id="matched-tumour")
        foreign = ExpressionBatch(tuple(
            expression(f"reference:{index}", float(index), context_key="foreign-context")
            for index in range(6)
        ))
        self.assertEqual(
            self.analyzer.analyze(target, foreign).state,
            RNAEvidenceState.OUT_OF_DOMAIN,
        )
        linear = ExpressionBatch(tuple(
            expression(f"reference:{index}", float(index), scale=ExpressionScale.TPM)
            for index in range(6)
        ))
        self.assertIn(
            "expression_scale_mismatch",
            self.analyzer.analyze(target, linear).reason_codes,
        )

    def test_raw_counts_are_not_treated_as_cross_sample_expression(self) -> None:
        target = expression(
            "tumour:opaque-01", 100, scale=ExpressionScale.RAW_COUNT, source_id="tumour"
        )
        references = ExpressionBatch(tuple(
            expression(
                f"reference:{index}",
                index,
                scale=ExpressionScale.RAW_COUNT,
            )
            for index in range(6)
        ))
        result = self.analyzer.analyze(target, references)
        self.assertEqual(result.state, RNAEvidenceState.OUT_OF_DOMAIN)
        self.assertIn("unnormalized_expression_scale", result.reason_codes)

    def test_result_round_trip_checks_content_address(self) -> None:
        result = self.analyzer.analyze(
            expression("tumour:opaque-01", 20, source_id="matched-tumour"),
            reference_batch([1, 2, 3, 4, 5, 6]),
        )
        self.assertEqual(ExpressionOutlierResult.from_json(result.to_json()), result)
        forged = result.to_dict() | {"content_address": "expression-outlier:forged"}
        with self.assertRaisesRegex(ValidationError, "content_address"):
            ExpressionOutlierResult.from_mapping(forged)


class AllelicImbalanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = AllelicImbalanceAnalyzer()

    def test_balanced_measurement_is_negative_and_has_zero_log2_ratio(self) -> None:
        result = self.analyzer.analyze(allelic(50, 50))
        self.assertEqual(result.state, RNAEvidenceState.MEASURED_NEGATIVE)
        self.assertEqual(result.direction, AllelicDirection.BALANCED)
        self.assertAlmostEqual(result.p_value or 0.0, 1.0)
        self.assertAlmostEqual(result.q_value or 0.0, 1.0)
        self.assertIsNotNone(result.log2_ratio)
        self.assertAlmostEqual(float(result.log2_ratio), 0.0)

    def test_imbalanced_measurement_is_supported_or_directionally_contradictory(self) -> None:
        observation = allelic(20, 80)
        supported = self.analyzer.analyze(
            observation, expected_direction=RegulatoryDirection.GAIN
        )
        contradicted = self.analyzer.analyze(
            observation, expected_direction=RegulatoryDirection.LOSS
        )
        self.assertEqual(supported.state, RNAEvidenceState.SUPPORTED)
        self.assertEqual(contradicted.state, RNAEvidenceState.CONTRADICTORY)
        self.assertEqual(supported.direction, AllelicDirection.ALT_ENRICHED)
        self.assertLess(supported.p_value or 1.0, 1e-8)
        self.assertAlmostEqual(supported.log2_ratio or 0.0, 2.0)

    def test_low_depth_unphased_and_mapping_biased_rows_abstain(self) -> None:
        cases = (
            (allelic(4, 5), "low_informative_depth"),
            (allelic(30, 70, phase=PhaseStatus.UNPHASED), "allele_phase_unresolved"),
            (allelic(30, 70, mapping_bias=0.2), "mapping_bias"),
            (allelic(30, 70, mapping_bias_flag=True), "mapping_bias"),
        )
        for observation, reason in cases:
            with self.subTest(reason=reason):
                result = self.analyzer.analyze(observation)
                self.assertEqual(result.state, RNAEvidenceState.ABSTAINED)
                self.assertIn(reason, result.reason_codes)
                self.assertIsNone(result.p_value)

    def test_missing_expected_fraction_abstains_without_assuming_half(self) -> None:
        observation = allelic(50, 50, expected_alt_fraction=None)
        self.assertIsNone(observation.resolved_expected_alt_fraction)
        result = self.analyzer.analyze(observation)
        self.assertEqual(result.state, RNAEvidenceState.ABSTAINED)
        self.assertIn("missing_expected_alt_fraction", result.reason_codes)
        self.assertIsNone(result.expected_alt_fraction)

    def test_copy_number_and_purity_adjust_loh_baseline(self) -> None:
        observation = allelic(
            90,
            10,
            expected_alt_fraction=None,
            ref_copy_number=2,
            alt_copy_number=0,
            purity=0.8,
        )
        self.assertAlmostEqual(observation.resolved_expected_alt_fraction or 0.0, 0.1)
        self.assertEqual(
            observation.expected_fraction_method,
            ExpectedFractionMethod.COPY_NUMBER_PURITY,
        )
        result = self.analyzer.analyze(observation)
        self.assertEqual(result.state, RNAEvidenceState.MEASURED_NEGATIVE)
        self.assertEqual(result.direction, AllelicDirection.BALANCED)
        self.assertAlmostEqual(result.p_value or 0.0, 1.0)
        self.assertIsNotNone(result.log2_ratio)
        self.assertAlmostEqual(float(result.log2_ratio), 0.0)

    def test_context_mismatch_is_out_of_domain(self) -> None:
        result = self.analyzer.analyze(
            allelic(20, 80), expected_context_key="foreign-context"
        )
        self.assertEqual(result.state, RNAEvidenceState.OUT_OF_DOMAIN)
        self.assertIn("context_mismatch", result.reason_codes)

    def test_exact_binomial_known_values_and_boundaries(self) -> None:
        self.assertAlmostEqual(exact_two_sided_binomial_pvalue(8, 10, 0.5), 0.109375)
        self.assertEqual(exact_two_sided_binomial_pvalue(0, 10, 0.0), 1.0)
        self.assertEqual(exact_two_sided_binomial_pvalue(1, 10, 0.0), 0.0)
        self.assertAlmostEqual(
            exact_two_sided_binomial_pvalue(2, 10, 0.2),
            1.0,
        )

    def test_exact_binomial_global_limit_fails_before_enumeration(self) -> None:
        self.assertEqual(
            exact_two_sided_binomial_pvalue(0, MAX_EXACT_BINOMIAL_TRIALS, 0.0),
            1.0,
        )
        with patch(
            "builtins.range",
            side_effect=AssertionError("exact outcome enumeration must not start"),
        ) as outcome_range:
            with self.assertRaisesRegex(
                ValidationError,
                "MAX_EXACT_BINOMIAL_TRIALS",
            ):
                exact_two_sided_binomial_pvalue(
                    1,
                    MAX_EXACT_BINOMIAL_TRIALS + 1,
                    0.5,
                )
        outcome_range.assert_not_called()

    def test_allelic_policy_validates_integer_depth_interval(self) -> None:
        default = AllelicImbalancePolicy()
        self.assertEqual(default.max_informative_depth, MAX_EXACT_BINOMIAL_TRIALS)
        self.assertEqual(
            default.max_batch_exact_outcomes,
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        legacy_positional = AllelicImbalancePolicy(20, 0.10, 0.10, 0.05)
        self.assertEqual(
            legacy_positional.max_informative_depth,
            MAX_EXACT_BINOMIAL_TRIALS,
        )
        self.assertEqual(
            legacy_positional.max_batch_exact_outcomes,
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        legacy_depth_positional = AllelicImbalancePolicy(20, 0.10, 0.10, 0.05, 25)
        self.assertEqual(legacy_depth_positional.max_informative_depth, 25)
        self.assertEqual(
            legacy_depth_positional.max_batch_exact_outcomes,
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        self.assertEqual(
            AllelicImbalancePolicy(
                min_informative_depth=25,
                max_informative_depth=25,
                max_batch_exact_outcomes=26,
            ).max_informative_depth,
            25,
        )
        invalid = (
            ({"min_informative_depth": True}, "min_informative_depth"),
            ({"min_informative_depth": 1.5}, "min_informative_depth"),
            ({"max_informative_depth": False}, "max_informative_depth"),
            ({"max_informative_depth": 100.5}, "max_informative_depth"),
            (
                {"min_informative_depth": 20, "max_informative_depth": 19},
                "at least min_informative_depth",
            ),
            (
                {"max_informative_depth": MAX_EXACT_BINOMIAL_TRIALS + 1},
                "MAX_EXACT_BINOMIAL_TRIALS",
            ),
            ({"max_batch_exact_outcomes": True}, "max_batch_exact_outcomes"),
            ({"max_batch_exact_outcomes": 1.5}, "max_batch_exact_outcomes"),
            ({"max_batch_exact_outcomes": 0}, "max_batch_exact_outcomes"),
            (
                {
                    "max_batch_exact_outcomes": (
                        MAX_ALLELIC_BATCH_EXACT_OUTCOMES + 1
                    )
                },
                "MAX_ALLELIC_BATCH_EXACT_OUTCOMES",
            ),
        )
        for arguments, message in invalid:
            with self.subTest(arguments=arguments), self.assertRaisesRegex(
                ValidationError,
                message,
            ):
                AllelicImbalancePolicy(**arguments)

    def test_batch_exact_work_budget_is_preflighted_and_order_independent(self) -> None:
        rows = (
            allelic(50, 49, sample_key="tumour:a"),
            allelic(50, 51, sample_key="tumour:b"),
        )
        boundary_analyzer = AllelicImbalanceAnalyzer(
            AllelicImbalancePolicy(
                min_informative_depth=1,
                max_informative_depth=101,
                max_batch_exact_outcomes=202,
            )
        )
        with patch(
            "glio_noncode.expression_evidence.exact_two_sided_binomial_pvalue",
            return_value=1.0,
        ) as exact_test:
            results = boundary_analyzer.analyze_batch(AllelicCountBatch(rows))
        self.assertEqual(len(results), 2)
        self.assertEqual(exact_test.call_count, 2)

        over_limit_analyzer = AllelicImbalanceAnalyzer(
            AllelicImbalancePolicy(
                min_informative_depth=1,
                max_informative_depth=101,
                max_batch_exact_outcomes=201,
            )
        )
        messages = []
        with patch(
            "glio_noncode.expression_evidence.exact_two_sided_binomial_pvalue",
            side_effect=AssertionError("exact inference must not start"),
        ) as exact_test:
            for ordered_rows in (rows, tuple(reversed(rows))):
                with self.assertRaisesRegex(
                    ValidationError,
                    "requires 202 outcomes.*policy maximum of 201",
                ) as raised:
                    over_limit_analyzer.analyze_batch(
                        AllelicCountBatch(ordered_rows)
                    )
                messages.append(str(raised.exception))
        exact_test.assert_not_called()
        self.assertEqual(messages[0], messages[1])

    def test_policy_boundary_runs_exact_test_and_over_limit_abstains(self) -> None:
        analyzer = AllelicImbalanceAnalyzer(
            AllelicImbalancePolicy(
                min_informative_depth=1,
                max_informative_depth=100,
            )
        )
        with patch(
            "glio_noncode.expression_evidence.exact_two_sided_binomial_pvalue",
            wraps=exact_two_sided_binomial_pvalue,
        ) as exact_test:
            boundary = analyzer.analyze(allelic(50, 50))
            self.assertIsNotNone(boundary.p_value)
            exact_test.assert_called_once()
            exact_test.reset_mock()

            over_limit = analyzer.analyze(allelic(50, 51))
            exact_test.assert_not_called()
        self.assertEqual(over_limit.state, RNAEvidenceState.ABSTAINED)
        self.assertEqual(over_limit.direction, AllelicDirection.UNKNOWN)
        self.assertIsNone(over_limit.p_value)
        self.assertIsNone(over_limit.q_value)
        self.assertIsNone(over_limit.log2_ratio)
        self.assertIn(
            "exact_binomial_depth_limit_exceeded",
            over_limit.reason_codes,
        )

    def test_global_over_limit_depth_abstains_without_exact_inference(self) -> None:
        observation = allelic(MAX_EXACT_BINOMIAL_TRIALS + 1, 0)
        with patch(
            "glio_noncode.expression_evidence.exact_two_sided_binomial_pvalue",
            side_effect=AssertionError("exact inference must not run"),
        ) as exact_test:
            result = self.analyzer.analyze(observation)
        exact_test.assert_not_called()
        self.assertEqual(result.state, RNAEvidenceState.ABSTAINED)
        self.assertEqual(
            result.reason_codes,
            ("exact_binomial_depth_limit_exceeded",),
        )
        self.assertIsNone(result.p_value)

    def test_batch_excludes_over_limit_rows_from_exact_test_and_bh(self) -> None:
        batch = AllelicCountBatch(
            (
                allelic(
                    MAX_EXACT_BINOMIAL_TRIALS + 1,
                    0,
                    sample_key="tumour:a",
                ),
                allelic(50, 50, sample_key="tumour:b"),
            )
        )
        with patch(
            "glio_noncode.expression_evidence.exact_two_sided_binomial_pvalue",
            wraps=exact_two_sided_binomial_pvalue,
        ) as exact_test:
            results = self.analyzer.analyze_batch(batch)
        exact_test.assert_called_once()
        by_depth = {item.informative_depth: item for item in results}
        oversized = by_depth[MAX_EXACT_BINOMIAL_TRIALS + 1]
        tested = by_depth[100]
        self.assertEqual(oversized.state, RNAEvidenceState.ABSTAINED)
        self.assertIsNone(oversized.p_value)
        self.assertIsNone(oversized.q_value)
        self.assertEqual(tested.state, RNAEvidenceState.MEASURED_NEGATIVE)
        self.assertAlmostEqual(tested.p_value or 0.0, 1.0)
        self.assertAlmostEqual(tested.q_value or 0.0, 1.0)

    def test_bh_is_deterministic_and_preserves_input_order(self) -> None:
        values = (0.01, 0.04, 0.03, 0.002)
        expected = (0.02, 0.04, 0.04, 0.008)
        self.assertEqual(benjamini_hochberg(values), expected)
        reverse_adjusted = benjamini_hochberg(tuple(reversed(values)))
        self.assertEqual(tuple(reversed(reverse_adjusted)), expected)

    def test_batch_addresses_and_q_values_are_row_order_deterministic(self) -> None:
        rows = (
            allelic(50, 50, sample_key="tumour:a"),
            allelic(20, 80, sample_key="tumour:b"),
            allelic(30, 70, sample_key="tumour:c"),
        )
        first = AllelicCountBatch(rows)
        second = AllelicCountBatch(tuple(reversed(rows)))
        self.assertEqual(first.content_address, second.content_address)
        left = self.analyzer.analyze_batch(first)
        right = self.analyzer.analyze_batch(second)
        self.assertEqual([item.to_dict() for item in left], [item.to_dict() for item in right])

    def test_observation_batch_and_result_round_trip(self) -> None:
        observation = allelic(20, 80)
        self.assertEqual(
            AllelicCountObservation.from_json(observation.to_json()), observation
        )
        batch = AllelicCountBatch((observation, allelic(50, 50, sample_key="tumour:b")))
        self.assertEqual(AllelicCountBatch.from_json(batch.to_json()), batch)
        result = self.analyzer.analyze(observation)
        self.assertEqual(type(result).from_json(result.to_json()), result)


class RNAIntegrationAndPrivacyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.prediction = PredictedRegulatoryEffect(
            prediction_id="prediction:01",
            variant_id="variant:chr3-181711925-A-G",
            feature_id="gene:SOX2",
            direction=RegulatoryDirection.GAIN,
            context_key=CONTEXT,
            source_id="sequence-model",
            source_version="model-3",
            confidence=0.91,
        )
        references = reference_batch([1, 2, 3, 4, 5, 6, 7])
        self.expression_supported = RobustExpressionOutlierAnalyzer().analyze(
            expression("tumour:secret-direct-id", 20, source_id="matched-tumour"),
            references,
        )
        self.expression_opposite = RobustExpressionOutlierAnalyzer().analyze(
            expression("tumour:secret-direct-id", -20, source_id="matched-tumour"),
            references,
        )
        self.allelic_supported = AllelicImbalanceAnalyzer().analyze(allelic(20, 80))

    def test_concordant_and_opposite_directions_remain_distinct(self) -> None:
        integrator = RNAConsequenceIntegrator()
        concordant = integrator.integrate(
            self.prediction,
            expression=self.expression_supported,
            allelic=self.allelic_supported,
        )
        opposite = integrator.integrate(
            self.prediction,
            expression=self.expression_opposite,
        )
        self.assertEqual(concordant.state, RNAEvidenceState.SUPPORTED)
        self.assertEqual(opposite.state, RNAEvidenceState.CONTRADICTORY)
        self.assertIn("rna_direction_concordant", concordant.reason_codes)
        self.assertIn("rna_direction_opposes_prediction", opposite.reason_codes)

    def test_scope_mismatch_is_out_of_domain(self) -> None:
        foreign_prediction = PredictedRegulatoryEffect(
            prediction_id="prediction:foreign",
            variant_id=self.prediction.variant_id,
            feature_id="gene:OTHER",
            direction=RegulatoryDirection.GAIN,
            context_key=CONTEXT,
            source_id="sequence-model",
        )
        result = RNAConsequenceIntegrator().integrate(
            foreign_prediction, expression=self.expression_supported
        )
        self.assertEqual(result.state, RNAEvidenceState.OUT_OF_DOMAIN)

    def test_public_projection_contains_no_sample_ids_or_cohort_vectors(self) -> None:
        result = RNAConsequenceIntegrator().integrate(
            self.prediction,
            expression=self.expression_supported,
            allelic=self.allelic_supported,
        )
        projection = result.public_projection()
        rendered = json.dumps(projection, sort_keys=True)
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("sample_id", rendered)
        self.assertNotIn("secret-direct-id", rendered)
        self.assertNotIn("observations", rendered)
        self.assertNotIn("cohort_values", rendered)
        self.assertEqual(set(projection), set(result.to_dict()))

    def test_integration_round_trip_and_content_address(self) -> None:
        result = RNAConsequenceIntegrator().integrate(
            self.prediction,
            expression=self.expression_supported,
            allelic=self.allelic_supported,
        )
        rebuilt = RNAConsequenceEvidence.from_json(result.to_json())
        self.assertEqual(rebuilt, result)
        self.assertEqual(rebuilt.content_address, result.content_address)

    def test_capability_and_public_schema_helpers_are_deterministic_and_private(self) -> None:
        capabilities = expression_evidence_capabilities()
        self.assertEqual(capabilities, expression_evidence_capabilities())
        self.assertTrue(capabilities["privacy"]["public_results_are_sample_free"])
        self.assertEqual(
            capabilities["computational_bounds"]["max_exact_binomial_trials"],
            MAX_EXACT_BINOMIAL_TRIALS,
        )
        self.assertEqual(
            capabilities["computational_bounds"][
                "max_expression_batch_observations"
            ],
            MAX_EXPRESSION_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            capabilities["computational_bounds"][
                "max_allelic_batch_observations"
            ],
            MAX_ALLELIC_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            capabilities["computational_bounds"][
                "max_allelic_batch_exact_outcomes"
            ],
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        self.assertEqual(
            capabilities["computational_bounds"][
                "default_max_batch_exact_outcomes"
            ],
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        self.assertEqual(
            capabilities["computational_bounds"][
                "batch_exact_work_over_limit_action"
            ],
            "reject_batch_before_inference",
        )
        self.assertEqual(
            capabilities["batch_validation"],
            {
                "bounded_materialization": True,
                "strict_item_types": True,
                "duplicate_identities_rejected": True,
            },
        )
        self.assertEqual(
            capabilities["computational_bounds"]["over_limit_state"],
            RNAEvidenceState.ABSTAINED.value,
        )
        public_schema = expression_evidence_schema()
        self.assertEqual(public_schema, expression_evidence_schema(public=True))
        rendered = json.dumps(public_schema, sort_keys=True)
        self.assertEqual(
            public_schema["$defs"]["AllelicImbalancePolicy"]["properties"][
                "max_informative_depth"
            ]["maximum"],
            MAX_EXACT_BINOMIAL_TRIALS,
        )
        self.assertEqual(
            public_schema["$defs"]["AllelicImbalancePolicy"]["properties"][
                "max_batch_exact_outcomes"
            ]["maximum"],
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )
        self.assertEqual(
            public_schema["$defs"]["AllelicImbalancePolicy"]["properties"]["alpha"][
                "minimum"
            ],
            0.0,
        )
        self.assertNotIn("sample_key", rendered)
        self.assertNotIn("ExpressionBatch", public_schema["$defs"])
        self.assertNotIn("AllelicCountBatch", public_schema["$defs"])
        private_schema = expression_evidence_schema(public=False)
        self.assertIn("sample_key", json.dumps(private_schema))
        self.assertEqual(
            private_schema["$defs"]["ExpressionBatch"]["properties"][
                "observations"
            ]["maxItems"],
            MAX_EXPRESSION_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            private_schema["$defs"]["AllelicCountBatch"]["properties"][
                "observations"
            ]["maxItems"],
            MAX_ALLELIC_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            public_schema["computational_bounds"][
                "max_expression_batch_observations"
            ],
            MAX_EXPRESSION_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            public_schema["computational_bounds"][
                "max_allelic_batch_observations"
            ],
            MAX_ALLELIC_BATCH_OBSERVATIONS,
        )
        self.assertEqual(
            public_schema["computational_bounds"][
                "max_allelic_batch_exact_outcomes"
            ],
            MAX_ALLELIC_BATCH_EXACT_OUTCOMES,
        )


if __name__ == "__main__":
    unittest.main()
