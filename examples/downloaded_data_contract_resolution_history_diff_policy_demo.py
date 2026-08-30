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
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry as policy_package_registry_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_audit as policy_package_registry_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_query as policy_package_registry_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_query_audit as policy_package_registry_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history as policy_package_registry_history_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_audit as policy_package_registry_history_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query as policy_package_registry_history_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_query_audit as policy_package_registry_history_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff as policy_package_registry_history_diff_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_audit as policy_package_registry_history_diff_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query as policy_package_registry_history_diff_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit as policy_package_registry_history_diff_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory as policy_package_registry_observatory_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_audit as policy_package_registry_observatory_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_query as policy_package_registry_observatory_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_query_audit as policy_package_registry_observatory_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive as policy_package_registry_observatory_archive_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_audit as policy_package_registry_observatory_archive_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query as policy_package_registry_observatory_archive_query_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_query_audit as policy_package_registry_observatory_archive_query_audit_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime as policy_package_registry_observatory_archive_runtime_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_remediation_resolution_history_diff_policy_package_registry_observatory_archive_runtime_audit as policy_package_registry_observatory_archive_runtime_audit_model,
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
    secondary_policy = policy_model.default_policy(policy_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-secondary-policy")
    secondary_runtime = policy_runtime_model.run_runtime(history_diff, policy=secondary_policy, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-secondary-runtime", evaluation_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-secondary-evaluation", resources=("summary", "rules"), limit=25)
    secondary_package = policy_package_model.run_package(secondary_runtime, package_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-secondary-package")
    package_registry = policy_package_registry_model.run_registry((package, secondary_package), registry_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry")
    package_registry_audit = policy_package_registry_audit_model.audit_registry(package_registry)
    package_registry_query = policy_package_registry_query_model.query_registry(package_registry, resources=("summary", "entries", "ready", "decisions"), decision="promote", limit=25)
    package_registry_query_audit = policy_package_registry_query_audit_model.audit_query(package_registry_query)
    baseline_package_registry = policy_package_registry_model.run_registry((package,), registry_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-history-registry")
    candidate_package_registry = policy_package_registry_model.run_registry((package, secondary_package), registry_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-history-registry")
    registry_history_baseline = policy_package_registry_history_model.run_history((baseline_package_registry,), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-history")
    registry_history_candidate = policy_package_registry_history_model.run_history((baseline_package_registry, candidate_package_registry), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-history")
    registry_history_audit = policy_package_registry_history_audit_model.audit_history(registry_history_candidate)
    registry_history_query = policy_package_registry_history_query_model.query_history(registry_history_candidate, resources=("summary", "entries", "ready", "decisions", "transitions"), transition="improved", limit=25)
    registry_history_query_audit = policy_package_registry_history_query_audit_model.audit_query(registry_history_query)
    registry_history_diff = policy_package_registry_history_diff_model.build_diff(registry_history_baseline, registry_history_candidate, diff_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-history-diff")
    registry_history_diff_audit = policy_package_registry_history_diff_audit_model.audit_diff(registry_history_diff)
    registry_history_diff_query = policy_package_registry_history_diff_query_model.query_diff(registry_history_diff, resources=("summary", "items", "added", "removed", "changed", "unchanged"), change="added", limit=25)
    registry_history_diff_query_audit = policy_package_registry_history_diff_query_audit_model.audit_query(registry_history_diff_query)
    observatory_history_baseline = policy_package_registry_history_model.run_history((baseline_package_registry,), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-observatory-baseline")
    observatory_history_candidate = policy_package_registry_history_model.run_history((baseline_package_registry, candidate_package_registry), history_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-observatory-candidate")
    policy_package_registry_observatory = policy_package_registry_observatory_model.run_observatory((observatory_history_baseline, observatory_history_candidate), observatory_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-observatory")
    policy_package_registry_observatory_audit = policy_package_registry_observatory_audit_model.audit_observatory(policy_package_registry_observatory)
    policy_package_registry_observatory_query = policy_package_registry_observatory_query_model.query_observatory(policy_package_registry_observatory, resources=("summary", "members", "transitions", "improved", "stable"), limit=25)
    policy_package_registry_observatory_query_audit = policy_package_registry_observatory_query_audit_model.audit_query(policy_package_registry_observatory_query)
    policy_package_registry_observatory_archive = policy_package_registry_observatory_archive_model.build_archive(policy_package_registry_observatory, archive_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-observatory-archive")
    policy_package_registry_observatory_archive_audit = policy_package_registry_observatory_archive_audit_model.audit_archive(policy_package_registry_observatory_archive)
    policy_package_registry_observatory_archive_query = policy_package_registry_observatory_archive_query_model.query_archive(policy_package_registry_observatory_archive, resources=policy_package_registry_observatory_archive_query_model.RESOURCES, limit=25)
    policy_package_registry_observatory_archive_query_audit = policy_package_registry_observatory_archive_query_audit_model.audit_query(policy_package_registry_observatory_archive_query)
    policy_package_registry_observatory_archive_runtime = policy_package_registry_observatory_archive_runtime_model.build_runtime(policy_package_registry_observatory_archive, runtime_id="glio-noncode-downloaded-contract-resolution-history-diff-policy-demo-registry-observatory-archive-runtime", resources=policy_package_registry_observatory_archive_query_model.RESOURCES, limit=25)
    policy_package_registry_observatory_archive_runtime_audit = policy_package_registry_observatory_archive_runtime_audit_model.audit_runtime(policy_package_registry_observatory_archive_runtime)
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
        "policy_package_registry_entry_count": package_registry.entry_count,
        "policy_package_registry_accepted_count": package_registry.accepted_count,
        "policy_package_registry_release_ready_count": package_registry.release_ready_count,
        "policy_package_registry_state": package_registry.state,
        "policy_package_registry_accepted": package_registry.accepted,
        "policy_package_registry_release_ready": package_registry.release_ready,
        "policy_package_registry_audit_checks": package_registry_audit.check_count,
        "policy_package_registry_audit_accepted": package_registry_audit.accepted,
        "policy_package_registry_query_total_count": package_registry_query.total_count,
        "policy_package_registry_query_returned_count": package_registry_query.returned_count,
        "policy_package_registry_query_audit_checks": package_registry_query_audit.check_count,
        "policy_package_registry_query_audit_accepted": package_registry_query_audit.accepted,
        "policy_package_registry_history_entry_count": registry_history_candidate.entry_count,
        "policy_package_registry_history_state": registry_history_candidate.state,
        "policy_package_registry_history_transition_counts": {"initial": registry_history_candidate.initial_count, "improved": registry_history_candidate.improved_count, "regressed": registry_history_candidate.regressed_count, "unchanged": registry_history_candidate.unchanged_count, "changed": registry_history_candidate.changed_count},
        "policy_package_registry_history_audit_checks": registry_history_audit.check_count,
        "policy_package_registry_history_audit_accepted": registry_history_audit.accepted,
        "policy_package_registry_history_query_total_count": registry_history_query.total_count,
        "policy_package_registry_history_query_returned_count": registry_history_query.returned_count,
        "policy_package_registry_history_query_audit_checks": registry_history_query_audit.check_count,
        "policy_package_registry_history_query_audit_accepted": registry_history_query_audit.accepted,
        "policy_package_registry_history_diff_direction": registry_history_diff.direction,
        "policy_package_registry_history_diff_added_count": registry_history_diff.added_count,
        "policy_package_registry_history_diff_removed_count": registry_history_diff.removed_count,
        "policy_package_registry_history_diff_changed_count": registry_history_diff.changed_count,
        "policy_package_registry_history_diff_unchanged_count": registry_history_diff.unchanged_count,
        "policy_package_registry_history_diff_audit_checks": registry_history_diff_audit.check_count,
        "policy_package_registry_history_diff_audit_accepted": registry_history_diff_audit.accepted,
        "policy_package_registry_history_diff_query_total_count": registry_history_diff_query.total_count,
        "policy_package_registry_history_diff_query_returned_count": registry_history_diff_query.returned_count,
        "policy_package_registry_history_diff_query_audit_checks": registry_history_diff_query_audit.check_count,
        "policy_package_registry_history_diff_query_audit_accepted": registry_history_diff_query_audit.accepted,
        "policy_package_registry_observatory_member_count": policy_package_registry_observatory.member_count,
        "policy_package_registry_observatory_transition_count": policy_package_registry_observatory.transition_count,
        "policy_package_registry_observatory_state": policy_package_registry_observatory.state,
        "policy_package_registry_observatory_decision": policy_package_registry_observatory.decision,
        "policy_package_registry_observatory_accepted": policy_package_registry_observatory.accepted,
        "policy_package_registry_observatory_release_ready": policy_package_registry_observatory.release_ready,
        "policy_package_registry_observatory_trend_counts": {"stable": policy_package_registry_observatory.unchanged_count, "improved": policy_package_registry_observatory.improved_count, "regressed": policy_package_registry_observatory.regressed_count, "changed": policy_package_registry_observatory.changed_count},
        "policy_package_registry_observatory_audit_checks": policy_package_registry_observatory_audit.check_count,
        "policy_package_registry_observatory_audit_accepted": policy_package_registry_observatory_audit.accepted,
        "policy_package_registry_observatory_query_total_count": policy_package_registry_observatory_query.total_count,
        "policy_package_registry_observatory_query_matched_count": policy_package_registry_observatory_query.matched_count,
        "policy_package_registry_observatory_query_returned_count": policy_package_registry_observatory_query.returned_count,
        "policy_package_registry_observatory_query_audit_checks": policy_package_registry_observatory_query_audit.check_count,
        "policy_package_registry_observatory_query_audit_accepted": policy_package_registry_observatory_query_audit.accepted,
        "policy_package_registry_observatory_archive_size": policy_package_registry_observatory_archive.archive_size,
        "policy_package_registry_observatory_archive_accepted": policy_package_registry_observatory_archive_audit.accepted,
        "policy_package_registry_observatory_archive_audit_checks": policy_package_registry_observatory_archive_audit.check_count,
        "policy_package_registry_observatory_archive_audit_accepted": policy_package_registry_observatory_archive_audit.accepted,
        "policy_package_registry_observatory_archive_query_total_count": policy_package_registry_observatory_archive_query.total_count,
        "policy_package_registry_observatory_archive_query_matched_count": policy_package_registry_observatory_archive_query.matched_count,
        "policy_package_registry_observatory_archive_query_returned_count": policy_package_registry_observatory_archive_query.returned_count,
        "policy_package_registry_observatory_archive_query_audit_checks": policy_package_registry_observatory_archive_query_audit.check_count,
        "policy_package_registry_observatory_archive_query_audit_accepted": policy_package_registry_observatory_archive_query_audit.accepted,
        "policy_package_registry_observatory_archive_runtime_state": policy_package_registry_observatory_archive_runtime.state,
        "policy_package_registry_observatory_archive_runtime_accepted": policy_package_registry_observatory_archive_runtime.accepted,
        "policy_package_registry_observatory_archive_runtime_stage_count": policy_package_registry_observatory_archive_runtime.stage_count,
        "policy_package_registry_observatory_archive_runtime_audit_checks": policy_package_registry_observatory_archive_runtime_audit.check_count,
        "policy_package_registry_observatory_archive_runtime_audit_accepted": policy_package_registry_observatory_archive_runtime_audit.accepted,
        "release_ready": runtime.release_ready,
        "runtime_state": runtime.state,
        "diff_address": history_diff.content_address,
        "evaluation_address": evaluation.content_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": runtime_audit.content_address,
        "policy_package_address": package.content_address,
        "policy_package_audit_address": package_audit.content_address,
        "policy_package_query_address": package_query.content_address,
        "policy_package_registry_address": package_registry.content_address,
        "policy_package_registry_audit_address": package_registry_audit.content_address,
        "policy_package_registry_query_address": package_registry_query.content_address,
        "policy_package_registry_history_address": registry_history_candidate.content_address,
        "policy_package_registry_history_audit_address": registry_history_audit.content_address,
        "policy_package_registry_history_query_address": registry_history_query.content_address,
        "policy_package_registry_history_diff_address": registry_history_diff.content_address,
        "policy_package_registry_history_diff_audit_address": registry_history_diff_audit.content_address,
        "policy_package_registry_history_diff_query_address": registry_history_diff_query.content_address,
        "policy_package_registry_observatory_address": policy_package_registry_observatory.content_address,
        "policy_package_registry_observatory_audit_address": policy_package_registry_observatory_audit.content_address,
        "policy_package_registry_observatory_query_address": policy_package_registry_observatory_query.content_address,
        "policy_package_registry_observatory_query_audit_address": policy_package_registry_observatory_query_audit.content_address,
        "policy_package_registry_observatory_archive_address": policy_package_registry_observatory_archive.content_address,
        "policy_package_registry_observatory_archive_audit_address": policy_package_registry_observatory_archive_audit.content_address,
        "policy_package_registry_observatory_archive_query_address": policy_package_registry_observatory_archive_query.content_address,
        "policy_package_registry_observatory_archive_query_audit_address": policy_package_registry_observatory_archive_query_audit.content_address,
        "policy_package_registry_observatory_archive_runtime_address": policy_package_registry_observatory_archive_runtime.content_address,
        "policy_package_registry_observatory_archive_runtime_audit_address": policy_package_registry_observatory_archive_runtime_audit.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "policy-runtime"
        policy_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        package_root = root / "policy-package"
        policy_package_model.persist_package(package, package_root, overwrite=True)
        registry_root = root / "policy-package-registry"
        policy_package_registry_model.persist_registry(package_registry, registry_root, overwrite=True)
        registry_history_root = root / "policy-package-registry-history"
        policy_package_registry_history_model.persist_history(registry_history_candidate, registry_history_root, overwrite=True)
        registry_history_diff_root = root / "policy-package-registry-history-diff"
        policy_package_registry_history_diff_model.persist_diff(registry_history_diff, registry_history_diff_root, overwrite=True)
        observatory_root = root / "policy-package-registry-observatory"
        policy_package_registry_observatory_model.persist_observatory(policy_package_registry_observatory, observatory_root, overwrite=True)
        archive_path = root / "policy-package-registry-observatory.zip"
        policy_package_registry_observatory_archive_model.write_archive(policy_package_registry_observatory_archive, archive_path, overwrite=True)
        archive_runtime_root = root / "policy-package-registry-observatory-archive-runtime"
        policy_package_registry_observatory_archive_runtime_model.persist_runtime(policy_package_registry_observatory_archive_runtime, archive_runtime_root, overwrite=True)
        (root / "policy-audit.json").write_text(policy_audit_model.audit_json(policy_audit), encoding="utf-8")
        (root / "policy-audit.md").write_text(policy_audit_model.render_audit_markdown(policy_audit), encoding="utf-8")
        (root / "runtime-audit.json").write_text(policy_runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(policy_runtime_audit_model.render_audit_markdown(runtime_audit), encoding="utf-8")
        (root / "policy-package-audit.json").write_text(policy_package_audit_model.audit_json(package_audit), encoding="utf-8")
        (root / "policy-package-audit.md").write_text(policy_package_audit_model.render_audit_markdown(package_audit), encoding="utf-8")
        (root / "policy-package-query-audit.json").write_text(policy_package_query_audit_model.audit_json(package_query_audit), encoding="utf-8")
        (root / "policy-package-query-audit.md").write_text(policy_package_query_audit_model.render_audit_markdown(package_query_audit), encoding="utf-8")
        (root / "policy-package-registry-audit.json").write_text(policy_package_registry_audit_model.audit_json(package_registry_audit), encoding="utf-8")
        (root / "policy-package-registry-audit.md").write_text(policy_package_registry_audit_model.render_audit_markdown(package_registry_audit), encoding="utf-8")
        (root / "policy-package-registry-query-audit.json").write_text(policy_package_registry_query_audit_model.audit_json(package_registry_query_audit), encoding="utf-8")
        (root / "policy-package-registry-query-audit.md").write_text(policy_package_registry_query_audit_model.render_audit_markdown(package_registry_query_audit), encoding="utf-8")
        (root / "policy-package-registry-history-audit.json").write_text(policy_package_registry_history_audit_model.audit_json(registry_history_audit), encoding="utf-8")
        (root / "policy-package-registry-history-audit.md").write_text(policy_package_registry_history_audit_model.render_audit_markdown(registry_history_audit), encoding="utf-8")
        (root / "policy-package-registry-history-query-audit.json").write_text(policy_package_registry_history_query_audit_model.audit_json(registry_history_query_audit), encoding="utf-8")
        (root / "policy-package-registry-history-query-audit.md").write_text(policy_package_registry_history_query_audit_model.render_audit_markdown(registry_history_query_audit), encoding="utf-8")
        (root / "policy-package-registry-history-diff-audit.json").write_text(policy_package_registry_history_diff_audit_model.audit_json(registry_history_diff_audit), encoding="utf-8")
        (root / "policy-package-registry-history-diff-audit.md").write_text(policy_package_registry_history_diff_audit_model.render_audit_markdown(registry_history_diff_audit), encoding="utf-8")
        (root / "policy-package-registry-history-diff-query-audit.json").write_text(policy_package_registry_history_diff_query_audit_model.audit_json(registry_history_diff_query_audit), encoding="utf-8")
        (root / "policy-package-registry-history-diff-query-audit.md").write_text(policy_package_registry_history_diff_query_audit_model.render_audit_markdown(registry_history_diff_query_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-audit.json").write_text(policy_package_registry_observatory_audit_model.audit_json(policy_package_registry_observatory_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-audit.md").write_text(policy_package_registry_observatory_audit_model.render_audit_markdown(policy_package_registry_observatory_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-query.json").write_text(policy_package_registry_observatory_query_model.query_json(policy_package_registry_observatory_query), encoding="utf-8")
        (root / "policy-package-registry-observatory-query-audit.json").write_text(policy_package_registry_observatory_query_audit_model.audit_json(policy_package_registry_observatory_query_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-query-audit.md").write_text(policy_package_registry_observatory_query_audit_model.render_audit_markdown(policy_package_registry_observatory_query_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-archive-query.json").write_text(policy_package_registry_observatory_archive_query_model.query_json(policy_package_registry_observatory_archive_query), encoding="utf-8")
        (root / "policy-package-registry-observatory-archive-query-audit.json").write_text(policy_package_registry_observatory_archive_query_audit_model.audit_json(policy_package_registry_observatory_archive_query_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-archive-query-audit.md").write_text(policy_package_registry_observatory_archive_query_audit_model.render_audit_markdown(policy_package_registry_observatory_archive_query_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-archive-runtime-audit.json").write_text(policy_package_registry_observatory_archive_runtime_audit_model.audit_json(policy_package_registry_observatory_archive_runtime_audit), encoding="utf-8")
        (root / "policy-package-registry-observatory-archive-runtime-audit.md").write_text(policy_package_registry_observatory_archive_runtime_audit_model.render_audit_markdown(policy_package_registry_observatory_archive_runtime_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["policy_runtime_directory"] = str(runtime_root.resolve())
        summary["policy_runtime_files"] = list(policy_runtime_model.FILES)
        summary["policy_package_directory"] = str(package_root.resolve())
        summary["policy_package_registry_directory"] = str(registry_root.resolve())
        summary["policy_package_registry_history_directory"] = str(registry_history_root.resolve())
        summary["policy_package_registry_history_files"] = list(policy_package_registry_history_model.FILES)
        summary["policy_package_registry_history_diff_directory"] = str(registry_history_diff_root.resolve())
        summary["policy_package_registry_history_diff_files"] = list(policy_package_registry_history_diff_model.FILES)
        summary["policy_package_registry_observatory_directory"] = str(observatory_root.resolve())
        summary["policy_package_registry_observatory_files"] = list(policy_package_registry_observatory_model.FILES)
        summary["policy_package_registry_observatory_archive_path"] = str(archive_path.resolve())
        summary["policy_package_registry_observatory_archive_files"] = list(policy_package_registry_observatory_archive_model.FILES)
        summary["policy_package_registry_observatory_archive_runtime_directory"] = str(archive_runtime_root.resolve())
        summary["policy_package_registry_observatory_archive_runtime_files"] = list(policy_package_registry_observatory_archive_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate policy-governed release readiness over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["policy_audit_accepted"] and summary["runtime_audit_accepted"] and summary["policy_package_accepted"] and summary["policy_package_audit_accepted"] and summary["policy_package_query_audit_accepted"] and summary["policy_package_registry_accepted"] and summary["policy_package_registry_audit_accepted"] and summary["policy_package_registry_query_audit_accepted"] and summary["policy_package_registry_history_audit_accepted"] and summary["policy_package_registry_history_query_audit_accepted"] and summary["policy_package_registry_history_diff_audit_accepted"] and summary["policy_package_registry_history_diff_query_audit_accepted"] and summary["policy_package_registry_observatory_accepted"] and summary["policy_package_registry_observatory_audit_accepted"] and summary["policy_package_registry_observatory_query_audit_accepted"] and summary["policy_package_registry_observatory_archive_accepted"] and summary["policy_package_registry_observatory_archive_audit_accepted"] and summary["policy_package_registry_observatory_archive_query_audit_accepted"] and summary["policy_package_registry_observatory_archive_runtime_accepted"] and summary["policy_package_registry_observatory_archive_runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
