"""Independent review, export, search, and accessibility operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .serialization import canonical_json
from .workbench_release_frontier_contracts import WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY, WorkbenchReleaseOperation, WorkbenchReleaseOperationResult, WorkbenchReleaseState
from .workbench_release_frontier_support import address, boolean, context_matches, duplicate_values, mapping, normalized_issue_codes, required_text, safe_output, sequence


def _result(operation: WorkbenchReleaseOperation, state: WorkbenchReleaseState, codes: Sequence[str], output: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    issues = normalized_issue_codes(codes)
    projected = safe_output(output)
    body = {"operation": operation, "state": state, "issue_codes": issues, "output": projected}
    return WorkbenchReleaseOperationResult(**body, content_address=address(body))


def _invalid(operation: WorkbenchReleaseOperation, fields: Sequence[str]) -> WorkbenchReleaseOperationResult:
    return _result(operation, WorkbenchReleaseState.REJECTED, ("invalid_payload",), {"accepted_fields": tuple(fields)})


def evaluate_review_form(payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    operation = WorkbenchReleaseOperation.REVIEW_FORM
    try:
        form_id = required_text(payload.get("form_id"), "form_id")
        reviewer_id = required_text(payload.get("reviewer_id"), "reviewer_id")
        context = payload.get("context_key")
        schema = sequence(payload.get("schema", ()), "schema")
        response = mapping(payload.get("response", {}), "response")
        issues: list[str] = []
        if not context_matches(context, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        fields: list[dict[str, Any]] = []
        for index, raw in enumerate(schema, start=1):
            field = mapping(raw, f"schema[{index}]")
            field_id = required_text(field.get("field_id", field.get("id")), f"schema[{index}].field_id")
            label = required_text(field.get("label", field_id), f"schema[{index}].label")
            required = bool(field.get("required", False))
            value = response.get(field_id)
            valid = value is not None and (not isinstance(value, str) or bool(value.strip()))
            field_issue = None
            if required and not valid:
                field_issue = "required_field_missing"
                issues.append(field_issue)
            choices = field.get("choices")
            if valid and choices is not None and value not in sequence(choices, f"schema[{index}].choices"):
                valid = False
                field_issue = "value_not_in_declared_choices"
                issues.append(field_issue)
            fields.append({"field_id": field_id, "label": label, "required": required, "valid": valid, "issue": field_issue, "value_present": value is not None})
        valid_count = sum(item["valid"] for item in fields)
        required_count = sum(item["required"] for item in fields)
        completion = round(valid_count / max(1, len(fields)), 6)
        state = WorkbenchReleaseState.BLOCKED if "context_mismatch" in issues else WorkbenchReleaseState.REVIEW if issues or valid_count < required_count else WorkbenchReleaseState.REVIEWED
        output = {"form_id": form_id, "reviewer_id": reviewer_id, "field_count": len(fields), "required_count": required_count, "valid_count": valid_count, "completion": completion, "fields": tuple(fields), "response_address": address(response)}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("form_id", "reviewer_id", "context_key", "schema", "response"))


def evaluate_report_export(payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    operation = WorkbenchReleaseOperation.REPORT_EXPORT
    try:
        report_id = required_text(payload.get("report_id"), "report_id")
        context = payload.get("context_key")
        output_format = required_text(payload.get("format", "json"), "format").lower()
        sections = sequence(payload.get("sections", ()), "sections")
        issues: list[str] = []
        if not context_matches(context, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        if output_format not in {"json", "markdown", "csv"}:
            issues.append("unsupported_format")
        rendered: list[dict[str, Any]] = []
        ids: list[str] = []
        for index, raw in enumerate(sections, start=1):
            row = mapping(raw, f"sections[{index}]")
            section_id = required_text(row.get("section_id", row.get("id")), f"sections[{index}].section_id")
            title = required_text(row.get("title", section_id), f"sections[{index}].title")
            order = int(row.get("order", index))
            content = row.get("content", row.get("records", ()))
            if output_format == "markdown":
                projection = {"markdown": f"## {title}\n\n{canonical_json(content)}"}
            elif output_format == "csv":
                projection = {"rows": content}
            else:
                projection = {"content": content}
            ids.append(section_id)
            rendered.append({"section_id": section_id, "title": title, "order": order, "content": projection, "line_count": len(canonical_json(projection).splitlines()), "content_address": address(projection)})
        duplicates = duplicate_values(ids)
        if duplicates:
            issues.append("duplicate_section_id")
        ordered = tuple(sorted(rendered, key=lambda item: (item["order"], item["section_id"])))
        if not ordered:
            issues.append("sections_missing")
        state = WorkbenchReleaseState.BLOCKED if "context_mismatch" in issues else WorkbenchReleaseState.REVIEW if issues else WorkbenchReleaseState.EXPORTED
        manifest = {"report_id": report_id, "context_key": context, "format": output_format, "sections": ordered}
        return _result(operation, state, issues, manifest | {"report_address": address(manifest)})
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("report_id", "context_key", "format", "sections"))


def evaluate_search_palette(payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    operation = WorkbenchReleaseOperation.SEARCH_PALETTE
    try:
        query = required_text(payload.get("query"), "query").lower()
        context = payload.get("context_key")
        records = sequence(payload.get("records", ()), "records")
        commands = tuple(required_text(value, "command") for value in sequence(payload.get("commands", ()), "commands"))
        maximum = int(payload.get("maximum_results", 20))
        if maximum < 1:
            raise ValueError("maximum_results must be positive")
        issues: list[str] = []
        if not context_matches(context, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        found: list[dict[str, Any]] = []
        for index, raw in enumerate(records, start=1):
            row = mapping(raw, f"records[{index}]")
            row_context = row.get("context_key", context)
            if not context_matches(row_context, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY):
                issues.append("context_mismatch")
                continue
            record_id = required_text(row.get("record_id", row.get("id")), f"records[{index}].record_id")
            record_type = required_text(row.get("record_type", row.get("type", "record")), f"records[{index}].record_type")
            matched: list[str] = []
            score = 0.0
            for field, value in row.items():
                if query in str(value).lower():
                    matched.append(str(field))
                    score += 2.0 if str(field) in {"record_id", "id", "title", "name"} else 1.0
            if matched:
                found.append({"record_id": record_id, "record_type": record_type, "title": str(row.get("title", record_id)), "matched_fields": tuple(sorted(matched)), "score": round(score, 6), "command": None})
        command_matches = tuple(sorted(command for command in commands if query in command.lower()))
        found.extend({"record_id": f"command:{command}", "record_type": "command", "title": command, "matched_fields": ("command",), "score": 3.0, "command": command} for command in command_matches)
        found.sort(key=lambda item: (-item["score"], item["record_type"], item["record_id"]))
        if not found and "context_mismatch" not in issues:
            issues.append("no_matches")
        state = WorkbenchReleaseState.BLOCKED if "context_mismatch" in issues else WorkbenchReleaseState.REVIEW if issues else WorkbenchReleaseState.SEARCHED
        output = {"query": query, "results": tuple(found[:maximum]), "command_matches": command_matches, "result_count": min(len(found), maximum), "search_address": address(found[:maximum])}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("query", "context_key", "records", "commands", "maximum_results"))


def evaluate_accessibility(payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    operation = WorkbenchReleaseOperation.ACCESSIBILITY
    criteria_names = ("keyboard", "label", "focus_order", "contrast", "motion", "reading_order")
    try:
        surface_id = required_text(payload.get("surface_id"), "surface_id")
        context = payload.get("context_key")
        surface = mapping(payload.get("surface", {}), "surface")
        requested = tuple(required_text(value, "criterion") for value in sequence(payload.get("required_criteria", criteria_names), "required_criteria"))
        issues: list[str] = []
        if not context_matches(context, WORKBENCH_RELEASE_FRONTIER_CONTEXT_KEY):
            issues.append("context_mismatch")
        findings: list[dict[str, Any]] = []
        for criterion in requested:
            value = surface.get(criterion)
            passed = value is True
            if not passed:
                issues.append("criterion_failed")
            findings.append({"criterion": criterion, "passed": passed, "severity": "info" if passed else "blocking", "message": "criterion passed" if passed else "criterion requires remediation"})
        pass_count = sum(item["passed"] for item in findings)
        score = round(pass_count / max(1, len(findings)), 6)
        state = WorkbenchReleaseState.BLOCKED if "context_mismatch" in issues else WorkbenchReleaseState.REVIEW if issues else WorkbenchReleaseState.PASSED
        output = {"surface_id": surface_id, "criteria": tuple(findings), "pass_count": pass_count, "fail_count": len(findings) - pass_count, "score": score, "surface_address": address(surface)}
        return _result(operation, state, issues, output)
    except (TypeError, ValueError, KeyError):
        return _invalid(operation, ("surface_id", "context_key", "surface", "required_criteria"))


def run_workbench_release_operation(operation: WorkbenchReleaseOperation, payload: Mapping[str, Any]) -> WorkbenchReleaseOperationResult:
    dispatch = {WorkbenchReleaseOperation.REVIEW_FORM: evaluate_review_form, WorkbenchReleaseOperation.REPORT_EXPORT: evaluate_report_export, WorkbenchReleaseOperation.SEARCH_PALETTE: evaluate_search_palette, WorkbenchReleaseOperation.ACCESSIBILITY: evaluate_accessibility}
    return dispatch[operation](mapping(payload, "payload"))


__all__ = ["evaluate_accessibility", "evaluate_report_export", "evaluate_review_form", "evaluate_search_palette", "run_workbench_release_operation"]
