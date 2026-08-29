# Assurance-history observatory archive transfer

The archive transfer is the byte-oriented handoff boundary for a verified
assurance-history observatory archive. It exists for uploads, object stores,
offline media, and constrained links where a single ZIP file is not the most
useful operational unit. It does not introduce a second observatory authority:
the transfer manifest addresses the existing archive, and reassembly must
replay the archive verifier before the result can be used.

The transfer boundary is:

```text
public_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer
```

The version is the archive version with `-transfer-v1` appended. Public
transfer records contain only bounded IDs, byte counts, ranges, and content
addresses. They do not contain local paths, usernames, email addresses,
agent fields, language fields, model fields, credentials, or arbitrary source
metadata.

## Data flow

```text
verified observatory directory
          |
          v
deterministic observatory ZIP
          |
          v
verified archive bytes -- split --> chunk receipts + chunk bytes
          |                                  |
          |                                  v
          |                         exact transfer directory
          |                                  |
          +-------------------------- load / verify
                                             |
                                             v
                         hash every chunk, reassemble exact bytes,
                         verify nested archive, preserve archive address
```

The archive content address is the primary identity. The transfer content
address is a separate address over the transfer ID, archive address, chunk
size, chunk count, byte ranges, and chunk addresses. Changing the transfer ID
or chunking policy changes the transfer address while preserving the archive
address. This makes the transport policy observable without confusing it with
the evidence package.

## Manifest contract

The public transfer projection contains:

| Field | Meaning |
| --- | --- |
| `transfer_id` | Stable caller-supplied handoff identity. |
| `version` | Current transfer contract version. |
| `boundary` | Public transfer boundary name. |
| `archive_address` | Address of the verified nested archive. |
| `archive_size` | Exact byte length of the nested ZIP. |
| `chunk_size` | Requested fixed size for all non-terminal chunks. |
| `chunk_count` | Number of chunks required to cover the archive. |
| `chunks` | Ordered index, offset, size, and address receipts. |
| `content_address` | Address of the complete transfer projection. |
| `manifest_address` | Address of the canonical on-disk manifest. |

The manifest contains one chunk record for every range. Indices begin at zero,
offsets are contiguous, all non-terminal chunks equal `chunk_size`, and the
last chunk is the exact remainder. The following conservation rule is always
checked:

```text
chunk_count = ceil(archive_size / chunk_size)
sum(chunk.size) = archive_size
chunk[i].offset = sum(chunk[j].size for j < i)
```

Each chunk address is computed from its exact bytes. A receipt cannot be
replaced with another byte sequence without changing the transfer graph.

## Bounds

The current implementation applies these limits:

| Limit | Value |
| --- | ---: |
| minimum chunk size | 256 bytes |
| maximum chunk size | 4 MiB |
| maximum archive/transfer size | 128 MiB |
| maximum chunk count | 4,096 |
| maximum query items | bounded by the public query limit |

Booleans are not accepted as integers for sizes, offsets, counts, or indices.
Strings are not coerced into numbers. A caller that needs a different policy
must choose it explicitly at the transport boundary and receive a new
content-addressed transfer.

## Exact directory layout

A persisted transfer contains only regular files in this shape:

```text
manifest.json
chunks/
  chunk-00000000.bin
  chunk-00000001.bin
  ...
```

The chunk names are zero-padded and derived only from the manifest index. The
loader first reads and verifies canonical `manifest.json`, then checks that
the directory has exactly the manifest, the `chunks` directory, and every
declared chunk. Extra files, missing files, nested paths, symlinks, and
non-regular members are rejected. Writes use a temporary sibling directory and
atomic replacement. Existing output requires explicit overwrite permission and
must already have the exact compatible shape; arbitrary directories are never
recursively replaced as a convenience.

## Reassembly and verification

`assemble_archive_bytes` accepts a typed transfer and optionally an explicit
mapping of chunk indices to bytes. It performs the following checks in order:

1. the transfer is typed and its public manifest validates;
2. the supplied index set is exactly `0..chunk_count-1`;
3. every byte value is a `bytes` object with the declared length;
4. every chunk hash equals its declared content address;
5. the assembled byte count equals `archive_size`;
6. the nested ZIP is loaded with the archive’s exact-member and canonical
   manifest controls; and
7. the nested archive address equals `archive_address` in the transfer.

This prevents a syntactically valid set of chunks from laundering a different
archive. A manifest-only transfer can be used for inventory and missing-chunk
queries, but it cannot be assembled until all bytes are supplied.

## Queries and projections

The bounded query resources are:

```text
summary, chunks, missing
```

`summary` returns one transfer projection. `chunks` returns ordered receipts.
`missing` returns the declared receipts when the caller has only a public
manifest and returns an empty set for a fully loaded transfer. `progress`
returns an addressed received/missing index snapshot and byte count. Text
search is case-insensitive over canonical record text. Offset and limit are
bounded and every result has its own content address.

The transfer audit surface adds eight independently addressed checks over a
complete or partial receiver state: transfer address, range conservation,
public boundary, manifest address, received chunk receipts, progress
conservation, nested archive linkage, and final completeness. A complete
transfer must pass all checks; a valid partial transfer remains inspectable but
reports incomplete status until reassembly is possible.

JSON is canonical. CSV uses deterministic sorted columns. Markdown is a
human-readable report over the same records. Presentation format cannot alter
selection, counts, byte ranges, or addresses.

## CLI

The long-form command is nested below the archive command. The examples use
`<archive-transfer-command>` as the generated full command name:

```powershell
python -m glio_noncode <archive-transfer-command> `
  --input review-output/observatory.zip `
  --destination review-output/transfer `
  --transfer-id transfer:release-window-2026-08-28 `
  --chunk-size 65536 `
  --format summary

python -m glio_noncode <archive-transfer-command>-verify `
  --input review-output/transfer

python -m glio_noncode <archive-transfer-command>-manifest `
  --input review-output/transfer

python -m glio_noncode <archive-transfer-command>-query `
  --input review-output/transfer `
  --resource progress `
  --offset 0 `
  --limit 50 `
  --format markdown

python -m glio_noncode <archive-transfer-command>-audit \
  --input review-output/transfer \
  --format markdown

python -m glio_noncode <archive-transfer-command>-audit \
  --input review-output/partial-transfer \
  --partial \
  --format json
```

The command emits status `0` for a successful build, verification, query, or
schema operation and status `1` for malformed input or contract failure.

The exact command can be discovered from the capability command or the
operator contract. The transfer schema, chunk schema, manifest schema, query
schema, query-result schema, and capabilities are separate CLI resources so a
consumer can negotiate bounds before sending bytes.

## HTTP

The transfer route is nested below the archive route:

```text
.../decision-ledger/assurance-history/observatory/archive/transfer
```

The read-oriented endpoints are:

| Route | Purpose |
| --- | --- |
| `/schema` | transfer projection schema |
| `/chunk-schema` | chunk receipt schema |
| `/manifest-schema` | persisted manifest schema |
| `/progress-schema` | incremental assembly progress schema |
| `/query-schema` | query filter schema |
| `/query-result-schema` | result schema |
| `/capabilities` | limits, resources, and features |
| `/` | build and persist from an archive file |
| `/verify` | load and verify an exact transfer directory |
| `/manifest` | return the canonical manifest projection |
| `/query` | return a bounded summary, chunk, or missing window |
| `/audit` | independently audit a complete or partial transfer |
| `/audit/schema` | audit projection schema |
| `/audit/check-schema` | audit check schema |
| `/audit/capabilities` | audit checks and states |

Build requests require `input`/`archive` and `destination`. Query requests
require `input`/`transfer`. CSV and Markdown are returned as text media types;
JSON responses preserve the same addressed objects. Filesystem paths are
request-edge parameters and are never copied into public responses.

## Negative controls

The transfer boundary deliberately rejects:

- non-typed archives and malformed archive bytes;
- chunk sizes outside the declared bounds or supplied as booleans/strings;
- missing or duplicate chunk indices;
- wrong offsets, sizes, or chunk counts;
- changed chunk bytes or changed chunk addresses;
- changed nested archive bytes or archive address linkage;
- non-canonical or extra manifest fields;
- manifest address, transfer address, or progress address drift;
- missing, extra, symlinked, or non-regular directory members;
- non-canonical manifest JSON;
- arbitrary destination replacement without explicit overwrite; and
- public fields that contain forbidden attribution or private-path metadata;
- conflicting duplicate chunks submitted to an incremental assembler; and
- finalization requested while the addressed progress receipt still has gaps.

Failures are not converted to an empty transfer. A valid manifest-only view is
different from a failed load, and an empty missing window is different from a
malformed transfer.

## Operational checklist

For a downloaded-data handoff:

1. verify the observatory directory before archiving;
2. build the deterministic archive and record its archive address;
3. choose a chunk size appropriate to the receiving transport;
4. write the transfer directory to a new destination;
5. copy or upload manifest and chunk files without renaming them;
6. load the receiving directory and run transfer verification;
7. query `summary` and `chunks` to compare counts and receipts;
8. reassemble only after all chunks are present; and
9. compare the nested archive address with the sender’s recorded address.

If a chunk fails, retain the transfer manifest, replace only the failed
transport copy from the original source, and rerun the full loader. Do not
edit a hash or manifest to make a copied byte appear valid.

## Demonstration

The runnable demonstration accepts a downloaded observatory ZIP and can write
and reload a transfer directory:

```powershell
python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_transfer_demo.py `
  --input review-output/observatory.zip `
  --destination review-output/transfer `
  --chunk-size 65536 `
  --resource chunks `
  --limit 5 `
  --format markdown
```

The focused transfer suite exercises the same flow with a current-format
downloaded-package fixture, deterministic repeat builds, manifest-only
inventory, explicit part reassembly, filesystem negative controls, CLI, HTTP,
schemas, renderers, incremental out-of-order assembly, addressed progress
receipts, persisted partial-transfer recovery, independent audit checks, and
nested archive verification.
