# Reference interval index

The reference interval boundary turns public track rows into a deterministic,
bounded, columnar index. It is intended for annotation, cohort context, and
other public reference projections; it does not retain subject-level records,
private credentials, attribution fields, model metadata, or language metadata.

## Input contract

Each row needs a chromosome, a zero-based half-open interval, and a context.
Accepted row spellings are chromosome/chrom/contig, start/position/pos, end,
and context_key or a six-part context mapping. Optional metadata includes
record_id, source_id, track_type, state, tags, payload, and raw_hash.

The six context dimensions are genome_build, disease_class, age_group,
cell_state, territory, and treatment_phase. Context keys use a pipe-delimited
form:

    GRCh38|glioma|adult|tumor|brain|baseline

The normalizer rejects malformed intervals, empty identifiers, invalid
contexts, duplicate record IDs, and payload keys that would cross the public
boundary. Invalid rows are retained only as bounded issue summaries in the
build report.

## Columnar layout

The index stores each normalized field in a parallel immutable column. Rows
are sorted by chromosome, start, end, context key, record ID, and content
address. Chromosome ranges and fixed-size blocks provide block-level minimum
start, maximum end, and prefix maximum-end metadata. Queries can therefore
skip blocks that cannot overlap the requested interval before examining rows.

The index, each block, each row match, and each query report has a deterministic
content address. Loading a serialized index rebuilds the columns and rejects
tampering when the recomputed address differs. The default record limit is
1,000,000, the default block size is 256, and query output is bounded to 5,000
matches.

## Context lattice

Exact mode requires all six context dimensions to match. Lattice mode permits
public track rows to generalize non-assembly dimensions with all, unknown, or
wildcard values. The genome_build dimension never generalizes, which prevents
cross-assembly matches. A query wildcard is an unconstrained dimension.

Results include the matched context, exact and generalized dimensions,
specificity, a stable score, and a reason. Exact matches sort before
generalized matches; ties are resolved by content address. The query report
distinguishes supported, absent, out_of_domain, ambiguous, truncated, and
invalid states.

## CLI

Build an index from JSON, JSONL, CSV, or TSV:

    glio-noncode build-reference-index tracks.json --index-id glioma-track --assembly GRCh38 --block-size 128 --output reference-index.json

Query the serialized index:

    glio-noncode query-reference-index reference-index.json --chromosome 7 --start 5500000 --end 5600000 --context-key GRCh38|glioma|adult|tumor|brain|baseline --mode lattice --limit 100 --output reference-query.json

The build command emits a report containing the normalized index, bounded
issue details, accepted and rejected counts, and a build address. The query
command accepts either that report or the bare index object.

Schema and capability declarations are available from:

    glio-noncode reference-index-schema --output reference-index-schema.json
    glio-noncode reference-index-capabilities --output reference-index-capabilities.json

## API

- POST /v1/reference/index/build accepts records or rows plus index_id,
  assembly, max_records, max_issues, and block_size.
- POST /v1/reference/index/query accepts an index object and a query object.
- GET /v1/reference/index/schema returns the versioned field contract.
- GET /v1/reference/index/capabilities returns limits, query states, context
  dimensions, public-boundary rules, and deterministic ordering guarantees.

API responses use public-safe projections and return HTTP 422 for invalid
builds or queries. An out-of-domain query is a valid, deterministic negative
result and is represented by its query state rather than by a server error.

