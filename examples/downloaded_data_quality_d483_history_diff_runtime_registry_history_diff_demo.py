"""Compare blocked and ready D482 runtime registry histories from real data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as source_diff_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff_query_audit as query_audit_model


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source_diff = source_diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d483-strict-runtime", policy=runtime_model.build_policy("glio-noncode-d483-strict-policy", source_diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    release = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d483-release-runtime", policy=runtime_model.build_policy("glio-noncode-d483-release-policy", source_diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked = registry_model.build_registry((strict, release), registry_id="glio-noncode-d483-blocked-registry", policy=registry_model.build_policy("glio-noncode-d483-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    ready = registry_model.build_registry((strict, release), registry_id="glio-noncode-d483-ready-registry", policy=registry_model.build_policy("glio-noncode-d483-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False))
    left = history_model.build_history(blocked, history_id="glio-noncode-d483-release-history", snapshot_id="blocked")
    right = history_model.append_history(left, ready, snapshot_id="ready", expected_head=left.entries[-1].content_address)
    value = diff_model.run_diff(left, right, diff_id="glio-noncode-d483-release-history-diff")
    audit = audit_model.audit_diff(value, left, right)
    query = query_model.query_diff(value, resources=("items", "changes", "direction"), change_filter="added", limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, value)
    result: dict[str, Any] = {"source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None, "source_diff_id": source_diff.diff_id, "diff_id": value.diff_id, "direction": value.direction, "state_transition": value.state_transition, "item_count": value.item_count, "added_count": value.added_count, "removed_count": value.removed_count, "changed_count": value.changed_count, "unchanged_count": value.unchanged_count, "accepted": value.accepted, "audit_check_count": audit.check_count, "audit_passed_count": audit.passed_count, "audit_accepted": audit.accepted, "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted}, "diff_address": value.content_address}
    if destination is not None:
        root = Path(destination); root.mkdir(parents=True, exist_ok=True); diff_directory_out = root / "diff"; diff_model.persist_diff(value, diff_directory_out, overwrite=True); (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8"); (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8"); (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8"); result["output_directory"] = str(root.resolve()); result["diff_directory"] = str(diff_directory_out.resolve()); (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare D482 runtime registry histories with D483")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D479 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args(); result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["accepted"] and result["audit_accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
