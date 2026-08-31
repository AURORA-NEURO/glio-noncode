# Downloaded-data history-observatory archive transfer

The history-observatory archive transfer is the resumable handoff layer for
the deterministic ZIP produced by the cross-history comparison-query
observatory. It is downstream of the verified archive contract. It does not
rebuild the archive from a second source and it does not expose downloaded
records, local paths, or private metadata in its public projections.

## What it does

Given a verified observatory archive, the transfer builder:

1. loads the canonical archive bytes;
2. records the archive content address and exact byte length;
3. divides the byte stream into bounded contiguous chunks;
4. assigns each chunk a content address derived from its bytes; and
5. assigns the complete transfer a content address derived from its public
   manifest.

The default chunk size is 1,024 bytes. The contract accepts chunk sizes from
64 bytes through 4 MiB, limits the transfer to 4,096 chunks, and limits the
archive payload to 128 MiB. Every chunk has an index, offset, size, and
receipt. The last chunk may be shorter than the requested chunk size.

## Complete and partial handoffs

A complete transfer directory has this exact shape:

```text
comparison-history-observatory-archive-transfer/
  manifest.json
  chunks/
    chunk-00000000.bin
    chunk-00000001.bin
    ...
```

`manifest.json` is canonical JSON and contains only the transfer contract,
chunk receipts, the archive address, and a manifest address. Chunk files use
canonical zero-padded names. Complete persistence is atomic and refuses
unknown members, traversal-like names, symlinks, missing chunks, invalid
receipts, non-canonical JSON, and archive bytes that fail nested verification.

A partial receiver uses the same shape but contains only the chunks received
so far. `TransferAssembler` accepts chunks in any order, treats an identical
duplicate as idempotent, rejects a conflicting duplicate, and exposes an
addressed progress receipt with received indices, missing indices, received
bytes, and completion state. The partial writer is atomic, so a receiver can
persist progress after each safe batch and resume from that directory later.

Assembly requires every chunk. The assembler validates each range and chunk
receipt, concatenates the ranges in manifest order, reloads the resulting ZIP
through the archive verifier, and confirms that the nested archive address is
the address recorded in the transfer manifest. No partially assembled bytes
are returned as a successful archive.

## Independent audits

`audit_transfer` recomputes sixteen fixed checks:

- current version and public boundary;
- transfer address replay;
- canonical chunk order and offsets;
- byte-range conservation;
- payload or manifest receipt conservation;
- archive namespace linkage;
- manifest address and field replay;
- canonical manifest bytes;
- nested payload replay when payload is available;
- empty receiver progress replay;
- public mapping round-trip;
- private-field/path exclusion;
- configured size and count bounds; and
- deterministic chunk address namespaces.

The transfer query audit independently rebuilds the requested query and
recomputes twelve checks covering version, boundary, resource ordering,
filters, counts, page ordering, row addresses, row membership, resource
semantics, transfer linkage, public boundary, and mapping replay.

## Inspection query

The transfer query is intentionally manifest-safe. Its resources are:

- `summary` and `archive` for transfer/archive identity;
- `chunks` for every manifest receipt;
- `received` for chunks currently present in the in-memory or persisted
  receiver;
- `missing` for chunks still required; and
- `progress` for the current receiver state.

Queries support resource selection, chunk index, offset, size, chunk address,
received state, bounded text search, offset, and limit filters. Rows are
deterministically ordered and independently addressed. A transfer loaded from
manifest JSON has no payload bytes but remains queryable for inventory and
missing-chunk inspection.

## CLI

Set the long archive command prefix to the existing history-observatory
archive command and append `-transfer`:

```powershell
$base = "downloaded-data-profile-contract-compatibility-remediation-resolution-history-diff-policy-package-registry-observatory-archive-runtime-query-snapshot-diff-query-snapshot-diff-query-snapshot-registry-history-observatory-archive-transfer"

python -m glio_noncode $base C:\data\observatory.zip `
  --transfer-id downloaded-history-transfer `
  --chunk-size 1024 `
  --destination C:\out\history-transfer `
  --format summary

python -m glio_noncode "$base-progress" C:\out\history-transfer
python -m glio_noncode "$base-query" C:\out\history-transfer `
  --resource missing --limit 32 --format json
python -m glio_noncode "$base-audit" C:\out\history-transfer --format markdown
python -m glio_noncode "$base-assemble" C:\out\history-transfer `
  --destination C:\out\reassembled-observatory.zip
```

The command also accepts an observatory directory or canonical archive JSON
where the corresponding upstream contracts are available. Transfer JSON is a
manifest projection; assembly requires a complete transfer directory or a
source archive from which the builder can retain verified chunk payloads.

## Local HTTP API

The same operations are under:

```text
/v1/downloaded-data/profile/contract/compatibility/remediation/resolution/history/diff/policy/package/registry/observatory/archive/runtime/query-snapshot/diff/query-snapshot/diff/query-snapshot/registry/history/observatory/archive/transfer
```

The base route builds and optionally persists a transfer. `/verify`,
`/manifest`, `/progress`, `/assemble`, `/audit`, `/query`, and `/query/audit`
provide the corresponding read or verification operations. Schema and
capability routes are available below `/transfer` for the transfer, manifest,
progress, audit, query, and query-audit contracts.

## Real downloaded-data demonstration

`examples/downloaded_data_contract_resolution_history_diff_policy_demo.py`
now runs this layer against the attached current-format ZIP after cataloging,
contract comparison, history construction, observatory folding, and archive
verification. The demo writes:

- `comparison-history-observatory-archive-transfer/` with all chunks;
- `comparison-history-observatory-archive-transfer-partial/` containing the
  first and last chunk as a resumable receiver sample;
- transfer audit JSON/Markdown;
- transfer query JSON/Markdown; and
- transfer query-audit JSON/Markdown.

The generated summary reports archive/transfer byte equality, chunk count and
size, partial received/missing counts, and the independent audit/query
acceptance results. The CI workflow exercises every transfer schema and
capability command.
