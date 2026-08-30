"""Run value-free structural profiling on the supplied downloaded ZIP.

The ZIP is used only as input data. The demo first creates the existing
replayable ingestion runtime, then derives a public profile runtime containing
counts, shapes, types, field presence, sizes, and bounded cardinality only.

Example:

    python examples/downloaded_data_profile_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-profile-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_ingestion_runtime as ingestion_runtime_model
from glio_noncode import downloaded_data_profile_runtime as profile_runtime_model
from glio_noncode import downloaded_data_profile_runtime_audit as profile_runtime_audit_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    """Select data-bearing members while leaving schema declarations as data outside the profile."""

    return tuple(
        item.member_name
        for item in catalog.members
        if "SCHEMAS" not in item.member_name.upper()
        and "OPENAPI_SPEC.YAML" not in item.member_name.upper()
    )


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    """Build ingestion and profile runtimes from a downloaded ZIP."""

    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-profile-demo-catalog")
    member_names = _selected_member_names(catalog)
    ingestion_runtime = ingestion_runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-downloaded-profile-demo-ingestion-runtime",
        member_names=member_names,
        resources=("summary",),
        record_limit=ingestion_model.MAX_RECORDS,
        limit=1,
    )
    profile_runtime = profile_runtime_model.run_runtime(
        ingestion_runtime.batch,
        runtime_id="glio-noncode-downloaded-profile-demo-runtime",
        resources=("summary", "members", "fields", "types"),
        limit=10_000,
    )
    profile_runtime_audit = profile_runtime_audit_model.audit_runtime(profile_runtime)
    type_counts = {item.value_type: item.count for item in profile_runtime.profile.type_counts}
    field_type_counts: dict[str, int] = {}
    for field in profile_runtime.profile.fields:
        for item in field.type_counts:
            field_type_counts[item.value_type] = field_type_counts.get(item.value_type, 0) + item.count
    shape_counts: dict[str, int] = {}
    for member in profile_runtime.profile.members:
        for item in member.shape_counts:
            shape_counts[item.shape] = shape_counts.get(item.shape, 0) + item.count
    summary = {
        "source_name": ingestion_runtime.source_name,
        "source_address": ingestion_runtime.source_address,
        "catalog_member_count": catalog.member_count,
        "selected_member_count": len(member_names),
        "selected_member_exclusion": "SCHEMAS and OPENAPI_SPEC.yaml",
        "record_count": profile_runtime.record_count,
        "available_record_count": ingestion_runtime.available_record_count,
        "profile_member_count": profile_runtime.member_count,
        "profile_field_count": profile_runtime.field_count,
        "total_value_bytes": profile_runtime.profile.total_value_bytes,
        "value_type_counts": type_counts,
        "field_value_type_counts": field_type_counts,
        "shape_counts": shape_counts,
        "profile_query_returned_count": profile_runtime.query.returned_count,
        "profile_query_truncated": profile_runtime.query.truncated,
        "ingestion_release_ready": ingestion_runtime.release_ready,
        "profile_audit_accepted": profile_runtime.audit.accepted,
        "profile_query_audit_accepted": profile_runtime.query_audit.accepted,
        "profile_runtime_audit_accepted": profile_runtime_audit.accepted,
        "profile_runtime_audit_checks": profile_runtime_audit.check_count,
        "profile_runtime_audit_address": profile_runtime_audit.content_address,
        "accepted": profile_runtime.accepted,
        "release_ready": profile_runtime.release_ready,
        "profile_runtime_address": profile_runtime.content_address,
        "profile_address": profile_runtime.profile_address,
        "profile_audit_address": profile_runtime.audit_address,
        "profile_query_address": profile_runtime.query_address,
        "profile_query_audit_address": profile_runtime.query_audit_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        ingestion_root = root / "ingestion-runtime"
        profile_root = root / "profile-runtime"
        ingestion_runtime_model.persist_runtime(ingestion_runtime, ingestion_root, overwrite=True)
        profile_runtime_model.persist_runtime(profile_runtime, profile_root, overwrite=True)
        (root / "profile-runtime-audit.json").write_text(profile_runtime_audit_model.audit_json(profile_runtime_audit), encoding="utf-8")
        (root / "profile-runtime-audit.md").write_text(profile_runtime_audit_model.render_audit_markdown(profile_runtime_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["ingestion_runtime_directory"] = str(ingestion_root.resolve())
        summary["profile_runtime_directory"] = str(profile_root.resolve())
        summary["profile_runtime_files"] = list(profile_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile a downloaded ZIP without exporting source values")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["profile_runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
