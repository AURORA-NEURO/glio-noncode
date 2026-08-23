"""Field-level public data dictionary for the D05 atlas boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_architecture_contracts import (
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureFixture,
    addressed,
)
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class AtlasArchitectureField:
    field_id: str
    entity: str
    name: str
    type_name: str
    required: bool
    nullable: bool
    semantic_role: str
    allowed_values: tuple[str, ...]
    example: str
    privacy: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasArchitectureDataDictionary:
    version: str
    fixture_id: str
    fields: tuple[AtlasArchitectureField, ...]
    checks: tuple[AtlasArchitectureCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "field_count": len(self.fields),
            "check_count": len(self.checks),
        }


def atlas_architecture_data_dictionary(
    fixture: AtlasArchitectureFixture,
) -> AtlasArchitectureDataDictionary:
    """Build the stable field manifest and validate its semantic coverage."""

    fields = _fields()
    checks = (
        _check(
            "dictionary-field-ids",
            len({item.field_id for item in fields}) == len(fields),
            len({item.field_id for item in fields}),
            len(fields),
            "every dictionary field has a unique identifier",
        ),
        _check(
            "dictionary-required-types",
            all(item.type_name and item.semantic_role for item in fields),
            sum(bool(item.type_name and item.semantic_role) for item in fields),
            len(fields),
            "every field has a type and semantic role",
        ),
        _check(
            "dictionary-public-scope",
            all(item.privacy == "public_aggregate" for item in fields),
            sum(item.privacy == "public_aggregate" for item in fields),
            len(fields),
            "all D05 fields are scoped to the public aggregate boundary",
        ),
        _check(
            "dictionary-fixture-join",
            bool(fixture.fixture_id and fixture.boundary and fixture.context_key),
            fixture.fixture_id,
            "fixture, boundary, and context are present",
            "dictionary joins to the composed fixture",
        ),
        _check(
            "dictionary-addresses",
            all(item.content_address.startswith("sha256:") for item in fields),
            sum(item.content_address.startswith("sha256:") for item in fields),
            len(fields),
            "every field manifest row is content addressed",
        ),
        _check(
            "dictionary-entity-coverage",
            {item.entity for item in fields}
            == {"source", "operation", "case", "receipt", "review", "ledger", "artifact"},
            sorted({item.entity for item in fields}),
            ["source", "operation", "case", "receipt", "review", "ledger", "artifact"],
            "the manifest covers every persisted D05 entity",
        ),
    )
    body = {
        "version": fixture.version,
        "fixture_id": fixture.fixture_id,
        "fields": fields,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return AtlasArchitectureDataDictionary(
        version=fixture.version,
        fixture_id=fixture.fixture_id,
        fields=fields,
        checks=checks,
        accepted=all(item.passed for item in checks),
        content_address=addressed(body, "atlas-data-dictionary"),
    )


def _fields() -> tuple[AtlasArchitectureField, ...]:
    rows = (
        (
            "source_id",
            "source",
            "string",
            True,
            False,
            "public source join key",
            (),
            "regulatory:source-01",
        ),
        (
            "family",
            "source",
            "enum",
            True,
            False,
            "family provenance",
            ("regulatory_atlas", "molecular_atlas", "atlas_alpha_evidence", "frontier_atlas"),
            "regulatory_atlas",
        ),
        (
            "title",
            "source",
            "string",
            True,
            False,
            "public source title",
            (),
            "ENCODE cCRE aggregate",
        ),
        (
            "uri",
            "source",
            "uri",
            True,
            False,
            "public source locator",
            (),
            "https://example.org/public-record",
        ),
        ("version", "source", "string", True, False, "source release", (), "2025-public-release"),
        ("operation_id", "operation", "string", True, False, "operation join key", (), "D05-C01"),
        (
            "capability_id",
            "operation",
            "string",
            True,
            False,
            "registry join key",
            (),
            "GNC-D05-C01",
        ),
        ("ordinal", "operation", "integer", True, False, "dependency order", (), "1"),
        (
            "plane",
            "operation",
            "enum",
            True,
            False,
            "validation plane",
            ("ingestion", "regulatory", "molecular", "evidence", "frontier"),
            "regulatory",
        ),
        ("dependencies", "operation", "string[]", True, False, "plan prerequisites", (), "[]"),
        ("case_id", "case", "string", True, False, "case join key", (), "D05-C01-positive"),
        (
            "scenario",
            "case",
            "enum",
            True,
            False,
            "policy scenario",
            ("positive", "foreign_context", "malformed_input", "identity_conflict"),
            "positive",
        ),
        (
            "context_key",
            "case",
            "context",
            True,
            False,
            "context boundary",
            (),
            "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown",
        ),
        (
            "source_ids",
            "case",
            "string[]",
            True,
            False,
            "source joins",
            (),
            "[regulatory:source-01]",
        ),
        ("payload", "case", "object", True, False, "adapter input", (), "{...}"),
        (
            "expected_state",
            "case",
            "enum",
            True,
            False,
            "contract state",
            ("accepted", "review"),
            "accepted",
        ),
        ("expected_issue_codes", "case", "string[]", True, False, "control policy", (), "[]"),
        ("content_address", "case", "sha256", True, False, "case identity", (), "sha256:..."),
        (
            "observed_state",
            "receipt",
            "enum",
            True,
            False,
            "runtime decision",
            ("accepted", "review"),
            "accepted",
        ),
        (
            "observed_result_state",
            "receipt",
            "string",
            True,
            False,
            "adapter result",
            (),
            "supported",
        ),
        ("observed_issue_codes", "receipt", "string[]", True, False, "runtime issues", (), "[]"),
        (
            "observed_counts",
            "receipt",
            "integer map",
            True,
            False,
            "evidence counts",
            (),
            "{primary: 1}",
        ),
        ("passed", "receipt", "boolean", True, False, "receipt gate", (), "true"),
        ("priority", "review", "integer", True, False, "review urgency", (), "2"),
        (
            "disposition",
            "review",
            "enum",
            True,
            False,
            "review status",
            ("held", "escalated", "resolved"),
            "held",
        ),
        (
            "next_action",
            "review",
            "string",
            True,
            False,
            "review instruction",
            (),
            "inspect context",
        ),
        ("sequence", "ledger", "integer", True, False, "event order", (), "1"),
        (
            "previous_address",
            "ledger",
            "sha256",
            True,
            False,
            "chain predecessor",
            (),
            "sha256:genesis",
        ),
        (
            "artifact_type",
            "artifact",
            "enum",
            True,
            False,
            "release artifact class",
            ("fixture", "evaluation", "review", "lineage", "metrics", "validation"),
            "evaluation",
        ),
        (
            "media_type",
            "artifact",
            "mime",
            True,
            False,
            "artifact serialization",
            ("application/json", "text/csv"),
            "application/json",
        ),
        (
            "retention",
            "artifact",
            "enum",
            True,
            False,
            "retention policy",
            ("release", "audit", "ephemeral"),
            "release",
        ),
    )
    return tuple(
        AtlasArchitectureField(
            field_id=f"D05-F{index:03d}",
            entity=entity,
            name=name,
            type_name=type_name,
            required=required,
            nullable=nullable,
            semantic_role=semantic_role,
            allowed_values=allowed_values,
            example=example,
            privacy="public_aggregate",
            content_address=addressed(
                {
                    "entity": entity,
                    "name": name,
                    "type_name": type_name,
                    "required": required,
                    "nullable": nullable,
                    "semantic_role": semantic_role,
                    "allowed_values": allowed_values,
                    "example": example,
                },
                "atlas-field",
            ),
        )
        for index, (
            name,
            entity,
            type_name,
            required,
            nullable,
            semantic_role,
            allowed_values,
            example,
        ) in enumerate(rows, 1)
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> AtlasArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": AtlasArchitectureCheckKind.FIXTURE,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return AtlasArchitectureCheck(
        check_id=check_id,
        kind=AtlasArchitectureCheckKind.FIXTURE,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "atlas-dictionary-check"),
    )


__all__ = [
    "AtlasArchitectureDataDictionary",
    "AtlasArchitectureField",
    "atlas_architecture_data_dictionary",
]
