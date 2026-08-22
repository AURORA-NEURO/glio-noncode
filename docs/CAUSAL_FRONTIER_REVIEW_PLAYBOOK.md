# Domain 11 reviewer playbook

## Reviewer role

The reviewer validates whether the artifact is internally consistent, bounded,
replayable, and suitable for the declared research use. The reviewer is not
asked to decide whether a hypothesis is true. The reviewer is asked to decide
whether the evidence receipt says exactly what it can support.

## Fast path

Run the depth audit first:

```powershell
glio-noncode causal-frontier-depth-audit
```

An accepted depth audit proves the current checked-in fixture has 18 passing
depth checks. It is a fast signal, not a substitute for reading a changed
fixture or release manifest.

Then run:

```powershell
glio-noncode causal-frontier-release
```

Inspect `state`, `accepted`, all four release checks, allowed uses, and excluded
uses. If state is `review`, stop before publishing the artifact.

## Step 1: inspect identity

Confirm:

- release ID is expected;
- version is the intended D11 version;
- fixture ID is the public aggregate fixture;
- context key is exact;
- boundary is non-patient;
- all addresses begin with `sha256:`.

An identity mismatch is a release issue even when all numeric checks pass.

## Step 2: inspect sources

Review the five source receipts. Confirm that every URI is HTTPS and that the
scope describes aggregate context. Check that the same source is not being
represented as independent evidence merely because it appears in multiple
records.

The public source list is not a patient cohort. It is a receipt list for the
research-use boundary.

## Step 3: inspect records

List records by operation and role:

```powershell
glio-noncode causal-frontier-evaluate | ConvertFrom-Json |
  Select-Object -ExpandProperty executions |
  Select-Object record_id, operation, role, state, issue_codes
```

Expected distribution:

| Operation | Positive | Controls |
| --- | ---: | ---: |
| posterior decomposition | 1 | 3 |
| driver posterior | 1 | 3 |
| selective prediction | 1 | 3 |
| dossier publication | 1 | 3 |

The controls should not be absent, filtered, or merged into a generic failure
bucket.

## Step 4: inspect C13

Open the positive C13 output. Verify that each component has named fields for
prior, likelihood, measurement, dependence penalty, raw posterior, normalized
posterior, and state.

Open the three controls. Verify that:

- zero mass is partial;
- empty input is invalid;
- out-of-bound prior is invalid.

The reviewer should not ask whether h1 is biologically correct from this
receipt. The reviewer should ask whether h1 is the top identity under the
declared bounded calculation.

## Step 5: inspect C14

Open the positive driver report. Verify that driver IDs, evidence IDs, support,
prior, posterior, and rank are all retained. Check that the top driver is only
a rank field.

Open the low-support control. Confirm that it remains present with
`low_driver_support`. A low-support row that disappears would be a material
review failure.

## Step 6: inspect C15

Open the positive prediction and confirm that score, uncertainty, threshold,
accepted list, and abstained list are retained.

Open the weak-score control and high-uncertainty control. The high-uncertainty
control should include both:

```text
prediction_uncertainty_high
selective_prediction_abstention
```

This confirms that the boundary does not hide the reason for abstention behind
a single status field.

## Step 7: inspect C16

Open the positive dossier. Confirm that it contains hypothesis IDs and evidence
addresses and that the top identity belongs to the hypothesis set.

Check that the dossier address is content based. The manifest is a research
receipt. It is not evidence of causal identification.

Inspect all three controls:

| Control | Required issue |
| --- | --- |
| unknown top identity | invalid dossier input |
| empty input | empty dossier input |
| missing address | invalid dossier input |

## Step 8: inspect policy

Policy decisions operate on the positive paths for release disposition. The
reviewer should see review allowance for supported aggregate operations and
publication allowance only for the dossier manifest.

Controls remain in evaluation and reconciliation. Their presence should not be
mistaken for a decision to release a weak input.

The key distinction is:

```text
positive operation disposition != control suppression
```

## Step 9: inspect lineage

Open the lineage JSON and confirm:

- every source ID resolves;
- each record has a fixture edge;
- each cited source has source edges;
- all 16 execution addresses are terminal;
- the graph is acyclic;
- edge operation fields match the record operation.

The current edge count is 36. A changed source list or changed record source
references should change this count and the graph address.

## Step 10: inspect metrics

Metrics should show a 1.0 overall check pass rate and positive acceptance rate
of 1.0 for the current fixture. Control rejection rate should also be 1.0.
Per-operation execution acceptance should be 0.25 because each operation has
one positive and three controls.

These numbers describe the fixture design. They do not represent a biological
effect, cohort prevalence, or clinical performance statistic.

## Step 11: inspect runtime

Runtime stages must be ordered from data audit through release bundle. Check
stage sequence, stage ID, output address, state, and duration.

Duration can vary by machine. Stage output addresses should remain stable when
the fixture and code are unchanged. A changed output address is a behavior or
serialization change and should be explained in the release notes.

## Step 12: inspect CSV review view

The CSV is a reviewer-friendly projection. It should have 16 data rows plus a
header. Every row must retain:

- record ID;
- operation;
- role;
- state;
- accepted flag;
- source count;
- issue codes;
- content address.

Use the CSV to triage records. Use JSON to inspect nested operation output and
lineage.

## Common review findings

### Missing control

If the positive record passes but a control is missing, reject the release. A
positive-only fixture cannot show that weak or invalid inputs remain bounded.

### New issue code

If an implementation emits an issue code that is not in the contract, update the
contract and fixture intentionally. Do not remove the issue from the output to
make a pass flag green.

### Context drift

If an input row has a different context key, retain the mismatch as an invalid
or review condition. Do not normalize it by truncating the key.

### Address drift

If repeated runs produce different addresses for unchanged inputs, inspect
serialization ordering, enum conversion, tuple handling, and inclusion of
runtime fields. Do not hide address drift by omitting the receipt.

### Threshold drift

If a score threshold or uncertainty boundary changes, run the scenario matrix
and update the documentation. A one-line threshold change can move a control
from accepted to abstained or vice versa.

### Dossier overreach

If release prose describes a published dossier as proof, diagnosis, treatment
guidance, or a clinical result, stop the release. The dossier is a manifest of
references and bounded ranking outputs.

## Sign-off record

A reviewer sign-off should capture:

| Field | Example |
| --- | --- |
| fixture ID | causal-frontier-public-aggregate |
| fixture version | 2026.08.d11-c13-c16.v1 |
| context key | exact key from release |
| depth audit | 18 of 18 |
| quality gate | 12 of 12 |
| evaluation | 120 of 120 |
| replay | accepted |
| release state | ready or review |
| allowed use | selected research use |
| excluded use | selected exclusions retained |
| notes | changed source, threshold, or code summary |

The sign-off is about repository evidence and boundary compliance. It is not a
claim about the truth of a biological hypothesis.

## Change review checklist

Before approving a D11 change, ask:

1. Did the change add or remove a public source receipt?
2. Did fixture counts change?
3. Did an operation gain a field or issue code?
4. Did a threshold change?
5. Did any control expected state change?
6. Did content addresses change for unchanged rows?
7. Did the CLI output shape change?
8. Did the registry evidence note change?
9. Did the quality gate count change?
10. Did the depth audit count change?
11. Did the Actions matrix run all supported Python versions?
12. Are restricted metadata markers absent from added lines?

Every yes answer should be reflected in tests or release notes.

## Exit criteria

The reviewer may accept the release candidate when:

- data audit is accepted;
- all 120 evaluation checks pass;
- all controls remain visible;
- lineage is acyclic;
- reconciliation is accepted;
- quality gate has no blocking checks;
- replay is deterministic;
- runtime is accepted;
- release state is ready;
- allowed and excluded uses are present.

If any criterion is not met, keep the artifact in review and preserve the
failure receipt for the next iteration.
