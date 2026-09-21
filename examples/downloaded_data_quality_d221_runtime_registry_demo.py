"""Aggregate D220 decisions with the D221 runtime registry contract.

The input directories are exact four-file D220 runtimes. Keeping a strict
blocked decision alongside the release-ready decision demonstrates that the
aggregate remains blocked until every admitted runtime is ready. Duplicate
identity rejection and audited bounded projections are persisted.

Example::

    python examples/downloaded_data_quality_d221_runtime_registry_demo.py \
        artifacts/d220-real/strict \
        artifacts/d220-real/release \
        --destination artifacts/d221-real \
        --source-zip C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d220_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d221_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d221_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d221_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d221_runtime_registry_query_audit as query_audit_model
from glio_noncode.errors import ValidationError


def build_demo(
    strict_directory: str | Path,
    release_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
    registry_id: str = "glio-noncode-d221-release-registry",
) -> dict[str, Any]:
    """Build, audit, query, and optionally persist one D221 registry."""

    strict = runtime_model.load_runtime(strict_directory)
    release = runtime_model.load_runtime(release_directory)
    registry = registry_model.run_registry((strict, release), registry_id=registry_id, destination=(Path(destination) / "registry") if destination is not None else None, overwrite=True)
    audit = audit_model.audit_registry(registry)
    query = query_model.query_registry(registry, resources=query_model.RESOURCES, state_filter="blocked", limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, registry)
    try:
        registry_model.build_registry((strict, strict), registry_id="glio-noncode-d221-duplicate-check")
    except ValidationError:
        duplicate_runtime_rejected = True
    else:
        duplicate_runtime_rejected = False
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "strict_runtime": strict.runtime_id,
        "release_runtime": release.runtime_id,
        "registry_id": registry.registry_id,
        "registry_address": registry.content_address,
        "state": registry.state,
        "release_ready": registry.release_ready,
        "accepted": registry.accepted,
        "entry_count": registry.entry_count,
        "ready_count": registry.ready_count,
        "blocked_count": registry.blocked_count,
        "duplicate_runtime_rejected": duplicate_runtime_rejected,
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "blocked_query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "blocked-query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "blocked-query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["registry_directory"] = str((root / "registry").resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate D220 runtimes with D221")
    parser.add_argument("strict_directory", type=Path, help="blocked D220 runtime directory")
    parser.add_argument("release_directory", type=Path, help="ready D220 runtime directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    parser.add_argument("--registry-id", default="glio-noncode-d221-release-registry")
    args = parser.parse_args()
    result = build_demo(args.strict_directory, args.release_directory, args.destination, source_zip=args.source_zip, registry_id=args.registry_id)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["audit"]["accepted"] and result["blocked_query"]["audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())



