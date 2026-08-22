# Domain 11 failure modes and response matrix

## Why failure modes are first-class

The causal frontier is designed around bounded failure. Empty data, weak scores,
uncertain predictions, invalid identities, and source drift are not exceptional
cases. They are evidence about where the boundary is safe.

The response to a failure is to retain the record, attach an issue code, and
preserve the receipt. The response is not to silently drop the row or replace a
missing value with a favorable default.

## Severity vocabulary

| Severity | Meaning | Release effect |
| --- | --- | --- |
| info | context worth retaining | no direct block |
| warning | quality concern | review recommended |
| review | output needs inspection | positive path may require review |
| blocking | contract or release boundary failure | release blocked |

Execution states and gate severities are related but not identical. A partial
execution can be useful for a control. A blocking gate check prevents release
of the bundle that contains it.

## Fixture failures

### Wrong fixture version

Symptom: `fixture_version` is not the current pinned version.

Response: inspect whether the fixture is intentionally from another release.
Use the matching evaluator and schema if it is a supported historical artifact;
otherwise reject the run as incompatible.

### Context mismatch

Symptom: a record context differs from the fixture context.

Response: retain the record and mark the context check failed. Do not shorten,
split, or fuzzy-match the key. Exact context is part of every operation receipt.

### Missing source receipt

Symptom: a record cites a source ID absent from the source list.

Response: fail source resolution and lineage checks. Add the receipt or remove
the citation intentionally; do not create a placeholder URI.

### Non-HTTPS source

Symptom: a receipt uses an insecure or malformed URI.

Response: keep the URI for diagnosis, fail the source audit, and replace it with
a verified HTTPS public source before release.

### Duplicate identity

Symptom: source IDs or record IDs are repeated.

Response: determine whether the duplicate is accidental or a deliberate alias.
The current fixture requires unique IDs. Use a new stable ID if two rows are
distinct.

## C13 failures

### Zero posterior mass

Symptom: all raw component products equal zero.

Response: keep the components, return partial state, and attach
`zero_posterior_mass`. Review the priors, measurements, penalties, and source
paths. Do not convert the zero into a negative biological result.

### Empty posterior input

Symptom: `input_records` is empty.

Response: return invalid state with `empty_posterior_input`. The empty list is
useful as a control because it proves the adapter does not invent a hypothesis.

### Invalid posterior range

Symptom: prior, likelihood, measurement, or penalty is outside 0 through 1 or
is not numeric.

Response: return invalid state with `invalid_posterior_input`. Preserve the error
text in the execution receipt and correct the fixture or upstream adapter.

## C14 failures

### Low driver support

Symptom: support is below `minimum_support`.

Response: retain the ranked driver row with review state and
`low_driver_support`. A low-support top row is still low support.

### Empty driver input

Symptom: no driver hypothesis rows are present.

Response: return invalid state with `empty_driver_input`. Do not publish an empty
driver report.

### Invalid driver prior

Symptom: prior is negative or above one.

Response: return invalid state with `invalid_driver_input`. The invalid prior
must not be clamped silently because clamping changes the declared input.

## C15 failures

### Weak score

Symptom: score is below the uncertainty-aware threshold.

Response: return partial state with `selective_prediction_abstention`. Preserve
the score, uncertainty, threshold, and abstained ID.

### High uncertainty

Symptom: uncertainty exceeds `maximum_uncertainty`.

Response: return partial state with `prediction_uncertainty_high`. If the score
also fails the threshold, retain both issue codes.

### Empty prediction input

Symptom: no predictions are present.

Response: return invalid state with `empty_prediction_input`. The report should
not contain a fabricated accepted list.

### Non-finite uncertainty

Symptom: uncertainty is NaN or infinite.

Response: return invalid state with `invalid_prediction_input`. Non-finite
values cannot be used to establish an abstention threshold.

## C16 failures

### Unknown top identity

Symptom: `top_hypothesis_id` is not in `hypothesis_ids`.

Response: return invalid state with `invalid_dossier_input`. The manifest cannot
bind a top identity that was not declared.

### Missing evidence address

Symptom: `evidence_addresses` is empty or contains an empty value.

Response: return invalid state with `invalid_dossier_input`. The dossier must
point to receipts, not only names.

### Empty dossier input

Symptom: the record has no input rows.

Response: return invalid state with `empty_dossier_input`, even if metadata
fields are present. This keeps the positive path and empty control distinct.

### Empty hypothesis set

Symptom: no hypothesis IDs are declared.

Response: return invalid state with `invalid_dossier_input`. A dossier without
an identity set cannot be reviewed.

## Cross-cutting failures

### Unknown issue code

Symptom: execution emits a code absent from the contract registry.

Response: fail the issue-vocabulary quality check. Update the contract, fixture,
tests, and documentation intentionally before release.

### Address drift

Symptom: repeated deterministic runs have different execution addresses.

Response: compare canonical JSON, enum conversion, tuple ordering, and input
normalization. Runtime timing and run IDs must not enter operation addresses.

### Lineage cycle

Symptom: a child receipt eventually appears as its own ancestor.

Response: block the quality gate. Inspect parent and child address creation and
ensure derived outputs are never reused as source roots.

### Reconciliation mismatch

Symptom: expected state or issue tuple differs from observed output.

Response: retain the mismatch ID and inspect the smallest changed adapter.
Update expectations only when the behavior change is deliberate and documented.

### Release review state

Symptom: the release manifest has `review` state.

Response: do not publish as ready. Use the checks and allowed-use list to
identify what can still be inspected safely.

### Export shape change

Symptom: JSON or CSV fields are missing or renamed.

Response: update the schema and CLI tests. The CSV is a projection, so preserve
the full JSON receipt for downstream consumers.

## Incident response sequence

1. retain the failing artifact;
2. record the run ID and content address;
3. identify the first failed gate check;
4. inspect the related record and source edges;
5. reproduce with the smallest fixture;
6. add or update a control test;
7. update contract and schema if the boundary changed;
8. rerun full depth audit;
9. rerun Actions across supported Python versions;
10. write a release note describing the behavior change.

## Prohibited shortcuts

Do not:

- delete controls to make counts pass;
- coerce invalid numbers into range;
- replace missing addresses with labels;
- ignore context drift;
- suppress a second issue code;
- treat a rank as proof;
- use a public source list as an individual cohort;
- publish a review state as ready;
- remove an excluded use from the release manifest;
- change expected values without a test.

## Maintenance checklist

For each new failure mode, add:

- a stable issue code;
- a contract entry;
- a fixture record;
- expected state and issue tuple;
- evaluator behavior;
- reconciliation coverage;
- a depth or quality check;
- CLI or API test;
- documentation entry.

## Final response table

| Result | Meaning |
| --- | --- |
| accepted and ready | all current release checks pass |
| accepted evaluation, review release | operations are reproducible but release checks need review |
| partial execution | output exists with a retained issue |
| invalid execution | input violated the operation contract |
| failed data audit | fixture boundary or source manifest is not trusted |
| failed reconciliation | implementation and declared expectation differ |
| blocked quality gate | release must stop until the check is resolved |

The failure receipt is part of the product surface. It is the evidence that the
system remains honest at the edge of its declared support.
