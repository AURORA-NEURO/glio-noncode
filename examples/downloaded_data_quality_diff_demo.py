"""Compare two structural quality decisions over a real downloaded ZIP.

The baseline and candidate policies are intentionally different: the baseline
allows the bounded cardinality observed in the profile, while the candidate
limits distinct values to one. The resulting diff is value-free and reports
which structural checks regressed under the candidate policy.

Example:

    python examples/downloaded_data_quality_diff_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-quality-diff-demo
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import downloaded_data_catalog as catalog_model
from glio_noncode import downloaded_data_ingestion as ingestion_model
from glio_noncode import downloaded_data_ingestion_runtime as ingestion_runtime_model
from glio_noncode import downloaded_data_profile as profile_model
from glio_noncode import downloaded_data_quality as quality_model
from glio_noncode import downloaded_data_quality_diff as diff_model
from glio_noncode import downloaded_data_quality_diff_audit as diff_audit_model
from glio_noncode import downloaded_data_quality_diff_query as diff_query_model
from glio_noncode import downloaded_data_quality_diff_query_audit as diff_query_audit_model
from glio_noncode import downloaded_data_quality_diff_runtime as diff_runtime_model
from glio_noncode import downloaded_data_quality_diff_runtime_audit as diff_runtime_audit_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-quality-diff-demo-catalog")
    member_names = _selected_member_names(catalog)
    ingestion_runtime = ingestion_runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-ingestion-runtime",
        member_names=member_names,
        resources=("summary",),
        record_limit=ingestion_model.MAX_RECORDS,
        limit=1,
    )
    profile = profile_model.build_profile(ingestion_runtime.batch, profile_id="glio-noncode-downloaded-quality-diff-demo-profile")
    baseline_policy = quality_model.build_policy(
        policy_id="glio-noncode-downloaded-quality-diff-demo-baseline-policy",
        max_missing_ratio_ppm=1_000_000,
        max_null_ratio_ppm=1_000_000,
        max_distinct_values=profile_model.MAX_DISTINCT_VALUES,
        max_value_size=ingestion_model.MAX_RECORD_BYTES,
        failure_state="review",
    )
    candidate_policy = quality_model.build_policy(
        policy_id="glio-noncode-downloaded-quality-diff-demo-candidate-policy",
        max_missing_ratio_ppm=1_000_000,
        max_null_ratio_ppm=1_000_000,
        max_distinct_values=1,
        max_value_size=ingestion_model.MAX_RECORD_BYTES,
        failure_state="review",
    )
    baseline = quality_model.build_quality(profile, policy=baseline_policy, result_id="glio-noncode-downloaded-quality-diff-demo-baseline")
    candidate = quality_model.build_quality(profile, policy=candidate_policy, result_id="glio-noncode-downloaded-quality-diff-demo-candidate")
    runtime = diff_runtime_model.build_runtime(
        baseline,
        candidate,
        runtime_id="glio-noncode-downloaded-quality-diff-demo-runtime",
        resources=("summary", "items", "regressed"),
        limit=diff_query_model.MAX_LIMIT,
    )
    runtime_audit = diff_runtime_audit_model.audit_runtime(runtime)
    diff = runtime.diff
    audit = runtime.audit
    query = runtime.query
    query_audit = runtime.query_audit
    summary: dict[str, object] = {
        "source_name": ingestion_runtime.source_name,
        "source_address": ingestion_runtime.source_address,
        "catalog_member_count": catalog.member_count,
        "selected_member_count": len(member_names),
        "record_count": profile.record_count,
        "profile_member_count": profile.member_count,
        "profile_field_count": profile.field_count,
        "baseline_quality_state": baseline.state,
        "candidate_quality_state": candidate.state,
        "baseline_failed_count": baseline.failed_count,
        "candidate_failed_count": candidate.failed_count,
        "added_count": diff.added_count,
        "removed_count": diff.removed_count,
        "changed_count": diff.changed_count,
        "unchanged_count": diff.unchanged_count,
        "improved_count": diff.improved_count,
        "regressed_count": diff.regressed_count,
        "diff_audit_accepted": audit.accepted,
        "diff_audit_checks": audit.check_count,
        "query_rows": query.returned_count,
        "query_audit_accepted": query_audit.accepted,
        "runtime_audit_accepted": runtime_audit.accepted,
        "runtime_audit_checks": runtime_audit.check_count,
        "runtime_release_ready": runtime.release_ready,
        "baseline_quality_address": baseline.content_address,
        "candidate_quality_address": candidate.content_address,
        "diff_address": diff.content_address,
        "runtime_address": runtime.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "quality-diff-runtime"
        diff_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "baseline-quality.json").write_text(quality_model.quality_json(baseline), encoding="utf-8")
        (root / "candidate-quality.json").write_text(quality_model.quality_json(candidate), encoding="utf-8")
        (root / "diff.json").write_text(diff_model.diff_json(diff), encoding="utf-8")
        (root / "diff.md").write_text(diff_model.render_diff_markdown(diff), encoding="utf-8")
        (root / "audit.json").write_text(diff_audit_model.audit_json(audit), encoding="utf-8")
        (root / "query.json").write_text(diff_query_model.query_json(query), encoding="utf-8")
        (root / "query-audit.json").write_text(diff_query_audit_model.audit_json(query_audit), encoding="utf-8")
        (root / "runtime-audit.json").write_text(diff_runtime_audit_model.audit_json(runtime_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["runtime_directory"] = str(runtime_root.resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare structural quality decisions over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["diff_audit_accepted"] and summary["query_audit_accepted"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
