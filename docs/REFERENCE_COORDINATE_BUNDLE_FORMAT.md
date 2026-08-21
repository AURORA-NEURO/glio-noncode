# Reference-coordinate evidence bundle format

This format describes the sanitized projections emitted by the Domain 04
C01-C04 evidence plane. It is intentionally smaller than the input fixture.
The bundle is a review and reproducibility artifact, not a copy of a chain
file, reference assembly, pangenome graph, or subject record.

## Bundle envelope

The JSON envelope has these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `fixture_id` | string | source fixture identity |
| `fixture_version` | string | schema and control version |
| `context_key` | string | exact six-part context |
| `format` | enum | `json`, `csv`, or `markdown` |
| `entries` | array | sanitized operation receipt projections |
| `included_controls` | boolean | whether review controls are present |
| `published` | boolean | whether this bundle may be used as a release projection |
| `state` | enum | `accepted` or `review` |
| `content_address` | string | address of the canonical envelope |

The canonical verification bundle includes sixteen entries: four positive
rows and twelve controls. The accepted-only bundle includes four positive
entries and may be marked published when all upstream components pass. A
bundle that contains controls is useful for audit but is not published by the
runtime.

## Entry schema

Each entry has:

```json
{
  "record_id": "d04-c03-control-competing-segments",
  "operation": "liftover_ambiguity",
  "role": "control",
  "state": "ambiguous",
  "issue_codes": ["ambiguity_competing"],
  "source_ids": ["SRC-UCSC-CHAIN"],
  "context_key": "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
  "result_summary": {
    "candidate_count": 2,
    "candidate_mapping_ids": ["ambiguity-compete-a", "ambiguity-compete-b"],
    "score": 0.5
  },
  "record_address": "sha256:<fixture-record-address>",
  "receipt_address": "sha256:<operation-receipt-address>",
  "content_address": "sha256:<entry-address>"
}
```

`result_summary` is operation-specific but always bounded. The four allowed
summary families are:

| Operation | Allowed summary content |
| --- | --- |
| `reference_registry` | query presence, resolved assembly, species, release, alias count |
| `liftover_chain` | parsed count, parse count, projection status, mapping ID, target coordinates |
| `liftover_ambiguity` | query interval, candidate IDs, count, score, state |
| `pangenome_coordinate` | query interval, path IDs, sequence IDs, count, state |

The entry does not include `payload`, raw chain text, full input rows, source
document bodies, direct identifiers, or secrets. The record and receipt
addresses allow a reviewer to compare source and derived views without
copying those restricted values into the release projection.

## Address construction

Addresses are computed in layers:

1. A source receipt address covers source metadata.
2. A fixture record address covers operation, role, expected state, context,
   source IDs, expected issues, and input payload.
3. An operation receipt address covers the sanitized state, issue codes,
   source IDs, context, and result summary.
4. An entry address covers the bundle projection plus record and receipt
   addresses.
5. The bundle address covers the ordered envelope and ordered entries.

The implementation uses canonical JSON serialization and a SHA-256 prefix.
Changing an operation state, mapping ID, candidate set, issue code, source set,
context, or output format changes the relevant address. Reordering source IDs
is normalized where the contract declares them as a set; record order remains
stable where scenario order is part of the fixture.

## CSV rendering

CSV has one header row and one row per entry. The columns are:

```text
record_id,operation,role,state,issue_codes,source_ids,context_key,
record_address,receipt_address,content_address,result_summary
```

`issue_codes` and `source_ids` use semicolon delimiters. `result_summary` is a
compact JSON object with stable key ordering. A CSV renderer must not flatten
candidate IDs into an uncontrolled number of columns because doing so would
make schema comparison dependent on the number of ambiguous candidates.

## Markdown rendering

Markdown is a human-readable index. It contains the fixture state, publication
flag, exact context, entry count, bundle address, and a table with record ID,
operation, role, state, issue codes, source IDs, and entry address. It is not
the canonical machine input. A Markdown change must not be used to repair a
JSON address drift.

## Verification rules

The bundle verifier checks:

- fixture ID and version agree with the catalog;
- exact context is retained;
- entry IDs are unique;
- every entry belongs to the fixture;
- record addresses match typed records;
- receipt addresses match evaluation receipts;
- entry and bundle addresses exist;
- context is present on every entry;
- rendered content contains no raw chain text;
- the control-inclusion flag is truthful; and
- the bundle state remains review when upstream evidence fails.

Verification is deterministic and side-effect free. It does not fetch source
URLs or rebuild a complete external reference resource. Those activities need
their own declared source and resource verification surfaces.

## Publication modes

There are two intended modes:

| Mode | Entries | Published |
| --- | ---: | --- |
| Verification | 16 | false |
| Accepted-only release projection | 4 | true only when every gate passes |

`allow_review` permits a reviewer to render the complete verification view. It
does not force `published=true`. A review-state evaluation, a context mismatch,
or a failed reconciliation remains non-publishing regardless of rendering
format.

## CLI examples

```powershell
python -m glio_noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output coordinate-bundle.json
python -m glio_noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output coordinate-bundle.csv --format csv
python -m glio_noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output coordinate-bundle.md --format markdown
python -m glio_noncode build-reference-coordinate-bundle examples/reference-coordinate-public-aggregate.json --output accepted-coordinate-bundle.json --accepted-only
```

The accepted-only command is the runtime publication projection. The default
command is the complete verification projection and deliberately retains
control states for audit.

## Compatibility and change policy

Adding a summary field requires an operation-contract decision and a privacy
test. Changing an issue code requires a positive/control fixture update and a
replay expectation update. Changing entry order, context, or output format
must be treated as an address-affecting release change. Removing a control is
not a compatibility-preserving change even when the positive count remains
unchanged.

The format does not promise that every future graph or reference resource can
be represented by a small entry. Large external resources should be referenced
by public source receipt, version, checksum, and resource manifest rather than
copied into the bundle.
