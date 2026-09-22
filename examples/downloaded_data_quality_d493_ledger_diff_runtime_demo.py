"""Evaluate policy-gated release readiness on a downloaded-data history diff."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import downloaded_data_quality_d492_ledger_diff_runtime_registry_history_diff as source_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime as runtime_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_audit as audit_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query as query_model
from glio_noncode import downloaded_data_quality_d493_ledger_diff_runtime_registry_history_diff_runtime_query_audit as query_audit_model
from glio_noncode import downloaded_data_quality_d494_release_evidence_archive as evidence_model
from glio_noncode import downloaded_data_quality_d494_release_evidence_archive_audit as evidence_audit_model


def _policy(policy_id: str, diff_id: str, maximum_added: int) -> runtime_model.RuntimePolicy:
    return runtime_model.build_policy(
        policy_id,
        diff_id,
        minimum_items=2,
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
    """Run strict and release budgets against one D492 comparison artifact."""
    source = source_model.load_diff(diff_directory)
    strict = runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-d493-strict-runtime",
        policy=_policy("glio-noncode-d493-strict-policy", source.diff_id, 0),
    )
    release = runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-d493-release-runtime",
        policy=_policy("glio-noncode-d493-release-policy", source.diff_id, 1),
    )
    strict_audit = audit_model.audit_runtime(strict, source)
    release_audit = audit_model.audit_runtime(release, source)
    release_query = query_model.query_runtime(
        release,
        resources=query_model.RESOURCES,
        limit=query_model.MAX_LIMIT,
    )
    query_audit = query_audit_model.audit_query(release_query, release)
    evidence = evidence_model.build_archive(
        source, strict, strict_audit, release, release_audit, release_query, query_audit,
        bundle_id="glio-noncode-d494-real-release-evidence",
    )
    evidence_audit = evidence_audit_model.audit_archive(evidence)
    blocked_checks = [item.check_id for item in strict.checks if not item.passed]
    result: dict[str, Any] = {
        "source_zip": str(Path(source_zip).resolve()) if source_zip is not None else None,
        "source_diff_directory": str(Path(diff_directory).resolve()),
        "source_diff": {
            "diff_id": source.diff_id,
            "address": source.content_address,
            "accepted": source.accepted,
            "direction": source.direction,
            "state_transition": source.state_transition,
            "items": source.item_count,
            "added": source.added_count,
            "removed": source.removed_count,
            "changed": source.changed_count,
            "unchanged": source.unchanged_count,
        },
        "policies": {
            "strict_maximum_added": strict.policy.maximum_added,
            "release_maximum_added": release.policy.maximum_added,
            "maximum_removed": release.policy.maximum_removed,
            "maximum_changed": release.policy.maximum_changed,
            "allowed_directions": list(release.policy.allowed_directions),
        },
        "evaluations": {
            item.runtime_id: {
                "state": item.state,
                "release_ready": item.release_ready,
                "checks": f"{item.passed_count}/{item.check_count}",
                "failed_checks": [check.check_id for check in item.checks if not check.passed],
                "address": item.content_address,
            }
            for item in (strict, release)
        },
        "release_audit": {
            "accepted": release_audit.accepted,
            "checks": f"{release_audit.passed_count}/{release_audit.check_count}",
        },
        "strict_audit": {
            "accepted": strict_audit.accepted,
            "checks": f"{strict_audit.passed_count}/{strict_audit.check_count}",
        },
        "release_query": {
            "resources": list(release_query.resources),
            "rows": f"{release_query.returned_count}/{release_query.total_count}",
            "truncated": release_query.truncated,
            "audit_accepted": query_audit.accepted,
            "audit_checks": f"{query_audit.passed_count}/{query_audit.check_count}",
        },
        "evidence_bundle": {
            "state": evidence.manifest.state,
            "release_ready": evidence.manifest.release_ready,
            "file_count": evidence.manifest.file_count,
            "total_size": evidence.manifest.total_size,
            "archive_address": evidence.content_address,
            "audit_accepted": evidence_audit.accepted,
            "audit_checks": f"{evidence_audit.passed_count}/{evidence_audit.check_count}",
        },
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_model.persist_runtime(strict, root / "strict-runtime", overwrite=True)
        runtime_model.persist_runtime(release, root / "release-runtime", overwrite=True)
        (root / "strict-audit.json").write_text(audit_model.audit_json(strict_audit) + "\n", encoding="utf-8")
        (root / "release-audit.json").write_text(audit_model.audit_json(release_audit) + "\n", encoding="utf-8")
        (root / "release-audit.md").write_text(audit_model.render_audit_markdown(release_audit), encoding="utf-8")
        (root / "release-query.json").write_text(query_model.query_json(release_query) + "\n", encoding="utf-8")
        (root / "release-query.csv").write_text(query_model.query_csv(release_query), encoding="utf-8")
        (root / "release-query-audit.json").write_text(query_audit_model.audit_json(query_audit) + "\n", encoding="utf-8")
        archive_path = evidence_model.persist_archive(evidence, root / "release-evidence.zip", overwrite=True)
        loaded_evidence = evidence_model.load_archive(archive_path)
        loaded_audit = evidence_audit_model.audit_archive(loaded_evidence)
        (root / "release-evidence-audit.json").write_text(evidence_audit_model.audit_json(loaded_audit) + "\n", encoding="utf-8")
        (root / "release-evidence-audit.md").write_text(evidence_audit_model.render_audit_markdown(loaded_audit), encoding="utf-8")
        result["evidence_bundle"]["archive_path"] = str(archive_path.resolve())
        result["evidence_bundle"]["round_trip_verified"] = loaded_evidence.content_address == evidence.content_address
        result["evidence_bundle"]["loaded_audit_accepted"] = loaded_audit.accepted
        result["output_directory"] = str(root.resolve())
        result["report_path"] = str((root / "demo-report.md").resolve())
        report = [
            "# D493/D494 real downloaded-data demonstration",
            "",
            f"- Source archive: `{result['source_zip']}`",
            f"- Comparison: `{source.diff_id}` ({source.content_address})",
            f"- Data change: {source.added_count} added, {source.removed_count} removed, {source.changed_count} changed, {source.unchanged_count} unchanged",
            f"- Comparison direction: **{source.direction}** (`{source.state_transition}`)",
            "",
            "## Policy outcomes",
            "",
            f"- Strict budget: at most {strict.policy.maximum_added} additions → **{strict.state}**, {strict.passed_count}/{strict.check_count} checks; blocked by `{', '.join(blocked_checks)}`.",
            f"- Release budget: at most {release.policy.maximum_added} addition → **{release.state}**, {release.passed_count}/{release.check_count} checks.",
            "- Both runtime artifacts pass their independent integrity audits: "
            f"strict {strict_audit.passed_count}/{strict_audit.check_count}; release {release_audit.passed_count}/{release_audit.check_count}.",
            "",
            "## Inspectable release projection",
            "",
            f"- Query: {release_query.returned_count}/{release_query.total_count} rows; truncated: `{str(release_query.truncated).lower()}`.",
            f"- Query audit: {query_audit.passed_count}/{query_audit.check_count} checks; accepted: `{str(query_audit.accepted).lower()}`.",
            f"- Portable evidence ZIP: **{evidence.manifest.state}**, {evidence.manifest.file_count} allowlisted files, {evidence.manifest.total_size} bytes; archive audit {evidence_audit.passed_count}/{evidence_audit.check_count}.",
            "- The ZIP contains a redacted comparison summary, runtimes, audits, query, and report; it excludes source snapshots and paths.",
            "- Persisted outputs: `strict-runtime/`, `release-runtime/`, runtime audits, query JSON/CSV, and query audit.",
            "",
            "This demonstration uses aggregate comparison metadata only; it does not print source records or payload contents.",
        ]
        (root / "demo-report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
        (root / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("diff_directory", type=Path, help="exact D492 history-diff artifact directory")
    parser.add_argument("--destination", type=Path, help="directory for persisted runtimes, audits, and query output")
    parser.add_argument("--source-zip", type=Path, help="optional downloaded archive provenance")
    args = parser.parse_args()
    result = build_demo(args.diff_directory, args.destination, source_zip=args.source_zip)
    print(json.dumps(result, indent=2, sort_keys=True))
    strict = result["evaluations"]["glio-noncode-d493-strict-runtime"]
    release = result["evaluations"]["glio-noncode-d493-release-runtime"]
    return 0 if (
        strict["state"] == "blocked"
        and "added_budget" in blocked_checks_for(result)
        and release["state"] == "ready"
        and result["strict_audit"]["accepted"]
        and result["release_audit"]["accepted"]
        and result["release_query"]["audit_accepted"]
        and not result["release_query"]["truncated"]
        and result["evidence_bundle"]["audit_accepted"]
        and result["evidence_bundle"].get("round_trip_verified", True)
        and result["evidence_bundle"].get("loaded_audit_accepted", True)
    ) else 2


def blocked_checks_for(result: dict[str, Any]) -> list[str]:
    return result["evaluations"]["glio-noncode-d493-strict-runtime"]["failed_checks"]


if __name__ == "__main__":
    raise SystemExit(main())
