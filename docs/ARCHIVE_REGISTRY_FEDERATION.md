# Archive-registry federation

## Purpose

The archive-registry federation boundary compares independently downloaded
certificate-observatory archive registries.

It is designed for operators who receive the same evidence package from more
than one source and need to know whether the sources agree.

The boundary keeps the source registries separate.

It does not merge entries.

It does not choose one source silently.

It does not replace a missing entry with an empty placeholder.

It does not treat a disagreement as an accepted result.

The output is a public, deterministic receipt.

Every typed object has a content address.

Every derived object retains addresses for the evidence used to build it.

Every persisted runtime has exact members and byte-level artifact receipts.

The result can therefore be inspected, copied, audited, compared, and replayed
without reopening the original download.

## Input contract

Inputs are existing archive-registry artifacts.

Each input may be:

- an exact archive-registry directory;
- a public `registry.json` document;
- a value already loaded by the Python API.

The runtime accepts at most two peers in the current boundary.

The limit is deliberate: it keeps the first federation receipt small enough for
local inspection while leaving room for a later bounded topology layer.

The input registry itself has its own manifest, registry, entries, metrics, and
index contracts.

Federation loading verifies that registry before any comparison is attempted.

Symlinks are rejected at the input edge.

Regular files and regular directories are required.

The federation output never contains an input path.

The caller may supply public peer labels.

When labels are omitted, deterministic labels are derived from registry IDs and
content addresses.

Explicit labels must be unique and must have the same cardinality as inputs.

## Comparison semantics

Entries are keyed by `entry_id`.

For each key, the federation builds an observation across every peer.

An observation contains:

- the entry identifier;
- the package identifier observed by the peers;
- the ordered peer identifiers;
- every observed archive address;
- every observed package address;
- the presence count;
- the expected peer count;
- a state;
- an observation content address.

The state is one of three values.

`consistent` means every peer has the entry and all archive and package
addresses agree.

`missing` means at least one peer lacks the entry.

`divergent` means every peer has an entry but the evidence addresses disagree.

The distinction matters operationally.

A missing result usually means incomplete replication or an older snapshot.

A divergent result usually means the same logical key resolves to different
content and requires investigation.

Neither state is silently promoted to consistency.

The federation summary conserves observation counts.

`consistent_count + divergent_count + missing_count = observation_count`.

`conflict_count = divergent_count + missing_count`.

Peer summaries conserve the registry metrics they project.

The federation content address is computed after all peer and observation
addresses are stable.

The address excludes the address field itself before hashing.

## Audit layer

The federation audit is independent of the federation builder.

Its checks cover:

1. federation content-address replay;
2. peer content-address replay;
3. observation content-address replay;
4. peer cardinality conservation;
5. observation cardinality conservation;
6. peer entry-count bounds;
7. observation presence bounds;
8. state-count conservation;
9. conflict-count conservation;
10. public-boundary safety.

The check order is fixed.

The check identifiers are part of the public contract.

An audit is accepted only when every check passes.

The audit has JSON, CSV, and Markdown serializers.

The serializers verify the typed audit before producing output.

Mapping reload verifies exact field vocabulary.

Unknown fields are rejected rather than ignored.

This prevents a producer from accidentally placing private operational fields
inside a public receipt.

## Query layer

The federation query exposes bounded resources.

The resources are:

- `summary`;
- `peers`;
- `observations`.

Queries can filter by peer, entry, state, package, and bounded text.

Queries accept non-negative offsets and positive limits.

Rows are re-addressed after filtering and pagination.

That means a page can verify its own ordinal sequence.

The query result contains:

- the addressed query specification;
- the federation identifier;
- returned rows;
- total rows before filtering;
- matched rows after filtering;
- rows returned by this page;
- the next offset;
- a truncation flag;
- a result content address.

The page contract is deterministic.

`next_offset = offset + returned_count`.

`truncated` is true only when another matched row remains.

The query audit verifies the query address, result address, row ordering, row
counts, pagination, resource names, state names, evidence retention, row
addresses, and public boundary.

## Diff layer

The federation diff compares two federation receipts.

The diff is keyed by entry identifier.

Each item includes both baseline and candidate states.

It retains baseline archive addresses and candidate archive addresses.

The available actions are:

- `added`;
- `removed`;
- `changed`;
- `resolved`;
- `regressed`;
- `unchanged`.

An added item exists only in the candidate.

A removed item exists only in the baseline.

A changed item remains present but has different projected evidence.

An unchanged item has the same projected evidence.

Resolution and regression actions are reserved for state transitions.

The diff summary conserves item counts.

The diff audit verifies item order, action counts, nested addresses, evidence,
and public output.

The diff query provides summary, item, action-specific, and bounded text views.

Its independent audit verifies all page contracts without using the builder's
internal bookkeeping.

## Quorum layer

The consensus module evaluates each observation independently.

The default quorum is a strict majority.

The caller may supply a positive quorum no greater than the peer count.

For each entry, candidate archive addresses are grouped by support.

A candidate is selectable only when its support meets the quorum.

Every dissenting address remains in the candidate receipt.

An entry with exactly one selectable candidate becomes `selected`.

An entry with no selectable candidate becomes `held`.

The consensus is `ready` and `accept` only when every entry is selected.

Any held entry produces `blocked` and `hold`.

The consensus audit checks candidate and decision order, support conservation,
quorum bounds, selected and held counts, dissent counts, nested addresses, and
public output.

## Report layer

The report composes federation and consensus findings into an operator-facing
health result.

Clean observations do not create alerts.

Missing observations create a missing-evidence alert.

Divergent observations create a divergent-evidence alert.

Held consensus decisions create a quorum alert.

The report carries links to federation, consensus, federation audit, and
consensus audit receipts.

It reports conflict, resolution, held, and alert counts.

The status is `ready`, `review`, or `blocked`.

Only a complete accepted federation and accepted consensus can be `ready`.

The report audit verifies alert order, severity vocabulary, counts, status and
decision linkage, nested receipt addresses, and public output.

## Runtime persistence

The runtime is the complete downloaded-data execution boundary.

It loads every registry input, builds the federation, runs the federation audit,
calculates quorum, builds the consensus audit, builds the report, and audits the
runtime.

The exact runtime members are:

1. `manifest.json`;
2. `runtime.json`;
3. `federation.json`;
4. `audits.json`;
5. `consensus.json`;
6. `report.json`.

No extra member is accepted.

No missing member is accepted.

Every member must contain canonical JSON bytes.

The manifest records member names, sizes, and byte hashes.

The manifest itself has a content address.

The projection files must exactly match the nested runtime values.

The writer uses a staging directory and an atomic replacement.

An existing destination requires explicit overwrite.

The runtime loader validates the exact member set before decoding.

It validates canonical bytes before constructing typed values.

It validates the manifest address and every artifact receipt.

It validates projection equality after typed reload.

The runtime audit separately checks the source count, receipt links, state,
acceptance, audit results, projection addresses, and public boundary.

## Python API

The core builder is:

```python
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation as federation

value = federation.build_federation(
    (primary_registry, replica_registry),
    peer_ids=("primary", "replica"),
    federation_id="downloaded-registry-federation",
)
```

The end-to-end runtime is:

```python
from glio_noncode import registry_federation_consensus_gate_certificate_observatory_archive_registry_federation_runtime as runtime

receipt = runtime.run_runtime(
    ("C:/data/primary-registry", "C:/data/replica-registry"),
    peer_ids=("primary", "replica"),
    quorum=2,
    destination="C:/data/federation-runtime",
)
```

Use `runtime.load_registry_input` when only the registry loader is needed.

Use `runtime.load_runtime` for a persisted runtime directory.

Use `federation.federation_from_mapping` for public JSON.

Use `federation.federation_json` for canonical JSON serialization.

Use `federation.render_federation_markdown` for a compact operator view.

## CLI

Build and persist a runtime:

```text
python -m glio_noncode registry-federation-consensus-gate-certificate-observatory-archive-registry-federation \
  --input C:/data/primary-registry \
  --input C:/data/replica-registry \
  --peer-id primary \
  --peer-id replica \
  --quorum 2 \
  --destination C:/data/federation-runtime \
  --format markdown
```

Audit the federation projection:

```text
python -m glio_noncode registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-audit \
  --input C:/data/federation-runtime/federation.json \
  --format json
```

Query observation evidence:

```text
python -m glio_noncode registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-query \
  --input C:/data/federation-runtime/federation.json \
  --resource observations \
  --state divergent \
  --limit 25 \
  --format csv
```

Run the independent query audit on the saved query output:

```text
python -m glio_noncode registry-federation-consensus-gate-certificate-observatory-archive-registry-federation-query-audit \
  --input C:/data/divergent-query.json \
  --format markdown
```

The diff, diff-query, consensus, report, and runtime-audit commands follow the
same pattern and accept public JSON documents.

Schema and capability commands are available for every typed sub-boundary.

They are included in the public-surface inventory and CI checks.

## HTTP API

The local HTTP namespace is:

```text
/v1/registry/federation/consensus/gate/certificate/observatory/archive/registry/federation
```

The base route accepts repeated `input` and `peer_id` query values.

It returns the runtime projection.

The base route accepts `federation_id`, `runtime_id`, `quorum`, `destination`,
`overwrite`, and `format`.

The `format` values are `summary`, `json`, `csv`, and `markdown` where the
operation supports the representation.

The operation routes are:

- `/audit`;
- `/query`;
- `/query-audit`;
- `/diff`;
- `/diff/audit`;
- `/diff/query`;
- `/diff/query-audit`;
- `/consensus`;
- `/consensus/audit`;
- `/report`;
- `/report/audit`;
- `/runtime`;
- `/runtime/audit`.

Each schema and capability route is available below the same namespace.

The HTTP handler loads source files only at the edge.

The response models remain path-free.

HTTP failures use a structured error response from the shared local API.

## Downloaded-data demo

Run the standalone demo with two registry downloads:

```text
python examples/registry_federation_certificate_observatory_archive_registry_federation_demo.py \
  --input C:/data/primary-registry \
  --input C:/data/replica-registry \
  --peer-id primary \
  --peer-id replica \
  --quorum 2 \
  --destination C:/data/federation-runtime
```

The demo prints only public summaries.

It shows the federation counts, audit result, query page, query audit,
consensus decision, consensus audit, readiness report, report audit, transition
diff, diff audit, diff query audit, runtime audit, and disk replay.

The supplied planning ZIP is not a canonical archive-registry input.

It is therefore not interpreted as evidence by this demo.

To demo with that planning material, first create canonical archive-registry
directories using the archive-registry builder and then pass those directories
to this federation demo.

This keeps planning text separate from evidence receipts.

## Failure triage

If loading fails with an exact-member error, inspect the registry directory for
extra files or missing canonical files.

If a canonical-byte error appears, rewrite the document through the JSON
serializer rather than a generic pretty printer.

If the federation audit fails at a peer address check, the peer registry was
modified after it was addressed or the mapping was altered.

If an observation is `missing`, compare entry IDs before comparing content.

If an observation is `divergent`, inspect the archive and package address arrays
for that entry.

If consensus is `held`, increase evidence coverage or investigate the dissenting
peer; do not force acceptance by deleting the candidate rows.

If the report is `blocked`, query `observations` and then `consensus` for the
entry-level evidence before attempting a new download.

If the diff reports `changed`, inspect both federation receipts and not only the
summary counts.

If a query audit fails row order, regenerate the result through the query API.

If runtime replay fails a projection receipt, treat the runtime as invalid and
rebuild it from the original canonical registry directories.

## Performance notes

The comparison is bounded by peer count and the registry entry limit.

Entry maps avoid repeated scans when the peer registry has many entries.

Observations are emitted in sorted entry order.

Peers are emitted in sorted label order.

Query rows are generated once, filtered once, and re-addressed only for the
returned page.

Serialization uses canonical JSON so equivalent values have identical bytes.

The runtime writes through a staging directory, keeping partial outputs away
from the destination name.

The loader verifies member sets before parsing payloads, which avoids doing
expensive typed construction for an obviously invalid directory.

The runtime stores projections once and reloads them by exact byte comparison.

This makes later inspection cheaper than rebuilding the complete graph.

## Extension boundary

The current boundary intentionally compares registries without a peer transport
protocol.

A future transport adapter can download a registry into a canonical directory,
then call the same runtime.

It must not add transport headers or machine paths to public models.

A future topology layer can support more peers by extending the bounded peer
limit and adding topology-specific receipts.

It must preserve the existing two-peer semantics.

A future policy layer can decide whether a held result blocks a downstream
operation.

It must consume the report and consensus receipts rather than changing their
meaning.

The federation boundary is therefore a stable evidence comparison core for the
next module build.
