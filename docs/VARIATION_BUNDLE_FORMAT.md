# Variation evidence bundle format

The variation bundle is the compact publication surface for the Domain 01
evidence slice. It is derived from a checked-in fixture and never replaces the
fixture evaluator, data audit, replay report, or quality gate. Its purpose is
to make the accepted/review boundary easy to archive, compare, and review.

## Construction

Build a bundle from the public aggregate fixture:

```powershell
python -m glio_noncode build-variation-bundle `
  examples/variation-public-aggregate.json `
  --output variation-bundle.json
```

The builder executes the fixture evaluator, quality gate, data catalog, scenario
matrix, and contract registry. It then selects compact fields from each report.
Raw operation payloads are not copied into the bundle. The builder refuses to
construct an unknown positive entry and returns a review-state bundle when the
quality gate fails.

## JSON shape

The JSON representation has these top-level fields:

| Field | Meaning |
| --- | --- |
| `bundle_id` | Stable bundle identity, defaulting to fixture identity plus a suffix. |
| `fixture_id` | Source fixture identity. |
| `fixture_version` | Source fixture schema version. |
| `context_key` | Exact six-dimension comparison context. |
| `source_ids` | Sorted source receipt IDs. |
| `quality_state` | `accepted` or `review`. |
| `entries` | Five positive and five review entry summaries. |
| `component_summaries` | Fixture, data, scenario, and quality receipts without raw payloads. |
| `contract_manifest` | Five-operation contract inventory. |
| `evidence_boundary` | Explicit claim limitation. |
| `content_address` | SHA-256 address over the body fields. |
| `accepted` | Derived convenience flag. |
| `entry_count` | Derived total count. |
| `positive_entry_count` | Derived positive count. |
| `review_entry_count` | Derived review count. |

An entry has this shape:

```json
{
  "entry_id": "dbsnp:rs121913502:vrs",
  "entry_class": "positive",
  "kind": "vrs",
  "state": "supported",
  "source_id": "ncbi-clinvar-rs121913502",
  "public_identifier": "dbsnp:rs121913502",
  "content_address": "sha256:..."
}
```

The `kind` field is the declared record kind, not an inferred biological class.
The `state` field is the adapter state. A positive repeat entry can therefore
have state `ambiguous` while the bundle quality state remains `accepted`: the
fixture expects ambiguity and proves that no placement was silently selected.

## Component summaries

The `quality` summary contains:

- overall state;
- pass flag;
- quality check count;
- failed check IDs;
- quality content address.

The `fixture` summary contains the operation check count, state, and fixture
content address. The `data` summary contains data state, record count, and data
content address. The `scenarios` summary contains scenario state, scenario
count, failed scenario IDs, and scenario content address.

The full reports remain available from their dedicated commands. The bundle is
deliberately smaller so it can be attached to a review without duplicating
source payloads.

## Content addressing

The bundle address is computed over:

1. bundle identity;
2. fixture identity and version;
3. exact context key;
4. sorted source IDs;
5. quality state;
6. ordered entry summaries;
7. component summaries;
8. contract manifest;
9. evidence boundary.

Derived convenience fields are excluded from the address. `accepted`, entry
counts, and the address itself are not part of the address input. This keeps
verification stable when a consumer rehydrates a JSON report.

Verify a loaded JSON mapping in Python:

```python
import json
from pathlib import Path

from glio_noncode.variation_bundle import VariationEvidenceBundleBuilder

payload = json.loads(Path("variation-bundle.json").read_text())
assert VariationEvidenceBundleBuilder.verify(payload)
```

Verification is structural and content-address based. It does not re-run the
source fixture. Re-run the quality gate when checking the current implementation
against the current fixture.

## CSV shape

CSV is a row-oriented entry view with this fixed header:

```text
entry_id,entry_class,kind,state,source_id,public_identifier,content_address
```

There is one header and ten data rows for the current fixture. CSV is useful for
sorting and filtering review entries, but it does not carry all component
summaries. Keep the JSON bundle beside a CSV export when both machine and human
consumers need the evidence.

## Markdown shape

Markdown contains:

- bundle identity;
- fixture version;
- exact context;
- quality state;
- bundle address;
- evidence boundary;
- entry table with source IDs and addresses.

Markdown is a presentation format, not a source of truth. Do not parse the
human table to reconstruct operation payloads.

## Format inference

The CLI infers a format from `.json`, `.csv`, `.md`, and `.markdown` output
suffixes. The explicit `--format` option overrides the suffix for a nonstandard
path:

```powershell
python -m glio_noncode build-variation-bundle `
  examples/variation-public-aggregate.json `
  --output review-artifact.txt `
  --format markdown
```

Unsupported format values fail before writing an output file. The writer uses
UTF-8 and LF line endings for reproducible cross-platform content.

## Privacy and scope

The bundle must not include:

- local reference-window sequence values;
- statement bodies or evidence-line attributes;
- patient, participant, donor, or medical-record values;
- credential-like values;
- unbounded raw input records.

It may include public identifiers, source receipt IDs, context keys, issue IDs,
state values, hashes, and contract fields. A source ID is not a patient ID and
must still be backed by a public source receipt in the fixture.

## Review workflow

Use the following workflow for a bundle attached to a code review:

1. inspect the quality state and failed IDs;
2. inspect the exact context and source IDs;
3. verify the bundle content address;
4. compare positive and review entry counts;
5. inspect the dedicated quality report if review state is present;
6. run the scenario matrix for a state-transition view;
7. rerun Actions before treating the bundle as a release receipt.

A bundle in `review` is useful diagnostic output. It is not a release artifact
and must not be relabeled as accepted by a consumer.

## Versioning

The fixture schema and bundle contract are separate versioned surfaces. A
fixture version change requires:

- a migration or explicit rejection path;
- updated fixture and replay tests;
- updated contract documentation;
- a new bundle content address;
- a CI run on every supported Python version.

Adding a field to a bundle requires deciding whether it is address-bearing or a
derived convenience field. Address-bearing fields must be included in the
builder body and verification path. Derived fields must be excluded in both
places.

## Extension rules

When adding a new record kind, update the following in one build:

- `VariationRecordKind`;
- `VariationOperationContract` registry;
- fixture positive record;
- scenario matrix derivation;
- quality-gate record floor and contract check;
- bundle entry mapping;
- JSON/CSV/Markdown tests;
- capability ledger and runbook.

Do not add a record kind that has no negative control. An operation without a
review boundary is incomplete for this repository.
