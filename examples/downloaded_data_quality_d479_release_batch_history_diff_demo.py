"""Compare D478 release-batch histories derived from real downloaded data.

The demonstration consumes the real D475 diff derived from the downloaded
source archive, creates a blocked history head and a ready promoted head, and
then compares the two D478 histories with field-level, address-preserving
diffs.

Example::

    python examples/downloaded_data_quality_d479_release_batch_history_diff_demo.py \
        artifacts/d475-real/diff \
        --destination artifacts/d479-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d475_history_diff as source_diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d478_release_batch_history as history_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff_query_audit as query_audit_model


def _runtime(diff: source_diff_model.HistoryDiff, runtime_id: str, policy_id: str, *, maximum_added: int, maximum_changed: int, require_state_change: bool) -> runtime_model.DiffRuntime:
    policy = runtime_model.build_policy(policy_id, diff.diff_id, maximum_added=maximum_added, maximum_removed=0, maximum_changed=maximum_changed, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=require_state_change, allow_unchanged=True)
    return runtime_model.run_runtime(diff, runtime_id=runtime_id, policy=policy)


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source_diff = source_diff_model.load_diff(diff_directory)
    strict = _runtime(source_diff, "glio-noncode-d479-strict-runtime", "glio-noncode-d479-strict-policy", maximum_added=0, maximum_changed=0, require_state_change=False)
    release = _runtime(source_diff, "glio-noncode-d479-release-runtime", "glio-noncode-d479-release-policy", maximum_added=1, maximum_changed=1, require_state_change=True)
    blocked = batch_model.build_batch((strict, release), batch_id="glio-noncode-d479-blocked-batch", policy=batch_model.build_policy("glio-noncode-d479-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True))
    ready = batch_model.build_batch((strict, release), batch_id="glio-noncode-d479-ready-batch", policy=batch_model.build_policy("glio-noncode-d479-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=False, require_release_ready=False))
    left = history_model.build_history(blocked, history_id="glio-noncode-d479-release-history", snapshot_id="all-ready-preview")
    right = history_model.append_history(left, ready, snapshot_id="controlled-promotion", expected_head=left.entries[-1].content_address)
    value = diff_model.run_diff(left, right, diff_id="glio-noncode-d479-release-history-diff")
    audit = audit_model.audit_diff(value, left, right)
    query = query_model.query_diff(value, resources=("items", "changes", "direction"), change_filter="added", limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, value)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "diff_id": value.diff_id,
        "direction": value.direction,
        "state_transition": value.state_transition,
        "item_count": value.item_count,
        "added_count": value.added_count,
        "removed_count": value.removed_count,
        "changed_count": value.changed_count,
        "unchanged_count": value.unchanged_count,
        "accepted": value.accepted,
        "audit_check_count": audit.check_count,
        "audit_passed_count": audit.passed_count,
        "audit_accepted": audit.accepted,
        "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
        "diff_address": value.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        diff_directory_out = root / "diff"
        diff_model.persist_diff(value, diff_directory_out, overwrite=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["diff_directory"] = str(diff_directory_out.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare D478 release-batch histories")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D475 diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["accepted"] and result["audit_accepted"] and result["query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
