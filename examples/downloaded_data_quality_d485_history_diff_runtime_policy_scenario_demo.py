"""Compare strict and release D484 runtimes as a D485 policy scenario."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d483_history_diff_runtime_registry_history_diff as diff_model
from glio_noncode import downloaded_data_quality_d484_history_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario as scenario_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_audit as audit_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query as query_model
from glio_noncode import downloaded_data_quality_d485_history_diff_runtime_policy_scenario_query_audit as query_audit_model


def _runtime_policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(
        policy_id,
        diff_id,
        maximum_added=maximum_added,
        maximum_removed=0,
        maximum_changed=0,
        allowed_directions=("improved",),
        require_accepted=True,
        require_state_change=True,
        allow_unchanged=True,
    )


def build_demo(
    diff_directory: str | Path,
    destination: str | Path | None = None,
    *,
    source_zip: str | Path | None = None,
) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d485-strict-runtime",
        policy=_runtime_policy("glio-noncode-d485-strict-policy", source_diff.diff_id, maximum_added=0),
    )
    release = runtime_model.run_runtime(
        source_diff,
        runtime_id="glio-noncode-d485-release-runtime",
        policy=_runtime_policy("glio-noncode-d485-release-policy", source_diff.diff_id, maximum_added=1),
    )
    scenario_policy = scenario_model.build_policy(
        "glio-noncode-d485-controlled-policy",
        minimum_runtimes=2,
        minimum_ready=1,
        maximum_blocked=1,
        require_same_diff=True,
        require_same_direction=True,
        require_same_transition=True,
        require_unique_policies=True,
        require_at_least_one_ready=True,
        require_at_least_one_blocked=True,
        require_accepted=True,
        allow_mixed=True,
    )
    scenario = scenario_model.run_scenario(
        (strict, release),
        scenario_id="glio-noncode-d485-controlled-scenario",
        policy=scenario_policy,
    )
    audit = audit_model.audit_scenario(scenario, (strict, release))
    query = query_model.query_scenario(scenario, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    query_audit = query_audit_model.audit_query(query, scenario)
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "scenario_id": scenario.scenario_id,
        "scenario_state": scenario.state,
        "scenario_release_ready": scenario.release_ready,
        "scenario_accepted": scenario.accepted,
        "direction": scenario.direction,
        "state_transition": scenario.state_transition,
        "runtime_count": scenario.entry_count,
        "ready_count": scenario.ready_count,
        "blocked_count": scenario.blocked_count,
        "risk_flags": list(scenario.risk_flags),
        "minimum_margins": {
            "added": scenario.minimum_added_margin,
            "removed": scenario.minimum_removed_margin,
            "changed": scenario.minimum_changed_margin,
        },
        "runtimes": [
            {
                "runtime_id": item.runtime_id,
                "policy_id": item.policy.policy_id,
                "state": item.state,
                "release_ready": item.release_ready,
                "failed_checks": [check.check_id for check in item.checks if not check.passed],
                "margins": {"added": item.policy.maximum_added - item.added_count, "removed": item.policy.maximum_removed - item.removed_count, "changed": item.policy.maximum_changed - item.changed_count},
            }
            for item in (strict, release)
        ],
        "audit": {"check_count": audit.check_count, "passed_count": audit.passed_count, "accepted": audit.accepted},
        "query": {"total_count": query.total_count, "returned_count": query.returned_count, "truncated": query.truncated, "audit_check_count": query_audit.check_count, "audit_passed_count": query_audit.passed_count, "audit_accepted": query_audit.accepted},
        "scenario_address": scenario.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        scenario_directory = scenario_model.persist_scenario(scenario, root / "scenario", overwrite=True)
        (root / "audit.json").write_text(audit_model.audit_json(audit) + "\n", encoding="utf-8")
        (root / "query.json").write_text(query_model.query_json(query) + "\n", encoding="utf-8")
        (root / "query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["scenario_directory"] = str(scenario_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare D484 runtimes as a D485 policy scenario")
    parser.add_argument("diff_directory", type=Path, help="exact four-file D483 history diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["scenario_release_ready"] and result["audit"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
