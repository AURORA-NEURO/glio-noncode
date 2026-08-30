"""Demonstrate archive transfer recovery from a persisted package.

This example is intentionally offline. It consumes a package directory already
produced by the certificate-observatory package boundary, writes a deterministic
ZIP, simulates an interrupted receiver by retaining every Nth chunk, reports
the missing ranges, resumes from the addressed ZIP, audits the recovery, and
prints only public receipt values.

Example:

    python examples/registry_federation_certificate_observatory_archive_recovery_demo.py \
      --package C:\\data\\certificate-observatory-package \
      --archive C:\\data\\certificate-observatory.zip \
      --partial C:\\data\\certificate-observatory-partial \
      --recovered C:\\data\\certificate-observatory-recovered
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive as archive_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer as transfer_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery as recovery_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_audit as recovery_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_transfer_recovery_query as recovery_query_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="demonstrate certificate-observatory archive transfer recovery")
    parser.add_argument("--package", required=True, type=Path, help="persisted certificate-observatory package directory")
    parser.add_argument("--archive", required=True, type=Path, help="deterministic ZIP archive destination/source")
    parser.add_argument("--partial", required=True, type=Path, help="simulated partial transfer directory")
    parser.add_argument("--recovered", required=True, type=Path, help="completed transfer directory")
    parser.add_argument("--archive-id", default="recovery-demo-archive")
    parser.add_argument("--transfer-id", default="recovery-demo-transfer")
    parser.add_argument("--recovery-id", default="recovery-demo-receipt")
    parser.add_argument("--chunk-size", default=4096, type=int)
    parser.add_argument("--receive-stride", default=2, type=int, help="retain every Nth chunk in the simulated interruption")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def _public_summary(value: object) -> dict[str, object]:
    if hasattr(value, "summary"):
        return getattr(value, "summary")()
    raise TypeError("demo value does not expose a public summary")


def run(args: argparse.Namespace) -> dict[str, object]:
    if args.receive_stride < 1:
        raise ValueError("receive stride must be positive")
    if args.partial.resolve() == args.recovered.resolve():
        raise ValueError("partial and recovered directories must be different")
    package = archive_model.package_model.load_package(args.package)
    archive = archive_model.build_archive(package, archive_id=args.archive_id)
    if args.archive.exists() and not args.overwrite:
        archive_loaded = archive_model.load_archive(args.archive)
        if archive_loaded.content_address != archive.content_address:
            raise ValueError("existing archive does not reproduce the package archive")
    else:
        archive_model.write_archive(archive, args.archive, overwrite=args.overwrite)
        archive_loaded = archive_model.load_archive(args.archive)
    transfer = transfer_model.build_transfer(archive_loaded, transfer_id=args.transfer_id, chunk_size=args.chunk_size)
    partial_assembler = transfer_model.TransferAssembler(transfer)
    for index in range(0, transfer.chunk_count, args.receive_stride):
        partial_assembler.add_chunk(index, transfer_model.chunk_bytes(transfer, index))
    transfer_model.write_partial_transfer(partial_assembler, args.partial, overwrite=args.overwrite)
    before = recovery_model.build_recovery_from_directory(args.partial, recovery_id=args.recovery_id)
    before_audit = recovery_audit_model.audit_recovery(before)
    missing_query = recovery_query_model.query_recovery(before, resource="missing", limit=200)
    resumed = recovery_model.resume_transfer(args.partial, args.archive, destination=args.recovered, recovery_id=args.recovery_id, overwrite=args.overwrite)
    resumed_audit = recovery_audit_model.audit_recovery(resumed)
    summary_query = recovery_query_model.query_recovery(resumed, resource="summary", limit=1)
    loaded_transfer = transfer_model.load_transfer(args.recovered)
    assembled = transfer_model.assemble_archive_bytes(loaded_transfer)
    return {
        "archive": _public_summary(archive_loaded),
        "transfer": _public_summary(transfer),
        "partial_recovery": _public_summary(before),
        "partial_recovery_audit": _public_summary(before_audit),
        "missing_query": missing_query.summary(),
        "resumed_recovery": _public_summary(resumed),
        "resumed_recovery_audit": _public_summary(resumed_audit),
        "resumed_query": summary_query.summary(),
        "recovered_transfer": _public_summary(loaded_transfer),
        "assembled_byte_equal": assembled == archive_model.archive_bytes(archive_loaded),
    }


def main() -> int:
    report = run(parse_args())
    print(json.dumps(report, indent=2, sort_keys=True, default=list))
    return 0 if report["assembled_byte_equal"] and report["partial_recovery_audit"]["accepted"] and report["resumed_recovery_audit"]["accepted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
