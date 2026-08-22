# Domain 09 topology frontier release format

## Manifest

An accepted release manifest contains:

| Field | Meaning |
| --- | --- |
| `release_id` | stable name for the release view |
| `fixture_id` | source fixture identity |
| `fixture_version` | fixture contract version |
| `run_id` | runtime execution identity |
| `context_key` | exact interpretation context |
| `evidence_boundary` | public aggregate boundary |
| `release_state` | `accepted` only after the quality gate |
| `source_ids` | closed source receipt set |
| `record_count` | number of fixture records |
| `positive_count` | positive record count |
| `control_count` | control record count |
| `bundle_address` | content address of the composed bundle |
| `record_address` | content address of evaluation |
| `release_address` | content address of this manifest |

## Construction rule

`build_topology_frontier_release` rejects a quality report that is not accepted.
It does not create a provisional manifest with an accepted-looking state. A
failed run can still be exported for diagnosis, but it cannot enter the release
path.

## Default counts

The default release has four positive records, twelve controls, sixteen total
records, five source receipts, and four operation metrics. The bundle has nine
stage inputs and the runtime trace has nine stage receipts.

## Release review

Before publishing a release, verify:

1. the run ID matches the runtime result;
2. the fixture version is the intended version;
3. the context key matches all records;
4. source IDs close against the fixture;
5. record counts match evaluation;
6. all four operations are present;
7. every quality check passes;
8. bundle and record addresses have the expected prefix;
9. the release address is recomputed from the manifest body.

## Projection files

The release may be accompanied by receipt CSV, review CSV, review Markdown,
metrics CSV, and a JSON bundle. The JSON bundle is the canonical structured
projection. CSV and Markdown are convenience views over the same run.

## Versioning

Any change to context, boundary, source purpose, issue vocabulary, state mapping,
operation fields, or address calculation requires a new fixture version. A new
version should add a focused control proving the changed boundary and should
update the schema and release documentation together.
