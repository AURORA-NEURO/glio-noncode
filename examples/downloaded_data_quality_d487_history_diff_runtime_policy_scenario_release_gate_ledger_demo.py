"""Record successive D486 decisions in an append-only D487 ledger."""

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
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_audit as audit_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_query as query_model
from glio_noncode import downloaded_data_quality_d487_history_diff_runtime_policy_scenario_release_gate_ledger_query_audit as query_audit_model


def _runtime_policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(policy_id, diff_id, maximum_added=maximum_added, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d487-strict-runtime", policy=_runtime_policy("glio-noncode-d487-strict-policy", source_diff.diff_id, maximum_added=0))
    release = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d487-release-runtime", policy=_runtime_policy("glio-noncode-d487-release-policy", source_diff.diff_id, maximum_added=1))
    scenario = scenario_model.run_scenario((strict, release), scenario_id="glio-noncode-d487-controlled-scenario", policy=scenario_model.build_policy("glio-noncode-d487-scenario-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_at_least_one_blocked=True, allow_mixed=True))
    scenario_audit = scenario_audit_model.audit_scenario(scenario, (strict, release))
    scenario_query = scenario_query_model.query_scenario(scenario, resources=scenario_query_model.RESOURCES, limit=scenario_query_model.MAX_LIMIT)
    scenario_query_audit = scenario_query_audit_model.audit_query(scenario_query, scenario)
    blocked = gate_model.build_gate(scenario, gate_id="glio-noncode-d487-default-gate", audit=scenario_audit, query=scenario_query, query_audit=scenario_query_audit)
    ready_policy = gate_model.build_policy("glio-noncode-d487-ready-gate-policy", scenario.scenario_id, minimum_ready=1, maximum_blocked=1, minimum_added_margin=-1, minimum_removed_margin=0, minimum_changed_margin=0, disallowed_risk_flags=(), require_scenario_accepted=True, require_scenario_release_ready=True, require_audit_accepted=True, require_query_complete=True, require_query_audit_accepted=True)
    ready = gate_model.build_gate(scenario, gate_id="glio-noncode-d487-controlled-gate", policy=ready_policy, audit=scenario_audit, query=scenario_query, query_audit=scenario_query_audit)
    ledger_policy = ledger_model.build_policy("glio-noncode-d487-ledger-policy", "glio-noncode-d487-ledger", minimum_decisions=2, minimum_ready=1, maximum_blocked=1, require_same_scenario=True, require_unique_gate_ids=True, require_unique_gate_addresses=True, require_contiguous_sequence=True, require_supersession_links=True, require_final_ready=True, allow_reopened=False)
    ledger = ledger_model.run_ledger((blocked, ready), ledger_id="glio-noncode-d487-ledger", policy=ledger_policy, decision_ids=("glio-noncode-d487-blocked-decision", "glio-noncode-d487-ready-decision"), supersedes_decision_ids=("", "glio-noncode-d487-blocked-decision"))
    audit = audit_model.audit_ledger(ledger, (blocked, ready))
    query = query_model.query_ledger(ledger, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, ledger)
    result: dict[str, Any] = {"source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None, "source_diff_id": source_diff.diff_id, "scenario_id": scenario.scenario_id, "ledger_id": ledger.ledger_id, "state": ledger.state, "release_ready": ledger.release_ready, "accepted": ledger.accepted, "transition": ledger.transition, "entry_count": ledger.entry_count, "ready_count": ledger.ready_count, "blocked_count": ledger.blocked_count, "superseded_count": ledger.superseded_count, "head_decision_id": ledger.head_decision_id, "decisions": [{"decision_id": item.decision_id, "gate_id": item.gate_id, "state": item.state, "release_ready": item.release_ready, "transition": item.transition, "supersedes_decision_id": item.supersedes_decision_id} for item in ledger.entries], "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted}, "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted}, "ledger_address": ledger.content_address}
    if destination is not None:
        root = Path(destination); root.mkdir(parents=True, exist_ok=True); ledger_directory = ledger_model.persist_ledger(ledger, root / "ledger", overwrite=True); (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8"); (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8"); (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8"); result["output_directory"] = str(root.resolve()); result["ledger_directory"] = str(ledger_directory.resolve()); (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record successive D486 decisions in a D487 append-only ledger")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D483 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args(); result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["release_ready"] and result["audit"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
