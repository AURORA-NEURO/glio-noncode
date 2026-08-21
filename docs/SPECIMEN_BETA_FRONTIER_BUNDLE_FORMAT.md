# Specimen beta frontier bundle format

The beta frontier bundle is a compact addressed release projection for Domain
03 C05-C08. It is produced by `SpecimenBetaFrontierEvidenceBundleBuilder` and
can be serialized as JSON, CSV, or Markdown. It contains summaries and
addresses, not raw variant observations.

## 1. Envelope

The JSON envelope has these required fields:

```json
{
  "schema": "specimen-beta-frontier-bundle-v1",
  "bundle_id": "specimen-beta-frontier-c05-c08",
  "fixture_id": "specimen-beta-frontier-public-aggregate-v1",
  "state": "accepted",
  "context_key": "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment",
  "source_ids": ["..."],
  "entry_count": 12,
  "entries": [],
  "quality_address": "sha256:...",
  "lineage_address": "sha256:...",
  "content_address": "sha256:..."
}
```

The states are:

| State | Meaning |
| --- | --- |
| `accepted` | all required checks pass |
| `review` | a bundle was explicitly allowed despite review or failed evidence |

The accepted aggregate fixture contains review controls as entries, but its
mechanical evidence checks pass. A malformed fixture cannot become accepted by
dropping its failed rows.

## 2. Entry schema

Each entry contains:

| Field | Description |
| --- | --- |
| `entry_id` | stable bundle-local ID |
| `record_id` | fixture record ID |
| `specimen_identifier` | aggregate display key, equal to record ID in this fixture |
| `operation` | origin, mosaicism, CCF, or subclone |
| `fixture_state` | accepted or review role |
| `result_state` | observed adapter state |
| `issue_codes` | bounded issue-code array |
| `source_ids` | source receipt IDs |
| `context_key` | exact six-field context |
| `record_address` | input record address |
| `result_address` | sanitized adapter result address |

Entries do not copy `payload`, raw VCF fields, raw observation rows, direct
identifiers, or unbounded source text. The builder's evaluator runs the
recursive sensitive-key check before entry serialization.

## 3. Address model

The following objects are independently addressed:

1. each fixture record;
2. each sanitized operation result;
3. the evaluation report;
4. the scenario report;
5. the quality report;
6. the lineage graph;
7. the final bundle.

Addresses use `sha256:` followed by lowercase hexadecimal. The digest input is
canonical JSON with sorted object keys, compact separators, stable enum values,
and declared array order. The address field is omitted from the value it
addresses.

The bundle address includes schema, bundle ID, fixture ID, state, context,
source IDs, entry objects, quality address, and lineage address. It is an
equality and replay mechanism, not a signature or proof of origin.

## 4. JSON projection

JSON is the machine-readable projection. It includes the full compact entry
objects and envelope receipts. The verifier checks `entry_count`, entry IDs,
context equality, address prefixes, and the bundle address.

```powershell
python -m glio_noncode build-specimen-beta-frontier-bundle examples/specimen-beta-frontier-public-aggregate.json --output beta-bundle.json --format json
```

## 5. CSV projection

CSV is a flat review view with this header:

```text
entry_id,record_id,specimen_identifier,operation,fixture_state,result_state,issue_codes,source_ids,context_key,record_address,result_address
```

Issue and source arrays are joined with semicolons. The six-field context is
quoted as required by the CSV writer. CSV does not contain the quality or
lineage graph body; those objects remain addressable through the JSON receipt.

```powershell
python -m glio_noncode build-specimen-beta-frontier-bundle examples/specimen-beta-frontier-public-aggregate.json --output beta-bundle.csv --format csv
```

## 6. Markdown projection

Markdown lists bundle identity, state, context, quality and lineage addresses,
and a bounded table of one row per entry. It is a human review view and not an
alternate address input.

```powershell
python -m glio_noncode build-specimen-beta-frontier-bundle examples/specimen-beta-frontier-public-aggregate.json --output beta-bundle.md --format markdown
```

## 7. Quality receipt

The quality report referenced by `quality_address` contains 21 check records.
Its compact summary is shaped like:

```json
{
  "passed": true,
  "check_count": 21,
  "failed_check_ids": [],
  "positive_count": 4,
  "control_count": 8,
  "operation_count": 4
}
```

The checks cover source scope, exact context, fixture identity, deterministic
evaluation, expected floors, operation contracts, sanitized output, replay
identity, scenario coverage, and lineage shape.

## 8. Lineage receipt

The lineage graph referenced by `lineage_address` has four node kinds:

| Kind | Identity |
| --- | --- |
| `source` | source ID and source receipt address |
| `fixture` | fixture ID and catalog address |
| `record` | record ID, operation, and record address |
| `result` | record ID, result state, and result address |

Valid edge relations are `declares`, `contains`, and `produces`. The graph has
36 edges: one of each relation for every record. The graph is provenance for
the evidence run and must not be interpreted as biological ancestry.

## 9. Runtime receipt

The pipeline report contains four stage receipts in fixed order:

```text
origin
mosaicism
cancer_cell_fraction
subclone
```

Each receipt contains input, accepted, review, and blocked counts, issue codes,
a result address, and a stage address. Counts are conserved. The final
manifest contains pipeline ID, context, source IDs, stage summaries, and no
raw operation payload.

## 10. Verification behavior

`SpecimenBetaFrontierEvidenceBundleBuilder.verify` checks:

- schema and state vocabulary;
- entry count and unique entry IDs;
- exact context in every entry;
- record and result address prefixes;
- bundle content-address equality.

It does not repair a bundle, re-sort entries, or recompute missing values. A
caller that wants a different order must build a new bundle with a new address.

## 11. Review opt-in

The builder refuses a failed quality gate by default. A reviewer may create a
review projection explicitly:

```powershell
python -m glio_noncode build-specimen-beta-frontier-bundle examples/specimen-beta-frontier-public-aggregate.json --output beta-review.json --allow-review
```

The review state is retained in the envelope and does not become accepted by
serialization. The CLI's release path returns a non-zero status when the
bundle cannot be verified.

## 12. Compatibility

The schema identifier is `specimen-beta-frontier-bundle-v1`. Adding an
optional field requires a verifier test and a documented compatibility rule.
Changing address inputs, required fields, ordering, or state vocabulary
requires a new schema identifier.

Consumers should reject an unknown schema and should report an address they
cannot verify as unverified. They should not invent missing fields or silently
drop unknown required state.

## 13. Complete command set

```powershell
python -m glio_noncode audit-specimen-beta-frontier-data examples/specimen-beta-frontier-public-aggregate.json --output beta-data.json
python -m glio_noncode evaluate-specimen-beta-frontier-fixture examples/specimen-beta-frontier-public-aggregate.json --output beta-fixture.json
python -m glio_noncode specimen-beta-frontier-quality-gate examples/specimen-beta-frontier-public-aggregate.json --output beta-quality.json
python -m glio_noncode specimen-beta-frontier-lineage examples/specimen-beta-frontier-public-aggregate.json --output beta-lineage.json
python -m glio_noncode run-specimen-beta-frontier-pipeline examples/specimen-beta-frontier-pipeline-accepted.json --output beta-pipeline.json
```

The repository tests cover all three projections, content-address verification,
review opt-in, line counts, and CLI behavior. The Actions workflow runs the
JSON release path on Python 3.11, 3.12, and 3.13.
