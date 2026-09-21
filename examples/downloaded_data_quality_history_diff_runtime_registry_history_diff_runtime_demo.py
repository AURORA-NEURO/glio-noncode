"""Evaluate a D191 history diff as a release decision with D192.

The input is an exact four-file D191 diff directory.  The example evaluates
the same real comparison twice: a strict policy blocks any changed snapshot,
while a release policy permits one improved change and requires a genuine
state transition.  Both decisions are persisted, independently audited, and
queried so the output can be inspected without importing private objects.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_demo.py \
        artifacts/d191-real-demo/diff \
        --destination artifacts/d192-real-demo \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model


def _summary(value: runtime_model.DiffRuntime, audit: Any) -> dict[str, Any]:
    return {
        "runtime_id": value.runtime_id,
        "state": value.state,
        "release_ready": value.release_ready,
        "passed_count": value.passed_count,
        "check_count": value.check_count,
        "failed_checks": [item.check_id for item in value.checks if not item.passed],
        "audit_passed_count": audit.passed_count,
        "audit_check_count": audit.check_count,
        "audit_accepted": audit.accepted,
        "runtime_address": value.content_address,
    }


def build_demo(
    diff_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
    strict_max_changed: int = 0,
    release_max_changed: int = 1,
    query_text: str = "",
) -> dict[str, Any]:
    """Evaluate, persist, audit, and query one D191 comparison."""

    diff = diff_model.load_diff(diff_directory)
    strict_policy = runtime_model.build_policy(
        "glio-noncode-d192-strict-policy",
        diff.diff_id,
        maximum_added=0,
        maximum_removed=0,
        maximum_changed=strict_max_changed,
        allowed_directions=("improved", "changed", "unchanged"),
        require_accepted=True,
        require_state_change=False,
        allow_unchanged=True,
    )
    release_policy = runtime_model.build_policy(
        "glio-noncode-d192-release-policy",
        diff.diff_id,
        maximum_added=0,
        maximum_removed=0,
        maximum_changed=release_max_changed,
        allowed_directions=("improved",),
        require_accepted=True,
        require_state_change=True,
        allow_unchanged=True,
    )
    strict = runtime_model.run_runtime(
        diff,
        runtime_id="glio-noncode-d192-strict-runtime",
        policy=strict_policy,
    )
    release = runtime_model.run_runtime(
        diff,
        runtime_id="glio-noncode-d192-release-runtime",
        policy=release_policy,
    )
    strict_audit = audit_model.audit_runtime(strict, diff)
    release_audit = audit_model.audit_runtime(release, diff)
    release_query = query_model.query_runtime(
        release,
        resources=query_model.RESOURCES,
        text_filter=query_text,
        offset=0,
        limit=query_model.MAX_LIMIT,
    )
    release_query_audit = query_audit_model.audit_query(release_query, release)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "diff_directory": str(Path(diff_directory).resolve()),
        "comparison": {
            "diff_id": diff.diff_id,
            "diff_address": diff.content_address,
            "direction": diff.direction,
            "state_transition": diff.state_transition,
            "item_count": diff.item_count,
            "added_count": diff.added_count,
            "removed_count": diff.removed_count,
            "changed_count": diff.changed_count,
            "unchanged_count": diff.unchanged_count,
            "accepted": diff.accepted,
        },
        "strict_policy": _summary(strict, strict_audit),
        "release_policy": _summary(release, release_audit),
        "release_query": {
            "text_filter": query_text,
            "total_count": release_query.total_count,
            "returned_count": release_query.returned_count,
            "truncated": release_query.truncated,
            "audit_passed_count": release_query_audit.passed_count,
            "audit_check_count": release_query_audit.check_count,
            "audit_accepted": release_query_audit.accepted,
        },
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        strict_directory = root / "strict"
        release_directory = root / "release"
        runtime_model.persist_runtime(strict, strict_directory, overwrite=True)
        runtime_model.persist_runtime(release, release_directory, overwrite=True)
        (root / "strict-audit.json").write_text(audit_model.audit_json(strict_audit) + "\n", encoding="utf-8")
        (root / "release-audit.json").write_text(audit_model.audit_json(release_audit) + "\n", encoding="utf-8")
        (root / "release-query.json").write_text(query_model.query_json(release_query) + "\n", encoding="utf-8")
        (root / "release-query-audit.json").write_text(query_audit_model.audit_json(release_query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["strict_directory"] = str(strict_directory.resolve())
        result["release_directory"] = str(release_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a D191 history diff with D192")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D191 diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    parser.add_argument("--strict-max-changed", type=int, default=0)
    parser.add_argument("--release-max-changed", type=int, default=1)
    parser.add_argument("--text", dest="query_text", default="")
    args = parser.parse_args()
    result = build_demo(
        args.diff_directory,
        args.destination,
        source_zip=args.source_zip,
        strict_max_changed=args.strict_max_changed,
        release_max_changed=args.release_max_changed,
        query_text=args.query_text,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["release_policy"]["release_ready"] and result["release_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
