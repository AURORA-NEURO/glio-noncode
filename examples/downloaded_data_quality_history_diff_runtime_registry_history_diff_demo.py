"""Compare two D190 runtime-registry histories with the D191 diff contract.

Each input is an exact four-file D190 history directory. The diff records
ordinal-level additions, removals, field changes, and unchanged snapshots
while preserving both history addresses for review and replay.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_demo.py \
        artifacts/d190-blocked/history \
        artifacts/d190-ready/history \
        --destination artifacts/d191-diff
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_query_audit as query_audit_model


def build_demo(
    left_directory: str | Path,
    right_directory: str | Path,
    destination: str | Path | None = None,
    *,
    diff_id: str = "glio-noncode-history-diff-runtime-registry-history-diff-demo",
    change_filter: str = "",
    key_filter: str = "",
    text_filter: str = "",
    offset: int = 0,
    limit: int = query_model.MAX_LIMIT,
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D191 history diff."""

    left = history_model.load_history(left_directory)
    right = history_model.load_history(right_directory)
    value = diff_model.build_diff(left, right, diff_id=diff_id)
    audit = audit_model.audit_diff(value)
    query = query_model.query_diff(
        value,
        resources=query_model.RESOURCES,
        change_filter=change_filter,
        key_filter=key_filter,
        text_filter=text_filter,
        offset=offset,
        limit=limit,
    )
    query_audit = query_audit_model.audit_query(query, value)
    summary: dict[str, Any] = {
        "diff_id": value.diff_id,
        "registry_id": value.registry_id,
        "left_history_id": value.left_history_id,
        "right_history_id": value.right_history_id,
        "diff_address": value.content_address,
        "direction": value.direction,
        "state_transition": value.state_transition,
        "item_count": value.item_count,
        "added_count": value.added_count,
        "removed_count": value.removed_count,
        "changed_count": value.changed_count,
        "unchanged_count": value.unchanged_count,
        "accepted": value.accepted,
        "diff_audit_checks": audit.check_count,
        "diff_audit_passed": audit.passed_count,
        "diff_audit_accepted": audit.accepted,
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
        diff_model.persist_diff(value, root / "diff", overwrite=True)
        (root / "diff.json").write_text(diff_model.diff_json(value) + "\n", encoding="utf-8")
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["diff_directory"] = str((root / "diff").resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare D190 runtime-registry histories with D191")
    parser.add_argument("left_directory", type=Path, help="baseline D190 history directory")
    parser.add_argument("right_directory", type=Path, help="candidate D190 history directory")
    parser.add_argument("--diff-id", default="glio-noncode-history-diff-runtime-registry-history-diff-demo")
    parser.add_argument("--change", dest="change_filter", default="")
    parser.add_argument("--key", dest="key_filter", default="")
    parser.add_argument("--text", dest="text_filter", default="")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=query_model.MAX_LIMIT)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    summary = build_demo(
        args.left_directory,
        args.right_directory,
        args.destination,
        diff_id=args.diff_id,
        change_filter=args.change_filter,
        key_filter=args.key_filter,
        text_filter=args.text_filter,
        offset=args.offset,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["diff_audit_accepted"] and summary["query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
