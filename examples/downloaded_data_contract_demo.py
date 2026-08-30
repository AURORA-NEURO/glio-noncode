"""Demonstrate value-free schema-contract inference on a downloaded ZIP.

The source archive is treated as input data only.  The emitted contract runtime
contains counts, types, field coverage, drift states, content addresses, and
audits; it does not export source values.

Example:

    python examples/downloaded_data_contract_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-demo
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_ingestion_runtime as ingestion_runtime_model
from glio_noncode import downloaded_data_profile_contract_runtime as contract_runtime_model
from glio_noncode import downloaded_data_profile_contract_runtime_audit as runtime_audit_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    """Select structured data members while treating schema files as data."""

    return tuple(
        item.member_name
        for item in catalog.members
        if "SCHEMAS" not in item.member_name.upper()
        and "OPENAPI_SPEC.YAML" not in item.member_name.upper()
    )


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    """Run ingestion, contract inference, query, audit, and exact persistence."""

    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-demo-catalog")
    member_names = _selected_member_names(catalog)
    ingestion_runtime = ingestion_runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-downloaded-contract-demo-ingestion-runtime",
        member_names=member_names,
        resources=("summary",),
        record_limit=ingestion_model.MAX_RECORDS,
        limit=1,
    )
    contract_runtime = contract_runtime_model.run_runtime(
        ingestion_runtime.batch,
        runtime_id="glio-noncode-downloaded-contract-demo-runtime",
        profile_id="glio-noncode-downloaded-contract-demo-profile",
        resources=("summary", "types", "members", "fields", "issues"),
        limit=10_000,
    )
    closure_audit = runtime_audit_model.audit_runtime(contract_runtime)
    contract = contract_runtime.contract
    state_counts = Counter(item.state for item in contract.fields)
    dominant_type_counts = Counter(item.dominant_value_type for item in contract.fields if item.dominant_value_type)
    member_required = {
        member.member_name: {
            "field_count": member.field_count,
            "required_field_count": member.required_field_count,
            "optional_field_count": member.optional_field_count,
            "mixed_type_field_count": member.mixed_type_field_count,
        }
        for member in contract.members
    }
    summary = {
        "source_name": ingestion_runtime.source_name,
        "source_address": ingestion_runtime.source_address,
        "catalog_member_count": catalog.member_count,
        "selected_member_count": len(member_names),
        "selected_member_exclusion": "SCHEMAS and OPENAPI_SPEC.yaml",
        "available_record_count": ingestion_runtime.available_record_count,
        "record_count": contract.record_count,
        "member_count": contract.member_count,
        "field_count": contract.field_count,
        "required_field_count": contract.required_field_count,
        "optional_field_count": contract.optional_field_count,
        "sparse_field_count": contract.sparse_field_count,
        "mixed_type_field_count": contract.mixed_type_field_count,
        "field_state_counts": dict(sorted(state_counts.items())),
        "dominant_field_type_counts": dict(sorted(dominant_type_counts.items())),
        "member_schema_summary": member_required,
        "contract_query_returned_count": contract_runtime.query.returned_count,
        "contract_query_truncated": contract_runtime.query.truncated,
        "contract_audit_accepted": contract_runtime.audit.accepted,
        "contract_query_audit_accepted": contract_runtime.query_audit.accepted,
        "runtime_audit_accepted": closure_audit.accepted,
        "runtime_audit_checks": closure_audit.check_count,
        "runtime_audit_address": closure_audit.content_address,
        "accepted": contract_runtime.accepted,
        "release_ready": contract_runtime.release_ready,
        "contract_runtime_address": contract_runtime.content_address,
        "contract_address": contract_runtime.contract_address,
        "contract_audit_address": contract_runtime.audit_address,
        "contract_query_address": contract_runtime.query_address,
        "contract_query_audit_address": contract_runtime.query_audit_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        contract_root = root / "contract-runtime"
        contract_runtime_model.persist_runtime(contract_runtime, contract_root, overwrite=True)
        (root / "runtime-audit.json").write_text(runtime_audit_model.audit_json(closure_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(runtime_audit_model.render_audit_markdown(closure_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["contract_runtime_directory"] = str(contract_root.resolve())
        summary["contract_runtime_files"] = list(contract_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Infer a value-free schema contract from a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
