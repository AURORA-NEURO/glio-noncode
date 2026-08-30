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
from glio_noncode import registry_federation_consensus_gate_certificate
from glio_noncode import registry_federation_consensus_gate_certificate_audit
from glio_noncode import registry_federation_consensus_gate_certificate_query
from glio_noncode import registry_federation_consensus_gate_certificate_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_package
from glio_noncode import registry_federation_consensus_gate_certificate_package_audit
from glio_noncode import registry_federation_consensus_gate_certificate_runtime
from glio_noncode import registry_federation_consensus_gate_certificate_diff
from glio_noncode import registry_federation_consensus_gate_certificate_diff_audit
from glio_noncode import registry_federation_consensus_gate_certificate_history
from glio_noncode import registry_federation_consensus_gate_certificate_history_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_report_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_package_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_diff_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_runtime
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_runtime_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_replay
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_replay_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_query
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_runtime
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_runtime_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_query
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history_audit
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report_audit


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
    certificate_runtime = registry_federation_consensus_gate_certificate_runtime.run_certificate_runtime((("primary", primary), ("replica", replica)), runtime_id="downloaded-data-certificate-runtime", federation_id=federation_id, consensus_id="downloaded-data-certificate-consensus", gate_id="downloaded-data-release-gate", certificate_id="downloaded-data-release-certificate", certificate_resources=("summary", "checks", "failures", "evidence", "policy"), limit=max(limit, 100))
    certificate = certificate_runtime.certificate
    certificate_audit = certificate_runtime.certificate_audit
    certificate_query = registry_federation_consensus_gate_certificate_query.query_certificate(certificate, resources=("summary", "checks", "failures", "evidence", "policy"), limit=limit)
    certificate_query_audit = registry_federation_consensus_gate_certificate_query_audit.audit_query(certificate_query)
    certificate_gate_runtime = certificate_runtime.gate_runtime
    strict_certificate_pending = registry_federation_consensus_gate_certificate.RegistryFederationConsensusGateCertificatePolicy("downloaded-data-strict-certificate-policy", ("eligible",), ("promote",), 1, certificate_gate_runtime.gate.check_count + 1, True, True, True, False, registry_federation_consensus_gate_certificate.POLICY_PREFIX + ":pending")
    strict_certificate_policy = registry_federation_consensus_gate_certificate.RegistryFederationConsensusGateCertificatePolicy(strict_certificate_pending.policy_id, strict_certificate_pending.allowed_gate_states, strict_certificate_pending.allowed_gate_decisions, strict_certificate_pending.minimum_check_count, strict_certificate_pending.minimum_passed_count, strict_certificate_pending.require_gate_acceptance, strict_certificate_pending.require_gate_audit, strict_certificate_pending.require_query_complete, strict_certificate_pending.require_package, registry_federation_consensus_gate_certificate.address_policy(strict_certificate_pending))
    strict_certificate = registry_federation_consensus_gate_certificate.evaluate_certificate(certificate_gate_runtime, policy=strict_certificate_policy, certificate_id="downloaded-data-strict-release-certificate")
    strict_certificate_audit = registry_federation_consensus_gate_certificate_audit.audit_certificate(strict_certificate)
    certificate_diff = registry_federation_consensus_gate_certificate_diff.build_diff(certificate, strict_certificate, diff_id="downloaded-data-certificate-transition")
    certificate_diff_audit = registry_federation_consensus_gate_certificate_diff_audit.audit_diff(certificate_diff)
    strict_certificate_query = registry_federation_consensus_gate_certificate_query.query_certificate(strict_certificate, resources=("summary", "checks", "failures"), limit=limit)
    strict_certificate_query_audit = registry_federation_consensus_gate_certificate_query_audit.audit_query(strict_certificate_query)
    certificate_history = registry_federation_consensus_gate_certificate_history.build_history(((certificate, certificate_audit),), history_id="downloaded-data-certificate-history")
    certificate_history = registry_federation_consensus_gate_certificate_history.append_history(certificate_history, strict_certificate, strict_certificate_audit)
    certificate_history_audit = registry_federation_consensus_gate_certificate_history_audit.audit_history(certificate_history)
    certificate_observatory = registry_federation_consensus_gate_certificate_observatory.build_observatory((certificate_history,), observatory_id="downloaded-data-certificate-observatory")
    certificate_observatory_audit = registry_federation_consensus_gate_certificate_observatory_audit.audit_observatory(certificate_observatory)
    certificate_observatory_query = registry_federation_consensus_gate_certificate_observatory.query_observatory(certificate_observatory, resources=registry_federation_consensus_gate_certificate_observatory.RESOURCES, limit=max(limit, 100))
    certificate_observatory_query_audit = registry_federation_consensus_gate_certificate_observatory_query_audit.audit_query(certificate_observatory_query)
    certificate_observatory_report = registry_federation_consensus_gate_certificate_observatory_report.build_report(certificate_observatory)
    certificate_observatory_report_audit = registry_federation_consensus_gate_certificate_observatory_report_audit.audit_report(certificate_observatory_report)
    certificate_baseline_history = registry_federation_consensus_gate_certificate_history.build_history(((certificate, certificate_audit),), history_id="downloaded-data-certificate-history")
    certificate_baseline_observatory = registry_federation_consensus_gate_certificate_observatory.build_observatory((certificate_baseline_history,), observatory_id="downloaded-data-certificate-observatory-baseline")
    certificate_observatory_diff = registry_federation_consensus_gate_certificate_observatory_diff.build_diff(certificate_baseline_observatory, certificate_observatory, diff_id="downloaded-data-certificate-observatory-transition")
    certificate_observatory_diff_audit = registry_federation_consensus_gate_certificate_observatory_diff_audit.audit_diff(certificate_observatory_diff)
    certificate_observatory_diff_query = registry_federation_consensus_gate_certificate_observatory_diff.query_diff(certificate_observatory_diff, resources=("summary", "items", "added", "changed", "failures"), limit=max(limit, 100))
    certificate_observatory_diff_query_audit = registry_federation_consensus_gate_certificate_observatory_diff_query_audit.audit_query(certificate_observatory_diff_query)
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
        certificate_package_target = Path(scratch) / "consensus-gate-certificate-package"
        certificate_package = registry_federation_consensus_gate_certificate_package.build_package(certificate_gate_runtime, certificate, gate_audit=certificate_gate_runtime.audit, gate_query=certificate_gate_runtime.query, certificate_audit=certificate_audit, certificate_query=certificate_query, package_id="downloaded-data-certificate-package")
        registry_federation_consensus_gate_certificate_package.write_package(certificate_package, certificate_package_target)
        certificate_package_loaded = registry_federation_consensus_gate_certificate_package.load_package(certificate_package_target)
        certificate_package_disk_replay = certificate_package_loaded.content_address == certificate_package.content_address
        certificate_package_audit = registry_federation_consensus_gate_certificate_package_audit.audit_package(certificate_package_loaded)
        certificate_history_target = Path(scratch) / "consensus-gate-certificate-history"
        registry_federation_consensus_gate_certificate_history.write_history(certificate_history, certificate_history_target)
        certificate_history_loaded = registry_federation_consensus_gate_certificate_history.load_history(certificate_history_target)
        certificate_history_disk_replay = certificate_history_loaded.content_address == certificate_history.content_address
        certificate_history_disk_audit = registry_federation_consensus_gate_certificate_history_audit.audit_history(certificate_history_loaded)
        certificate_observatory_target = Path(scratch) / "consensus-gate-certificate-observatory-package"
        certificate_observatory_package = registry_federation_consensus_gate_certificate_observatory_package.build_package(certificate_observatory, query=certificate_observatory_query, report=certificate_observatory_report, observatory_audit=certificate_observatory_audit, query_audit=certificate_observatory_query_audit, report_audit=certificate_observatory_report_audit, package_id="downloaded-data-certificate-observatory-package")
        registry_federation_consensus_gate_certificate_observatory_package.write_package(certificate_observatory_package, certificate_observatory_target)
        certificate_observatory_package_loaded = registry_federation_consensus_gate_certificate_observatory_package.load_package(certificate_observatory_target)
        certificate_observatory_package_disk_replay = certificate_observatory_package_loaded.content_address == certificate_observatory_package.content_address
        certificate_observatory_package_audit = registry_federation_consensus_gate_certificate_observatory_package_audit.audit_package(certificate_observatory_package_loaded)
        certificate_observatory_runtime_target = Path(scratch) / "consensus-gate-certificate-observatory-runtime-package"
        certificate_observatory_runtime = registry_federation_consensus_gate_certificate_observatory_runtime.run_runtime((certificate_history_target,), runtime_id="downloaded-data-certificate-observatory-runtime", destination=certificate_observatory_runtime_target, limit=max(limit, 100))
        certificate_observatory_runtime_audit = registry_federation_consensus_gate_certificate_observatory_runtime_audit.audit_runtime(certificate_observatory_runtime)
        certificate_observatory_replay = registry_federation_consensus_gate_certificate_observatory_replay.replay_package(certificate_observatory_runtime_target)
        certificate_observatory_replay_audit = registry_federation_consensus_gate_certificate_observatory_replay_audit.audit_replay(certificate_observatory_replay)
        certificate_observatory_archive = registry_federation_consensus_gate_certificate_observatory_archive.build_archive(certificate_observatory_package_loaded, archive_id="downloaded-data-certificate-observatory-archive")
        certificate_observatory_archive_target = Path(scratch) / "consensus-gate-certificate-observatory.zip"
        registry_federation_consensus_gate_certificate_observatory_archive.write_archive(certificate_observatory_archive, certificate_observatory_archive_target)
        certificate_observatory_archive_loaded = registry_federation_consensus_gate_certificate_observatory_archive.load_archive(certificate_observatory_archive_target)
        certificate_observatory_archive_disk_replay = certificate_observatory_archive_loaded.content_address == certificate_observatory_archive.content_address
        certificate_observatory_archive_audit = registry_federation_consensus_gate_certificate_observatory_archive_audit.audit_archive(certificate_observatory_archive_loaded)
        certificate_observatory_archive_query = registry_federation_consensus_gate_certificate_observatory_archive_query.query_archive(certificate_observatory_archive_loaded, limit=max(limit, 100))
        certificate_observatory_archive_query_audit = registry_federation_consensus_gate_certificate_observatory_archive_query_audit.audit_query(certificate_observatory_archive_query)
        certificate_observatory_archive_transfer = registry_federation_consensus_gate_certificate_observatory_archive_transfer.build_transfer(certificate_observatory_archive_loaded, transfer_id="downloaded-data-certificate-observatory-transfer", chunk_size=4096)
        certificate_observatory_archive_transfer_target = Path(scratch) / "consensus-gate-certificate-observatory-transfer"
        registry_federation_consensus_gate_certificate_observatory_archive_transfer.write_transfer(certificate_observatory_archive_transfer, certificate_observatory_archive_transfer_target)
        certificate_observatory_archive_transfer_loaded = registry_federation_consensus_gate_certificate_observatory_archive_transfer.load_transfer(certificate_observatory_archive_transfer_target)
        certificate_observatory_archive_transfer_disk_replay = certificate_observatory_archive_transfer_loaded.content_address == certificate_observatory_archive_transfer.content_address
        certificate_observatory_archive_transfer_audit = registry_federation_consensus_gate_certificate_observatory_archive_transfer_audit.audit_transfer(certificate_observatory_archive_transfer_loaded)
        certificate_observatory_archive_transfer_reassembled = registry_federation_consensus_gate_certificate_observatory_archive_transfer.assemble_archive_bytes(certificate_observatory_archive_transfer_loaded) == registry_federation_consensus_gate_certificate_observatory_archive.archive_bytes(certificate_observatory_archive_loaded)
        certificate_observatory_archive_partial_transfer = Path(scratch) / "consensus-gate-certificate-observatory-partial-transfer"
        certificate_observatory_archive_partial_assembler = registry_federation_consensus_gate_certificate_observatory_archive_transfer.TransferAssembler(certificate_observatory_archive_transfer)
        for index in range(0, certificate_observatory_archive_transfer.chunk_count, 2):
            certificate_observatory_archive_partial_assembler.add_chunk(index, registry_federation_consensus_gate_certificate_observatory_archive_transfer.chunk_bytes(certificate_observatory_archive_transfer, index))
        registry_federation_consensus_gate_certificate_observatory_archive_transfer.write_partial_transfer(certificate_observatory_archive_partial_assembler, certificate_observatory_archive_partial_transfer)
        certificate_observatory_archive_recovery_before = registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery.build_recovery_from_directory(certificate_observatory_archive_partial_transfer, recovery_id="downloaded-data-certificate-observatory-transfer-recovery")
        certificate_observatory_archive_recovery_before_query = registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_query.query_recovery(certificate_observatory_archive_recovery_before, resource="missing", limit=max(limit, 100))
        certificate_observatory_archive_recovery_target = Path(scratch) / "consensus-gate-certificate-observatory-recovered-transfer"
        certificate_observatory_archive_recovery = registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery.resume_transfer(certificate_observatory_archive_partial_transfer, certificate_observatory_archive_target, destination=certificate_observatory_archive_recovery_target, recovery_id="downloaded-data-certificate-observatory-transfer-recovery")
        certificate_observatory_archive_recovery_audit = registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_audit.audit_recovery(certificate_observatory_archive_recovery)
        certificate_observatory_archive_recovery_query = registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_query.query_recovery(certificate_observatory_archive_recovery, resource="summary", limit=1)
        certificate_observatory_archive_recovery_disk_replay = registry_federation_consensus_gate_certificate_observatory_archive_transfer.load_transfer(certificate_observatory_archive_recovery_target).content_address == certificate_observatory_archive_transfer.content_address
        certificate_observatory_archive_runtime_target = Path(scratch) / "consensus-gate-certificate-observatory-runtime-archive.zip"
        certificate_observatory_archive_transfer_runtime_target = Path(scratch) / "consensus-gate-certificate-observatory-runtime-transfer"
        certificate_observatory_archive_runtime = registry_federation_consensus_gate_certificate_observatory_archive_runtime.run_runtime((certificate_observatory_target,), runtime_id="downloaded-data-certificate-observatory-archive-runtime", archive_id="downloaded-data-certificate-observatory-runtime-archive", transfer_id="downloaded-data-certificate-observatory-runtime-transfer", chunk_size=4096, limit=max(limit, 100), destination=certificate_observatory_archive_runtime_target, transfer_destination=certificate_observatory_archive_transfer_runtime_target)
        certificate_observatory_archive_runtime_audit = registry_federation_consensus_gate_certificate_observatory_archive_runtime_audit.audit_runtime(certificate_observatory_archive_runtime)
        registry_primary_archive = certificate_observatory_archive_loaded
        registry_replica_archive = registry_federation_consensus_gate_certificate_observatory_archive.build_archive(certificate_observatory_package_loaded, archive_id="downloaded-data-certificate-observatory-replica-archive")
        archive_registry = registry_federation_consensus_gate_certificate_observatory_archive_registry.build_registry_from_archives((registry_primary_archive,), entry_ids=("downloaded-data-observatory-primary",), registry_id="downloaded-data-observatory-registry-primary")
        archive_registry_replica = registry_federation_consensus_gate_certificate_observatory_archive_registry.build_registry_from_archives((registry_primary_archive, registry_replica_archive), entry_ids=("downloaded-data-observatory-primary", "downloaded-data-observatory-replica"), registry_id="downloaded-data-observatory-registry-replica")
        archive_registry_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_audit.audit_registry(archive_registry_replica)
        archive_registry_query = registry_federation_consensus_gate_certificate_observatory_archive_registry_query.query_registry(archive_registry_replica, resources=("summary", "entries", "packages"), limit=max(limit, 100))
        archive_registry_query_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_query_audit.audit_query(archive_registry_query, archive_registry_replica)
        archive_registry_diff = registry_federation_consensus_gate_certificate_observatory_archive_registry_diff.build_diff(archive_registry, archive_registry_replica, diff_id="downloaded-data-observatory-archive-registry-transition")
        archive_registry_diff_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_audit.audit_diff(archive_registry_diff, archive_registry, archive_registry_replica)
        archive_registry_diff_query = registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query.query_diff(archive_registry_diff, resources=("summary", "items", "added", "removed", "changed"), limit=max(limit, 100))
        archive_registry_diff_query_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query_audit.audit_query(archive_registry_diff_query, archive_registry_diff)
        archive_registry_history = registry_federation_consensus_gate_certificate_observatory_archive_registry_history.build_history((archive_registry, archive_registry_replica), history_id="downloaded-data-observatory-archive-registry-history")
        archive_registry_history_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_history_audit.audit_history(archive_registry_history, (archive_registry, archive_registry_replica))
        archive_registry_target = Path(scratch) / "certificate-observatory-archive-registry"
        registry_federation_consensus_gate_certificate_observatory_archive_registry.write_registry(archive_registry_replica, archive_registry_target)
        archive_registry_loaded = registry_federation_consensus_gate_certificate_observatory_archive_registry.load_registry(archive_registry_target)
        archive_registry_disk_replay = archive_registry_loaded.content_address == archive_registry_replica.content_address
        archive_registry_history_target = Path(scratch) / "certificate-observatory-archive-registry-history"
        registry_federation_consensus_gate_certificate_observatory_archive_registry_history.write_history(archive_registry_history, archive_registry_history_target)
        archive_registry_history_loaded = registry_federation_consensus_gate_certificate_observatory_archive_registry_history.load_history(archive_registry_history_target)
        archive_registry_history_disk_replay = archive_registry_history_loaded.content_address == archive_registry_history.content_address
        archive_registry_runtime_target = Path(scratch) / "certificate-observatory-archive-registry-runtime"
        archive_registry_runtime = registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime.run_runtime((certificate_observatory_target, certificate_observatory_target), runtime_id="downloaded-data-observatory-archive-registry-runtime", registry_id="downloaded-data-observatory-runtime-registry", entry_ids=("runtime-primary", "runtime-replica"), archive_ids=("runtime-primary-archive", "runtime-replica-archive"), destination=archive_registry_runtime_target, limit=max(limit, 100))
        archive_registry_runtime_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime_audit.audit_runtime(archive_registry_runtime)
        archive_registry_report = registry_federation_consensus_gate_certificate_observatory_archive_registry_report.build_report(archive_registry_replica, report_id="downloaded-data-observatory-archive-registry-report")
        archive_registry_report_audit = registry_federation_consensus_gate_certificate_observatory_archive_registry_report_audit.audit_report(archive_registry_report)
    return {"federation": federation.summary(), "audit": audit.summary(), "gate": gate.summary(), "matrix": matrix.summary(), "matrix_audit": matrix_audit.summary(), "consensus": consensus.summary(), "consensus_audit": consensus_audit.summary(), "consensus_query": consensus_query.summary(), "consensus_query_rows": [row.to_dict() for row in consensus_query.rows], "consensus_runtime": consensus_runtime.summary(), "consensus_diff": consensus_diff.summary(), "consensus_diff_audit": consensus_diff_audit.summary(), "consensus_history": consensus_history.summary(), "consensus_observatory": consensus_observatory.summary(), "consensus_gate_runtime": gate_runtime.summary(), "consensus_gate": gate_value.summary(), "consensus_gate_audit": gate_audit.summary(), "consensus_gate_query": gate_query.summary(), "consensus_gate_diff": gate_diff.summary(), "consensus_gate_diff_audit": gate_diff_audit.summary(), "consensus_gate_history": gate_history.summary(), "consensus_gate_history_audit": gate_history_audit.summary(), "consensus_gate_observatory": gate_observatory.summary(), "consensus_gate_observatory_audit": gate_observatory_audit.summary(), "consensus_gate_package": gate_package.summary(), "consensus_gate_package_audit": gate_package_audit.summary(), "consensus_gate_package_disk_replay": gate_package_disk_replay, "consensus_gate_certificate_runtime": certificate_runtime.summary(), "consensus_gate_certificate": certificate.summary(), "consensus_gate_certificate_audit": certificate_audit.summary(), "consensus_gate_certificate_query": certificate_query.summary(), "consensus_gate_certificate_query_audit": certificate_query_audit.summary(), "consensus_gate_certificate_query_rows": [row.to_dict() for row in certificate_query.rows], "consensus_gate_certificate_strict": strict_certificate.summary(), "consensus_gate_certificate_strict_audit": strict_certificate_audit.summary(), "consensus_gate_certificate_strict_query": strict_certificate_query.summary(), "consensus_gate_certificate_strict_query_audit": strict_certificate_query_audit.summary(), "consensus_gate_certificate_diff": certificate_diff.summary(), "consensus_gate_certificate_diff_audit": certificate_diff_audit.summary(), "consensus_gate_certificate_history": certificate_history.summary(), "consensus_gate_certificate_history_audit": certificate_history_audit.summary(), "consensus_gate_certificate_history_disk_audit": certificate_history_disk_audit.summary(), "consensus_gate_certificate_history_disk_replay": certificate_history_disk_replay, "consensus_gate_certificate_package": certificate_package.summary(), "consensus_gate_certificate_package_audit": certificate_package_audit.summary(), "consensus_gate_certificate_package_disk_replay": certificate_package_disk_replay, "consensus_gate_certificate_observatory": certificate_observatory.summary(), "consensus_gate_certificate_observatory_audit": certificate_observatory_audit.summary(), "consensus_gate_certificate_observatory_query": certificate_observatory_query.summary(), "consensus_gate_certificate_observatory_query_audit": certificate_observatory_query_audit.summary(), "consensus_gate_certificate_observatory_report": certificate_observatory_report.summary(), "consensus_gate_certificate_observatory_report_audit": certificate_observatory_report_audit.summary(), "consensus_gate_certificate_observatory_package": certificate_observatory_package.summary(), "consensus_gate_certificate_observatory_package_audit": certificate_observatory_package_audit.summary(), "consensus_gate_certificate_observatory_package_disk_replay": certificate_observatory_package_disk_replay, "consensus_gate_certificate_observatory_diff": certificate_observatory_diff.summary(), "consensus_gate_certificate_observatory_diff_audit": certificate_observatory_diff_audit.summary(), "consensus_gate_certificate_observatory_diff_query": certificate_observatory_diff_query.summary(), "consensus_gate_certificate_observatory_diff_query_audit": certificate_observatory_diff_query_audit.summary(), "consensus_gate_certificate_observatory_runtime": certificate_observatory_runtime.summary(), "consensus_gate_certificate_observatory_runtime_audit": certificate_observatory_runtime_audit.summary(), "consensus_gate_certificate_observatory_replay": certificate_observatory_replay.summary(), "consensus_gate_certificate_observatory_replay_audit": certificate_observatory_replay_audit.summary(), "consensus_gate_certificate_observatory_archive": certificate_observatory_archive.summary(), "consensus_gate_certificate_observatory_archive_audit": certificate_observatory_archive_audit.summary(), "consensus_gate_certificate_observatory_archive_query": certificate_observatory_archive_query.summary(), "consensus_gate_certificate_observatory_archive_query_audit": certificate_observatory_archive_query_audit.summary(), "consensus_gate_certificate_observatory_archive_transfer": certificate_observatory_archive_transfer.summary(), "consensus_gate_certificate_observatory_archive_transfer_audit": certificate_observatory_archive_transfer_audit.summary(), "consensus_gate_certificate_observatory_archive_transfer_reassembled": certificate_observatory_archive_transfer_reassembled, "consensus_gate_certificate_observatory_archive_transfer_recovery_before": certificate_observatory_archive_recovery_before.summary(), "consensus_gate_certificate_observatory_archive_transfer_recovery_before_query": certificate_observatory_archive_recovery_before_query.summary(), "consensus_gate_certificate_observatory_archive_transfer_recovery": certificate_observatory_archive_recovery.summary(), "consensus_gate_certificate_observatory_archive_transfer_recovery_audit": certificate_observatory_archive_recovery_audit.summary(), "consensus_gate_certificate_observatory_archive_transfer_recovery_query": certificate_observatory_archive_recovery_query.summary(), "consensus_gate_certificate_observatory_archive_transfer_recovery_disk_replay": certificate_observatory_archive_recovery_disk_replay, "consensus_gate_certificate_observatory_archive_runtime": certificate_observatory_archive_runtime.summary(), "consensus_gate_certificate_observatory_archive_runtime_audit": certificate_observatory_archive_runtime_audit.summary(), "consensus_gate_certificate_observatory_archive_disk_replay": certificate_observatory_archive_disk_replay, "consensus_gate_certificate_observatory_archive_transfer_disk_replay": certificate_observatory_archive_transfer_disk_replay, "consensus_gate_certificate_observatory_archive_registry": archive_registry_replica.summary(), "consensus_gate_certificate_observatory_archive_registry_audit": archive_registry_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_query": archive_registry_query.summary(), "consensus_gate_certificate_observatory_archive_registry_query_audit": archive_registry_query_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_diff": archive_registry_diff.summary(), "consensus_gate_certificate_observatory_archive_registry_diff_audit": archive_registry_diff_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_diff_query": archive_registry_diff_query.summary(), "consensus_gate_certificate_observatory_archive_registry_diff_query_audit": archive_registry_diff_query_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_history": archive_registry_history.summary(), "consensus_gate_certificate_observatory_archive_registry_history_audit": archive_registry_history_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_disk_replay": archive_registry_disk_replay, "consensus_gate_certificate_observatory_archive_registry_history_disk_replay": archive_registry_history_disk_replay, "consensus_gate_certificate_observatory_archive_registry_runtime": archive_registry_runtime.summary(), "consensus_gate_certificate_observatory_archive_registry_runtime_audit": archive_registry_runtime_audit.summary(), "consensus_gate_certificate_observatory_archive_registry_report": archive_registry_report.summary(), "consensus_gate_certificate_observatory_archive_registry_report_audit": archive_registry_report_audit.summary(), "query": query.summary(), "query_rows": [row.to_dict() for row in query.rows], "disk_replay": disk_replay, "consensus_disk_replay": consensus_disk_replay}


def main() -> int:
    args = parse_args()
    report = run(args.primary_registry, args.replica_registry, federation_id=args.federation_id, destination=args.destination, limit=args.limit)
    print(json.dumps(report, indent=2, sort_keys=True, default=list))
    return 0 if report["federation"]["accepted"] and report["gate"]["accepted"] and report["consensus"]["accepted"] and report["consensus_runtime"]["accepted"] and report["consensus_diff_audit"]["accepted"] and report["consensus_gate"]["accepted"] and report["consensus_gate_audit"]["accepted"] and report["consensus_gate_diff_audit"]["accepted"] and report["consensus_gate_history_audit"]["accepted"] and report["consensus_gate_observatory_audit"]["accepted"] and report["consensus_gate_package_audit"]["accepted"] and report["consensus_gate_package_disk_replay"] and report["consensus_gate_certificate"]["accepted"] and report["consensus_gate_certificate_audit"]["accepted"] and report["consensus_gate_certificate_query_audit"]["accepted"] and report["consensus_gate_certificate_diff_audit"]["accepted"] and report["consensus_gate_certificate_history_audit"]["accepted"] and report["consensus_gate_certificate_history_disk_audit"]["accepted"] and report["consensus_gate_certificate_history_disk_replay"] and report["consensus_gate_certificate_package_audit"]["accepted"] and report["consensus_gate_certificate_package_disk_replay"] and report["consensus_gate_certificate_observatory_audit"]["accepted"] and report["consensus_gate_certificate_observatory_query_audit"]["accepted"] and report["consensus_gate_certificate_observatory_report_audit"]["accepted"] and report["consensus_gate_certificate_observatory_package_audit"]["accepted"] and report["consensus_gate_certificate_observatory_package_disk_replay"] and report["consensus_gate_certificate_observatory_diff_audit"]["accepted"] and report["consensus_gate_certificate_observatory_diff_query_audit"]["accepted"] and report["consensus_gate_certificate_observatory_runtime_audit"]["accepted"] and report["consensus_gate_certificate_observatory_replay"]["byte_equal"] and report["consensus_gate_certificate_observatory_replay_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_query_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_transfer_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_transfer_reassembled"] and report["consensus_gate_certificate_observatory_archive_transfer_recovery_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_transfer_recovery_query"]["returned"] == 1 and report["consensus_gate_certificate_observatory_archive_transfer_recovery_disk_replay"] and report["consensus_gate_certificate_observatory_archive_runtime_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_disk_replay"] and report["consensus_gate_certificate_observatory_archive_transfer_disk_replay"] and report["consensus_gate_certificate_observatory_archive_registry_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_query_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_diff_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_diff_query_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_history_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_disk_replay"] and report["consensus_gate_certificate_observatory_archive_registry_history_disk_replay"] and report["consensus_gate_certificate_observatory_archive_registry_runtime_audit"]["accepted"] and report["consensus_gate_certificate_observatory_archive_registry_report_audit"]["accepted"] and not report["consensus_gate_certificate_strict"]["accepted"] and report["consensus_gate_certificate_strict_query_audit"]["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
