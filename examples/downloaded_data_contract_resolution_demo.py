"""Demonstrate value-free remediation resolution over a downloaded ZIP.

The demo reads the archive as data only, compares two structural contracts,
plans remediation, creates a default pending resolution ledger, and persists
an independently audited exact seven-file runtime. No source record values or
operator identity metadata enter the output.

Example:

    python examples/downloaded_data_contract_resolution_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-resolution-demo
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
from glio_noncode import downloaded_data_profile_contract_compatibility as compatibility_model
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation as remediation_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_audit as resolution_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_runtime as runtime_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_runtime_audit as runtime_audit_model,
)
from glio_noncode import downloaded_data_profile_contract_diff as diff_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-resolution-demo-catalog")
    left_names = _selected_member_names(catalog)
    if len(left_names) < 3:
        raise ValueError("the downloaded archive needs at least three structured members for a comparison")
    right_names = left_names[:-2]
    left_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-demo-left-ingestion", member_names=left_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    right_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-demo-right-ingestion", member_names=right_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    left_contract = contract_model.build_contract(profile_model.build_profile(left_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-demo-left-profile"))
    right_contract = contract_model.build_contract(profile_model.build_profile(right_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-demo-right-profile"))
    diff = diff_model.build_diff(left_contract, right_contract, diff_id="glio-noncode-downloaded-contract-resolution-demo-diff")
    gate = compatibility_model.evaluate(diff, gate_id="glio-noncode-downloaded-contract-resolution-demo-gate")
    plan = remediation_model.build_plan(gate, plan_id="glio-noncode-downloaded-contract-resolution-demo-plan")
    runtime = runtime_model.run_runtime(plan, runtime_id="glio-noncode-downloaded-contract-resolution-demo-runtime", resolution_id="glio-noncode-downloaded-contract-resolution-demo-resolution", resources=("summary", "entries"), limit=25)
    resolution_audit = resolution_audit_model.audit_resolution(runtime.resolution)
    runtime_audit = runtime_audit_model.audit_runtime(runtime)
    status_counts = Counter(item.status for item in runtime.resolution.entries)
    action_counts = Counter(item.action for item in plan.actions)
    summary = {
        "source_name": Path(source).name,
        "catalog_member_count": catalog.member_count,
        "left_selected_member_count": len(left_names),
        "right_selected_member_count": len(right_names),
        "excluded_member_count": len(left_names) - len(right_names),
        "left_record_count": left_contract.record_count,
        "right_record_count": right_contract.record_count,
        "diff_item_count": len(diff.items),
        "finding_count": gate.finding_count,
        "action_count": plan.action_count,
        "action_counts": dict(sorted(action_counts.items())),
        "resolution_count": runtime.resolution_count,
        "required_open_count": runtime.required_open_count,
        "status_counts": dict(sorted(status_counts.items())),
        "query_returned_count": runtime.query.returned_count,
        "query_truncated": runtime.query.truncated,
        "gate_state": gate.state,
        "gate_decision": gate.decision,
        "plan_state": plan.state,
        "plan_decision": plan.decision,
        "resolution_state": runtime.resolution.state,
        "resolution_decision": runtime.resolution.decision,
        "resolution_accepted": runtime.resolution.accepted,
        "resolution_audit_accepted": resolution_audit.accepted,
        "query_audit_accepted": runtime.query_audit.accepted,
        "runtime_audit_accepted": runtime_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "release_ready": runtime.release_ready,
        "plan_address": runtime.plan_address,
        "resolution_address": runtime.resolution_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": runtime_audit.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "resolution-runtime"
        runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "resolution-audit.json").write_text(resolution_audit_model.audit_json(resolution_audit), encoding="utf-8")
        (root / "runtime-audit.json").write_text(runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(runtime_audit_model.render_audit_markdown(runtime_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["resolution_runtime_directory"] = str(runtime_root.resolve())
        summary["resolution_runtime_files"] = list(runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Record value-free remediation resolutions over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
