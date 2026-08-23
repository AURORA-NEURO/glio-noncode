"""Operational playbook text embedded beside executable planning contracts.

The playbook is intentionally versioned in code so a release can expose the
same review language that the runtime used to build its dispositions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningOperation
from .serialization import content_hash, jsonable


PLAYBOOK_VERSION = "2026.08.d13-c09-c12.playbook.v1"


@dataclass(frozen=True, slots=True)
class PlanningPlaybookEntry:
    entry_id: str
    operation: PlanningOperation | None
    phase: str
    instruction: str
    evidence_to_inspect: str
    stop_condition: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningPlaybook:
    version: str
    entries: tuple[PlanningPlaybookEntry, ...]
    phase_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def for_phase(self, phase: str) -> tuple[PlanningPlaybookEntry, ...]:
        return tuple(item for item in self.entries if item.phase == phase)


def _entry(entry_id: str, operation: PlanningOperation | None, phase: str, instruction: str, evidence: str, stop: str) -> PlanningPlaybookEntry:
    body = {"entry_id": entry_id, "operation": operation, "phase": phase, "instruction": instruction, "evidence_to_inspect": evidence, "stop_condition": stop}
    return PlanningPlaybookEntry(**body, content_address=content_hash(body, prefix="planning-playbook-entry"))


def default_planning_playbook() -> PlanningPlaybook:
    entries = (
        _entry("scope-001", None, "scope", "Read the fixture boundary before reading any result.", "evidence_boundary", "Stop if the boundary is absent."),
        _entry("scope-002", None, "scope", "Confirm that every source receipt is an HTTPS public portal.", "source uri", "Stop on an unknown scheme."),
        _entry("scope-003", None, "scope", "Treat aggregate rows as planning inputs, not observations from an individual.", "record notes", "Stop if an individual identity is present."),
        _entry("scope-004", None, "scope", "Keep the exact context key visible in every review export.", "context_key", "Stop on a missing context key."),
        _entry("scope-005", None, "scope", "Check the fixture address before comparing downstream outputs.", "fixture content_address", "Stop on an unaddressed fixture."),
        _entry("source-001", None, "sources", "Build the source registry before executing a planner.", "source ids and joins", "Stop on an unresolved join."),
        _entry("source-002", None, "sources", "Use a source version or portal receipt for each citation.", "source version", "Stop on an empty version."),
        _entry("source-003", None, "sources", "Keep source scope narrower than the claim boundary.", "source scope", "Stop when scope is broader than evidence."),
        _entry("source-004", None, "sources", "Hash receipt identity and retain it with every record.", "content_address", "Stop on a missing address."),
        _entry("source-005", None, "sources", "Do not infer a source support relationship from a title alone.", "allowed operations", "Stop on an inferred-only join."),
        _entry("context-001", None, "context", "Compare genome build exactly before comparing biological labels.", "context_key", "Stop on a genome mismatch."),
        _entry("context-002", None, "context", "Compare territory and treatment phase exactly.", "territory and treatment fields", "Stop on a foreign territory."),
        _entry("context-003", None, "context", "Keep a foreign-context result blocked even when the sequence looks similar.", "issue_codes", "Stop if a mismatch is downgraded."),
        _entry("context-004", None, "context", "Require declared source support for model eligibility.", "declared_context_keys", "Stop on inferred support."),
        _entry("context-005", None, "context", "Do not merge margin and core observations silently.", "context partition", "Stop on an implicit merge."),
        _entry("eligibility-001", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Read model family and requested family separately.", "model_system", "Hold on a family mismatch."),
        _entry("eligibility-002", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Check declared context membership before evidence strength.", "declared_context_keys", "Hold if membership is absent."),
        _entry("eligibility-003", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Use the ordinal strength threshold only as declared.", "minimum_evidence_strength", "Hold unknown strength values."),
        _entry("eligibility-004", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Retain blockers alongside the eligible boolean.", "blockers", "Hold if blockers disappear."),
        _entry("eligibility-005", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Treat no observations as abstention, not as ineligibility.", "no_model_observations", "Stop if empty becomes negative."),
        _entry("eligibility-006", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Check cell state as a descriptive planning field.", "cell_state", "Hold an absent cell state for review."),
        _entry("eligibility-007", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Retain source identity for every model observation.", "source_id", "Stop on an unjoined observation."),
        _entry("eligibility-008", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Do not call a selected model representative without a separate validation record.", "claim boundary", "Stop on a fidelity claim."),
        _entry("eligibility-009", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Report both eligible count and total observation count.", "eligible_count and observation_count", "Stop when denominator is hidden."),
        _entry("eligibility-010", PlanningOperation.MODEL_ELIGIBILITY, "eligibility", "Use controls and readouts as planning context only.", "controls_readouts", "Stop if they are treated as measured outcomes."),
        _entry("guide-001", PlanningOperation.GUIDE_OLIGO, "guide", "Accept JSON only when rows are objects.", "input_format and row shape", "Quarantine non-object rows."),
        _entry("guide-002", PlanningOperation.GUIDE_OLIGO, "guide", "Accept CSV and TSV headers without rewriting source identity.", "header names", "Hold missing required columns."),
        _entry("guide-003", PlanningOperation.GUIDE_OLIGO, "guide", "Normalize DNA case while preserving the normalized sequence.", "sequence", "Quarantine unsupported bases."),
        _entry("guide-004", PlanningOperation.GUIDE_OLIGO, "guide", "Carry design, target, and oligo identity independently.", "design_id, target_id, oligo_id", "Hold an ambiguous identity."),
        _entry("guide-005", PlanningOperation.GUIDE_OLIGO, "guide", "Retain strand, offset, and PAM as optional context.", "strand, start_offset, pam", "Do not synthesize missing values."),
        _entry("guide-006", PlanningOperation.GUIDE_OLIGO, "guide", "Quarantine malformed rows without discarding their row address.", "quarantined", "Stop if the row cannot be traced."),
        _entry("guide-007", PlanningOperation.GUIDE_OLIGO, "guide", "Block a foreign guide context even if its sequence is valid.", "context_mismatch", "Stop on a context bypass."),
        _entry("guide-008", PlanningOperation.GUIDE_OLIGO, "guide", "Treat an empty source as abstention.", "empty_source", "Stop if empty becomes failure evidence."),
        _entry("guide-009", PlanningOperation.GUIDE_OLIGO, "guide", "Retain input hash and row address for replay.", "input_address and row_address", "Stop on an unaddressed adaptation."),
        _entry("guide-010", PlanningOperation.GUIDE_OLIGO, "guide", "Do not interpret sequence adaptation as activity or specificity.", "claim boundary", "Stop on an efficacy claim."),
        _entry("control-001", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Require an explicit plan identity.", "plan_id", "Stop on an anonymous plan."),
        _entry("control-002", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Require an explicit seed for deterministic assignments.", "randomization_seed", "Stop on an unstated seed."),
        _entry("control-003", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Separate control type from target condition.", "control_types and condition", "Hold a collapsed dimension."),
        _entry("control-004", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Make biological and technical replicate counts explicit.", "replicate fields", "Stop on an implicit count."),
        _entry("control-005", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Generate assignment identity from plan, seed, and dimensions.", "assignment_id", "Stop on a non-replayable assignment."),
        _entry("control-006", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Sort assignments by deterministic key for stable exports.", "randomization_key", "Stop on order drift."),
        _entry("control-007", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Hold missing target identity for review.", "missing_target_id", "Stop if an anonymous target is assigned."),
        _entry("control-008", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Block a foreign target context.", "context_mismatch", "Stop on a context bypass."),
        _entry("control-009", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Treat an empty target inventory as abstention.", "no_targets", "Stop if empty becomes negative evidence."),
        _entry("control-010", PlanningOperation.CONTROLS_RANDOMIZATION, "controls", "Do not call a deterministic plan balanced without a balance analysis.", "claim boundary", "Stop on a balance guarantee."),
        _entry("power-001", PlanningOperation.POWER_REPLICATION, "power", "Require a design and assay identity for every observation.", "design_id and assay_id", "Hold ambiguous observations."),
        _entry("power-002", PlanningOperation.POWER_REPLICATION, "power", "Reject non-finite effect and variance values.", "effect_size and variance", "Stop on invalid arithmetic."),
        _entry("power-003", PlanningOperation.POWER_REPLICATION, "power", "Require positive variance for the approximation.", "variance", "Stop on zero or negative variance."),
        _entry("power-004", PlanningOperation.POWER_REPLICATION, "power", "Keep alpha and target power inside the open unit interval.", "alpha and target_power", "Hold invalid fractions."),
        _entry("power-005", PlanningOperation.POWER_REPLICATION, "power", "Report planned and required repetitions together.", "planned_replicates and required_replicates", "Stop when shortfall is hidden."),
        _entry("power-006", PlanningOperation.POWER_REPLICATION, "power", "Expose blocking factor count as an assumption.", "blocking_factor_count", "Stop on a hidden multiplier."),
        _entry("power-007", PlanningOperation.POWER_REPLICATION, "power", "Keep observation source and context joins.", "source_id and context_key", "Stop on an unjoined observation."),
        _entry("power-008", PlanningOperation.POWER_REPLICATION, "power", "Treat a replicate shortfall as review, not as a failed assay.", "replicate_shortfall", "Stop if review becomes biological failure."),
        _entry("power-009", PlanningOperation.POWER_REPLICATION, "power", "Treat no observations as abstention.", "no_power_observations", "Stop if empty becomes zero effect."),
        _entry("power-010", PlanningOperation.POWER_REPLICATION, "power", "Keep the normal approximation named in every released estimate.", "assumptions", "Stop if assumptions are omitted."),
        _entry("quality-001", None, "quality", "Run five checks for each fixture row.", "evaluation checks", "Stop on a missing plane."),
        _entry("quality-002", None, "quality", "Reconcile expected and observed states.", "state check", "Stop on an unexpected state."),
        _entry("quality-003", None, "quality", "Check the expected issue code floor.", "issue check", "Stop when issue codes disappear."),
        _entry("quality-004", None, "quality", "Check role separation.", "role check", "Stop on an unlabeled control."),
        _entry("quality-005", None, "quality", "Check content addresses.", "integrity check", "Stop on an unaddressed result."),
        _entry("quality-006", None, "quality", "Check private-marker projection.", "safety check", "Stop on a private marker."),
        _entry("quality-007", None, "quality", "Require source, record, and operation closure.", "data audit", "Stop on an imbalanced fixture."),
        _entry("quality-008", None, "quality", "Require at least three visible states.", "state distribution", "Stop when controls collapse to one state."),
        _entry("quality-009", None, "quality", "Retain all held rows in the review queue.", "review queue", "Stop on a silent drop."),
        _entry("quality-010", None, "quality", "Keep the public boundary in the report.", "claim boundary", "Stop when exclusions disappear."),
        _entry("replay-001", None, "replay", "Run the same fixture twice.", "replay receipt", "Stop on an address difference."),
        _entry("replay-002", None, "replay", "Compare execution addresses, not only counts.", "execution addresses", "Stop on a shallow replay."),
        _entry("replay-003", None, "replay", "Compare output ordering for deterministic assignments.", "sorted assignments", "Stop on order drift."),
        _entry("replay-004", None, "replay", "Keep the replay identity separate from the fixture identity.", "replay_id", "Stop on identity collision."),
        _entry("replay-005", None, "replay", "Do not call replay independent biological replication.", "claim boundary", "Stop on a replication claim."),
        _entry("release-001", None, "release", "Include only addressed artifacts.", "artifact inventory", "Stop on an unaddressed artifact."),
        _entry("release-002", None, "release", "Separate ready rows from held rows.", "release manifest", "Stop on a held row in the ready set."),
        _entry("release-003", None, "release", "List excluded uses in the release package.", "excluded claims", "Stop when exclusions are missing."),
        _entry("release-004", None, "release", "Retain source citations with the package.", "source registry", "Stop on an orphaned citation."),
        _entry("release-005", None, "release", "Require quality, provenance, and boundary acceptance.", "quality and provenance", "Stop on a partial gate."),
        _entry("release-006", None, "release", "Use the release address as a comparison key.", "package content_address", "Stop on a mutable package."),
        _entry("handoff-001", None, "handoff", "Give reviewers the exact context key.", "handoff summary", "Stop on an implicit context."),
        _entry("handoff-002", None, "handoff", "Give reviewers issue-specific next actions.", "diagnostics", "Stop on a generic action only."),
        _entry("handoff-003", None, "handoff", "Keep controls in the handoff.", "control coverage", "Stop on a positive-only handoff."),
        _entry("handoff-004", None, "handoff", "Mention assumptions for power estimates.", "power output", "Stop on an assumption-free handoff."),
        _entry("handoff-005", None, "handoff", "Keep research-only language visible.", "claim boundary", "Stop on a clinical interpretation."),
        _entry("audit-001", None, "audit", "Log every runtime stage with an output address.", "stage ledger", "Stop on a missing stage address."),
        _entry("audit-002", None, "audit", "Keep stage sequence numbers contiguous.", "stage sequence", "Stop on a sequence gap."),
        _entry("audit-003", None, "audit", "Record held state rather than coercing to complete.", "stage state", "Stop on a held-to-complete coercion."),
        _entry("audit-004", None, "audit", "Record operation and role in every execution.", "execution record", "Stop on an unlabeled execution."),
        _entry("audit-005", None, "audit", "Record a diagnostic for every issue code.", "diagnostics", "Stop on an unexplained issue."),
        _entry("maintenance-001", None, "maintenance", "Update the contract catalog when required fields change.", "contract catalog", "Stop on undocumented drift."),
        _entry("maintenance-002", None, "maintenance", "Update the data dictionary when output fields change.", "data dictionary", "Stop on an undocumented output."),
        _entry("maintenance-003", None, "maintenance", "Regenerate the example fixture after contract changes.", "example hash", "Stop on a stale fixture."),
        _entry("maintenance-004", None, "maintenance", "Run focused tests before the full suite.", "test commands", "Stop on a focused regression."),
        _entry("maintenance-005", None, "maintenance", "Commit only after a clean metadata scan.", "repository scan", "Stop on forbidden metadata."),
        _entry("maintenance-006", None, "maintenance", "Keep the main branch release commit address visible.", "git log", "Stop before a remote verification."),
    )
    phase_counts: dict[str, int] = {}
    for item in entries:
        phase_counts[item.phase] = phase_counts.get(item.phase, 0) + 1
    accepted = bool(len(entries) >= 80 and all(item.content_address.startswith("planning-playbook-entry:") for item in entries))
    body = {"version": PLAYBOOK_VERSION, "entries": entries, "phase_counts": phase_counts, "accepted": accepted}
    return PlanningPlaybook(PLAYBOOK_VERSION, entries, phase_counts, accepted, content_hash(body, prefix="planning-playbook"))


__all__ = ["PLAYBOOK_VERSION", "PlanningPlaybook", "PlanningPlaybookEntry", "default_planning_playbook"]
