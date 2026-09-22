from __future__ import annotations

import math
import unittest

from glio_noncode._geo_statistics import (
    fit_linear_contrast,
    prepare_linear_model,
    student_t_two_sided_p,
)
from glio_noncode.errors import ValidationError


class GeoStatisticsTests(unittest.TestCase):
    def test_student_t_two_sided_tail_values_and_extremes(self) -> None:
        self.assertEqual(student_t_two_sided_p(0.0, 10), 1.0)
        self.assertAlmostEqual(student_t_two_sided_p(1.0, 1), 0.5, places=14)
        self.assertAlmostEqual(student_t_two_sided_p(2.2281388519649385, 10), 0.05, places=10)
        self.assertEqual(student_t_two_sided_p(math.inf, 10), 0.0)
        self.assertGreaterEqual(student_t_two_sided_p(100.0, 3), 0.0)
        self.assertLessEqual(student_t_two_sided_p(100.0, 3), 1.0)

    def test_linear_contrast_recovers_group_effect_and_residual_df(self) -> None:
        design = ((1.0, 0.0), (1.0, 0.0), (1.0, 1.0), (1.0, 1.0))
        model = prepare_linear_model(design, contrast_index=1)

        result = fit_linear_contrast(model, (1.0, 2.0, 3.0, 4.0))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.coefficient, 2.0)
        self.assertAlmostEqual(result.statistic, 2.0 * math.sqrt(2.0))
        self.assertEqual(result.degrees_of_freedom, 2)
        self.assertAlmostEqual(
            result.p_value,
            1.0 - result.statistic / math.sqrt(result.statistic**2 + 2.0),
            places=13,
        )

    def test_rank_deficient_designs_and_zero_residual_variance_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValidationError, "rank deficient|collinear"):
            prepare_linear_model(
                ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 1.0), (1.0, 1.0, 1.0)),
                contrast_index=1,
            )

        model = prepare_linear_model(
            ((1.0, 0.0), (1.0, 0.0), (1.0, 1.0), (1.0, 1.0)),
            contrast_index=1,
        )
        self.assertIsNone(fit_linear_contrast(model, (1.0, 1.0, 3.0, 3.0)))

    def test_invalid_shapes_and_nonfinite_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "inconsistent widths"):
            prepare_linear_model(((1.0, 0.0), (1.0,), (1.0, 1.0)), contrast_index=1)
        with self.assertRaisesRegex(ValidationError, "non-finite"):
            prepare_linear_model(
                ((1.0, 0.0), (1.0, 0.0), (1.0, 1.0), (1.0, math.nan)),
                contrast_index=1,
            )


if __name__ == "__main__":
    unittest.main()
