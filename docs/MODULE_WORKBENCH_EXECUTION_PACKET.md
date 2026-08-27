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
