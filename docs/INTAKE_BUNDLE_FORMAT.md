# Intake evidence bundle format

`IntakeEvidenceBundleBuilder` creates a compact, content-addressed summary of
the Domain 01 C13-C16 intake evidence gate.  The bundle is deliberately not a
copy of the fixture.  It contains traceable operation summaries, source IDs,
quality receipts, and contract metadata while leaving raw operation payloads
in the source fixture boundary.

## Design goals

The format provides:

- deterministic output from the same fixture and bundle ID;
- one traceable row for every positive record and review control;
- capability and operation identity on every row;
- public identifier and source receipt linkage;
- a content address for each operation receipt;
- component summaries for data, fixture execution, scenarios, and quality;
- a contract manifest that names all four C13-C16 operations;
- JSON, CSV, and Markdown renderings;
- an offline verifier that recomputes the bundle content address.

The format does not include raw policy payloads, raw row values, unrestricted
exception messages, or any record field that is not required to trace the
bounded operation result.  The public fixture remains the authoritative input
for a detailed review.

## JSON envelope

The JSON rendering has this shape:

```json
{
  "bundle_id": "intake-public-aggregate-001-bundle",
  "fixture_id": "intake-public-aggregate-001",
  "fixture_version": "intake-evidence-v1",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "source_ids": ["fixture-validation-controls", "ncbi-clinvar-rs121913502"],
  "entries": [],
  "component_summaries": {},
  "contract_manifest": {},
  "quality_summary": {},
  "content_address": "sha256:<64 hex characters>",
  "state": "accepted",
  "accepted": true,
  "entry_count": 12,
  "positive_entry_count": 4,
  "review_entry_count": 8
}
```

`accepted`, `entry_count`, `positive_entry_count`, and `review_entry_count`
are derived convenience fields.  They are excluded when the verifier
reconstructs the signed body.  The state and quality summary are part of the
addressed body.

## Entry schema

Every entry has exactly these fields:

| Field | Meaning |
| --- | --- |
| `entry_id` | `positive:<record_id>` or `review:<control_id>` |
| `entry_class` | `positive` or `review` |
| `capability_id` | `GNC-D01-C13` through `GNC-D01-C16` |
| `operation` | stable CLI and contract operation name |
| `state` | observed operation state, such as `accepted`, `blocked`, `quarantined`, `review`, or `published` |
| `public_identifier` | source-facing public identity from the fixture |
| `source_id` | source receipt ID used for the envelope |
| `evidence_address` | address of the operation receipt, beginning with `sha256:` |
| `summary` | bounded human-readable result summary |

Entries are sorted by entry class, capability ID, and entry ID.  Sorting is a
format invariant rather than a presentation preference: two local runs should
produce the same entry order and bundle address.

The positive rows in the canonical fixture are:

| Capability | Positive state | Summary source |
| --- | --- | --- |
| C13 | `accepted` | count of active policy attachments |
| C14 | `accepted` | count of rows passing anomaly inspection |
| C15 | `accepted` | weighted mean completeness score |
| C16 | `published` | count of records in the deterministic manifest |

The eight review rows summarize the explicit controls.  A blocked consent row
reports a policy block; an anomaly control reports the quarantined count; a
completeness control reports review count; and a bundle control reports that
export was withheld.  A validation failure is described generically and does
not copy the rejected input into the summary.

## Component summaries

The bundle contains four component summary objects:

```text
component_summaries.fixture
  check_count
  passed_count
  failed_count
  positive_count
  review_control_count

component_summaries.data
  record_count
  control_count
  issue_count
  state

component_summaries.scenarios
  scenario_count
  failed_count
  state

component_summaries.quality
  check_count
  passed_count
  failed_count
  state
```

For the canonical fixture these values are 33 fixture checks, four positive
records, eight review controls, twelve scenarios, and fourteen quality checks.
All component states are accepted when the bundle is accepted.

## Contract manifest

`contract_manifest` is the output of
`default_intake_contract_registry().manifest()`.  It carries:

- `contract_version: intake-contracts-v1`;
- `contract_count: 4`;
- the C13-C16 operation contracts;
- required input fields;
- output fields;
- accepted and review state vocabularies;
- evidence role and external boundary for each operation;
- its own content address.

The quality gate verifies that every positive fixture operation maps to one
contract and that the positive payload has every required field.  This avoids
building a bundle whose rows are traceable but whose input shape is outside
the declared interface.

## Quality summary

The `quality_summary` object contains:

```text
state
passed
check_count
failed_check_ids
evidence_boundary
quality_address
```

The evidence boundary is carried into Markdown so a human reader sees the
limitations next to the table.  `quality_address` links the compact bundle to
the full quality-gate receipt.  A review-state bundle may be rendered with
`--allow-review` for diagnosis, but its `accepted` field remains false and its
state remains `review`.

## Address calculation

The builder addresses this canonical body:

```text
bundle_id
fixture_id
fixture_version
context_key
source_ids
entries
component_summaries
contract_manifest
quality_summary
state
```

The body is serialized with the repository's canonical JSON serializer: sorted
object keys, compact separators, UTF-8, and deterministic enum conversion.
The SHA-256 digest is prefixed with `sha256:`.  The verifier removes only the
derived convenience fields and the stored address before recomputing the hash.

An entry's `evidence_address` is the address of its operation receipt.  It is
not a substitute for the top-level bundle address: the entry addresses make a
row-level trace possible, while the top-level address makes the whole summary
reproducible.

## CSV rendering

CSV is a row-oriented export with one header plus one row per entry.  Its
columns are:

```text
entry_id,entry_class,capability_id,operation,state,
public_identifier,source_id,evidence_address,summary
```

The CSV does not include the component summaries or contract manifest.  Use
JSON when machine consumers need the full envelope; use CSV when a reviewer
needs a flat table; use Markdown when a release note or audit record needs a
readable table with the evidence boundary and source list.

## Markdown rendering

Markdown begins with the bundle ID, fixture ID/version, exact context, state,
top-level content address, and entry count.  It then renders all entries in
the deterministic order, followed by the evidence boundary and source IDs.
The content address remains visible in the heading metadata rather than being
hidden in an attachment.

## CLI examples

```powershell
python -m glio_noncode build-intake-bundle `
  examples/intake-public-aggregate.json `
  --output intake-bundle.json

python -m glio_noncode build-intake-bundle `
  examples/intake-public-aggregate.json `
  --output intake-bundle.csv `
  --format csv

python -m glio_noncode build-intake-bundle `
  examples/intake-public-aggregate.json `
  --output intake-bundle.md `
  --format markdown
```

The builder runs the quality gate before writing.  A failed gate exits with a
validation error unless `--allow-review` is supplied.  The latter is an
inspection path; it does not promote a review result.

## Verification obligations

Bundle tests verify:

- four positive and eight review entries are present;
- all four capability IDs are represented;
- raw operation field names are not copied into the compact envelope;
- every entry and the whole bundle are content-addressed;
- tampering with an entry invalidates verification;
- repeated builds are deterministic;
- changing the bundle ID changes the top-level address;
- JSON, CSV, and Markdown output are all usable;
- review-state bundles require explicit inspection mode;
- CLI output formats and exit behavior match the library contract.

This format is a reproducibility and review surface for bounded intake
mechanics.  It is not a legal consent certificate, a specimen authentication
certificate, or a clinical report.
