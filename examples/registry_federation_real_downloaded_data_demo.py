"""Run federation reconciliation against downloaded package-registry data.

Example:

    python examples/registry_federation_real_downloaded_data_demo.py \
      --primary-registry C:\\data\\primary-registry \
      --replica-registry C:\\data\\replica-registry

The two registry directories must be canonical outputs of the package-registry
module. The example reports the public receipt, independent audits, release
gate, pairwise agreement matrix, bounded query, and optional disk replay
without exposing local paths in the generated JSON objects.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode import registry_federation_audit
from glio_noncode import registry_federation_gate
from glio_noncode import registry_federation_matrix
from glio_noncode import registry_federation_matrix_audit
from glio_noncode import registry_federation_query
from glio_noncode import registry_federation_runtime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="demonstrate package-registry federation on downloaded data")
    parser.add_argument("--primary-registry", required=True, type=Path)
    parser.add_argument("--replica-registry", required=True, type=Path)
    parser.add_argument("--federation-id", default="downloaded-data-federation")
    parser.add_argument("--destination", default=None, type=Path)
    parser.add_argument("--limit", default=10, type=int)
    return parser.parse_args()


def run(primary: Path, replica: Path, *, federation_id: str, destination: Path | None, limit: int) -> dict[str, object]:
    runtime = registry_federation_runtime.run_federation_runtime((("primary", primary), ("replica", replica)), runtime_id="downloaded-data-runtime", federation_id=federation_id, destination=destination, resources=("summary", "peers", "packages", "conflicts", "actions"), limit=limit)
    federation = runtime.federation
    audit = registry_federation_audit.audit_federation(federation)
    gate = registry_federation_gate.evaluate_gate(federation, audit, gate_id="downloaded-data-release-gate")
    matrix = registry_federation_matrix.build_matrix(federation, matrix_id="downloaded-data-agreement-matrix")
    matrix_audit = registry_federation_matrix_audit.audit_matrix(matrix)
    query = registry_federation_query.query_federation(federation, resources=("summary", "peers", "packages", "conflicts", "actions"), limit=limit)
    with tempfile.TemporaryDirectory(prefix="federation-demo-verify-") as scratch:
        replay_target = Path(scratch) / "federation"
        federation_model.write_federation(federation, replay_target)
        reloaded = federation_model.load_federation(replay_target)
        disk_replay = reloaded.content_address == federation.content_address
    return {"federation": federation.summary(), "audit": audit.summary(), "gate": gate.summary(), "matrix": matrix.summary(), "matrix_audit": matrix_audit.summary(), "query": query.summary(), "query_rows": [row.to_dict() for row in query.rows], "disk_replay": disk_replay}


def main() -> int:
    args = parse_args()
    report = run(args.primary_registry, args.replica_registry, federation_id=args.federation_id, destination=args.destination, limit=args.limit)
    print(json.dumps(report, indent=2, sort_keys=True, default=list))
    return 0 if report["federation"]["accepted"] and report["gate"]["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
