"""Run federation reconciliation against downloaded package-registry data.

Example:

    python examples/registry_federation_real_downloaded_data_demo.py \
      --primary-registry C:\\data\\primary-registry \
      --replica-registry C:\\data\\replica-registry

The two registry directories must be canonical outputs of the package-registry
module. The example reports the public receipt, independent audits, release
gate, pairwise agreement matrix, bounded query, consensus execution, strict-
quorum transition diff, history, observatory, and disk replay without exposing
local paths in the generated JSON objects.
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
from glio_noncode import registry_federation_consensus
from glio_noncode import registry_federation_consensus_audit
from glio_noncode import registry_federation_consensus_query
from glio_noncode import registry_federation_consensus_runtime
from glio_noncode import registry_federation_consensus_diff
from glio_noncode import registry_federation_consensus_diff_audit
from glio_noncode import registry_federation_consensus_history
from glio_noncode import registry_federation_consensus_observatory
from glio_noncode import registry_federation_consensus_gate
from glio_noncode import registry_federation_consensus_gate_audit
from glio_noncode import registry_federation_consensus_gate_package
from glio_noncode import registry_federation_consensus_gate_package_audit
from glio_noncode import registry_federation_consensus_gate_runtime
from glio_noncode import registry_federation_consensus_gate_diff
from glio_noncode import registry_federation_consensus_gate_diff_audit
from glio_noncode import registry_federation_consensus_gate_history
from glio_noncode import registry_federation_consensus_gate_history_audit
from glio_noncode import registry_federation_consensus_gate_observatory
from glio_noncode import registry_federation_consensus_gate_observatory_audit


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
    consensus = registry_federation_consensus.build_consensus(federation, consensus_id="downloaded-data-consensus")
    consensus_audit = registry_federation_consensus_audit.audit_consensus(consensus)
    consensus_query = registry_federation_consensus_query.query_consensus(consensus, resources=("packages", "candidates", "actions"), limit=limit)
    consensus_runtime = registry_federation_consensus_runtime.run_consensus_runtime((("primary", primary), ("replica", replica)), runtime_id="downloaded-data-consensus-runtime", federation_id=federation_id, consensus_id="downloaded-data-runtime-consensus", resources=("summary", "packages", "candidates", "actions"), limit=limit)
    strict_quorum = max(1, federation.peer_count)
    strict_consensus = registry_federation_consensus.build_consensus(federation, consensus_id="downloaded-data-consensus-strict", quorum=strict_quorum)
    strict_audit = registry_federation_consensus_audit.audit_consensus(strict_consensus)
    consensus_diff = registry_federation_consensus_diff.build_diff(consensus, strict_consensus, diff_id="downloaded-data-consensus-transition")
    consensus_diff_audit = registry_federation_consensus_diff_audit.audit_diff(consensus_diff)
    consensus_history = registry_federation_consensus_history.build_history(((consensus, consensus_audit), (strict_consensus, strict_audit)), history_id="downloaded-data-consensus-history")
    consensus_observatory = registry_federation_consensus_observatory.build_observatory((consensus_history,), observatory_id="downloaded-data-consensus-observatory")
    gate_runtime = registry_federation_consensus_gate_runtime.run_gate_runtime((("primary", primary), ("replica", replica)), runtime_id="downloaded-data-gate-runtime", federation_id=federation_id, consensus_id="downloaded-data-gate-consensus", gate_id="downloaded-data-release-gate", resources=("summary", "checks", "failures", "evidence"), limit=limit)
    gate_value = gate_runtime.gate
    gate_audit = gate_runtime.audit
    gate_query = gate_runtime.query
    strict_policy_pending = registry_federation_consensus_gate.RegistryFederationConsensusGatePolicy("downloaded-data-strict-policy", ("consistent",), ("accept",), 1, federation.peer_count + 1, 1, 0, 0, True, True, True, False, registry_federation_consensus_gate.POLICY_PREFIX + ":pending")
    strict_policy = registry_federation_consensus_gate.RegistryFederationConsensusGatePolicy(strict_policy_pending.policy_id, strict_policy_pending.allowed_states, strict_policy_pending.allowed_decisions, strict_policy_pending.minimum_peer_count, strict_policy_pending.minimum_quorum, strict_policy_pending.minimum_selected_packages, strict_policy_pending.maximum_unresolved_packages, strict_policy_pending.maximum_blocking_steps, strict_policy_pending.require_consensus_audit, strict_policy_pending.require_remediation_audit, strict_policy_pending.require_remediation_query_audit, strict_policy_pending.require_complete_queries, registry_federation_consensus_gate.address_policy(strict_policy_pending))
    strict_gate = registry_federation_consensus_gate.evaluate_gate(gate_runtime.consensus_runtime, policy=strict_policy, gate_id="downloaded-data-strict-release-gate")
    strict_gate_audit = registry_federation_consensus_gate_audit.audit_gate(strict_gate)
    gate_diff = registry_federation_consensus_gate_diff.build_diff(gate_value, strict_gate, diff_id="downloaded-data-gate-transition")
    gate_diff_audit = registry_federation_consensus_gate_diff_audit.audit_diff(gate_diff)
    gate_history = registry_federation_consensus_gate_history.build_history(((gate_value, gate_audit), (strict_gate, strict_gate_audit)), history_id="downloaded-data-gate-history")
    gate_history_audit = registry_federation_consensus_gate_history_audit.audit_history(gate_history)
    gate_observatory = registry_federation_consensus_gate_observatory.build_observatory((gate_history,), observatory_id="downloaded-data-gate-observatory")
    gate_observatory_audit = registry_federation_consensus_gate_observatory_audit.audit_observatory(gate_observatory)
    query = registry_federation_query.query_federation(federation, resources=("summary", "peers", "packages", "conflicts", "actions"), limit=limit)
    with tempfile.TemporaryDirectory(prefix="federation-demo-verify-") as scratch:
        replay_target = Path(scratch) / "federation"
        federation_model.write_federation(federation, replay_target)
        reloaded = federation_model.load_federation(replay_target)
        disk_replay = reloaded.content_address == federation.content_address
        consensus_target = Path(scratch) / "consensus"
        registry_federation_consensus.write_consensus(consensus, consensus_target)
        consensus_disk_replay = registry_federation_consensus.load_consensus(consensus_target).content_address == consensus.content_address
        gate_package_target = Path(scratch) / "consensus-gate-package"
        gate_package = registry_federation_consensus_gate_package.build_package(gate_runtime.consensus_runtime, gate_value, audit=gate_audit, query=gate_query, package_id="downloaded-data-gate-package")
        registry_federation_consensus_gate_package.write_package(gate_package, gate_package_target)
        gate_package_disk_replay = registry_federation_consensus_gate_package.load_package(gate_package_target).content_address == gate_package.content_address
        gate_package_audit = registry_federation_consensus_gate_package_audit.audit_package(gate_package)
    return {"federation": federation.summary(), "audit": audit.summary(), "gate": gate.summary(), "matrix": matrix.summary(), "matrix_audit": matrix_audit.summary(), "consensus": consensus.summary(), "consensus_audit": consensus_audit.summary(), "consensus_query": consensus_query.summary(), "consensus_query_rows": [row.to_dict() for row in consensus_query.rows], "consensus_runtime": consensus_runtime.summary(), "consensus_diff": consensus_diff.summary(), "consensus_diff_audit": consensus_diff_audit.summary(), "consensus_history": consensus_history.summary(), "consensus_observatory": consensus_observatory.summary(), "consensus_gate_runtime": gate_runtime.summary(), "consensus_gate": gate_value.summary(), "consensus_gate_audit": gate_audit.summary(), "consensus_gate_query": gate_query.summary(), "consensus_gate_diff": gate_diff.summary(), "consensus_gate_diff_audit": gate_diff_audit.summary(), "consensus_gate_history": gate_history.summary(), "consensus_gate_history_audit": gate_history_audit.summary(), "consensus_gate_observatory": gate_observatory.summary(), "consensus_gate_observatory_audit": gate_observatory_audit.summary(), "consensus_gate_package": gate_package.summary(), "consensus_gate_package_audit": gate_package_audit.summary(), "consensus_gate_package_disk_replay": gate_package_disk_replay, "query": query.summary(), "query_rows": [row.to_dict() for row in query.rows], "disk_replay": disk_replay, "consensus_disk_replay": consensus_disk_replay}


def main() -> int:
    args = parse_args()
    report = run(args.primary_registry, args.replica_registry, federation_id=args.federation_id, destination=args.destination, limit=args.limit)
    print(json.dumps(report, indent=2, sort_keys=True, default=list))
    return 0 if report["federation"]["accepted"] and report["gate"]["accepted"] and report["consensus"]["accepted"] and report["consensus_runtime"]["accepted"] and report["consensus_diff_audit"]["accepted"] and report["consensus_gate"]["accepted"] and report["consensus_gate_audit"]["accepted"] and report["consensus_gate_diff_audit"]["accepted"] and report["consensus_gate_history_audit"]["accepted"] and report["consensus_gate_observatory_audit"]["accepted"] and report["consensus_gate_package_audit"]["accepted"] and report["consensus_gate_package_disk_replay"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
