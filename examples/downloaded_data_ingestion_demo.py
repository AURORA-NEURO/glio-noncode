"""Run the downloaded-data ingestion and replay boundary on a real ZIP.

The ZIP is treated as input data only. The demo selects structured data
members explicitly and keeps schema declarations and the OpenAPI document
outside the record-ingestion set.

Example:

    python examples/downloaded_data_ingestion_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-ingestion-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion_runtime as runtime_model
from glio_noncode import downloaded_data_ingestion_runtime_audit as runtime_audit_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    """Choose data-bearing members without treating schemas or API prose as rows."""

    return tuple(
        item.member_name
        for item in catalog.members
        if "SCHEMAS" not in item.member_name.upper()
        and "OPENAPI_SPEC.YAML" not in item.member_name.upper()
    )


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    """Run a bounded, replayable ingestion against ``source``."""

    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-ingestion-demo-catalog")
    member_names = _selected_member_names(catalog)
    runtime = runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-downloaded-ingestion-demo-runtime",
        member_names=member_names,
        resources=("summary", "records", "lineage"),
        record_limit=runtime_model.ingestion_model.MAX_RECORDS,
        limit=40,
    )
    runtime_audit = runtime_audit_model.audit_runtime(runtime)
    summary = {
        "source_name": runtime.source_name,
        "source_address": runtime.source_address,
        "catalog_member_count": catalog.member_count,
        "selected_member_count": runtime.selected_member_count,
        "selected_member_exclusion": "SCHEMAS and OPENAPI_SPEC.yaml",
        "record_count": runtime.record_count,
        "available_record_count": runtime.available_record_count,
        "query_returned_count": runtime.query.returned_count,
        "state": runtime.state,
        "complete": runtime.complete,
        "accepted": runtime.accepted,
        "release_ready": runtime.release_ready,
        "runtime_address": runtime.content_address,
        "batch_address": runtime.batch_address,
        "query_address": runtime.query_address,
        "runtime_audit_address": runtime_audit.content_address,
        "runtime_audit_passed": runtime_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "sample_records": [
            {
                "record_id": record.record_id,
                "data_kind": record.data_kind,
                "shape": record.shape,
                "member_name": record.lineage.member_name,
                "source_row": record.lineage.source_row,
                "record_address": record.content_address,
            }
            for record in runtime.batch.records[:5]
        ],
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "runtime"
        runtime_model.persist_runtime(runtime, runtime_root)
        (root / "runtime-audit.json").write_text(runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(runtime_audit_model.render_audit_markdown(runtime_audit), encoding="utf-8")
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["runtime_directory"] = str(runtime_root.resolve())
        summary["runtime_files"] = list(runtime_model.FILES)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest real downloaded ZIP data into a replayable runtime")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["runtime_audit_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
