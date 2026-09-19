"""Evaluate structural quality of a real downloaded ZIP.

The quality result is deliberately value-free at the decision surface. The
source values are used only to build the existing bounded ingestion batch and
profile; the emitted policy, findings, audits, and query contain counts,
addresses, and explanations rather than a copied source payload.

Example:

    python examples/downloaded_data_quality_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-quality-demo
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
from glio_noncode import downloaded_data_quality_audit as quality_audit_model
from glio_noncode import downloaded_data_quality_query as quality_query_model
from glio_noncode import downloaded_data_quality_query_audit as quality_query_audit_model
from glio_noncode import downloaded_data_quality_runtime as quality_runtime_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(
        item.member_name
        for item in catalog.members
        if "SCHEMAS" not in item.member_name.upper()
        and "OPENAPI_SPEC.YAML" not in item.member_name.upper()
    )


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-quality-demo-catalog")
    member_names = _selected_member_names(catalog)
    ingestion_runtime = ingestion_runtime_model.run_runtime(
        source,
        runtime_id="glio-noncode-downloaded-quality-demo-ingestion-runtime",
        member_names=member_names,
        resources=("summary",),
        record_limit=ingestion_model.MAX_RECORDS,
        limit=1,
    )
    profile = profile_model.build_profile(ingestion_runtime.batch, profile_id="glio-noncode-downloaded-quality-demo-profile")
    policy = quality_model.build_policy(
        policy_id="glio-noncode-downloaded-quality-demo-policy",
        min_records=1,
        max_missing_ratio_ppm=1_000_000,
        max_null_ratio_ppm=1_000_000,
        max_distinct_values=profile_model.MAX_DISTINCT_VALUES,
        max_value_size=ingestion_model.MAX_RECORD_BYTES,
        failure_state="review",
    )
    runtime = quality_runtime_model.build_runtime(
        profile,
        policy=policy,
        runtime_id="glio-noncode-downloaded-quality-demo-runtime",
        result_id="glio-noncode-downloaded-quality-demo-result",
        resources=("summary", "findings"),
        limit=10_000,
    )
    quality = runtime.quality
    audit = runtime.audit
    query = runtime.query
    query_audit = runtime.query_audit
    failed_rules = [item.rule_id for item in quality.findings if not item.passed]
    summary: dict[str, object] = {
        "source_name": ingestion_runtime.source_name,
        "source_address": ingestion_runtime.source_address,
        "catalog_member_count": catalog.member_count,
        "selected_member_count": len(member_names),
        "record_count": profile.record_count,
        "profile_member_count": profile.member_count,
        "profile_field_count": profile.field_count,
        "total_value_bytes": profile.total_value_bytes,
        "policy_address": policy.content_address,
        "quality_state": quality.state,
        "quality_accepted": quality.accepted,
        "quality_checks": quality.check_count,
        "quality_failed_checks": quality.failed_count,
        "quality_failed_rules": failed_rules,
        "quality_audit_accepted": audit.accepted,
        "quality_audit_checks": audit.check_count,
        "quality_query_rows": query.returned_count,
        "quality_query_audit_accepted": query_audit.accepted,
        "quality_address": quality.content_address,
        "quality_audit_address": audit.content_address,
        "quality_query_address": query.content_address,
        "quality_query_audit_address": query_audit.content_address,
        "quality_runtime_address": runtime.content_address,
        "quality_runtime_release_ready": runtime.release_ready,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "quality-runtime"
        quality_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "policy.json").write_text(quality_model.policy_json(policy), encoding="utf-8")
        (root / "quality.json").write_text(quality_model.quality_json(quality), encoding="utf-8")
        (root / "quality.md").write_text(quality_model.render_quality_markdown(quality), encoding="utf-8")
        (root / "audit.json").write_text(quality_audit_model.audit_json(audit), encoding="utf-8")
        (root / "audit.md").write_text(quality_audit_model.render_audit_markdown(audit), encoding="utf-8")
        (root / "query.json").write_text(quality_query_model.query_json(query), encoding="utf-8")
        (root / "query.md").write_text(quality_query_model.render_query_markdown(query), encoding="utf-8")
        (root / "query-audit.json").write_text(quality_query_audit_model.audit_json(query_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["quality_runtime_directory"] = str(runtime_root.resolve())
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate structural quality of a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["quality_audit_accepted"] and summary["quality_query_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
