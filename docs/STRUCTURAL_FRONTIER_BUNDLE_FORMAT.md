# Structural frontier bundle format

The C13-C16 bundle is the compact release projection for structural frontier
evidence. It is designed for inspection, archival, and downstream review. It
is not a replacement for the typed reports that produce it and it never carries
raw operation payloads.

## Bundle lifecycle

```text
fixture
  -> data audit
  -> fixture evaluation
  -> quality gate
  -> lineage audit
  -> bundle projection
  -> format writer
```

`StructuralFrontierEvidenceBundleBuilder` reads the fixture, runs the quality
gate, builds a sanitized entry for every record, and writes the selected
format. The builder refuses to write an accepted release projection when the
gate fails. A review projection is allowed only when the caller explicitly
passes `allow_review=True` or the CLI `--allow-review` flag.

The bundle carries a deterministic ID, fixture ID, exact context, state,
quality address, lineage address, entry count, source IDs, and content address.
The entry list is sorted by record ID. A second build from the same fixture
produces byte-equivalent JSON and Markdown and stable row ordering in CSV.

## Top-level JSON shape

The JSON projection has the following shape:

```json
{
  "schema_version": "structural-frontier-bundle-v1",
  "bundle_id": "structural-frontier-public-aggregate-2026-08-21",
  "fixture_id": "structural-frontier-public-aggregate-2026-08-21",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "state": "accepted",
  "accepted": true,
  "entry_count": 12,
  "source_ids": [
    "gnomad-sv-v4",
    "ncbi-dbvar-ftp-manifest",
    "ncbi-dbvar-human-hub",
    "ncbi-dbvar-study-browser"
  ],
  "quality_address": "sha256:...",
  "lineage_address": "sha256:...",
  "entries": [],
  "content_address": "sha256:..."
}
```

The example hashes are abbreviated for documentation. Writers always emit the
full lowercase SHA-256 address. The content address is calculated over the
canonical body without the address field itself, preventing a self-reference
from changing the value.

## Entry contract

Every entry has these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `record_id` | string | stable fixture record identity |
| `operation` | string | one of the four C13-C16 operation IDs |
| `fixture_state` | string | accepted or review control state |
| `result_state` | string | adapter state such as accepted, review, invalid, or published |
| `expected_result_state` | string | declared expectation from the fixture |
| `issue_codes` | array | sorted review or validation codes |
| `counts` | object | operation-specific sanitized counts |
| `source_id` | string | declared aggregate source receipt |
| `context_key` | string | exact six-dimension context |
| `output_address` | string | address of the sanitized operation result |
| `passed` | boolean | expected-versus-observed check result |

An entry never includes input rows, nucleotide strings, sample IDs, patient
labels, or arbitrary adapter objects. The writer selects fields rather than
serializing an adapter report wholesale. That allow-list is part of the
privacy and review boundary.

## Operation count projections

The `counts` object is intentionally regular enough for tables while retaining
operation-specific meaning:

### Tandem repeat

```json
{
  "observations": 1,
  "expanded": 1,
  "contracted": 0,
  "review": 0
}
```

`expanded` and `contracted` are mutually exclusive classifications for the
same observation. A within-uncertainty observation may have both counts at
zero. A malformed motif may have one observation and a positive review count.

### Compound haplotype

```json
{
  "evaluations": 1,
  "compatible": 1,
  "review": 0
}
```

`compatible` counts only complete, phase-compatible evaluations. An unknown
phase control can preserve an evaluation while still carrying review state.
This prevents a count of observed alleles from being mistaken for a resolved
haplotype.

### Breakpoint uncertainty

```json
{
  "intervals": 1,
  "high_confidence": 1,
  "review": 0
}
```

Interval count is independent from confidence count. A low-confidence interval
remains an interval but is not counted as high confidence. An inverted interval
is represented by a validation issue and does not become a valid interval.

### Structural evidence export

```json
{
  "evidence": 2,
  "sources": 2,
  "published": 1
}
```

`published` is one only when the required fields, context, and source identity
are valid. A failed export can still be represented as a review-safe entry
with zero counts and an explicit validation issue.

## JSON rules

The JSON writer applies these rules:

1. keys are sorted;
2. arrays are emitted in stable semantic order;
3. enum values are emitted as strings;
4. addresses use `sha256:` followed by 64 lowercase hexadecimal characters;
5. absent optional values are represented consistently;
6. no raw payload keys are copied from fixture records;
7. no non-deterministic timestamps are added;
8. the final newline is present.

The verifier re-parses the JSON and checks the schema version, entry count,
context, source set, state, address format, and content address. Tampering with
one entry changes the content address and fails verification.

## CSV projection

CSV is a row-oriented projection for spreadsheet and text processing. The
header is fixed:

```text
bundle_id,fixture_id,context_key,record_id,operation,fixture_state,result_state,expected_result_state,issue_codes,counts,source_id,output_address,passed
```

There is one row per entry. `issue_codes` is a pipe-delimited sorted list and
`counts` is a compact canonical JSON object. Both fields are quoted according
to standard CSV rules. The bundle metadata is repeated in every row so a CSV
file remains meaningful after filtering or sorting.

CSV does not add a second source of truth. A verifier reconstructs the same
entry body from rows, checks the repeated metadata, and compares the resulting
content address with the JSON-equivalent bundle body.

## Markdown projection

Markdown is a human-review projection. Its first heading is:

```markdown
# Structural frontier evidence bundle
```

The document includes:

1. bundle metadata;
2. quality and lineage addresses;
3. source receipt IDs;
4. a table of all twelve entries;
5. issue-code notes;
6. operation count summaries;
7. a release-state statement.

The table is deliberately compact. Long details remain in the JSON report,
while the Markdown projection makes state, operation, control issues, and
addresses visible during review. The renderer escapes pipes and line breaks in
record fields so a record cannot alter table structure.

## Review-state bundles

Review-state output is useful for inspecting controls and failed input. It is
not a release artifact. The `accepted` field is false and the state is `review`
or `blocked`. A caller must opt in to write it. The builder retains all
sanitized entries so reviewers can see which controls fired:

| Condition | Bundle state | Publication |
| --- | --- | --- |
| all gate checks pass | accepted | permitted |
| a fixture control is expected review but gate passes | accepted | permitted |
| catalog audit fails | blocked | requires explicit review output |
| evaluation check fails | review | requires explicit review output |
| export misses a required field | review | not published |
| context drift is detected | blocked | not published |

The distinction between an expected review control and a failing release check
is important. Negative controls are part of a passing fixture; malformed
catalogs and unexpected results are not.

## Security and scope rules

The bundle builder checks the same sensitive-key deny list as the fixture audit.
The current deny list includes:

```text
patient_id
subject_id
medical_record_number
sample_patient_id
participant_id
```

It also rejects source receipts marked as patient level. Aggregate source
receipts may identify a public resource surface and release label, but they do
not identify individuals.

The builder does not fetch data. The fixture contains only public aggregate
references and compact operation parameters. Network retrieval, if needed for
a future extension, must remain outside this deterministic release writer and
must produce a new source receipt before it enters a fixture.

## Verifier behavior

`StructuralFrontierEvidenceBundleBuilder.verify` returns a structured result,
not a bare exception-only outcome. Verification checks:

- file format and JSON/CSV/Markdown parsing;
- schema version;
- bundle identity;
- entry count;
- exact context agreement;
- source set agreement;
- entry ordering;
- address syntax;
- accepted-state consistency;
- content address;
- absence of raw payload markers.

The CLI exits with zero only when a written accepted bundle verifies. It exits
with two when the builder returns a review or blocked result. This makes the
command suitable for a CI step without treating review output as a successful
release.

## Examples

Write JSON:

```powershell
python -m glio_noncode build-structural-frontier-bundle `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-bundle.json
```

Write CSV:

```powershell
python -m glio_noncode build-structural-frontier-bundle `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-bundle.csv `
  --format csv
```

Write Markdown:

```powershell
python -m glio_noncode build-structural-frontier-bundle `
  examples/structural-frontier-public-aggregate.json `
  --output structural-frontier-bundle.md `
  --format markdown
```

Inspecting review controls:

```powershell
python -m glio_noncode build-structural-frontier-bundle `
  examples/structural-frontier-pipeline-review.json `
  --output structural-frontier-review.json `
  --allow-review
```

The public aggregate fixture is the release example. The review pipeline is a
runtime example and is not a substitute for the twelve-record fixture gate.

## Compatibility policy

The schema version changes when a field is removed, changes meaning, or loses
its deterministic behavior. Additive fields require an explicit version review
because downstream readers may use strict key checks. Any new operation must
add a new operation ID, contract, adapter receipt, fixture controls, scenario,
quality check, lineage rule, bundle projection, CLI command, test module, and
ledger entry in the same release.

The bundle format deliberately keeps result summaries small. Large evidence
tables, raw source records, and sequence data belong in separate audited
artifacts referenced by content address. The C13-C16 bundle is the stable
index, not an unbounded data container.
