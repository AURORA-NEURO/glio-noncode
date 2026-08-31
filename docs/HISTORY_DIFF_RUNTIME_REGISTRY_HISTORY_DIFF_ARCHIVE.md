# Exact history-diff runtime-registry history-diff archive

This module is the portable handoff for an exact baseline/candidate history
comparison. It receives a verified four-file history-diff package and emits a
single deterministic ZIP envelope that can be moved, reloaded, queried, and
audited without the original downloaded archive.

## Contract

The ZIP has exactly five members in this order:

1. `manifest.json`
2. `history-diff/manifest.json`
3. `history-diff/diff.json`
4. `history-diff/items.json`
5. `history-diff/summary.json`

The outer manifest records the history-diff identity and address, exact member
vocabulary, four byte receipts, archive size, and archive address. ZIP entries
use fixed epoch metadata, regular-file permissions, DEFLATE level 9, empty
comments, and canonical JSON. Archive addressing excludes only the measured
ZIP size so the address remains stable while the physical byte count is still
verified.

## Verification and queries

Loading is fail-closed. The verifier rejects missing, duplicate, reordered,
absolute, traversal, backslash, symlink, encrypted, commented, oversized,
non-canonical, or tampered members. It rehydrates the nested history diff,
replays all four projections, checks every receipt, verifies the outer manifest
address, and confirms byte-for-byte deterministic regeneration. Writes are
atomic and require explicit overwrite for an existing destination.

The independent archive audit has 18 checks covering identity, boundaries,
ordering, receipts, linkage, nested replay, size, ZIP safety, deterministic
bytes, public-boundary safety, and mapping/byte round trips. The archive query
has eight bounded resources: `summary`, `manifest`, `artifacts`, `diff`,
`items`, `changes`, `addresses`, and `bounds`. It supports key/text filtering
and deterministic pagination. The independent query audit has 13 checks for
filter replay, counts, row order and addresses, resource membership, bounds,
linkage, and public safety.

## CLI and HTTP

The CLI appends `-archive` to the exact history-diff command. The lifecycle is
available as build, `-verify`, `-audit`, `-query`, `-query-audit`, schema, and
capability commands. The local HTTP API mirrors the same lifecycle at the
history-diff `/archive` route, including schema and capability projections.

All public results retain labels, decisions, counts, and content addresses.
They do not publish local source paths, downloaded records, raw payload bytes,
or private attribution fields.

## Real downloaded-data demo

Run the reproducible demo with the supplied ZIP:

```text
python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
  artifacts/history-diff-archive-transfer-recovery-execution-runtime-registry-history-diff-archive-real-downloaded-data-demo
```

The run builds a 25-member catalog and 160 review actions, creates the
baseline/candidate history diff, writes the archive package, reloads it, and
emits JSON/CSV/Markdown evidence. The observed archive is 4,783 bytes with
four embedded artifacts; all 18 archive checks pass, all 48 archive-query rows
replay, and all 13 query-audit checks pass. The summary reports the stable
content address and `release_ready: true`.
