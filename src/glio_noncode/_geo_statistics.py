"""Small, dependency-free linear-model primitives for public GEO screening."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import ValidationError

_BETA_MAX_ITERATIONS = 512
_BETA_EPSILON = 3.0e-14
_BETA_FLOOR = 1.0e-300


@dataclass(frozen=True, slots=True)
class LinearContrastResult:
    coefficient: float | None
    standard_error: float
    statistic: float
    degrees_of_freedom: int
    p_value: float


@dataclass(frozen=True, slots=True)
class PreparedLinearModel:
    q_columns: tuple[tuple[float, ...], ...]
    upper_triangle: tuple[tuple[float, ...], ...]
    contrast_index: int
    contrast_variance_factor: float
    degrees_of_freedom: int


def _norm(values: Sequence[float]) -> float:
    return math.sqrt(math.fsum(value * value for value in values))


def prepare_linear_model(
    rows: Sequence[Sequence[float]],
    *,
    contrast_index: int,
    rank_tolerance: float = 1.0e-10,
    maximum_diagonal_condition: float = 1.0e8,
) -> PreparedLinearModel:
    """Factor a fixed full-rank design with re-orthogonalized modified Gram-Schmidt."""

    if not rows:
        raise ValidationError("adjusted model has no complete sample rows")
    column_count = len(rows[0])
    if (
        isinstance(contrast_index, bool)
        or not isinstance(contrast_index, int)
        or column_count < 2
        or not 0 <= contrast_index < column_count
    ):
        raise ValidationError("adjusted model contrast column is invalid")
    if (
        not math.isfinite(rank_tolerance)
        or not 0.0 < rank_tolerance < 1.0
        or not math.isfinite(maximum_diagonal_condition)
        or maximum_diagonal_condition <= 1.0
    ):
        raise ValidationError("adjusted model numerical tolerances are invalid")
    if len(rows) <= column_count:
        raise ValidationError("adjusted model has no residual degrees of freedom")
    if any(len(row) != column_count for row in rows):
        raise ValidationError("adjusted model design rows have inconsistent widths")
    if any(not math.isfinite(value) for row in rows for value in row):
        raise ValidationError("adjusted model design contains a non-finite value")

    columns = [tuple(row[index] for row in rows) for index in range(column_count)]
    q_columns: list[tuple[float, ...]] = []
    upper = [[0.0] * column_count for _ in range(column_count)]
    diagonal: list[float] = []
    for column_index, source_column in enumerate(columns):
        residual = list(source_column)
        source_norm = _norm(source_column)
        if source_norm == 0.0:
            raise ValidationError("adjusted model design is rank deficient")
        for _ in range(2):
            for basis_index, basis in enumerate(q_columns):
                projection = math.fsum(
                    left * right for left, right in zip(basis, residual, strict=True)
                )
                upper[basis_index][column_index] += projection
                residual = [
                    value - projection * q for value, q in zip(residual, basis, strict=True)
                ]
        residual_norm = _norm(residual)
        if residual_norm <= rank_tolerance * source_norm:
            raise ValidationError("adjusted model design is rank deficient or collinear")
        upper[column_index][column_index] = residual_norm
        diagonal.append(residual_norm)
        q_columns.append(tuple(value / residual_norm for value in residual))

    condition_ratio = max(diagonal) / min(diagonal)
    if not math.isfinite(condition_ratio) or condition_ratio > maximum_diagonal_condition:
        raise ValidationError("adjusted model design is ill-conditioned")

    # For X = QR, (X'X)^-1 = R^-1 R^-T. The contrast variance factor is
    # ||R^-T e_contrast||^2 and is reused for every feature in this design.
    solved = [0.0] * column_count
    for row_index in range(column_count):
        right_hand_side = 1.0 if row_index == contrast_index else 0.0
        prior = math.fsum(
            upper[column_index][row_index] * solved[column_index]
            for column_index in range(row_index)
        )
        solved[row_index] = (right_hand_side - prior) / upper[row_index][row_index]
    variance_factor = math.fsum(value * value for value in solved)
    if not math.isfinite(variance_factor) or variance_factor <= 0.0:
        raise ValidationError("adjusted model contrast variance is not estimable")

    return PreparedLinearModel(
        q_columns=tuple(q_columns),
        upper_triangle=tuple(tuple(row) for row in upper),
        contrast_index=contrast_index,
        contrast_variance_factor=variance_factor,
        degrees_of_freedom=len(rows) - column_count,
    )


def fit_linear_contrast(
    model: PreparedLinearModel,
    response: Sequence[float],
) -> LinearContrastResult | None:
    """Fit one response on a prepared design; return None if residual variance is zero."""

    if len(response) != len(model.q_columns[0]):
        raise ValidationError("adjusted model response length differs from its design")
    if any(not math.isfinite(value) for value in response):
        raise ValidationError("adjusted model response contains a non-finite value")
    response_scale = max(abs(value) for value in response)
    if response_scale == 0.0:
        return None
    scaled_response = tuple(value / response_scale for value in response)

    projected = tuple(
        math.fsum(
            q_value * response_value
            for q_value, response_value in zip(column, scaled_response, strict=True)
        )
        for column in model.q_columns
    )
    coefficients = [0.0] * len(projected)
    for row_index in range(len(projected) - 1, -1, -1):
        remainder = math.fsum(
            model.upper_triangle[row_index][column_index] * coefficients[column_index]
            for column_index in range(row_index + 1, len(projected))
        )
        coefficients[row_index] = (projected[row_index] - remainder) / model.upper_triangle[
            row_index
        ][row_index]

    residual_sum_squares = math.fsum(
        (
            response_value
            - math.fsum(
                model.q_columns[column_index][row_index] * projected[column_index]
                for column_index in range(len(projected))
            )
        )
        ** 2
        for row_index, response_value in enumerate(scaled_response)
    )
    response_energy = math.fsum(value * value for value in scaled_response)
    relative_roundoff = 64.0 * math.ulp(1.0) * max(len(response), len(projected))
    zero_residual_bound = relative_roundoff**2 * max(1.0, response_energy)
    if not math.isfinite(residual_sum_squares) or residual_sum_squares <= zero_residual_bound:
        return None
    residual_variance = residual_sum_squares / model.degrees_of_freedom
    scaled_standard_error = math.sqrt(residual_variance * model.contrast_variance_factor)
    if scaled_standard_error <= 0.0 or not math.isfinite(scaled_standard_error):
        raise ArithmeticError("adjusted model contrast standard error is not representable")
    scaled_coefficient = coefficients[model.contrast_index]
    statistic = scaled_coefficient / scaled_standard_error
    if not math.isfinite(statistic):
        raise ArithmeticError("adjusted model contrast statistic is not representable")
    p_value = student_t_two_sided_p(statistic, model.degrees_of_freedom)
    coefficient = scaled_coefficient * response_scale
    standard_error = scaled_standard_error * response_scale
    if not math.isfinite(coefficient):
        coefficient = None
    if not math.isfinite(standard_error):
        raise ArithmeticError("adjusted model contrast standard error is not representable")
    return LinearContrastResult(
        coefficient=coefficient,
        standard_error=standard_error,
        statistic=statistic,
        degrees_of_freedom=model.degrees_of_freedom,
        p_value=p_value,
    )


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _BETA_FLOOR:
        d = _BETA_FLOOR
    d = 1.0 / d
    result = d
    for iteration in range(1, _BETA_MAX_ITERATIONS + 1):
        twice = 2 * iteration
        numerator = iteration * (b - iteration) * x / ((qam + twice) * (a + twice))
        d = 1.0 + numerator * d
        if abs(d) < _BETA_FLOOR:
            d = _BETA_FLOOR
        c = 1.0 + numerator / c
        if abs(c) < _BETA_FLOOR:
            c = _BETA_FLOOR
        d = 1.0 / d
        result *= d * c

        numerator = -(a + iteration) * (qab + iteration) * x / ((a + twice) * (qap + twice))
        d = 1.0 + numerator * d
        if abs(d) < _BETA_FLOOR:
            d = _BETA_FLOOR
        c = 1.0 + numerator / c
        if abs(c) < _BETA_FLOOR:
            c = _BETA_FLOOR
        d = 1.0 / d
        multiplier = d * c
        result *= multiplier
        if abs(multiplier - 1.0) <= _BETA_EPSILON:
            return result
    raise ArithmeticError("incomplete beta continued fraction did not converge")


def _regularized_incomplete_beta(x: float, a: float, b: float) -> float:
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValidationError("incomplete beta arguments are outside their domain")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front) if log_front > -745.0 else 0.0
    if x < (a + 1.0) / (a + b + 2.0):
        return min(1.0, max(0.0, front * _beta_continued_fraction(a, b, x) / a))
    complement = front * _beta_continued_fraction(b, a, 1.0 - x) / b
    return min(1.0, max(0.0, 1.0 - complement))


def student_t_two_sided_p(statistic: float, degrees_of_freedom: int) -> float:
    """Return a two-sided Student t tail probability using the incomplete beta identity."""

    if isinstance(degrees_of_freedom, bool) or not isinstance(degrees_of_freedom, int):
        raise ValidationError("Student t degrees of freedom must be an integer")
    if degrees_of_freedom <= 0:
        raise ValidationError("Student t degrees of freedom must be positive")
    if (
        isinstance(statistic, bool)
        or not isinstance(statistic, (int, float))
        or math.isnan(float(statistic))
    ):
        raise ValidationError("Student t statistic must be numeric and not NaN")
    absolute_statistic = abs(float(statistic))
    if math.isinf(absolute_statistic):
        return 0.0
    df = float(degrees_of_freedom)
    x = df / (df + absolute_statistic * absolute_statistic)
    return _regularized_incomplete_beta(x, df / 2.0, 0.5)


def student_t_critical_value(confidence_level: float, degrees_of_freedom: int) -> float:
    """Return the positive critical value for a central two-sided t interval."""

    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(float(confidence_level))
        or not 0.0 < float(confidence_level) < 1.0
    ):
        raise ValidationError("Student t confidence level must be between zero and one")
    if isinstance(degrees_of_freedom, bool) or not isinstance(degrees_of_freedom, int):
        raise ValidationError("Student t degrees of freedom must be an integer")
    if degrees_of_freedom <= 0:
        raise ValidationError("Student t degrees of freedom must be positive")

    target_two_sided_tail = 1.0 - float(confidence_level)
    lower = 0.0
    upper = 1.0
    while student_t_two_sided_p(upper, degrees_of_freedom) > target_two_sided_tail:
        upper *= 2.0
    for _ in range(128):
        midpoint = lower + (upper - lower) / 2.0
        if midpoint == lower or midpoint == upper:
            break
        if student_t_two_sided_p(midpoint, degrees_of_freedom) > target_two_sided_tail:
            lower = midpoint
        else:
            upper = midpoint
    critical_value = lower + (upper - lower) / 2.0
    if not math.isfinite(critical_value) or critical_value <= 0.0:
        raise ArithmeticError("Student t critical value could not be represented")
    return critical_value


__all__ = [
    "LinearContrastResult",
    "PreparedLinearModel",
    "fit_linear_contrast",
    "prepare_linear_model",
    "student_t_critical_value",
    "student_t_two_sided_p",
]
