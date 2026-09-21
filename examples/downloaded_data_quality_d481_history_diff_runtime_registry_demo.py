"""Aggregate a real D479 history diff into a policy-controlled D481 registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry_query_audit as query_audit_model


def _decision(value: runtime_model.DiffRuntime, audit: Any) -> dict[str, Any]:
    return {"runtime_id": value.runtime_id, "state": value.state, "release_ready": value.release_ready, "passed_count": value.passed_count, "check_count": value.check_count, "failed_checks": [item.check_id for item in value.checks if not item.passed], "audit_passed_count": audit.passed_count, "audit_check_count": audit.check_count, "audit_accepted": audit.accepted, "runtime_address": value.content_address}


def _registry_decision(value: registry_model.RuntimeRegistry, audit: Any) -> dict[str, Any]:
    return {"registry_id": value.registry_id, "state": value.state, "release_ready": value.release_ready, "accepted": value.accepted, "entry_count": value.entry_count, "ready_count": value.ready_count, "blocked_count": value.blocked_count, "audited_count": value.audited_count, "passed_count": sum(item.passed for item in value.checks), "check_count": len(value.checks), "failed_checks": [item.check_id for item in value.checks if not item.passed], "audit_passed_count": audit.passed_count, "audit_check_count": audit.check_count, "audit_accepted": audit.accepted, "registry_address": value.content_address}


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    diff = diff_model.load_diff(diff_directory)
    strict_policy = runtime_model.build_policy("glio-noncode-d481-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)
    release_policy = runtime_model.build_policy("glio-noncode-d481-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)
    strict = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d481-strict-runtime", policy=strict_policy)
    release = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d481-release-runtime", policy=release_policy)
    strict_audit = runtime_audit_model.audit_runtime(strict, diff)
    release_audit = runtime_audit_model.audit_runtime(release, diff)
    controlled_policy = registry_model.build_policy("glio-noncode-d481-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=True, require_release_ready=False)
    controlled = registry_model.run_registry((strict, release), registry_id="glio-noncode-d481-controlled-registry", policy=controlled_policy, audit_addresses={strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address})
    controlled_audit = audit_model.audit_registry(controlled, (strict, release))
    controlled_query = query_model.query_registry(controlled, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    controlled_query_audit = query_audit_model.audit_query(controlled_query, controlled)
    all_ready_policy = registry_model.build_policy("glio-noncode-d481-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=True, require_release_ready=True)
    all_ready = registry_model.build_registry((strict, release), registry_id="glio-noncode-d481-all-ready-preview", policy=all_ready_policy, audit_addresses={strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address})
    result: dict[str, Any] = {"source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None, "diff_id": diff.diff_id, "direction": diff.direction, "state_transition": diff.state_transition, "item_count": diff.item_count, "added_count": diff.added_count, "removed_count": diff.removed_count, "changed_count": diff.changed_count, "unchanged_count": diff.unchanged_count, "strict_runtime": _decision(strict, strict_audit), "release_runtime": _decision(release, release_audit), "controlled_registry": _registry_decision(controlled, controlled_audit), "controlled_query": {"total_count": controlled_query.total_count, "returned_count": controlled_query.returned_count, "truncated": controlled_query.truncated, "audit_check_count": controlled_query_audit.check_count, "audit_passed_count": controlled_query_audit.passed_count, "audit_accepted": controlled_query_audit.accepted}, "all_ready_preview": {"state": all_ready.state, "release_ready": all_ready.release_ready, "failed_checks": [item.check_id for item in all_ready.checks if not item.passed], "entry_count": all_ready.entry_count}}
    if destination is not None:
        root = Path(destination); root.mkdir(parents=True, exist_ok=True); registry_directory = root / "controlled-registry"; registry_model.persist_registry(controlled, registry_directory, overwrite=True); (root / "registry-audit.json").write_text(audit_model.audit_json(controlled_audit) + "\n", encoding="utf-8"); (root / "registry-query.json").write_text(query_model.query_json(controlled_query) + "\n", encoding="utf-8"); (root / "registry-query-audit.json").write_text(query_audit_model.audit_json(controlled_query_audit) + "\n", encoding="utf-8"); result["output_directory"] = str(root.resolve()); result["registry_directory"] = str(registry_directory.resolve()); (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate a D479 history diff with D481")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D479 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args(); result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["controlled_registry"]["release_ready"] and result["controlled_registry"]["audit_accepted"] and result["controlled_query"]["audit_accepted"] and not result["controlled_query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
