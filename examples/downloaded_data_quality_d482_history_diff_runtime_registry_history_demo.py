"""Record blocked-to-ready D481 runtime registries in a D482 history."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d479_release_batch_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d480_release_batch_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d481_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d482_history_diff_runtime_registry_history_query_audit as query_audit_model


def _registry(value: registry_model.RuntimeRegistry) -> dict[str, Any]:
    return {"registry_id": value.registry_id, "state": value.state, "release_ready": value.release_ready, "accepted": value.accepted, "entry_count": value.entry_count, "ready_count": value.ready_count, "blocked_count": value.blocked_count, "audited_count": value.audited_count, "registry_address": value.content_address}


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d482-strict-runtime", policy=runtime_model.build_policy("glio-noncode-d482-strict-policy", diff.diff_id, maximum_added=0, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    release = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d482-release-runtime", policy=runtime_model.build_policy("glio-noncode-d482-release-policy", diff.diff_id, maximum_added=1, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True))
    blocked = registry_model.build_registry((strict, release), registry_id="glio-noncode-d482-blocked-registry", policy=registry_model.build_policy("glio-noncode-d482-all-ready-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    ready = registry_model.build_registry((strict, release), registry_id="glio-noncode-d482-ready-registry", policy=registry_model.build_policy("glio-noncode-d482-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=False))
    history = history_model.build_history(blocked, history_id="glio-noncode-d482-release-history", snapshot_id="blocked")
    history = history_model.append_history(history, ready, snapshot_id="ready", expected_head=history.entries[-1].content_address)
    history_audit = audit_model.audit_history(history, (blocked, ready))
    history_query = query_model.query_history(history, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    history_query_audit = query_audit_model.audit_query(history_query, history)
    promoted_query = query_model.query_history(history, resources=("transitions",), transition_filter="promoted", limit=query_model.MAX_LIMIT)
    result: dict[str, Any] = {"source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None, "diff_id": diff.diff_id, "direction": diff.direction, "state_transition": diff.state_transition, "blocked_registry": _registry(blocked), "ready_registry": _registry(ready), "history": {"history_id": history.history_id, "entry_count": history.entry_count, "initial_count": history.initial_count, "promoted_count": history.promoted_count, "regressed_count": history.regressed_count, "latest_state": history.latest_state, "latest_release_ready": history.latest_release_ready, "history_address": history.content_address, "audit_check_count": history_audit.check_count, "audit_passed_count": history_audit.passed_count, "audit_accepted": history_audit.accepted}, "history_query": {"total_count": history_query.total_count, "returned_count": history_query.returned_count, "truncated": history_query.truncated, "audit_check_count": history_query_audit.check_count, "audit_passed_count": history_query_audit.passed_count, "audit_accepted": history_query_audit.accepted}, "promoted_query": {"total_count": promoted_query.total_count, "returned_count": promoted_query.returned_count, "truncated": promoted_query.truncated}}
    if destination is not None:
        root = Path(destination); root.mkdir(parents=True, exist_ok=True); history_directory = root / "history"; history_model.persist_history(history, history_directory, overwrite=True); (root / "history-audit.json").write_text(audit_model.audit_json(history_audit) + "\n", encoding="utf-8"); (root / "history-query.json").write_text(query_model.query_json(history_query) + "\n", encoding="utf-8"); (root / "history-query-audit.json").write_text(query_audit_model.audit_json(history_query_audit) + "\n", encoding="utf-8"); result["output_directory"] = str(root.resolve()); result["history_directory"] = str(history_directory.resolve()); (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record D481 runtime registries with D482")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D479 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args(); result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip); print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["history"]["latest_release_ready"] and result["history"]["audit_accepted"] and result["history_query"]["audit_accepted"] and not result["history_query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
