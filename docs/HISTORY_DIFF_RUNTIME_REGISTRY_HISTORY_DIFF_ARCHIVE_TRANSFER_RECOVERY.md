# Exact history-diff archive transfer recovery

The exact history-diff archive transfer recovery layer turns a persisted
receiver directory into a deterministic, resumable recovery plan. It is the
next boundary above the exact archive and addressed transfer: it reports what
has arrived, what remains, and the exact addressed actions required to finish
the transfer.

## Contract

The importable implementation uses the exact-prefixed modules
`glio_noncode.exact_history_diff_archive_transfer_recovery_execution_runtime_registry_history_diff_archive_transfer_recovery`
and its `_audit`, `_query`, and `_query_audit` companions. The shorter recovery
modules remain available for the earlier compatibility boundary; the public
command and HTTP names remain fully explicit under the exact archive transfer
boundary.

A recovery snapshot contains the transfer and archive addresses, archive and
chunk bounds, received and missing indexes, received and remaining byte
totals, an ordered action for every missing chunk, state, decision, safety,
checkpoint, next-index, and a content address. Recovery actions contain only
the missing chunk index, byte range, chunk address, and action address; they do
not contain payload bytes or source paths.

The builder accepts an in-memory transfer assembler or a persisted complete or
partial transfer directory. Partial state produces `state: partial`,
`decision: resume`, `safe_to_resume: true`, and one addressed action per
missing chunk. Complete state produces `state: complete`, `decision: assemble`,
no actions, and `next_index: -1`. Replaying the same receiver directory is
deterministic and preserves byte and index conservation.

## Verification and query projections

The independent recovery audit has 17 checks covering version and boundary,
transfer and archive linkage, index and byte conservation, action coverage and
addresses, action ranges, state and decision replay, next-index behavior,
checkpoint type, public-boundary safety, mapping round trips, and deterministic
plan replay.

The bounded query exposes `summary`, `actions`, `received`, `missing`,
`state`, `progress`, and `bounds` resources. It supports resource, chunk
index, state, received-state, text, offset, and limit filters. Its independent
query audit has 12 checks for version/boundary, resource order, filter replay,
counts, row order and addresses, membership, resource semantics, recovery
linkage, public safety, and mapping round trips.

## CLI and HTTP

The exact command appends `-recovery` to the exact archive transfer command.
It supports the base builder, `-verify`, `-audit`, `-query`, `-query-audit`,
and 12 schema/capability commands: action schema, recovery schema and
capabilities, audit check/schema/capabilities, query row/schema/capabilities,
and query-audit check/schema/capabilities.

The local HTTP API mirrors the lifecycle at the exact transfer `/recovery`
route. The operational routes are `/recovery`, `/recovery/verify`,
`/recovery/audit`, `/recovery/query`, and `/recovery/query/audit`; nested
schema and capability routes expose the same typed contracts.

## Real downloaded-data demonstration

Run the demo against the supplied ZIP:

    python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
        C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
        artifacts/exact-history-diff-archive-transfer-recovery-execution-runtime-registry-history-diff-archive-transfer-recovery-real-downloaded-data-demo

The verified run reads 25 catalog members and produces the exact 5,077-byte
archive and five 1,024-byte transfer chunks. The persisted partial receiver
contains chunk indexes 0 and 4, so recovery reports missing indexes 1, 2, and
3, three addressed actions, 2,005 received bytes, 3,072 remaining bytes, and
`next_index: 1`. All 17 recovery checks and all 12 recovery-query audit
checks pass. A complete recovery replay reports `complete` and `assemble`,
and all recovery artifacts reload with the same content addresses.
