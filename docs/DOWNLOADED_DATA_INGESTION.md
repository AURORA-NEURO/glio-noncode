# Downloaded-data ingestion

The downloaded-data plane makes a local ZIP inspectable without turning the
package into executable configuration. It accepts a downloaded archive as
input, catalogs safe structured members, applies an explicit selection, parses
bounded records, records immutable lineage, audits the result, and persists an
offline runtime that can be loaded and queried again.

The ZIP is data. Repository source files, old repositories, generated code,
instructions, and prose are never used as a framework for this plane.

## Real ZIP demo

The checked-in demo accepts the product rebuild ZIP as downloaded input. It
selects the 17 data-bearing members and leaves the seven schema documents and
the OpenAPI YAML document outside the record set. This is intentional: schema
declarations describe a boundary, while the ingestion command operates on
selected data records.

```powershell
python examples/downloaded_data_ingestion_demo.py `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  artifacts/downloaded-data-ingestion-demo
```

The current ZIP produces 25 cataloged structured members, 17 selected
members, and 4,030 parsed records. The demo returns a 40-row inspection page,
while the persisted batch retains all 4,030 records. It reports the source,
content addresses, selection, record count, completion state, audit result,
release readiness, and five redacted record metadata samples. It does not print
the full values to the terminal.

The output layout is:

```text
artifacts/downloaded-data-ingestion-demo/
  summary.json
  runtime-audit.json
  runtime-audit.md
  runtime/
    manifest.json
    catalog.json
    selection.json
    batch.json
    audit.json
    query.json
    query-audit.json
    runtime.json
```

The `runtime` directory is an exact eight-file replay bundle. Every artifact
is content-addressed, and the manifest links the component addresses. The
runtime audit recomputes the component relationships and checks that the
replayed runtime is release-ready.

## CLI workflow

Catalog the ZIP first when you want to inspect available members:

```powershell
glio-noncode downloaded-data-catalog `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --format markdown --output catalog.md
```

Run ingestion with explicit member names. Repeat `--member` for every member
you want to read. The command also supports repeatable `--suffix` and
`--data-kind` selectors.

```powershell
glio-noncode downloaded-data-ingest `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --member GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20/03_CAPABILITIES/CORE_CAPABILITIES_256.csv `
  --member GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20/06_DATA_AND_EVIDENCE/DATA_SOURCE_REGISTRY.csv `
  --resource summary --resource records --resource lineage `
  --destination downloaded-data-runtime `
  --format summary
```

For a repeatable saved runtime, provide an output directory. Persistence is
atomic: the completed temporary directory is moved into place only after all
eight files have been written and validated.

```powershell
glio-noncode downloaded-data-ingest `
  C:/Users/murar/Downloads/GLIO_NONCODE_vNext_Product_Rebuild_2026-08-20.zip `
  --suffix .csv --record-limit 100000 `
  --destination downloaded-data-runtime --format json `
  --output downloaded-data-runtime.json
```

Use a smaller explicit `--record-limit` when an input may exceed the bounded
record budget. The default policy is `reject`, which prevents a partial
runtime from being mistaken for a complete result. `--overflow-policy
truncate` is available when partial inspection is desired; the resulting batch
is marked incomplete, retains `dropped_record_count`, and is not release-ready.

Audit, query, and inspect the persisted result:

```powershell
glio-noncode downloaded-data-ingest-audit downloaded-data-runtime `
  --format markdown --output ingestion-audit.md

glio-noncode downloaded-data-ingest-query downloaded-data-runtime `
  --resource records --data-kind delimited --limit 25 `
  --format csv --output records.csv

glio-noncode downloaded-data-ingest-query downloaded-data-runtime `
  --resource lineage --member-name DATA_SOURCE_REGISTRY.csv `
  --format markdown --output lineage.md

glio-noncode downloaded-data-ingest-runtime-audit downloaded-data-runtime `
  --format json --output runtime-audit.json
```

The query resources are `summary`, `records`, `lineage`, and `values`.
Filters include record ID, member name, data kind, shape, field name, and
bounded text search. Pagination is explicit through `--offset` and `--limit`.
The summary row is always useful even when a filter returns an empty page;
empty pages are valid and remain auditable.

## Comparing two ingestions

Ingest two downloaded snapshots with stable member selections, then compare
their record values by the deterministic key `member_name#source_row`:

```powershell
glio-noncode downloaded-data-ingest-diff `
  --left downloaded-data-runtime-left `
  --right downloaded-data-runtime-right `
  --format json --output downloaded-data-diff.json

glio-noncode downloaded-data-ingest-diff-query downloaded-data-diff.json `
  --resource changed --changed-field value `
  --format csv --output changed.csv

glio-noncode downloaded-data-ingest-diff-audit downloaded-data-diff.json `
  --format summary
```

Diff items are classified as `added`, `removed`, `changed`, or `unchanged`.
Changed items include the exact field names that differ and both bounded values;
unchanged items do not duplicate values. Diff and diff-query contracts have
their own audits and content addresses, so comparison output is not an
unverified convenience view.

## Boundary and safety behavior

The ingestion boundary is deliberately strict:

- only regular ZIP members with supported `.json`, `.jsonl`, `.ndjson`,
  `.csv`, `.tsv`, or `.yaml`/`.yml` suffixes are eligible;
- absolute paths, traversal paths, duplicate names, encrypted members, and
  mismatched member digests are rejected;
- UTF-8 decoding is required;
- JSON non-finite constants are rejected;
- JSON/YAML depth, collection size, string size, member size, and record count
  are bounded;
- CSV and TSV headers must be unique, non-empty, and valid public field names;
- YAML support is intentionally conservative and accepts scalar, mapping,
  sequence, and block-scalar structures needed for bounded data inspection;
- unknown contract fields are rejected during replay;
- content addresses are recomputed from canonical values;
- public projections reject attribution and runtime-identity keys such as
  `agent`, `assistant`, `author`, `language`, and `model`;
- schema and OpenAPI files are not silently interpreted as application data
  by the demo selection policy.

Input values remain data and are never executed. A value with a prohibited
public key fails closed rather than being silently rewritten. The source ZIP
used in the demo is a product/planning package, not a clinical measurement
dataset; its records are suitable for exercising ingestion, lineage, query,
replay, and diff behavior only.

## HTTP surface

The same operations are available from the local service:

```text
GET /v1/downloaded-data/catalog?input=<zip-path>
GET /v1/downloaded-data/ingest?input=<zip-path>&member=<member-name>
GET /v1/downloaded-data/ingest/query?input=<runtime-or-batch-json>&resource=records
GET /v1/downloaded-data/ingest/diff?left=<runtime-or-batch-json>&right=<runtime-or-batch-json>
GET /v1/downloaded-data/ingest/runtime/audit?input=<runtime-directory>
GET /v1/downloaded-data/ingest/schema
GET /v1/downloaded-data/ingest/capabilities
```

Paths and query values must be URL-encoded by clients. The HTTP surface uses
the same parser, limits, content-address checks, and fail-closed errors as the
CLI. It is an offline inspection surface; it does not fetch remote sources or
execute archive content.

## Contract inventory

The public surface includes schemas and capabilities for selection, lineage,
records, batches, audits, queries, diff items, diff queries, runtime manifests,
and runtime audits. The repository-wide surface audit counts these contracts
and fails if one is omitted. Focused coverage is in
`tests/test_downloaded_data_ingestion.py`, including all supported fixture
formats, truncation, empty queries, exact-file replay, diff classification,
tamper rejection, and public-schema checks.
