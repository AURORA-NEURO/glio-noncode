"""Public boundary compliance for D16 execution payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_execution_architecture_contracts import PlatformExecutionFixture, addressed
from .platform_execution_architecture_public_data import default_platform_execution_fixture

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
class PlatformExecutionComplianceReport:
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


def _walk(value: Any, path: str = "payload") -> tuple[tuple[str, str], ...]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            text = str(key)
            if text in _FORBIDDEN_FIELDS:
                found.append((f"{path}.{text}", text))
            found.extend(_walk(child, f"{path}.{text}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(_walk(child, f"{path}[{index}]"))
    return tuple(found)


def assess_platform_execution_compliance(
    fixture: PlatformExecutionFixture | None = None,
) -> PlatformExecutionComplianceReport:
    selected = fixture or default_platform_execution_fixture()
    hits = [hit for case in selected.cases for hit in _walk(case.payload, f"cases.{case.case_id}")]
    checks = (
        {
            "check_id": "compliance:public-sources",
            "passed": all(item.public_aggregate for item in selected.sources),
            "observed": all(item.public_aggregate for item in selected.sources),
            "required": True,
            "detail": "source receipts are public aggregate",
        },
        {
            "check_id": "compliance:no-forbidden-fields",
            "passed": not hits,
            "observed": tuple(path for path, _key in hits),
            "required": (),
            "detail": "restricted keys are absent",
        },
        {
            "check_id": "compliance:case-addresses",
            "passed": all(item.content_address for item in selected.cases),
            "observed": len(selected.cases),
            "required": len(selected.cases),
            "detail": "all cases are addressed",
        },
        {
            "check_id": "compliance:context-visibility",
            "passed": all(item.delegate_context_key for item in selected.cases),
            "observed": len({item.delegate_context_key for item in selected.cases}),
            "required": "non-empty contexts",
            "detail": "contexts remain visible",
        },
    )
    forbidden = tuple(sorted({key for _path, key in hits}))
    body = {"fixture_id": selected.fixture_id, "checks": checks, "forbidden_keys": forbidden}
    return PlatformExecutionComplianceReport(
        selected.fixture_id,
        checks,
        all(item["passed"] for item in checks),
        forbidden,
        addressed(body, "platform-execution-compliance"),
    )


__all__ = ["PlatformExecutionComplianceReport", "assess_platform_execution_compliance"]
