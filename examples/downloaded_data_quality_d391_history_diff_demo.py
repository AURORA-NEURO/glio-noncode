"""Compare D390 registry histories with the D391 history diff contract.

The baseline is the blocked-only D390 history and the candidate is the
blocked-to-ready D390 history. D391 preserves both history addresses,
classifies each ordinal, folds release movement, and emits independent audits.

Example::

    python examples/downloaded_data_quality_d391_history_diff_demo.py \
        artifacts/d390-baseline/history \
        artifacts/d390-real/history \
        --destination artifacts/d391-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d390_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d391_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d391_history_diff_audit as audit_model
from glio_noncode import downloaded_data_quality_d391_history_diff_query as query_model
from glio_noncode import downloaded_data_quality_d391_history_diff_query_audit as query_audit_model


def build_demo(baseline_directory: str | Path, candidate_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None, diff_id: str = "glio-noncode-d391-history-diff", change_filter: str = "added") -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D391 history diff."""

    baseline = history_model.load_history(baseline_directory)
    candidate = history_model.load_history(candidate_directory)
    value = diff_model.build_diff(baseline, candidate, diff_id=diff_id)
    audit = audit_model.audit_diff(value)
    query = query_model.query_diff(value, resources=query_model.RESOURCES, change_filter=change_filter, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, value)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "diff_id": value.diff_id,
        "diff_address": value.content_address,
        "left_history_id": value.left_history_id,
        "right_history_id": value.right_history_id,
        "direction": value.direction,
        "state_transition": value.state_transition,
        "item_count": value.item_count,
        "added_count": value.added_count,
        "removed_count": value.removed_count,
        "changed_count": value.changed_count,
        "unchanged_count": value.unchanged_count,
        "accepted": value.accepted,
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "query": {"change_filter": change_filter, "total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        diff_directory = root / "diff"
        diff_model.persist_diff(value, diff_directory, overwrite=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["diff_directory"] = str(diff_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare D390 registry histories with D391")
    parser.add_argument("baseline_directory", type=Path, help="baseline D390 history directory")
    parser.add_argument("candidate_directory", type=Path, help="candidate D390 history directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    parser.add_argument("--diff-id", default="glio-noncode-d391-history-diff")
    parser.add_argument("--change", dest="change_filter", default="added")
    args = parser.parse_args()
    result = build_demo(args.baseline_directory, args.candidate_directory, args.destination, source_zip=args.source_zip, diff_id=args.diff_id, change_filter=args.change_filter)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["audit"]["accepted"] and result["query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
