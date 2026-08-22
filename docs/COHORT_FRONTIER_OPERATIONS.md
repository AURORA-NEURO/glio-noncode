# Domain 12 operation handbook

This handbook describes how each cohort frontier operation behaves from input
receipt through review export. It is written for maintainers, reviewers, and
downstream integrators who need to understand the state machine without reading
the implementation first.

## Shared execution model

Every fixture record follows the same path:

1. identify the operation and role;
2. validate the exact context;
3. validate the operation payload;
4. call the underlying scientific-beta primitive;
5. normalize state and issue codes;
6. calculate the execution receipt;
7. compare with the expected fixture values;
8. include the result in evaluation, lineage, and review surfaces.

The evaluator never mutates the fixture. Expected values are read-only evidence
of the fixture contract. The observed result is a separate execution object.
This separation allows a failed implementation to be diagnosed instead of
silently rewriting its own expected result.

## Operation 13: subgroup fairness

### Input shape

The operation consumes rows with a group label and a binary outcome field. The
fixture represents rows as aggregate observations with a group, total count,
and positive count. The exact context is carried on the record rather than
inferred from the group label.

### Computation

The stratifier calculates a rate for every group:

```text
rate = positive_count / total_count
```

The parity gap for a group is the distance from the reference rate selected by
the primitive. The maximum observed gap is retained in the report. The declared
maximum parity gap is a review threshold, not a claim that values below it are
fair in every setting.

### Accepted path

`C13-POS-001` has two balanced strata. The evaluator expects:

- two strata;
- a maximum parity gap of zero;
- no review IDs;
- a `supported` state;
- no issue codes.

### Review path

`C13-CTRL-001` has a high gap in group B. The evaluator expects the group ID in
`review_ids`, a `review` state, and `parity_gap_high`. The row remains visible
in the CSV and the observability event stream.

### Invalid paths

`C13-CTRL-002` has no rows and expects `empty_fairness_input`.
`C13-CTRL-003` has a malformed group payload and expects
`invalid_fairness_input`. These are different failure classes and must not be
collapsed into one generic error.

### Review questions

- Are all groups retained?
- Are denominators visible?
- Is the gap threshold included in the output?
- Is the review group listed?
- Does the control issue match the contract vocabulary?
- Is the output bounded to aggregate data?

## Operation 14: transportability

### Input shape

Each analysis row has an analysis ID, a source feature set, a target feature
set, an overlap score, and a distribution shift score. Feature names are
opaque identifiers in the fixture; the operation does not assign biological
meaning to them.

### Computation

The estimator retains the source and target sets and evaluates two declared
signals:

- overlap must meet the minimum overlap threshold;
- shift must remain below the maximum shift threshold.

The estimator also calculates the target-minus-source feature gap. The gap is a
review signal and is never silently filled from the source set.

### Accepted path

`C14-POS-001` has complete overlap and bounded shift. The evaluator expects the
analysis ID in `transportable_ids`, no review IDs, and a `supported` state.

### Feature-gap path

`C14-CTRL-001` omits a target feature. It expects `analysis-gap` in
`review_ids` and `target_feature_gap`. A feature gap is not equivalent to a
distribution shift; downstream review must retain the distinction.

### Shift path

`C14-CTRL-002` has a shift above the threshold. It expects `analysis-shift` in
`review_ids` and `distribution_shift_high`. The source and target fields remain
in the report to make the review reproducible.

### Empty path

`C14-CTRL-003` has no analyses and expects `empty_transportability_input`.
Empty input is an input boundary, not evidence that transportability failed for
an unobserved population.

### Review questions

- Are source and target features both preserved?
- Is overlap distinct from shift?
- Are missing target features named?
- Is an empty analysis set visible?
- Are IDs stable between replay runs?

## Operation 15: federated summary

### Input shape

The summary accepts site-local aggregate observations. Each observation has a
feature ID, site ID, count, and mean. The public fixture has two sites for the
positive path and deliberately small or malformed controls.

### Computation

For each feature the report retains:

- number of contributing sites;
- total count;
- mean of the declared site means;
- maximum between-site spread;
- privacy floor;
- review IDs.

This is an aggregate summary operation. It does not reconstruct raw rows and
does not infer a pooled patient-level distribution.

### Accepted path

`C15-POS-001` has two sites with counts 10 and 12. The evaluator expects a total
count of 22, a privacy floor of five, a `supported` state, and `f-1` in
`supported_ids`.

### Privacy path

`C15-CTRL-001` has a count below the privacy floor. It expects `f-low` in
`review_ids` and `privacy_floor_violation`. The values remain available for
review only under the declared aggregate boundary.

### Empty and malformed paths

`C15-CTRL-002` expects `empty_federated_input`. `C15-CTRL-003` includes a value
that cannot be represented as a numeric mean and expects
`invalid_federated_input`. The two controls ensure that absence and malformed
presence are distinct.

### Review questions

- Is site count separate from total count?
- Is the privacy floor retained?
- Is spread retained rather than discarded?
- Are raw site rows absent from public exports?
- Does a low count remain a review state?

## Operation 16: cohort discovery

### Input shape

The publisher receives a bundle ID, exact context, feature IDs, analysis IDs,
and aggregate input records. It returns a discovery bundle with record and
publication addresses.

### Publication rule

The publisher may emit `published` only when all required aggregate fields are
present and the context equals the fixture context. The publication state is a
bounded manifest state. It is not a claim that the discovered feature is
clinically relevant or ready for patient use.

### Accepted path

`C16-POS-001` publishes the feature `f-1` under bundle
`cohort-frontier-1`. The output includes the exact context, analysis ID, input
record address, and publication address.

### Context path

`C16-CTRL-001` changes the context and expects
`invalid_cohort_discovery_input`. Exact context equality is required because a
nearby cohort is not interchangeable with the declared cohort.

### Empty and incomplete paths

`C16-CTRL-002` has no input records and expects
`empty_cohort_discovery_input`. `C16-CTRL-003` has an empty analysis set and
expects `invalid_cohort_discovery_input`.

### Review questions

- Is the context exact?
- Are feature and analysis IDs both present?
- Is the record address retained?
- Is the publication address deterministic?
- Are excluded uses present in the release manifest?

## Cross-operation controls

The fixture is intentionally balanced by operation:

| Operation | Positive | Controls | Total |
| --- | ---: | ---: | ---: |
| subgroup fairness | 1 | 3 | 4 |
| transportability | 1 | 3 | 4 |
| federated summary | 1 | 3 | 4 |
| cohort discovery | 1 | 3 | 4 |

This structure makes it possible to compare operation coverage without treating
one operation as more important because it has more records.

## States and issue handling

The evaluator produces one execution state and a tuple of issue codes per
record. The expected issue tuple is sorted before reconciliation. A record with
one expected issue must not produce zero issues, a different issue, or a second
unexplained issue.

Accepted positives have no issue codes. Controls have exactly one expected issue
in the default fixture. Future fixtures may use multiple issues, but the
contract and reconciliation tests must then assert the complete sorted set.

## Operation metrics

The metrics module produces overall checks, positive acceptance, control
rejection, and one acceptance metric per operation. The default report has 11
rows:

1. overall check pass rate;
2. positive acceptance rate;
3. control rejection rate;
4. subgroup fairness acceptance rate;
5. transportability acceptance rate;
6. federated summary acceptance rate;
7. cohort discovery acceptance rate;
8. supported execution count;
9. review execution count;
10. invalid execution count;
11. published execution count.

Metrics are descriptive. They are useful for fixture health and regression
review, not for estimating a population property.

## Lineage

Every source receipt connects to each execution that cites it. Every fixture
record connects to its execution. The default graph has 20 source-to-execution
edges and 16 fixture-to-execution edges. The terminals are the 16 record
addresses. A cycle or missing terminal blocks release.

## Reconciliation

Reconciliation joins each fixture record to its execution and the operation
policy decision. It compares expected state and issue codes exactly. The report
retains a row for every record, including controls and invalid inputs. A
reconciled report means the code matches the declared fixture contract; it does
not mean that the fixture proves a scientific claim.

## Export order

For a complete review package, export in this order:

1. data audit;
2. contracts;
3. schema;
4. evaluation;
5. metrics;
6. lineage;
7. policy;
8. quality gate;
9. runtime;
10. release;
11. review CSV;
12. depth audit.

The release manifest should be distributed only with the data audit, evaluation,
quality, replay, and excluded-use sections available to the reader.

## Maintainer checklist

- [ ] Each operation has one positive record.
- [ ] Each operation has three controls.
- [ ] Each control has one expected issue.
- [ ] Each issue is in the contract vocabulary.
- [ ] Each execution is content-addressed.
- [ ] Each operation has a schema.
- [ ] Each operation has a policy rule.
- [ ] Each operation appears in metrics.
- [ ] Each operation appears in lineage.
- [ ] Each operation appears in the review CSV.
- [ ] Each operation appears in the depth audit.
