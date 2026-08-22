# Domain 10 link frontier schema

The Domain 10 schema is a four-operation contract registry. Each operation
has required payload fields, positive states, control states, issue vocabulary,
and interpretation limits. The schema is validated before the quality gate.

## Version

The current fixture version is:

```text
2026.08.d10-c13-c16.v1
```

The schema version for each operation is `v1`. A schema change must update the
contract ID, fixture version, expected checks, replay receipt, and release
documentation together.

## Common record envelope

Every fixture record contains:

| Field | Type | Requirement |
| --- | --- | --- |
| `record_id` | string | unique and non-empty |
| `operation` | enum | one of the four operation values |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact fixture context |
| `source_ids` | list | at least one resolvable source |
| `payload` | object | operation input and declared thresholds |
| `expected_state` | string | state expected by the fixture |
| `expected_issue_codes` | list | empty or explicit issue vocabulary |
| `description` | string | review-facing purpose |
| `content_address` | string | canonical address |

The loader rejects an unknown operation or role. It does not infer a missing
source ID from a title or URI.

## Source receipt

Each source receipt contains:

```json
{
  "source_id": "encode-project",
  "title": "ENCODE public functional genomics portal",
  "uri": "https://www.encodeproject.org/",
  "source_kind": "public_assay_archive",
  "release": "2024-01",
  "scope": "aggregate regulatory activity and link evidence",
  "content_address": "sha256:..."
}
```

Source receipts are descriptive. They identify the public source boundary used
by the fixture; they do not claim that the source validates the result.

## Operation C13

Operation: `link_dependence_correction`.

Required payload field:

- `input_records` — a list of link rows.

Each link row should contain:

| Field | Type | Meaning |
| --- | --- | --- |
| `link_id` | string | stable evidence path ID |
| `dependence_group` | string | declared correlated group |
| `support` | number | bounded descriptive support |

The output link row contains:

- `link_id`;
- `context_key`;
- `raw_support`;
- `dependence_group`;
- `group_size`;
- `corrected_support`;
- `state`.

Positive state: `supported`.

Control states: `partial`, `invalid`.

Issue values:

- `zero_corrected_support`;
- `empty_dependence_input`;
- `invalid_dependence_input`.

The transform is monotone downward with respect to raw support. The schema
does not describe corrected support as a probability.

## Operation C14

Operation: `target_gene_ranking`.

Required payload field:

- `input_records` — a list of candidate link rows.

Each row contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `link_id` | string | stable evidence path ID |
| `variant_id` | string | variant identity |
| `element_id` | string | regulatory element identity |
| `gene_id` | string | candidate gene identity |
| `component_scores` | object | named bounded components |

The output contains `ranks` and `top_gene_by_variant`. Every rank retains its
component score map and identity fields. Alternative genes remain in `ranks`.

Positive state: `supported`.

Control states: `partial`, `invalid`.

Issue values:

- `zero_rank_support`;
- `empty_rank_input`;
- `invalid_rank_input`.

The top-gene map is a deterministic view, not a deletion of alternatives.

## Operation C15

Operation: `link_calibration_abstention`.

Required payload fields:

- `input_records`;
- `maximum_uncertainty`;
- `maximum_calibration_error`.

Each decision contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `link_id` | string | path identity |
| `predicted_score` | number | declared prediction score |
| `observed_score` | number or null | optional observation |
| `calibration_error` | number or null | absolute difference |
| `uncertainty` | number | uncertainty value |
| `abstained` | boolean | threshold disposition |
| `issues` | list | structured review issues |

Positive state: `supported`.

Control states: `partial`, `invalid`.

Issue values:

- `link_uncertainty_high`;
- `link_calibration_error_high`;
- `empty_calibration_input`.

Abstention preserves the record. It does not produce a negative scientific
finding.

## Operation C16

Operation: `link_evidence_publication`.

Required payload fields:

- `input_records`;
- `bundle_id`.

Each row contains `link_id`, `source_id`, and `context_key`.

The output contains:

- `bundle_id`;
- `context_key`;
- sorted `link_ids`;
- `records_address`;
- `bundle_address`;
- `state`.

Positive state: `published`.

Control state: `invalid`.

Issue values:

- `publication_context_mismatch`;
- `invalid_publication_input`;
- `empty_publication_input`.

The publisher requires exact context equality. It does not transport a row from
another context into the bundle context.

## Contract limits

Every contract includes interpretation limits. The current limits cover:

- causal regulation;
- causal probability;
- clinical interpretation;
- diagnostic use;
- pathogenicity;
- treatment use;
- actionability;
- target selection as a scientific conclusion.

The limits are checked as non-empty contract data. They are also rendered into
the release documentation and review exports.

## Schema checks

There are five checks for each operation:

1. required fields are non-empty;
2. state vocabulary contains the operation's accepted and control states;
3. issue vocabulary is non-empty and matches the contract;
4. the operation is represented in the fixture;
5. the schema has a content address.

The schema report therefore contains twenty checks. A report with a missing
operation, empty issue vocabulary, or unaddressed schema is not accepted.

## Serialization rules

Canonical serialization uses sorted object keys and deterministic enum values.
Lists preserve declared order unless a publisher contract explicitly sorts an
identity list. Content addresses are calculated without the address field
itself.

The JSON export adds computed acceptance and failure summaries. CSV exports
use a fixed header and represent issue tuples with a pipe separator. Markdown
exports are review-oriented and do not expose uncontrolled raw input.

## Fixture invariants

The default fixture must maintain:

- one exact context;
- four operations;
- four positive records;
- twelve controls;
- five source receipts;
- sixteen records total;
- HTTPS source URIs;
- unique source IDs;
- unique record IDs;
- complete operation coverage.

The data audit enforces these invariants before operation execution.

## Change procedure

When changing a field:

1. update the contract;
2. update the fixture payload;
3. update the positive record;
4. update at least one control;
5. update the evaluator;
6. update the depth audit;
7. update the schema report;
8. update the CLI test;
9. update the release document;
10. run replay and the full suite.

When adding an issue code, add it to the contract vocabulary and at least one
control. An issue code that exists only in an implementation branch is not a
stable interface.

## Inspecting schema output

```powershell
glio-noncode link-frontier-contracts --output link-contracts.json
glio-noncode link-frontier-schema --output link-schema.json
Get-Content link-schema.json
```

The schema output is safe to attach to a review because it contains contract
fields, expected states, issue vocabulary, and content addresses rather than
unbounded input data.
