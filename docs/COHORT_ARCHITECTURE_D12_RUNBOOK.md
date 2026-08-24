# D12 Cohort Architecture Deep Runbook

## Generate the public fixture

```powershell
python -m glio_noncode cohort-architecture-fixture `
  --output data/cohort-architecture-public-aggregate.json
python -m glio_noncode cohort-architecture-data-audit `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-audit.json
python -m glio_noncode cohort-architecture-validation `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-validation.json
```

The audit must close 22 sources, 16 operations, 64 cases, four family
contexts, contiguous ordinals, public source flags, resolved joins, and exact
four-case operation balance.

## Run the full runtime

```powershell
python -m glio_noncode cohort-architecture-runtime `
  --input data/cohort-architecture-public-aggregate.json `
  --output data/cohort-architecture-d12-runtime-closure.json
```

The runtime must report 458 evaluation checks, 24 stages, six artifacts, 80
ledger events, a published release, accepted quality, and accepted compliance.
The output is the checked-in closure projection for this build.

## Inspect depth and quality

```powershell
python -m glio_noncode cohort-architecture-depth `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-depth.json
python -m glio_noncode cohort-architecture-quality `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-quality.json
python -m glio_noncode cohort-architecture-compliance `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-compliance.json
python -m glio_noncode replay-cohort-architecture `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-replay.json
```

Depth completion is 100 percent only when all cardinality and 458-check
targets close. Quality must pass data audit, plan, evaluation, replay,
artifact safety, metrics, lineage, release, ledger, recursive compliance,
state coverage, and control-surface coverage.

## Query a family or operation

```powershell
python -m glio_noncode cohort-architecture-query `
  --input data/cohort-architecture-public-aggregate.json `
  --operation D12-C13 `
  --output .tmp/d12-c13.json
```

The operation projection returns four cases with state, issue codes, source
references, delegate context, and output addresses. Family and scenario
filters may be combined with the operation filter.

## Build the review bundle

```powershell
python -m glio_noncode cohort-architecture-bundle `
  --input data/cohort-architecture-public-aggregate.json `
  --output .tmp/d12-bundle
```

The bundle contains runtime, release, quality, depth, and fixture projections.
The runtime file is the full deterministic closure; release contains artifact
inventory, publication limitations, quality checks, and depth counts.

## Focused tests

```powershell
python -m unittest `
  tests.test_cohort_architecture `
  tests.test_cohort_architecture_exports `
  tests.test_cohort_architecture_cli `
  tests.test_cohort_architecture_reporting
```

## Failure triage

### Context check failure

Compare `delegate_context_key`, the family context map, and issue codes. A
different context is accepted only when the delegate emits
`context_mismatch`. Do not normalize a mismatched context into the positive
path.

### Cardinality failure

Inspect source registries and operation case counts. The release contract is
22 sources, 16 operations, 64 cases, and four cases per operation.

### Issue or state failure

Inspect the exact case receipt. D12 preserves the full issue tuple, including
negative controls, empty controls, privacy-floor violations, shifts, parity
gaps, and invalid discovery inputs.

### Compliance failure

Inspect `forbidden_payload_keys` and `forbidden_payload_paths`. Remove a
restricted key from the public aggregate projection or correct the adapter;
never bypass the recursive scan.

### Quality failure

Inspect the failed quality check IDs. A state-vocabulary or control-surface
failure means the fixture no longer documents enough distinct bounded paths for
release review.

### Release review

The release remains in review when evaluation fails or fewer than six safe
artifacts are available. Inspect provenance and limitation fields before any
promotion decision.

## Change sequence

1. Update typed contracts and schema requirements.
2. Update family normalization and expected controls.
3. Update the seven case checks and ten global checks.
4. Update depth, quality, runtime stages, and report projections.
5. Regenerate the runtime closure JSON.
6. Run focused tests and related family regressions.
7. Run the restricted metadata scan on all new and staged content.
8. Review the staged diff, commit the substantial build, and push to public
   `main`.
