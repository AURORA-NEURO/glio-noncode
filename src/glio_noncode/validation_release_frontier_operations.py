"""Independent operation adapters for D13 C13-C16."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import jsonable
from .validation_release_frontier_contracts import (
    VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY,
    ValidationReleaseOperation,
    ValidationReleaseOperationResult,
    ValidationReleaseState,
)
from .validation_release_frontier_support import (
    address,
    bounded,
    context_matches,
    mapping,
    normalized_issue_codes,
    positive_number,
    required_text,
    safe_output,
    sequence,
)


def _result(operation: ValidationReleaseOperation, state: ValidationReleaseState, codes: Sequence[str], output: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    normalized = normalized_issue_codes(codes)
    body = {"operation": operation, "state": state, "issue_codes": normalized, "output": safe_output(output)}
    return ValidationReleaseOperationResult(**body, content_address=address(body))


def evaluate_off_target_risk(payload: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    operation = ValidationReleaseOperation.OFF_TARGET_RISK
    issues: list[str] = []
    try:
        target_id = required_text(payload.get("target_id"), "target_id")
        context = payload.get("context_key")
        on_target = bounded(payload.get("on_target_score"), "on_target_score")
        candidates = sequence(payload.get("off_targets", ()), "off_targets")
        scores: list[float] = []
        weighted_terms: list[float] = []
        total_weight = 0.0
        for index, raw in enumerate(candidates, start=1):
            candidate = mapping(raw, f"off_targets[{index}]")
            score = bounded(candidate.get("score"), f"off_targets[{index}].score")
            weight = positive_number(candidate.get("weight", 1.0), f"off_targets[{index}].weight")
            scores.append(score)
            weighted_terms.append(score * weight)
            total_weight += weight
        maximum = max(scores, default=0.0)
        weighted = sum(weighted_terms) / total_weight if total_weight else 0.0
        if not context_matches(context, VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        if maximum >= float(payload.get("blocking_threshold", 0.6)):
            issues.append("off_target_risk_high")
        elif weighted >= float(payload.get("review_threshold", 0.25)):
            issues.append("off_target_risk_review")
        state = ValidationReleaseState.BLOCKED if "context_mismatch" in issues or "off_target_risk_high" in issues else ValidationReleaseState.REVIEW if issues else ValidationReleaseState.READY
        output = {"target_id": target_id, "on_target_score": round(on_target, 6), "maximum_off_target_score": round(maximum, 6), "weighted_off_target_score": round(weighted, 6), "specificity": round(max(0.0, on_target - maximum), 6), "candidate_count": len(scores), "risk_tier": "high" if maximum >= 0.6 else "review" if weighted >= 0.25 else "low"}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _result(operation, ValidationReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": ("target_id", "context_key", "on_target_score", "off_targets")})


def _has_cycle(graph: Mapping[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(dep) for dep in graph.get(node, ()) if dep in graph):
            return True
        visiting.remove(node)
        visited.add(node)
        return False
    return any(visit(node) for node in graph)


def evaluate_value_of_information(payload: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    operation = ValidationReleaseOperation.VALUE_OF_INFORMATION
    try:
        context = payload.get("context_key")
        budget = positive_number(payload.get("budget"), "budget")
        rows = sequence(payload.get("experiments", ()), "experiments")
        parsed: list[dict[str, Any]] = []
        ids: set[str] = set()
        for index, raw in enumerate(rows, start=1):
            row = mapping(raw, f"experiments[{index}]")
            experiment_id = required_text(row.get("experiment_id"), f"experiments[{index}].experiment_id")
            if experiment_id in ids:
                return _result(operation, ValidationReleaseState.REVIEW, ("duplicate_experiment_id",), {"experiment_count": len(rows)})
            ids.add(experiment_id)
            parsed.append({"id": experiment_id, "cost": positive_number(row.get("cost"), f"{experiment_id}.cost"), "information": bounded(row.get("information_gain"), f"{experiment_id}.information_gain"), "risk": bounded(row.get("risk_reduction"), f"{experiment_id}.risk_reduction"), "prerequisites": tuple(str(item) for item in sequence(row.get("prerequisites", ()), f"{experiment_id}.prerequisites"))})
        if not context_matches(context, VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY):
            return _result(operation, ValidationReleaseState.BLOCKED, ("context_mismatch",), {"experiment_count": len(parsed)})
        graph = {item["id"]: item["prerequisites"] for item in parsed}
        missing = tuple(sorted({dep for deps in graph.values() for dep in deps if dep not in graph}))
        if missing:
            return _result(operation, ValidationReleaseState.REVIEW, ("missing_prerequisite",), {"missing_prerequisites": missing, "experiment_count": len(parsed)})
        if _has_cycle(graph):
            return _result(operation, ValidationReleaseState.BLOCKED, ("prerequisite_cycle",), {"experiment_count": len(parsed)})
        remaining = budget
        selected: list[dict[str, Any]] = []
        selected_ids: set[str] = set()
        pending = list(parsed)
        while pending:
            eligible = [item for item in pending if all(dep in selected_ids for dep in item["prerequisites"])]
            if not eligible:
                break
            item = sorted(eligible, key=lambda value: (-(value["information"] + value["risk"]) / value["cost"], value["id"]))[0]
            pending.remove(item)
            if item["cost"] <= remaining:
                selected.append(item)
                selected_ids.add(item["id"])
                remaining -= item["cost"]
        state = ValidationReleaseState.READY if selected else ValidationReleaseState.REVIEW
        output = {"plan_id": required_text(payload.get("plan_id"), "plan_id"), "budget": round(budget, 6), "selected_ids": tuple(item["id"] for item in selected), "total_cost": round(sum(item["cost"] for item in selected), 6), "total_information_gain": round(sum(item["information"] for item in selected), 6), "total_risk_reduction": round(sum(item["risk"] for item in selected), 6), "experiment_count": len(parsed), "remaining_budget": round(remaining, 6)}
        return _result(operation, state, (), output)
    except (TypeError, ValueError, KeyError):
        return _result(operation, ValidationReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": ("plan_id", "context_key", "budget", "experiments")})


def evaluate_experiment_package(payload: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    operation = ValidationReleaseOperation.EXPERIMENT_PACKAGE
    try:
        package_id = required_text(payload.get("package_id"), "package_id")
        context = payload.get("context_key")
        experiments = sequence(payload.get("experiments", ()), "experiments")
        controls = sequence(payload.get("controls", ()), "controls")
        protocols = sequence(payload.get("protocols", ()), "protocols")
        if not context_matches(context, VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY):
            return _result(operation, ValidationReleaseState.BLOCKED, ("context_mismatch",), {"package_id": package_id})
        if not experiments:
            return _result(operation, ValidationReleaseState.REJECTED, ("experiments_missing",), {"package_id": package_id})
        def ids(items: Sequence[Any], field: str) -> tuple[str, ...]:
            values = tuple(required_text(mapping(item, field).get(field[:-1] if field.endswith("s") else field), field) for item in items)
            return values
        experiment_ids = tuple(required_text(mapping(item, "experiment").get("experiment_id"), "experiment_id") for item in experiments)
        control_ids = tuple(required_text(mapping(item, "control").get("control_id"), "control_id") for item in controls)
        protocol_ids = tuple(required_text(mapping(item, "protocol").get("protocol_id"), "protocol_id") for item in protocols)
        all_ids = experiment_ids + control_ids + protocol_ids
        duplicates = tuple(sorted({item for item in all_ids if all_ids.count(item) > 1}))
        if duplicates:
            return _result(operation, ValidationReleaseState.REVIEW, ("duplicate_package_id",), {"package_id": package_id, "duplicate_ids": duplicates})
        files = {}
        for name, rows in (("experiments.json", experiments), ("controls.json", controls), ("protocols.json", protocols)):
            if rows:
                content = jsonable(rows)
                files[name] = {"row_count": len(rows), "content_address": address(content)}
        manifest = {"package_id": package_id, "context_key": context, "experiment_ids": experiment_ids, "control_ids": control_ids, "protocol_ids": protocol_ids, "files": files}
        return _result(operation, ValidationReleaseState.PACKAGED, (), manifest | {"manifest_address": address(manifest)})
    except (TypeError, ValueError, KeyError):
        return _result(operation, ValidationReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": ("package_id", "context_key", "experiments", "controls", "protocols")})


def evaluate_claim_update(payload: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    operation = ValidationReleaseOperation.CLAIM_UPDATE
    try:
        context = payload.get("context_key")
        claims = sequence(payload.get("claims", ()), "claims")
        results = sequence(payload.get("results", ()), "results")
        claim_map = {required_text(mapping(item, "claim").get("claim_id"), "claim_id"): mapping(item, "claim") for item in claims}
        updated: list[str] = []
        review: list[str] = []
        issues: list[str] = []
        for raw in results:
            result = mapping(raw, "result")
            claim_id = required_text(result.get("claim_id"), "claim_id")
            if not context_matches(result.get("context_key"), VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY) or not context_matches(context, VALIDATION_RELEASE_FRONTIER_CONTEXT_KEY):
                issues.append("context_mismatch")
                review.append(claim_id)
                continue
            if claim_id not in claim_map:
                issues.append("unknown_claim")
                review.append(claim_id)
                continue
            evidence_address = result.get("evidence_address")
            if not isinstance(evidence_address, str) or not evidence_address.startswith("sha256:"):
                issues.append("evidence_address_missing")
                review.append(claim_id)
                continue
            updated.append(claim_id)
        state = ValidationReleaseState.BLOCKED if "context_mismatch" in issues else ValidationReleaseState.UPDATED if updated and not issues else ValidationReleaseState.REVIEW if review or issues else ValidationReleaseState.REVIEW
        output = {"updated_ids": tuple(updated), "review_ids": tuple(review), "result_count": len(results), "claim_count": len(claim_map), "issue_codes": normalized_issue_codes(issues)}
        return _result(operation, state, normalized_issue_codes(issues), output)
    except (TypeError, ValueError, KeyError):
        return _result(operation, ValidationReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": ("context_key", "claims", "results")})


def run_validation_release_operation(operation: ValidationReleaseOperation, payload: Mapping[str, Any]) -> ValidationReleaseOperationResult:
    dispatch = {ValidationReleaseOperation.OFF_TARGET_RISK: evaluate_off_target_risk, ValidationReleaseOperation.VALUE_OF_INFORMATION: evaluate_value_of_information, ValidationReleaseOperation.EXPERIMENT_PACKAGE: evaluate_experiment_package, ValidationReleaseOperation.CLAIM_UPDATE: evaluate_claim_update}
    return dispatch[operation](mapping(payload, "payload"))


__all__ = ["evaluate_claim_update", "evaluate_experiment_package", "evaluate_off_target_risk", "evaluate_value_of_information", "run_validation_release_operation"]
