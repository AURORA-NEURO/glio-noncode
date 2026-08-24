# D08 Operational Runbook

## 1. Intake and boundary

Start from the checked-in public aggregate fixture or generate it from the four family receipts. Confirm the fixture boundary is `public_aggregate_cell_state_disease_territory` and the routing context is `GRCh38|glioma|adult|stem_like|tumor|unknown`.

The intake gate must reject:

- a missing or changed fixture address;
- a source without public aggregate scope;
- a source whose public marker is false;
- a case with an empty delegated context;
- a case outside the declared context pair;
- a foreign control without `context_mismatch`;
- an operation or case with an unresolved source join.

The foreign pediatric context exists as a control boundary. It is not a second positive cohort.

## 2. Sequence the build

The runtime is a fixed 24-stage sequence. Each stage receives the prior stage address and emits its own addressed output. The stages are:

1. `fixture-loaded`
2. `sources-audited`
3. `schema-validated`
4. `plan-compiled`
5. `taxonomy-family-ready`
6. `prior-family-ready`
7. `territory-family-ready`
8. `cell-state-family-ready`
9. `cases-executed`
10. `review-routed`
11. `lineage-linked`
12. `ledger-closed`
13. `metrics-materialized`
14. `invariants-closed`
15. `replay-closed`
16. `artifacts-materialized`
17. `bundle-closed`
18. `access-closed`
19. `release-built`
20. `quality-gated`
21. `depth-accounted`
22. `controls-closed`
23. `compliance-closed`
24. `runtime-finalized`

All stages must report `accepted`. A stage may have a review item in its data products; review items are expected for the 48 control cases and do not make the runtime stage itself fail.

## 3. Review the operation families

The four family groups are stable:

| Group | Operations | Focus |
| --- | --- | --- |
| context | C01-C04 | disease ontology, age route, molecular state, territory assembly |
| beta context | C05-C08 | developmental lineage and malignant-state priors |
| alpha context | C09-C12 | spatial niche, core-margin, recurrence, treatment-induced state |
| cell state | C13-C16 | abundance, reference mapping, OOD, context publication |

For C01-C12, verify that the family record identifier resolves to a positive receipt and that its context is copied into the delegated context field. For C13-C16, inspect the primitive summary:

- C13: bounded count, total, interval multiplier, stable state identifier, and interval address;
- C14: top score, second score, margin, threshold, and mapped stable identifier;
- C15: distance, support score, support boundary, and OOD decision;
- C16: exact context, cell IDs, and upstream mapping, abundance, and OOD addresses.

## 4. Triage controls

`context_mismatch` means the case was held before delegation. Correct the context pair and regenerate the fixture address before retrying. Do not turn the pediatric control into a positive case.

`malformed_input` means the payload shape or required field set is invalid. Repair the typed aggregate payload. Do not default a missing count, score, margin, or address to a positive value.

`identity_conflict` means the aggregate record contains a contradiction that must stay review-held. Preserve the issue code and the original case address while reconciling the upstream aggregate receipt.

`invalid_cell_count` means the abundance count is negative or exceeds total cells. Check both bounds and retain the review state until the aggregate record is corrected.

`ambiguous_reference_mapping` means the top score or score margin fails its threshold. Keep the case review-held; inspect the score ordering and margin rather than forcing a label.

`cell_state_out_of_domain` means the distance or support score does not fit the declared support region. Record the OOD result and expand the support boundary only through a new reviewed build.

## 5. Audit the 458 checks

The check ledger should be reconciled with the following accounting:

```text
64 cases * 7 case checks = 448
10 global checks          = 10
total                     = 458
```

The global checks must show 16 positive receipts, 48 control receipts, four families, 16 operations, 64 case IDs, 64 addressed outputs, balanced four-case operation groups, and explicit context controls.

The quality gate should show 12 checks. If the quality count changes, inspect the quality module and tests together; a quality check addition is a contract change and requires fixture-independent regression coverage.

## 6. Verify lineage and ledger

Lineage must have no gaps across:

1. source to operation;
2. operation to case;
3. case to execution;
4. execution to output address;
5. output address to receipt;
6. receipt to ledger event;
7. artifact to source address.

The ledger contains 64 events. Positive cases are marked delegated; controls are marked held. Every event carries source IDs and an output address. State counts must sum to 64.

## 7. Verify the release bundle

Run the bundle command into a new output directory. Inspect all four files:

```text
bundle/fixture.json
bundle/runtime.json
bundle/release.json
bundle/report.json
```

`runtime.json` must contain the 24 stages, depth report, and quality gate. `release.json` must contain six artifact descriptors, the published release, depth values, and all twelve quality checks. `report.json` must expose metrics, scenario matrix, source registry, lineage, observability, dictionary, depth percent, and stage count.

The release is accepted only when `runtime.accepted`, `quality.accepted`, compliance acceptance, and published release state are all true.

## 8. Regression commands

```text
python -m unittest tests.test_cell_state_architecture tests.test_cell_state_architecture_exports tests.test_cell_state_architecture_reporting tests.test_cell_state_architecture_cli
python -m ruff check src/glio_noncode/cell_state_architecture_*.py tests/test_cell_state_architecture*.py
```

Run the D08 CLI commands with the checked-in fixture and verify each returns zero. Run the neighboring D09-D12 suites after D08 changes because the shared export surface and runtime patterns are intentionally aligned.

## 9. Address and regeneration policy

Never edit a generated fixture or runtime closure manually. Change the builder or contract, regenerate both files, run the matrix, and inspect the staged diff. Content addresses are evidence of the exact serialized build; a changed address is expected after a valid contract change and must be recorded in the same commit as its generated projections.

## 10. Handoff checklist

- source count is 18;
- operation count is 16;
- case count is 64;
- scenario counts are 16/16/16/16;
- evaluation checks are 458;
- quality checks are 12;
- runtime stages are 24;
- depth percent is 100.0;
- result states are six;
- issue codes are three;
- lineage gaps are empty;
- ledger is reconciled;
- compliance is accepted;
- release state is published;
- bundle contains four files;
- focused tests pass;
- staged metadata scan is empty;
- main contains the build commit.
