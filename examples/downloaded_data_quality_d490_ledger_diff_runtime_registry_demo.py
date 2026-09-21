"""Aggregate strict and release D489 runtimes from downloaded data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d488_gate_decision_ledger_diff as diff_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d489_gate_decision_ledger_diff_runtime_audit as runtime_audit_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry as registry_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_audit as audit_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_query as query_model
from glio_noncode import downloaded_data_quality_d490_ledger_diff_runtime_registry_query_audit as query_audit_model


def _runtime_policy(policy_id: str, diff_id: str, *, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(policy_id, diff_id, minimum_items=2, maximum_added=maximum_added, maximum_removed=0, maximum_changed=0, allowed_directions=("improved",), require_accepted=True, require_state_change=True, allow_unchanged=True)


def build_demo(diff_directory: str | Path, destination: str | Path | None = None, *, source_zip: str | Path | None = None) -> dict[str, Any]:
    source_diff = diff_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d490-strict-runtime", policy=_runtime_policy("glio-noncode-d490-strict-policy", source_diff.diff_id, maximum_added=0))
    release = runtime_model.run_runtime(source_diff, runtime_id="glio-noncode-d490-release-runtime", policy=_runtime_policy("glio-noncode-d490-release-policy", source_diff.diff_id, maximum_added=1))
    strict_audit = runtime_audit_model.audit_runtime(strict, source_diff)
    release_audit = runtime_audit_model.audit_runtime(release, source_diff)
    audit_addresses = {strict.runtime_id: strict_audit.content_address, release.runtime_id: release_audit.content_address}
    controlled_policy = registry_model.build_policy("glio-noncode-d490-controlled-policy", minimum_runtimes=2, minimum_ready=1, maximum_blocked=1, require_same_diff=True, require_same_direction=True, require_audited=True, require_release_ready=False)
    controlled = registry_model.run_registry((strict, release), registry_id="glio-noncode-d490-controlled-registry", policy=controlled_policy, audit_addresses=audit_addresses)
    controlled_audit = audit_model.audit_registry(controlled, (strict, release))
    controlled_query = query_model.query_registry(controlled, resources=query_model.RESOURCES, limit=query_model.MAX_LIMIT)
    controlled_query_audit = query_audit_model.audit_query(controlled_query, controlled)
    preview = registry_model.build_registry((strict, release), registry_id="glio-noncode-d490-all-ready-preview", policy=registry_model.build_policy("glio-noncode-d490-all-ready-preview-policy", minimum_runtimes=2, minimum_ready=2, maximum_blocked=0, require_same_diff=True, require_same_direction=True, require_audited=False, require_release_ready=True))
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_id": source_diff.diff_id,
        "runtimes": {"strict": {"runtime_id": strict.runtime_id, "state": strict.state, "release_ready": strict.release_ready, "failed_checks": [item.check_id for item in strict.checks if not item.passed]}, "release": {"runtime_id": release.runtime_id, "state": release.state, "release_ready": release.release_ready, "passed_count": release.passed_count}},
        "controlled_registry": {"registry_id": controlled.registry_id, "state": controlled.state, "release_ready": controlled.release_ready, "entry_count": controlled.entry_count, "ready_count": controlled.ready_count, "blocked_count": controlled.blocked_count, "audited_count": controlled.audited_count, "accepted": controlled.accepted, "address": controlled.content_address},
        "all_ready_preview": {"state": preview.state, "release_ready": preview.release_ready, "failed_checks": [item.check_id for item in preview.checks if not item.passed]},
        "audit": {"runtime_strict": {"check_count": strict_audit.check_count, "passed_count": strict_audit.passed_count, "accepted": strict_audit.accepted}, "runtime_release": {"check_count": release_audit.check_count, "passed_count": release_audit.passed_count, "accepted": release_audit.accepted}, "registry": {"check_count": controlled_audit.check_count, "passed_count": controlled_audit.passed_count, "accepted": controlled_audit.accepted}},
        "query": {"total_count": controlled_query.total_count, "returned_count": controlled_query.returned_count, "truncated": controlled_query.truncated, "audit_check_count": controlled_query_audit.check_count, "audit_passed_count": controlled_query_audit.passed_count, "audit_accepted": controlled_query_audit.accepted},
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        strict_directory = runtime_model.persist_runtime(strict, root / "strict-runtime", overwrite=True)
        release_directory = runtime_model.persist_runtime(release, root / "release-runtime", overwrite=True)
        registry_directory = registry_model.persist_registry(controlled, root / "registry", overwrite=True)
        (root / "strict-runtime-audit.json").write_text(runtime_audit_model.audit_json(strict_audit) + "\n", encoding="utf-8")
        (root / "release-runtime-audit.json").write_text(runtime_audit_model.audit_json(release_audit) + "\n", encoding="utf-8")
        (root / "registry-audit.json").write_text(audit_model.audit_json(controlled_audit) + "\n", encoding="utf-8")
        (root / "registry-query.json").write_text(query_model.query_json(controlled_query) + "\n", encoding="utf-8")
        (root / "registry-query-audit.json").write_text(query_audit_model.audit_json(controlled_query_audit) + "\n", encoding="utf-8")
        result["output_directory"] = str(root.resolve())
        result["strict_runtime_directory"] = str(strict_directory.resolve())
        result["release_runtime_directory"] = str(release_directory.resolve())
        result["registry_directory"] = str(registry_directory.resolve())
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate D489 ledger-diff runtimes into a controlled registry")
    parser.add_argument("diff_directory", type=Path, help="exact six-file D488 ledger diff directory")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--source-zip", type=Path, help="optional provenance path for the downloaded source archive")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["controlled_registry"]["release_ready"] and result["audit"]["registry"]["accepted"] and result["query"]["audit_accepted"] and not result["query"]["truncated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
