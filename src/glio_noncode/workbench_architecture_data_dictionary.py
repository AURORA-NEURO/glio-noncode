"""Field dictionary for D15 public aggregate records."""

from __future__ import annotations

from .workbench_architecture_contracts import WorkbenchArchitectureFixture
from .workbench_architecture_public_data import default_workbench_architecture_fixture


def workbench_architecture_data_dictionary(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> tuple[dict[str, object], ...]:
    selected = fixture or default_workbench_architecture_fixture()
    fields = (
        ("fixture_id", "string", "stable aggregate fixture identifier", "fixture"),
        ("source_id", "string", "namespaced source receipt identifier", "source"),
        ("operation_id", "string", "D15 capability operation join key", "operation"),
        ("case_id", "string", "scenario-specific execution join key", "case"),
        ("family", "enum", "delegate family boundary", "case"),
        ("plane", "enum", "workspace or release plane", "case"),
        ("scenario", "enum", "positive or control path", "case"),
        ("aggregate_context_key", "string", "aggregate evaluation context", "case"),
        ("delegate_context_key", "string", "retained family context or control context", "case"),
        ("expected_state", "enum", "state required by the case contract", "case"),
        ("expected_issue_codes", "tuple[string]", "visible issue vocabulary", "case"),
        ("expected_counts", "mapping[string,int]", "bounded payload and output counts", "case"),
        ("content_address", "string", "deterministic integrity address", "all"),
    )
    return tuple(
        {
            "field": field,
            "type": field_type,
            "meaning": meaning,
            "scope": scope,
            "fixture_id": selected.fixture_id,
        }
        for field, field_type, meaning, scope in fields
    )


def workbench_architecture_data_dictionary_summary(
    fixture: WorkbenchArchitectureFixture | None = None,
) -> dict[str, object]:
    rows = workbench_architecture_data_dictionary(fixture)
    return {"field_count": len(rows), "fields": [item["field"] for item in rows]}


__all__ = [
    "workbench_architecture_data_dictionary",
    "workbench_architecture_data_dictionary_summary",
]
