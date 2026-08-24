# D07 runbook

## Standard run

1. Generate the deterministic fixture with
   `chromatin-architecture-fixture`.
2. Run `chromatin-architecture-data-audit`. Confirm 19 sources, 16 operations,
   and 64 cases.
3. Run `chromatin-architecture-plan`. Confirm every node is ready and every
   predecessor is declared.
4. Run `evaluate-chromatin-architecture`. Confirm 64 passing receipts and 458
   passing checks.
5. Run `chromatin-architecture-validation`. Confirm 80 cells: five views by
   sixteen operations.
6. Run `chromatin-architecture-quality`. Confirm the release gate is accepted.
7. Run `replay-chromatin-architecture`. Confirm both evaluation and receipt
   addresses are identical.
8. Export the review CSV and inspect the 48 controls. Controls must remain
   review-held.
9. Run `chromatin-architecture-compliance` and
   `chromatin-architecture-sources`.
10. Materialize the bundle only after all prior commands succeed.

For `chromatin-architecture-query`, pass the enum operation value such as
`context_imputation_confidence`; the command returns matching case and receipt
IDs while the operation register retains the `D07-C13` identity.

## Stop conditions

Stop and retain the run in review if:

- a context key differs from the aggregate context;
- a source is not HTTPS or no longer has a public aggregate scope;
- a family record cannot be matched to its operation;
- a receipt loses an expected issue code;
- a summary contains raw input fields;
- an output address changes during replay;
- a schema, lineage, invariant, access, or release check fails.

## Review handling

Foreign-context controls are medium priority and non-blocking for the positive
release. Malformed inputs are high priority and blocking for the affected case.
Identity conflicts are blocking until the source and operation joins are
reconciled. None of the three controls is silently promoted to accepted.

## Recovery

The fixture and family receipts are deterministic. Re-run from the fixture
boundary after correcting the source or case input. Do not edit a receipt by
hand: regenerate the evaluation so all addresses, metrics, lineage links, and
release artifacts are recomputed together.

## Observability

The runtime emits 24 addressed stages. The final stage is
`runtime-finalized`. A run is accepted only when the final stage, quality gate,
access policy, compliance report, depth report, and published release all agree.
