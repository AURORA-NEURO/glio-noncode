"""Record D265 registry decisions in an append-only D266 history.

The mixed D265 registry is the blocked baseline. A ready-only D265 registry is
built from the release D264 runtime and appended with an optimistic head check,
producing a durable ``blocked->ready`` transition. History and query audits
are persisted for inspection.

Example::

    python examples/downloaded_data_quality_d266_runtime_registry_history_demo.py \
        artifacts/d265-real/registry \
        artifacts/d264-real/release \
        --destination artifacts/d266-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d264_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d265_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d266_runtime_registry_history as history_model
from glio_noncode import downloaded_data_quality_d266_runtime_registry_history_audit as audit_model
from glio_noncode import downloaded_data_quality_d266_runtime_registry_history_query as query_model
from glio_noncode import downloaded_data_quality_d266_runtime_registry_history_query_audit as query_audit_model


def build_demo(
    blocked_registry_directory: str | Path,
    release_runtime_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
    history_id: str = "glio-noncode-d266-release-history",
) -> dict[str, Any]:
    """Build, append, audit, query, and optionally persist one D266 history."""

    blocked_registry = registry_model.load_registry(blocked_registry_directory)
    release_runtime = runtime_model.load_runtime(release_runtime_directory)
    ready_registry = registry_model.build_registry((release_runtime,), registry_id=blocked_registry.registry_id)
    history = history_model.build_history(blocked_registry, history_id=history_id, snapshot_id="blocked")
    history = history_model.append_history(history, ready_registry, snapshot_id="ready", expected_head=history.entries[-1].content_address)
    audit = audit_model.audit_history(history)
    query = query_model.query_history(history, resources=query_model.RESOURCES, readiness_filter=True, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, history)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "history_id": history.history_id,
        "history_address": history.content_address,
        "registry_id": history.registry_id,
        "entry_count": history.entry_count,
        "latest_state": history.latest_state,
        "latest_release_ready": history.latest_release_ready,
        "transition": history.entries[-1].transition,
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "ready_query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        history_directory = root / "history"
        history_model.persist_history(history, history_directory, overwrite=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "ready-query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "ready-query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["history_directory"] = str(history_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Record D265 registry decisions with D266")
    parser.add_argument("blocked_registry_directory", type=Path, help="mixed D265 registry directory")
    parser.add_argument("release_runtime_directory", type=Path, help="ready D264 runtime directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    parser.add_argument("--history-id", default="glio-noncode-d266-release-history")
    args = parser.parse_args()
    result = build_demo(args.blocked_registry_directory, args.release_runtime_directory, args.destination, source_zip=args.source_zip, history_id=args.history_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["audit"]["accepted"] and result["ready_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())







