# Module Workbench Execution Packets

The execution packet is the portable handoff for the module-by-module
implementation workbench. The in-memory execution ledger is useful while a
run is being assembled, but an offline reviewer needs a directory that can be
moved, archived, verified, queried, replayed, and released without access to
the original source tree. This layer provides that boundary.

The packet is intentionally local-first. It does not fetch source data, open a
database, or authorize code changes. It packages the deterministic workbench
report, a bounded portfolio, the initial and current execution ledgers, the
module review projection, independent audit, policy result, runtime handoff,
and the contract declarations needed by an offline reader.

## Public boundary

The packet boundary is:

```text
public_aggregate_module_workbench_execution_packet
```

Every packet manifest and artifact is timestamp-free, path-free in its public
projection, and free of personal or private workflow fields. Files on disk
have safe POSIX-style relative names. A local destination is an operational
input to the writer, not a value retained in the manifest.

The packet has a second decision boundary for release:

```text
public_aggregate_module_workbench_execution_packet_release
```

The release decision does not alter the packet. It records whether the packet
passed the minimum artifact, verification, replay, and public-boundary checks.
This keeps storage integrity separate from a release policy decision.

## Artifact contract

Version `module-workbench-execution-packet-v1` contains thirteen artifacts.
The manifest records each artifact's ID, relative path, media type, kind,
UTF-8 byte count, line count, and exact byte content address.

| Artifact | Path | Format | Purpose |
| --- | --- | --- | --- |
| `audit` | `audit.json` | JSON | Independent execution-ledger checks |
| `blockers` | `blockers.csv` | CSV | Flat rows for explicit blockers |
| `capabilities` | `capabilities.json` | JSON | Offline operation declaration |
| `events` | `events.csv` | CSV | Ordered transition history |
| `initial-ledger` | `initial-ledger.json` | JSON | Pre-replay plan snapshot |
| `items` | `items.csv` | CSV | Current task rows |
| `ledger` | `ledger.json` | JSON | Current evidence-gated state |
| `policy` | `policy.json` | JSON | Policy thresholds and gate result |
| `portfolio` | `portfolio.json` | JSON | Bounded task selection |
| `review` | `review.json` | JSON | Per-module review routing |
| `runtime` | `runtime.json` | JSON | Six-stage execution handoff |
| `schema` | `schema.json` | JSON | Packet contract and limits |
| `workbench-summary` | `workbench-summary.json` | JSON | Source workbench aggregate |

The artifact IDs and paths are sorted and unique. The fixed count prevents a
writer from silently omitting a required view. Future versions can add a new
version and a new declared artifact contract without changing the meaning of
an existing packet.

## Address domains

There are deliberately separate address domains:

1. The ledger, review, audit, policy, gate, runtime, and report each retain
   their own existing typed content address.
2. An artifact address is a hash over the exact UTF-8 bytes written to disk.
3. The packet address is a hash over the canonical manifest descriptor with
   artifact payloads omitted.
4. A verification receipt and release decision have independent addresses.

The byte address is the important storage guarantee. Reformatting a JSON
artifact, changing a newline, or changing a CSV delimiter changes its byte
address and fails verification. The packet does not infer equivalence from a
parsed object after the bytes have been written.

## Build flow

`build_module_workbench_execution_packet` accepts a typed workbench report and
an optional portfolio, command sequence, policy, and packet ID. The normal
flow is:

```text
workbench report
      |
      v
bounded portfolio
      |
      v
initial execution ledger -- command replay --> current ledger
      |                         |                 |
      |                         +--> audit       |
      |                         +--> policy      |
      |                         +--> runtime     |
      +------------------------------------------+
                           |
                           v
                    module review projection
                           |
                           v
                    thirteen packet artifacts
                           |
                           v
                    packet checks and address
```

The command sequence is normalized to a tuple before it is replayed. That is
important for callers that provide a generator: the same commands must be
used for both the packet ledger and the retained runtime handoff.

The builder recalculates each downstream artifact from the same current
ledger. A packet cannot accidentally combine one review projection with a
different ledger address. Linkage checks cover report, portfolio, initial
ledger, current ledger, review, audit, policy, and runtime references.

## Atomic writer

`write_module_workbench_execution_packet` creates a dedicated destination and
writes the manifest and each artifact with a temporary sibling file followed
by an atomic replacement. The file is flushed and synchronized before the
replacement is made visible. A pre-existing destination is rejected unless
`allow_existing=True` is explicit.

The writer never deletes an existing file. When replacement is enabled, the
verifier's `no-unlisted-files` check makes stale or manually added files
visible as a blocked packet. This makes an accidental mixture of two packet
versions detectable instead of silently publishing the newer manifest with
older artifacts.

Example:

```python
from glio_noncode import (
    build_module_workbench_execution_packet,
    write_module_workbench_execution_packet,
)

packet = build_module_workbench_execution_packet(workbench_report)
write_module_workbench_execution_packet(
    packet,
    "out/execution-packet",
)
```

The directory contains `manifest.json` plus the thirteen declared files. The
manifest does not embed payloads. A typed packet can include payloads in an
explicit JSON export for local diagnostics, but the default public manifest
and query projections retain descriptors only.

## Independent verification

`verify_module_workbench_execution_packet` reconstructs a verification receipt
from the directory. It does not trust the packet builder. Its check planes
are:

| Check | What it proves |
| --- | --- |
| `manifest-readable` | The manifest is a UTF-8 JSON object |
| `manifest-shape` | The artifact collection is an array |
| `manifest-version-boundary` | The version and boundary are recognized |
| `safe-paths` | No absolute or traversal path is accepted |
| `artifact-count` | The fixed thirteen-artifact contract is present |
| `unique-artifacts` | IDs and paths are unique and sorted |
| `artifact-presence` | Every declared file is readable |
| `artifact-byte-addresses` | Bytes, counts, and descriptor fields agree |
| `no-unlisted-files` | No extra file is present in the packet directory |
| `canonical-json` | JSON bytes round-trip to canonical JSON |
| `public-boundary` | Manifest and payload keys stay public |
| `manifest-address` | The exact descriptor has the retained packet address |

The verifier returns all findings even when the packet is blocked. It does
not stop at the first failure. This is useful for offline repair because a
reviewer can see whether a failure is missing storage, a byte mismatch, a
path violation, or a manifest-address mismatch.

`load_module_workbench_execution_packet` only hydrates a directory after the
verification receipt is accepted. It restores the exact payload strings in
the typed artifact objects and checks that the loaded packet address matches
the manifest address. A blocked directory raises `ValidationError` rather
than producing a partially trusted packet.

For an in-memory packet, `verify_module_workbench_execution_packet_value`
checks the packet address, every artifact byte address, packet acceptance, and
the public boundary without creating a directory.

## Offline query resources

`query_module_workbench_execution_packet` accepts a typed packet or a verified
directory. It provides bounded pages over five resources:

| Resource | Rows | Index |
| --- | --- | --- |
| `manifest` | One packet descriptor | `packet_id` |
| `artifacts` | One descriptor per file | `artifact_id` |
| `checks` | One build check per result | `check_id` |
| `links` | Nine stage-to-address links | `name` |
| `summary` | One compact aggregate | `packet_id` |

Artifact filters include ID and kind. Check filters include plane and pass
state. Link filters include the link name. All resources support free-text
matching, offset, and a maximum limit of 512. The query body includes the
packet address, selected resource, filters, page, index used, and an address
for the result itself.

Example:

```python
from glio_noncode import query_module_workbench_execution_packet

ready = query_module_workbench_execution_packet(
    "out/execution-packet",
    resource="checks",
    plane="linkage",
    passed=True,
    limit=32,
)
```

No query uses the source tree. Once a packet is verified, it is a self-
contained review surface.

## Replay and packet diffs

`replay_module_workbench_execution_packet` returns a compact receipt listing
the packet address, verification address when a directory was used, artifact
count, JSON artifact IDs, and all replayed artifact IDs. It is a verification
and readability operation; it does not execute source code or transition the
ledger.

`diff_module_workbench_execution_packets` compares two typed packets or two
verified directories. It reports:

- added and removed artifact IDs;
- changed and unchanged byte-addressed artifacts;
- changed address-chain link names;
- state and acceptance changes; and
- separate left and right packet IDs and addresses.

A diff of a packet with itself is a useful invariant: every artifact is
unchanged, no link changes, and the result remains accepted. A command replay
that changes the current ledger changes the ledger, review, runtime, and
possibly audit/policy artifacts while unchanged contract declarations remain
stable.

## Release decision

`build_module_workbench_execution_packet_release` accepts a typed packet or a
verified packet directory. It evaluates six explicit checks:

1. artifact threshold;
2. passed-check threshold;
3. packet acceptance;
4. public boundary;
5. replay acceptance; and
6. retained verification address.

The default minimum artifact count is thirteen and the default minimum passed
check count is one. A caller can require more passed checks or intentionally
set an impossible threshold to rehearse a blocked release:

```python
strict = build_module_workbench_execution_packet_release(
    "out/execution-packet",
    minimum_artifact_count=13,
    minimum_passed_check_count=14,
)
```

The release state is `accepted` only when every check passes. Otherwise it is
`blocked`; the failed checks remain visible through JSON, CSV, Markdown, and
the bounded `checks` query. Release verification recomputes each check
address, the aggregate release address, and acceptance conservation.

## Seven-stage packet runtime

`run_module_workbench_execution_packet_runtime` exposes one ordered runtime:

```text
build -> write -> verify -> load -> query -> replay -> release
```

When no destination is given, the write stage is an explicitly accepted
in-memory handoff and typed verification is used. When a destination is given,
the writer and filesystem verifier are used. The public runtime retains no
local path; it retains the packet, verification, replay, release, and stage
addresses.

Every stage is either `completed` and accepted or `blocked` and unaccepted.
The runtime contract conserves stage count, completed count, and blocked count,
requires the exact declared order, and recomputes every stage address. The
runtime's acceptance is the conjunction of the stage acceptances.

This runtime is a handoff coordinator, not a source executor. It does not
pretend that writing a packet performed the implementation tasks represented
by the ledger.

## CLI

Build and write a packet:

```powershell
python -m glio_noncode module-workbench-execution-packet `
  --capacity 25 `
  --max-tasks-per-module 2 `
  --destination .\out\execution-packet `
  --output .\out\execution-packet-result.json
```

Build a JSON or Markdown projection without writing a directory:

```powershell
python -m glio_noncode module-workbench-execution-packet --format json
python -m glio_noncode module-workbench-execution-packet --format markdown
python -m glio_noncode module-workbench-execution-packet --resource links
```

Verify, load, query, diff, and replay a persisted packet:

```powershell
python -m glio_noncode module-workbench-execution-packet-verify .\out\execution-packet
python -m glio_noncode module-workbench-execution-packet-load .\out\execution-packet
python -m glio_noncode module-workbench-execution-packet-query .\out\execution-packet --resource checks --plane linkage
python -m glio_noncode module-workbench-execution-packet-diff .\out\left .\out\right
python -m glio_noncode module-workbench-execution-packet-replay .\out\execution-packet
```

Evaluate a release and inspect the ordered packet runtime:

```powershell
python -m glio_noncode module-workbench-execution-packet-release .\out\execution-packet --format summary
python -m glio_noncode module-workbench-execution-packet-release-query .\out\execution-packet --resource checks --passed
python -m glio_noncode module-workbench-execution-packet-runtime --destination .\out\runtime-packet
python -m glio_noncode module-workbench-execution-packet-runtime --resource summary
```

Schemas and capabilities are separate commands so an offline client can
discover limits without building a workbench:

```powershell
python -m glio_noncode module-workbench-execution-packet-schema
python -m glio_noncode module-workbench-execution-packet-capabilities
python -m glio_noncode module-workbench-execution-packet-release-schema
python -m glio_noncode module-workbench-execution-packet-runtime-schema
python -m glio_noncode module-workbench-execution-packet-inspection-schema
python -m glio_noncode module-workbench-execution-packet-inspection-capabilities
```

## Inspection findings

Packet verification and release decisions are intentionally separate typed
objects. The inspection projection joins them into one bounded review surface
without hiding which plane produced a result. Each finding retains its stable
identifier, plane, severity, code, observed value, required value, detail, and
content address.

The inspection builder accepts either a typed packet or a persisted packet
directory. For a directory it runs the independent filesystem verifier, loads
the packet only when verification accepts, replays the declared artifacts, and
evaluates the release gate. A malformed directory therefore becomes a blocked
inspection with findings rather than being silently treated as trusted input.

Severity is deterministic: passing findings are `info`; failed byte, path,
storage, or public-boundary checks are `critical`; other failed semantic,
replay, linkage, or release checks are `warning`. Severity is a review aid and
does not override the packet or release state.

The command-line review and query surfaces are:

```powershell
python -m glio_noncode module-workbench-execution-packet-inspection .\out\execution-packet --format markdown
python -m glio_noncode module-workbench-execution-packet-inspection .\out\execution-packet --format csv
python -m glio_noncode module-workbench-execution-packet-inspection-query .\out\execution-packet --resource summary
python -m glio_noncode module-workbench-execution-packet-inspection-query .\out\execution-packet --plane release --passed
python -m glio_noncode module-workbench-execution-packet-inspection-query .\out\execution-packet --severity critical
```

The two query resources are `summary` and `findings`. Finding queries support
severity, plane, exact code, result, text, offset, and bounded limit filters.
JSON is canonical and includes every finding; CSV serializes observed and
required values as canonical JSON cells; Markdown provides a human-readable
table while preserving all finding IDs and addresses.

The read-only HTTP routes mirror the typed module:

```text
GET /v1/module-workbench/execution/packet/inspection
GET /v1/module-workbench/execution/packet/inspection/query
GET /v1/module-workbench/execution/packet/inspection/schema
GET /v1/module-workbench/execution/packet/inspection/capabilities
```

The inspection boundary is public aggregate, path-free, timestamp-free, and
identity-free. It does not include source paths, credentials, downloaded
payloads, private workflow fields, or mutable runtime state. It is a review
projection only: accepting an inspection does not claim a scientific result,
complete an implementation task, or authorize deployment.

## API

The read-only HTTP service exposes:

```text
GET /v1/module-workbench/execution/packet
GET /v1/module-workbench/execution/packet/query
GET /v1/module-workbench/execution/packet/replay
GET /v1/module-workbench/execution/packet/schema
GET /v1/module-workbench/execution/packet/capabilities
GET /v1/module-workbench/execution/packet/release
GET /v1/module-workbench/execution/packet/release/query
GET /v1/module-workbench/execution/packet/release/schema
GET /v1/module-workbench/execution/packet/release/capabilities
GET /v1/module-workbench/execution/packet/runtime
GET /v1/module-workbench/execution/packet/runtime/query
GET /v1/module-workbench/execution/packet/runtime/schema
GET /v1/module-workbench/execution/packet/runtime/capabilities
```

The API builds a read-only packet in memory. Filesystem writes and persisted
packet verification remain explicit Python and CLI operations so an HTTP GET
cannot mutate a local directory. Format parameters provide JSON, CSV, and
Markdown where the route supports them. Query parameters mirror the typed
query functions and are bounded before work is performed.

## Failure matrix

| Failure | Build | Verify | Load | Release |
| --- | --- | --- | --- | --- |
| Unknown workbench type | error | not applicable | not applicable | not applicable |
| Missing artifact | not applicable | blocked receipt | error | blocked |
| Changed artifact byte | not applicable | blocked receipt | error | blocked |
| Extra directory file | not applicable | blocked receipt | error | blocked |
| Unsafe manifest path | not applicable | blocked receipt | error | blocked |
| Non-canonical JSON | not applicable | blocked receipt | error | blocked |
| Packet address mismatch | not applicable | blocked receipt | error | blocked |
| Impossible release threshold | not applicable | not applicable | allowed if packet valid | blocked |
| Tampered release check | not applicable | not applicable | not applicable | verification error |

The distinction between a blocked receipt and an exception is intentional. A
filesystem verifier can explain a bad directory. A loader must not return
that directory as trusted typed state. A release can retain a blocked decision
for an operator without turning it into an accepted handoff.

## Data and privacy boundary

The packet operates on module workbench aggregates: module IDs, task IDs,
families, evidence receipt addresses, state transitions, and contract checks.
It does not embed downloaded payloads, subject-level values, credentials, or
private workflow fields. The packet's payloads are derived public aggregate
JSON and CSV projections. The `public-boundary` check walks the manifest and
all artifact payloads before the packet can be accepted.

A source registry or public reference dataset can be used upstream to produce
an aggregate report, but the packet itself records only the addressed report
and downstream aggregates. The packet writer does not download any external
source and does not treat a source declaration as scientific validation.

## Verification checklist

The packet regression suite covers:

- fixed artifact set and address-chain conservation;
- typed byte verification;
- atomic write, filesystem verify, and exact reload;
- canonical manifest shape and payload exclusion;
- every query resource and filter family;
- bounded paging failures;
- typed and filesystem replay receipts;
- byte tampering, missing files, and unlisted files;
- same-packet and changed-packet diffs;
- accepted and threshold-blocked release decisions;
- release exports and address verification;
- in-memory and filesystem-backed seven-stage runtimes;
- runtime stage-address tampering; and
- schema and capability count conservation.

The packet is a durable review and handoff artifact. It does not upgrade a
task to `completed`, certify a scientific result, or authorize a production
deployment. Those meanings remain in the execution ledger, independent audit,
and explicit release policy.

## Deterministic archive transport

The packet directory is convenient for local inspection; the archive transport
is the portable boundary for moving the same packet as one exact byte stream.
`build_module_workbench_execution_packet_archive` accepts a typed packet or a
verified packet directory and emits a fixed-metadata `ZIP_STORED` container.
The default archive contains fourteen members: `manifest.json` followed by the
thirteen packet artifacts. Every member is UTF-8 JSON or CSV already addressed
by the packet contract. Compression is deliberately not used, because the
transport address must be stable across machines and runtimes.

Archive construction fixes ZIP timestamps, creator fields, version fields,
comments, and extra data. It rejects missing, unlisted, unsafe, non-regular,
symlink, or non-canonical members before accepting the container. Archive
descriptors retain the archive ID, packet ID, packet address, member ordinals,
member paths, member kinds, exact byte counts, content addresses, and the
binary archive address. The raw bytes are available to a transport caller but
are intentionally omitted from descriptor JSON and all public aggregate
projections.

Verification is multi-plane and fail-closed:

| Plane | Verification |
| --- | --- |
| ZIP | Readability, duplicate member names, regular member attributes, and bounded member count |
| Path | Relative UTF-8 paths only; no absolute paths, parent traversal, drive prefixes, or empty segments |
| Manifest | Canonical manifest bytes, required artifact set, ordinal conservation, and descriptor alignment |
| Bytes | Exact member bytes, content addresses, line counts, and total payload conservation |
| Packet | Hydrated packet verification, packet address, packet state, and public boundary |
| Storage | Atomic archive write, destination policy, and safe staging replacement |

The verifier returns an addressed receipt even when a container is blocked.
The loader raises on a blocked archive and only hydrates a typed packet after
all checks pass. The writer uses a sibling temporary file and an atomic replace;
it does not silently overwrite an existing destination. Unpacking uses a
staging directory, creates only validated relative paths, and atomically
replaces the requested destination. Existing extraction trees require the
explicit `allow_existing` option.

The archive can be queried without unpacking. `entries` returns bounded member
rows, `summary` returns the aggregate descriptor, and entry ID, entry kind,
free-text, offset, and limit filters are available. JSON, CSV, and Markdown
exports preserve the same member ordering and stable addresses. No query
returns a source path, local username, credential, downloaded subject value, or
mutable process detail.

## Chunk transfer and runtime

The transfer module divides exact archive bytes into addressed contiguous
chunks. Each chunk carries its ordinal, offset, byte count, archive address,
payload-derived address, and optional payload bytes. Chunk descriptors are
sorted, bounded, and independently verifiable. The transfer receipt conserves
the archive byte count and total chunk count while distinguishing `ready`,
`partial`, and `completed` states. Resuming a transfer merges completed
ordinals idempotently, rejects out-of-range ordinals, and gives the new receipt
its own content address. Reassembly refuses missing, duplicate, foreign, or
misordered chunks and verifies the final archive address before returning
bytes.

The archive runtime composes the transport lifecycle into nine ordered stages:

1. build the archive;
2. write or retain its exact bytes;
3. verify the container;
4. load the packet from bytes;
5. create addressed chunks;
6. establish a partial transfer;
7. resume and complete the transfer;
8. reassemble and optionally unpack; and
9. query the resulting chunk set.

Every stage has a stable artifact address and an accepted or blocked state.
Runtime verification recomputes stage addresses, conserves completed and
blocked counts, checks stage order, and verifies the final runtime address.
The runtime can therefore be used as a local rehearsal, CI contract command,
or a handoff receipt without accessing a network service.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive .\out\execution-packet --destination .\out\execution-packet.zip --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-verify .\out\execution-packet.zip
python -m glio_noncode module-workbench-execution-packet-archive-load .\out\execution-packet.zip
python -m glio_noncode module-workbench-execution-packet-archive-chunk .\out\execution-packet.zip --chunk-size 4096 --limit 5
python -m glio_noncode module-workbench-execution-packet-archive-runtime .\out\execution-packet --chunk-size 4096 --unpack-destination .\out\unpacked
```

## Archive reconciliation and indexing

`diff_module_workbench_execution_packet_archives` compares two verified
containers without source access. It classifies every member as `added`,
`removed`, `modified`, or `unchanged`, retains left and right descriptors,
calculates archive/payload/entry deltas, and reports exact-byte identity,
packet compatibility, and format compatibility. The diff itself is addressed
and conserves both member sets. It can be queried by resource, change kind,
relative member path, entry kind, free text, offset, and bounded limit.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-diff .\out\left.zip .\out\right.zip
python -m glio_noncode module-workbench-execution-packet-archive-diff .\out\left.zip .\out\right.zip --resource modified
python -m glio_noncode module-workbench-execution-packet-archive-diff .\out\left.zip .\out\right.zip --format csv --output archive-diff.csv
```

The archive index is a path-free catalog of already verified archives. It
retains no binary payloads and no source locations. Each record carries its
archive and packet addresses, byte totals, member counts, acceptance state,
and nested content address. The index conserves record counts and bytes,
groups records by packet address, identifies duplicate archive addresses, and
supports address resolution when a group is unambiguous. Archive, packet,
duplicate, and summary resources have bounded filters and stable exports.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-index .\out\left.zip .\out\right.zip --resource duplicates
python -m glio_noncode module-workbench-execution-packet-archive-index .\out\left.zip .\out\right.zip --resource packets --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-index-schema
python -m glio_noncode module-workbench-execution-packet-archive-index-capabilities
```

Archive transport, diff, and index schemas expose their version, boundary,
resources, filters, limits, output types, deterministic/offline guarantees,
and identity-free status. Capabilities enumerate each operation rather than
implying that a broad endpoint is supported. The direct HTTP routes build the
current public aggregate in memory and expose archive, transfer, runtime, and
diff contracts as read-only projections; filesystem archive comparison and
multi-archive indexing remain explicit CLI or Python operations.

## Durable archive object store

The archive store is the next persistence boundary above individual packet
archives. It separates a canonical `manifest.json` from an `objects/`
directory containing exact ZIP bytes. The public manifest retains only typed
archive descriptors and deterministic object keys; binary payloads stay in the
object directory and are never embedded in JSON, query rows, or capability
projections.

Store construction sorts archive inputs by address, stores each exact byte
stream once, and records every registration in an addressed append-only
journal. A repeated byte-identical archive creates a `deduplicate` operation
without another object. Each operation links to the previous head, so the
store head is a compact journal commitment. Appends accept an optional
expected-head address and reject stale writers. Store addresses include the
full manifest descriptor, while object addresses include exact archive bytes.

The writer stages a sibling directory, writes canonical UTF-8 manifest bytes,
flushes the manifest, and atomically replaces the destination. Existing
destinations require an explicit replacement flag. The loader refuses symlinked
directories, symlinked objects, unsafe object tokens, missing objects, extra
objects, non-regular files, malformed JSON, and any failed verification.

Verification covers manifest shape, entry and operation addresses, journal
continuity, exact object hashes, store address, public-boundary keys, count
conservation, and storage policy. A replay receipt reloads every stored ZIP,
rehydrates its packet, and proves its archive and packet addresses against the
manifest. Store queries are bounded and support summary, entry, and operation
resources; store diffs compare catalog entries, journal operations, heads, and
byte totals without unpacking binaries.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store .\out\left.zip .\out\right.zip --destination .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-verify .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-load .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-replay .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-query .\out\archive-store --resource operations --limit 10
python -m glio_noncode module-workbench-execution-packet-archive-store-diff .\out\left-store .\out\right-store --format csv
python -m glio_noncode module-workbench-execution-packet-archive-store-runtime .\out\left.zip .\out\right.zip
```

## Archive-store checkpoints

An archive-store checkpoint captures the store ID, addressed manifest, head,
conserved counts, operation-address sequence, and entry-address sequence. It
contains no binary data and no filesystem path. A current store can be
compared with an exported checkpoint to produce one of four explicit states:
`matched`, `extended`, `diverged`, or `blocked`. `extended` is accepted only
when the current operation and entry sequences retain the checkpoint as an
exact prefix. The comparison reports added and missing operation or entry
addresses, making a stale or forked journal inspectable instead of silently
merging it.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint .\out\archive-store --output .\out\archive-checkpoint.json
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint-compare .\out\archive-store .\out\archive-checkpoint.json
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint-query .\out\archive-store .\out\archive-checkpoint.json --resource added_operations
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-checkpoint-capabilities
```

## Archive-store recovery diagnostics

Recovery inspection is a read-only storage diagnostic for directories that may
be too damaged to load as typed stores. It never mutates the target and never
returns the inspected path. It checks the directory boundary, manifest
readability and canonical bytes, entry shape, safe object tokens, object
directory presence, regular non-symlink objects, exact object-byte addresses,
declared/actual object-set conservation, and the identity-free public key
boundary. Each check is an addressed finding; the report conserves passed and
blocked counts and remains exportable even when the store is blocked.

This distinction is useful operationally: the normal store loader answers
“can this store be trusted and hydrated?”, while recovery inspection answers
“which storage invariant prevented hydration?” Missing and extra objects,
symlinks, malformed manifests, non-canonical bytes, and byte tampering are
reported without attempting repair or silently rewriting data.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery .\out\archive-store
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery .\out\archive-store --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery-query .\out\archive-store --plane objects --limit 20
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-recovery-capabilities
```

## Archive-store replication and promotion

Replication compares two verified archive-store directories as one logical
append-only lineage. The plan proves source and target identity, checks that
the target operation and entry sequences are exact prefixes of the source,
accounts for every source object as `reuse`, `copy`, or `conflict`, and
accounts for every journal operation with the same explicit action set. A
diverged journal, foreign store ID, stale expected head, failed object check,
or operation-ID conflict is represented as blocked and cannot be applied.

The plan is read-only and path-free. It contains addresses, counts, bounded
actions, required byte totals, and independent safety checks; it never embeds
ZIP bytes, filesystem locations, timestamps, or identity metadata. A matching
boundary is an accepted noop. An accepted append-only extension is applyable
only through an explicit destination operation. Apply re-verifies both stores,
rebuilds the plan to reject stale callers, atomically writes the source
boundary, reloads it, and returns a path-free receipt. Promotion remains held
until that receipt proves that the target address equals the source address.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication .\out\source-store .\out\target-store --expected-target-head-address module-workbench-execution-packet-archive-store-operation:... --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-query .\out\source-store .\out\target-store --resource entries --action copy
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-runtime .\out\source-store .\out\target-store --apply --destination .\out\promoted-store
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-runtime-capabilities
```

The apply operation is deliberately separate from planning so offline review,
CI validation, and transport scheduling can inspect the exact transfer before
any destination replacement. Re-running an identical plan produces the same
addresses, while a changed target head produces a different plan and is
rejected before writing.

### Portable replication packets

The replication packet is a portable review bundle for the plan and promotion
decision. It writes a canonical `packet.json` manifest plus a fixed artifact
set under `artifacts/`: plan JSON/CSV/Markdown, a bounded summary query, and
the promotion decision. Runtime JSON/CSV and an apply receipt are added when
those typed values are supplied by a caller. Each file has its own byte count
and content address; the manifest has its own address. Packet loading rejects
missing or extra files, non-canonical manifests, symlinks, byte tampering, and
public fields that would identify a private runtime or operator.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet .\out\source-store .\out\target-store --destination .\out\replication-packet --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-query .\out\source-store .\out\target-store --resource artifacts --role plan
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-replay .\out\replication-packet
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-schema
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-query-capabilities
```

The packet command is deterministic for the same verified source and target:
repeated builds produce the same manifest and artifact addresses. Persistence
uses an atomic directory replacement and requires an explicit existing-target
override, while replay is read-only. API routes mirror the CLI under
`/v1/module-workbench/execution/packet/archive/store/replication/packet`.

## Packet-to-packet diff and assurance

The packet diff layer compares two already persisted packet directories. It
loads both manifests through the same fail-closed packet verifier, then emits
one addressed artifact row per artifact ID. Rows preserve both content
addresses and byte counts, and classify the action as added, removed,
unchanged, or changed. Required removals, rejected candidate packets,
non-canonical boundaries, and public-key violations are explicit checks; no
binary payload is embedded in the diff.

The aggregate state is `matched` when packet addresses agree, `extended` when
the candidate adds only accepted artifacts, `changed` when existing artifact
bytes differ, `diverged` for other incompatible boundaries, and `blocked` when
verification or required conservation fails. A release object turns this
into `promotable`, `hold`, or `blocked`. Only matched and accepted extension
boundaries with no changed or removed artifacts can be promotable.

The diff runtime is a six-stage typed handoff: load, verify-left,
verify-right, compare, release, and complete. Each stage carries a source or
result address and is independently verified. Bounded query projections cover
summary, artifacts, checks, release checks, and runtime stages with action,
acceptance, kind, state, text, offset, and limit filters.

Independent assurance is a separate addressed aggregate rather than a
relabeling of the diff. It conserves finding counts and score, classifies
findings by info/warning/blocker severity, and evaluates release readiness.
Warnings produce a review hold; blockers produce a blocked report. JSON, CSV,
Markdown, query, schema, and capabilities projections exclude paths,
timestamps, private fields, and attribution metadata.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff .\out\left-packet .\out\right-packet --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-query .\out\left-packet .\out\right-packet --resource artifacts --action changed
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release .\out\left-packet .\out\right-packet --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-runtime .\out\left-packet .\out\right-packet --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-assurance .\out\left-packet .\out\right-packet --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-assurance-query .\out\left-packet .\out\right-packet --resource findings --severity blocker
```

The HTTP routes use the same contract beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff`.
Schema and capability routes are filesystem-independent; diff, release,
runtime, assurance, and query routes require URL-encoded left and right
packet directories. A consumer can verify every returned aggregate or query
address offline.

## Multi-packet diff matrices

For a release window, the batch layer evaluates multiple packet pairs with
the same fail-closed comparison contract. Pair specifications are supplied as
`PAIR_ID=LEFT_DIRECTORY=RIGHT_DIRECTORY`; the pair identifier is the only
caller-provided label retained in the public projection. Every row includes
the diff address, release address, state, release state, acceptance, release
readiness, score, and bounded detail. The aggregate conserves item counts,
state counts, release counts, and score, making partial or reordered matrix
results detectable.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-batch `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --pair "review=.\out\base-packet=.\out\candidate-packet" --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-batch-query `
  --pair "review=.\out\base-packet=.\out\candidate-packet" --state diverged --limit 20
```

The batch API accepts repeatable URL query values named `pair` beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/batch`.
It returns an addressed matrix or bounded query response; schema and
capability routes do not inspect packet directories.

## Policy-governed release-window handoffs

The release-window layer turns a matrix into a policy-bound handoff. The
default policy requires at least one pair, a score of one, no held or blocked
pairs, no changed artifacts, no required removals, and all pairs accepted and
release-ready. Every threshold can be changed explicitly. The decision retains
eleven checks with observed values, expected values, severity, detail, and
remediation so a hold or block is reviewable rather than a bare boolean.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --minimum-score 1.0 --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-runtime `
  --pair "matched=.\out\base-packet=.\out\base-packet" --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-assurance `
  --pair "matched=.\out\base-packet=.\out\base-packet" --format markdown
```

The seven-stage runtime is load, verify-matrix, resolve-policy, evaluate,
audit, release, and complete. If policy checks block the window, audit is
blocked and release/complete are skipped. Independent assurance has its own
addressed findings and can be queried by severity and pass state. All window,
runtime, assurance, and query projections are bounded, deterministic,
path-free, timestamp-free, and identity-free.

## Release-window policy sensitivity

Sensitivity analysis compares several explicit policies over one verified
packet-diff matrix. It preserves each scenario's policy and window addresses,
conserves promotable, hold, blocked, and accepted counts, and selects a stable
best-promotable reference for review. That reference is only an analysis
pointer: sensitivity output is always marked analysis-only and never grants
approval or mutates a packet store.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --scenario "strict=1.0=0" `
  --scenario "review=0.0=1" `
  --allow-held --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-sensitivity-query `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --scenario "strict=1.0=0" --resource scenarios --state promotable
```

The HTTP sensitivity family is available beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/sensitivity`.
Operational requests accept repeatable `pair` and `scenario` values;
`scenario=SCENARIO_ID=MINIMUM_SCORE=MAXIMUM_HOLD_COUNT` keeps policy variation
explicit while shared bounds remain visible. Scenario pages are bounded and
support state, readiness, acceptance, and text filters.

## Release-window decision ledger

The review layer records an explicit human-readable decision against the
verified release window and independent packet assurance. Entries support
`promote`, `hold`, `block`, and `supersede`. Every entry is content-addressed,
ordered, linked to the previous entry, and retained in an append-only ledger.
Promotion is fail-closed: the window and packet assurance must already be
release-ready, the entry must have no required actions, and the current head
must be an explicit promote decision. Holds, blocks, and supersessions retain
bounded required actions so the next review step is visible without storing
reviewer identity or private metadata.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review `
  --pair "matched=.outase-packet=.outase-packet" `
  --decision "promote=promote=verified evidence is ready for handoff" --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime `
  --pair "matched=.outase-packet=.outase-packet" `
  --decision "promote=promote=verified evidence is ready for handoff" --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance `
  --pair "matched=.outase-packet=.outase-packet" `
  --decision "promote=promote=verified evidence is ready for handoff" --format markdown
```

The review query returns bounded ledger summaries or entries with decision,
state, readiness, acceptance, action, and text filters. The runtime exposes
seven fail-closed stages; independent review assurance checks evidence links,
chain continuity, decision semantics, action accounting, head closure, and
runtime linkage. The review diff compares two revisions and classifies them
as exact, append-only, or divergent, with one bounded action per entry.
Operational routes are beneath
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review`.
All review projections are deterministic, path-free, timestamp-free, and
identity-free.

## Durable release-window review stores

The review-store layer persists the decision ledger without creating a second
approval authority. A store is a deterministic index over one addressed
ledger and its public checks. Its exact directory contains a manifest, the
canonical ledger projection, and a canonical operation journal. The journal
starts with a genesis record and can grow only through addressed append
operations. Writes are staged beside the destination and atomically replaced;
existing destinations require an explicit overwrite flag.

Loading rechecks the exact artifact set, regular-file boundary, UTF-8
canonical JSON, manifest byte counts and byte addresses, operation equality,
ledger address, aggregate address, and hydrated head. Replay compares the
persisted head and entry count to the rehydrated ledger. An expected-head
guard makes concurrent append attempts fail closed. Bounded queries expose
summary, operations, checks, and ledger entries, with deterministic JSON, CSV,
and Markdown renderings.

The durable runtime emits eight content-addressed stages. Independent
assurance recomputes linkage, head conservation, operation continuity,
replay, public boundary, readiness, and acceptance, classifying an empty
store as blocked and a held store as a warning. Store diffs compare ledger
entry IDs and addresses and prove exact, append-only, or divergent history.
All public output is path-free, timestamp-free, and identity-free.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --decision "promote=promote=verified evidence is ready" `
  --destination .\out\review-store --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-runtime `
  --pair "matched=.\out\base-packet=.\out\base-packet" `
  --decision "promote=promote=verified evidence is ready" --format markdown
```

## Durable review-store catalogs and federation

The catalog continuation indexes multiple durable review-store directories
without merging their ledgers or creating a second approval authority. Build
requires one or more `--store-directory` values. Stores are sorted by their
public store ID, then represented by addressed catalog entries containing the
store, ledger, head, evidence-window, state, acceptance, and readiness links.
The catalog retains a genesis operation plus one registration operation per
member, so the registration history is deterministic and append-only.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog `
  --store-directory .\out\review-store-a `
  --store-directory .\out\review-store-b `
  --catalog-id release-window-catalog `
  --destination .\out\review-store-catalog --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-query `
  --catalog-directory .\out\review-store-catalog --resource entries --release-ready --limit 20
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-runtime `
  --catalog-directory .\out\review-store-catalog --format markdown
```

The catalog directory contains exactly `review-store-catalog.json`,
`review-store-catalog-entries.json`, and
`review-store-catalog-operations.json`. The loader verifies canonical bytes,
manifest addresses, artifact counts, the registration chain, and the catalog
address. Query receipts expose summary, entries, operations, and checks with
bounded filters and deterministic addresses. The eight-stage runtime then
reconciles evidence windows, resolves the release set, and distinguishes a
completed ready catalog from an accepted held catalog or a blocked catalog.

Federation selects a bounded release collection from a loaded catalog. It can
require one evidence window and unique ledgers, select explicit store IDs,
enforce minimum member and ready counts, and report ready, held, mixed, blocked,
or empty state. A held member is accepted as valid evidence that is not yet
release-ready; a blocked member or unknown selection fails closed.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-federation `
  --catalog-directory .\out\review-store-catalog `
  --require-same-window --require-unique-ledger --minimum-members 2 `
  --minimum-ready 2 --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-federation-query `
  --catalog-directory .\out\review-store-catalog --resource checks --passed-only
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-diff `
  .\out\review-store-catalog-base .\out\review-store-catalog-current --format markdown
```

Catalog diffs compare store IDs and entry addresses, classifying exact,
append-only, or divergent revisions with added, removed, unchanged, and
changed actions. All catalog and federation projections are path-free,
timestamp-free, identity-free, and safe to run against downloaded public data.
The same contracts are available through the HTTP family under
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog`,
including query, runtime, federation, diff, schema, and capability routes.

## Catalog assurance and release gate

Catalog verification proves the typed collection is structurally valid. The
independent assurance command recomputes the collection relationships again
and records one addressed finding for each assurance plane. It checks the
aggregate address, version and boundary, entry and journal conservation,
predecessor links, evidence windows, optional hydrated members, acceptance,
readiness, and the public projection. A valid held catalog produces a warning
and remains accepted; a rejected member or broken relationship produces a
blocker.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance `
  --catalog-directory .\out\review-store-catalog --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-assurance-query `
  --catalog-directory .\out\review-store-catalog --plane readiness --limit 20
```

The release gate combines the catalog, its eight-stage runtime, the selected
federation, and independent assurance. Structural checks are required and
block the gate when they fail. Readiness checks are non-required warnings, so
the gate can report a valid held collection without treating it as release
ready. Release closure requires a ready catalog, a completed runtime, a ready
federation, and assurance without warnings.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate `
  --catalog-directory .\out\review-store-catalog `
  --require-same-window --require-unique-ledger --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-gate-query `
  --catalog-directory .\out\review-store-catalog --plane linkage --passed --limit 20
```

The gate and assurance projections are deterministic, bounded, path-free,
timestamp-free, and identity-free. Their schema and capability commands are
also exercised by GitHub Actions, and the HTTP equivalents live below
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/assurance`
and `/gate`.

## Portable catalog release packet

The packet closes the handoff boundary above catalog, runtime, federation,
assurance, and gate. It builds one deterministic manifest plus five canonical
component artifacts:

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet `
  --catalog-directory .\out\review-store-catalog --format summary
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-query `
  --catalog-directory .\out\review-store-catalog --kind gate --limit 10
```

The persisted packet contains exactly `manifest.json`, `catalog.json`,
`runtime.json`, `federation.json`, `assurance.json`, and `gate.json`. The
manifest conserves artifact order, component addresses, exact byte counts, and
byte hashes. Writes are atomic and refuse an existing destination unless the
caller explicitly opts into overwrite. Loading rejects symlinks, extra or
missing files, non-canonical JSON, manifest mutations, kind/file mismatches,
byte tampering, and nested component address divergence. Successful loads
rehydrate all five typed objects and rerun their component verifiers.

Ready packets are accepted and release-ready. Held packets are accepted but
not release-ready. Blocked packets are preserved as valid rejected transport
records so the failure evidence can be moved and inspected without being
mistaken for release approval. JSON, CSV, and Markdown renderings are
deterministic, and packet queries return bounded, addressed receipts. HTTP
routes mirror the CLI under
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet`;
base/query schema and capability routes are included. The public packet is
path-free, timestamp-free, and free of attribution, agent/model/language, and
other identity-bearing fields.

## Catalog packet diff and review

Two persisted catalog packets can be compared without reopening the source
catalogs. The diff loader verifies both exact six-file packets, aligns the
five fixed artifact kinds, and emits one addressed action per kind. Actions
carry left/right component and byte addresses, byte counts, and changed
fields; the aggregate conserves unchanged, changed, added, and removed counts.
The diff also records whether the packet addresses are exact and whether the
right-hand release is unchanged, promoted, held, blocked, recovered, or
regressed. Its six checks independently verify packet boundaries, artifact
conservation, action addresses, state classification, transition vocabulary,
and the public boundary.

```powershell
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff `
  --left-packet-directory .\out\packet-a `
  --right-packet-directory .\out\packet-b --format markdown
python -m glio_noncode module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-diff-query `
  --left-packet-directory .\out\packet-a `
  --right-packet-directory .\out\packet-b --resource actions --action changed
```

The review object is an append-only decision chain over these diffs. Its
default decision promotes a fully accepted, release-ready right packet,
holds accepted but not-ready evidence, and blocks failed or blocked evidence.
Callers can explicitly hold, block, supersede, or promote when the typed
constraints permit it. Each entry retains the prior head address and the
review head becomes the entry address. An expected-head argument rejects
stale concurrent appends, while a non-contiguous left packet rejects a
skipped transition.

Review persistence contains exactly `manifest.json` and `review.json`. Both
files are canonical and byte-addressed; writes are atomic, overwrite is
explicit, and loads reject symlinks, extra or missing files, noncanonical
JSON, manifest/document mismatches, and tampered nested entries. Diff and
review base/query schema and capability projections are exposed through the
CLI and HTTP API, with deterministic JSON, CSV, Markdown, and addressed query
receipts. These public projections remain path-free, timestamp-free, and
free of attribution, agent/model/language, and identity-bearing fields.

## Independent packet-review assurance and release gate

The packet review boundary records the typed decision, but a release system
also needs a second computation that can challenge the decision builder. The
packet-review assurance module performs that computation. It verifies the
review chain and entry addresses, recomputes the promote/hold/block/supersede
policy, checks the review head and readiness classification, and audits the
public projection. When a packet diff is supplied, it additionally verifies
the diff and the review head's diff address, packet endpoints, acceptance, and
readiness. These checks become ordered findings with warning-versus-blocker
severity, expected and observed values, explicit pass state, and addressed
receipts.

Assurance acceptance means every finding passed. Assurance release readiness
also requires a ready review whose own evidence is release-ready. Consequently
hold and supersede decisions can be preserved as accepted, reviewable
evidence without being mistaken for a promotion. Failed findings remain
inspectable and can be persisted as rejected evidence only through a verified
record, allowing operators to audit why a candidate did not advance.

The release gate consumes the diff, review, and assurance projections. It
recomputes component links, component acceptance, decision closure, readiness,
and state. The only ready gate is an accepted promote decision over ready
evidence and independent assurance. Accepted non-ready decisions are `held`;
failed gate checks are `blocked`. The gate has its own ordered checks and
verification receipt so a caller can verify the aggregate without rehydrating
the source packet directories.

Assurance persistence publishes exactly `manifest.json` plus `assurance.json`.
Gate persistence publishes exactly `manifest.json` plus `gate.json`. Both
writers stage a sibling directory and atomically publish it. Both loaders
enforce canonical JSON, exact file sets, regular files, manifest addresses,
document byte counts, document byte addresses, nested content addresses, and
independent verification. Their query planes are bounded, content-addressed,
and available as summary, finding/check rows, JSON, CSV, and Markdown.

The corresponding CLI commands are:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-assurance-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-query
```

Each family also provides base and query schema/capability commands and HTTP
resources beneath the packet-review route. Responses remain path-free,
timestamp-free, and identity-free.

## Longitudinal observatory and runtime

The history observatory consumes one or more persisted history archives rather
than source packet directories. It sorts observations by their explicit
ordinal, keeps history and terminal-gate addresses, and classifies every
adjacent pair. This makes repeated downloads, identical reruns, promotions,
recoveries, regressions, holds, blocks, and supersessions inspectable without
timestamps or local paths. Its rollup checks prove conservation across
observations, transitions, decisions, and states.

The observatory commands are:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-verify
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-observatory-runtime-query
```

The build commands accept repeatable `--history-directory` arguments and can
write exact-byte archives. Query commands support summary, observations,
transitions, checks, verification, stages, and policy checks. The runtime
applies a bounded policy to the conserved observatory and emits load, verify,
policy, project, and complete stages. A failed policy remains an explicit
held/blocked result and never becomes a ready release by omission.

The HTTP family is rooted at:

```text
/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history/observatory
```

It exposes base/query/schema/capability/verification resources and a nested
`/runtime` family with policy schema and capability resources. All response
projections are deterministic, path-free, timestamp-free, and identity-free.

## Longitudinal packet-review gate history and replay

The packet-review gate history extends the single gate receipt into a durable
sequence of release decisions. Its first entry records the gate head and each
later entry is an immutable projection of a newly verified gate. Entries carry
contiguous ordinals, their gate content address, the prior history head
address, decision closure, state, acceptance, release readiness, explanation,
and their own content address. The history head always projects the last
entry, while promote/hold/block/supersede counters are conserved across the
whole sequence.

The public decision table is explicit:

| Decision | State | Accepted | Release ready |
|---|---|---:|---:|
| promote | ready | true | true |
| hold | held | true | false |
| supersede | held | true | false |
| block | blocked | false | false |

An expected-head argument provides a bounded optimistic concurrency guard for
append callers. A stale expected head or repeated gate address is rejected;
no merge or implicit fork is attempted. Accepted blocked history remains
valid audit evidence even though the current release decision is not ready.

History storage is canonical and atomic. The exact directory contains only
`manifest.json` and `history.json`; the manifest binds the embedded public
document to its byte count, byte address, and manifest address. The loader
rejects unknown files, symlinks, noncanonical bytes, mismatched manifests,
tampered nested entries, invalid addresses, and failed structural checks.
All history JSON, CSV, Markdown, and bounded query outputs are deterministic,
path-free, timestamp-free, and free of attribution fields.

The history CLI family is:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-schema
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-capabilities
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query-schema
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-query-capabilities
```

The HTTP family is nested at
`/v1/module-workbench/execution/packet/archive/store/replication/packet/diff/release-window/review-store/catalog/packet/review/gate/history`.
It provides the history, query, schema, capability, query-schema, and
query-capability resources. Directory locations are input-only and never
appear in a response.

The replay module reconstructs the `start`-to-terminal state sequence without
re-reading source directories. It retains gate and entry head addresses,
recomputes decision/state closure, checks transition continuity, independently
projects the terminal state, and emits an addressed replay report. Its query
plane exposes summary, events, and checks with bounded decision, before-state,
after-state, acceptance, readiness, text, and paging filters. Replay exports
are available as JSON, CSV, and Markdown and reject reports whose source
history or replay receipt is not accepted.

Replay commands are:

```text
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-schema
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-capabilities
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query-schema
module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-store-catalog-packet-review-gate-history-replay-query-capabilities
```

## Portable observatory closure packet

The observatory packet closes the longitudinal boundary into one transportable
handoff. It packages the verified observatory, a freshly recomputed packet
verification receipt, the release policy, and the five-stage runtime. The
runtime is replayed during independent verification, so a caller cannot
replace a policy result with a structurally plausible but inconsistent report.
The packet retains accepted held and blocked evidence without projecting it as
ready.

The packet address deliberately excludes only the recursive verification link
and artifact list. The verification receipt checks the packet address,
artifact order and file names, nested observatory/policy/runtime links,
observatory verification, runtime replay, state/readiness projection, and
the public boundary. This produces a finite address graph while retaining
explicit link checks.

Persistence is exactly these five canonical files:

```text
manifest.json
observatory.json
verification.json
policy.json
runtime.json
```

The manifest records the packet metadata and four artifact receipts. Each
artifact binds its file name, byte count, byte address, and content address.
The writer stages a sibling directory and atomically publishes it. The loader
rejects symlinks, extra or missing files, noncanonical bytes, stale manifest
addresses, byte mismatches, stale nested addresses, and failed independent
verification.

The CLI packet command can build from a persisted observatory directory or
repeatable history directories; it can write the exact handoff and emit
summary, JSON, CSV, or Markdown. The query command exposes summary, artifact,
verification, observation, transition, runtime-stage, and policy-check rows.
The API mirrors these operations beneath the observatory `/packet` route.
All packet projections are deterministic, path-free, timestamp-free, and
free of attribution, agent, model, language, and identity fields.

## Multi-packet observatory registry

The registry provides the collection boundary above individual closure
packets. It accepts fully verified packet directories, sorts them by packet ID
and address, rejects duplicates, and emits one addressed entry per packet.
The collection conserves state, acceptance, and release-readiness counts. A
collection of only ready packets is ready; accepted non-ready packets produce
held; blocked or rejected packet evidence produces blocked. This is a
transport and review projection, not a scientific ranking.

The exact registry directory contains:

```text
manifest.json
registry.json
packets.json
verification.json
```

`registry.json` stores the public collection summary and entry index.
`packets.json` stores the packet metadata projections used to re-check each
packet address offline. `verification.json` contains independently recomputed
registry findings. The manifest binds all three documents to canonical byte
counts, byte addresses, content addresses, the registry address, and the
verification address. Atomic writes and strict file-set checks make the
registry safe to move between workspaces.

Registry verification detects stale collection addresses, non-contiguous
entries, duplicate IDs or packet addresses, mismatched packet metadata,
count-conservation errors, invalid state projections, stale finding receipts,
and forbidden public fields. Registry queries cover summaries, entry rows,
packet rows, verification summaries, and verification checks with bounded
filters and deterministic JSON, CSV, and Markdown exports.

The CLI accepts repeatable `--packet-directory` inputs and can persist the
registry. The API adds the registry family below
`.../history/observatory/packet/registry`. A registry can therefore be built
from the real downloaded-data packet handoffs produced by the preceding
section, then inspected without reopening the original data source.

## Observatory packet registry federation

Federation is the next collection boundary above packet registries. It loads
portable registries that have already passed their own independent checks,
orders them by stable registry identity and address, and preserves each
registry's packet counts and readiness evidence. It does not combine or rank
scientific findings. Duplicate registry IDs and addresses, rejected registry
evidence, and policy-bound violations remain visible as blocked or held
outcomes.

Federation policy controls minimum and maximum registry counts, the maximum
packet total, blocked and held registry budgets, whether every registry must
be accepted, whether every registry must be release-ready, and whether an
empty federation is permitted. The state projection is `ready` when all
required evidence is ready, `held` when accepted evidence is not release
ready, `blocked` when any required evidence is rejected or blocked, and
`empty` only under an explicit empty policy.

The exact federation handoff contains `manifest.json`, `federation.json`,
`registries.json`, `policy.json`, `verification.json`, and `runtime.json`.
Canonical bytes, byte counts, document hashes, nested addresses, collection
conservation, policy checks, and five runtime stages are independently
verified on reload. The federation query plane supports summaries, registry
rows, packet rollups, verification checks, policy checks, and runtime stages
with deterministic bounded JSON, CSV, and Markdown exports.

The CLI accepts repeatable `--registry-directory` inputs or a persisted
federation directory for query, verification, and runtime replay. The API
adds the federation family below
`.../history/observatory/packet/registry/federation`, including schema and
capability resources. Real downloaded packet registries can therefore be
federated and reloaded offline without returning source paths or attribution
metadata.

## Federation assurance and release gate

The federation release boundary is independently assured before promotion.
Assurance replays the federation verifier and policy runtime, reconciles
registry and packet totals, checks hydrated member addresses, verifies nested
receipt addresses, and audits the public path-free boundary. It records 21
findings with explicit pass, warning, or blocker severity and remediation
text. The release gate then evaluates 15 conserved checks: required failures
produce `block`, optional readiness failures produce `hold`, and a complete
closure produces `promote`.

The gate handoff is a strict three-file package:

```text
manifest.json
assurance.json
gate.json
```

Canonical bytes, byte addresses, file addresses, exact file sets, nested
component links, and deterministic JSON/CSV/Markdown query projections are
verified on reload. The assurance and gate API/CLI surfaces accept a
persisted federation directory as input and write only path-free public
projections. No member scientific claims are merged or ranked by this layer.

## Federation operational review routing

The assurance gate is also projected into an operational review queue. Every
assurance finding and gate check is retained as an addressed queue item with
its record type, plane, kind, severity, pass state, remediation, and source
evidence address. The queue conserves all 36 records and distinguishes clear
records from high-priority review warnings and critical blockers.

Queue persistence is an exact two-file canonical handoff (`manifest.json` and
`review.json`). A separate diff projection compares two queue snapshots by
stable record keys and reports added, removed, unchanged, changed, and
resolved items, plus improved or regressed aggregate state. Both projections
are path-free, bounded, deterministic, and queryable as JSON, CSV, or
Markdown. Source paths and identity-like metadata remain outside this public
boundary.

### Federation review decision handoff

After a federation assurance gate produces its operational review queue, the
decision-ledger layer records adjudication without mutating the queue or
overriding the source release gate. The ledger carries all queue-item metadata,
then appends addressed `acknowledge`, `remediate`, `waive`, `escalate`, and
`reopen` entries with contiguous previous-head links. Remediation requires an
evidence address; critical blocker items cannot be waived; reopening requires a
prior decision; and an expected-head guard rejects stale writers.

Ledger replay derives effective item state and conserved counts. A closed
ledger means operational work is closed, while `release_ready` additionally
requires the original queue to have been release-ready. This distinction keeps
human review evidence separate from promotion authority.

The exact three-file decision package is `manifest.json`, `ledger.json`, and
`entries.json`. It rejects missing, extra, symlinked, non-canonical, tampered,
or incorrectly addressed files. Decision-ledger snapshots also support
deterministic added/removed/unchanged/changed diffs and resolved open-to-closed
queries, all exposed through the CLI and HTTP API.

### Independent review-decision assurance

The decision ledger is checked by a separate assurance plane before it can be
used as a release handoff. The assurance builder does not trust ledger
aggregates alone: it recomputes the ledger address, queue linkage, item
addresses, append-only entry chain, entry-to-item linkage, remediation
evidence, waiver limits, terminal head, count conservation, source-queue
readiness, public boundary, and effective accepted state. These become 12
addressed findings with explicit pass, warning, or blocker severity.

The release gate adds eight conserved checks. The original source queue remains
authoritative, so an accepted-but-held queue can produce a held gate and a
blocked queue produces a blocked gate even after every operational item has
been adjudicated. The assurance handoff is exactly
`manifest.json`, `assurance.json`, and `gate.json`; all bytes, file receipts,
nested addresses, and canonical documents are checked on reload. Bounded
queries and JSON/CSV/Markdown exports are available through the assurance CLI
and decision-prefix HTTP routes.

### Assurance snapshot diffs

Two persisted decision-assurance gates can be compared as an analysis-only
projection. The diff verifies both inputs, joins their findings and checks by
stable plane/kind keys, retains baseline/candidate addresses, and classifies
each row as added, removed, unchanged, or changed. Outcome scoring identifies
improvements and regressions while preserving mixed changes as `changed`.

The exact diff handoff is `manifest.json` plus `diff.json`. Atomic writes,
canonical JSON, byte/file receipts, exact file membership, manifest linkage,
record addresses, bounded queries, and JSON/CSV/Markdown exports are all
verified. CLI and HTTP diff routes are read-only and never mutate either
assurance gate.
