# Exact execution-ledger history-diff archive transfer

The exact execution-ledger runtime registry history-diff archive now has an addressed transfer contract. It carries the archive as fixed-size binary chunks while keeping the public contract value-free: the transfer exposes identities, offsets, lengths, and content addresses, while the receiver keeps chunk bytes only in its private assembly state.

## Contract

`build_transfer` verifies the nested archive before splitting its canonical bytes. Every chunk receipt records an ordinal, byte offset, byte length, and content address. The transfer records the archive identity, archive address, total byte count, chunk size, chunk count, and transfer address. The default chunk size is 1,024 bytes with bounded chunk and payload limits.

The receiver is deterministic and idempotent. It accepts chunks in any arrival order, accepts an identical duplicate, rejects a conflicting duplicate, reports received and missing indices, conserves received bytes, and refuses finalization until every receipt is present. Finalization reassembles the bytes in manifest order and reloads the nested archive so archive identity and content address are verified again.

## Persistence and inspection

Complete transfers persist atomically as a strict directory containing `manifest.json`, `chunks/`, and one canonical file per chunk. Partial transfers use the same manifest and only the received chunk files, allowing a receiver to stop and resume without weakening complete-directory checks. Non-canonical manifests, unexpected files, missing chunks, invalid names, changed bytes, and nested archive mismatches are rejected.

The transfer has an independent 18-check audit covering version, boundary, identity, archive linkage, chunk count and order, range conservation, receipts, payload completeness, reassembly, manifest and transfer addresses, empty and complete progress, public boundary, and mapping/byte/manifest round trips. The query surface exposes nine bounded resources: summary, chunks, addresses, bounds, progress, received, missing, receipts, and latest. Its independent query audit has 12 checks for resource order, filter and count replay, row addresses and membership, resource semantics, linkage, public boundary, and mapping round trip.

## Interfaces and real downloaded data

The exact-prefixed CLI and local HTTP API expose transfer construction, verification, manifest, partial progress, assembly, audit, query, query audit, schemas, and capabilities. Actions run the focused transfer regression suite.

The downloaded-data demonstration uses `GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip` only as bounded structural input. The current execution-ledger history-diff archive is 5,183 bytes and is transferred as six 1,024-byte chunks. The demo writes and reloads complete and partial receiver directories, delivers all chunks in reverse order, verifies exact reassembly, passes 18 transfer-audit checks and 12 query-audit checks, and records received/missing chunk and byte evidence in JSON, CSV, and Markdown inspection artifacts.
