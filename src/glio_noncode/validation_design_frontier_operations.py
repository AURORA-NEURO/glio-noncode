"""Functional evidence-gap, assay-route, MPRA, and STARR-seq planners."""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any
from .validation_design_frontier_contracts import VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY, ValidationDesignOperation, ValidationDesignOperationResult, ValidationDesignState
from .validation_design_frontier_support import address, context_matches, mapping, normalized_issue_codes, positive_integer, required_text, safe_output, sequence

def _result(operation: ValidationDesignOperation, state: ValidationDesignState, codes: Sequence[str], output: Mapping[str, Any]) -> ValidationDesignOperationResult:
    issues = normalized_issue_codes(codes); projected = safe_output(output); body = {"operation": operation, "state": state, "issue_codes": issues, "output": projected}
    return ValidationDesignOperationResult(**body, content_address=address(body))

def _invalid(operation: ValidationDesignOperation, fields: Sequence[str]) -> ValidationDesignOperationResult:
    return _result(operation, ValidationDesignState.REJECTED, ("invalid_payload",), {"accepted_fields": tuple(fields)})

def evaluate_gap_analysis(payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    operation = ValidationDesignOperation.GAP_ANALYSIS
    try:
        target_id = required_text(payload.get("target_id"), "target_id"); context = payload.get("context_key")
        required = tuple(required_text(value, "required_evidence") for value in sequence(payload.get("required_evidence", ()), "required_evidence"))
        available_rows = sequence(payload.get("available_evidence", ()), "available_evidence"); available: dict[str, dict[str, Any]] = {}; issues: list[str] = []
        if not context_matches(context, VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY): issues.append("context_mismatch")
        for index, raw in enumerate(available_rows, start=1):
            row = mapping(raw, f"available_evidence[{index}]"); dimension = required_text(row.get("dimension"), f"available_evidence[{index}].dimension"); state = required_text(row.get("state", "unknown"), f"available_evidence[{index}].state"); available[dimension] = {"state": state, "source_ids": tuple(str(item) for item in sequence(row.get("source_ids", ()), "source_ids"))}
        gaps = tuple(item for item in required if item not in available or available[item]["state"] not in {"supported", "ready"})
        if not required: issues.append("required_evidence_missing")
        if gaps: issues.append("gap_dimensions")
        state = ValidationDesignState.BLOCKED if "context_mismatch" in issues else ValidationDesignState.REVIEW if issues or gaps else ValidationDesignState.READY
        output = {"target_id": target_id, "required_dimensions": required, "available_dimensions": tuple(sorted(available)), "gap_dimensions": gaps, "gap_count": len(gaps), "coverage": round((len(required) - len(gaps)) / max(1, len(required)), 6), "analysis_address": address({"target_id": target_id, "required": required, "available": available})}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("target_id", "context_key", "required_evidence", "available_evidence"))

def evaluate_assay_eligibility(payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    operation = ValidationDesignOperation.ASSAY_ELIGIBILITY
    try:
        target_id = required_text(payload.get("target_id"), "target_id"); context = payload.get("context_key"); requested = required_text(payload.get("requested_assay"), "requested_assay"); capabilities = sequence(payload.get("capabilities", ()), "capabilities"); issues: list[str] = []
        if not context_matches(context, VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY): issues.append("context_mismatch")
        candidates = []
        for index, raw in enumerate(capabilities, start=1):
            row = mapping(raw, f"capabilities[{index}]"); assay = required_text(row.get("assay"), f"capabilities[{index}].assay"); supported = row.get("supported") is True; readouts = tuple(str(value) for value in sequence(row.get("readouts", ()), "readouts")); limits = mapping(row.get("limits", {}), "limits")
            if assay == requested and supported: candidates.append({"assay": assay, "readouts": readouts, "limits": limits, "capability_address": address(row)})
        if not candidates: issues.append("assay_unsupported")
        state = ValidationDesignState.BLOCKED if "context_mismatch" in issues else ValidationDesignState.REVIEW if issues else ValidationDesignState.ROUTED
        output = {"target_id": target_id, "requested_assay": requested, "eligible": bool(candidates), "candidate_count": len(candidates), "routes": tuple(candidates), "route_address": address(candidates)}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("target_id", "context_key", "requested_assay", "capabilities"))

def _reporter_package(payload: Mapping[str, Any], operation: ValidationDesignOperation, required_fields: tuple[str, ...]) -> ValidationDesignOperationResult:
    try:
        package_id = required_text(payload.get("package_id"), "package_id"); context = payload.get("context_key"); rows = sequence(payload.get("constructs", ()), "constructs"); controls = sequence(payload.get("controls", ()), "controls"); budget = positive_integer(payload.get("construct_budget"), "construct_budget"); issues: list[str] = []
        if not context_matches(context, VALIDATION_DESIGN_FRONTIER_CONTEXT_KEY): issues.append("context_mismatch")
        if not rows: issues.append("constructs_missing")
        parsed = []; ids = []
        for index, raw in enumerate(rows, start=1):
            row = mapping(raw, f"constructs[{index}]"); construct_id = required_text(row.get("construct_id"), f"constructs[{index}].construct_id"); ids.append(construct_id); parsed.append(dict(row))
            if any(field not in row for field in required_fields): issues.append("construct_field_missing")
            if row.get("sequence_length", 0) <= 0: issues.append("sequence_length_invalid")
            if operation == ValidationDesignOperation.MPRA_PACKAGE and row.get("reference") == row.get("alternate"): issues.append("allele_unchanged")
            if operation == ValidationDesignOperation.STARRSEQ_PACKAGE and row.get("strand") not in {"+", "-"}: issues.append("construct_field_missing")
        if len(parsed) > budget: issues.append("construct_budget_exceeded")
        if len(set(ids)) != len(ids): issues.append("duplicate_construct_id")
        if not controls: issues.append("controls_missing")
        state = ValidationDesignState.BLOCKED if "context_mismatch" in issues else ValidationDesignState.REVIEW if issues else ValidationDesignState.PACKAGED
        manifest = {"package_id": package_id, "context_key": context, "construct_count": len(parsed), "control_count": len(controls), "construct_ids": tuple(ids), "constructs": tuple(parsed), "budget": budget, "manifest_address": address({"package_id": package_id, "constructs": parsed, "controls": controls})}
        return _result(operation, state, issues, manifest)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("package_id", "context_key", "constructs", "controls", "construct_budget"))

def evaluate_mpra_package(payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    return _reporter_package(payload, ValidationDesignOperation.MPRA_PACKAGE, ("construct_id", "reference", "alternate", "sequence_length"))

def evaluate_starrseq_package(payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    return _reporter_package(payload, ValidationDesignOperation.STARRSEQ_PACKAGE, ("construct_id", "element_id", "strand", "sequence_length"))

def run_validation_design_operation(operation: ValidationDesignOperation, payload: Mapping[str, Any]) -> ValidationDesignOperationResult:
    dispatch = {ValidationDesignOperation.GAP_ANALYSIS: evaluate_gap_analysis, ValidationDesignOperation.ASSAY_ELIGIBILITY: evaluate_assay_eligibility, ValidationDesignOperation.MPRA_PACKAGE: evaluate_mpra_package, ValidationDesignOperation.STARRSEQ_PACKAGE: evaluate_starrseq_package}
    return dispatch[operation](mapping(payload, "payload"))

__all__ = ["evaluate_assay_eligibility", "evaluate_gap_analysis", "evaluate_mpra_package", "evaluate_starrseq_package", "run_validation_design_operation"]
