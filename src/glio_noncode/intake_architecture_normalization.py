"""Composition layer for VRS, Cat-VRS, multiallelic, and repeat operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .models import VariantIdentity
from .variant_beta import CatVRSNormalizer, CategoricalCatalogParser, RepeatAwareNormalizer
from .variant_normalization import NormalizationState, VRSNormalizer
from .intake_architecture_contracts import (
    IntakeArchitectureCase,
    IntakeArchitectureNormalizationReceipt,
    IntakeArchitectureOperation,
    IntakeArchitectureState,
    addressed,
)


def _variant(payload: Mapping[str, Any]) -> VariantIdentity:
    raw = payload.get("variant", payload)
    if not isinstance(raw, Mapping):
        raise ValidationError("normalization requires a variant object")
    return VariantIdentity.from_dict(raw)


def normalize_vrs(payload: Mapping[str, Any]) -> tuple[int, str | None, IntakeArchitectureState, tuple[str, ...], str]:
    report = VRSNormalizer().normalize(_variant(payload), genome_build=str(payload.get("variant", {}).get("genome_build", "GRCh38")))
    state = IntakeArchitectureState.ACCEPTED if report.state is NormalizationState.SUPPORTED else IntakeArchitectureState.REVIEW
    selected = report.selected_candidate_id
    return len(report.candidates), selected, state, tuple(report.warnings) + tuple(report.ambiguities), report.content_address


def normalize_cat_vrs(payload: Mapping[str, Any]) -> tuple[int, str | None, IntakeArchitectureState, tuple[str, ...], str]:
    category = payload.get("category", payload)
    if not isinstance(category, Mapping):
        return 0, None, IntakeArchitectureState.ABSTAINED, ("category_not_object",), addressed(payload, "catvrs-error")
    text = json.dumps(category, sort_keys=True)
    batch = CategoricalCatalogParser().parse_json(text, source_id="public-reference-aggregate", source_version="d01-controls-v1")
    report = CatVRSNormalizer(batch.definitions).normalize(category)
    state = IntakeArchitectureState.ACCEPTED if report.state.value == "supported" else IntakeArchitectureState.REVIEW
    warnings = tuple(issue.code for issue in report.issues) + tuple(report.warnings)
    stable_address = addressed(
        {
            "category_id": category.get("category_id"),
            "selected_category_id": report.selected_category_id,
            "state": state,
            "warnings": warnings,
        },
        "catvrs-receipt",
    )
    return len(report.candidates), report.selected_category_id, state, warnings, stable_address


def normalize_repeat(payload: Mapping[str, Any]) -> tuple[int, str | None, IntakeArchitectureState, tuple[str, ...], str]:
    window = payload.get("reference_window", {})
    if not isinstance(window, Mapping):
        return 0, None, IntakeArchitectureState.ABSTAINED, ("reference_window_missing",), addressed(payload, "repeat-error")
    try:
        report = RepeatAwareNormalizer().normalize(
            _variant(payload),
            reference_sequence=str(window["sequence"]),
            reference_start=int(window["start"]),
            max_shift_bp=int(window.get("max_shift_bp", 50)),
            genome_build="GRCh38",
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        return 0, None, IntakeArchitectureState.REVIEW, ("malformed_input", str(exc)), addressed(payload, "repeat-error")
    state = IntakeArchitectureState.ACCEPTED if report.state.value == "supported" else IntakeArchitectureState.REVIEW
    selected = report.variant.variant_id if report.variant is not None else None
    return len(report.placements), selected, state, tuple(issue.code for issue in report.issues) + tuple(report.warnings), report.content_address


def normalize_intake_architecture_case(case: IntakeArchitectureCase) -> IntakeArchitectureNormalizationReceipt:
    payload = case.payload
    operation = next((item for item in IntakeArchitectureOperation if case.operation_id.endswith(f"C{list(IntakeArchitectureOperation).index(item) + 1:02d}")), None)
    normalizer = "identity-preserving-parser"
    try:
        if operation is IntakeArchitectureOperation.CAT_VRS_NORMALIZATION:
            candidate_count, selected, state, warnings, input_address = normalize_cat_vrs(payload)
            normalizer = "CatVRSNormalizer"
        elif operation is IntakeArchitectureOperation.REPEAT_AWARE_NORMALIZATION:
            candidate_count, selected, state, warnings, input_address = normalize_repeat(payload)
            normalizer = "RepeatAwareNormalizer"
        else:
            candidate_count, selected, state, warnings, input_address = normalize_vrs(payload)
            normalizer = "VRSNormalizer"
    except (TypeError, ValueError, ValidationError) as exc:
        candidate_count, selected, state, warnings, input_address = 0, None, IntakeArchitectureState.REVIEW, ("malformed_input", str(exc)), addressed(payload, "normalization-error")
    if case.scenario.value == "malformed_input":
        state = IntakeArchitectureState.REVIEW
        warnings = tuple(sorted(set(warnings) | {"malformed_input"}))
    body = {
        "case_id": case.case_id,
        "normalizer": normalizer,
        "input_address": input_address,
        "candidate_count": candidate_count,
        "selected_identifier": selected,
        "state": state,
        "warnings": warnings,
    }
    return IntakeArchitectureNormalizationReceipt(**body, content_address=addressed(body, "intake-normalization-receipt"))


__all__ = [
    "normalize_vrs",
    "normalize_cat_vrs",
    "normalize_repeat",
    "normalize_intake_architecture_case",
]
