# Domain 12 review playbook

Use this playbook when inspecting a cohort frontier run, comparing two runs, or
deciding whether a release manifest is suitable for aggregate research use.
The playbook assumes that the reader wants the computation to remain bounded,
reproducible, and explicit about gaps.

## 1. Establish identity

Record these values before reading the result:

- fixture ID;
- fixture version;
- schema version;
- exact context key;
- evidence boundary;
- run ID;
- release ID;
- content address.

The identity values are the frame for every later observation. If the context or
boundary differs, do not compare the reports as if they were the same run.

## 2. Verify source receipts

The default fixture has five public source receipts. For each receipt check:

1. the source ID is non-empty;
2. the title is readable;
3. the URI is HTTPS;
4. the access note says aggregate evidence;
5. the content address is present;
6. the receipt is cited by at least one fixture record.

A source receipt identifies provenance. It does not prove that the source is
complete, current, or appropriate for a clinical decision.

## 3. Read the record inventory

The default inventory is:

| Operation | Positive | Controls | Review focus |
| --- | --- | --- | --- |
| subgroup fairness | C13-POS-001 | C13-CTRL-001..003 | gaps and strata |
| transportability | C14-POS-001 | C14-CTRL-001..003 | feature overlap and shift |
| federated summary | C15-POS-001 | C15-CTRL-001..003 | floor and spread |
| cohort discovery | C16-POS-001 | C16-CTRL-001..003 | exact context and manifest |

Check that controls have not been filtered before evaluation. The control count
is part of the quality gate because review boundaries are evidence.

## 4. Review positive paths

Review positive records in operation order. For each one, confirm:

- the execution is accepted;
- the state is supported or published;
- the issue tuple is empty;
- the output has the expected operation fields;
- the content address is present;
- the state matches the fixture expectation.

Positive-path review is a structural check. It does not establish calibration,
external validity, causal relevance, or clinical utility.

## 5. Review controls

Review each control as a test of one boundary. Ask whether the observed issue is
the exact issue named by the fixture and whether the output still carries useful
context for diagnosis.

### Subgroup controls

- High gap: verify the affected group remains in `review_ids`.
- Empty input: verify the state is invalid and the issue is explicit.
- Missing group: verify the payload is not coerced into a default group.

### Transportability controls

- Feature gap: verify source and target sets remain visible.
- Shift: verify overlap is not used to hide the shift.
- Empty input: verify no absent population is treated as a negative finding.

### Federated controls

- Privacy floor: verify low counts remain review-visible.
- Empty input: verify missing site data is not summarized as zero effect.
- Malformed mean: verify the invalid payload is quarantined from support.

### Discovery controls

- Context mismatch: verify near-matching context does not publish.
- Empty input: verify no empty manifest is published.
- Empty analysis set: verify feature-only output is not sufficient.

## 6. Interpret metrics

Metrics are fixture health indicators. Read the denominator before the value.
For example, a 100% positive acceptance rate is based on four positive records,
not a population. A 100% control rejection rate means the controls reached the
expected non-accepted boundary; it does not mean all possible bad inputs are
covered.

The default report should have 11 rows and these key values:

| Metric | Expected |
| --- | ---: |
| overall_check_pass_rate | 1.0 |
| positive_acceptance_rate | 1.0 |
| control_rejection_rate | 1.0 |
| subgroup_fairness_acceptance_rate | 0.25 |
| transportability_acceptance_rate | 0.25 |
| federated_summary_acceptance_rate | 0.25 |
| cohort_discovery_acceptance_rate | 0.25 |

The operation acceptance rows count all four records in their operation. The
three controls are expected to be non-accepted.

## 7. Inspect policy decisions

The policy should return four decisions, one per operation. Confirm that the
decision references the positive execution and that its issue tuple is empty.
Controls are not removed from the evaluation to make these decisions pass.

The discovery decision may allow publication because the output is a bounded
aggregate manifest. Review and transport decisions allow method review rather
than asserting transport or fairness in a new population.

## 8. Inspect lineage

The default lineage graph has:

- 20 source-to-execution edges;
- 16 fixture-to-execution edges;
- 36 edges in total;
- 16 terminal addresses;
- no cycles.

Trace one record in each operation from its source receipt to its execution and
then to the terminal address. Trace one control as well as one positive record.
This catches a common failure in which only supported records receive lineage.

## 9. Inspect reconciliation

Reconciliation must be exact. The report should have 16 items and no mismatched
record IDs. Compare both state and sorted issue codes. A matching state with a
wrong issue code is still a failed reconciliation.

The policy decision is retained on every reconciliation row. This permits a
reviewer to distinguish a computational mismatch from a policy decision that
correctly keeps a result in review.

## 10. Inspect quality gate and runtime

The quality gate has 12 blocking checks. The runtime has ten stages in sequence:

1. data audit;
2. contracts;
3. schema;
4. fixture replay;
5. metrics;
6. policy;
7. lineage;
8. reconciliation;
9. quality gate;
10. release bundle.

Every stage has a sequence number, output address, duration, and detail string.
Durations support performance review but are not acceptance thresholds.

## 11. Inspect replay

Replay executes the same fixture and compares stable fields. The replay ID may
differ; the comparison intentionally excludes run identifiers that should vary.
The default replay should report 120 checks, 120 passing checks, no drift
fields, and an accepted receipt.

When drift occurs, inspect the drift fields in this order:

1. fixture content address;
2. execution content addresses;
3. issue code order;
4. state values;
5. output serialization;
6. release fields.

Do not accept a replay with drift merely because the final boolean is true.

## 12. Review release use

Before sharing a release, confirm the allowed uses:

- aggregate cohort review;
- method development;
- reproducibility testing;
- research triage.

Confirm the excluded uses:

- patient care;
- diagnosis;
- prognosis;
- treatment selection;
- individual risk;
- clinical cohort claims.

If either list is absent, the manifest is incomplete even if the computational
checks pass.

## Comparing two versions

When comparing versions, first compare fixture and schema versions. Then compare
the canonical fixture, contract issue vocabulary, execution map, metrics, and
release state. Use content addresses to identify changes. A changed source note
can change a fixture address even when operation values are unchanged.

Classify differences as:

| Class | Meaning |
| --- | --- |
| expected | versioned threshold or fixture change |
| structural | field, operation, or issue change |
| computational | observed state or value change |
| provenance | source receipt or note change |
| policy | allowed or excluded use change |

Every non-expected difference needs a review note before merge.

## Handling a failed control

If a control unexpectedly passes, treat it as a regression in the boundary. Do
not weaken the control to fit the implementation. First inspect the input
payload, then the underlying primitive, then the wrapper issue mapping, then
the evaluator check.

If a control emits an unexpected issue, preserve the failing output and add a
focused regression test. The issue vocabulary is part of the contract and must
not be changed just to make a run green.

## Handling a failed positive

If a positive record becomes review or invalid, inspect context, payload shape,
thresholds, and source references in that order. A positive failure may indicate
an intentional threshold update; if so, update the fixture version and the
documentation rather than silently changing the expected state.

## Export review

Review CSV is the compact queue. It must have one header and 16 data rows. The
columns are fixed:

```text
record_id,operation,role,state,accepted,source_count,issue_codes,content_address
```

CSV is for review and handoff. The JSON release manifest remains the source for
complete policy and gate detail.

## Final sign-off

- [ ] Identity values captured.
- [ ] Source receipts inspected.
- [ ] Positive paths accepted.
- [ ] All twelve controls retained and classified.
- [ ] Metrics denominators understood.
- [ ] Policy decisions reviewed.
- [ ] Lineage acyclic and complete.
- [ ] Reconciliation exact.
- [ ] Twelve gate checks pass.
- [ ] Ten runtime stages pass.
- [ ] Replay has no drift.
- [ ] Use boundary is attached to the handoff.
