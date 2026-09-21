"""Evaluate a registry-history diff with a release policy.

The input is the exact four-file D187 diff directory.  This keeps the D188
example value-free: the diff may have been produced from the downloaded ZIP,
but this layer only carries addresses, counts, transitions, and policy
evidence.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_demo.py \
        artifacts/runtime-history-d187-diff \
        artifacts/runtime-history-d188
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model


def build_demo(
    diff_directory: str | Path,
    destination: str | Path | None = None,
    *,
    runtime_id: str = "glio-noncode-history-diff-runtime-demo",
    minimum_items: int = 1,
    maximum_added: int = diff_model.MAX_ITEMS,
    maximum_removed: int = 0,
    maximum_changed: int = 0,
    allowed_directions: tuple[str, ...] = ("improved", "changed", "unchanged"),
    require_accepted: bool = True,
    require_state_change: bool = False,
    allow_unchanged: bool = True,
    limit: int = query_model.MAX_LIMIT,
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D188 runtime."""

    diff = diff_model.load_diff(diff_directory)
    policy = runtime_model.build_policy(
        f"{runtime_id}-policy",
        diff.diff_id,
        minimum_items=minimum_items,
        maximum_added=maximum_added,
        maximum_removed=maximum_removed,
        maximum_changed=maximum_changed,
        allowed_directions=allowed_directions,
        require_accepted=require_accepted,
        require_state_change=require_state_change,
        allow_unchanged=allow_unchanged,
    )
    runtime = runtime_model.build_runtime(diff, runtime_id=runtime_id, policy=policy)
    audit = audit_model.audit_runtime(runtime, diff)
    query = query_model.query_runtime(runtime, resources=query_model.RESOURCES, limit=limit)
    query_audit = query_audit_model.audit_query(query, runtime)
    summary: dict[str, Any] = {
        "diff_id": diff.diff_id,
        "diff_address": diff.content_address,
        "policy_address": policy.content_address,
        "runtime_id": runtime.runtime_id,
        "runtime_address": runtime.content_address,
        "state": runtime.state,
        "release_ready": runtime.release_ready,
        "direction": runtime.direction,
        "state_transition": runtime.state_transition,
        "item_count": runtime.item_count,
        "added_count": runtime.added_count,
        "removed_count": runtime.removed_count,
        "changed_count": runtime.changed_count,
        "runtime_audit_checks": audit.check_count,
        "runtime_audit_passed": audit.passed_count,
        "runtime_audit_accepted": audit.accepted,
        "query_total_count": query.total_count,
        "query_returned_count": query.returned_count,
        "query_truncated": query.truncated,
        "query_audit_checks": query_audit.check_count,
        "query_audit_passed": query_audit.passed_count,
        "query_audit_accepted": query_audit.accepted,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_model.persist_runtime(runtime, root / "runtime", overwrite=True)
        (root / "policy.json").write_text(runtime_model.policy_json(policy) + "\n", encoding="utf-8")
        (root / "runtime.json").write_text(runtime_model.runtime_json(runtime) + "\n", encoding="utf-8")
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["runtime_directory"] = str((root / "runtime").resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a D187 registry-history diff with a D188 release policy")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D187 diff directory")
    parser.add_argument("destination", type=Path, nargs="?", help="optional output directory")
    parser.add_argument("--runtime-id", default="glio-noncode-history-diff-runtime-demo")
    parser.add_argument("--minimum-items", type=int, default=1)
    parser.add_argument("--maximum-added", type=int, default=diff_model.MAX_ITEMS)
    parser.add_argument("--maximum-removed", type=int, default=0)
    parser.add_argument("--maximum-changed", type=int, default=0)
    parser.add_argument("--allow-direction", action="append", choices=diff_model.DIRECTIONS, dest="allowed_directions")
    parser.add_argument("--no-require-accepted", action="store_false", dest="require_accepted")
    parser.add_argument("--require-state-change", action="store_true")
    parser.add_argument("--disallow-unchanged", action="store_false", dest="allow_unchanged")
    parser.add_argument("--limit", type=int, default=query_model.MAX_LIMIT)
    args = parser.parse_args()
    directions = tuple(args.allowed_directions or ("improved", "changed", "unchanged"))
    summary = build_demo(
        args.diff_directory,
        args.destination,
        runtime_id=args.runtime_id,
        minimum_items=args.minimum_items,
        maximum_added=args.maximum_added,
        maximum_removed=args.maximum_removed,
        maximum_changed=args.maximum_changed,
        allowed_directions=directions,
        require_accepted=args.require_accepted,
        require_state_change=args.require_state_change,
        allow_unchanged=args.allow_unchanged,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["runtime_audit_accepted"] and summary["query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
