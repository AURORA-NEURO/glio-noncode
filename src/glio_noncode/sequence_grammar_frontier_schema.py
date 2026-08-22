"""Schema and field conformance checks for sequence grammar records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_contracts import (
    SequenceGrammarContractRegistry,
    default_sequence_grammar_contracts,
)
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarOperation,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarField:
    name: str
    value_kind: str
    required: bool
    description: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarSchema:
    operation: SequenceGrammarOperation
    schema_id: str
    version: str
    fields: tuple[SequenceGrammarField, ...]
    output_states: tuple[SequenceGrammarState, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.schema_id.strip() or not self.version.strip() or not self.fields:
            raise ValidationError("sequence grammar schema is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "schema_id": self.schema_id,
                        "version": self.version,
                        "fields": self.fields,
                        "output_states": self.output_states,
                    }
                ),
            )

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id.strip() or not self.detail.strip():
            raise ValidationError("schema check requires ID and detail")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"check_id": self.check_id, "passed": self.passed, "detail": self.detail}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarSchemaReport:
    accepted: bool
    checks: tuple[SequenceGrammarSchemaCheck, ...]
    fixture_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.checks:
            raise ValidationError("schema report requires checks")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "checks": self.checks,
                        "fixture_id": self.fixture_id,
                    }
                ),
            )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "check_count": len(self.checks),
            "failed_check_ids": list(self.failed_check_ids),
            "checks": [check.to_dict() for check in self.checks],
            "content_address": self.content_address,
        }


def default_sequence_grammar_schemas() -> tuple[SequenceGrammarSchema, ...]:
    states = tuple(SequenceGrammarState)
    common = (
        SequenceGrammarField(
            "context_key", "string", False, "exact scientific context when supplied"
        ),
    )
    definitions = (
        (
            SequenceGrammarOperation.MOTIF_DISRUPTION,
            "motif-disruption",
            ("variant_id", "reference", "alternate", "motifs"),
        ),
        (
            SequenceGrammarOperation.MOTIF_CREATION,
            "motif-creation",
            ("variant_id", "reference", "alternate", "motifs"),
        ),
        (SequenceGrammarOperation.SPACING_GRAMMAR, "spacing-grammar", ("hits", "rules")),
        (
            SequenceGrammarOperation.COOPERATIVE_GRAMMAR,
            "cooperative-grammar",
            ("sequence", "hits", "interactions", "model_id", "model_version"),
        ),
    )
    return tuple(
        SequenceGrammarSchema(
            operation=operation,
            schema_id=f"glio.sequence-grammar.{schema_id}",
            version="1.0",
            fields=common
            + tuple(
                SequenceGrammarField(
                    name,
                    "array" if name in {"motifs", "hits", "rules", "interactions"} else "string",
                    True,
                    f"required {name}",
                )
                for name in required
            ),
            output_states=states,
        )
        for operation, schema_id, required in definitions
    )


def validate_sequence_grammar_schema(
    fixture: SequenceGrammarFixture,
    evaluation: SequenceGrammarEvaluation,
    contracts: SequenceGrammarContractRegistry | None = None,
) -> SequenceGrammarSchemaReport:
    """Validate fixture payload shape and evaluated state vocabulary."""

    registry = contracts or default_sequence_grammar_contracts()
    schemas = {schema.operation: schema for schema in default_sequence_grammar_schemas()}
    checks: list[SequenceGrammarSchemaCheck] = []
    checks.append(
        SequenceGrammarSchemaCheck(
            "registry.closed", len(registry.contracts) == 4, "four contracts are registered"
        )
    )
    checks.append(
        SequenceGrammarSchemaCheck(
            "schema.closed", len(schemas) == 4, "four schemas are registered"
        )
    )
    checks.append(
        SequenceGrammarSchemaCheck(
            "evaluation.closed",
            len(evaluation.executions) == len(fixture.records),
            "every record has an execution",
        )
    )
    for record in fixture.records:
        schema = schemas.get(record.operation)
        present = set(record.payload)
        required = set(schema.required_fields) if schema else set()
        checks.append(
            SequenceGrammarSchemaCheck(
                f"{record.record_id}.fields",
                schema is not None and required <= present,
                "required payload fields are present",
            )
        )
        checks.append(
            SequenceGrammarSchemaCheck(
                f"{record.record_id}.boundary",
                record.context_key == fixture.context_key,
                "record context matches fixture",
            )
        )
    checks.append(
        SequenceGrammarSchemaCheck(
            "evaluation.states",
            all(
                execution.adapter_state in set(SequenceGrammarState)
                for execution in evaluation.executions
            ),
            "states use the closed vocabulary",
        )
    )
    checks.append(
        SequenceGrammarSchemaCheck(
            "evaluation.addresses",
            all(
                execution.content_address.startswith("sha256:")
                for execution in evaluation.executions
            ),
            "execution addresses are present",
        )
    )
    accepted = all(check.passed for check in checks)
    return SequenceGrammarSchemaReport(accepted, tuple(checks), fixture.fixture_id)


def sequence_grammar_schema_manifest() -> dict[str, Any]:
    schemas = default_sequence_grammar_schemas()
    return {
        "version": "2026.08.d06-c05-c08.schema-manifest.v1",
        "schemas": [schema.to_dict() for schema in schemas],
        "content_address": content_hash({"schemas": schemas}),
    }


__all__ = [
    "SequenceGrammarField",
    "SequenceGrammarSchema",
    "SequenceGrammarSchemaCheck",
    "SequenceGrammarSchemaReport",
    "default_sequence_grammar_schemas",
    "sequence_grammar_schema_manifest",
    "validate_sequence_grammar_schema",
]
