# Assurance history observatory archive registry diff

The registry-diff boundary explains how two independently verified observatory
archive registry packages differ. It compares the public registry projections
after each side has passed the exact five-file registry loader. It does not
merge archive payloads, infer scientific findings, or persist filesystem paths.

## Contract

The public module is:

```text
glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff
```

`build_diff` verifies both typed registries, forms the sorted union of entry
IDs, and emits one `RegistryDiffItem` per key. The four actions are:

| Action | Baseline | Candidate | Meaning |
| --- | --- | --- | --- |
| `added` | absent | present | the entry exists only in the candidate |
| `removed` | present | absent | the entry exists only in the baseline |
| `changed` | present | present | one or more public entry fields differ |
| `unchanged` | present | present | the complete public entry projection matches |

Changed items expose the exact fields that differ. Added and removed items
expose the complete bounded entry field set so downstream consumers never need
to guess which side is authoritative. Registry-level changes are tracked
separately, including aggregate metrics, registry identity, and verification
links.

The aggregate diff state is `unchanged`, `improved`, `regressed`, or `mixed`.
It is a conservative explanation derived from source acceptance, readiness,
and registry state; the candidate registry remains authoritative for whether a
release is actually ready.

## Python example

```python
from glio_noncode import (
    build_assurance_history_observatory_archive_registry_diff_from_directories,
    query_assurance_history_observatory_archive_registry_diff,
    render_assurance_history_observatory_archive_registry_diff_markdown,
)

value = build_assurance_history_observatory_archive_registry_diff_from_directories(
    "review-output/baseline-registry",
    "review-output/candidate-registry",
    diff_id="review:observatory-registry-transition",
)
print(render_assurance_history_observatory_archive_registry_diff_markdown(value))
result = query_assurance_history_observatory_archive_registry_diff(
    value,
    resource="readiness-transitions",
    limit=50,
)
print(result.to_dict())
```

The directory helper loads both exact registry packages before comparison.
`diff_from_mapping` is available for typed public inspection, while source
directory comparison always uses the byte-backed loader and its full linkage
checks. Item, diff, and query results have independent content addresses.

## Query resources

`RegistryDiffQuery` provides bounded, deterministic resources:

```text
summary
items
added
removed
changed
unchanged
state-transitions
readiness-transitions
registry-changes
```

Queries support action, text, offset, and limit filters. Result records are
public summaries, and the query itself is included in the result address.
JSON, CSV, and Markdown renderers preserve the same selected records.

## CLI

The command is the registry command with the `-diff` suffix. Both inputs are
registry directories, not raw archive paths:

```powershell
python -m glio_noncode.cli `
  <registry-command>-diff `
  --baseline review-output/baseline-registry `
  --candidate review-output/candidate-registry `
  --format markdown

python -m glio_noncode.cli `
  <registry-command>-diff-query `
  --baseline review-output/baseline-registry `
  --candidate review-output/candidate-registry `
  --resource readiness-transitions `
  --format csv
```

The command family also exposes `-diff-schema`, `-diff-item-schema`,
`-diff-query-schema`, `-diff-query-result-schema`, and `-diff-capabilities`.

## HTTP API

The diff route is nested below the existing registry route:

```text
.../observatory/archive/registry/diff
```

Required query parameters are `baseline` and `candidate`, each pointing to an
exact registry directory. The root route accepts `format=summary|json|csv|markdown`.
The `/query` route additionally accepts `resource`, `action`, `q` or `text`,
`offset`, and `limit`. Schema routes are `/schema`, `/item-schema`,
`/query-schema`, and `/query-result-schema`; `/capabilities` declares the
limits, actions, resources, fields, and public features.

## Integrity and boundary behavior

The diff rejects non-typed registry inputs, unknown fields, malformed nested
entries, forged addresses, duplicate or unsorted item identities, count
mismatches, invalid transitions, path-bearing values, and private or
attribution metadata. It accepts up to 256 diff items (the union of two
128-entry registries) and bounds query windows to 2,048 records.

The diff is an explanation of verified snapshots. It does not turn a changed
archive into an accepted release and does not replace the independent archive
or registry audits.
