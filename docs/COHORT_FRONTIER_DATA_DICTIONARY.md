# Domain 12 data dictionary

This dictionary names the fields used by the public aggregate cohort frontier.
Fields are descriptive and typed. A field name does not imply a clinical
interpretation.

## Fixture fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| fixture_id | string | yes | stable fixture identity |
| fixture_version | string | yes | semantic evidence version |
| context_key | string | yes | exact cohort context |
| evidence_boundary | string | yes | public aggregate boundary token |
| sources | array | yes | source receipts |
| records | array | yes | positive and control records |
| content_address | string | yes | fixture receipt |

The fixture ID is `cohort-frontier-public-aggregate`. The fixture version is
`2026.08.d12-c13-c16.v1`.

## Source receipt fields

| Field | Type | Description |
| --- | --- | --- |
| source_id | string | stable source reference |
| title | string | readable source name |
| uri | string | HTTPS source URL |
| access_note | string | aggregate boundary explanation |
| content_address | string | receipt of source metadata |

Source IDs used by the default fixture are `geo`, `dbgap`, `encode`, `pubmed`,
and `common-fund`. The IDs are local references, not claims about data access.

## Record identity fields

| Field | Type | Description |
| --- | --- | --- |
| record_id | string | operation-scoped fixture ID |
| operation | enum | operation being exercised |
| role | enum | positive or control |
| context_key | string | exact record scope |
| source_ids | array<string> | source receipt references |
| expected_state | enum | expected bounded outcome |
| expected_issue_codes | array<string> | expected issue set |
| notes | string | review explanation |
| content_address | string | record receipt |

The role is not a quality score. It labels the purpose of a fixture row.

## Subgroup payload fields

| Field | Type | Description |
| --- | --- | --- |
| group | string | stratum label |
| total | integer | aggregate denominator |
| positive | integer | aggregate positive count |
| prediction_field | string | declared binary field name |
| maximum_parity_gap | number | review threshold |

The evaluator preserves the group label and denominator. A rate is computed from
the declared total and positive values. A missing group is invalid.

## Transport payload fields

| Field | Type | Description |
| --- | --- | --- |
| analysis_id | string | analysis reference |
| source_features | array<string> | source feature IDs |
| target_features | array<string> | target feature IDs |
| overlap | number | declared feature overlap |
| distribution_shift | number | declared shift score |
| minimum_overlap | number | support threshold |
| maximum_shift | number | review threshold |

Feature sets are retained as declared. The operation does not assign meaning to
feature IDs or infer missing target fields.

## Federated payload fields

| Field | Type | Description |
| --- | --- | --- |
| feature_id | string | aggregate feature reference |
| site_id | string | site-local aggregate reference |
| count | integer | site count |
| mean | number | site aggregate mean |
| privacy_floor | integer | minimum visible count |

Site IDs may appear in the typed input but public exports contain summary values
only. A low count is review-visible and is not treated as an accepted summary.

## Discovery payload fields

| Field | Type | Description |
| --- | --- | --- |
| bundle_id | string | aggregate bundle identity |
| analysis_ids | array<string> | analysis references |
| feature_ids | array<string> | feature references |
| context_key | string | exact publication context |
| input_records | array<object> | aggregate input rows |
| evidence_boundary | string | publication boundary |

The publisher requires bundle, analysis, and feature identifiers and exact
context. The publication address covers the complete aggregate manifest.

## Execution fields

| Field | Type | Description |
| --- | --- | --- |
| record_id | string | source record ID |
| operation | string | operation value |
| role | string | positive or control |
| state | string | observed bounded state |
| accepted | boolean | whether operation accepted |
| issue_codes | array<string> | observed issue set |
| output | object | normalized operation report |
| content_address | string | execution receipt |

The execution object is separate from the fixture record. This allows
reconciliation to detect a changed state or issue set.

## Evaluation fields

| Field | Description |
| --- | --- |
| fixture_id | evaluated fixture |
| executions | sixteen record executions |
| checks | record and global checks |
| accepted | all expected checks pass |
| passed_checks | number of passing checks |
| failed_check_ids | failed check references |
| content_address | evaluation receipt |

The default evaluation has 120 checks and no failed IDs.

## Metric fields

| Field | Description |
| --- | --- |
| metric_id | stable metric name |
| value | metric value |
| numerator | supporting count when applicable |
| denominator | comparison count when applicable |
| scope | overall, positive, control, or operation |
| content_address | metric receipt |

Metric values must be interpreted with their denominator and scope.

## Lineage fields

| Field | Description |
| --- | --- |
| edge_id | stable edge identity |
| edge_kind | source or fixture relationship |
| source_node | upstream node ID |
| target_node | downstream node ID |
| content_address | edge receipt |

The lineage graph also stores terminal addresses, cycle status, and graph
content address.

## Gate fields

| Field | Description |
| --- | --- |
| check_id | blocking check name |
| passed | check result |
| severity | blocking severity |
| observed | measured value |
| required | required value |
| rationale | explanation |
| content_address | check receipt |

The gate stores twelve checks, blocking IDs, accepted state, and a gate receipt.

## Runtime fields

| Field | Description |
| --- | --- |
| run_id | caller-selected run identity |
| stage_id | runtime stage name |
| sequence | one-based order |
| state | completed stage state |
| duration_ms | measured duration |
| output_address | stage result address |
| detail | stage purpose |
| content_address | stage receipt |

Runtime durations support operational review and are not part of stable replay
semantics.

## Release fields

| Field | Description |
| --- | --- |
| release_id | release identity |
| version | release version |
| state | draft, review, ready, blocked, or published |
| bundle_address | release bundle receipt |
| quality_gate_address | quality gate receipt |
| replay_address | replay receipt |
| checks | four release checks |
| allowed_uses | bounded permitted uses |
| excluded_uses | prohibited interpretation or use |
| content_address | release receipt |

## Export fields

The review CSV has exactly these fields:

1. `record_id`;
2. `operation`;
3. `role`;
4. `state`;
5. `accepted`;
6. `source_count`;
7. `issue_codes`;
8. `content_address`.

Issue codes are joined with semicolons. The default fixture has no issue code on
four positive rows and one issue code on each of twelve control rows.

## Nullability rules

Context, record ID, operation, role, boundary, and content addresses are not
nullable. Optional operation fields may be absent only when the operation
contract declares a control path. Empty arrays are meaningful and must not be
converted into null values.

## Sorting rules

Canonical JSON sorts object keys. Fixture record order is stable and follows
operation order and role fixtures. Issue codes are sorted before reconciliation.
CSV row order follows fixture record order.

## Dictionary maintenance

When adding a field, document its type, nullability, semantic role, validation,
serialization behavior, and release impact. Add a positive or control fixture
row when the field has a new boundary. Update schema version only when the
change is breaking or changes the interpretation of an existing field.
