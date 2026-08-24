# D10 Link-Graph Architecture Deep Runbook

## Generate and validate

```powershell
python -m glio_noncode link-graph-architecture-fixture `
  --output data/link-graph-architecture-public-aggregate.json
python -m glio_noncode link-graph-architecture-data-audit `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-audit.json
python -m glio_noncode link-graph-architecture-validation `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-validation.json
```

The audit must close 19 sources, 16 operations, 64 cases, four families,
contiguous ordinals, public source visibility, and four cases per operation.

## Run the closure

```powershell
python -m glio_noncode link-graph-architecture-runtime `
  --input data/link-graph-architecture-public-aggregate.json `
  --output data/link-graph-architecture-d10-runtime-closure.json
```

The accepted result must contain 458 evaluation checks, 24 stages, six
artifacts, 80 ledger events, ten quality checks, and a published release.

## Inspect gates and replay

```powershell
python -m glio_noncode link-graph-architecture-quality `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-quality.json
python -m glio_noncode link-graph-architecture-depth `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-depth.json
python -m glio_noncode link-graph-architecture-compliance `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-compliance.json
python -m glio_noncode replay-link-graph-architecture `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-replay.json
```

Depth must return 100 percent. Compliance must return an empty restricted-key
set and all address checks must pass. Replay must reproduce the evaluation and
receipt addresses.

## Query and bundle

```powershell
python -m glio_noncode link-graph-architecture-query `
  --input data/link-graph-architecture-public-aggregate.json `
  --operation D10-C13 `
  --output .tmp/d10-c13.json
python -m glio_noncode link-graph-architecture-bundle `
  --input data/link-graph-architecture-public-aggregate.json `
  --output .tmp/d10-bundle
```

The query returns four operation cases with aggregate state, delegate result
state, issue codes, context, and output address. The bundle contains runtime,
release, quality, depth, report, and fixture projections.

## Focused tests

```powershell
python -m unittest `
  tests.test_link_graph_architecture `
  tests.test_link_graph_architecture_exports `
  tests.test_link_graph_architecture_cli `
  tests.test_link_graph_architecture_reporting
```

## Failure triage

### Context mismatch

Compare `delegate_context_key` with the case `context_key`. A difference is
valid only when `context_mismatch` is present in the issue tuple.

### Result mismatch

Compare `observed_result_state` with `expected_result_state`. A partial or
contradictory graph result must not be rewritten as an accepted link.

### Cardinality failure

Inspect source count, operation ordinals, and case balance. The contract is 19
sources, 16 operations, 64 cases, and four cases per operation.

### Compliance failure

Inspect the restricted keys and exact payload paths. Correct the public graph
projection or adapter instead of bypassing recursive compliance.

### Quality failure

Inspect the ten quality check IDs. State and issue coverage are execution-derived
and a decrease can indicate a missing control path.

## Change sequence

1. Update typed contracts and schema invariants.
2. Update family normalization and graph controls.
3. Update seven case checks and ten global checks.
4. Update depth, quality, runtime, CLI bundle, and reports.
5. Regenerate the runtime closure JSON.
6. Run D10, D11, and D12 focused regressions.
7. Run restricted metadata scans on new and staged content.
8. Review, commit, and push the substantial build to public `main`.
