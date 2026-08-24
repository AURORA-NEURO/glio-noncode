# D16 Platform Execution Architecture Runbook

## Preconditions

Run commands from the repository root. The D16 fixture is public aggregate
data. A custom fixture may be supplied when it follows the typed schema and
retains the required count, context, source, operation, and case contracts.

The default fixture is generated locally and does not require network access.
Delegate modules are imported from the repository package and their pinned
aggregate data remains visible in normalized source receipts.

## Generate and inspect the fixture

```powershell
python -m glio_noncode platform-execution-architecture-fixture `
  --output data/platform-execution-architecture-public-aggregate.json
python -m glio_noncode platform-execution-architecture-data-audit `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-data-audit.json
python -m glio_noncode platform-execution-architecture-plan `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-plan.json
```

The audit must report nineteen sources, sixteen operations, sixty-four cases,
three family contexts, all-public receipts, contiguous ordinals, resolved
joins, four cases per operation, and the reserved foreign-context control.

## Execute the evaluation

```powershell
python -m glio_noncode evaluate-platform-execution-architecture `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-evaluation.json
python -m glio_noncode platform-execution-architecture-runtime `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-runtime.json
```

The evaluation must have 64 executions, 64 receipts, and 458 passed checks.
The runtime must have 24 accepted stages and a published release. If a control
is intentionally changed, inspect its expected and observed state, issue
codes, counts, context, and output address before accepting the fixture.

## Quality, depth, and replay

```powershell
python -m glio_noncode platform-execution-architecture-quality `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-quality.json
python -m glio_noncode platform-execution-architecture-depth `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-depth.json
python -m glio_noncode replay-platform-execution-architecture `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-replay.json
```

Quality checks include the coordination cross-plane closure. Depth must retain
the 458-check count and non-empty state and issue vocabularies. Replay compares
the evaluation content address and every receipt address against a second
evaluation of the same fixture.

## Reports and projections

```powershell
python -m glio_noncode platform-execution-architecture-report `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-report.json
python -m glio_noncode platform-execution-architecture-scenarios `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-scenarios.json
python -m glio_noncode platform-execution-architecture-sources `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-sources.json
python -m glio_noncode platform-execution-architecture-compliance `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-compliance.json
```

The report contains source, operation, case, state, family, scenario, issue,
and check metrics. The scenario projection contains all 64 cases. The source
projection exposes the nineteen normalized public receipts. Compliance must
return an empty restricted-key list.

## Targeted queries

```powershell
python -m glio_noncode platform-execution-architecture-query `
  --input data/platform-execution-architecture-public-aggregate.json `
  --operation D16-C14 `
  --output .tmp/d16-c14.json
```

The operation query returns four scenarios for C14. Filters may be combined
with family and scenario values. Every row retains the operation, family,
plane, state, issue codes, and output address.

## Bundle generation

```powershell
python -m glio_noncode platform-execution-architecture-bundle `
  --input data/platform-execution-architecture-public-aggregate.json `
  --output .tmp/d16-bundle
```

The bundle contains `runtime.json`, `release.json`, `report.json`, and
`fixture.json`. `release.json` contains artifact inventory, release state,
quality checks, and depth counts. The bundle directory can be archived as a
review projection after the runtime returns zero.

## Focused verification

```powershell
python -m unittest `
  tests.test_platform_execution_architecture `
  tests.test_platform_execution_architecture_exports `
  tests.test_platform_execution_architecture_cli `
  tests.test_platform_execution_architecture_reporting
```

The focused suite checks typed exports, root exports, direct operation output,
runtime acceptance, stage order, public boundary, coordination closure, CLI
serialization, query filtering, bundle files, and report rendering.

## Failure triage

### Audit failure

Inspect source count, family context map, operation ordinals, source joins, and
case balance. A count mismatch means the fixture was not generated from the
current three-family contract.

### Evaluation failure

Locate failed check IDs in `evaluation.json`. State or issue mismatch usually
means the delegate row changed. Context mismatch is valid only when the issue
codes explicitly include `context_mismatch`.

### Plan failure

Inspect operation dependencies. A dependency may reference only an earlier
operation ordinal. Cycles and forward references are rejected.

### Quality failure

Inspect the named quality check. Coordination failure means the cross-plane
fixture is not accepted. Control-surface failure means the issue vocabulary
has become too narrow to document bounded behavior.

### Compliance failure

Inspect the restricted-key paths and source public flags. Do not bypass the
scan. Remove the field from the aggregate payload or revise the source adapter
so only allowed public values are retained.

### Release hold

A hold is an explicit release state. Inspect artifact addresses, evaluation
acceptance, digest checks, and release limitations. Do not promote a hold by
changing the output state alone.

## CI sequence

Actions runs the D16 command matrix in four groups: fixture and plan;
evaluation and runtime; quality, depth, validation, and replay; scenarios,
sources, compliance, report, and bundle. The final group runs all four focused
test modules. This mirrors the local runbook and makes a failed stage easy to
locate.

## Change procedure

1. Update the typed contract first when a new state, family, operation, or
   receipt field is required.
2. Update the public aggregate adapter and its exact expected controls.
3. Update evaluation, quality, depth, reporting, runtime, and CLI surfaces.
4. Add or update focused tests for positive and control paths.
5. Regenerate the pinned data file with the fixture command.
6. Run the focused suite and relevant delegate regression suites.
7. Scan new files and staged additions for restricted attribution or syntax
   metadata fields.
8. Review `git diff --cached --check`, confirm a substantial build, commit on
   the build branch, and push the commit to public `main`.

## Current acceptance record

The D16 default fixture is expected to close with:

```text
19 sources
16 operations
64 cases
458 checks
80 ledger events
6 artifacts
24 runtime stages
11 quality checks
published release
accepted runtime
```
