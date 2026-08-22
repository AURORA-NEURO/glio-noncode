# Domain 11 schema and contract reference

## Envelope

Every causal frontier artifact is JSON-compatible and content addressed. The
top-level fixture envelope has these fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `fixture_id` | string | yes | stable fixture identity |
| `fixture_version` | string | yes | pinned behavior version |
| `context_key` | string | yes | exact genomic and cohort scope |
| `evidence_boundary` | string | yes | public aggregate boundary |
| `sources` | array | yes | source receipts |
| `records` | array | yes | positive and control records |
| `content_address` | string | yes | fixture receipt |

The current version is `2026.08.d11-c13-c16.v1`. The current boundary is
`public_aggregate_non_patient`. The current context is
`GRCh38|glioma|adult|stem_like|core|unknown`.

## Source receipt

Source receipts make external context explicit without copying a large external
dataset into the fixture.

| Field | Type | Meaning |
| --- | --- | --- |
| `source_id` | string | stable local source key |
| `title` | string | readable source label |
| `uri` | HTTPS string | public source location |
| `source_kind` | string | archive, index, or program role |
| `release` | string | pinned source release marker |
| `scope` | string | aggregate use in this boundary |
| `content_address` | string | receipt for the receipt |

The source list currently contains ENCODE, 4D Nucleome, NCBI GEO, PubMed, and
NIH Common Fund. A source ID referenced by a record must resolve in the source
map. A source can be cited by many records; the record retains the exact source
ID list so lineage can be reconstructed.

## Record envelope

Every record has the following fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `record_id` | string | positive or control identity |
| `operation` | enum | one of four operation paths |
| `role` | enum | `positive` or `control` |
| `context_key` | string | exact context retained on the row |
| `source_ids` | array[string] | source receipt references |
| `payload` | object | operation input and parameters |
| `expected_state` | enum string | fixture expectation |
| `expected_issue_codes` | array[string] | exact control vocabulary |
| `description` | string | review explanation |
| `content_address` | string | record receipt |

The payload includes `input_records` and an `input_hash`. Operation-specific
parameters remain beside the input rows so replay can be performed without a
second configuration file.

## C13 posterior decomposition

### Input rows

| Field | Type | Constraint |
| --- | --- | --- |
| `hypothesis_id` | string | required identity |
| `prior` | number | 0 through 1 |
| `likelihood` | number | 0 through 1 |
| `measurement` | number | 0 through 1 |
| `dependency_penalty` | number | 0 through 1 |

The adapter calculates a bounded raw value from the declared components and
normalizes across the input rows when total mass is nonzero. The output retains
both raw and normalized values. Zero total mass is `partial` with
`zero_posterior_mass`. An empty list is `invalid` with
`empty_posterior_input`. A numeric range failure is `invalid` with
`invalid_posterior_input`.

### Output rows

| Field | Meaning |
| --- | --- |
| `hypothesis_id` | named hypothesis |
| `context_key` | exact request context |
| `prior` | retained prior |
| `likelihood` | retained likelihood |
| `measurement` | retained measurement |
| `dependency_penalty` | retained penalty |
| `raw_posterior` | bounded component product |
| `normalized_posterior` | normalized component |
| `state` | accepted or review |

## C14 driver posterior

### Input rows

| Field | Type | Constraint |
| --- | --- | --- |
| `driver_id` | string | required identity |
| `evidence_ids` | array[string] | evidence path identities |
| `evidence_support` | number | 0 through 1 |
| `prior` | number | 0 through 1 |

The adapter retains evidence IDs and ranks by bounded support times prior. The
minimum-support parameter is explicit. Support below that threshold yields a
review state and `low_driver_support`; it is not discarded.

### Output rows

`DriverPosterior` contains driver ID, context, evidence IDs, support, prior,
posterior, rank, and state. The report retains the top driver ID only as a
ranking receipt. It is not a mechanistic conclusion.

## C15 selective prediction

### Input rows

| Field | Type | Constraint |
| --- | --- | --- |
| `prediction_id` | string | required identity |
| `score` | number | 0 through 1 |
| `uncertainty` | number | finite and nonnegative |

The threshold is `max(minimum_score, uncertainty * 2)`. A score below the
threshold creates `selective_prediction_abstention`. Uncertainty above
`maximum_uncertainty` creates `prediction_uncertainty_high`. A prediction can
therefore retain two issues at once. The report has accepted and abstained ID
lists, so a consumer does not need to infer abstention from a missing row.

## C16 dossier publication

### Payload

| Field | Type | Constraint |
| --- | --- | --- |
| `input_records` | array | nonempty for a positive path |
| `dossier_id` | string | required |
| `hypothesis_ids` | array[string] | nonempty |
| `evidence_addresses` | array[string] | nonempty |
| `top_hypothesis_id` | string or null | must belong to hypothesis IDs |

The publisher creates a dossier address from the identity, context, hypotheses,
addresses, and top identity. It does not include a free-form conclusion field.
An unknown top identity and missing evidence addresses are invalid controls.

## Issue vocabulary

| Code | Operation | Meaning |
| --- | --- | --- |
| `zero_posterior_mass` | C13 | components have no mass |
| `empty_posterior_input` | C13 | input array is empty |
| `invalid_posterior_input` | C13 | typed validation failed |
| `low_driver_support` | C14 | support below threshold |
| `empty_driver_input` | C14 | input array is empty |
| `invalid_driver_input` | C14 | typed validation failed |
| `selective_prediction_abstention` | C15 | score below threshold |
| `prediction_uncertainty_high` | C15 | uncertainty above threshold |
| `empty_prediction_input` | C15 | input array is empty |
| `invalid_dossier_input` | C16 | identity or address validation failed |
| `empty_dossier_input` | C16 | input array is empty |

Issue codes are exact strings. The evaluator sorts and compares them. Adding a
new issue code is a contract change and requires a fixture, a test, and a
release note.

## State vocabulary

| State | Meaning |
| --- | --- |
| `supported` | bounded positive operation succeeded |
| `partial` | output exists but a review issue is retained |
| `invalid` | input did not satisfy the operation contract |
| `published` | manifest receipt was emitted |

The `accepted` property is true only for `supported` and `published` outputs
without an error. A control may have a useful output and still be non-accepted
because its purpose is to prove a boundary condition.

## Content addressing

Every receipt uses canonical JSON serialization and SHA-256. Tuple and enum
values are normalized before hashing. The address is calculated from the
object body before the address field is attached. This makes addresses stable
across repeated runs and independent of wall-clock timing.

Content addresses are used for:

- source receipts;
- fixture records;
- operation executions;
- evaluation checks;
- replay receipts;
- lineage edges;
- metrics;
- policy decisions;
- release bundles;
- runtime stages;
- release checks.

## Schema evolution

A schema version must change when a required field, field interpretation, issue
code, state, or boundary changes. A documentation-only clarification can retain
the version if the canonical object body and tests remain unchanged. Any change
to a threshold parameter should be treated as behavior-significant even if the
Python signature is unchanged.

## Consumer guidance

Consumers should:

1. validate the boundary before reading operation outputs;
2. inspect `state` and `issue_codes` together;
3. retain `context_key` in downstream keys;
4. follow `content_address` into the manifest;
5. retain abstained rows;
6. avoid converting ranked identities into conclusions;
7. respect the excluded-use list in the release manifest.

Consumers should not:

1. drop control rows;
2. replace an abstained value with zero;
3. treat a top hypothesis as a causal proof;
4. infer clinical value from a published manifest;
5. merge contexts by partial string matching;
6. use the public source list as a patient cohort.
