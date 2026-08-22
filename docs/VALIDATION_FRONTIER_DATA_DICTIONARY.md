# Domain 13 planning data dictionary

This dictionary defines the public aggregate fixture and release fields.

## Fixture

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| fixture_id | string | yes | stable fixture identity |
| fixture_version | string | yes | evidence version |
| context_key | string | yes | exact planning context |
| evidence_boundary | string | yes | aggregate boundary token |
| sources | array | yes | source receipts |
| records | array | yes | positive and control rows |
| content_address | string | yes | fixture receipt |

The default identity is `validation-frontier-public-aggregate` and version
`2026.08.d13-c01-c04.v1`.

## Source receipt

| Field | Type | Description |
| --- | --- | --- |
| source_id | string | stable source reference |
| title | string | readable title |
| uri | string | HTTPS source URL |
| access_note | string | public aggregate note |
| content_address | string | metadata receipt |

## Record identity

| Field | Type | Description |
| --- | --- | --- |
| record_id | string | stable row ID |
| operation | enum | one of four planning operations |
| role | enum | positive or control |
| context_key | string | exact row context |
| source_ids | array<string> | source references |
| payload | object | typed operation input |
| expected_state | enum | bounded expected state |
| expected_issue_codes | array<string> | expected issue set |
| notes | string | review explanation |
| content_address | string | record receipt |

## Hypothesis fields

| Field | Type | Description |
| --- | --- | --- |
| hypothesis_id | string | planning hypothesis |
| variant_id | string | variant reference |
| element_id | string | regulatory element reference |
| gene_id | string | gene reference |
| state_id | string | state reference |
| mechanism | string | declared mechanism |
| context_key | string | exact context |
| state | enum | typed causal state |
| support_proxy | number | bounded proxy value |
| uncertainty | number | bounded uncertainty |
| factor_graph_id | string | graph reference |
| factor_ids | array<string> | factor references |
| missing_evidence | array<string> | unresolved channels |
| contradictory_edges | array<string> | contradiction references |
| limitations | array<string> | planning limitations |

## Constraint fields

| Field | Description |
| --- | --- |
| constraint_id | constraint identity |
| assay | assay value |
| context_key | exact route context |
| model_system | required model |
| min_insert_length | lower insert bound |
| max_insert_length | upper insert bound |
| max_constructs | construct budget |
| required_controls | required controls |
| required_readouts | required readouts |
| require_both_alleles | paired-allele switch |

## Inventory fields

| Field | Description |
| --- | --- |
| assay | available assay |
| model_systems | supported models |
| min_insert_length | lower capability bound |
| max_insert_length | upper capability bound |
| controls | available controls |
| readouts | available readouts |
| source_id | inventory receipt |
| feasibility | declared feasibility value |

## Target fields

| Field | Description |
| --- | --- |
| target_id | target identity |
| variant_id | variant identity |
| element_id | element identity |
| sequence | reference sequence |
| variant_offset | allele offset |
| reference_allele | expected reference allele |
| alternate_allele | declared alternate allele |
| context | structured reference context |
| source_id | sequence receipt |

## Execution

| Field | Description |
| --- | --- |
| record_id | source row |
| operation | operation value |
| role | positive or control |
| state | normalized observed state |
| accepted | positive expected-path acceptance |
| issue_codes | normalized issue tuple |
| output | typed planning output |
| content_address | execution receipt |

## Evaluation and release

The evaluation has fixture ID, executions, checks, accepted, passed checks,
failed IDs, and content address. The quality gate has check ID, passed, severity,
observed, required, rationale, and address for twelve rows.

The release has release ID, version, state, bundle address, gate address, replay
address, four release checks, allowed uses, excluded uses, and address.

## CSV fields

The review CSV columns are:

```text
record_id,operation,role,state,accepted,source_count,issue_codes,content_address
```

The default export has one header and sixteen data rows. Controls are not
filtered.

## Nullability and sorting

Identity, context, operation, role, source IDs, and addresses are non-nullable.
Empty inventory and target arrays are meaningful control inputs. Canonical JSON
sorts object keys, issue codes are sorted for reconciliation, and CSV follows
fixture record order.

## Maintenance

Adding a field requires schema, contract, fixture, test, documentation, and
release review. Change fixture and schema versions for breaking semantics.
