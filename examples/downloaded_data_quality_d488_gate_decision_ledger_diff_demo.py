"""Compare baseline and candidate D487 decision ledgers from downloaded data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as scenario_audit_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as scenario_query_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as scenario_query_audit_model
from glio_noncode import downloaded_data_quality_d486_history_diff_runtime_policy_scenario_release_gate as gate_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger as ledger_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as ledger_diff_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_query as query_model
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff_query_audit as query_audit_model


def _runtime_policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(
        policy_id,
        diff_id,
        maximum_added=maximum_added,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_accepted=True,
        require_state_change=True,
        allow_unchanged=True,
    )


def build_demo(
    diff_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d488-strict-runtime",
        policy=_runtime_policy("glio-noncode-d488-strict-policy", source_diff.diff_id, maximum_added=0),
    )
    release = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d488-release-runtime",
        policy=_runtime_policy("glio-noncode-d488-release-policy", source_diff.diff_id, maximum_added=1),
    )
    scenario = scenario_model.run_scenario(
        (strict, release),
        scenario_id="glio-noncode-d488-controlled-scenario",
        policy=scenario_model.build_policy(
            "glio-noncode-d488-scenario-policy",
            minimum_runtimes=2,
            minimum_ready=1,
            maximum_blocked=1,
            require_at_least_one_blocked=True,
            allow_mixed=True,
        ),
    )
    scenario_audit = scenario_audit_model.audit_scenario(scenario, (strict, release))
    scenario_query = scenario_query_model.query_scenario(scenario, resources=scenario_query_model.RESOURCES, limit=scenario_query_model.MAX_LIMIT)
    scenario_query_audit = scenario_query_audit_model.audit_query(scenario_query, scenario)
    blocked = gate_model.build_gate(
        scenario,
        gate_id="glio-noncode-d488-default-gate",
        audit=scenario_audit,
        query=scenario_query,
        query_audit=scenario_query_audit,
    )
    ready = gate_model.build_gate(
        scenario,
        gate_id="glio-noncode-d488-controlled-gate",
        policy=gate_model.build_policy(
            "glio-noncode-d488-ready-gate-policy",
            scenario.scenario_id,
            minimum_ready=1,
            maximum_blocked=1,
            minimum_added_margin=-1,
            minimum_removed_margin=0,
            minimum_changed_margin=0,
            disallowed_risk_flags=(),
            require_scenario_accepted=True,
            require_scenario_release_ready=True,
            require_audit_accepted=True,
            require_query_complete=True,
            require_query_audit_accepted=True,
        ),
        audit=scenario_audit,
        query=scenario_query,
        query_audit=scenario_query_audit,
    )
    ledger_id = "glio-noncode-d488-ledger"
    baseline = ledger_model.run_ledger(
        (blocked,),
        ledger_id=ledger_id,
        policy=ledger_model.build_policy(
            "glio-noncode-d488-baseline-ledger-policy",
            ledger_id,
            minimum_decisions=1,
            minimum_ready=0,
            maximum_blocked=1,
            require_supersession_links=False,
            require_final_ready=False,
            allow_reopened=False,
        ),
        decision_ids=("glio-noncode-d488-blocked-decision",),
        supersedes_decision_ids=("",),
    )
    candidate = ledger_model.run_ledger(
        (blocked, ready),
        ledger_id=ledger_id,
        policy=ledger_model.build_policy(
            "glio-noncode-d488-candidate-ledger-policy",
            ledger_id,
            minimum_decisions=2,
            minimum_ready=1,
            maximum_blocked=1,
            require_supersession_links=True,
            require_final_ready=True,
            allow_reopened=False,
        ),
        decision_ids=("glio-noncode-d488-blocked-decision", "glio-noncode-d488-ready-decision"),
        supersedes_decision_ids=("", "glio-noncode-d488-blocked-decision"),
    )
    policy = ledger_diff_model.build_policy(
        "glio-noncode-d488-ledger-diff-policy",
        baseline.ledger_id,
        candidate.ledger_id,
        minimum_items=2,
        maximum_added=1,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_same_scenario=True,
        require_append_only=True,
        require_head_change=True,
        require_accepted=True,
    )
    value = ledger_diff_model.run_diff(
        baseline,
        candidate,
        diff_id="glio-noncode-d488-ledger-diff",
        policy=policy,
    )
    audit = audit_model.audit_diff(value, baseline, candidate)
    query = query_model.query_diff(value, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, value)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "scenario_id": scenario.scenario_id,
        "baseline": {"ledger_id": baseline.ledger_id, "state": baseline.state, "release_ready": baseline.release_ready, "head_decision_id": baseline.head_decision_id},
        "candidate": {"ledger_id": candidate.ledger_id, "state": candidate.state, "release_ready": candidate.release_ready, "head_decision_id": candidate.head_decision_id},
        "diff": {"diff_id": value.diff_id, "direction": value.direction, "state_transition": value.state_transition, "item_count": value.item_count, "added_count": value.added_count, "removed_count": value.removed_count, "changed_count": value.changed_count, "unchanged_count": value.unchanged_count, "accepted": value.accepted, "release_ready": value.release_ready, "address": value.content_address, "changed_decisions": [{"decision_id": item.decision_id, "change": item.change, "changed_fields": list(item.changed_fields)} for item in value.items if item.change != "unchanged"]},
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        baseline_directory = ledger_model.persist_ledger(baseline, root / "baseline-ledger", overwrite=True)
        candidate_directory = ledger_model.persist_ledger(candidate, root / "candidate-ledger", overwrite=True)
        diff_directory = ledger_diff_model.persist_diff(value, root / "diff", overwrite=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["baseline_ledger_directory"] = str(baseline_directory.resolve())
        result["candidate_ledger_directory"] = str(candidate_directory.resolve())
        result["diff_directory"] = str(diff_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate D487 ledgers from downloaded data")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D483 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["diff"]["release_ready"] and result["audit"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
