# Execution-ledger runtime registry history diff archive

The history-diff archive is the portable transport boundary above the exact execution-ledger runtime registry history diff.

## Contract

- The ZIP has five members in fixed order: `manifest.json`, then the four canonical `history-diff/` projections.
- ZIP metadata is fixed, compression is deterministic, comments are rejected, and path safety is checked before any member is read.
- The outer manifest records the archive identity, nested diff address, exact member vocabulary, per-member byte receipts, and the physical archive size.
- Reload verifies canonical JSON, nested diff identity, every projected member, every receipt, physical size, and the outer manifest address.
- Archive values expose no source paths, source records, or payload bytes in their public mapping; raw bytes are used only for transport replay.

## Independent review surfaces

The archive has an 18-check audit covering identity, member order, size replay, receipt replay, archive and manifest addresses, ZIP replay, nested projections, public boundaries, raw availability, and mapping/byte round trips.

The archive query has eight bounded resources: `summary`, `artifacts`, `members`, `addresses`, `bounds`, `nested`, `receipts`, and `latest`. Its independent query audit verifies resource order, filtering, pagination, row addresses, membership, semantics, archive linkage, public boundaries, and mapping replay.

## Interfaces

The boundary is available through the CLI and local HTTP API at the `...history-diff-archive` route. Both surfaces support archive creation, verification, audit, bounded query, query audit, thirteen schema/capability documents, and atomic ZIP persistence.

The downloaded-data demonstration builds the archive from the exact history diff produced from the supplied ZIP, then reloads the persisted ZIP and replays the archive audit and query audit. The resulting evidence is deterministic and reviewable from the generated summary, archive, and inspection files.
