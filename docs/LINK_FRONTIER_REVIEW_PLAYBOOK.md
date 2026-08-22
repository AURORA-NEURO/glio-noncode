# Domain 10 link frontier review playbook

This playbook gives a repeatable review route for the Domain 10 C13-C16
frontier. The reviewer checks evidence shape, scope, controls, and limitations.
The reviewer is not deciding whether a biological mechanism is true.

## Review charter

The review must answer five questions:

1. Is the evidence boundary explicit?
2. Is exact context retained on every record?
3. Are positive and control records both executed?
4. Are uncertainty, alternatives, and missingness visible?
5. Does the release point to the evaluated data and quality gate?

If any answer is unknown, the release remains in review.

## Artifact table

| Artifact | Command | Review question |
| --- | --- | --- |
| data audit | `audit-link-frontier-data` | is the fixture closed? |
| evaluation | `evaluate-link-frontier-fixture` | did every record execute? |
| depth audit | `link-frontier-depth-audit` | did output fields survive? |
| replay | `replay-link-frontier` | is the run deterministic? |
| contracts | `link-frontier-contracts` | are fields and limits declared? |
| schema | `link-frontier-schema` | does coverage match contracts? |
| policy | `link-frontier-policy` | do bounded-use rules pass? |
| metrics | `link-frontier-metrics` | are counts stable? |
| review view | `link-frontier-review-view` | are controls visible? |
| pipeline | `run-link-frontier-pipeline` | did stages complete? |
| release | `build-link-frontier-release` | is the state accepted? |

## Boundary checklist

Open the data audit and verify:

- boundary is `public_aggregate_non_patient`;
- fixture version is `2026.08.d10-c13-c16.v1`;
- context is `GRCh38|glioma|adult|stem_like|core|unknown`;
- source count is five;
- record count is sixteen;
- positive count is four;
- control count is twelve;
- all four operation values appear;
- every URI uses HTTPS;
- every source ID resolves.

Do not proceed if a custom fixture has a second context key. A multi-context
fixture requires a new contract, version, and control matrix.

## Source receipt checklist

For every source receipt, inspect:

- stable source ID;
- title;
- URI;
- source kind;
- release label;
- scope statement;
- content address.

The scope statement prevents a general public archive receipt from being read as
support for an operation it did not provide.

Every record must map to one or more source IDs. An unresolved source blocks
release.

## Record envelope checklist

Inspect one positive and every control for each operation. Check:

- stable record ID;
- operation matching the payload;
- explicit role;
- exact context;
- source IDs;
- non-empty payload except for an intentional empty-input control;
- expected state;
- expected issue codes;
- review-facing description;
- content address.

Expected state is fixture data. It is not a runtime default.

## C13 dependence correction

C13 verifies how correlated link support is represented.

### Positive path

Confirm three links are present. Confirm two links share one dependence group
and a third link has a second group. Confirm each output retains:

- link ID;
- context key;
- raw support;
- dependence group;
- group size;
- corrected support;
- state;
- content address.

Corrected support must not exceed raw support. The operation is a descriptive
transform, not a probability calibration or mechanism claim.

### Controls

| Control | Expected handling |
| --- | --- |
| zero support | `partial`, `zero_corrected_support` |
| empty rows | `invalid`, `empty_dependence_input` |
| support above one | `invalid`, `invalid_dependence_input` |

If a control has no issue code, stop review. The control has lost its purpose.

## C14 target-gene ranking

C14 verifies that a ranking view retains alternatives.

### Positive path

Confirm one variant, one element, two candidate genes, component score maps,
deterministic totals, contiguous ranks, a top-gene map, and the lower-ranked
gene in the full list. The top map is a convenience index and never a deletion
operation.

### Controls

| Control | Expected handling |
| --- | --- |
| empty scores | `partial`, `zero_rank_support` |
| missing gene | `invalid`, `invalid_rank_input` |
| empty rows | `invalid`, `empty_rank_input` |

## C15 calibration and abstention

C15 verifies that calibration uncertainty can block acceptance.

### Positive path

Confirm predicted score, observed score, calibration error, uncertainty,
accepted IDs, abstained IDs, and threshold values are retained.

### Controls

| Control | Expected handling |
| --- | --- |
| high uncertainty | `partial`, `link_uncertainty_high` |
| high error | `partial`, `link_calibration_error_high` |
| empty rows | `invalid`, `empty_calibration_input` |

An abstained path is review material. It is not a negative observation.

## C16 publication

C16 verifies that a bundle is traceable to exact context and sources.

### Positive path

Confirm bundle ID, exact context, sorted link IDs, records address, bundle
address, and published state.

### Controls

| Control | Expected handling |
| --- | --- |
| context mismatch | `invalid`, `publication_context_mismatch` |
| missing source | `invalid`, `invalid_publication_input` |
| empty rows | `invalid`, `empty_publication_input` |

## Depth audit

The depth audit contains fifty-one checks:

| Band | Operation checks | Contract checks |
| --- | ---: | ---: |
| C13 | 7 | 5 |
| C14 | 8 | 5 |
| C15 | 8 | 5 |
| C16 | 8 | 5 |
| Total | 31 | 20 |

The operation reports contain 12 checks for C13 and 13 for every other band.
Inspect a failed check ID rather than only the aggregate state. Depth failures
usually indicate a dropped field, changed ordering, or altered control branch.

## Reconciliation

Reconciliation should report sixteen state matches and sixteen issue matches.
Matching states with mismatching issue codes is not accepted.

For each item inspect expected state, observed state, expected issue codes,
observed issue codes, state match, issue match, and content address.

## Policy

The policy report should have twelve passing rules:

1. boundary;
2. context;
3. source closure;
4. positive/control separation;
5. missingness;
6. dependence grouping;
7. alternatives;
8. calibration thresholds;
9. publication path;
10. interpretation limits;
11. content addresses;
12. deterministic evaluation.

Controls are expected review material and should not by themselves fail policy.

## Replay

Run replay after evaluation and before release. Confirm first and second
evaluation addresses, every record address, states, and issue codes match.

If replay differs, preserve both reports. Compare row order, sort keys,
threshold defaults, source receipts, issue codes, serialization, and output
fields before changing expectations.

## Review queue

The default view has twelve rows. Accepted positives are absent and controls
remain present. Inspect priority 3 rows first, then priority 2 rows.

| Priority | Meaning |
| ---: | --- |
| 3 | malformed or rejected input |
| 2 | threshold or evidence review |
| 1 | low-severity review |

Actions should identify remediation: repair malformed input, inspect a
threshold, block context transport, or restore a source receipt.

## Metrics

Expected default values:

| Metric | Value |
| --- | ---: |
| records | 16 |
| positives | 4 |
| controls | 12 |
| executions | 16 |
| positive acceptance rate | 1.0 |
| control rejection rate | 1.0 |

The operation count map contains four values with four records each. Metrics
describe fixture behavior; they do not estimate real-world accuracy.

## Runtime

The pipeline stages must appear in this order:

```text
load
evaluate
reconcile
lineage
policy
schema
metrics
quality
complete
```

Every stage has a state, output address, detail, and content address. The final
stage must match the quality gate.

## Release

The release state is `released` only when the pipeline is accepted. The
manifest must include release ID, version, fixture ID, context, boundary,
pipeline address, quality address, record count, source count, and limitations.

Read every limitation before approving the manifest. Limitations are part of
the output contract.

## Exports

Generate receipts CSV, review CSV, review Markdown, and metrics CSV. Check fixed
header order, newline stability, visible issue codes, visible source and
context fields, bounded raw input, and row addresses.

```powershell
glio-noncode export-link-frontier-receipts-csv --output link-receipts.csv
glio-noncode export-link-frontier-review-csv --output link-review.csv
glio-noncode export-link-frontier-review-markdown --output link-review.md
glio-noncode export-link-frontier-metrics-csv --output link-metrics.csv
```

## Stop conditions

Stop the release if:

- boundary is not public aggregate;
- contexts differ without a contract;
- a positive record fails;
- a control is silently accepted;
- an issue code disappears;
- alternatives disappear from ranking;
- uncertainty is dropped;
- a source receipt is unresolved;
- replay is non-deterministic;
- depth audit fails;
- limitations are missing.

## Sign-off record

Record the exact values below in the build note:

```text
fixture_id:
fixture_version:
context_key:
evidence_boundary:
evaluation_address:
depth_address:
replay_address:
quality_address:
pipeline_address:
release_address:
```

This identifies the evaluated surface. It does not turn a candidate link into a
scientific or clinical conclusion.
