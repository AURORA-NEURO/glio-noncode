"""Schema error grouping for operator-facing input repair."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseSchemaDiagnostics:
    errors: tuple[str, ...]
    fields: tuple[str, ...]
    repairable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def diagnose_evidence_release_schema(errors: Iterable[str]) -> EvidenceReleaseSchemaDiagnostics:
    normalized = tuple(sorted({str(error) for error in errors}))
    fields = tuple(sorted({error.split(":", 1)[1] for error in normalized if ":" in error}))
    body = {"errors": normalized, "fields": fields, "repairable": all(not error.startswith("context") for error in normalized)}
    return EvidenceReleaseSchemaDiagnostics(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseSchemaDiagnostics", "diagnose_evidence_release_schema"]
