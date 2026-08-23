"""Fine-grained sequence and identity rules for guide adaptation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .planning_frontier_support import dna, required_text
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class GuideRuleResult:
    rule_id: str
    passed: bool
    detail: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def check_guide_row(row: dict[str, Any]) -> tuple[GuideRuleResult, ...]:
    checks = []
    try:
        sequence = dna(row.get("sequence"), "sequence")
        checks.append(("sequence", bool(sequence), "sequence contains supported DNA bases"))
    except (TypeError, ValueError):
        checks.append(("sequence", False, "sequence is invalid"))
    for field in ("design_id", "target_id"):
        try: passed = bool(required_text(row.get(field), field))
        except (TypeError, ValueError): passed = False
        checks.append((field, passed, f"{field} is stable"))
    return tuple(GuideRuleResult(rule_id=rule, passed=passed, detail=detail, content_address=content_hash({"rule": rule, "passed": passed, "detail": detail}, prefix="guide-rule")) for rule, passed, detail in checks)
__all__ = ["GuideRuleResult", "check_guide_row"]
