# D11 Causal Architecture Deep Runbook

## Generate and validate

```powershell
python -m glio_noncode causal-architecture-fixture `
  --output data/causal-architecture-public-aggregate.json
python -m glio_noncode causal-architecture-data-audit `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-audit.json
python -m glio_noncode causal-architecture-validation `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-validation.json
```

The audit must close 20 sources, 16 operations, 64 cases, four family values,
contiguous ordinals, public source visibility, and four cases per operation.

## Run the closure projection

```powershell
python -m glio_noncode causal-architecture-runtime `
  --input data/causal-architecture-public-aggregate.json `
  --output data/causal-architecture-d11-runtime-closure.json
```

The accepted runtime must contain 458 checks, 24 stages, six artifacts, 80
ledger events, ten quality checks, and a published release. The generated file
is the checked-in runtime closure for review.

## Inspect the gates

```powershell
python -m glio_noncode causal-architecture-quality `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-quality.json
python -m glio_noncode causal-architecture-depth `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-depth.json
python -m glio_noncode causal-architecture-compliance `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-compliance.json
python -m glio_noncode replay-causal-architecture `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-replay.json
```

Depth must report 100 percent. Compliance must report an empty restricted-key
set and all public source/address checks must pass. Replay must reproduce the
evaluation address and all receipt addresses.

## Query and bundle

```powershell
python -m glio_noncode causal-architecture-query `
  --input data/causal-architecture-public-aggregate.json `
  --operation D11-C13 `
  --output .tmp/d11-c13.json
python -m glio_noncode causal-architecture-bundle `
  --input data/causal-architecture-public-aggregate.json `
  --output .tmp/d11-bundle
```

The operation query returns four cases with result states, issue codes,
contexts, and addresses. The bundle contains runtime, release, quality, depth,
report, and fixture projections.

## Focused tests

```powershell
python -m unittest `
  tests.test_causal_architecture `
  tests.test_causal_architecture_exports `
  tests.test_causal_architecture_cli `
  tests.test_causal_architecture_reporting
```

## Failure triage

### Context mismatch

Compare `delegate_context_key` with `context_key` on the case. A difference is
accepted only when the issue tuple contains `context_mismatch`.

### Result state mismatch

Compare the delegate result state with `expected_result_state`. The aggregate
positive/review state and the family result state are separate contract fields
and must not be merged.

### Cardinality or balance failure

Inspect source registries, operation ordinals, and case counts. The contract is
20 sources, 16 operations, 64 cases, and four scenarios per operation.

### Compliance failure

Inspect `forbidden_payload_keys` and `forbidden_payload_paths`. Correct the
public projection or adapter rather than bypassing the recursive scan.

### Quality failure

Inspect the ten quality check IDs. State coverage and issue vocabulary are
derived from executions; a reduction can indicate that control paths were
silently removed.

### Release review

The release remains in review when evaluation, artifacts, or release
provenance fail. Review the limitation ceiling before any publication change.

## Change sequence

1. Update typed contracts and schema invariants.
2. Update family normalization and exact controls.
3. Update seven case checks and ten global checks.
4. Update depth, quality, runtime, CLI bundle, and reports.
5. Regenerate the runtime closure JSON.
6. Run focused and neighboring domain tests.
7. Run restricted metadata scans on new and staged content.
8. Review the staged diff, commit the substantial build, and push to public
   `main`.
