"""Field-level dictionary for public D06 sequence evidence receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_architecture_contracts import (
    SequenceArchitectureCheck,
    SequenceArchitectureCheckKind,
    SequenceArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class SequenceArchitectureField:
    field_id: str
    entity: str
    name: str
    type_name: str
    required: bool
    semantic_role: str
    allowed_values: tuple[str, ...]
    example: str
    privacy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceArchitectureDataDictionary:
    fixture_id: str
    version: str
    fields: tuple[SequenceArchitectureField, ...]
    checks: tuple[SequenceArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"field_count": len(self.fields), "check_count": len(self.checks)}


def sequence_architecture_data_dictionary(
    fixture: SequenceArchitectureFixture,
) -> SequenceArchitectureDataDictionary:
    fields = _fields()
    checks = (
        _check(
            "dictionary-ids",
            len({item.field_id for item in fields}) == len(fields),
            len({item.field_id for item in fields}),
            len(fields),
            "field IDs are unique",
        ),
        _check(
            "dictionary-entities",
            {item.entity for item in fields}
            == {"source", "operation", "case", "receipt", "review", "ledger", "artifact"},
            sorted({item.entity for item in fields}),
            ["artifact", "case", "ledger", "operation", "receipt", "review", "source"],
            "all persisted sequence entities are represented",
        ),
        _check(
            "dictionary-public",
            all(item.privacy == "public_aggregate" for item in fields),
            sum(item.privacy == "public_aggregate" for item in fields),
            len(fields),
            "field scope is public aggregate",
        ),
        _check(
            "dictionary-fixture",
            bool(fixture.fixture_id and fixture.context_key and fixture.boundary),
            fixture.fixture_id,
            "fixture identity",
            "dictionary joins the D06 fixture",
        ),
        _check(
            "dictionary-addresses",
            all(item.content_address.startswith("sha256:") for item in fields),
            sum(item.content_address.startswith("sha256:") for item in fields),
            len(fields),
            "field rows are addressed",
        ),
        _check(
            "dictionary-required",
            all(item.required and item.type_name and item.semantic_role for item in fields),
            sum(item.required and bool(item.type_name and item.semantic_role) for item in fields),
            len(fields),
            "required fields have semantic types and roles",
        ),
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "version": fixture.version,
        "fields": fields,
        "checks": checks,
    }
    return SequenceArchitectureDataDictionary(
        fixture_id=fixture.fixture_id,
        version=fixture.version,
        fields=fields,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "sequence-dictionary"),
    )


def _fields() -> tuple[SequenceArchitectureField, ...]:
    rows = (
        (
            "source",
            "source_id",
            "string",
            "source join key",
            (),
            "sequence_effect_frontier:seq-refseq",
        ),
        (
            "source",
            "family",
            "enum",
            "family provenance",
            (
                "sequence_effect_frontier",
                "sequence_grammar_frontier",
                "sequence_regulation_frontier",
                "sequence_frontier",
            ),
            "sequence_effect_frontier",
        ),
        ("source", "uri", "uri", "public locator", (), "https://www.ncbi.nlm.nih.gov/refseq/"),
        ("source", "version", "string", "public release", (), "2026-01"),
        ("source", "checksum", "sha256", "source identity", (), "sha256:..."),
        ("operation", "operation_id", "string", "operation join key", (), "D06-C01"),
        ("operation", "capability_id", "string", "registry join key", (), "GNC-D06-C01"),
        ("operation", "ordinal", "integer", "dependency order", (), "1"),
        (
            "operation",
            "plane",
            "enum",
            "validation plane",
            ("ingestion", "effect", "grammar", "regulation", "frontier"),
            "effect",
        ),
        ("operation", "dependencies", "string[]", "plan prerequisites", (), "[]"),
        ("case", "case_id", "string", "case identity", (), "D06-C01-positive"),
        (
            "case",
            "scenario",
            "enum",
            "boundary scenario",
            ("positive", "foreign_context", "malformed_input", "identity_conflict"),
            "positive",
        ),
        (
            "case",
            "context_key",
            "context",
            "sequence context",
            (),
            "GRCh38|diffuse_glioma|adult|bulk_tumor|sequence|baseline",
        ),
        (
            "case",
            "source_ids",
            "string[]",
            "public joins",
            (),
            "[sequence_effect_frontier:seq-refseq]",
        ),
        ("case", "payload", "object", "family adapter input", (), "{record_id: C01-POS-001}"),
        (
            "case",
            "expected_state",
            "enum",
            "aggregate decision contract",
            ("accepted", "review"),
            "accepted",
        ),
        ("case", "expected_issue_codes", "string[]", "expected control or family issues", (), "[]"),
        ("case", "expected_counts", "integer map", "bounded evidence counts", (), "{primary: 1}"),
        (
            "receipt",
            "observed_state",
            "enum",
            "aggregate decision",
            ("accepted", "review"),
            "accepted",
        ),
        ("receipt", "observed_result_state", "string", "family result", (), "supported"),
        ("receipt", "observed_issue_codes", "string[]", "preserved issues", (), "[motif_loss]"),
        (
            "receipt",
            "observed_counts",
            "integer map",
            "bounded observed counts",
            (),
            "{primary: 1}",
        ),
        ("receipt", "passed", "boolean", "receipt gate", (), "true"),
        ("review", "priority", "integer", "review urgency", (), "2"),
        ("review", "next_action", "string", "review instruction", (), "confirm context"),
        ("ledger", "sequence", "integer", "event order", (), "1"),
        ("ledger", "previous_address", "sha256", "chain predecessor", (), "sha256:genesis"),
        (
            "artifact",
            "artifact_type",
            "enum",
            "release class",
            ("fixture", "evaluation", "review", "lineage", "metrics", "validation"),
            "evaluation",
        ),
        (
            "artifact",
            "media_type",
            "mime",
            "interchange format",
            ("application/json",),
            "application/json",
        ),
        ("artifact", "retention", "enum", "retention policy", ("release", "audit"), "release"),
    )
    return tuple(
        SequenceArchitectureField(
            field_id=f"D06-F{index:03d}",
            entity=entity,
            name=name,
            type_name=type_name,
            required=True,
            semantic_role=role,
            allowed_values=allowed,
            example=example,
            privacy="public_aggregate",
            content_address=addressed(
                {
                    "entity": entity,
                    "name": name,
                    "type_name": type_name,
                    "role": role,
                    "allowed": allowed,
                    "example": example,
                },
                "sequence-field",
            ),
        )
        for index, (entity, name, type_name, role, allowed, example) in enumerate(rows, 1)
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SequenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": SequenceArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SequenceArchitectureCheck(
        check_id=check_id,
        kind=SequenceArchitectureCheckKind.FIXTURE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "sequence-dictionary-check"),
    )


__all__ = [
    "SequenceArchitectureDataDictionary",
    "SequenceArchitectureField",
    "sequence_architecture_data_dictionary",
]
