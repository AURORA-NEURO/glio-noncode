"""Functional planners for CRISPR, base-edit, prime-edit, and reporter designs."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from .serialization import content_hash
from .editing_design_frontier_contracts import EDITING_DESIGN_FRONTIER_CONTEXT_KEY, EditingDesignOperation, EditingDesignOperationResult, EditingDesignState
from .editing_design_frontier_support import address, context_matches, dna, issue_codes, mapping, non_negative_integer, positive_integer, required_text, safe_output, sequence

def _result(operation: EditingDesignOperation, state: EditingDesignState, codes: list[str], output: Mapping[str, Any]) -> EditingDesignOperationResult:
    normalized = issue_codes(codes); projected = safe_output(output); body = {"operation": operation, "state": state, "issue_codes": normalized, "output": projected}
    return EditingDesignOperationResult(**body, content_address=address(body))

def _invalid(operation: EditingDesignOperation, fields: tuple[str, ...]) -> EditingDesignOperationResult:
    return _result(operation, EditingDesignState.REJECTED, ["invalid_payload"], {"accepted_fields": fields})

def _contexts(payload: Mapping[str, Any], issues: list[str]) -> str:
    context = payload.get("context_key")
    if not context_matches(context, EDITING_DESIGN_FRONTIER_CONTEXT_KEY): issues.append("context_mismatch")
    return str(context or "")

def _controls(payload: Mapping[str, Any], issues: list[str]) -> tuple[str, ...]:
    values = sequence(payload.get("controls", ()), "controls")
    controls = tuple(required_text(item, "controls") for item in values)
    if not controls: issues.append("controls_missing")
    return controls

def _readouts(payload: Mapping[str, Any], issues: list[str]) -> tuple[str, ...]:
    values = sequence(payload.get("readouts", ()), "readouts")
    readouts = tuple(required_text(item, "readouts") for item in values)
    if not readouts: issues.append("readouts_missing")
    return readouts

def evaluate_crispr_design(payload: Mapping[str, Any]) -> EditingDesignOperationResult:
    operation = EditingDesignOperation.CRISPR_DESIGN
    try:
        design_id = required_text(payload.get("design_id"), "design_id"); context = _contexts(payload, issues := [])
        targets = sequence(payload.get("targets", ()), "targets"); modes = tuple(required_text(item, "modes") for item in sequence(payload.get("modes", ()), "modes")); guide_length = positive_integer(payload.get("guide_length", 20), "guide_length"); max_guides = positive_integer(payload.get("max_guides", 4), "max_guides"); controls = _controls(payload, issues); readouts = _readouts(payload, issues)
        if not targets: issues.append("targets_missing")
        if not modes or any(mode not in {"crispri", "crispra"} for mode in modes): issues.append("mode_unsupported")
        candidates = []
        for index, raw in enumerate(targets, start=1):
            row = mapping(raw, f"targets[{index}]"); target_id = required_text(row.get("target_id"), f"targets[{index}].target_id"); sequence_value = dna(row.get("sequence"), f"targets[{index}].sequence")
            if row.get("context_key") not in (None, context): issues.append("context_mismatch")
            if len(sequence_value) < guide_length: issues.append("sequence_short"); continue
            starts = tuple(dict.fromkeys((0, max(0, (len(sequence_value) - guide_length) // 2), len(sequence_value) - guide_length)))
            for start in starts[:max_guides]:
                guide = sequence_value[start:start + guide_length]; gc = (guide.count("G") + guide.count("C")) / max(1, len(guide)); candidates.append({"target_id": target_id, "start": start, "guide_sequence": guide, "gc_fraction": round(gc, 6), "candidate_address": address({"target_id": target_id, "start": start, "guide": guide})})
        if len(candidates) > max_guides: issues.append("guide_budget_exceeded")
        state = EditingDesignState.BLOCKED if "context_mismatch" in issues else EditingDesignState.REVIEW if issues else EditingDesignState.DESIGNED
        output = {"design_id": design_id, "context_key": context, "modes": modes, "target_count": len(targets), "candidate_count": len(candidates), "candidates": candidates[:max_guides], "controls": controls, "readouts": readouts, "design_address": address({"design_id": design_id, "candidates": candidates[:max_guides]})}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("design_id", "context_key", "targets", "modes", "guide_length", "max_guides", "controls", "readouts"))

def _single_edit(payload: Mapping[str, Any], operation: EditingDesignOperation, *, prime: bool = False) -> EditingDesignOperationResult:
    try:
        design_id = required_text(payload.get("design_id"), "design_id"); context = _contexts(payload, issues := []); targets = sequence(payload.get("targets", ()), "targets"); controls = _controls(payload, issues); readouts = _readouts(payload, issues)
        if not targets: issues.append("targets_missing")
        edits = []
        for index, raw in enumerate(targets, start=1):
            row = mapping(raw, f"targets[{index}]"); target_id = required_text(row.get("target_id"), f"targets[{index}].target_id"); sequence_value = dna(row.get("sequence"), f"targets[{index}].sequence"); reference = dna(row.get("reference"), f"targets[{index}].reference"); alternate = dna(row.get("alternate"), f"targets[{index}].alternate"); offset = non_negative_integer(row.get("variant_offset"), f"targets[{index}].variant_offset")
            if row.get("context_key") not in (None, context): issues.append("context_mismatch")
            if len(reference) != 1 or len(alternate) != 1 or reference == alternate: issues.append("substitution_not_single_base")
            if sequence_value[offset:offset + len(reference)] != reference: issues.append("reference_mismatch")
            if prime:
                maximum = positive_integer(payload.get("max_edit_length", 50), "max_edit_length"); pbs = positive_integer(payload.get("pbs_length", 13), "pbs_length"); rtt = positive_integer(payload.get("rtt_length", 20), "rtt_length"); flank = positive_integer(payload.get("flank_length", len(sequence_value)), "flank_length")
                if len(alternate) > maximum: issues.append("edit_length_exceeded")
                if flank < pbs + rtt: issues.append("flank_shortage")
                edits.append({"target_id": target_id, "variant_offset": offset, "reference": reference, "alternate": alternate, "pbs_length": pbs, "rtt_length": rtt, "flank_length": flank, "edit_address": address({"target_id": target_id, "reference": reference, "alternate": alternate})})
            else:
                window = sequence(row.get("editing_window", payload.get("editing_window", (4, 8))), "editing_window")
                if len(window) != 2: raise ValueError("editing_window must contain two bounds")
                start = non_negative_integer(window[0], "editing_window_start"); end = non_negative_integer(window[1], "editing_window_end")
                if offset < start or offset > end: issues.append("edit_outside_window")
                edits.append({"target_id": target_id, "variant_offset": offset, "reference": reference, "alternate": alternate, "editing_window": (start, end), "edit_address": address({"target_id": target_id, "reference": reference, "alternate": alternate})})
        state = EditingDesignState.BLOCKED if "context_mismatch" in issues else EditingDesignState.REVIEW if issues else EditingDesignState.DESIGNED
        output = {"design_id": design_id, "context_key": context, "target_count": len(targets), "edits": edits, "controls": controls, "readouts": readouts, "package_address": address({"design_id": design_id, "edits": edits})}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("design_id", "context_key", "targets", "controls", "readouts"))

def evaluate_base_editing(payload: Mapping[str, Any]) -> EditingDesignOperationResult: return _single_edit(payload, EditingDesignOperation.BASE_EDITING)
def evaluate_prime_editing(payload: Mapping[str, Any]) -> EditingDesignOperationResult: return _single_edit(payload, EditingDesignOperation.PRIME_EDITING, prime=True)

def evaluate_allele_reporter(payload: Mapping[str, Any]) -> EditingDesignOperationResult:
    operation = EditingDesignOperation.ALLELE_REPORTER
    try:
        design_id = required_text(payload.get("design_id"), "design_id"); context = _contexts(payload, issues := []); constructs = sequence(payload.get("constructs", ()), "constructs"); max_constructs = positive_integer(payload.get("max_constructs", 2), "max_constructs"); controls = _controls(payload, issues); readouts = _readouts(payload, issues); seen = set(); alleles = set(); parsed = []
        if not constructs: issues.append("constructs_missing")
        for index, raw in enumerate(constructs, start=1):
            row = mapping(raw, f"constructs[{index}]"); construct_id = required_text(row.get("construct_id"), f"constructs[{index}].construct_id"); allele = required_text(row.get("allele"), f"constructs[{index}].allele").lower(); sequence_value = dna(row.get("sequence"), f"constructs[{index}].sequence"); seen.add(construct_id); alleles.add(allele); parsed.append({"construct_id": construct_id, "allele": allele, "sequence_length": len(sequence_value), "construct_address": address(row)})
            if row.get("context_key") not in (None, context): issues.append("context_mismatch")
        if len(seen) != len(parsed): issues.append("duplicate_construct_id")
        if len(parsed) > max_constructs: issues.append("construct_budget_exceeded")
        if not {"reference", "alternate"}.issubset(alleles): issues.append("allele_pair_missing")
        state = EditingDesignState.BLOCKED if "context_mismatch" in issues else EditingDesignState.REVIEW if issues else EditingDesignState.DESIGNED
        output = {"design_id": design_id, "context_key": context, "construct_count": len(parsed), "constructs": parsed, "controls": controls, "readouts": readouts, "package_address": address({"design_id": design_id, "constructs": parsed})}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError): return _invalid(operation, ("design_id", "context_key", "constructs", "max_constructs", "controls", "readouts"))

def run_editing_design_operation(operation: EditingDesignOperation, payload: Mapping[str, Any]) -> EditingDesignOperationResult:
    dispatch = {EditingDesignOperation.CRISPR_DESIGN: evaluate_crispr_design, EditingDesignOperation.BASE_EDITING: evaluate_base_editing, EditingDesignOperation.PRIME_EDITING: evaluate_prime_editing, EditingDesignOperation.ALLELE_REPORTER: evaluate_allele_reporter}
    return dispatch[operation](mapping(payload, "payload"))

__all__ = ["evaluate_allele_reporter", "evaluate_base_editing", "evaluate_crispr_design", "evaluate_prime_editing", "run_editing_design_operation"]
