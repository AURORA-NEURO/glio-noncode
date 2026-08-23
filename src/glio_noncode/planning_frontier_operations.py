"""Functional execution for eligibility, guide, control, and power planning."""

from __future__ import annotations

import csv
import io
import json
import math
from collections.abc import Mapping
from typing import Any

from .planning_frontier_contracts import (
    PLANNING_FRONTIER_CONTEXT_KEY,
    PlanningOperation,
    PlanningOperationResult,
    PlanningState,
)
from .planning_frontier_support import (
    address,
    bounded_fraction,
    context_matches,
    dna,
    finite_number,
    issue_codes,
    mapping,
    positive_integer,
    required_text,
    safe_output,
    sequence,
    unique_text,
)


STRENGTH_RANK = {"exploratory": 1, "moderate": 2, "strong": 3, "replicated": 4}


def _result(
    operation: PlanningOperation,
    state: PlanningState,
    issues: list[str],
    output: Mapping[str, Any],
) -> PlanningOperationResult:
    normalized = issue_codes(issues)
    projected = safe_output(output)
    body = {
        "operation": operation,
        "state": state,
        "issue_codes": normalized,
        "output": projected,
    }
    return PlanningOperationResult(**body, content_address=address(body, prefix="planning-result"))


def _invalid(operation: PlanningOperation, fields: tuple[str, ...]) -> PlanningOperationResult:
    return _result(
        operation,
        PlanningState.REJECTED,
        ["invalid_payload"],
        {"accepted_fields": fields},
    )


def _context(payload: Mapping[str, Any], issues: list[str]) -> str:
    value = str(payload.get("context_key") or "")
    if not context_matches(value, PLANNING_FRONTIER_CONTEXT_KEY):
        issues.append("context_mismatch")
    return value


def _controls_and_readouts(payload: Mapping[str, Any], issues: list[str]) -> dict[str, tuple[str, ...]]:
    controls = unique_text(sequence(payload.get("controls", ()), "controls"), "controls")
    readouts = unique_text(sequence(payload.get("readouts", ()), "readouts"), "readouts")
    if not controls:
        issues.append("controls_missing")
    if not readouts:
        issues.append("readouts_missing")
    return {"controls": controls, "readouts": readouts}


def evaluate_model_system_eligibility(payload: Mapping[str, Any]) -> PlanningOperationResult:
    operation = PlanningOperation.MODEL_ELIGIBILITY
    try:
        request_id = required_text(payload.get("request_id"), "request_id")
        context = _context(payload, issues := [])
        model_system = required_text(payload.get("model_system"), "model_system")
        minimum = required_text(payload.get("minimum_evidence_strength", "moderate"), "minimum_evidence_strength").lower()
        observations = sequence(payload.get("observations", ()), "observations")
        if minimum not in STRENGTH_RANK:
            issues.append("evidence_threshold_unknown")
            minimum = "moderate"
        if not observations:
            issues.append("no_model_observations")
        results: list[dict[str, Any]] = []
        for index, raw in enumerate(observations, start=1):
            row = mapping(raw, f"observations[{index}]")
            model_id = required_text(row.get("model_id", row.get("id")), f"observations[{index}].model_id")
            row_context = str(row.get("context_key", ""))
            strength = str(row.get("evidence_strength", "exploratory")).lower()
            declared = tuple(str(item) for item in sequence(row.get("declared_context_keys", ()), "declared_context_keys"))
            blockers = unique_text(sequence(row.get("blockers", ()), "blockers"), "blockers")
            row_issues: list[str] = []
            if row_context != context:
                row_issues.append("context_mismatch")
            if context not in declared:
                row_issues.append("context_not_declared_supported")
            if strength not in STRENGTH_RANK or STRENGTH_RANK.get(strength, 0) < STRENGTH_RANK.get(minimum, 99):
                row_issues.append("evidence_below_threshold")
            if blockers:
                row_issues.append("eligibility_blocked")
            eligible = not row_issues and bool(row.get("supports_context", True)) and model_system == str(row.get("model_system", model_system))
            if not bool(row.get("supports_context", True)):
                row_issues.append("context_not_declared_supported")
                eligible = False
            results.append({
                "model_id": model_id,
                "model_system": str(row.get("model_system", "")),
                "cell_state": str(row.get("cell_state", "")),
                "evidence_strength": strength,
                "declared_context_keys": declared,
                "blockers": blockers,
                "eligible": eligible,
                "issue_codes": issue_codes(row_issues),
                "observation_address": address(row, prefix="eligibility-observation"),
            })
            issues.extend(row_issues)
        if not any(item["eligible"] for item in results) and observations:
            issues.append("no_declared_eligible_model_system")
        state = (
            PlanningState.BLOCKED if "context_mismatch" in issues
            else PlanningState.ABSTAINED if not observations
            else PlanningState.REVIEW if issues
            else PlanningState.READY_FOR_REVIEW
        )
        output = {
            "request_id": request_id,
            "context_key": context,
            "model_system": model_system,
            "minimum_evidence_strength": minimum,
            "observation_count": len(observations),
            "eligible_count": sum(bool(item["eligible"]) for item in results),
            "results": results,
            "controls_readouts": _controls_and_readouts(payload, issues),
            "eligibility_address": address({"request_id": request_id, "results": results}, prefix="eligibility-package"),
        }
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("request_id", "context_key", "model_system", "observations", "minimum_evidence_strength"))


def _parse_guide_rows(text: str, input_format: str | None) -> tuple[Mapping[str, Any], ...]:
    raw = str(text or "")
    if not raw.strip():
        return ()
    mode = (input_format or "").lower()
    if mode in {"json", "jsonl"} or raw.lstrip().startswith(("[", "{")):
        parsed = json.loads(raw)
        rows = parsed.get("observations", parsed) if isinstance(parsed, Mapping) else parsed
        return tuple(mapping(item, "guide row") for item in sequence(rows, "observations"))
    delimiter = "\t" if mode in {"tsv", "tab"} else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
    return tuple(dict(row) for row in reader)


def evaluate_guide_oligo_adaptation(payload: Mapping[str, Any]) -> PlanningOperationResult:
    operation = PlanningOperation.GUIDE_OLIGO
    try:
        source_id = required_text(payload.get("source_id"), "source_id")
        source_version = required_text(payload.get("source_version", "unspecified"), "source_version")
        context = str(payload.get("context_key", PLANNING_FRONTIER_CONTEXT_KEY))
        input_format = str(payload.get("input_format", "")) or None
        rows = _parse_guide_rows(str(payload.get("text") or ""), input_format)
        issues: list[str] = []
        observations: list[dict[str, Any]] = []
        quarantined: list[dict[str, Any]] = []
        for index, row in enumerate(rows, start=1):
            row_issues: list[str] = []
            try:
                observation_id = required_text(row.get("observation_id", row.get("id", f"{source_id}:{index}")), "observation_id")
                design_id = required_text(row.get("design_id", row.get("design")), "design_id")
                target_id = required_text(row.get("target_id", row.get("target")), "target_id")
                oligo_id = required_text(row.get("oligo_id", row.get("guide_id", f"oligo:{index}")), "oligo_id")
                sequence_value = dna(row.get("sequence", row.get("guide_sequence")), "sequence")
                row_context = required_text(row.get("context_key", row.get("context")), "context_key")
                if row_context != context:
                    row_issues.append("context_mismatch")
                item = {
                    "observation_id": observation_id,
                    "design_id": design_id,
                    "target_id": target_id,
                    "oligo_id": oligo_id,
                    "oligo_type": str(row.get("oligo_type", row.get("type", "guide"))),
                    "sequence": sequence_value,
                    "sequence_length": len(sequence_value),
                    "context_key": row_context,
                    "strand": str(row.get("strand", "unspecified")),
                    "start_offset": int(row.get("start_offset", row.get("offset", 0)) or 0),
                    "pam": str(row.get("pam", "")),
                    "source_id": source_id,
                    "source_version": source_version,
                    "row_address": address(row, prefix="guide-row"),
                    "issue_codes": issue_codes(row_issues),
                }
                if item["start_offset"] < 0:
                    row_issues.append("negative_start_offset")
                item["issue_codes"] = issue_codes(row_issues)
                if row_issues:
                    quarantined.append(item)
                else:
                    observations.append(item)
                issues.extend(row_issues)
            except (TypeError, ValueError, KeyError) as exc:
                issue = {"row_number": index, "issue_code": "invalid_guide_oligo_row", "detail": str(exc), "row_address": address(row, prefix="guide-invalid")}
                quarantined.append(issue)
                issues.append("invalid_guide_oligo_row")
        if not rows:
            issues.append("empty_source")
        state = (
            PlanningState.ABSTAINED if not rows
            else PlanningState.BLOCKED if "context_mismatch" in issues and not observations
            else PlanningState.REVIEW if issues
            else PlanningState.READY_FOR_REVIEW
        )
        output = {
            "source_id": source_id,
            "source_version": source_version,
            "context_key": context,
            "input_format": input_format or "csv",
            "input_row_count": len(rows),
            "accepted_observation_count": len(observations),
            "quarantined_row_count": len(quarantined),
            "observations": observations,
            "quarantined": quarantined,
            "input_address": address(payload.get("text", ""), prefix="guide-input"),
        }
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return _invalid(operation, ("source_id", "source_version", "input_format", "text", "context_key"))


def evaluate_controls_randomization(payload: Mapping[str, Any]) -> PlanningOperationResult:
    operation = PlanningOperation.CONTROLS_RANDOMIZATION
    try:
        plan_id = required_text(payload.get("plan_id"), "plan_id")
        context = _context(payload, issues := [])
        seed = required_text(payload.get("randomization_seed"), "randomization_seed")
        controls = unique_text(sequence(payload.get("control_types", ()), "control_types"), "control_types")
        biological = positive_integer(payload.get("biological_replicates", 1), "biological_replicates")
        technical = positive_integer(payload.get("technical_replicates", 1), "technical_replicates")
        targets = sequence(payload.get("targets", ()), "targets")
        if not controls:
            issues.append("control_types_missing")
        if not targets:
            issues.append("no_targets")
        assignments: list[dict[str, Any]] = []
        target_ids: list[str] = []
        for index, raw in enumerate(targets, start=1):
            row = mapping(raw, f"targets[{index}]")
            target_id = str(row.get("target_id", row.get("id", ""))).strip()
            if not target_id:
                issues.append("missing_target_id")
                continue
            target_ids.append(target_id)
            row_context = str(row.get("context_key", context))
            if row_context != context:
                issues.append("context_mismatch")
                continue
            condition = str(row.get("condition", "target")).strip() or "target"
            for control in controls:
                for bio in range(1, biological + 1):
                    for tech in range(1, technical + 1):
                        key = address({"seed": seed, "target": target_id, "condition": condition, "control": control, "biological": bio, "technical": tech}, prefix="randomization")
                        assignments.append({
                            "assignment_id": address({"plan_id": plan_id, "key": key}, prefix="assignment"),
                            "target_id": target_id,
                            "condition": condition,
                            "control_type": control,
                            "biological_replicate": bio,
                            "technical_replicate": tech,
                            "randomization_key": key,
                            "context_key": context,
                        })
        assignments.sort(key=lambda item: (item["randomization_key"], item["assignment_id"]))
        state = (
            PlanningState.BLOCKED if "context_mismatch" in issues
            else PlanningState.ABSTAINED if not targets
            else PlanningState.REVIEW if issues
            else PlanningState.READY_FOR_REVIEW
        )
        output = {
            "plan_id": plan_id,
            "context_key": context,
            "randomization_seed": seed,
            "control_types": controls,
            "biological_replicates": biological,
            "technical_replicates": technical,
            "target_ids": tuple(dict.fromkeys(target_ids)),
            "assignment_count": len(assignments),
            "assignments": assignments,
            "plan_address": address({"plan_id": plan_id, "assignments": assignments}, prefix="control-plan"),
        }
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("plan_id", "context_key", "targets", "control_types", "biological_replicates", "technical_replicates", "randomization_seed"))


def _normal_quantile(probability: float) -> float:
    """Acklam-style inverse normal approximation with deterministic constants."""

    p = bounded_fraction(probability, "probability")
    a = (-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924)
    b = (-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857)
    c = (-0.00778489400243029, -0.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878)
    d = (0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742)
    if p < 0.02425:
        q = math.sqrt(-2 * math.log(p))
        numerator = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        denominator = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
        return numerator / denominator
    if p > 1 - 0.02425:
        return -_normal_quantile(1 - p)
    q = p - 0.5
    r = q * q
    numerator = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
    denominator = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    return numerator / denominator


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def evaluate_power_replication(payload: Mapping[str, Any]) -> PlanningOperationResult:
    operation = PlanningOperation.POWER_REPLICATION
    try:
        request_id = required_text(payload.get("request_id"), "request_id")
        context = _context(payload, issues := [])
        observations = sequence(payload.get("observations", ()), "observations")
        if not observations:
            issues.append("no_power_observations")
        parsed: list[dict[str, Any]] = []
        for index, raw in enumerate(observations, start=1):
            try:
                row = mapping(raw, f"observations[{index}]")
                observation = {
                    "observation_id": required_text(row.get("observation_id", row.get("id")), "observation_id"),
                    "design_id": required_text(row.get("design_id"), "design_id"),
                    "assay_id": required_text(row.get("assay_id"), "assay_id"),
                    "effect_size": finite_number(row.get("effect_size"), "effect_size"),
                    "variance": finite_number(row.get("variance"), "variance"),
                    "alpha": bounded_fraction(row.get("alpha"), "alpha"),
                    "target_power": bounded_fraction(row.get("target_power"), "target_power"),
                    "planned_replicates": positive_integer(row.get("planned_replicates"), "planned_replicates"),
                    "blocking_factor_count": positive_integer(row.get("blocking_factor_count", 1), "blocking_factor_count"),
                    "context_key": required_text(row.get("context_key"), "context_key"),
                    "source_id": required_text(row.get("source_id", "public-aggregate"), "source_id"),
                }
                if observation["effect_size"] == 0 or observation["variance"] <= 0:
                    raise ValueError("effect_size must be non-zero and variance positive")
                if observation["context_key"] != context:
                    issues.append("context_mismatch")
                    continue
                parsed.append(observation)
            except (TypeError, ValueError, KeyError):
                issues.append("invalid_power_row")
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in parsed:
            grouped.setdefault((row["design_id"], row["assay_id"]), []).append(row)
        results: list[dict[str, Any]] = []
        for (design_id, assay_id), rows in sorted(grouped.items()):
            effect = sum(row["effect_size"] for row in rows) / len(rows)
            variance = sum(row["variance"] for row in rows) / len(rows)
            alpha = sum(row["alpha"] for row in rows) / len(rows)
            target_power = sum(row["target_power"] for row in rows) / len(rows)
            planned = max(row["planned_replicates"] for row in rows)
            blocking = max(row["blocking_factor_count"] for row in rows)
            z_alpha = _normal_quantile(1 - alpha / 2)
            z_power = _normal_quantile(target_power)
            required = max(2, math.ceil(2 * (z_alpha + z_power) ** 2 * variance / (effect * effect)) * blocking)
            achieved = _normal_cdf(math.sqrt(planned / (2 * variance)) * abs(effect) - z_alpha)
            shortfall = max(0, required - planned)
            results.append({
                "design_id": design_id,
                "assay_id": assay_id,
                "observation_count": len(rows),
                "effect_size": round(effect, 8),
                "variance": round(variance, 8),
                "alpha": round(alpha, 8),
                "target_power": round(target_power, 8),
                "planned_replicates": planned,
                "required_replicates": required,
                "achieved_power": round(achieved, 8),
                "replicate_shortfall": shortfall,
                "blocking_factor_count": blocking,
                "state": "ready_for_review" if shortfall == 0 else "review",
                "assumptions": ("two-sided normal approximation", "independent variance proxy", "blocking factor multiplies requirement"),
                "estimate_address": address({"design_id": design_id, "assay_id": assay_id, "required": required}, prefix="power-estimate"),
            })
        if parsed and not results:
            issues.append("no_context_matched_power_observations")
        state = (
            PlanningState.BLOCKED if "context_mismatch" in issues and not results
            else PlanningState.ABSTAINED if not observations
            else PlanningState.REVIEW if issues or any(item["replicate_shortfall"] for item in results)
            else PlanningState.READY_FOR_REVIEW
        )
        output = {
            "request_id": request_id,
            "context_key": context,
            "observation_count": len(observations),
            "parsed_observation_count": len(parsed),
            "result_count": len(results),
            "results": results,
            "estimate_address": address({"request_id": request_id, "results": results}, prefix="power-package"),
        }
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("request_id", "context_key", "observations"))


def run_planning_operation(operation: PlanningOperation, payload: Mapping[str, Any]) -> PlanningOperationResult:
    dispatch = {
        PlanningOperation.MODEL_ELIGIBILITY: evaluate_model_system_eligibility,
        PlanningOperation.GUIDE_OLIGO: evaluate_guide_oligo_adaptation,
        PlanningOperation.CONTROLS_RANDOMIZATION: evaluate_controls_randomization,
        PlanningOperation.POWER_REPLICATION: evaluate_power_replication,
    }
    selected = operation if isinstance(operation, PlanningOperation) else PlanningOperation(str(operation))
    return dispatch[selected](mapping(payload, "payload"))


__all__ = [
    "evaluate_controls_randomization",
    "evaluate_guide_oligo_adaptation",
    "evaluate_model_system_eligibility",
    "evaluate_power_replication",
    "run_planning_operation",
]
