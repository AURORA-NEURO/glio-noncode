"""Evaluate D483 history diffs with strict and release D484 policies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model


def _policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(
        policy_id,
        diff_id,
        maximum_added=maximum_added,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_accepted=True,
        require_state_change=True,
        allow_unchanged=True,
    )


def build_demo(
    diff_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d484-strict-runtime",
        policy=_policy("glio-noncode-d484-strict-policy", source_diff.diff_id, maximum_added=0),
    )
    release = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d484-release-runtime",
        policy=_policy("glio-noncode-d484-release-policy", source_diff.diff_id, maximum_added=1),
    )
    strict_audit = audit_model.audit_runtime(strict, source_diff)
    release_audit = audit_model.audit_runtime(release, source_diff)
    release_query = query_model.query_runtime(
        release,
        query_id="glio-noncode-d484-release-query",
        resources=query_model.RESOURCES,
        limit=query_model.MAX_LIMIT,
    )
    release_query_audit = query_audit_model.audit_query(release_query, release)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "diff_id": source_diff.diff_id,
        "direction": source_diff.direction,
        "state_transition": source_diff.state_transition,
        "item_count": source_diff.item_count,
        "added_count": source_diff.added_count,
        "removed_count": source_diff.removed_count,
        "changed_count": source_diff.changed_count,
        "unchanged_count": source_diff.unchanged_count,
        "diff_accepted": source_diff.accepted,
        "strict": {
            "runtime_id": strict.runtime_id,
            "release_ready": strict.release_ready,
            "accepted": strict.accepted,
            "failed_checks": [item.check_id for item in strict.checks if not item.passed],
            "audit_check_count": strict_audit.check_count,
            "audit_passed_count": strict_audit.passed_count,
            "audit_accepted": strict_audit.accepted,
        },
        "release": {
            "runtime_id": release.runtime_id,
            "release_ready": release.release_ready,
            "accepted": release.accepted,
            "failed_checks": [item.check_id for item in release.checks if not item.passed],
            "audit_check_count": release_audit.check_count,
            "audit_passed_count": release_audit.passed_count,
            "audit_accepted": release_audit.accepted,
            "query_total_count": release_query.total_count,
            "query_returned_count": release_query.returned_count,
            "query_truncated": release_query.truncated,
            "query_audit_check_count": release_query_audit.check_count,
            "query_audit_passed_count": release_query_audit.passed_count,
            "query_audit_accepted": release_query_audit.accepted,
        },
        "diff_address": source_diff.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        strict_directory = runtime_model.persist_runtime(strict, root / "strict", overwrite=True)
        release_directory = runtime_model.persist_runtime(release, root / "release", overwrite=True)
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
    parser = argparse.ArgumentParser(description="Evaluate a D483 history diff with D484 policies")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D483 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    release = result["release"]
    return 0 if release["release_ready"] and release["audit_accepted"] and release["query_audit_accepted"] and not release["query_truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
