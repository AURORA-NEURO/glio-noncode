"""Promote multiple D476 decisions into a D477 release batch.

The demonstration consumes the real D475 diff derived from the downloaded
source archive, creates strict and release runtimes, links their runtime
audits, and evaluates a controlled batch that allows one blocked runtime while
requiring one ready runtime. It also evaluates the stricter all-ready policy so
the promotion boundary is visible.

Example::

    python examples/downloaded_data_quality_d477_release_batch_demo.py \
        artifacts/d475-real/diff \
        --destination artifacts/d477-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d475_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d476_history_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d477_release_batch as batch_model
from glio_noncode import downloaded_data_quality_d477_release_batch_audit as audit_model
from glio_noncode import downloaded_data_quality_d477_release_batch_query as query_model
from glio_noncode import downloaded_data_quality_d477_release_batch_query_audit as query_audit_model


def _runtime(diff: diff_model.HistoryDiff, runtime_id: str, policy_id: str, *, maximum_added: int, maximum_changed: int, require_state_change: bool) -> runtime_model.DiffRuntime:
    policy = runtime_model.build_policy(policy_id, diff.diff_id, maximum_added=maximum_added, maximum_removed=0, maximum_changed=maximum_changed, allowed_directions=("improved", "changed", "unchanged"), require_accepted=True, require_state_change=require_state_change, allow_unchanged=True)
    return runtime_model.run_runtime(diff, runtime_id=runtime_id, policy=policy)


def _decision(value: runtime_model.DiffRuntime, audit: Any) -> dict[str, Any]:
    return {"runtime_id": value.runtime_id, "state": value.state, "release_ready": value.release_ready, "passed_count": value.passed_count, "check_count": value.check_count, "failed_checks": [item.check_id for item in value.checks if not item.passed], "audit_passed_count": audit.passed_count, "audit_check_count": audit.check_count, "audit_accepted": audit.accepted, "runtime_address": value.content_address, "audit_address": audit.content_address}


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    diff = diff_model.load_diff(diff_directory)
    strict = _runtime(diff, "glio-noncode-d477-strict-runtime", "glio-noncode-d477-strict-policy", maximum_added=0, maximum_changed=0, require_state_change=False)
    release = _runtime(diff, "glio-noncode-d477-release-runtime", "glio-noncode-d477-release-policy", maximum_added=1, maximum_changed=1, require_state_change=True)
    strict_audit = runtime_audit_model.audit_runtime(strict, diff)
    release_audit = runtime_audit_model.audit_runtime(release, diff)
    evidence = {strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address}
    controlled_policy = batch_model.build_policy("glio-noncode-d477-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_audited=True, require_release_ready=False)
    controlled = batch_model.run_batch((strict, release), batch_id="glio-noncode-d477-controlled-batch", policy=controlled_policy, audit_addresses=evidence)
    controlled_audit = audit_model.audit_batch(controlled, (strict, release))
    controlled_query = query_model.query_batch(controlled, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    controlled_query_audit = query_audit_model.audit_query(controlled_query, controlled)
    all_ready_policy = batch_model.build_policy("glio-noncode-d477-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_audited=False, require_release_ready=True)
    all_ready = batch_model.build_batch((strict, release), batch_id="glio-noncode-d477-all-ready-preview", policy=all_ready_policy)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "diff_id": diff.diff_id,
        "direction": diff.direction,
        "state_transition": diff.state_transition,
        "item_count": diff.item_count,
        "strict_runtime": _decision(strict, strict_audit),
        "release_runtime": _decision(release, release_audit),
        "controlled_batch": {"batch_id": controlled.batch_id, "state": controlled.state, "release_ready": controlled.release_ready, "item_count": controlled.item_count, "ready_count": controlled.ready_count, "blocked_count": controlled.blocked_count, "audited_count": controlled.audited_count, "failed_checks": [item.check_id for item in controlled.checks if not item.passed], "audit_check_count": controlled_audit.check_count, "audit_passed_count": controlled_audit.passed_count, "audit_accepted": controlled_audit.accepted, "batch_address": controlled.content_address},
        "all_ready_preview": {"state": all_ready.state, "release_ready": all_ready.release_ready, "failed_checks": [item.check_id for item in all_ready.checks if not item.passed]},
        "controlled_query": {"total_count": controlled_query.total_count, "returned_count": controlled_query.returned_count, "truncated": controlled_query.truncated, "audit_check_count": controlled_query_audit.check_count, "audit_passed_count": controlled_query_audit.passed_count, "audit_accepted": controlled_query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        batch_directory = root / "controlled"
        batch_model.persist_batch(controlled, batch_directory, overwrite=True)
        (root / "strict-runtime-audit.json").write_text(runtime_audit_model.audit_json(strict_audit) + "\n", encoding="utf-8")
        (root / "release-runtime-audit.json").write_text(runtime_audit_model.audit_json(release_audit) + "\n", encoding="utf-8")
        (root / "controlled-batch-audit.json").write_text(audit_model.audit_json(controlled_audit) + "\n", encoding="utf-8")
        (root / "controlled-query.json").write_text(query_model.query_json(controlled_query) + "\n", encoding="utf-8")
        (root / "controlled-query-audit.json").write_text(query_audit_model.audit_json(controlled_query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["batch_directory"] = str(batch_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote D476 runtimes into a D477 release batch")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D475 diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["controlled_batch"]["release_ready"] and result["controlled_batch"]["audit_accepted"] and result["controlled_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
