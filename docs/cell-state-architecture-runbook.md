# D08 Runbook

## Build sequence

1. Generate or load the public aggregate fixture.
2. Validate typed identity, boundary, source joins, operation order, and case cardinality.
3. Audit source receipts, operation specifications, case balance, scenario balance, and addresses.
4. Compile the dependency plan and verify every node is ready.
5. Execute the four family tranches and the four direct cell-state primitives.
6. Reconcile all case receipts and ten global checks, including operation balance and context controls.
7. Route 48 control cases to the review queue.
8. Close source lineage, metrics, observability events, invariants, and deterministic replay.
9. Materialize six artifacts, assemble the bundle, evaluate access, construct the release, close compliance, and run the 12-check quality gate.

## Expected runtime checkpoints

The runtime stages are `fixture-loaded`, `sources-audited`, `schema-validated`, `plan-compiled`, `taxonomy-family-ready`, `prior-family-ready`, `territory-family-ready`, `cell-state-family-ready`, `cases-executed`, `review-routed`, `lineage-linked`, `ledger-closed`, `metrics-materialized`, `invariants-closed`, `replay-closed`, `artifacts-materialized`, `bundle-closed`, `access-closed`, `release-built`, `quality-gated`, `depth-accounted`, `controls-closed`, `compliance-closed`, and `runtime-finalized`.

Every stage must be `accepted`. The final runtime address is derived only after the stage sequence, release state, and acceptance boolean are assembled.

## Triage

* `context_mismatch`: retain the case in hold state and correct the exact context key before retrying.
* `malformed_input`: inspect the typed payload shape; do not coerce missing fields into a positive result.
* `identity_conflict`: preserve the contradiction and reconcile it outside the published release.
* `invalid_cell_count`: verify the cell count is between zero and total cells.
* `ambiguous_reference_mapping`: inspect top score and margin; keep the mapping in review until both gates pass.
* `cell_state_out_of_domain`: retain the OOD finding or declare a separately supported boundary.

## Verification commands

```text
python -m unittest tests.test_cell_state_architecture tests.test_cell_state_architecture_exports tests.test_cell_state_architecture_reporting tests.test_cell_state_architecture_cli
python -m glio_noncode cell-state-architecture-runtime --output /tmp/d08-runtime.json
python -m glio_noncode cell-state-architecture-validation --output /tmp/d08-validation.json
```

The focused suite should report 14 passing tests. A healthy runtime reports 18 sources, 16 operations, 64 cases, 458 checks, six artifacts, 24 stages, six result states, three issue codes, a 12-check accepted quality gate, published release state, and an accepted boolean.
