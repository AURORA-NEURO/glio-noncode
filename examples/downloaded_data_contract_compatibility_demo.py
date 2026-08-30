"""Demonstrate policy-governed compatibility over a real downloaded ZIP.

The source archive is read as data only. Two value-free structural contracts
are inferred from different member selections, compared, classified by an
explicit compatibility policy, independently audited, queried, and persisted
as an exact seven-file runtime. No source record values are written.

Example:

    python examples/downloaded_data_contract_compatibility_demo.py \
      C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
      artifacts/downloaded-data-contract-compatibility-demo
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
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_runtime as compatibility_runtime_model,
)
from glio_noncode import (
    downloaded_data_profile_contract_compatibility_runtime_audit as runtime_audit_model,
)
from glio_noncode import downloaded_data_profile_contract_diff as diff_model


def _selected_member_names(catalog: catalog_model.DownloadedDataCatalog) -> tuple[str, ...]:
    return tuple(item.member_name for item in catalog.members if "SCHEMAS" not in item.member_name.upper() and "OPENAPI_SPEC.YAML" not in item.member_name.upper())


def build_demo(source: str | Path, destination: str | Path | None = None) -> dict[str, object]:
    catalog = catalog_model.build_catalog(source, catalog_id="glio-noncode-downloaded-contract-compatibility-demo-catalog")
    left_names = _selected_member_names(catalog)
    if len(left_names) < 3:
        raise ValueError("the downloaded archive needs at least three structured members for a comparison")
    right_names = left_names[:-2]
    left_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-compatibility-demo-left-ingestion", member_names=left_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    right_ingestion = ingestion_runtime_model.run_runtime(source, runtime_id="glio-noncode-downloaded-contract-compatibility-demo-right-ingestion", member_names=right_names, resources=("summary",), record_limit=ingestion_model.MAX_RECORDS, limit=1)
    left_contract = contract_model.build_contract(profile_model.build_profile(left_ingestion.batch, profile_id="glio-noncode-downloaded-contract-compatibility-demo-left-profile"))
    right_contract = contract_model.build_contract(profile_model.build_profile(right_ingestion.batch, profile_id="glio-noncode-downloaded-contract-compatibility-demo-right-profile"))
    diff = diff_model.build_diff(left_contract, right_contract, diff_id="glio-noncode-downloaded-contract-compatibility-demo-diff")
    runtime = compatibility_runtime_model.run_runtime(diff, runtime_id="glio-noncode-downloaded-contract-compatibility-demo-runtime", resources=("summary", "findings"), limit=25)
    closure_audit = runtime_audit_model.audit_runtime(runtime)
    outcome_counts = Counter(item.outcome for item in runtime.gate.findings)
    reason_counts = Counter(reason for item in runtime.gate.findings for reason in item.reason_codes)
    summary = {
        "source_name": Path(source).name,
        "catalog_member_count": catalog.member_count,
        "left_selected_member_count": len(left_names),
        "right_selected_member_count": len(right_names),
        "excluded_member_count": len(left_names) - len(right_names),
        "left_record_count": left_contract.record_count,
        "right_record_count": right_contract.record_count,
        "diff_item_count": len(diff.items),
        "finding_count": runtime.finding_count,
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "query_returned_count": runtime.query.returned_count,
        "query_truncated": runtime.query.truncated,
        "gate_state": runtime.gate.state,
        "gate_decision": runtime.gate.decision,
        "gate_accepted": runtime.gate.accepted,
        "compatibility_audit_accepted": runtime.audit.accepted,
        "compatibility_query_audit_accepted": runtime.query_audit.accepted,
        "runtime_audit_accepted": closure_audit.accepted,
        "runtime_audit_checks": closure_audit.check_count,
        "release_ready": runtime.release_ready,
        "diff_address": runtime.diff_address,
        "gate_address": runtime.gate_address,
        "query_address": runtime.query_address,
        "runtime_address": runtime.content_address,
        "runtime_audit_address": closure_audit.content_address,
    }
    if destination is not None:
        root = Path(destination)
        root.mkdir(parents=True, exist_ok=True)
        runtime_root = root / "compatibility-runtime"
        compatibility_runtime_model.persist_runtime(runtime, runtime_root, overwrite=True)
        (root / "runtime-audit.json").write_text(runtime_audit_model.audit_json(closure_audit), encoding="utf-8")
        (root / "runtime-audit.md").write_text(runtime_audit_model.render_audit_markdown(closure_audit), encoding="utf-8")
        summary["output_directory"] = str(root.resolve())
        summary["compatibility_runtime_directory"] = str(runtime_root.resolve())
        summary["compatibility_runtime_files"] = list(compatibility_runtime_model.FILES)
        (root / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate value-free contract compatibility over a downloaded ZIP")
    parser.add_argument("source", type=Path, help="path to the downloaded ZIP")
    parser.add_argument("destination", type=Path, nargs="?", help="optional demo artifact directory")
    args = parser.parse_args()
    summary = build_demo(args.source, args.destination)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["release_ready"] and summary["runtime_audit_accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
