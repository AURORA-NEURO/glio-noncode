# Federation History-Diff Archive Transfer

This boundary transports the deterministic ZIP produced by the federation runtime-registry history-diff archive. It is deliberately a transport contract, not a second interpretation of the downloaded source. The transfer anchors the exact archive address and exposes only bounded manifest, chunk geometry, receipt, progress, audit, and query data.

## Transfer contract

`build_transfer` verifies the source history-diff archive, serializes its canonical five-member ZIP, and divides those bytes into contiguous fixed-size ranges. The default chunk size is 1,024 bytes; callers may choose a bounded size from 64 bytes through 4 MiB. Every chunk has an ordinal, offset, byte count, and content address. The transfer address is derived from the public manifest fields and never from the private chunk payload.

The public transfer projection contains:

- transfer identity and version boundary;
- the anchored history-diff archive address and byte count;
- chunk size, count, ordered byte ranges, and chunk addresses;
- the transfer content address.

Payload bytes are held only by a local builder or receiver assembler. They are not included in `transfer_json`, `manifest_json`, progress, audits, queries, schemas, or capabilities.

## Receiver lifecycle

`HistoryDiffArchiveTransferAssembler` accepts verified chunks in any arrival order. Repeating the same chunk is idempotent; a conflicting replacement is rejected. The progress receipt conserves the full chunk index set into sorted `received_indices` and `missing_indices`, reports received bytes, and becomes complete only when every range is present.

Complete transfers persist atomically as a canonical directory containing `manifest.json` and `chunks/chunk-00000000.bin` through the final canonical member. Partial transfers use the same manifest and retain only received chunk members. Reload rejects symlinks, non-canonical JSON, unknown members, non-canonical names, out-of-range indices, wrong sizes, and wrong content addresses. Finalization reassembles the bytes in manifest order and runs the nested history-diff archive verifier, including the anchored archive address check.

## Independent assurance and inspection

The transfer audit has 18 checks covering version and boundary, transfer identity, range ordering and conservation, receipts, archive linkage, manifest replay, canonical bytes, available payload replay, nested archive replay, empty-progress replay, mapping round trips, public boundaries, bounds, chunk namespaces, and deterministic addresses.

The query boundary is manifest-only and bounded to seven resources: `summary`, `archive`, `chunks`, `received`, `missing`, `progress`, and `bounds`. It supports resource selection, chunk index/offset/size/address filters, received-state filtering, text matching, and pagination. A query can be run against a partial directory so the receiver partition is visible without reading absent payload bytes. Its independent audit has 12 checks covering contract derivation, canonical resource ordering, filter and count replay, row ordering and addressing, row membership, resource semantics, transfer linkage, public boundary, and mapping replay.

## Interfaces

The CLI command family is derived from the downloaded-data history-diff archive command:

```text
...-history-diff-archive-transfer INPUT --destination DIR
...-history-diff-archive-transfer-partial INPUT --received INDEX --destination DIR
...-history-diff-archive-transfer-verify DIR
...-history-diff-archive-transfer-manifest DIR
...-history-diff-archive-transfer-progress DIR
...-history-diff-archive-transfer-assemble DIR --archive-output ZIP
...-history-diff-archive-transfer-audit DIR
...-history-diff-archive-transfer-query DIR --resource chunks --received false
...-history-diff-archive-transfer-query-audit QUERY_JSON --transfer-input DIR
```

The HTTP surface is rooted at `/v1/downloaded-data/.../history/diff/archive/transfer` and mirrors those operations with `/partial`, `/verify`, `/manifest`, `/progress`, `/assemble`, `/audit`, `/query`, and `/query/audit`. Fourteen schema and capability routes describe the transfer, audit, query, and query-audit projections.

The downloaded-data demo builds this boundary from the attached ZIP, receives chunks in reverse order, persists a complete transfer, persists a two-chunk partial transfer, reloads both states, runs all audits and bounded queries, and writes a reassembled ZIP. The demonstration summary records addresses, sizes, chunk counts, partial receipt state, audit counts, deterministic replay, and exact archive equality while keeping source paths and payload bytes out of public JSON projections.
