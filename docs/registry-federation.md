# Package-registry federation

This document describes the package-registry federation boundary in
`glio-noncode`. The boundary consumes already verified package registries. It
does not copy source repositories, infer missing package contents, or publish
local filesystem paths into a public receipt.

## What the boundary does

The federation layer turns one or more registry directories into a deterministic
replication receipt. Every input registry is loaded through the package
registry verifier before it is admitted as a peer. A peer contributes its
registry address, manifest address, package IDs, package addresses, entry
counters, and audit disposition. The federation then computes:

1. The union of package IDs observed across all peers.
2. Missing-package conflicts when a package is present on fewer peers than the
   federation expects.
3. Divergent-package conflicts when a package ID resolves to more than one
   package content address.
4. A quorum-aware federation state and release decision.
5. Address-linked review or blocking actions for every conflict and quorum
   deficiency.

The resulting receipt is public data. It contains no source path, agent field,
model field, programming-language field, author field, or process handle.

## Module boundaries

The family is intentionally split into narrow modules:

| Module | Responsibility |
| --- | --- |
| federation core | Peer receipts, conflicts, actions, reconciliation, five-file persistence |
| federation query | Bounded projections for summary, peers, packages, conflicts, actions, evidence |
| federation audit | Fourteen independent conservation checks |
| federation diff | Peer, package, conflict, and action transition items |
| diff audit | Independent validation of transition counters and item addresses |
| federation runtime | Build, audit, query, and optional atomic persistence composition |
| federation gate | Policy evaluation over state, decision, quorum, conflicts, actions, and audit |
| federation history | Append-only history of addressed federation release receipts |
| federation observatory | Cross-history timeline and bounded state/decision filters |
| federation matrix | Pairwise peer agreement, missing observations, and address divergence |
| matrix audit | Sixteen independent pair, ratio, state, evidence, and address checks |

The core is the only module that computes package-registry federation facts.
Queries and reports are projections. Audits recompute relationships from the
receipt fields. Diffs compare public receipts rather than private directories.
The runtime composes these boundaries without changing their source data.

## Pairwise agreement matrix

`registry_federation_matrix.py` derives an unordered comparison for every peer pair. It is useful when a federation has more than two downloaded registries and an aggregate conflict is not enough to explain the topology of the disagreement.

Each observation reports the peer pair and package union, common/matching/divergent/left-only/right-only counts, a bounded agreement ratio, a consistent or conflicted state, and address-linked evidence. For `n` peers, the matrix has exactly `n(n-1)/2` observations in lexicographic pair order. A one-peer federation is valid with zero pair observations and ratio `1.0`. A pair is conflicted whenever it has a divergent package address or a one-sided package observation; the matrix is conflicted if any pair is conflicted.

The independent matrix audit recomputes all sixteen invariants, including the pair set, package unions, state transitions, ratios, evidence ordering, mapping replay, and content addresses. Audit acceptance means the receipt is internally sound; it does not turn a conflicted matrix into an accepted release.

Build a matrix from three downloaded registries:

```text
python -m glio_noncode.cli registry-federation-matrix \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --peer archive=C:\data\archive-registry \
  --federation-id downloaded-three-peer \
  --format markdown
```

Persisted matrix JSON can be filtered without rebuilding the federation:

```text
python -m glio_noncode.cli registry-federation-matrix-query \
  --input C:\data\matrix.json \
  --state conflicted \
  --format markdown
```

The HTTP equivalent is `GET /v1/registry/federation/matrix` with repeated `peer=ID=DIRECTORY` query values. Matrix schemas and capability responses are available below the same API surface. Matrix exports contain addresses and package IDs, not filesystem paths.

With the downloaded demonstration registries, two equivalent registries produce one consistent pair with ratio `1.0`; the ready-versus-held registries produce one conflicted pair with ratio `0.0`, while the independent audit still passes all `16/16` integrity checks.

## State model

The reconciliation state is determined in this order:

| Condition | State | Decision | Accepted |
| --- | --- | --- | --- |
| No conflicts and healthy peers meet quorum | `consistent` | `accept` | true |
| Missing packages or healthy peers below quorum | `degraded` | `review` | false |
| Any divergent package | `conflicted` | `reject` | false |

The default quorum is the ceiling of half the peer count. A caller may declare
a stricter positive quorum, up to the configured peer limit. A divergence is
always blocking because selecting one address would silently discard another
peer's evidence. Missing content is review severity because it may represent a
stale replica rather than incompatible content.

## Canonical persistence

The federation core writes exactly these members:

| File | Content |
| --- | --- |
| `manifest.json` | version, boundary, federation identity, projection addresses |
| `federation.json` | complete typed federation receipt |
| `peers.json` | peer projection document |
| `reconciliation.json` | conflict and disposition projection |
| `actions.json` | deterministic operator actions |

All JSON is canonicalized. Writes use a sibling staging directory and a final
directory replacement. Reloading checks the exact member set, canonical bytes,
manifest links, projection links, and byte-for-byte package replay. The core
does not accept a partially shaped destination as an overwrite target.

History uses the same approach with `manifest.json`, `history.json`, and
`entries.json`. History entries retain receipt addresses rather than copying
the complete federation payload into every timeline row.

## CLI

Build and persist a federation from registry directories:

```text
python -m glio_noncode.cli registry-federation \
  --peer primary=C:\data\primary-registry \
  --peer replica=C:\data\replica-registry \
  --federation-id release-federation \
  --destination C:\data\federation \
  --format json
```

The command returns exit code `0` for an accepted federation and `2` for a
review or rejection disposition while still emitting the receipt. This makes
it suitable for a GitHub Actions gate that uploads the JSON as an artifact.

Query a persisted receipt:

```text
python -m glio_noncode.cli registry-federation-query C:\data\federation \
  --resource conflicts \
  --severity blocking \
  --format markdown
```

Audit, gate, and compare receipts:

```text
python -m glio_noncode.cli registry-federation-audit C:\data\federation
python -m glio_noncode.cli registry-federation-gate C:\data\federation
python -m glio_noncode.cli registry-federation-diff C:\data\left C:\data\right
```

History and observatory commands consume persisted federation/history
directories:

```text
python -m glio_noncode.cli registry-federation-history \
  --input C:\data\left \
  --input C:\data\right \
  --destination C:\data\history
python -m glio_noncode.cli registry-federation-observatory \
  --input C:\data\history \
  --format csv
```

Every boundary has schema and capability commands. The capability responses
describe the supported resources, limits, prefixes, and output formats without
requiring a private implementation import.

## HTTP API

The local API exposes the same surface under `/v1/registry/federation`:

| Path | Purpose |
| --- | --- |
| `/v1/registry/federation` | Build from repeated `peer=ID=DIRECTORY` values |
| `/v1/registry/federation/query` | Query a persisted federation using `input` |
| `/v1/registry/federation/audit` | Run the fourteen-check audit |
| `/v1/registry/federation/gate` | Evaluate the default release policy |
| `/v1/registry/federation/diff` | Compare `left` and `right` persisted receipts |
| `/v1/registry/federation/history` | Build history from repeated `input` values |
| `/v1/registry/federation/observatory` | Aggregate repeated history inputs |
| `/v1/registry/federation/matrix` | Compare every peer pair from repeated `peer` values |
| `/v1/registry/federation/matrix/audit` | Independently audit a serialized matrix |
| `/v1/registry/federation/matrix/query` | Filter and page a serialized matrix |

Each endpoint supports JSON responses and the projection endpoints also support
CSV or Markdown where their CLI equivalent does. `/schema` and
`/capabilities` routes are available at each module boundary.

## Real-data demonstration

The tested demonstration used two downloaded package-registry directories from
the product handoff. Feeding the same downloaded registry as two replica peers
produced:

```text
state=consistent decision=accept accepted=True
peers=2 packages=1 conflicts=0 actions=0
audit=14/14
```

Feeding the downloaded ready registry beside a downloaded held registry with
the same package ID produced:

```text
state=conflicted decision=reject accepted=False
peers=2 packages=1 conflicts=1 actions=1
conflict=divergent severity=blocking
audit=14/14
```

The query layer returned the expected summary, peer, package, conflict, and
action rows with deterministic offsets. Mapping replay and five-member disk
replay both reproduced the original content address. The runtime composed the
same federation, audit, query, and persistence result into one runtime receipt.

## Integrity and public-boundary rules

Addresses are hashes over canonical public mappings with the content-address
field removed before hashing. Typed objects reject unknown fields, duplicate
IDs, unsupported states, malformed addresses, unbounded sequences, and
filesystem separators in public address lists. Loaders reject non-canonical
JSON and missing or extra files.

The public-surface audit includes every federation schema and capability
projection. The repository-wide inventory count increases when a new public
schema is added, so an accidental omission or an undocumented surface change
causes CI to fail. The Actions workflow compiles all federation modules and
runs the focused federation contract test alongside the existing regression
suite.

## Extension guidance

New federation projections should follow these rules:

- Accept typed verified federation values, not unverified paths, at the
  projection boundary.
- Derive rows from existing addressed fields instead of recalculating package
  semantics in a second location.
- Give every new public row an exact field set and a replayable address.
- Keep pagination bounded and deterministic.
- Add a schema, capability response, focused tests, CLI route, HTTP route, and
  public-surface inventory entry together.
- Add a downloaded-data demonstration when the projection depends on a new
  persistence or reconciliation relationship.
