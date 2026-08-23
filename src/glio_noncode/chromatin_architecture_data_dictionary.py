"""Field-level data dictionary for D07 public aggregate receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_architecture_contracts import ChromatinArchitectureFixture, addressed
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureField:
    field_name: str
    domain: str
    type_name: str
    required: bool
    public: bool
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinArchitectureDataDictionary:
    fixture_id: str
    fields: tuple[ChromatinArchitectureField, ...]
    checks: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


_FIELDS = (
    ("fixture_id", "fixture", "string", True, True, "aggregate fixture identity"),
    ("version", "fixture", "string", True, True, "pinned D07 contract version"),
    ("boundary", "fixture", "enum", True, True, "public aggregate evidence boundary"),
    ("context_key", "context", "string", True, True, "exact biological context"),
    ("source_id", "source", "string", True, True, "prefixed source receipt identity"),
    ("source_uri", "source", "uri", True, True, "public source locator"),
    ("source_version", "source", "string", True, True, "source release receipt"),
    ("source_scope", "source", "enum", True, True, "public aggregate scope"),
    ("operation_id", "operation", "string", True, True, "D07 operation identity"),
    ("capability_id", "operation", "string", True, True, "capability identity"),
    ("family", "operation", "enum", True, True, "family dispatch boundary"),
    ("plane", "operation", "enum", True, True, "evidence plane"),
    ("dependencies", "operation", "array[string]", True, True, "ordered predecessor IDs"),
    ("case_id", "case", "string", True, True, "case identity"),
    ("scenario", "case", "enum", True, True, "positive or control scenario"),
    ("expected_state", "case", "enum", True, True, "declared aggregate expectation"),
    ("expected_issue_codes", "case", "array[string]", True, True, "declared issue floor"),
    ("expected_counts", "case", "object", True, True, "bounded count expectation"),
    ("observed_state", "receipt", "enum", True, True, "aggregate result state"),
    ("observed_result_state", "receipt", "string", True, True, "family or release result"),
    ("observed_issue_codes", "receipt", "array[string]", True, True, "observed issue vocabulary"),
    ("observed_counts", "receipt", "object", True, True, "bounded observed counts"),
    ("summary", "receipt", "object", True, True, "sanitized summary"),
    ("output_address", "receipt", "sha256", True, True, "execution address"),
    ("content_address", "receipt", "sha256", True, True, "receipt address"),
    ("lineage_address", "release", "sha256", True, True, "lineage address"),
    ("review_state", "release", "enum", True, True, "review disposition"),
    ("artifact_id", "release", "string", True, True, "artifact identity"),
    ("release_state", "release", "enum", True, True, "release disposition"),
    ("limitation", "release", "string", True, True, "claim boundary"),
)


def chromatin_architecture_data_dictionary(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureDataDictionary:
    fields = tuple(
        ChromatinArchitectureField(
            field_name=name,
            domain=domain,
            type_name=type_name,
            required=required,
            public=public,
            description=description,
            content_address=addressed(
                {"name": name, "domain": domain, "type": type_name}, "chromatin-dictionary-field"
            ),
        )
        for name, domain, type_name, required, public, description in _FIELDS
    )
    checks = (
        "all fields have owners and descriptions",
        "all public fields are review-safe",
        "raw family payloads are not receipt fields",
        "context and source identity remain explicit",
        "issue and uncertainty fields remain enumerable",
        "release limitations remain visible",
    )
    return ChromatinArchitectureDataDictionary(
        fixture.fixture_id,
        fields,
        checks,
        addressed(
            {"fixture_id": fixture.fixture_id, "fields": fields, "checks": checks},
            "chromatin-dictionary",
        ),
    )


__all__ = [
    "ChromatinArchitectureDataDictionary",
    "ChromatinArchitectureField",
    "chromatin_architecture_data_dictionary",
]
