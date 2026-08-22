# Domain 04 C13-C16 release format

## Release manifest

`ReferenceReleaseManifest` is created from the nine-stage runtime. It carries:

| Field | Meaning |
| --- | --- |
| `release_id` | Stable release decision identity. |
| `fixture_id` / `fixture_version` | Input fixture identity. |
| `context_key` | Exact context inherited from the fixture. |
| `state` | `ready` or `review`. |
| `runtime_address` | Runtime report address. |
| `replay_address` | Replay receipt address. |
| `quality_address` | Quality gate address. |
| `selected_record_ids` | Accepted execution IDs selected for the bundle. |
| `checks` | Twelve manifest readiness checks. |
| `output_format` | `json-v1`. |
| `content_address` | Manifest address. |

The accepted fixture has five selected rows: the accepted provenance row, two
stable annotation rows, the published reference bundle row, and the published
release-gate row. The C14 ignored-field control is structurally accepted and
is retained in the selected receipt projection; the manifest selection is
explicit and test-backed.

`verify_reference_release_manifest` checks the manifest prefix, failed-check
closure, selected-ID uniqueness, and the invariant that a `ready` state cannot
carry failed checks.

## Evidence bundle

`ReferenceReleaseEvidenceBundle` contains sanitized receipt entries with fixed
fields:

| Field | Meaning |
| --- | --- |
| `record_id` | Fixture execution identity. |
| `operation` | Operation value. |
| `role` | Positive or control role. |
| `state` | Observed adapter state. |
| `accepted` | State-derived acceptance Boolean. |
| `issue_codes` | Sorted retained issue codes. |
| `receipt_address` | Execution receipt address. |
| `content_address` | Bundle-entry address. |

The default bundle is accepted-only JSON. The builder also renders NDJSON and
CSV. `verify` checks the bundle address, non-empty entries, duplicate IDs,
entry addresses, and raw-key exclusion. The accepted bundle has five entries.

## Artifact inventory

The inventory has eleven named artifact kinds:

`runtime`, `evaluation`, `metrics`, `policy`, `lineage`, `projection`,
`reconciliation`, `quality`, `replay`, `manifest`, and `bundle`.

Every row contains the source report address, a media type, public visibility,
retention class, and an artifact-row address. The inventory verifier requires
one row for each kind, no duplicate kind, an application media type, and public
visibility.

## Review view and queue

The review view has nine fixed columns and sixteen rows:

`row_id`, `record_id`, `operation`, `role`, `state`, `accepted`, `issue_codes`,
`source_ids`, and `review_priority`.

The queue is a separate projection. It does not change the bundle or manifest.
It contains eleven items for the accepted fixture because provenance review,
drift, bundle blocks, and release blocks are all actionable controls. Queue
order is deterministic: highest priority first, then record ID.

## Export formats

JSON uses sorted keys, two-space indentation, and a terminal newline. CSV uses
fixed columns and pipe-separated issue/source ID lists. The export functions
are pure string functions; the CLI owns optional file output.

```python
from glio_noncode import (
    export_reference_release_bundle_csv,
    export_reference_release_json,
)

json_text = export_reference_release_json(bundle)
csv_text = export_reference_release_bundle_csv(bundle)
```

## Release boundary

The package publishes aggregate reference metadata only. It does not fetch
reference bytes, write to an external source, select a preferred annotation,
infer regulatory effect, or make a clinical classification. Missing license,
checksum, context, identity, availability, or release checks remain reviewable
and block the relevant release operation.
