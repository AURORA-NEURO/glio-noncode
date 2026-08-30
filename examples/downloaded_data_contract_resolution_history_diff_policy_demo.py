"""Demonstrate policy-governed release review over a downloaded ZIP.

The archive is bounded structural input. The demo builds the same value-free
contract, remediation, resolution, and history-diff chain used by the other
downloaded-data examples, then evaluates the history diff against explicit
release thresholds and persists an exact eight-file review runtime.

Example:

    python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-resolution-history-diff-policy-demo
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
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff as history_diff_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy as policy_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_audit as policy_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package as policy_package_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_audit as policy_package_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_query as policy_package_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_query_audit as policy_package_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime as policy_runtime_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_runtime_audit as policy_runtime_audit_model,
)
from glio_noncode import downloaded_data_profile_contract_diff as contract_diff_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-catalog")
    left_names = _selected_member_names(catalog)
    if len(left_names) < 3:
        raise ValueError("the downloaded archive needs at least three structured members for a comparison")
    right_names = left_names[:-2]
    left_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-left-ingestion", member_names=left_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    right_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-right-ingestion", member_names=right_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    left_contract = contract_model.build_contract(profile_model.build_profile(left_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-left-profile"))
    right_contract = contract_model.build_contract(profile_model.build_profile(right_ingestion.batch, profile_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-right-profile"))
    contract_diff = compatibility_model.evaluate(contract_diff_model.build_diff(left_contract, right_contract, diff_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-contract-diff"), gate_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-gate")
    plan = remediation_model.build_plan(contract_diff, plan_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-plan")
    pending = resolution_model.build_resolution(plan, resolution_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-pending")
    statuses = {item.action_address: "resolved" for item in pending.entries if item.required}
    closed = resolution_model.build_resolution(plan, resolution_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-closed", statuses=statuses)
    baseline = history_model.build_history((pending,), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-baseline")
    candidate = history_model.build_history((pending, closed), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-candidate")
    history_diff = history_diff_model.build_diff(baseline, candidate, diff_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo")
    policy = policy_model.default_policy(policy_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-policy")
    evaluation = policy_model.evaluate(history_diff, policy=policy, evaluation_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-evaluation")
    policy_audit = policy_audit_model.audit_evaluation(evaluation)
    runtime = policy_runtime_model.run_runtime(history_diff, policy=policy, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-runtime", evaluation_id=evaluation.evaluation_id, resources=("summary", "rules"), limit=25)
    runtime_audit = policy_runtime_audit_model.audit_runtime(runtime)
    package = policy_package_model.run_package(runtime, package_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-package")
    package_audit = policy_package_audit_model.audit_package(package)
    package_query = policy_package_query_model.query_package(package, resources=("summary", "policy-rules"), limit=25)
    package_query_audit = policy_package_query_audit_model.audit_query(package_query)
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
        "diff_direction": history_diff.direction,
        "policy_id": policy.policy_id,
        "policy_allowed_directions": list(policy.allowed_directions),
        "policy_rule_count": evaluation.rule_count,
        "policy_passed_rule_count": evaluation.passed_rule_count,
        "policy_failed_rule_count": evaluation.failed_rule_count,
        "policy_state": evaluation.state,
        "policy_decision": evaluation.decision,
        "policy_accepted": evaluation.accepted,
        "policy_release_ready": evaluation.release_ready,
        "policy_audit_checks": policy_audit.check_count,
        "policy_audit_accepted": policy_audit.accepted,
        "query_total_count": runtime.query.total_count,
        "query_returned_count": runtime.query.returned_count,
        "query_audit_accepted": runtime.query_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "runtime_audit_accepted": runtime_audit.accepted,
        "policy_package_files": list(policy_package_model.FILES),
        "policy_package_audit_checks": package_audit.check_count,
        "policy_package_audit_accepted": package_audit.accepted,
        "policy_package_query_total_count": package_query.total_count,
        "policy_package_query_returned_count": package_query.returned_count,
        "policy_package_query_audit_checks": package_query_audit.check_count,
        "policy_package_query_audit_accepted": package_query_audit.accepted,
        "policy_package_accepted": package.accepted,
        "policy_package_release_ready": package.release_ready,
        "release_ready": runtime.release_ready,
        "runtime_state": runtime.state,
        "diff_address": history_diff.content_address,
        "evaluation_address": evaluation.content_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": runtime_audit.content_address,
        "policy_package_address": package.content_address,
        "policy_package_audit_address": package_audit.content_address,
        "policy_package_query_address": package_query.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "policy-runtime"
        policy_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        package_root = root / "policy-package"
        policy_package_model.persist_package(package, package_root, overwrite=True)
        (root / "policy-audit.json").write_text(policy_audit_model.audit_json(policy_audit), encoding="utf-8")
        (root / "policy-audit.md").write_text(policy_audit_model.render_audit_markdown(policy_audit), encoding="utf-8")
        (root / "runtime-audit.json").write_text(policy_runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(policy_runtime_audit_model.render_audit_markdown(runtime_audit), encoding="utf-8")
        (root / "policy-package-audit.json").write_text(policy_package_audit_model.audit_json(package_audit), encoding="utf-8")
        (root / "policy-package-audit.md").write_text(policy_package_audit_model.render_audit_markdown(package_audit), encoding="utf-8")
        (root / "policy-package-query-audit.json").write_text(policy_package_query_audit_model.audit_json(package_query_audit), encoding="utf-8")
        (root / "policy-package-query-audit.md").write_text(policy_package_query_audit_model.render_audit_markdown(package_query_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["policy_runtime_directory"] = str(runtime_root.resolve())
        summary["policy_runtime_files"] = list(policy_runtime_model.FILES)
        summary["policy_package_directory"] = str(package_root.resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate policy-governed release readiness over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["policy_audit_accepted"] and summary["runtime_audit_accepted"] and summary["policy_package_accepted"] and summary["policy_package_audit_accepted"] and summary["policy_package_query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
