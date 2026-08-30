"""Demonstrate the certificate-observatory archive registry on downloaded inputs.

The inputs are package directories, archive ZIPs, or public package/archive
JSON documents already downloaded by the operator.  The example keeps source
paths at the edge of the program and prints only public, content-addressed
summaries.  With two inputs it also shows a baseline-to-candidate diff and a
two-snapshot append-only history.

Example:

    python examples/registry_federation_certificate_observatory_archive_registry_demo.py \
      --input C:\\data\\primary-observatory-package \
      --input C:\\data\\replica-observatory-package \
      --entry-id primary-entry --entry-id replica-entry \
      --archive-id primary-archive --archive-id replica-archive \
      --destination C:\\data\\observatory-archive-registry
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Sequence

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry as registry_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_audit as registry_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query as diff_query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_diff_query_audit as diff_query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report as report_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_report_audit as report_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime as runtime_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_runtime_audit as runtime_audit_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="demonstrate archive-registry processing on downloaded observatory packages")
    parser.add_argument("--input", action="append", required=True, type=Path, help="package directory, archive ZIP, or public package/archive JSON")
    parser.add_argument("--entry-id", action="append", default=None, help="stable entry ID for each input")
    parser.add_argument("--archive-id", action="append", default=None, help="stable archive ID for each input")
    parser.add_argument("--registry-id", default=registry_model.DEFAULT_REGISTRY_ID)
    parser.add_argument("--runtime-id", default=runtime_model.DEFAULT_RUNTIME_ID)
    parser.add_argument("--history-id", default=history_model.DEFAULT_HISTORY_ID)
    parser.add_argument("--destination", default=None, type=Path, help="optional exact five-file registry destination")
    parser.add_argument("--history-destination", default=None, type=Path, help="optional exact four-file history destination")
    parser.add_argument("--limit", default=50, type=int)
    return parser.parse_args()


def _selected_ids(inputs: Sequence[Path], values: Sequence[str] | None, prefix: str) -> tuple[str, ...]:
    if values is not None:
        selected = tuple(values)
        if len(selected) != len(inputs):
            raise ValueError(f"{prefix} count must match --input count")
        return selected
    return tuple(f"{prefix}-{index:03d}" for index in range(1, len(inputs) + 1))


def _summary(value: object) -> object:
    return value.summary() if hasattr(value, "summary") else value


def run(inputs: Sequence[Path], *, entry_ids: Sequence[str] | None = None, archive_ids: Sequence[str] | None = None, registry_id: str = registry_model.DEFAULT_REGISTRY_ID, runtime_id: str = runtime_model.DEFAULT_RUNTIME_ID, history_id: str = history_model.DEFAULT_HISTORY_ID, destination: Path | None = None, history_destination: Path | None = None, limit: int = 50) -> dict[str, object]:
    """Run the complete registry path and return path-free public summaries."""

    sources = tuple(inputs)
    if not sources:
        raise ValueError("at least one --input is required")
    selected_entry_ids = _selected_ids(sources, entry_ids, "entry")
    selected_archive_ids = _selected_ids(sources, archive_ids, "archive")

    runtime = runtime_model.run_runtime(sources, runtime_id=runtime_id, registry_id=registry_id, entry_ids=selected_entry_ids, archive_ids=selected_archive_ids, query_resources=("summary", "entries", "accepted", "held", "packages"), limit=limit, destination=destination, overwrite=False)
    archives = tuple(runtime_model.load_archive_input(source, archive_id=selected_archive_ids[index]) for index, source in enumerate(sources))
    registry = registry_model.build_registry_from_archives(archives, entry_ids=selected_entry_ids, registry_id=registry_id)
    registry_audit = registry_audit_model.audit_registry(registry)
    registry_query = query_model.query_registry(registry, resources=("summary", "entries", "accepted", "held", "packages"), limit=limit)
    registry_query_audit = query_audit_model.audit_query(registry_query, registry)
    report = report_model.build_report(registry, report_id=registry_id + "-health")
    report_audit = report_audit_model.audit_report(report)

    with tempfile.TemporaryDirectory(prefix="glio-noncode-registry-demo-") as temporary:
        scratch = Path(temporary)
        baseline = registry_model.build_registry_from_archives((archives[0],), entry_ids=(selected_entry_ids[0],), registry_id=registry_id + "-baseline")
        diff = diff_model.build_diff(baseline, registry, diff_id=registry_id + "-transition")
        diff_audit = diff_audit_model.audit_diff(diff, baseline, registry)
        diff_query = diff_query_model.query_diff(diff, resources=("summary", "items", "added", "removed", "changed"), limit=limit)
        diff_query_audit = diff_query_audit_model.audit_query(diff_query, diff)
        history = history_model.build_history((baseline, registry), history_id=history_id) if len(sources) > 1 else history_model.build_history((registry,), history_id=history_id)
        history_audit = history_audit_model.audit_history(history, (baseline, registry) if len(sources) > 1 else (registry,))
        history_disk_replay = False
        if history_destination is not None:
            history_model.write_history(history, history_destination, overwrite=False)
            history_disk_replay = history_model.load_history(history_destination).content_address == history.content_address
        registry_disk_replay = False
        if destination is not None:
            registry_disk_replay = registry_model.load_registry(destination).content_address == registry.content_address
        else:
            replay_target = scratch / "registry"
            registry_model.write_registry(registry, replay_target)
            registry_disk_replay = registry_model.load_registry(replay_target).content_address == registry.content_address

    return {
        "runtime": _summary(runtime),
        "registry": registry.summary(),
        "registry_audit": registry_audit.summary(),
        "registry_query": registry_query.summary(),
        "registry_query_audit": registry_query_audit.summary(),
        "report": report.summary(),
        "report_audit": report_audit.summary(),
        "diff": diff.summary(),
        "diff_audit": diff_audit.summary(),
        "diff_query": diff_query.summary(),
        "diff_query_audit": diff_query_audit.summary(),
        "history": history.summary(),
        "history_audit": history_audit.summary(),
        "registry_disk_replay": registry_disk_replay,
        "history_disk_replay": history_disk_replay,
    }


def main() -> int:
    args = parse_args()
    result = run(args.input, entry_ids=args.entry_id, archive_ids=args.archive_id, registry_id=args.registry_id, runtime_id=args.runtime_id, history_id=args.history_id, destination=args.destination, history_destination=args.history_destination, limit=args.limit)
    print(json.dumps(result, indent=2, sort_keys=True, default=list))
    return 0 if result["runtime"]["accepted"] and result["registry_audit"]["accepted"] and result["registry_query_audit"]["accepted"] and result["report_audit"]["accepted"] and result["diff_audit"]["accepted"] and result["diff_query_audit"]["accepted"] and result["history_audit"]["accepted"] and result["registry_disk_replay"] and (args.history_destination is None or result["history_disk_replay"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
