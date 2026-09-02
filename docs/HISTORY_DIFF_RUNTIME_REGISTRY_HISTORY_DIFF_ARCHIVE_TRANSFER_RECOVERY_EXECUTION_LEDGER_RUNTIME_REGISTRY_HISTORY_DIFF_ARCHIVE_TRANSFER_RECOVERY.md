# Exact execution-ledger archive-transfer recovery

The exact execution-ledger runtime-registry history-diff archive transfer
recovery layer turns a complete or persisted partial receiver into a
deterministic checkpoint plan. It makes continuation explicit: every missing
chunk has one addressed action, every received and remaining byte is conserved,
and the projected state selects resume or assemble.

## Contract

The implementation is split into four exact-prefixed modules:

`glio_noncode.exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery`

`glio_noncode.exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_audit`

`glio_noncode.exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_query`

`glio_noncode.exact_history_diff_archive_transfer_recovery_execution_ledger_runtime_registry_history_diff_archive_transfer_recovery_query_audit`

A recovery snapshot retains the transfer and archive addresses, archive and
chunk bounds, received and missing indexes, received and remaining byte totals,
an ordered action for every missing chunk, state, decision, safety,
checkpoint, next-index, and a content address. Actions contain only a chunk
index, byte range, chunk address, and action address. Payload bytes and local
source paths never enter the public projection.

The builder accepts a transfer value, an in-memory assembler, or a persisted
complete/partial receiver directory. Complete input yields `complete`,
`assemble`, zero actions, and `next_index: -1`. Partial input yields
`partial`, `resume`, `safe_to_resume: true`, one action per missing chunk, and
the next safe index after the received prefix. Replaying the same checkpoint
produces the same addresses and byte/index partitions.

## Verification and query projections

The independent recovery audit has 18 checks covering version and boundary,
transfer and archive linkage, index and byte conservation, action coverage and
addresses, action ranges, state and decision replay, next-index behavior,
checkpoint typing, safety, public-boundary constraints, mapping round trips,
and deterministic plan replay.

The bounded query exposes nine resources: `summary`, `actions`, `addresses`,
`bounds`, `received`, `missing`, `state`, `decisions`, and `latest`. It supports
resource, key, text, offset, and limit filters with deterministic pagination.
Its independent query audit has 12 checks for ordering, filtering, counts, row
addresses, membership, resource semantics, recovery linkage, public safety,
and mapping round trips.

## CLI and HTTP

The exact command appends `-recovery` to the exact archive-transfer command. It
supports the base builder, `-verify`, `-audit`, `-query`, `-query-audit`, and
12 schema/capability commands for actions, recovery, audit checks, audits,
query rows, queries, query-audit checks, and query audits.

The local HTTP API mirrors the lifecycle at the exact transfer `/recovery`
route. Operational routes are `/recovery`, `/recovery/verify`,
`/recovery/audit`, `/recovery/query`, and `/recovery/query/audit`; nested
schema and capability routes expose the same typed contracts.

## Real downloaded-data demonstration

Run the demo against the supplied ZIP:

    python examples/downloaded_data_contract_resolution_history_diff_policy_demo.py \
        C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip \
        artifacts/real-downloaded-data-demo-recovery

The verified run reads 25 catalog members and produces the exact 5,183-byte
archive split into six 1,024-byte chunks. The complete recovery replays as
`complete` and `assemble` with zero actions. The persisted partial checkpoint
contains chunk indexes 0 and 5, reports missing indexes 1 through 4, emits
four addressed resume actions, conserves 1,087 received bytes plus 4,096
remaining bytes, and reloads with the same content address. Both recovery
audits pass 18/18 checks and both query audits pass 12/12 checks.
