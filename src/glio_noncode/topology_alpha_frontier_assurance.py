"""Composed assurance result for the complete alpha module surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_audit_log import TopologyAlphaFrontierAuditLog, build_topology_alpha_frontier_audit_log
from .topology_alpha_frontier_checksum_audit import TopologyAlphaFrontierChecksumAuditReport, audit_topology_alpha_frontier_checksums
from .topology_alpha_frontier_comparison import TopologyAlphaFrontierComparisonReport, build_topology_alpha_frontier_comparisons
from .topology_alpha_frontier_data_dictionary import TopologyAlphaFrontierDataDictionary, build_topology_alpha_frontier_data_dictionary
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_lineage_audit import TopologyAlphaFrontierLineageAuditReport, audit_topology_alpha_frontier_lineage
from .topology_alpha_frontier_operator_handbook import TopologyAlphaFrontierOperatorHandbook, default_topology_alpha_frontier_operator_handbook
from .topology_alpha_frontier_partition import TopologyAlphaFrontierPartitionReport, build_topology_alpha_frontier_partitions
from .topology_alpha_frontier_pipeline import TopologyAlphaFrontierPipelineReport
from .topology_alpha_frontier_release_gate import TopologyAlphaFrontierReleaseGateReport, evaluate_topology_alpha_frontier_release_gate
from .topology_alpha_frontier_resource_limits import TopologyAlphaFrontierResourceReport, audit_topology_alpha_frontier_resources
from .topology_alpha_frontier_review_actions import TopologyAlphaFrontierReviewActionPlan, build_topology_alpha_frontier_review_actions
from .topology_alpha_frontier_scorecard import TopologyAlphaFrontierScorecardReport, build_topology_alpha_frontier_scorecards
from .topology_alpha_frontier_state_transitions import TopologyAlphaFrontierStateTransitionReport, audit_topology_alpha_frontier_state_transitions


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAssuranceCheck:
    check_id: str
    passed: bool
    observed: Any
    requirement: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAssuranceReport:
    run_id: str
    dictionary: TopologyAlphaFrontierDataDictionary
    transitions: TopologyAlphaFrontierStateTransitionReport
    scorecards: TopologyAlphaFrontierScorecardReport
    lineage: TopologyAlphaFrontierLineageAuditReport
    resources: TopologyAlphaFrontierResourceReport
    checksums: TopologyAlphaFrontierChecksumAuditReport
    comparisons: TopologyAlphaFrontierComparisonReport
    actions: TopologyAlphaFrontierReviewActionPlan
    audit_log: TopologyAlphaFrontierAuditLog
    release_gate: TopologyAlphaFrontierReleaseGateReport
    partitions: TopologyAlphaFrontierPartitionReport
    handbook: TopologyAlphaFrontierOperatorHandbook
    checks: tuple[TopologyAlphaFrontierAssuranceCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierAssuranceCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"run_id": self.run_id, "dictionary": self.dictionary.to_dict(), "transitions": self.transitions.to_dict(), "scorecards": self.scorecards.to_dict(), "lineage": self.lineage.to_dict(), "resources": self.resources.to_dict(), "checksums": self.checksums.to_dict(), "comparisons": self.comparisons.to_dict(), "actions": self.actions.to_dict(), "audit_log": self.audit_log.to_dict(), "release_gate": self.release_gate.to_dict(), "partitions": self.partitions.to_dict(), "handbook": self.handbook.to_dict(), "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_assurance(pipeline: TopologyAlphaFrontierPipelineReport) -> TopologyAlphaFrontierAssuranceReport:
    fixture, evaluation = pipeline.fixture, pipeline.evaluation
    dictionary = build_topology_alpha_frontier_data_dictionary()
    transitions = audit_topology_alpha_frontier_state_transitions(evaluation)
    scorecards = build_topology_alpha_frontier_scorecards(evaluation)
    lineage = audit_topology_alpha_frontier_lineage(fixture, evaluation)
    resources = audit_topology_alpha_frontier_resources(evaluation, pipeline)
    checksums = audit_topology_alpha_frontier_checksums(fixture, evaluation)
    comparisons = build_topology_alpha_frontier_comparisons(evaluation)
    actions = build_topology_alpha_frontier_review_actions(evaluation)
    audit_log = build_topology_alpha_frontier_audit_log(pipeline)
    release_gate = evaluate_topology_alpha_frontier_release_gate(pipeline)
    partitions = build_topology_alpha_frontier_partitions(evaluation)
    handbook = default_topology_alpha_frontier_operator_handbook()
    checks = (TopologyAlphaFrontierAssuranceCheck("dictionary", dictionary.accepted, dictionary.field_count, "all operation fields are defined"), TopologyAlphaFrontierAssuranceCheck("transitions", transitions.accepted, len(transitions.observations), "all states use the locked vocabulary"), TopologyAlphaFrontierAssuranceCheck("scorecards", scorecards.accepted, scorecards.aggregate_record_count, "each operation has a closed scorecard"), TopologyAlphaFrontierAssuranceCheck("lineage", lineage.accepted, len(lineage.checks), "source-to-result relations are closed"), TopologyAlphaFrontierAssuranceCheck("resources", resources.accepted, len(resources.checks), "execution remains bounded"), TopologyAlphaFrontierAssuranceCheck("checksums", checksums.accepted, checksums.checked_count, "addresses and checksums are present"), TopologyAlphaFrontierAssuranceCheck("comparisons", comparisons.accepted, len(comparisons.comparisons), "positive and control rows remain paired"), TopologyAlphaFrontierAssuranceCheck("actions", actions.accepted, actions.open_count, "every row has a next action"), TopologyAlphaFrontierAssuranceCheck("audit_log", audit_log.accepted, len(audit_log.events), "stage audit log is ordered"), TopologyAlphaFrontierAssuranceCheck("release_gate", release_gate.publishable, len(release_gate.checks), "blocking release gates pass"), TopologyAlphaFrontierAssuranceCheck("partitions", partitions.accepted, partitions.covered_record_count, "partitions cover all records"), TopologyAlphaFrontierAssuranceCheck("handbook", handbook.accepted, len(handbook.procedures), "operator procedures are complete"))
    return TopologyAlphaFrontierAssuranceReport(pipeline.run_id, dictionary, transitions, scorecards, lineage, resources, checksums, comparisons, actions, audit_log, release_gate, partitions, handbook, checks, all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierAssuranceCheck", "TopologyAlphaFrontierAssuranceReport", "build_topology_alpha_frontier_assurance"]
