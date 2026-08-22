# Domain 13 validation-planning schema

The schema manifest describes the fields required to execute evidence-gap,
eligibility, MPRA, and STARR-seq planning. Contracts define issue vocabulary;
schemas define field type, requiredness, nullability, and semantic role.

## Shared record fields

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| record_id | string | yes | stable fixture row |
| operation | enum | yes | one of four planning operations |
| role | enum | yes | positive or control |
| context_key | string | yes | exact planning context |
| source_ids | array<string> | yes | public source receipts |
| payload | object | yes | operation input |
| expected_state | enum | yes | fixture expectation |
| expected_issue_codes | array<string> | yes | declared control issues |
| content_address | string | yes | row receipt |

The context is exact. A related disease, age group, cell state, or treatment
phase is not interchangeable with the fixture context.

## Evidence-gap input

The C01 payload requires a typed hypothesis and may include available channels.
The hypothesis retains:

- hypothesis ID;
- variant, element, gene, and state IDs;
- mechanism;
- exact context;
- causal state;
- support proxy;
- uncertainty;
- factor graph and factor IDs;
- missing evidence;
- contradictory edges;
- limitations.

The output retains gaps, priority order, available channels, warnings, state,
and content address. A gap is not silently filled when a channel is absent.

## Eligibility input

The C02 payload contains constraints and inventory rows. Constraints require:

- constraint ID;
- context key;
- model system;
- minimum and maximum insert length;
- maximum constructs;
- required controls;
- required readouts;
- paired-allele requirement.

Inventory rows require assay, model systems, insert bounds, controls, readouts,
source ID, and feasibility. The route output retains satisfied constraints,
blockers, alternatives, sensitivity, feasibility, and rationale.

## Reporter planning input

C03 and C04 share a target and constraints structure. A target requires:

- target ID;
- variant ID;
- element ID;
- sequence;
- variant offset;
- reference allele;
- alternate allele;
- context object;
- source ID.

The planner checks exact context, insert length, target presence, and construct
budget before generating constructs. The output retains the reference and
alternate sequence pair, controls, readouts, blockers, alternatives,
sensitivity, and limitations.

## Issue vocabulary

The issue vocabulary is:

```text
context_mismatch
invalid_evidence_gap_input
complete_hypothesis_control
model_system_not_available
missing_controls
missing_readouts
assay_not_present_in_inventory
invalid_assay_eligibility_input
insert_length
max_constructs_exceeded
no_validation_targets
invalid_validation_design_input
```

Issue spelling is stable output. Adding or renaming an issue requires contract,
fixture, test, documentation, and release review.

## State vocabulary

The planner uses:

```text
partial
ready_for_review
blocked
abstained
invalid
```

The underlying validation planning objects use their own typed enum values. The
frontier evaluator normalizes those values to the bounded strings above and
retains the complete typed output in the execution body.

## Source receipt schema

| Field | Constraint |
| --- | --- |
| source_id | stable non-empty reference |
| title | readable source title |
| uri | HTTPS URL |
| access_note | public aggregate boundary note |
| content_address | deterministic receipt |

The default five receipts are public indexes and registries. They identify the
declared provenance boundary and do not imply access to restricted records.

## Output serialization

`to_dict()` converts enums to values and tuples to arrays. JSON export sorts keys
and ends with a newline. Canonical export uses the repository canonical JSON
routine. CSV export has a fixed eight-column order and one row per fixture record.

## Compatibility

Compatible changes may add explanatory fields without altering required field
meaning. Breaking changes include renaming a required field, changing issue
spelling, changing state semantics, changing context representation, or changing
the body used for a content address. Breaking changes require a new schema and
fixture version.

## Schema checks

- [ ] Four operations have contracts.
- [ ] Four operations have schemas.
- [ ] Every required payload field is declared.
- [ ] Context is required and non-nullable.
- [ ] Empty target or inventory paths are explicit.
- [ ] State values are bounded.
- [ ] Issue codes are declared once.
- [ ] Outputs have content addresses.
- [ ] Limitations are retained.
- [ ] Allowed and excluded uses are release fields.
