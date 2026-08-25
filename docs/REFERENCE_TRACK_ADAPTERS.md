# Declared reference-track adapters

Reference feature readings must carry the source contract that makes them
usable. The declared adapter boundary composes a public row source with the
columnar interval index and requires the following metadata before atlas code
can consume the result:

- source and adapter identifiers, source release, and adapter version;
- license, URI, and access mode;
- assembly and coordinate convention;
- supported context patterns and channels;
- explicit limitations and bounded retrieval limits; and
- an availability state that can force abstention.

The adapter does not infer activity, disease relevance, or causality. An
overlap is a reference reading only. Absence, out-of-domain context, stale or
provisional data, unavailable artifacts, and invalid requests remain distinct
states.

## Build and query

Rows may be JSON, JSONL, CSV, or TSV. A metadata file uses the fields emitted
by the adapter schema:

    glio-noncode build-reference-adapter tracks.json --metadata track-metadata.json --output declared-adapter.json
    glio-noncode query-reference-adapter declared-adapter.json --chromosome 7 --start 5500000 --end 5600000 --context-key GRCh38|glioma|adult|tumor|brain|baseline --mode lattice --output track-query.json

The build receipt contains the verified adapter, its columnar index, bounded
row issues, and a deterministic build address. Loading an adapter rebuilds the
index and checks the adapter, metadata, row, and block addresses.

## Contract and conformance

The adapter schema and operational capabilities are available from:

    glio-noncode reference-adapter-schema --output adapter-schema.json
    glio-noncode reference-adapter-capabilities --output adapter-capabilities.json

Conformance probes are explicit query objects. A release-accepted adapter
requires declared limitations, a valid manifest artifact, an index round trip,
public-boundary checks, and at least one deterministic probe:

    glio-noncode reference-adapter-conformance declared-adapter.json --probes probes.json --output conformance.json

The conformance report addresses each metadata, artifact, index, invocation,
determinism, context, output, and public-boundary check. Missing or failed
release checks produce review or blocked states rather than silently promoting
the adapter.

## Atlas integration

Pass a ReferenceTrackAdapterRegistry to PublicAtlasRetriever to add declared
track reports to the atlas bundle. Each observation retains the adapter
metadata, license, access mode, source release, query receipt, context score,
limitations, and interpretation boundary. A quarantined or unavailable
artifact yields abstained, not absent. The observation can be converted to a
reference-tier evidence claim without assigning a scientific score.

The registry can emit a versioned ReferenceManifest for all registered
adapters. The manifest contains metadata and source receipts only; it never
embeds the indexed row payload.

## API

- GET /v1/reference/adapters/schema returns the versioned adapter contract.
- GET /v1/reference/adapters/capabilities returns limits and release gates.
- POST /v1/reference/adapters/build accepts metadata plus records or rows.
- POST /v1/reference/adapters/query accepts a serialized adapter and query.
- POST /v1/reference/adapters/conformance accepts an adapter and probes.

All adapter output is recursively checked for attribution, credential,
model, language, and direct-private fields. Public source metadata remains
visible because it is part of the required license and access contract.
