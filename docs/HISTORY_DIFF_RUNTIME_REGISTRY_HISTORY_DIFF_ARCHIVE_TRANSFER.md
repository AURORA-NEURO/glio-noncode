# Exact history-diff runtime-registry addressed transfer

This module transports the exact history-diff archive as a resumable, addressed
chunk stream. It is intentionally layered above the deterministic archive:
the archive remains the integrity boundary, while the transfer adds receiver
progress, partial persistence, and out-of-order delivery.

## Contract

A transfer contains an immutable archive address, archive size, fixed chunk
size, chunk count, and ordered chunk receipts. Chunk addresses are derived
from their bytes and every chunk has an explicit index, offset, and length.
The public transfer manifest contains no chunk payload bytes.

The receiver supports complete and partial directories. Complete directories
contain the manifest and every chunk; partial directories contain the manifest
and only received chunks. Writes are atomic and existing destinations require
explicit overwrite. Duplicate chunk receipt is idempotent, delivery order is
irrelevant, and assembly requires every expected chunk before the nested
archive is verified.

## Verification and queries

Transfer verification checks archive linkage, chunk ordering, contiguous
offsets, lengths, receipts, size conservation, chunk bounds, transfer
addressing, mapping round trips, public-boundary safety, and deterministic
replay. The independent transfer audit has 18 checks.

The receiver-aware query exposes bounded summary, archive, chunks, received,
missing, progress, and bounds resources. It supports chunk index, offset,
size, address, received-state, text, and pagination filters. The independent
query audit has 12 checks for filter replay, counts, stable ordering, row
addresses, linkage, bounds, and public safety.

## CLI and HTTP

The CLI appends -transfer to the exact history-diff archive command. The
lifecycle includes build, -partial, -verify, -manifest, -progress,
-assemble, -audit, -query, -query-audit, and the complete schema and
capability projections.

The local HTTP API mirrors the lifecycle at the exact archive /transfer
route, including /partial, /verify, /manifest, /progress, /assemble,
/audit, /query, /query/audit, and schema and capability routes.

Public projections retain labels, counts, states, receipts, and content
addresses. They do not expose source paths, source records, chunk bytes,
private metadata, agent attribution, or language metadata.

## Real downloaded-data demo

Run the reproducible demo with the supplied ZIP:

    python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py
        C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip
        artifacts/history-diff-archive-transfer-recovery-execution-runtime-registry-history-diff-archive-transfer-real-downloaded-data-demo

The observed run reads 25 catalog members and produces 160 review actions.
The exact 4,783-byte archive is split into five 1,024-byte chunks. The
complete transfer reloads with the same address, the partial receiver retains
chunk indices 0 and 4 while 1, 2, and 3 remain missing, all 18 transfer checks
pass, all 14 transfer-query rows replay, all 12 query-audit checks pass, and
reassembly produces the original archive address with release_ready: true.
