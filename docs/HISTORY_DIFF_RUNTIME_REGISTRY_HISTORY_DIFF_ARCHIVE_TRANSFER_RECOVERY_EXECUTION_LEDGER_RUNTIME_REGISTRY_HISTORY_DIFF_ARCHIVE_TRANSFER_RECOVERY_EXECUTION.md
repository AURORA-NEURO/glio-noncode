# Exact history-diff archive transfer recovery execution receipts

This contract records what happened after a path-free archive-transfer recovery plan was created. It is deliberately separate from the recovery plan: the recovery contract says which chunks are missing and what may be done, while this execution contract records which planned actions were applied, left pending, or rejected.

## Contract boundary

The execution quartet is composed of four public, exact-prefixed modules:

1. The execution receipt model creates an immutable, content-addressed receipt over one recovery plan.
2. The execution audit independently replays the receipt's index sets, byte totals, outcome addresses, state, decision, safety, checkpoint, and next-index projections.
3. The execution query projects bounded, deterministic rows from the receipt.
4. The query audit independently replays resource selection, status and index filters, text matching, pagination, row addresses, and receipt linkage.

The public boundary contains identifiers, indexes, byte counts, offsets, sizes, status labels, content addresses, and decisions. It does not expose source paths, source records, private metadata, or archive payload bytes. A content address is calculated from canonical public fields, so an altered receipt cannot retain the original address.

## Outcome state machine

Every recovery action appears exactly once in `outcomes`, in recovery-plan order. Its status is one of:

- `pending`: the action remains available and its reason is `awaiting-chunk`.
- `applied`: the chunk was observed in the matching assembler or explicitly marked applied and its reason is `verified-chunk`.
- `rejected`: the receiver rejected the action and its reason is `receiver-rejected`.

The receipt derives its state from those outcomes:

| Outcome condition | State | Decision | Safe to continue | Safe to assemble |
| --- | --- | ---: | ---: | ---: |
| no applied or rejected outcomes | `planned` | `resume` | yes | no |
| at least one applied and pending remains | `in_progress` | `resume` | yes | no |
| no pending or rejected outcomes | `complete` | `assemble` | yes | yes |
| any rejected outcome | `blocked` | `block` | no | no |

The state is replayed, not caller-supplied. `next_index` is the lowest pending index, then the lowest rejected index, or `-1` when the plan is complete. This makes a receipt useful to a resumable receiver and to an operator reviewing why assembly is or is not safe.

## Conservation rules

The model rejects a receipt unless all of the following hold:

- the base received indexes and planned indexes partition the transfer universe;
- applied, pending, and rejected indexes partition the planned indexes;
- current received indexes equal base indexes plus applied indexes;
- current missing indexes equal pending indexes plus rejected indexes;
- every outcome index is present once and remains in plan order;
- planned bytes equal applied bytes plus pending bytes plus rejected bytes;
- current received bytes equal recovery received bytes plus applied bytes;
- current received bytes plus current remaining bytes equal the archive size;
- action counts and status counts replay their corresponding sets;
- the state, decision, safety flags, and next index agree with the outcome partition.

This permits partial progress without pretending that a pending or rejected chunk has been received. It also provides a compact audit trail for complete, in-progress, planned, and blocked decisions.

## Builder modes

`build_execution` accepts explicit applied and rejected index sets. It only accepts indexes already present in the recovery plan and rejects overlap. This is useful for a verified external execution record.

`build_execution_from_assembler` derives applied indexes from a typed transfer assembler. It verifies that the assembler belongs to the recovery transfer and that any additional received indexes are planned recovery indexes. `build_execution_from_directory` applies the same checks after loading a persisted partial receiver directory. Both paths default to a checkpointed receipt because the observed receiver state is durable input.

The resulting receipt includes exact linkage to recovery, transfer, and archive addresses. Outcome rows retain the action address, chunk address, offset, size, status, reason, and their own content address. There is no mutable execution counter outside the receipt's canonical projection.

## Audit and query surfaces

The independent execution audit has 18 checks:

`version`, `boundary`, `execution-address`, `recovery-linkage`, `transfer-linkage`, `plan-conservation`, `current-index-conservation`, `outcome-order`, `outcome-addresses`, `status-conservation`, `byte-conservation`, `state-replay`, `decision-replay`, `safety-replay`, `checkpoint-type`, `next-index`, `public-boundary`, and `mapping-round-trip`.

The bounded query has nine resources, kept in contract order:

`summary`, `outcomes`, `addresses`, `applied`, `pending`, `rejected`, `state`, `decisions`, and `bounds`.

Queries can additionally constrain status, chunk index, free text, offset, and limit. Rows are addressed and paginated deterministically. The independent query audit has 12 checks covering version, boundary, resource order, filter replay, count replay, row order, row addresses, row membership, resource semantics, execution linkage, public-boundary validation, and mapping round-trip.

## Projections and interfaces

The model exposes canonical JSON, CSV outcome rows, and Markdown review output. CLI commands expose receipt creation, verification, audit, query, query audit, and twelve schema/capability documents. The local HTTP API mirrors those operations under the execution route. Public inventory registration includes the outcome, receipt, audit, query-row, query, and query-audit schema/capability surfaces.

All serialized forms are reconstructed through strict typed mapping validation. Unknown fields, missing fields, duplicate indexes, invalid statuses, wrong address namespaces, byte drift, and altered content addresses are rejected.

## Downloaded-ZIP demonstration

The demonstration consumes the supplied downloaded ZIP as real input. Its canonical archive is 5,183 bytes in six 1,024-byte transfer chunks, with chunks `0` and `5` already received and chunks `1` through `4` planned for recovery.

The persisted execution receipts show three meaningful branches over the same recovery plan:

- in-progress: chunk `1` applied, chunks `2`, `3`, and `4` pending; 2,111 current received bytes and 3,072 remaining bytes;
- complete: all four planned chunks applied; 5,183 current received bytes and zero remaining bytes, with `assemble` permitted;
- blocked: chunk `1` rejected; 1,087 current received bytes and 4,096 remaining bytes, with `block` required.

Each branch is reloaded from canonical JSON, audited, and included in the summary artifact. The full query and query-audit projections are also persisted in JSON, CSV, and Markdown so the same evidence can be inspected without reopening the source archive.

## Verification examples

The focused test exercises the typed builders, conservation invariants, negative controls, canonical reload, CLI routes, local HTTP routes, all twelve schema/capability routes, and public inventory. The downloaded-data demo is the operational path: it reads the ZIP, creates the recovery plan, derives execution receipts, writes the projections, reloads them, and reports release readiness only when every required check is true.

The contract is intentionally value-free. It proves transfer execution state and assembly safety while keeping archive content outside the public execution surface.
