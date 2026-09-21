"""Evaluate a D195 history diff as a D196 release decision.

The D195 input is a four-file comparison derived from the downloaded source
archive.  This example evaluates it under two explicit policies: a zero-added
budget blocks the decision, while a one-added improved transition is ready.
Both outcomes are persisted with independent runtime audits and full bounded
query projections.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_demo.py \
        artifacts/d195-real/diff \
        --destination artifacts/d196-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model


def _decision(value: runtime_model.DiffRuntime, audit: Any) -> dict[str, Any]:
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
    strict_max_added: int = 0,
    release_max_added: int = 1,
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist two D196 decisions."""

    diff = diff_model.load_diff(diff_directory)
    strict_policy = runtime_model.build_policy(
        "glio-noncode-d196-strict-policy",
        diff.diff_id,
        maximum_added=strict_max_added,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved", "changed", "unchanged"),
        require_accepted=True,
        require_state_change=False,
        allow_unchanged=True,
    )
    release_policy = runtime_model.build_policy(
        "glio-noncode-d196-release-policy",
        diff.diff_id,
        maximum_added=release_max_added,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_accepted=True,
        require_state_change=True,
        allow_unchanged=True,
    )
    strict = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d196-strict-runtime", policy=strict_policy)
    release = runtime_model.run_runtime(diff, runtime_id="glio-noncode-d196-release-runtime", policy=release_policy)
    strict_audit = audit_model.audit_runtime(strict, diff)
    release_audit = audit_model.audit_runtime(release, diff)
    release_query = query_model.query_runtime(release, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    release_query_audit = query_audit_model.audit_query(release_query, release)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "diff_id": diff.diff_id,
        "direction": diff.direction,
        "state_transition": diff.state_transition,
        "item_count": diff.item_count,
        "added_count": diff.added_count,
        "removed_count": diff.removed_count,
        "changed_count": diff.changed_count,
        "accepted": diff.accepted,
        "strict_policy": _decision(strict, strict_audit),
        "release_policy": _decision(release, release_audit),
        "release_query": {
            "total_count": release_query.total_count,
            "returned_count": release_query.returned_count,
            "truncated": release_query.truncated,
            "audit_check_count": release_query_audit.check_count,
            "audit_passed_count": release_query_audit.passed_count,
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
    parser = argparse.ArgumentParser(description="Evaluate a D195 history diff with D196")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D195 diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    parser.add_argument("--strict-max-added", type=int, default=0)
    parser.add_argument("--release-max-added", type=int, default=1)
    args = parser.parse_args()
    result = build_demo(
        args.diff_directory,
        args.destination,
        source_zip=args.source_zip,
        strict_max_added=args.strict_max_added,
        release_max_added=args.release_max_added,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["release_policy"]["release_ready"] and result["release_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
