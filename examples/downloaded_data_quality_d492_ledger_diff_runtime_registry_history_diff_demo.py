"""Compare baseline/candidate D491 registry histories built from downloaded data."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any
from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as source_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff_query_audit as query_audit_model

def _runtime_policy(policy_id: str, diff_id: str, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(policy_id, diff_id, minimum_items=2, maximum_added=maximum_added, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)

def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source = source_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(source, runtime_id="glio-noncode-d492-strict-runtime", policy=_runtime_policy("glio-noncode-d492-strict-policy", source.diff_id, 0))
    release = runtime_model.run_runtime(source, runtime_id="glio-noncode-d492-release-runtime", policy=_runtime_policy("glio-noncode-d492-release-policy", source.diff_id, 1))
    runtimes = (strict, release)
    blocked_policy = registry_model.build_policy("glio-noncode-d492-blocked-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True)
    ready_policy = registry_model.build_policy("glio-noncode-d492-ready-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False)
    blocked = registry_model.build_registry(runtimes, registry_id="glio-noncode-d492-blocked-registry", policy=blocked_policy)
    ready = registry_model.build_registry(runtimes, registry_id="glio-noncode-d492-ready-registry", policy=ready_policy)
    baseline = history_model.build_history(blocked, history_id="glio-noncode-d492-history", snapshot_id="blocked")
    candidate = history_model.append_history(baseline, ready, snapshot_id="ready", expected_head=baseline.entries[-1].content_address)
    diff = diff_model.build_diff(baseline, candidate, diff_id="glio-noncode-d492-history-diff")
    audit = audit_model.audit_diff(diff, baseline, candidate)
    query = query_model.query_diff(diff, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, diff)
    added_query = query_model.query_diff(diff, resources=("items",), change_filter="added", limit=query_model.MAX_LIMIT)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source.diff_id,
        "runtimes": {item.runtime_id: {"state": item.state, "release_ready": item.release_ready, "accepted": item.accepted} for item in runtimes},
        "histories": {"baseline": {"entry_count": baseline.entry_count, "latest_state": baseline.latest_state, "address": baseline.content_address}, "candidate": {"entry_count": candidate.entry_count, "latest_state": candidate.latest_state, "address": candidate.content_address}},
        "diff": {"diff_id": diff.diff_id, "added_count": diff.added_count, "removed_count": diff.removed_count, "changed_count": diff.changed_count, "unchanged_count": diff.unchanged_count, "direction": diff.direction, "state_transition": diff.state_transition, "accepted": diff.accepted, "address": diff.content_address},
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
        "added_snapshot_query": {"total_count": added_query.total_count, "returned_count": added_query.returned_count, "snapshots": [row.key for row in added_query.rows]},
    }
    if destination is not None:
        root = Path(destination); root.mkdir(parents=True, exist_ok=True)
        output = diff_model.persist_diff(diff, root / "diff", overwrite=True)
        (root / "diff-audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "diff-query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "diff-query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        (root / "added-snapshot-query.json").write_text(query_model.query_json(added_query) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve()); result["diff_directory"] = str(output.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description="Compare baseline and candidate runtime-registry histories from a downloaded ledger diff")
    parser.add_argument("diff_directory", type=Path, help="exact D488 ledger-diff artifact directory")
    parser.add_argument("--destination", type=Path); parser.add_argument("--source-zip", type=Path, help="optional supplied archive provenance")
    args = parser.parse_args(); result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip); print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["diff"]["accepted"] and result["diff"]["direction"] == "improved" and result["audit"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2

if __name__ == "__main__": raise SystemExit(main())
