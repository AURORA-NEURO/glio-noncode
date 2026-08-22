"""Schema manifests and boundary checks for sequence-effect outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_effect_frontier_contracts import (
    SequenceEffectContractRegistry,
    default_sequence_effect_contracts,
)
from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture, SequenceEffectOperation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectField:
    name: str
    value_type: str
    required: bool
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.value_type.strip():
            raise ValidationError("schema fields require names and types")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(jsonable(self) | {"content_address": ""})
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectSchema:
    operation: SequenceEffectOperation
    fields: tuple[SequenceEffectField, ...]
    invariants: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fields or not self.invariants:
            raise ValidationError("schema requires fields and invariants")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "fields": self.fields,
                        "invariants": self.invariants,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation.value,
            "fields": [item.to_dict() for item in self.fields],
            "invariants": list(self.invariants),
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectSchemaCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
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
class SequenceEffectSchemaReport:
    schemas: tuple[SequenceEffectSchema, ...]
    checks: tuple[SequenceEffectSchemaCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {"schemas": self.schemas, "checks": self.checks, "accepted": self.accepted}
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "schemas": [item.to_dict() for item in self.schemas],
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def default_sequence_effect_schemas() -> tuple[SequenceEffectSchema, ...]:
    def fields(names: tuple[tuple[str, str, bool, str], ...]) -> tuple[SequenceEffectField, ...]:
        return tuple(SequenceEffectField(*item) for item in names)

    common = ("context_key", "source_ids", "content_address")
    return (
        SequenceEffectSchema(
            SequenceEffectOperation.CONTEXT_ENCODING,
            fields(
                tuple(
                    (name, "text", True, "context encoding field")
                    for name in (
                        *common,
                        "sequence_hash",
                        "gc_fraction",
                        "ambiguous_fraction",
                        "kmer_frequencies",
                    )
                )
            ),
            ("sequence hash is stable", "fractions are bounded", "ambiguous bases remain visible"),
        ),
        SequenceEffectSchema(
            SequenceEffectOperation.FOUNDATION_MODEL,
            fields(
                tuple(
                    (name, "text", True, "model adapter field")
                    for name in (*common, "input_hash", "observations", "issues")
                )
            ),
            ("raw input is addressed", "model identity is retained", "issues are not hidden"),
        ),
        SequenceEffectSchema(
            SequenceEffectOperation.LONG_CONTEXT,
            fields(
                tuple(
                    (name, "text", True, "long context field")
                    for name in (*common, "input_hash", "observations", "issues")
                )
            ),
            (
                "context length is declared",
                "short windows are rejected",
                "effect deltas remain model outputs",
            ),
        ),
        SequenceEffectSchema(
            SequenceEffectOperation.REGULATORY_ENSEMBLE,
            fields(
                tuple(
                    (name, "text", True, "ensemble field")
                    for name in (*common, "rows", "mean_delta", "disagreement")
                )
            ),
            ("model IDs are retained", "spread remains visible", "mean delta is not a probability"),
        ),
    )


def validate_sequence_effect_schema(
    fixture: SequenceEffectFixture,
    evaluation: SequenceEffectEvaluation,
    contracts: SequenceEffectContractRegistry | None = None,
) -> SequenceEffectSchemaReport:
    contracts = contracts or default_sequence_effect_contracts()
    schemas = default_sequence_effect_schemas()
    checks = tuple(
        SequenceEffectSchemaCheck(check_id, passed, detail)
        for check_id, passed, detail in (
            ("schema-operation-count", len(schemas) == 4, "four schemas are declared"),
            (
                "schema-contract-closure",
                {item.operation for item in schemas}
                == {item.operation for item in contracts.contracts},
                "schemas and contracts cover the same operations",
            ),
            (
                "schema-fixture-address",
                fixture.content_address.startswith("sha256:"),
                "fixture address is present",
            ),
            (
                "schema-evaluation-address",
                evaluation.content_address.startswith("sha256:"),
                "evaluation address is present",
            ),
            (
                "schema-context",
                all(item.context_key == fixture.context_key for item in evaluation.executions),
                "execution contexts are exact",
            ),
            (
                "schema-output-addresses",
                all(item.content_address.startswith("sha256:") for item in evaluation.executions),
                "execution outputs are addressed",
            ),
            (
                "schema-control-retention",
                all(
                    item.role.value == "control"
                    for item in evaluation.executions
                    if item.record_id.endswith("CTRL-001")
                    or item.record_id.endswith("CTRL-002")
                    or item.record_id.endswith("CTRL-003")
                ),
                "control roles remain explicit",
            ),
            (
                "schema-no-payload-leak",
                all("ACGT" not in str(item.to_dict()) for item in evaluation.executions),
                "serialized output does not expose raw sequence payloads",
            ),
        )
    )
    return SequenceEffectSchemaReport(schemas, checks, all(item.passed for item in checks))


def sequence_effect_schema_manifest() -> dict[str, Any]:
    schemas = default_sequence_effect_schemas()
    return {
        "schemas": [item.to_dict() for item in schemas],
        "content_address": content_hash(tuple(item.to_dict() for item in schemas)),
    }


__all__ = [
    "SequenceEffectField",
    "SequenceEffectSchema",
    "SequenceEffectSchemaCheck",
    "SequenceEffectSchemaReport",
    "default_sequence_effect_schemas",
    "sequence_effect_schema_manifest",
    "validate_sequence_effect_schema",
]
