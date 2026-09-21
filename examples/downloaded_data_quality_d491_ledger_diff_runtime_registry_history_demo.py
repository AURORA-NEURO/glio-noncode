"""Track D490 runtime registries as an append-only history over downloaded data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d491_ledger_diff_runtime_registry_history_query_audit as query_audit_model


def _runtime_policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(policy_id, diff_id, minimum_items=2, maximum_added=maximum_added, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)


def _registry_policy(policy_id: str, *, minimum_ready: int, maximum_blocked: int, require_release_ready: bool) -> registry_model.RegistryPolicy:
    return registry_model.build_policy(policy_id, minimum_runtimes=2, minimum_ready=minimum_ready, maximum_blocked=maximum_blocked, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=require_release_ready)


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d491-strict-runtime", policy=_runtime_policy("glio-noncode-d491-strict-policy", source_diff.diff_id, maximum_added=0))
    release = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d491-release-runtime", policy=_runtime_policy("glio-noncode-d491-release-policy", source_diff.diff_id, maximum_added=1))
    runtimes = (strict, release)
    blocked = registry_model.build_registry(runtimes, registry_id="glio-noncode-d491-blocked-registry", policy=_registry_policy("glio-noncode-d491-blocked-policy", minimum_ready=2, maximum_blocked=0, require_release_ready=True))
    ready = registry_model.build_registry(runtimes, registry_id="glio-noncode-d491-ready-registry", policy=_registry_policy("glio-noncode-d491-ready-policy", minimum_ready=1, maximum_blocked=1, require_release_ready=False))
    history = history_model.build_history(blocked, history_id="glio-noncode-d491-history", snapshot_id="blocked")
    history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
    history_audit = audit_model.audit_history(history, (blocked, ready))
    history_query = query_model.query_history(history, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    history_query_audit = query_audit_model.audit_query(history_query, history)
    promoted_query = query_model.query_history(history, resources=("transitions",), transition_filter="promoted", limit=query_model.MAX_LIMIT)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "runtimes": {item.runtime_id: {"state": item.state, "release_ready": item.release_ready, "accepted": item.accepted} for item in runtimes},
        "registries": {"blocked": {"registry_id": blocked.registry_id, "state": blocked.state, "release_ready": blocked.release_ready, "address": blocked.content_address}, "ready": {"registry_id": ready.registry_id, "state": ready.state, "release_ready": ready.release_ready, "address": ready.content_address}},
        "history": {"history_id": history.history_id, "entry_count": history.entry_count, "initial_count": history.initial_count, "promoted_count": history.promoted_count, "regressed_count": history.regressed_count, "latest_state": history.latest_state, "latest_release_ready": history.latest_release_ready, "latest_accepted": history.latest_accepted, "address": history.content_address},
        "audit": {"check_count": history_audit.check_count, "passed_count": history_audit.passed_count, "accepted": history_audit.accepted},
        "query": {"total_count": history_query.total_count, "returned_count": history_query.returned_count, "truncated": history_query.truncated, "audit_check_count": history_query_audit.check_count, "audit_passed_count": history_query_audit.passed_count, "audit_accepted": history_query_audit.accepted},
        "promoted_query": {"total_count": promoted_query.total_count, "returned_count": promoted_query.returned_count, "truncated": promoted_query.truncated, "snapshots": [item.key for item in promoted_query.rows]},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        history_directory = history_model.persist_history(history, root / "history", overwrite=True)
        (root / "history-audit.json").write_text(audit_model.audit_json(history_audit) + "\n", encoding="utf-8")
        (root / "history-query.json").write_text(query_model.query_json(history_query) + "\n", encoding="utf-8")
        (root / "history-query-audit.json").write_text(query_audit_model.audit_json(history_query_audit) + "\n", encoding="utf-8")
        (root / "promoted-query.json").write_text(query_model.query_json(promoted_query) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["history_directory"] = str(history_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an append-only D491 runtime registry history from a downloaded ledger diff")
    parser.add_argument("diff_directory", type=Path, help="exact six-file D488 ledger diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["history"]["latest_state"] == "ready" and result["history"]["latest_release_ready"] and result["history"]["latest_accepted"] and result["audit"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] and result["promoted_query"]["returned_count"] == 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
