# D07 Chromatin Architecture Runbook

## Intake gate

Begin with the public aggregate fixture. Confirm the boundary is
`public_aggregate_chromatin_accessibility_methylation` and the routing context
is `GRCh38|glioma|adult|stem_like|tumor|unknown`.

Reject the intake when:

- a source lacks public aggregate scope or its explicit public marker;
- a source, operation, or case has no SHA-256 address;
- an operation has an unresolved source join;
- a case has an unresolved operation join;
- a case has an empty delegated context;
- a foreign control lacks `context_mismatch`;
- the fixture does not have 19 sources, 16 operations, and 64 cases.

The differentiated cell-state context is a deliberate foreign control, not a
second positive cohort.

## Execution sequence

Run the following sequence in order:

1. generate or load the fixture;
2. audit version, boundary, context, cardinality, joins, scenarios, markers,
   and addresses;
3. compile the total-order dependency plan;
4. execute all four family tranches and the four direct cross-assay paths;
5. reconcile 64 receipts and 458 checks;
6. route 48 controls to the review queue;
7. close lineage, ledger, metrics, schema, invariants, and replay;
8. materialize six artifacts;
9. account for depth and close policy;
10. run the 14-check quality gate;
11. build the published release and access policy;
12. run compliance and observability;
13. finalize the 24-stage runtime.

Do not publish a partially evaluated fixture. All four scenario rows per
operation must remain available for audit even when only the 16 positive rows
are eligible for delegation.

## Functional review points

For C01-C12, verify the family record identifier, family context, sanitized
summary, result state, issue tuple, and source joins. A missing family receipt
is a held failure, not a default positive.

For C13, inspect observed and imputed feature identifiers separately. The
confidence value belongs to the declared prior and must not be presented as an
observed measurement.

For C14, verify all required assays are present and that the coverage threshold
is applied before a feature is marked supported.

For C15, inspect direction values and concordance. A descriptive agreement
score is not a causal conclusion.

For C16, verify exact routing context, feature identifiers, assay IDs, and the
addresses of the upstream records before accepting `published`.

## Control triage

`context_mismatch` means the case was held before family execution. Correct the
context boundary and regenerate the fixture rather than changing the observed
result by hand.

`malformed_input` means required structure is missing or invalid. Repair the
aggregate payload and rerun the full evaluation.

`identity_conflict` means contradictory evidence remains review-held. Preserve
the issue code and source joins until the contradiction is reconciled.

Other family issue codes remain descriptive and visible in the result-state and
issue-code metrics. They are not silently collapsed into a positive result.

## Check reconciliation

The evaluation must satisfy this exact accounting:

```text
case checks:   64 * 7 = 448
global checks:           10
evaluation total:       458
quality checks:           14
```

The global operation-balance check must observe exactly four receipts for each
of the 16 operation IDs. The context-control check must observe a mismatch code
on all 16 foreign controls and a non-empty result state on every receipt.

## Lineage and ledger

Lineage must close source-to-operation, operation-to-case, case-to-execution,
execution-to-receipt, and receipt-to-ledger relationships. The ledger contains
64 events. Positive receipts are accepted dispositions; controls are review
dispositions with their issue codes preserved. State counts must sum to 64.

## Bundle review

Run the bundle command into a new output directory and inspect:

```text
fixture.json
runtime.json
release.json
report.json
```

`runtime.json` must contain 24 stages, depth, quality, and compliance.
`release.json` must contain six artifacts, the published release, 14 quality
checks, depth counters, and compliance. `report.json` must contain 458 checks,
14 quality checks, 100.0 percent depth, 24 stages, six result states, and
accepted compliance.

## Failure recovery

When an address drifts, regenerate the fixture, evaluation, artifacts, release,
and runtime together. Never edit a generated receipt or runtime projection by
hand. When a check fails, retain the failing case and inspect the corresponding
source, operation, context, payload, and adapter summary before retrying.

## Regression commands

```text
python -m unittest tests.test_chromatin_architecture tests.test_chromatin_architecture_exports tests.test_chromatin_architecture_cli tests.test_chromatin_architecture_reporting
python -m ruff check src/glio_noncode/chromatin_architecture_compliance.py src/glio_noncode/chromatin_architecture_contracts.py src/glio_noncode/chromatin_architecture_depth.py src/glio_noncode/chromatin_architecture_metrics.py src/glio_noncode/chromatin_architecture_operations.py src/glio_noncode/chromatin_architecture_public_data.py src/glio_noncode/chromatin_architecture_quality.py src/glio_noncode/chromatin_architecture_reporting.py src/glio_noncode/chromatin_architecture_runtime.py src/glio_noncode/chromatin_architecture_schema.py
```

Run the neighboring D08-D12 tests after a D07 change because the modules share
the public aggregate conventions, runtime projections, and CLI entry point.

## Handoff checklist

- 19 public sources;
- 16 operations;
- 64 cases;
- 16 positive and 48 review-held controls;
- 458 evaluation checks;
- 14 quality checks;
- 24 accepted runtime stages;
- six artifacts;
- six result states;
- compliance accepted;
- depth percent 100.0;
- published release;
- four bundle files;
- focused and neighboring regression suites green;
- staged additions free of prohibited metadata;
- commit pushed to `main`.
