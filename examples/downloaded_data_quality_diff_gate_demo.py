"""Evaluate a release gate over a real downloaded-data quality diff.

Run the diff demo first so ``diff.json`` is derived from the downloaded ZIP:

    python examples/downloaded_data_quality_diff_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-quality-diff-demo
    python examples/downloaded_data_quality_diff_gate_demo.py \
      artifacts/downloaded-data-quality-diff-demo/diff.json \
      artifacts/downloaded-data-quality-diff-demo/gate

The default policy is intentionally fail-closed. The permissive comparison is
included to make the state machine visible; it does not change the default
decision or mutate the downloaded source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import downloaded_data_quality_diff as diff_model
from glio_noncode import downloaded_data_quality_diff_gate as gate_model
from glio_noncode import downloaded_data_quality_diff_gate_audit as gate_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_query as gate_query_model
from glio_noncode import downloaded_data_quality_diff_gate_query_audit as gate_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_runtime as gate_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_runtime_audit as gate_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history as gate_history_model
from glio_noncode import downloaded_data_quality_diff_gate_history_audit as gate_history_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history_query as gate_history_query_model
from glio_noncode import downloaded_data_quality_diff_gate_history_query_audit as gate_history_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_history_runtime as gate_history_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_history_runtime_audit as gate_history_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation as gate_remediation_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_audit as gate_remediation_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_query as gate_remediation_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_query_audit as gate_remediation_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_runtime as gate_remediation_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_runtime_audit as gate_remediation_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution as gate_remediation_resolution_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_audit as gate_remediation_resolution_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_query as gate_remediation_resolution_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_query_audit as gate_remediation_resolution_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_runtime as gate_remediation_resolution_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_runtime_audit as gate_remediation_resolution_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history as gate_remediation_resolution_history_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_audit as gate_remediation_resolution_history_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_query as gate_remediation_resolution_history_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_query_audit as gate_remediation_resolution_history_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_runtime as gate_remediation_resolution_history_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_runtime_audit as gate_remediation_resolution_history_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff as gate_remediation_resolution_history_diff_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_audit as gate_remediation_resolution_history_diff_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_query as gate_remediation_resolution_history_diff_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_query_audit as gate_remediation_resolution_history_diff_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_runtime as gate_remediation_resolution_history_diff_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_runtime_audit as gate_remediation_resolution_history_diff_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy as gate_remediation_resolution_history_diff_policy_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_audit as gate_remediation_resolution_history_diff_policy_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_query as gate_remediation_resolution_history_diff_policy_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_query_audit as gate_remediation_resolution_history_diff_policy_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_runtime as gate_remediation_resolution_history_diff_policy_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_runtime_audit as gate_remediation_resolution_history_diff_policy_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package as gate_remediation_resolution_history_diff_policy_package_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_audit as gate_remediation_resolution_history_diff_policy_package_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_query as gate_remediation_resolution_history_diff_policy_package_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_query_audit as gate_remediation_resolution_history_diff_policy_package_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry as gate_remediation_resolution_history_diff_policy_package_registry_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_audit as gate_remediation_resolution_history_diff_policy_package_registry_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_query as gate_remediation_resolution_history_diff_policy_package_registry_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_query_audit as gate_remediation_resolution_history_diff_policy_package_registry_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history as gate_remediation_resolution_history_diff_policy_package_registry_history_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_query as gate_remediation_resolution_history_diff_policy_package_registry_history_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_query_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_model
from glio_noncode import downloaded_data_quality_diff_gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit as gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_model


def _permissive_policy(item_count: int) -> gate_model.DownloadedDataQualityDiffGatePolicy:
    provisional = gate_model.DownloadedDataQualityDiffGatePolicy(
        "glio-noncode-downloaded-quality-diff-demo-permissive-policy",
        diff_model.DIRECTIONS,
        item_count,
        item_count,
        item_count,
        item_count,
        True,
        True,
        True,
        gate_model.POLICY_PREFIX + ":pending",
    )
    return gate_model.DownloadedDataQualityDiffGatePolicy(
        provisional.policy_id,
        provisional.allowed_directions,
        provisional.maximum_regressed,
        provisional.maximum_changed,
        provisional.maximum_added,
        provisional.maximum_removed,
        provisional.require_diff_audit,
        provisional.require_query_audit,
        provisional.require_complete_query,
        gate_model.address_policy(provisional),
    )


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    diff = diff_model.diff_from_mapping(json.loads(Path(source).read_text(encoding="utf-8")))
    default_gate = gate_model.evaluate(diff, gate_id="glio-noncode-downloaded-quality-diff-demo-default-gate")
    default_audit = gate_audit_model.audit_gate(default_gate)
    blocked_query = gate_query_model.query_gate(
        default_gate,
        resources=("summary", "blocked"),
        outcome="blocked",
        limit=gate_query_model.MAX_LIMIT,
    )
    blocked_query_audit = gate_query_audit_model.audit_query(blocked_query)
    runtime = gate_runtime_model.build_runtime(
        diff,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-gate-runtime",
        gate_id="glio-noncode-downloaded-quality-diff-demo-default-gate",
        resources=("summary", "findings"),
        limit=gate_query_model.MAX_LIMIT,
    )
    runtime_audit = gate_runtime_audit_model.audit_runtime(runtime)
    permissive_gate = gate_model.evaluate(
        diff,
        policy=_permissive_policy(len(diff.items)),
        gate_id="glio-noncode-downloaded-quality-diff-demo-permissive-gate",
    )
    permissive_runtime = gate_runtime_model.build_runtime(
        diff,
        policy=_permissive_policy(len(diff.items)),
        runtime_id="glio-noncode-downloaded-quality-diff-demo-permissive-runtime",
        gate_id="glio-noncode-downloaded-quality-diff-demo-default-gate",
        resources=("summary", "findings"),
        limit=gate_query_model.MAX_LIMIT,
    )
    history = gate_history_model.build_history(
        runtime,
        history_id="glio-noncode-downloaded-quality-diff-demo-history",
        snapshot_id="default-policy",
    )
    history = gate_history_model.append_history(
        history,
        permissive_runtime,
        snapshot_id="permissive-policy",
        expected_head=history.head_address,
    )
    history_audit = gate_history_audit_model.audit_history(history)
    history_query = gate_history_query_model.query_history(
        history,
        resources=("entries", "improved"),
        transition="improved",
        limit=gate_history_query_model.MAX_LIMIT,
    )
    history_query_audit = gate_history_query_audit_model.audit_query(history_query)
    history_runtime = gate_history_runtime_model.build_runtime(
        history,
        resources=("summary", "entries", "latest"),
        limit=gate_history_query_model.MAX_LIMIT,
    )
    history_runtime_audit = gate_history_runtime_audit_model.audit_runtime(history_runtime)
    remediation = gate_remediation_model.build_plan(default_gate, plan_id="glio-noncode-downloaded-quality-diff-demo-remediation")
    remediation_audit = gate_remediation_audit_model.audit_plan(remediation)
    remediation_query = gate_remediation_query_model.query_plan(
        remediation,
        resources=("summary", "required", "blocked", "critical"),
        required_only=True,
        limit=gate_remediation_query_model.MAX_LIMIT,
    )
    remediation_query_audit = gate_remediation_query_audit_model.audit_query(remediation_query)
    remediation_runtime = gate_remediation_runtime_model.build_runtime(
        default_gate,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-remediation-runtime",
        plan_id=remediation.plan_id,
        resources=("summary", "blocked"),
        limit=gate_remediation_query_model.MAX_LIMIT,
    )
    remediation_runtime_audit = gate_remediation_runtime_audit_model.audit_runtime(remediation_runtime)
    remediation_resolution = gate_remediation_resolution_model.build_resolution(
        remediation,
        resolution_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution",
    )
    remediation_resolution_audit = gate_remediation_resolution_audit_model.audit_resolution(remediation_resolution)
    remediation_resolution_query = gate_remediation_resolution_query_model.query_resolution(
        remediation_resolution,
        resources=("summary", "pending"),
        limit=gate_remediation_resolution_query_model.MAX_LIMIT,
    )
    remediation_resolution_query_audit = gate_remediation_resolution_query_audit_model.audit_query(remediation_resolution_query)
    remediation_resolution_runtime = gate_remediation_resolution_runtime_model.build_runtime(
        remediation_resolution,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-runtime",
        resources=("summary", "pending"),
        limit=gate_remediation_resolution_query_model.MAX_LIMIT,
    )
    remediation_resolution_runtime_audit = gate_remediation_resolution_runtime_audit_model.audit_runtime(remediation_resolution_runtime)
    resolved_statuses = {item.content_address: "resolved" for item in remediation.actions if item.required}
    remediation_resolution_closed = gate_remediation_resolution_model.build_resolution(
        remediation,
        resolution_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-closed",
        statuses=resolved_statuses,
    )
    remediation_resolution_history = gate_remediation_resolution_history_model.build_history(
        (remediation_resolution, remediation_resolution_closed),
        history_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-history",
    )
    remediation_resolution_history_audit = gate_remediation_resolution_history_audit_model.audit_history(remediation_resolution_history)
    remediation_resolution_history_query = gate_remediation_resolution_history_query_model.query_history(
        remediation_resolution_history,
        resources=("summary", "entries", "improved", "latest"),
        limit=gate_remediation_resolution_history_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_query_audit = gate_remediation_resolution_history_query_audit_model.audit_query(remediation_resolution_history_query)
    remediation_resolution_history_runtime = gate_remediation_resolution_history_runtime_model.build_runtime(
        remediation_resolution_history,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-history-runtime",
        resources=("summary", "entries", "improved", "latest"),
        limit=gate_remediation_resolution_history_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_runtime_audit = gate_remediation_resolution_history_runtime_audit_model.audit_runtime(remediation_resolution_history_runtime)
    remediation_resolution_history_baseline = gate_remediation_resolution_history_model.build_history(
        (remediation_resolution,),
        history_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-history-baseline",
    )
    remediation_resolution_history_diff = gate_remediation_resolution_history_diff_model.build_diff(
        remediation_resolution_history_baseline,
        remediation_resolution_history,
        diff_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-history-diff",
    )
    remediation_resolution_history_diff_audit = gate_remediation_resolution_history_diff_audit_model.audit_diff(remediation_resolution_history_diff)
    remediation_resolution_history_diff_query = gate_remediation_resolution_history_diff_query_model.query_diff(
        remediation_resolution_history_diff,
        resources=("summary", "items"),
        limit=gate_remediation_resolution_history_diff_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_query_audit = gate_remediation_resolution_history_diff_query_audit_model.audit_query(remediation_resolution_history_diff_query)
    remediation_resolution_history_diff_runtime = gate_remediation_resolution_history_diff_runtime_model.build_runtime(
        remediation_resolution_history_diff,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-remediation-resolution-history-diff-runtime",
        resources=("summary", "items"),
        change="changed",
        limit=gate_remediation_resolution_history_diff_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_runtime_audit = gate_remediation_resolution_history_diff_runtime_audit_model.audit_runtime(remediation_resolution_history_diff_runtime)
    remediation_resolution_history_diff_policy = gate_remediation_resolution_history_diff_policy_model.default_policy(
        policy_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy",
        max_added_count=1,
        max_improved_delta=1,
    )
    remediation_resolution_history_diff_policy_evaluation = gate_remediation_resolution_history_diff_policy_model.evaluate(
        remediation_resolution_history_diff,
        policy=remediation_resolution_history_diff_policy,
    )
    remediation_resolution_history_diff_policy_audit = gate_remediation_resolution_history_diff_policy_audit_model.audit_evaluation(remediation_resolution_history_diff_policy_evaluation)
    remediation_resolution_history_diff_policy_query = gate_remediation_resolution_history_diff_policy_query_model.query_evaluation(
        remediation_resolution_history_diff_policy_evaluation,
        resources=("summary", "rules"),
        limit=gate_remediation_resolution_history_diff_policy_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_query_audit = gate_remediation_resolution_history_diff_policy_query_audit_model.audit_query(remediation_resolution_history_diff_policy_query)
    remediation_resolution_history_diff_policy_runtime = gate_remediation_resolution_history_diff_policy_runtime_model.build_runtime(
        remediation_resolution_history_diff,
        policy=remediation_resolution_history_diff_policy,
        resources=("summary", "rules"),
        limit=gate_remediation_resolution_history_diff_policy_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_runtime_audit = gate_remediation_resolution_history_diff_policy_runtime_audit_model.audit_runtime(remediation_resolution_history_diff_policy_runtime)
    remediation_resolution_history_diff_policy_package = gate_remediation_resolution_history_diff_policy_package_model.build_package(
        remediation_resolution_history_diff_policy_runtime,
        package_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package",
    )
    remediation_resolution_history_diff_policy_package_audit = gate_remediation_resolution_history_diff_policy_package_audit_model.audit_package(remediation_resolution_history_diff_policy_package)
    remediation_resolution_history_diff_policy_package_query = gate_remediation_resolution_history_diff_policy_package_query_model.query_package(
        remediation_resolution_history_diff_policy_package,
        resources=gate_remediation_resolution_history_diff_policy_package_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_query_audit = gate_remediation_resolution_history_diff_policy_package_query_audit_model.audit_query(remediation_resolution_history_diff_policy_package_query)
    remediation_resolution_history_diff_policy_package_two = gate_remediation_resolution_history_diff_policy_package_model.build_package(
        remediation_resolution_history_diff_policy_runtime,
        package_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-two",
    )
    remediation_resolution_history_diff_policy_package_registry = gate_remediation_resolution_history_diff_policy_package_registry_model.build_registry(
        (remediation_resolution_history_diff_policy_package_two, remediation_resolution_history_diff_policy_package),
        registry_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry",
    )
    remediation_resolution_history_diff_policy_package_registry_audit = gate_remediation_resolution_history_diff_policy_package_registry_audit_model.audit_registry(remediation_resolution_history_diff_policy_package_registry)
    remediation_resolution_history_diff_policy_package_registry_query = gate_remediation_resolution_history_diff_policy_package_registry_query_model.query_registry(
        remediation_resolution_history_diff_policy_package_registry,
        resources=gate_remediation_resolution_history_diff_policy_package_registry_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_query_audit = gate_remediation_resolution_history_diff_policy_package_registry_query_audit_model.audit_query(remediation_resolution_history_diff_policy_package_registry_query)
    remediation_resolution_history_diff_policy_package_registry_baseline = gate_remediation_resolution_history_diff_policy_package_registry_model.build_registry(
        (remediation_resolution_history_diff_policy_package,),
        registry_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry",
    )
    remediation_resolution_history_diff_policy_package_registry_history_baseline = gate_remediation_resolution_history_diff_policy_package_registry_history_model.build_history(
        (remediation_resolution_history_diff_policy_package_registry_baseline,),
        history_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry-history",
    )
    remediation_resolution_history_diff_policy_package_registry_history = gate_remediation_resolution_history_diff_policy_package_registry_history_model.build_history(
        (remediation_resolution_history_diff_policy_package_registry_baseline, remediation_resolution_history_diff_policy_package_registry),
        history_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry-history",
    )
    remediation_resolution_history_diff_policy_package_registry_history_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_audit_model.audit_history(remediation_resolution_history_diff_policy_package_registry_history)
    remediation_resolution_history_diff_policy_package_registry_history_query = gate_remediation_resolution_history_diff_policy_package_registry_history_query_model.query_history(
        remediation_resolution_history_diff_policy_package_registry_history,
        resources=gate_remediation_resolution_history_diff_policy_package_registry_history_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_history_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_history_query_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_query_audit_model.audit_query(remediation_resolution_history_diff_policy_package_registry_history_query)
    remediation_resolution_history_diff_policy_package_registry_history_diff = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_model.build_diff(
        remediation_resolution_history_diff_policy_package_registry_history_baseline,
        remediation_resolution_history_diff_policy_package_registry_history,
        diff_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry-history-diff",
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_audit_model.audit_diff(remediation_resolution_history_diff_policy_package_registry_history_diff)
    remediation_resolution_history_diff_policy_package_registry_history_diff_query = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.query_diff(
        remediation_resolution_history_diff_policy_package_registry_history_diff,
        resources=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_model.audit_query(remediation_resolution_history_diff_policy_package_registry_history_diff_query)
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model.build_runtime(
        remediation_resolution_history_diff_policy_package_registry_history_diff,
        resources=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_model.audit_runtime(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime)
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_second = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model.build_runtime(
        remediation_resolution_history_diff_policy_package_registry_history_diff,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry-history-diff-runtime-second",
        resources=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_model.build_registry(
        (remediation_resolution_history_diff_policy_package_registry_history_diff_runtime, remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_second),
        registry_id="glio-noncode-downloaded-quality-diff-demo-history-diff-policy-package-registry-history-diff-runtime-registry",
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_model.audit_registry(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry)
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_model.query_registry(
        remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry,
        resources=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_model.RESOURCES,
        limit=gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_model.MAX_LIMIT,
    )
    remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit = gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_model.audit_query(
        remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query,
        remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry,
    )
    summary: dict[str, object] = {
        "diff_address": diff.content_address,
        "diff_id": diff.diff_id,
        "finding_count": default_gate.finding_count,
        "safe_count": default_gate.safe_count,
        "review_count": default_gate.review_count,
        "blocked_count": default_gate.blocked_count,
        "default_state": default_gate.state,
        "default_decision": default_gate.decision,
        "default_accepted": default_gate.accepted,
        "default_gate_audit_accepted": default_audit.accepted,
        "blocked_query_rows": blocked_query.returned_count,
        "blocked_query_truncated": blocked_query.truncated,
        "blocked_query_audit_accepted": blocked_query_audit.accepted,
        "runtime_state": runtime.state,
        "runtime_release_ready": runtime.release_ready,
        "runtime_query_rows": runtime.query_returned_count,
        "runtime_query_truncated": runtime.query_truncated,
        "runtime_audit_accepted": runtime_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "history_entry_count": history.entry_count,
        "history_state": history.state,
        "history_release_ready": history.release_ready,
        "history_transitions": tuple(item.transition for item in history.entries),
        "history_audit_accepted": history_audit.accepted,
        "history_audit_checks": history_audit.check_count,
        "history_query_rows": history_query.returned_count,
        "history_query_audit_accepted": history_query_audit.accepted,
        "history_runtime_state": history_runtime.state,
        "history_runtime_release_ready": history_runtime.release_ready,
        "history_runtime_audit_accepted": history_runtime_audit.accepted,
        "history_runtime_audit_checks": history_runtime_audit.check_count,
        "remediation_state": remediation.state,
        "remediation_decision": remediation.decision,
        "remediation_action_count": remediation.action_count,
        "remediation_required_action_count": remediation.required_action_count,
        "remediation_critical_action_count": remediation.critical_action_count,
        "remediation_audit_accepted": remediation_audit.accepted,
        "remediation_audit_checks": remediation_audit.check_count,
        "remediation_query_rows": remediation_query.returned_count,
        "remediation_query_truncated": remediation_query.truncated,
        "remediation_query_audit_accepted": remediation_query_audit.accepted,
        "remediation_runtime_state": remediation_runtime.state,
        "remediation_runtime_release_ready": remediation_runtime.release_ready,
        "remediation_runtime_audit_accepted": remediation_runtime_audit.accepted,
        "remediation_runtime_audit_checks": remediation_runtime_audit.check_count,
        "remediation_resolution_state": remediation_resolution.state,
        "remediation_resolution_decision": remediation_resolution.decision,
        "remediation_resolution_pending_count": remediation_resolution.pending_count,
        "remediation_resolution_required_open_count": remediation_resolution.required_open_count,
        "remediation_resolution_release_ready": remediation_resolution.release_ready,
        "remediation_resolution_audit_accepted": remediation_resolution_audit.accepted,
        "remediation_resolution_audit_checks": remediation_resolution_audit.check_count,
        "remediation_resolution_query_rows": remediation_resolution_query.returned_count,
        "remediation_resolution_query_truncated": remediation_resolution_query.truncated,
        "remediation_resolution_query_audit_accepted": remediation_resolution_query_audit.accepted,
        "remediation_resolution_runtime_state": remediation_resolution_runtime.state,
        "remediation_resolution_runtime_release_ready": remediation_resolution_runtime.release_ready,
        "remediation_resolution_runtime_audit_accepted": remediation_resolution_runtime_audit.accepted,
        "remediation_resolution_runtime_audit_checks": remediation_resolution_runtime_audit.check_count,
        "remediation_resolution_history_entry_count": remediation_resolution_history.entry_count,
        "remediation_resolution_history_state": remediation_resolution_history.state,
        "remediation_resolution_history_decision": remediation_resolution_history.decision,
        "remediation_resolution_history_transitions": tuple(item.transition for item in remediation_resolution_history.entries),
        "remediation_resolution_history_release_ready": remediation_resolution_history.release_ready,
        "remediation_resolution_history_audit_accepted": remediation_resolution_history_audit.accepted,
        "remediation_resolution_history_audit_checks": remediation_resolution_history_audit.check_count,
        "remediation_resolution_history_query_rows": remediation_resolution_history_query.returned_count,
        "remediation_resolution_history_query_truncated": remediation_resolution_history_query.truncated,
        "remediation_resolution_history_query_audit_accepted": remediation_resolution_history_query_audit.accepted,
        "remediation_resolution_history_runtime_state": remediation_resolution_history_runtime.state,
        "remediation_resolution_history_runtime_release_ready": remediation_resolution_history_runtime.release_ready,
        "remediation_resolution_history_runtime_audit_accepted": remediation_resolution_history_runtime_audit.accepted,
        "remediation_resolution_history_runtime_audit_checks": remediation_resolution_history_runtime_audit.check_count,
        "remediation_resolution_history_diff_direction": remediation_resolution_history_diff.direction,
        "remediation_resolution_history_diff_state_transition": remediation_resolution_history_diff.state_transition,
        "remediation_resolution_history_diff_added_count": remediation_resolution_history_diff.added_count,
        "remediation_resolution_history_diff_removed_count": remediation_resolution_history_diff.removed_count,
        "remediation_resolution_history_diff_changed_count": remediation_resolution_history_diff.changed_count,
        "remediation_resolution_history_diff_unchanged_count": remediation_resolution_history_diff.unchanged_count,
        "remediation_resolution_history_diff_improved_delta": remediation_resolution_history_diff.improved_delta,
        "remediation_resolution_history_diff_regressed_delta": remediation_resolution_history_diff.regressed_delta,
        "remediation_resolution_history_diff_audit_accepted": remediation_resolution_history_diff_audit.accepted,
        "remediation_resolution_history_diff_audit_checks": remediation_resolution_history_diff_audit.check_count,
        "remediation_resolution_history_diff_query_rows": remediation_resolution_history_diff_query.returned_count,
        "remediation_resolution_history_diff_query_truncated": remediation_resolution_history_diff_query.truncated,
        "remediation_resolution_history_diff_query_audit_accepted": remediation_resolution_history_diff_query_audit.accepted,
        "remediation_resolution_history_diff_runtime_state": remediation_resolution_history_diff_runtime.state,
        "remediation_resolution_history_diff_runtime_release_ready": remediation_resolution_history_diff_runtime.release_ready,
        "remediation_resolution_history_diff_runtime_audit_accepted": remediation_resolution_history_diff_runtime_audit.accepted,
        "remediation_resolution_history_diff_runtime_audit_checks": remediation_resolution_history_diff_runtime_audit.check_count,
        "remediation_resolution_history_diff_policy_id": remediation_resolution_history_diff_policy.policy_id,
        "remediation_resolution_history_diff_policy_state": remediation_resolution_history_diff_policy_evaluation.state,
        "remediation_resolution_history_diff_policy_decision": remediation_resolution_history_diff_policy_evaluation.decision,
        "remediation_resolution_history_diff_policy_accepted": remediation_resolution_history_diff_policy_evaluation.accepted,
        "remediation_resolution_history_diff_policy_release_ready": remediation_resolution_history_diff_policy_evaluation.release_ready,
        "remediation_resolution_history_diff_policy_passed_rules": remediation_resolution_history_diff_policy_evaluation.passed_rule_count,
        "remediation_resolution_history_diff_policy_failed_rules": remediation_resolution_history_diff_policy_evaluation.failed_rule_count,
        "remediation_resolution_history_diff_policy_audit_accepted": remediation_resolution_history_diff_policy_audit.accepted,
        "remediation_resolution_history_diff_policy_audit_checks": remediation_resolution_history_diff_policy_audit.check_count,
        "remediation_resolution_history_diff_policy_query_rows": remediation_resolution_history_diff_policy_query.returned_count,
        "remediation_resolution_history_diff_policy_query_truncated": remediation_resolution_history_diff_policy_query.truncated,
        "remediation_resolution_history_diff_policy_query_audit_accepted": remediation_resolution_history_diff_policy_query_audit.accepted,
        "remediation_resolution_history_diff_policy_runtime_state": remediation_resolution_history_diff_policy_runtime.state,
        "remediation_resolution_history_diff_policy_runtime_release_ready": remediation_resolution_history_diff_policy_runtime.release_ready,
        "remediation_resolution_history_diff_policy_runtime_audit_accepted": remediation_resolution_history_diff_policy_runtime_audit.accepted,
        "remediation_resolution_history_diff_policy_runtime_audit_checks": remediation_resolution_history_diff_policy_runtime_audit.check_count,
        "remediation_resolution_history_diff_policy_package_state": remediation_resolution_history_diff_policy_package.state,
        "remediation_resolution_history_diff_policy_package_decision": remediation_resolution_history_diff_policy_package.decision,
        "remediation_resolution_history_diff_policy_package_accepted": remediation_resolution_history_diff_policy_package.accepted,
        "remediation_resolution_history_diff_policy_package_release_ready": remediation_resolution_history_diff_policy_package.release_ready,
        "remediation_resolution_history_diff_policy_package_audit_accepted": remediation_resolution_history_diff_policy_package_audit.accepted,
        "remediation_resolution_history_diff_policy_package_audit_checks": remediation_resolution_history_diff_policy_package_audit.check_count,
        "remediation_resolution_history_diff_policy_package_query_rows": remediation_resolution_history_diff_policy_package_query.returned_count,
        "remediation_resolution_history_diff_policy_package_query_truncated": remediation_resolution_history_diff_policy_package_query.truncated,
        "remediation_resolution_history_diff_policy_package_query_audit_accepted": remediation_resolution_history_diff_policy_package_query_audit.accepted,
        "remediation_resolution_history_diff_policy_package_query_audit_checks": remediation_resolution_history_diff_policy_package_query_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_state": remediation_resolution_history_diff_policy_package_registry.state,
        "remediation_resolution_history_diff_policy_package_registry_entries": remediation_resolution_history_diff_policy_package_registry.entry_count,
        "remediation_resolution_history_diff_policy_package_registry_accepted": remediation_resolution_history_diff_policy_package_registry.accepted,
        "remediation_resolution_history_diff_policy_package_registry_release_ready": remediation_resolution_history_diff_policy_package_registry.release_ready,
        "remediation_resolution_history_diff_policy_package_registry_audit_accepted": remediation_resolution_history_diff_policy_package_registry_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_audit_checks": remediation_resolution_history_diff_policy_package_registry_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_query_rows": remediation_resolution_history_diff_policy_package_registry_query.returned_count,
        "remediation_resolution_history_diff_policy_package_registry_query_truncated": remediation_resolution_history_diff_policy_package_registry_query.truncated,
        "remediation_resolution_history_diff_policy_package_registry_query_audit_accepted": remediation_resolution_history_diff_policy_package_registry_query_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_query_audit_checks": remediation_resolution_history_diff_policy_package_registry_query_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_state": remediation_resolution_history_diff_policy_package_registry_history.state,
        "remediation_resolution_history_diff_policy_package_registry_history_entries": remediation_resolution_history_diff_policy_package_registry_history.entry_count,
        "remediation_resolution_history_diff_policy_package_registry_history_transitions": tuple(item.transition for item in remediation_resolution_history_diff_policy_package_registry_history.entries),
        "remediation_resolution_history_diff_policy_package_registry_history_release_ready": remediation_resolution_history_diff_policy_package_registry_history.release_ready,
        "remediation_resolution_history_diff_policy_package_registry_history_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_query_rows": remediation_resolution_history_diff_policy_package_registry_history_query.returned_count,
        "remediation_resolution_history_diff_policy_package_registry_history_query_truncated": remediation_resolution_history_diff_policy_package_registry_history_query.truncated,
        "remediation_resolution_history_diff_policy_package_registry_history_query_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_query_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_query_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_query_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_direction": remediation_resolution_history_diff_policy_package_registry_history_diff.direction,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_state_transition": remediation_resolution_history_diff_policy_package_registry_history_diff.state_transition,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_added_count": remediation_resolution_history_diff_policy_package_registry_history_diff.added_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_removed_count": remediation_resolution_history_diff_policy_package_registry_history_diff.removed_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_changed_count": remediation_resolution_history_diff_policy_package_registry_history_diff.changed_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_unchanged_count": remediation_resolution_history_diff_policy_package_registry_history_diff.unchanged_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_diff_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_query_rows": remediation_resolution_history_diff_policy_package_registry_history_diff_query.returned_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_query_truncated": remediation_resolution_history_diff_policy_package_registry_history_diff_query.truncated,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_state": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime.state,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_release_ready": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime.release_ready,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_state": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry.state,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_entries": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry.entry_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit.check_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_rows": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query.returned_count,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_truncated": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query.truncated,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_accepted": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit.accepted,
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_checks": remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit.check_count,
        "permissive_state": permissive_gate.state,
        "permissive_decision": permissive_gate.decision,
        "permissive_accepted": permissive_gate.accepted,
        "gate_address": default_gate.content_address,
        "policy_address": default_gate.policy.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        (root / "gate.json").write_text(gate_model.gate_json(default_gate), encoding="utf-8")
        (root / "gate.md").write_text(gate_model.render_gate_markdown(default_gate), encoding="utf-8")
        (root / "gate-audit.json").write_text(gate_audit_model.audit_json(default_audit), encoding="utf-8")
        (root / "blocked-query.json").write_text(gate_query_model.query_json(blocked_query), encoding="utf-8")
        (root / "blocked-query-audit.json").write_text(gate_query_audit_model.audit_json(blocked_query_audit), encoding="utf-8")
        runtime_root = root / "gate-runtime"
        gate_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "runtime.md").write_text(gate_runtime_model.render_runtime_markdown(runtime), encoding="utf-8")
        (root / "runtime-audit.json").write_text(gate_runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        (root / "history.json").write_text(gate_history_model.history_json(history), encoding="utf-8")
        (root / "history.md").write_text(gate_history_model.render_history_markdown(history), encoding="utf-8")
        (root / "history-audit.json").write_text(gate_history_audit_model.audit_json(history_audit), encoding="utf-8")
        (root / "history-query.json").write_text(gate_history_query_model.query_json(history_query), encoding="utf-8")
        (root / "history-query-audit.json").write_text(gate_history_query_audit_model.audit_json(history_query_audit), encoding="utf-8")
        history_runtime_root = root / "history-runtime"
        gate_history_runtime_model.persist_runtime(history_runtime, history_runtime_root, overwrite=True)
        (root / "history-runtime.md").write_text(gate_history_runtime_model.render_runtime_markdown(history_runtime), encoding="utf-8")
        (root / "history-runtime-audit.json").write_text(gate_history_runtime_audit_model.audit_json(history_runtime_audit), encoding="utf-8")
        (root / "remediation.json").write_text(gate_remediation_model.remediation_json(remediation), encoding="utf-8")
        (root / "remediation.md").write_text(gate_remediation_model.render_remediation_markdown(remediation), encoding="utf-8")
        (root / "remediation-audit.json").write_text(gate_remediation_audit_model.audit_json(remediation_audit), encoding="utf-8")
        (root / "remediation-query.json").write_text(gate_remediation_query_model.query_json(remediation_query), encoding="utf-8")
        (root / "remediation-query-audit.json").write_text(gate_remediation_query_audit_model.audit_json(remediation_query_audit), encoding="utf-8")
        remediation_runtime_root = root / "remediation-runtime"
        gate_remediation_runtime_model.persist_runtime(remediation_runtime, remediation_runtime_root, overwrite=True)
        (root / "remediation-runtime.md").write_text(gate_remediation_runtime_model.render_runtime_markdown(remediation_runtime), encoding="utf-8")
        (root / "remediation-runtime-audit.json").write_text(gate_remediation_runtime_audit_model.audit_json(remediation_runtime_audit), encoding="utf-8")
        (root / "remediation-resolution.json").write_text(gate_remediation_resolution_model.resolution_json(remediation_resolution), encoding="utf-8")
        (root / "remediation-resolution.md").write_text(gate_remediation_resolution_model.render_resolution_markdown(remediation_resolution), encoding="utf-8")
        (root / "remediation-resolution-audit.json").write_text(gate_remediation_resolution_audit_model.audit_json(remediation_resolution_audit), encoding="utf-8")
        (root / "remediation-resolution-query.json").write_text(gate_remediation_resolution_query_model.query_json(remediation_resolution_query), encoding="utf-8")
        (root / "remediation-resolution-query-audit.json").write_text(gate_remediation_resolution_query_audit_model.audit_json(remediation_resolution_query_audit), encoding="utf-8")
        remediation_resolution_runtime_root = root / "remediation-resolution-runtime"
        gate_remediation_resolution_runtime_model.persist_runtime(remediation_resolution_runtime, remediation_resolution_runtime_root, overwrite=True)
        (root / "remediation-resolution-runtime.md").write_text(gate_remediation_resolution_runtime_model.render_runtime_markdown(remediation_resolution_runtime), encoding="utf-8")
        (root / "remediation-resolution-runtime-audit.json").write_text(gate_remediation_resolution_runtime_audit_model.audit_json(remediation_resolution_runtime_audit), encoding="utf-8")
        (root / "remediation-resolution-history.json").write_text(gate_remediation_resolution_history_model.history_json(remediation_resolution_history), encoding="utf-8")
        (root / "remediation-resolution-history.md").write_text(gate_remediation_resolution_history_model.render_history_markdown(remediation_resolution_history), encoding="utf-8")
        (root / "remediation-resolution-history-audit.json").write_text(gate_remediation_resolution_history_audit_model.audit_json(remediation_resolution_history_audit), encoding="utf-8")
        (root / "remediation-resolution-history-query.json").write_text(gate_remediation_resolution_history_query_model.query_json(remediation_resolution_history_query), encoding="utf-8")
        (root / "remediation-resolution-history-query-audit.json").write_text(gate_remediation_resolution_history_query_audit_model.audit_json(remediation_resolution_history_query_audit), encoding="utf-8")
        remediation_resolution_history_runtime_root = root / "remediation-resolution-history-runtime"
        gate_remediation_resolution_history_runtime_model.persist_runtime(remediation_resolution_history_runtime, remediation_resolution_history_runtime_root, overwrite=True)
        (root / "remediation-resolution-history-runtime.md").write_text(gate_remediation_resolution_history_runtime_model.render_runtime_markdown(remediation_resolution_history_runtime), encoding="utf-8")
        (root / "remediation-resolution-history-runtime-audit.json").write_text(gate_remediation_resolution_history_runtime_audit_model.audit_json(remediation_resolution_history_runtime_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff.json").write_text(gate_remediation_resolution_history_diff_model.diff_json(remediation_resolution_history_diff), encoding="utf-8")
        (root / "remediation-resolution-history-diff.md").write_text(gate_remediation_resolution_history_diff_model.render_diff_markdown(remediation_resolution_history_diff), encoding="utf-8")
        (root / "remediation-resolution-history-diff-audit.json").write_text(gate_remediation_resolution_history_diff_audit_model.audit_json(remediation_resolution_history_diff_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-query.json").write_text(gate_remediation_resolution_history_diff_query_model.query_json(remediation_resolution_history_diff_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-query-audit.json").write_text(gate_remediation_resolution_history_diff_query_audit_model.audit_json(remediation_resolution_history_diff_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_runtime_root = root / "remediation-resolution-history-diff-runtime"
        gate_remediation_resolution_history_diff_runtime_model.persist_runtime(remediation_resolution_history_diff_runtime, remediation_resolution_history_diff_runtime_root, overwrite=True)
        (root / "remediation-resolution-history-diff-runtime.md").write_text(gate_remediation_resolution_history_diff_runtime_model.render_runtime_markdown(remediation_resolution_history_diff_runtime), encoding="utf-8")
        (root / "remediation-resolution-history-diff-runtime-audit.json").write_text(gate_remediation_resolution_history_diff_runtime_audit_model.audit_json(remediation_resolution_history_diff_runtime_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy.json").write_text(gate_remediation_resolution_history_diff_policy_model.evaluation_json(remediation_resolution_history_diff_policy_evaluation), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy.md").write_text(gate_remediation_resolution_history_diff_policy_model.render_evaluation_markdown(remediation_resolution_history_diff_policy_evaluation), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-audit.json").write_text(gate_remediation_resolution_history_diff_policy_audit_model.audit_json(remediation_resolution_history_diff_policy_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-query.json").write_text(gate_remediation_resolution_history_diff_policy_query_model.query_json(remediation_resolution_history_diff_policy_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_query_audit_model.audit_json(remediation_resolution_history_diff_policy_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_runtime_root = root / "remediation-resolution-history-diff-policy-runtime"
        gate_remediation_resolution_history_diff_policy_runtime_model.persist_runtime(remediation_resolution_history_diff_policy_runtime, remediation_resolution_history_diff_policy_runtime_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-runtime.md").write_text(gate_remediation_resolution_history_diff_policy_runtime_model.render_runtime_markdown(remediation_resolution_history_diff_policy_runtime), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-runtime-audit.json").write_text(gate_remediation_resolution_history_diff_policy_runtime_audit_model.audit_json(remediation_resolution_history_diff_policy_runtime_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package.json").write_text(gate_remediation_resolution_history_diff_policy_package_model.package_json(remediation_resolution_history_diff_policy_package), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package.md").write_text(gate_remediation_resolution_history_diff_policy_package_model.render_package_markdown(remediation_resolution_history_diff_policy_package), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_audit_model.audit_json(remediation_resolution_history_diff_policy_package_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-query.json").write_text(gate_remediation_resolution_history_diff_policy_package_query_model.query_json(remediation_resolution_history_diff_policy_package_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_query_audit_model.audit_json(remediation_resolution_history_diff_policy_package_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_root = root / "remediation-resolution-history-diff-policy-package"
        gate_remediation_resolution_history_diff_policy_package_model.persist_package(remediation_resolution_history_diff_policy_package, remediation_resolution_history_diff_policy_package_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-package-registry.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_model.registry_json(remediation_resolution_history_diff_policy_package_registry), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry.md").write_text(gate_remediation_resolution_history_diff_policy_package_registry_model.render_registry_markdown(remediation_resolution_history_diff_policy_package_registry), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-query.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_query_model.query_json(remediation_resolution_history_diff_policy_package_registry_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_query_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_registry_root = root / "remediation-resolution-history-diff-policy-package-registry"
        gate_remediation_resolution_history_diff_policy_package_registry_model.persist_registry(remediation_resolution_history_diff_policy_package_registry, remediation_resolution_history_diff_policy_package_registry_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-package-registry-history.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_model.history_json(remediation_resolution_history_diff_policy_package_registry_history), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history.md").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_model.render_history_markdown(remediation_resolution_history_diff_policy_package_registry_history), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-query.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_query_model.query_json(remediation_resolution_history_diff_policy_package_registry_history_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_query_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_registry_history_root = root / "remediation-resolution-history-diff-policy-package-registry-history"
        gate_remediation_resolution_history_diff_policy_package_registry_history_model.persist_history(remediation_resolution_history_diff_policy_package_registry_history, remediation_resolution_history_diff_policy_package_registry_history_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_model.diff_json(remediation_resolution_history_diff_policy_package_registry_history_diff), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff.md").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_model.render_diff_markdown(remediation_resolution_history_diff_policy_package_registry_history_diff), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_diff_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-query.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_model.query_json(remediation_resolution_history_diff_policy_package_registry_history_diff_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_registry_history_diff_root = root / "remediation-resolution-history-diff-policy-package-registry-history-diff"
        gate_remediation_resolution_history_diff_policy_package_registry_history_diff_model.persist_diff(remediation_resolution_history_diff_policy_package_registry_history_diff, remediation_resolution_history_diff_policy_package_registry_history_diff_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model.runtime_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime.md").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model.render_runtime_markdown(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_root = root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime"
        gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_model.persist_runtime(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime, remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_root, overwrite=True)
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_model.registry_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry.md").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_model.render_registry_markdown(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-query.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_model.query_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query), encoding="utf-8")
        (root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry-query-audit.json").write_text(gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_model.audit_json(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit), encoding="utf-8")
        remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_root = root / "remediation-resolution-history-diff-policy-package-registry-history-diff-runtime-registry"
        gate_remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_model.persist_registry(remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry, remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_root, overwrite=True)
        (root / "permissive-gate.json").write_text(gate_model.gate_json(permissive_gate), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["runtime_directory"] = str(runtime_root.resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a release gate over a downloaded-data quality diff")
    parser.add_argument("diff", type=Path, help="path to a value-free downloaded-data quality diff JSON")
    parser.add_argument("destination", type=Path, nargs="?", help="optional output directory")
    args = parser.parse_args()
    summary = build_demo(args.diff, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if all(summary[key] for key in (
        "default_gate_audit_accepted",
        "blocked_query_audit_accepted",
        "runtime_audit_accepted",
        "history_audit_accepted",
        "history_query_audit_accepted",
        "history_runtime_audit_accepted",
        "remediation_audit_accepted",
        "remediation_query_audit_accepted",
        "remediation_runtime_audit_accepted",
        "remediation_resolution_audit_accepted",
        "remediation_resolution_query_audit_accepted",
        "remediation_resolution_runtime_audit_accepted",
        "remediation_resolution_history_audit_accepted",
        "remediation_resolution_history_query_audit_accepted",
        "remediation_resolution_history_runtime_audit_accepted",
        "remediation_resolution_history_diff_audit_accepted",
        "remediation_resolution_history_diff_query_audit_accepted",
        "remediation_resolution_history_diff_runtime_audit_accepted",
        "remediation_resolution_history_diff_policy_audit_accepted",
        "remediation_resolution_history_diff_policy_query_audit_accepted",
        "remediation_resolution_history_diff_policy_runtime_audit_accepted",
        "remediation_resolution_history_diff_policy_package_audit_accepted",
        "remediation_resolution_history_diff_policy_package_query_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_query_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_query_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_query_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_audit_accepted",
        "remediation_resolution_history_diff_policy_package_registry_history_diff_runtime_registry_query_audit_accepted",
    )) else 2


if __name__ == "__main__":
    raise SystemExit(main())
