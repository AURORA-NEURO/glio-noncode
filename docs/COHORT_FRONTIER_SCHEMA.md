# Domain 12 schema and contract reference

The cohort frontier uses explicit operation contracts and field schemas. The
contract says what each operation requires and which issue codes it may emit.
The schema says how the input and output fields are represented. Both manifests
are content-addressed and must cover all four operations.

## Common fields

Every operation carries:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| input_records | array<object> | yes | aggregate rows for the operation |
| context_key | string | yes | exact cohort scope |
| content_address | string | yes | deterministic receipt |
| state | enum | yes | supported, review, invalid, published |

Controls may use an empty input array when the expected issue is an empty-input
boundary. Positive records must contain the operation-specific payload.

## Operation contract matrix

| Operation | Required payload | Output emphasis |
| --- | --- | --- |
| subgroup_fairness | group and prediction fields | strata, rates, parity gap |
| transportability | source and target features | overlap, shift, review IDs |
| federated_summary | site, count, mean fields | totals, spread, privacy floor |
| cohort_discovery | bundle, analysis, feature IDs | aggregate publication manifest |

The runtime does not silently coerce a missing field into an empty value. A
missing or malformed field is an invalid payload and retains a declared issue.

## Issue vocabulary

The issue vocabulary has twelve entries:

```text
parity_gap_high
empty_fairness_input
invalid_fairness_input
target_feature_gap
distribution_shift_high
empty_transportability_input
privacy_floor_violation
empty_federated_input
invalid_federated_input
invalid_cohort_discovery_input
empty_cohort_discovery_input
context_mismatch
```

The public fixture uses the first eleven directly. `context_mismatch` remains
available for adapter-level callers that identify the mismatch before the
publisher contract is invoked. The issue vocabulary is part of the release
surface; adding an issue requires updating the contract, schema, fixture, tests,
and documentation together.

## Subgroup fairness

The stratifier groups aggregate rows by the declared group field. A stratum
retains:

- group label;
- total count;
- positive count;
- rate;
- parity gap;
- review state.

The maximum parity gap is retained in the report. A gap above the declared
threshold adds the affected group to `review_ids` and emits
`parity_gap_high`. A missing group field emits `invalid_fairness_input`. An
empty input emits `empty_fairness_input`.

The operation must preserve small strata. It must not hide a high gap by
rounding away the denominator or by dropping a group with fewer rows.

## Transportability

The estimator compares source and target feature sets for each analysis. It
retains:

- analysis ID;
- source features;
- target features;
- overlap score;
- distribution shift score;
- transportable IDs;
- review IDs.

A missing target feature emits `target_feature_gap`. A shift above the declared
threshold emits `distribution_shift_high`. An empty input emits
`empty_transportability_input`.

The overlap score and shift score are descriptive signals. They do not prove
generalization to an unseen cohort.

## Federated summary

The summary analyzer accepts site-local aggregate rows. A summary retains:

- feature ID;
- site count;
- total count;
- aggregate mean;
- between-site spread;
- privacy floor;
- review state.

The analyzer does not need raw site rows after aggregation and the public
fixture does not contain them. A count below the privacy floor emits
`privacy_floor_violation`. Empty input emits `empty_federated_input`. A value
that cannot be represented as a numeric mean emits `invalid_federated_input`.

The privacy floor is a visibility rule, not a full privacy guarantee. It does
not replace a formal disclosure review.

## Cohort discovery

The publisher requires:

- a non-empty bundle ID;
- the exact context key;
- at least one feature ID;
- at least one analysis ID;
- aggregate input rows;
- a declared evidence boundary.

The bundle retains feature IDs, analysis IDs, context, record address, and
publication address. A context mismatch, missing analysis set, or empty input
is invalid. The published result is a manifest-only result and carries the
same excluded-use list as the release manifest.

## Source receipt schema

Each source receipt has:

| Field | Constraint |
| --- | --- |
| source_id | non-empty stable identifier |
| title | readable source title |
| uri | HTTPS URL |
| access_note | aggregate boundary note |
| content_address | SHA-256-style receipt |

The five default receipts are drawn from public research indexes and registries.
The receipt only identifies the declared source; it does not assert that the
source supplies patient-level data to this repository.

## Record schema

Each record has:

| Field | Meaning |
| --- | --- |
| record_id | stable fixture row ID |
| operation | one of four operation enum values |
| role | positive or control |
| context_key | exact scope |
| source_ids | source receipt references |
| payload | operation input values |
| expected_state | expected bounded state |
| expected_issue_codes | sorted issue vocabulary subset |
| notes | review explanation |
| content_address | deterministic record receipt |

The loader checks record uniqueness, operation membership, role membership,
context equality, source references, and expected issue vocabulary.

## Serialization

`to_dict()` returns enum values as strings and tuples as JSON arrays. JSON export
uses sorted keys and a trailing newline. Canonical export uses the repository's
canonical JSON routine and no presentation indentation. CSV export uses a fixed
column order so downstream review does not depend on dictionary ordering.

## Compatibility rules

Backward-compatible changes may add non-required report fields, add explanatory
notes, or add a new export that leaves existing fields unchanged. Breaking
changes include renaming a required field, changing issue spelling, changing
state semantics, changing the context key, or changing the content-address
input. Breaking changes require a new schema version and fixture version.

## Validation examples

```powershell
glio-noncode cohort-frontier-contracts --output contracts.json
glio-noncode cohort-frontier-schema --output schema.json
glio-noncode cohort-frontier-evaluate --output evaluation.json
```

The contract manifest should report four contracts. The schema manifest should
report four operation schemas and the `2026.08.d12.v1` version. The evaluation
should report 16 executions and 120 passing checks.

## Schema review checklist

- [ ] Every operation enum has one contract.
- [ ] Every operation enum has one schema.
- [ ] Required payload fields are named in the contract.
- [ ] Issue codes are declared once and reused by the evaluator.
- [ ] Common fields are present on every schema.
- [ ] Output states are bounded.
- [ ] Addresses are represented as strings.
- [ ] Context is required and non-nullable.
- [ ] Empty inputs are allowed only for declared controls.
- [ ] The schema manifest has an explicit version.
- [ ] The schema content address is stable across replay.

## Boundary reminders

The schema is a computational contract. It is not a data-use agreement, a
clinical protocol, a privacy certification, or a general-purpose cohort model.
Consumers must carry the boundary and use lists forward when embedding these
records in another report.
