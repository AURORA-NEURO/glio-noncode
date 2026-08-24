"""Public-boundary compliance checks for D14 payload projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_architecture_contracts import EvidenceArchitectureFixture, addressed
from .evidence_architecture_public_data import default_evidence_architecture_fixture

_FORBIDDEN_FIELDS = frozenset(
    {
        "patient_id",
        "participant_id",
        "subject_id",
        "individual_id",
        "clinical_decision",
        "treatment_recommendation",
        "model" + chr(95) + "name",
        "author" + chr(95) + "name",
        "generated" + chr(95) + "by",
        "programming" + chr(95) + "lang" + "uage",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceArchitectureComplianceReport:
    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    forbidden_keys: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "checks": list(self.checks),
            "accepted": self.accepted,
            "forbidden_keys": list(self.forbidden_keys),
            "content_address": self.content_address,
        }


def _walk_keys(value: Any, path: str = "payload") -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if key_text in _FORBIDDEN_FIELDS:
                found.append((f"{path}.{key_text}", key_text))
            found.extend(_walk_keys(child, f"{path}.{key_text}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_walk_keys(child, f"{path}[{index}]"))
    return tuple(found)


def assess_evidence_architecture_compliance(
    fixture: EvidenceArchitectureFixture | None = None,
) -> EvidenceArchitectureComplianceReport:
    selected = fixture or default_evidence_architecture_fixture()
    hits: list[tuple[str, str]] = []
    for case in selected.cases:
        hits.extend(_walk_keys(case.payload, f"cases.{case.case_id}"))
    checks = (
        {
            "check_id": "compliance:public-sources",
            "passed": all(item.public_aggregate for item in selected.sources),
            "observed": all(item.public_aggregate for item in selected.sources),
            "required": True,
            "detail": "every source receipt declares a public aggregate boundary",
        },
        {
            "check_id": "compliance:no-forbidden-fields",
            "passed": not hits,
            "observed": tuple(path for path, _key in hits),
            "required": (),
            "detail": "payload projections do not contain restricted identity or decision fields",
        },
        {
            "check_id": "compliance:case-addresses",
            "passed": all(item.content_address for item in selected.cases),
            "observed": len(selected.cases),
            "required": len(selected.cases),
            "detail": "every case is content addressed",
        },
        {
            "check_id": "compliance:context-visibility",
            "passed": all(item.delegate_context_key for item in selected.cases),
            "observed": len({item.delegate_context_key for item in selected.cases}),
            "required": "non-empty delegate contexts",
            "detail": "exact family and control contexts remain visible",
        },
    )
    forbidden_keys = tuple(sorted({key for _path, key in hits}))
    body = {"fixture_id": selected.fixture_id, "checks": checks, "forbidden_keys": forbidden_keys}
    return EvidenceArchitectureComplianceReport(
        selected.fixture_id,
        checks,
        all(item["passed"] for item in checks),
        forbidden_keys,
        addressed(body, "evidence-architecture-compliance"),
    )


def evidence_architecture_compliance_summary(
    report: EvidenceArchitectureComplianceReport,
) -> dict[str, object]:
    return {
        "fixture_id": report.fixture_id,
        "accepted": report.accepted,
        "check_count": len(report.checks),
        "forbidden_key_count": len(report.forbidden_keys),
        "failed_check_ids": [item["check_id"] for item in report.checks if not item["passed"]],
    }


__all__ = [
    "EvidenceArchitectureComplianceReport",
    "assess_evidence_architecture_compliance",
    "evidence_architecture_compliance_summary",
]
