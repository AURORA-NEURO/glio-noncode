# D03 operation matrix

This matrix is the build inventory for the composed specimen architecture.
The operation names are stable fixture values and are also the dispatch keys.

## Core specimen context

| ID | Operation | Plane | Contract | Receipt focus |
| --- | --- | --- | --- | --- |
| GNC-D03-C01 | ontology_mapping | ontology | core.aggregate_input.v1 | supported ontology mapping |
| GNC-D03-C02 | matched_normal | purity_integrity | core.aggregate_input.v1 | matched normal resolution |
| GNC-D03-C03 | purity_ploidy | purity_integrity | core.aggregate_input.v1 | purity and ploidy import |
| GNC-D03-C04 | sample_integrity | purity_integrity | core.aggregate_input.v1 | sample fingerprint integrity |

These cases use the existing specimen context fixture adapter. The architecture
receipt checks result state, issue codes, bounded counts, and output address.

## Beta frontier

| ID | Operation | Plane | Contract | Receipt focus |
| --- | --- | --- | --- | --- |
| GNC-D03-C05 | origin | origin_clonality | beta.aggregate_input.v1 | somatic or germline origin |
| GNC-D03-C06 | mosaicism | origin_clonality | beta.aggregate_input.v1 | mosaic posterior |
| GNC-D03-C07 | cancer_cell_fraction | origin_clonality | beta.aggregate_input.v1 | CCF estimate |
| GNC-D03-C08 | subclone | origin_clonality | beta.aggregate_input.v1 | subclone assignment |

The beta family normalizes its typed execution receipt into the same
`observed_result_state`, `issue_codes`, `counts`, and `output_address` fields
used by all other operation families.

## Lineage frontier

| ID | Operation | Plane | Contract | Receipt focus |
| --- | --- | --- | --- | --- |
| GNC-D03-C09 | region_lineage | lineage | lineage.aggregate_input.v1 | region tree |
| GNC-D03-C10 | longitudinal_linking | lineage | lineage.aggregate_input.v1 | longitudinal specimen link |
| GNC-D03-C11 | phase_mapping | lineage | lineage.aggregate_input.v1 | primary/recurrence phase |
| GNC-D03-C12 | treatment_context | lineage | lineage.aggregate_input.v1 | treatment exposure context |

Lineage cases retain only sanitized counts and issue codes at this boundary.
The 64-event architecture ledger joins each case declaration to its receipt
with a previous-address link.

## Preanalytic frontier

| ID | Operation | Plane | Contract | Receipt focus |
| --- | --- | --- | --- | --- |
| GNC-D03-C13 | preanalytic_quality | preanalytic | preanalytic.aggregate_input.v1 | ischemia, storage, and integrity |
| GNC-D03-C14 | assay_lineage | preanalytic | preanalytic.aggregate_input.v1 | assay protocol lineage |
| GNC-D03-C15 | identity_adjudication | preanalytic | preanalytic.aggregate_input.v1 | identity conflict review |
| GNC-D03-C16 | context_envelope | preanalytic | preanalytic.aggregate_input.v1 | context envelope publication |

The preanalytic family does not publish a numeric result count. The architecture
normalizer maps an accepted preanalytic receipt to the common `supported`
result state and retains its summary behind the adapter boundary.

## Per-operation lifecycle

Each operation proceeds through the same lifecycle:

1. the operation spec joins to its source IDs;
2. the case declares context, scenario, payload, expected result, and expected counts;
3. the policy report decides whether adapter dispatch is allowed;
4. a positive case is converted to the family-specific typed record;
5. the typed adapter returns a bounded execution receipt;
6. a control is held without adapter invocation;
7. the architecture receipt compares expected and observed fields;
8. validation, review, lineage, replay, and release consume the receipt.

The four-case balance means operation-level coverage is visible even when a
family-specific adapter has an internal implementation change.

## Expected control outcomes

| Scenario | State | Result | Issue |
| --- | --- | --- | --- |
| foreign_context | review | out_of_domain | context_mismatch |
| malformed_input | review | invalid | malformed_input |
| identity_conflict | review | contradictory | identity_conflict |

These are architecture outcomes, not conclusions about a specimen. A held
control is evidence that the boundary behaved conservatively.
