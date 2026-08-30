"""Demonstrate value-free schema evolution over the supplied downloaded ZIP.

The ZIP is used as input data only. Two structural contracts are inferred from
different member selections, compared, audited, queried, and persisted. The
emitted files contain counts, field names, types, states, addresses, and audit
evidence; source record values are never written to the demo artifacts.

Example:

    python examples/downloaded_data_contract_diff_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-diff-demo
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_ingestion_runtime as ingestion_runtime_model
from glio_noncode import downloaded_data_profile as profile_model
from glio_noncode import downloaded_data_profile_contract as contract_model
from glio_noncode import downloaded_data_profile_contract_diff_runtime as diff_runtime_model
from glio_noncode import downloaded_data_profile_contract_diff_runtime_audit as runtime_audit_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-diff-demo-catalog")
    left_names = _selected_member_names(catalog)
    if len(left_names) < 3:
        raise ValueError("the downloaded archive needs at least three structured members for a comparison")
    right_names = left_names[:-2]
    left_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-diff-demo-left-ingestion", member_names=left_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    right_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-diff-demo-right-ingestion", member_names=right_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    left_contract = contract_model.build_contract(profile_model.build_profile(left_ingestion.batch, profile_id="glio-noncode-downloaded-contract-diff-demo-left-profile"))
    right_contract = contract_model.build_contract(profile_model.build_profile(right_ingestion.batch, profile_id="glio-noncode-downloaded-contract-diff-demo-right-profile"))
    runtime = diff_runtime_model.build_runtime(left_contract, right_contract, runtime_id="glio-noncode-downloaded-contract-diff-demo-runtime", resources=("summary", "fields", "members", "types"), limit=25)
    closure_audit = runtime_audit_model.audit_runtime(runtime)
    changed_attributes = Counter(attribute for item in runtime.diff.items for attribute in item.changed_attributes)
    change_counts = {resource: {change: sum(item.resource == resource and item.change == change for item in runtime.diff.items) for change in ("added", "removed", "changed", "unchanged")} for resource in ("fields", "members", "types")}
    summary = {
        "source_name": Path(source).name,
        "catalog_member_count": catalog.member_count,
        "left_selected_member_count": len(left_names),
        "right_selected_member_count": len(right_names),
        "excluded_member_count": len(left_names) - len(right_names),
        "left_record_count": left_contract.record_count,
        "right_record_count": right_contract.record_count,
        "left_field_count": left_contract.field_count,
        "right_field_count": right_contract.field_count,
        "left_member_count": left_contract.member_count,
        "right_member_count": right_contract.member_count,
        "diff_item_count": len(runtime.diff.items),
        "change_counts": change_counts,
        "changed_attribute_counts": dict(sorted(changed_attributes.items())),
        "query_returned_count": runtime.query.returned_count,
        "query_truncated": runtime.query.truncated,
        "diff_audit_accepted": runtime.audit.accepted,
        "query_audit_accepted": runtime.query_audit.accepted,
        "runtime_audit_accepted": closure_audit.accepted,
        "runtime_audit_checks": closure_audit.check_count,
        "release_ready": runtime.release_ready,
        "left_contract_address": left_contract.content_address,
        "right_contract_address": right_contract.content_address,
        "diff_address": runtime.diff_address,
        "query_address": runtime.query_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": closure_audit.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        diff_runtime_root = root / "diff-runtime"
        diff_runtime_model.persist_runtime(runtime, diff_runtime_root, overwrite=True)
        (root / "left-contract.json").write_text(contract_model.contract_json(left_contract), encoding="utf-8")
        (root / "right-contract.json").write_text(contract_model.contract_json(right_contract), encoding="utf-8")
        (root / "runtime-audit.json").write_text(runtime_audit_model.audit_json(closure_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(runtime_audit_model.render_audit_markdown(closure_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["diff_runtime_directory"] = str(diff_runtime_root.resolve())
        summary["diff_runtime_files"] = list(diff_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two value-free contracts inferred from a downloaded ZIP")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path, nargs="?")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
