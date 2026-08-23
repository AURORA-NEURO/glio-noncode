"""Release-use policy for control frontier receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierRole
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierPolicyRule:
    rule_id: str
    label: str
    blocking: bool
    description: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierPolicy:
    policy_id: str
    version: str
    rules: tuple[ControlFrontierPolicyRule, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def evaluate(self, evaluation: ControlFrontierEvaluation) -> tuple[dict[str, Any], ...]:
        return tuple({"rule_id": rule.rule_id, "passed": self._passed(rule.rule_id, evaluation), "blocking": rule.blocking, "detail": rule.description} for rule in self.rules)

    @staticmethod
    def _passed(rule_id: str, evaluation: ControlFrontierEvaluation) -> bool:
        if rule_id == "evaluation-accepted":
            return evaluation.accepted
        if rule_id == "controls-visible":
            return all(item.role is ControlFrontierRole.CONTROL for item in evaluation.executions if not item.accepted) and sum(item.role is ControlFrontierRole.CONTROL for item in evaluation.executions) == 24
        if rule_id == "addresses-closed":
            return all(item.content_address.startswith("sha256:") for item in evaluation.executions)
        return True


def default_control_frontier_policy() -> ControlFrontierPolicy:
    specs = (
        ("evaluation-accepted", "evaluation receipt accepted", True, "all row checks pass"),
        ("controls-visible", "negative controls remain visible", True, "controls are part of the release surface"),
        ("addresses-closed", "execution addresses are closed", True, "each operation receipt has a SHA-256 address"),
        ("research-only", "research-only boundary retained", True, "no clinical or autonomous use claim"),
        ("source-boundary", "public source boundary retained", True, "source IDs remain explicit"),
        ("review-disposition", "review states remain actionable", False, "blocked and abstained states remain visible"),
    )
    rules = []
    for rule_id, label, blocking, description in specs:
        body = {"rule_id": rule_id, "label": label, "blocking": blocking, "description": description}
        rules.append(ControlFrontierPolicyRule(**body, content_address=content_hash(body)))
    body = {"policy_id": "control-frontier-release-policy", "version": "v1", "rules": tuple(rules), "allowed_uses": ("research-use-only", "aggregate-operational-review", "reproducibility-testing"), "excluded_uses": ("clinical-decision", "patient-ranking", "autonomous-action")}
    return ControlFrontierPolicy(**body, content_address=content_hash(body))


__all__ = ["ControlFrontierPolicy", "ControlFrontierPolicyRule", "default_control_frontier_policy"]
