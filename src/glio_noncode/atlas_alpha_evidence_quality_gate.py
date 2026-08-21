"""Layered quality gate for Domain 05 C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_bundle import AtlasAlphaEvidenceBundle, build_atlas_alpha_evidence_bundle
from .atlas_alpha_evidence_fixture_eval import evaluate_atlas_alpha_evidence_fixture
from .atlas_alpha_evidence_lineage import (
    build_atlas_alpha_evidence_lineage,
    verify_atlas_alpha_evidence_lineage,
)
from .atlas_alpha_evidence_metrics import compute_atlas_alpha_evidence_metrics
from .atlas_alpha_evidence_policy import evaluate_atlas_alpha_evidence_policy
from .atlas_alpha_evidence_public_data import (
    AtlasAlphaEvidenceFixture,
    audit_atlas_alpha_evidence_data,
    default_atlas_alpha_evidence_fixture,
)
from .atlas_alpha_evidence_reconciliation import reconcile_atlas_alpha_evidence
from .atlas_alpha_evidence_replay import replay_atlas_alpha_evidence_evaluation
from .atlas_alpha_evidence_scenario_matrix import evaluate_atlas_alpha_evidence_scenarios
from .atlas_alpha_evidence_schema import validate_atlas_alpha_evidence_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceQualityCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceQualityReport:
    fixture_id: str
    checks: tuple[AtlasAlphaEvidenceQualityCheck, ...]
    bundle: AtlasAlphaEvidenceBundle
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks) and self.bundle.accepted

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def run_atlas_alpha_evidence_quality_gate(
    fixture: AtlasAlphaEvidenceFixture | None = None,
) -> AtlasAlphaEvidenceQualityReport:
    """Run data, adapter, replay, scenario, policy, lineage, and reconciliation gates."""

    selected = fixture or default_atlas_alpha_evidence_fixture()
    data_audit = audit_atlas_alpha_evidence_data(selected)
    evaluation = evaluate_atlas_alpha_evidence_fixture(selected)
    replay = replay_atlas_alpha_evidence_evaluation(evaluation, fixture=selected)
    scenarios = evaluate_atlas_alpha_evidence_scenarios(evaluation)
    policy = evaluate_atlas_alpha_evidence_policy(selected, evaluation)
    lineage = build_atlas_alpha_evidence_lineage(selected, evaluation)
    reconciliation = reconcile_atlas_alpha_evidence(selected, evaluation)
    metrics = compute_atlas_alpha_evidence_metrics(evaluation)
    schema = validate_atlas_alpha_evidence_schema(selected, evaluation)
    checks: list[AtlasAlphaEvidenceQualityCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(AtlasAlphaEvidenceQualityCheck(**body, content_address=content_hash(body)))

    add("data-audit", data_audit.accepted, "public aggregate data audit accepted")
    add("evaluation", evaluation.accepted, "adapter fixture evaluation accepted")
    add("replay", replay.accepted, "deterministic replay accepted")
    add("scenarios", scenarios.accepted, "scenario matrix accepted")
    add("policy", policy.accepted, "evidence policy accepted")
    add(
        "lineage",
        not verify_atlas_alpha_evidence_lineage(lineage, selected, evaluation),
        "source lineage closes",
    )
    add("reconciliation", reconciliation.accepted, "expected and observed receipts reconcile")
    add("check-floor", len(evaluation.checks) >= 120, "evaluation has the 120-check floor")
    add("positive-floor", evaluation.positive_count == 4, "four positive paths are present")
    add("control-floor", evaluation.control_count == 12, "twelve controls are present")
    add("metric-address", metrics.content_address.startswith("sha256:"), "metrics are addressed")
    add("schema", schema.accepted, "operation input and output schemas are accepted")
    bundle = build_atlas_alpha_evidence_bundle(
        selected,
        data_audit,
        evaluation,
        replay,
        scenarios,
        policy,
        lineage,
        reconciliation,
        metrics,
    )
    body = {"fixture_id": selected.fixture_id, "checks": checks, "bundle": bundle}
    return AtlasAlphaEvidenceQualityReport(
        selected.fixture_id, tuple(checks), bundle, content_hash(body)
    )


__all__ = [
    "AtlasAlphaEvidenceQualityCheck",
    "AtlasAlphaEvidenceQualityReport",
    "run_atlas_alpha_evidence_quality_gate",
]
