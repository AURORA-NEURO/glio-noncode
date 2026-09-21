"""Record D477 release-batch promotion history from real downloaded data.

The demonstration consumes the real D475 diff derived from the downloaded
source archive, creates a blocked all-ready batch and a ready controlled batch,
then appends both to one D478 history with optimistic head verification.

Example::

    python examples/downloaded_data_quality_d478_release_batch_history_demo.py \
        artifacts/d475-real/diff \
        --destination artifacts/d478-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d475_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history as history_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_query as query_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history_query_audit as query_audit_model


def _runtime(diff: diff_model.HistoryDiff, runtime_id: str, policy_id: str, *, maximum_added: int, maximum_changed: int, require_state_change: bool) -> runtime_model.DiffRuntime:
    policy = runtime_model.build_policy(policy_id, diff.diff_id, maximum_added=maximum_added, maximum_removed=0, maximum_changed=maximum_changed, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=require_state_change, allow_unchanged=True)
    return runtime_model.run_runtime(diff, runtime_id=runtime_id, policy=policy)


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    diff = diff_model.load_diff(diff_directory)
    strict = _runtime(diff, "glio-noncode-d478-strict-runtime", "glio-noncode-d478-strict-policy", maximum_added=0, maximum_changed=0, require_state_change=False)
    release = _runtime(diff, "glio-noncode-d478-release-runtime", "glio-noncode-d478-release-policy", maximum_added=1, maximum_changed=1, require_state_change=True)
    blocked_policy = batch_model.build_policy("glio-noncode-d478-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True)
    ready_policy = batch_model.build_policy("glio-noncode-d478-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False)
    blocked = batch_model.build_batch((strict, release), batch_id="glio-noncode-d478-blocked-batch", policy=blocked_policy)
    ready = batch_model.build_batch((strict, release), batch_id="glio-noncode-d478-ready-batch", policy=ready_policy)
    initial = history_model.build_history(blocked, history_id="glio-noncode-d478-release-history", snapshot_id="all-ready-preview")
    history = history_model.append_history(initial, ready, snapshot_id="controlled-promotion", expected_head=initial.entries[-1].content_address)
    history_audit = audit_model.audit_history(history, (blocked, ready))
    promotion_query = query_model.query_history(history, resources=("entries", "transitions", "readiness"), transition_filter="promoted", limit=query_model.MAX_LIMIT)
    promotion_query_audit = query_audit_model.audit_query(promotion_query, history)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "diff_id": diff.diff_id,
        "direction": diff.direction,
        "state_transition": diff.state_transition,
        "blocked_batch": {"state": blocked.state, "release_ready": blocked.release_ready, "failed_checks": [item.check_id for item in blocked.checks if not item.passed], "batch_address": blocked.content_address},
        "ready_batch": {"state": ready.state, "release_ready": ready.release_ready, "failed_checks": [item.check_id for item in ready.checks if not item.passed], "batch_address": ready.content_address},
        "history": {"history_id": history.history_id, "entry_count": history.entry_count, "latest_state": history.latest_state, "latest_release_ready": history.latest_release_ready, "initial_count": history.initial_count, "promoted_count": history.promoted_count, "regressed_count": history.regressed_count, "transition": history.entries[-1].transition, "history_address": history.content_address, "audit_check_count": history_audit.check_count, "audit_passed_count": history_audit.passed_count, "audit_accepted": history_audit.accepted},
        "promotion_query": {"total_count": promotion_query.total_count, "returned_count": promotion_query.returned_count, "truncated": promotion_query.truncated, "audit_check_count": promotion_query_audit.check_count, "audit_passed_count": promotion_query_audit.passed_count, "audit_accepted": promotion_query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        history_directory = root / "history"
        history_model.persist_history(history, history_directory, overwrite=True)
        (root / "history-audit.json").write_text(audit_model.audit_json(history_audit) + "\n", encoding="utf-8")
        (root / "promotion-query.json").write_text(query_model.query_json(promotion_query) + "\n", encoding="utf-8")
        (root / "promotion-query-audit.json").write_text(query_audit_model.audit_json(promotion_query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["history_directory"] = str(history_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record D477 release-batch promotion history")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D475 diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["history"]["latest_release_ready"] and result["history"]["audit_accepted"] and result["promotion_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
