# Domain 10 link frontier operations

This playbook is the operator-facing reference for the Domain 10 C13-C16
frontier. It describes inputs, outputs, controls, review priorities, and the
release sequence.

## Quick start

Run the default fixture:

```powershell
glio-noncode run-link-frontier-pipeline --run-id link-operator --output link-pipeline.json
```

Confirm the final stage:

```powershell
(Get-Content link-pipeline.json | ConvertFrom-Json).accepted
```

The expected value is `True` for the checked-in fixture.

Run the depth audit separately:

```powershell
glio-noncode link-frontier-depth-audit --output link-depth.json
```

The expected count is fifty-one passed checks.

## Input handling

Without an input path, commands use the deterministic public aggregate
fixture. With an input path, the JSON loader requires the complete fixture
envelope. A custom fixture must preserve the declared public boundary and exact
context.

The loader does not merge a custom record into the default fixture. This keeps
the content address and source closure meaningful.

An input path should be a file created by the fixture exporter or an equivalent
JSON document with the required fields. The loader rejects scalar JSON,
unknown operation values, unknown roles, empty source lists, and missing
content addresses when they are required by the record type.

## Recommended run sequence

1. `audit-link-frontier-data`;
2. `evaluate-link-frontier-fixture`;
3. `link-frontier-depth-audit`;
4. `replay-link-frontier`;
5. `link-frontier-policy`;
6. `link-frontier-schema`;
7. `link-frontier-metrics`;
8. `link-frontier-review-view`;
9. `link-frontier-quality-gate`;
10. `run-link-frontier-pipeline`;
11. `build-link-frontier-release`.

The quality gate can be run directly, but the sequence above makes it easier to
locate a failing boundary.

## C13 operator notes

Use C13 when multiple link observations may share an assay or source group.
The operation is useful for inspecting duplicate-support pressure. It is not a
causal correction.

Review these fields first:

- `dependence_group`;
- `group_size`;
- `raw_support`;
- `corrected_support`;
- `state`;
- `issue_codes`.

Priority 3 review is assigned to malformed input. Priority 2 is assigned to
explicit zero or threshold review. A positive link with corrected support is
not automatically a release-grade conclusion.

Control interpretation:

| Control | Expected handling |
| --- | --- |
| zero support | `partial` with `zero_corrected_support` |
| empty rows | `invalid` with `empty_dependence_input` |
| support above one | `invalid` with `invalid_dependence_input` |

## C14 operator notes

Use C14 to inspect a candidate ranking view while retaining all candidates.
The operation is not a preferred-target selector.

Review these fields first:

- `variant_id`;
- `element_id`;
- `gene_id`;
- `component_scores`;
- `total_score`;
- `rank`;
- `top_gene_by_variant`.

The top map is a convenience index. The full rank list remains authoritative
for review. If two candidates are tied, the deterministic ordering is visible
in the rank list and should not be interpreted as biological precedence.

Control interpretation:

| Control | Expected handling |
| --- | --- |
| empty scores | `partial` with `zero_rank_support` |
| missing gene | `invalid` with `invalid_rank_input` |
| empty rows | `invalid` with `empty_rank_input` |

## C15 operator notes

Use C15 when predicted link support can be compared with an optional observed
score. Always record the thresholds used for the run.

Review these fields first:

- `predicted_score`;
- `observed_score`;
- `calibration_error`;
- `uncertainty`;
- `abstained`;
- `issues`;
- `accepted_ids`;
- `abstained_ids`.

An abstained row is a request for review. It is not a negative control outcome
and it is not evidence that the candidate is false.

Control interpretation:

| Control | Expected handling |
| --- | --- |
| high uncertainty | `partial` with `link_uncertainty_high` |
| high error | `partial` with `link_calibration_error_high` |
| empty rows | `invalid` with `empty_calibration_input` |

## C16 operator notes

Use C16 to bind a selected set of descriptive link records into a content-
addressed bundle. The bundle must contain exact context and source IDs.

Review these fields first:

- `bundle_id`;
- `context_key`;
- `link_ids`;
- `records_address`;
- `bundle_address`;
- `state`.

Control interpretation:

| Control | Expected handling |
| --- | --- |
| context mismatch | `invalid` with `publication_context_mismatch` |
| missing source | `invalid` with `invalid_publication_input` |
| empty rows | `invalid` with `empty_publication_input` |

## Review queue

The review view excludes accepted positive records and retains all controls.
Each row contains:

- record ID;
- operation;
- role;
- state;
- priority;
- issue codes;
- action;
- context key;
- content address.

Priority values:

| Priority | Meaning |
| ---: | --- |
| 3 | malformed or rejected input requiring remediation |
| 2 | explicit threshold or evidence review |
| 1 | low-severity review state |

The source view is separate from the review queue. It lists source IDs, public
URIs, release labels, scope, and record counts. It does not imply source
quality beyond the receipt fields.

## Metrics

The metrics report includes:

- total records;
- positive records;
- control records;
- execution count;
- passed and failed check counts;
- state counts;
- operation counts;
- issue counts;
- positive acceptance rate;
- control rejection rate.

Expected default values:

| Metric | Value |
| --- | ---: |
| records | 16 |
| positives | 4 |
| controls | 12 |
| executions | 16 |
| positive acceptance rate | 1.0 |
| control rejection rate | 1.0 |

Metrics are operational summaries. They are not model performance estimates.

## Replay and drift

Replay should be run after changing a fixture, contract, adapter, or serializer.
The report compares execution state, issue codes, execution address, and full
evaluation address.

A mismatch can arise from:

- changed row order;
- changed sort key;
- changed default threshold;
- changed source receipt;
- changed issue code;
- changed serialization;
- changed operation output field.

Treat a mismatch as a release review item. Do not update the expected address
until the changed field and its reason are documented.

## Policy review

The policy report should be accepted before release. Inspect failed rule IDs if
it is not. Boundary, source closure, publication, and interpretation rules are
blocking. Missingness, dependence, alternative retention, calibration,
addresses, and deterministic evaluation are review rules.

The policy checks are intentionally redundant with the quality gate. Redundant
checks make a release failure easier to localize.

## Release procedure

1. Run the full CLI sequence.
2. Confirm `link-frontier-depth-audit` has 51 passed checks.
3. Confirm replay is deterministic.
4. Confirm the quality gate has 12 passed checks.
5. Confirm the release state is `released`.
6. Export receipts and review CSV.
7. Export review Markdown.
8. Store the release manifest address with the build record.

The release manifest includes the fixture ID, version, context, evidence
boundary, pipeline address, quality address, record count, source count, state,
and limitations.

## Export commands

```powershell
glio-noncode export-link-frontier-receipts-csv --output link-receipts.csv
glio-noncode export-link-frontier-review-csv --output link-review.csv
glio-noncode export-link-frontier-review-markdown --output link-review.md
glio-noncode export-link-frontier-metrics-csv --output link-metrics.csv
```

Every export is newline-stable. The export receipt records byte count and a
content address.

## Troubleshooting

### The data audit fails

Inspect boundary, context, source IDs, record IDs, and counts first. A custom
fixture must preserve one context and complete operation coverage.

### The evaluator fails a positive record

Inspect the operation execution, not only the top-level state. The issue code,
error string, and output fields identify the missing input or changed primitive.

### The controls fail

Controls are part of the release contract. If an empty or malformed record is
accepted, the implementation is too permissive. If a threshold control is
accepted, the issue vocabulary or threshold propagation is incomplete.

### Replay fails

Compare execution addresses first. Then compare state, issue codes, and output
field ordering. Stable canonical serialization is required for release.

### The depth audit fails

Inspect the operation-specific check ID. The depth audit is designed to catch
lost fields even when the generic state gate remains green.

### The release is blocked

Read the quality gate failed IDs, policy failed rule IDs, schema failed IDs,
lineage verifier failures, and reconciliation counts. Resolve the earliest
boundary failure before editing later-stage expectations.

## Safe interpretation

The link frontier provides a structured way to preserve candidate evidence and
uncertainty. It does not determine a target gene, establish regulation,
estimate patient risk, or recommend treatment. All outputs must be reviewed in
their declared context and evidence boundary.
