"""Demonstrate a value-free resolution-history diff over a downloaded ZIP.

The archive is bounded input data only. The demo derives a structural
compatibility plan, creates a pending baseline and resolved candidate, then
compares their addressed history snapshots without retaining source values or
operator metadata.

Example:

    python examples/downloaded_data_contract_resolution_history_diff_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-resolution-history-diff-demo
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
    downloaded_data_profile_contract_compatibility_remediation_resolution as resolution_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history as history_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_audit as history_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as history_diff_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_audit as history_diff_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_runtime as history_diff_runtime_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_runtime_audit as history_diff_runtime_audit_model,
)
from glio_noncode import downloaded_data_profile_contract_diff as contract_diff_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-catalog")
    left_names = _selected_member_names(catalog)
    if len(left_names) < 3:
        raise ValueError("the downloaded archive needs at least three structured members for a comparison")
    right_names = left_names[:-2]
    left_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-left-ingestion", member_names=left_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    right_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-right-ingestion", member_names=right_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    left_contract = contract_model.build_contract(profile_model.build_profile(left_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-left-profile"))
    right_contract = contract_model.build_contract(profile_model.build_profile(right_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-right-profile"))
    contract_diff = compatibility_model.evaluate(contract_diff_model.build_diff(left_contract, right_contract, diff_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-contract-diff"), gate_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-gate")
    plan = remediation_model.build_plan(contract_diff, plan_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-plan")
    pending = resolution_model.build_resolution(plan, resolution_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-pending")
    statuses = {item.action_address: "resolved" for item in pending.entries if item.required}
    closed = resolution_model.build_resolution(plan, resolution_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-closed", statuses=statuses)
    baseline = history_model.build_history((pending,), history_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-baseline")
    candidate = history_model.build_history((pending, closed), history_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-candidate")
    history_diff = history_diff_model.build_diff(baseline, candidate, diff_id="glio-noncode-downloaded-contract-resolution-history-diff-demo")
    diff_audit = history_diff_audit_model.audit_diff(history_diff)
    runtime = history_diff_runtime_model.run_runtime(history_diff, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-demo-runtime", resources=("summary", "items"), limit=25)
    runtime_audit = history_diff_runtime_audit_model.audit_runtime(runtime)
    baseline_audit = history_audit_model.audit_history(baseline)
    action_counts = Counter(item.action for item in plan.actions)
    summary = {
        "source_name": Path(source).name,
        "catalog_member_count": catalog.member_count,
        "left_selected_member_count": len(left_names),
        "right_selected_member_count": len(right_names),
        "excluded_member_count": len(left_names) - len(right_names),
        "left_record_count": left_contract.record_count,
        "right_record_count": right_contract.record_count,
        "finding_count": contract_diff.finding_count,
        "action_count": plan.action_count,
        "action_counts": dict(sorted(action_counts.items())),
        "baseline_history_entry_count": baseline.entry_count,
        "candidate_history_entry_count": candidate.entry_count,
        "diff_added_count": history_diff.added_count,
        "diff_removed_count": history_diff.removed_count,
        "diff_changed_count": history_diff.changed_count,
        "diff_unchanged_count": history_diff.unchanged_count,
        "diff_improved_delta": history_diff.improved_delta,
        "diff_regressed_delta": history_diff.regressed_delta,
        "diff_direction": history_diff.direction,
        "diff_state_transition": history_diff.state_transition,
        "diff_audit_accepted": diff_audit.accepted,
        "diff_audit_checks": diff_audit.check_count,
        "query_returned_count": runtime.query.returned_count,
        "query_audit_accepted": runtime.query_audit.accepted,
        "runtime_audit_accepted": runtime_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "release_ready": runtime.release_ready,
        "baseline_history_audit_accepted": baseline_audit.accepted,
        "diff_address": history_diff.content_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": runtime_audit.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "history-diff-runtime"
        history_diff_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "diff-audit.json").write_text(history_diff_audit_model.audit_json(diff_audit), encoding="utf-8")
        (root / "runtime-audit.json").write_text(history_diff_runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(history_diff_runtime_audit_model.render_audit_markdown(runtime_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["history_diff_runtime_directory"] = str(runtime_root.resolve())
        summary["history_diff_runtime_files"] = list(history_diff_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare value-free remediation resolution histories over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["diff_audit_accepted"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
