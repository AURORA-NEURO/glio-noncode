"""Demonstrate federated reconciliation of downloaded archive registries.

This program consumes canonical archive-registry directories or public registry
JSON documents already downloaded by an operator.  It does not merge the
registries, infer private provenance, or print source paths.  Instead it keeps
each peer's registry address and entry evidence, classifies every entry as
consistent, missing, or divergent, evaluates quorum, emits a readiness report,
and optionally persists an exact six-file runtime for later replay.

Example with two persisted registry downloads::

    python examples/registry_federation_certificate_observatory_archive_registry_federation_demo.py \
      --input C:\\data\\primary-registry \
      --input C:\\data\\replica-registry \
      --peer-id primary \
      --peer-id replica \
      --quorum 2 \
      --destination C:\\data\\federation-runtime

The accepted output is a public JSON summary.  The input paths remain CLI
arguments only; they are never fields in a returned model.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_audit as federation_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_consensus_audit as consensus_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_query as diff_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_report_audit as report_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime_audit as runtime_audit_model


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse only bounded, explicit inputs for the downloaded-data demo."""

    parser = argparse.ArgumentParser(description="reconcile downloaded archive registries without flattening peer evidence")
    parser.add_argument("--input", action="append", required=True, type=Path, help="canonical archive registry directory or public registry JSON; repeat for each peer")
    parser.add_argument("--peer-id", action="append", default=None, help="public peer label; repeat once per input")
    parser.add_argument("--federation-id", default=federation_model.DEFAULT_FEDERATION_ID)
    parser.add_argument("--runtime-id", default=runtime_model.DEFAULT_RUNTIME_ID)
    parser.add_argument("--quorum", default=None, type=int, help="minimum peer support; defaults to strict majority")
    parser.add_argument("--limit", default=50, type=int, help="bounded rows in the printed evidence summaries")
    parser.add_argument("--destination", default=None, type=Path, help="optional exact six-file runtime destination")
    return parser.parse_args(argv)


def _summary(value: Any) -> Any:
    """Return a model's public summary without carrying input paths forward."""

    return value.summary() if hasattr(value, "summary") else value


def _peer_ids(inputs: Sequence[Path], values: Sequence[str] | None) -> tuple[str, ...] | None:
    """Validate explicit peer labels before any downloaded input is opened."""

    if values is None:
        return None
    selected = tuple(values)
    if len(selected) != len(inputs):
        raise ValueError("--peer-id count must match --input count")
    return selected


def run(
    inputs: Sequence[Path],
    *,
    peer_ids: Sequence[str] | None = None,
    federation_id: str = federation_model.DEFAULT_FEDERATION_ID,
    runtime_id: str = runtime_model.DEFAULT_RUNTIME_ID,
    quorum: int | None = None,
    limit: int = 50,
    destination: Path | None = None,
) -> dict[str, Any]:
    """Run the complete federation graph over real persisted registry inputs.

    The returned dictionary is deliberately made entirely of summaries.  This
    keeps the example useful at a shell prompt while preserving full typed
    runtime artifacts under ``destination`` when persistence is requested.
    """

    sources = tuple(inputs)
    if not sources:
        raise ValueError("at least one --input is required")
    if limit < 1:
        raise ValueError("--limit must be positive")
    selected_peer_ids = _peer_ids(sources, peer_ids)
    runtime = runtime_model.run_runtime(
        sources,
        peer_ids=selected_peer_ids,
        federation_id=federation_id,
        runtime_id=runtime_id,
        quorum=quorum,
        destination=destination,
        overwrite=False,
    )
    federation = runtime.federation
    federation_audit = federation_audit_model.audit_federation(federation)
    query = query_model.query_federation(federation, resources=query_model.RESOURCES, limit=limit)
    query_audit = query_audit_model.audit_query(query)
    consensus = runtime.consensus
    consensus_audit = consensus_audit_model.audit_consensus(consensus)
    report = report_model.build_report(
        federation,
        consensus=consensus,
        federation_audit=federation_audit,
        consensus_audit=consensus_audit,
    )
    report_audit = report_audit_model.audit_report(report)
    runtime_audit = runtime_audit_model.audit_runtime(runtime)

    registries = tuple(runtime_model.load_registry_input(source) for source in sources)
    baseline = federation_model.build_federation(
        (registries[0],),
        peer_ids=(selected_peer_ids[0] if selected_peer_ids else "baseline",),
        federation_id=federation_id + "-baseline",
    )
    candidate = federation_model.build_federation(
        (registries[-1],),
        peer_ids=(selected_peer_ids[-1] if selected_peer_ids else "candidate",),
        federation_id=federation_id + "-candidate",
    )
    transition = diff_model.build_diff(baseline, candidate, diff_id=federation_id + "-transition")
    transition_audit = diff_audit_model.audit_diff(transition)
    transition_query = diff_query_model.query_diff(transition, resources=diff_query_model.RESOURCES, limit=limit)
    transition_query_audit = diff_query_audit_model.audit_query(transition_query)

    replayed = False
    with tempfile.TemporaryDirectory(prefix="glio-noncode-federation-demo-") as scratch:
        replay_target = destination or (Path(scratch) / "runtime")
        if destination is None:
            runtime_model.write_runtime(runtime, replay_target)
        replayed = runtime_model.load_runtime(replay_target).content_address == runtime.content_address

    return {
        "runtime": _summary(runtime),
        "federation": _summary(federation),
        "federation_audit": _summary(federation_audit),
        "query": _summary(query),
        "query_audit": _summary(query_audit),
        "consensus": _summary(consensus),
        "consensus_audit": _summary(consensus_audit),
        "report": _summary(report),
        "report_audit": _summary(report_audit),
        "transition": _summary(transition),
        "transition_audit": _summary(transition_audit),
        "transition_query": _summary(transition_query),
        "transition_query_audit": _summary(transition_query_audit),
        "runtime_audit": _summary(runtime_audit),
        "disk_replay": replayed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print the public demo receipt and return a shell-friendly status."""

    args = parse_args(argv)
    result = run(
        args.input,
        peer_ids=args.peer_id,
        federation_id=args.federation_id,
        runtime_id=args.runtime_id,
        quorum=args.quorum,
        limit=args.limit,
        destination=args.destination,
    )
    print(json.dumps(result, indent=2, sort_keys=True, default=list))
    accepted = (
        result["runtime"]["accepted"]
        and result["federation_audit"]["accepted"]
        and result["query_audit"]["accepted"]
        and result["consensus_audit"]["accepted"]
        and result["report_audit"]["accepted"]
        and result["transition_audit"]["accepted"]
        and result["transition_query_audit"]["accepted"]
        and result["runtime_audit"]["accepted"]
        and result["disk_replay"]
    )
    return 0 if accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())
