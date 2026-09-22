# Cohort recurrence analysis

The cohort recurrence primitive compares one declared target locus with a set of
distinct matched control loci. It is intended for descriptive research review;
it does not identify drivers, estimate clinical significance, or produce a
hypothesis-test p-value.

## Required observation grain

Provide one row per subject and locus. Each row records whether the locus was
callable in that subject and whether it was mutated. A mutation cannot be
recorded on a non-callable row. Duplicate observation identifiers and duplicate
subject-by-locus pairs are rejected. Inputs are bounded at 250,000 rows.

In addition to the base cohort observation fields, every target callable row
must supply all of these matching dimensions:

| Field | How it is used |
| --- | --- |
| `context` | The full reference context must match, including genome build, disease, age, cell state, territory, treatment phase, assay support, and source version. |
| `disease_class`, `ancestry_group` | Exact stratum matching. |
| `variant_class`, `sequence_context` | Exact variant-class and sequence-context matching. |
| `molecular_context`, `recurrence_phase` | Exact molecular and recurrence-phase matching. |
| `locus_length` | Exact target/control locus-length matching. |
| `batch_id`, `ascertainment_group` | Each control must match the corresponding target subject's batch and ascertainment labels. |
| `mutability_score`, `chromatin_score` | Continuous matching variables used to rank eligible controls by mean paired absolute distance. |

All listed dimensions other than mutability and chromatin scores are exact
matching requirements. Controls must
have callable observations for every callable target subject; controls with an
incomplete subject set, a non-callable paired row, or a per-subject batch or
ascertainment mismatch are excluded. Repeated rows for one control locus never
inflate the control count.

## Calculation and status

The target observed rate is its mutated count divided by its callable target
subjects. Each control locus contributes one mutation rate on that same set of
subjects. The expected background rate is the unweighted mean of selected
control-locus rates, so a locus with extra rows cannot dominate the null.
Controls are ranked deterministically by paired mutability-plus-chromatin gap,
then locus identifier. Up to 20 are selected by default; the supported limit is
1–500, while at least five are required for an estimate.

The standardized descriptive contrast is `(target rate - mean control rate) /
population SD(control rates)`. It is omitted when there is no target callable
denominator, required matching metadata are absent, fewer than five matched
controls remain, or matched-control rates have zero variance. In those cases
the status is `not_estimable`, support is zero, and uncertainty is one. A
positive `enrichment` is emitted only when the expected control rate is above
zero; zero background never creates an infinite or arbitrarily large ratio.

`support` and `uncertainty` are explicitly uncalibrated descriptive indices,
not probabilities or confidence levels. The result includes candidate,
eligible, and selected control counts; effective sample size; per-control
mutation rates; mean matching gaps; excluded-control counts; unmatched target
covariates; and limitations. Serialized results include aggregate control
counts and rates but no subject identifiers. There is no multiple-testing
correction or causal interpretation.

## Python usage

Construct `CohortObservation` rows from a documented cohort table, then call:

```python
from glio_noncode.cohort import RecurrenceModel

result = RecurrenceModel().evaluate(observations, locus_id="candidate-17")
summary = result.to_dict()
```

Inspect `summary["status"]` before using any rate or contrast. The bounded
application interface applies the same validation and estimability rules.
Non-estimable results are surfaced as an abstention rather than supported
recurrence evidence.

## Command-line usage

The input contract is packaged as `schemas/cohort_observations.schema.json`.
It is a JSON object with `schema: "glio.cohort-observations.v1"`, one target
`locus_id`, and an `observations` array. For a prepared input file:

```powershell
glio-noncode cohort-recurrence cohort-observations.json --output recurrence.json
glio-noncode cohort-recurrence cohort-observations.json --control-limit 40
```

The default is 20 selected controls; between 1 and 500 may be requested. A valid
but non-estimable analysis is still a successful command execution and returns
`status: "not_estimable"`; inspect the JSON status and limitations before using
the output. Invalid or unreadable input returns exit code 2 and a path-free
error report. Input is bounded to 128 MiB and 250,000 observation rows.
