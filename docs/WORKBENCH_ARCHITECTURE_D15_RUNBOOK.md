# D15 Workbench Build and Review Runbook

## Load and audit

Load `default_workbench_architecture_fixture()` for the checked-in aggregate or `WorkbenchArchitectureFixture.from_file()` for a reviewed copy. Confirm the fixture boundary, four family contexts, 20 sources, 16 operations, and 64 cases. Run `audit_workbench_architecture_data()` before any execution.

The audit checks source count, operation count, case count, family contexts, public aggregate flags, contiguous ordinals, source joins, operation joins, four-case operation balance, and the reserved foreign context label.

## Compile and execute

`build_workbench_architecture_plan()` compiles sixteen nodes. `evaluate_workbench_architecture_fixture()` resolves each case to a namespaced delegate record and retains observed state, issue codes, bounded field counts, output fields, delegate context, and output address.

The four cases for each operation are ordered as positive, control A, control B, and control C. The public fixture retains the delegate record id even when the source fixture uses a different naming convention. The beta family has one historical source alias for topology rows; the normalized source registry records the canonical public source receipt and the case remains linked.

## Review routing

`build_workbench_architecture_review_queue()` routes every control and every positive result outside the successful-state set. Blocking contexts, invalid inputs, denied access, rejected payloads, and blocked dependencies receive critical priority. The queue never changes the underlying execution state.

## Lineage and ledger

Lineage emits one row per case-to-source join and retains source, operation, family, plane, case, scenario, delegate fixture, delegate record, aggregate context, delegate context, and integrity addresses.

The append-only ledger emits 16 operation declaration events and 64 execution events. Sequence continuity and event addresses are required for closure.

## Quality and release

The ten-check quality gate requires audit, plan, evaluation, replay, safe artifacts, metric invariants, complete lineage, publishable release, closed ledger, and broad state coverage. The release becomes `published` only when evaluation is accepted and all six artifacts are safe.

## CLI matrix

The D15 CLI surface includes fixture, data audit, plan, evaluation, runtime, quality, depth, replay, report, scenarios, sources, compliance, validation, query, and bundle commands. The CI workflow runs the full matrix and four focused D15 test modules.

## Review checklist

1. run ruff on all D15 modules and tests;
2. regenerate the checked-in fixture and confirm its address;
3. confirm 20 sources, 16 operations, 64 cases, and 458 checks;
4. confirm 80 ledger events and 24 runtime stages;
5. confirm zero compliance hits;
6. run existing foundation, beta, collaboration, and release delegate tests;
7. run the D15 focused suite and CLI matrix;
8. scan staged added lines for prohibited attribution fields;
9. run `git diff --cached --check`;
10. commit the coherent build above five thousand added lines on `main`.
