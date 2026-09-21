"""Record successive D189 runtime registries as a D190 history.

The two inputs are exact four-file D189 registry directories. The history
enforces one stable registry identity, optimistic expected-head appends, and
deterministic transitions without copying source data.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_registry_history_demo.py \
        artifacts/d189-blocked/registry \
        artifacts/d189-ready/registry \
        --destination artifacts/d190-history
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_query_audit as query_audit_model


def build_demo(
    baseline_directory: str | Path,
    candidate_directory: str | Path,
    destination: str | Path | None = None,
    *,
    history_id: str = "glio-noncode-history-diff-runtime-registry-history-demo",
    baseline_snapshot_id: str = "baseline",
    candidate_snapshot_id: str = "candidate",
    limit: int = query_model.MAX_LIMIT,
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D190 history."""

    baseline = registry_model.load_registry(baseline_directory)
    candidate = registry_model.load_registry(candidate_directory)
    history = history_model.build_history(baseline, history_id=history_id, snapshot_id=baseline_snapshot_id)
    history = history_model.append_history(history, candidate, snapshot_id=candidate_snapshot_id, expected_head=history.entries[-1].content_address)
    audit = audit_model.audit_history(history)
    query = query_model.query_history(history, resources=query_model.RESOURCES, limit=limit)
    query_audit = query_audit_model.audit_query(query, history)
    summary: dict[str, Any] = {
        "history_id": history.history_id,
        "registry_id": history.registry_id,
        "history_address": history.content_address,
        "entry_count": history.entry_count,
        "initial_count": history.initial_count,
        "improved_count": history.improved_count,
        "regressed_count": history.regressed_count,
        "unchanged_count": history.unchanged_count,
        "changed_count": history.changed_count,
        "latest_state": history.latest_state,
        "latest_release_ready": history.latest_release_ready,
        "history_audit_checks": audit.check_count,
        "history_audit_passed": audit.passed_count,
        "history_audit_accepted": audit.accepted,
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
        history_model.persist_history(history, root / "history", overwrite=True)
        (root / "history.json").write_text(history_model.history_json(history) + "\n", encoding="utf-8")
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["history_directory"] = str((root / "history").resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Record D189 runtime registries as a D190 history")
    parser.add_argument("baseline_directory", type=Path, help="baseline D189 registry directory")
    parser.add_argument("candidate_directory", type=Path, help="candidate D189 registry directory")
    parser.add_argument("--history-id", default="glio-noncode-history-diff-runtime-registry-history-demo")
    parser.add_argument("--baseline-snapshot-id", default="baseline")
    parser.add_argument("--candidate-snapshot-id", default="candidate")
    parser.add_argument("--limit", type=int, default=query_model.MAX_LIMIT)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    summary = build_demo(
        args.baseline_directory,
        args.candidate_directory,
        args.destination,
        history_id=args.history_id,
        baseline_snapshot_id=args.baseline_snapshot_id,
        candidate_snapshot_id=args.candidate_snapshot_id,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["history_audit_accepted"] and summary["query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
