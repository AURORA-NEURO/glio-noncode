"""Admit D188 policy runtimes into a deterministic D189 registry.

The inputs are exact four-file D188 runtime directories. The registry carries
only runtime identities, addresses, counts, dispositions, and audit evidence;
it does not copy source paths, records, or payload values.

Example::

    python examples/downloaded_data_quality_history_diff_runtime_registry_demo.py \
        artifacts/d188-ready/runtime \
        artifacts/d188-blocked/runtime \
        --destination artifacts/d189-registry
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_runtime_history_release_evidence_history_runtime_registry_history_diff_runtime_registry_history_diff_runtime_registry_query_audit as query_audit_model


def build_demo(
    runtime_directories: tuple[str | Path, ...],
    destination: str | Path | None = None,
    *,
    registry_id: str = "glio-noncode-history-diff-runtime-registry-demo",
    limit: int = query_model.MAX_LIMIT,
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D189 registry."""

    runtimes = tuple(runtime_model.load_runtime(path) for path in runtime_directories)
    registry = registry_model.build_registry(runtimes, registry_id=registry_id)
    audit = audit_model.audit_registry(registry)
    query = query_model.query_registry(registry, resources=query_model.RESOURCES, limit=limit)
    query_audit = query_audit_model.audit_query(query, registry)
    summary: dict[str, Any] = {
        "registry_id": registry.registry_id,
        "registry_address": registry.content_address,
        "state": registry.state,
        "release_ready": registry.release_ready,
        "accepted": registry.accepted,
        "entry_count": registry.entry_count,
        "ready_count": registry.ready_count,
        "blocked_count": registry.blocked_count,
        "registry_audit_checks": audit.check_count,
        "registry_audit_passed": audit.passed_count,
        "registry_audit_accepted": audit.accepted,
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
        registry_model.persist_registry(registry, root / "registry", overwrite=True)
        (root / "registry.json").write_text(registry_model.registry_json(registry) + "\n", encoding="utf-8")
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["registry_directory"] = str((root / "registry").resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Admit D188 history-diff runtimes into a D189 registry")
    parser.add_argument("runtime_directories", type=Path, nargs="+", help="exact four-file D188 runtime directories")
    parser.add_argument("--registry-id", default="glio-noncode-history-diff-runtime-registry-demo")
    parser.add_argument("--limit", type=int, default=query_model.MAX_LIMIT)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    summary = build_demo(tuple(args.runtime_directories), args.destination, registry_id=args.registry_id, limit=args.limit)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["registry_audit_accepted"] and summary["query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
