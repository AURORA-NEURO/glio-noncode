# Runtime-registry federation archive transfer

The runtime-registry federation archive can be moved as a resumable addressed
transfer. The transfer consumes the verified deterministic ZIP produced by the
federation archive boundary and records only public geometry and content
addresses in its manifest. Chunk bytes are held by the receiver or by an
explicitly persisted transfer directory; they are not included in the public
manifest projection.

## Transfer contract

`build_transfer` verifies the nested federation archive, splits its canonical
bytes into fixed-size contiguous ranges, and assigns each chunk a content
address. A transfer has a stable transfer address, archive address, byte size,
chunk size, chunk count, and ordered chunk receipts. `TransferAssembler`
accepts chunks out of order, treats an identical duplicate as idempotent, and
rejects a conflicting or incorrectly addressed receipt.

Complete transfers persist atomically as:

```text
manifest.json
chunks/
  chunk-00000000.bin
  ...
```

Partial transfers use the same vocabulary and contain only received chunks.
Reload validates canonical JSON, exact directory membership, canonical chunk
names, chunk sizes, chunk addresses, and the transfer manifest address. Final
assembly requires every chunk and then re-verifies the nested federation
archive and its archive address.

## Inspection and assurance

The transfer audit independently replays 18 checks covering version and
boundary, chunk order and ranges, receipt conservation, archive linkage,
manifest addressing, canonical bytes, payload replay, nested archive replay,
progress, mapping round trips, the public boundary, bounds, chunk addresses,
and deterministic serialization.

The bounded query exposes summary, archive, chunks, received, missing,
progress, and bounds resources. It supports chunk index, offset, size, content
address, received-state, text, and pagination filters. Its independent query
audit replays 12 checks for resource order, filters, counts, row addresses,
membership, resource semantics, linkage, public-boundary safety, and mapping
round trips.

## CLI and HTTP API

The CLI command family is derived from the long downloaded-data federation
archive command and ends in `-archive-transfer`. It supports complete transfer
creation, partial receiver persistence, verification, audit, query, query audit,
and all transfer/query schema and capability projections. The HTTP API mirrors
the same boundary below the existing federation archive route, including
`/transfer`, `/transfer/partial`, `/transfer/verify`, `/transfer/audit`,
`/transfer/query`, `/transfer/query/audit`, and the schema routes.

The downloaded-data demo reads the attached real ZIP, builds the federation
archive, writes a six-chunk 1,024-byte transfer, persists a two-chunk partial
receiver, emits complete and partial progress, audits, bounded query output,
and query-audit artifacts, and verifies byte-for-byte reassembly.

The public contract deliberately excludes source paths, source records,
payload bytes, private metadata, agent metadata, and language metadata.
