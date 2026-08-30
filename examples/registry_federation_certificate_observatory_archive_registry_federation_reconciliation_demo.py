"""Demonstrate evidence-preserving registry reconciliation on downloaded inputs.

The inputs are independently downloaded archive-registry directories or public
registry JSON documents.  The example builds a federation, calculates quorum
evidence, resolves every entry, derives a per-peer action matrix, audits each
projection, and optionally writes the exact nine-file runtime handoff.  Source
paths stay at the command boundary; the printed result contains only public
labels, counts, evidence addresses, and bounded operation detail.

Example:

    python examples/registry_federation_certificate_observatory_archive_registry_federation_reconciliation_demo.py \
      --input C:\\data\\primary-registry \
      --input C:\\data\\replica-registry \
      --peer-id primary --peer-id replica \
      --quorum 2 \
      --destination C:\\data\\reconciliation-runtime

The source directories must be archive-registry downloads that already pass
their own registry contracts.  This example does not fetch, modify, or merge
source registries.  A divergent or missing peer is retained as review or
blocked evidence and produces a non-mutating plan rather than an automatic
overwrite.
"""

# ruff: noqa: E501, I001, UP035

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_audit as plan_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_query as plan_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_plan_query_audit as plan_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_reconciliation_runtime_audit as runtime_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_query as resolution_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_resolution_query_audit as resolution_query_audit_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="demonstrate archive-registry federation reconciliation on downloaded registries")
    parser.add_argument("--input", action="append", required=True, type=Path, help="archive-registry directory or public registry JSON")
    parser.add_argument("--peer-id", action="append", default=None, help="stable peer ID for each input")
    parser.add_argument("--federation-id", default="consensus-certificate-observatory-archive-registry-federation")
    parser.add_argument("--runtime-id", default=runtime_model.DEFAULT_RUNTIME_ID)
    parser.add_argument("--quorum", default=None, type=int, help="minimum peer count for a selected archive address")
    parser.add_argument("--destination", default=None, type=Path, help="optional exact nine-file runtime destination")
    parser.add_argument("--limit", default=50, type=int, help="maximum rows shown in each bounded query")
    return parser.parse_args()


def _summary(value: Any) -> Any:
    return value.summary() if hasattr(value, "summary") else value


def _operation_public(operation: Any) -> dict[str, Any]:
    """Keep the operation preview useful while excluding source paths."""

    return {
        "ordinal": operation.ordinal,
        "peer_id": operation.peer_id,
        "registry_id": operation.registry_id,
        "entry_id": operation.entry_id,
        "package_id": operation.package_id,
        "source_state": operation.source_state,
        "action": operation.action,
        "status": operation.status,
        "priority": operation.priority,
        "observed_archive_address": operation.observed_archive_address,
        "desired_archive_address": operation.desired_archive_address,
        "requires_confirmation": operation.requires_confirmation,
        "reason": operation.reason,
        "evidence_addresses": operation.evidence_addresses,
    }


def _resolution_public(item: Any) -> dict[str, Any]:
    return {
        "ordinal": item.ordinal,
        "entry_id": item.entry_id,
        "package_id": item.package_id,
        "state": item.state,
        "action": item.action,
        "selected_archive_address": item.selected_archive_address,
        "candidate_addresses": item.candidate_addresses,
        "supporting_peer_ids": item.supporting_peer_ids,
        "missing_peer_ids": item.missing_peer_ids,
        "dissenting_peer_ids": item.dissenting_peer_ids,
        "required_quorum": item.required_quorum,
        "observed_peer_count": item.observed_peer_count,
        "presence_count": item.presence_count,
        "evidence_addresses": item.evidence_addresses,
        "rationale": item.rationale,
        "content_address": item.content_address,
    }


def run(
    inputs: Sequence[Path],
    *,
    peer_ids: Sequence[str] | None = None,
    federation_id: str = "consensus-certificate-observatory-archive-registry-federation",
    runtime_id: str = runtime_model.DEFAULT_RUNTIME_ID,
    quorum: int | None = None,
    destination: Path | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Run all reconciliation projections and return a path-free public view."""

    runtime = runtime_model.run_runtime(
        tuple(inputs),
        peer_ids=peer_ids,
        federation_id=federation_id,
        runtime_id=runtime_id,
        quorum=quorum,
        destination=destination,
    )
    resolution_query = resolution_query_model.query_resolution(
        runtime.resolution,
        resources=resolution_query_model.RESOURCES,
        limit=limit,
    )
    plan_query = plan_query_model.query_plan(
        runtime.plan,
        resources=plan_query_model.RESOURCES,
        limit=limit,
    )
    runtime_audit = runtime_audit_model.audit_runtime(runtime)
    resolution_query_audit = resolution_query_audit_model.audit_query(resolution_query)
    plan_query_audit = plan_query_audit_model.audit_query(plan_query)
    plan_audit = plan_audit_model.audit_plan(runtime.plan)
    return {
        "runtime": _summary(runtime),
        "runtime_audit": _summary(runtime_audit),
        "resolution": _summary(runtime.resolution),
        "resolution_items": tuple(_resolution_public(item) for item in runtime.resolution.items[:limit]),
        "resolution_query": _summary(resolution_query),
        "resolution_query_audit": _summary(resolution_query_audit),
        "reconciliation_plan": _summary(runtime.plan),
        "plan_operations": tuple(_operation_public(item) for item in runtime.plan.operations[:limit]),
        "plan_query": _summary(plan_query),
        "plan_query_audit": _summary(plan_query_audit),
        "plan_audit": _summary(plan_audit),
        "persisted_files": runtime_model.FILES if destination is not None else (),
    }


def main() -> int:
    args = parse_args()
    result = run(
        args.input,
        peer_ids=args.peer_id,
        federation_id=args.federation_id,
        runtime_id=args.runtime_id,
        quorum=args.quorum,
        destination=args.destination,
        limit=args.limit,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=list))
    return 0 if result["runtime"]["accepted"] and result["runtime"]["release_ready"] and result["runtime_audit"]["accepted"] and result["resolution_query_audit"]["accepted"] and result["plan_query_audit"]["accepted"] and result["plan_audit"]["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
