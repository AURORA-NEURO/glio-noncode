# D12 Build and Release Runbook

## Build

Run the focused D12 path from the repository root:

```text
python -m glio_noncode cohort-architecture-fixture --output data/cohort-architecture-public-aggregate.json
python -m glio_noncode cohort-architecture-data-audit
python -m glio_noncode cohort-architecture-plan
python -m glio_noncode evaluate-cohort-architecture
python -m glio_noncode cohort-architecture-runtime
python -m glio_noncode cohort-architecture-quality
python -m glio_noncode cohort-architecture-depth
```

Commands accept `--input` for a caller-selected fixture and `--output` for a JSON projection. The bundle command writes `runtime.json`, `release.json`, and `fixture.json` into a caller-selected directory.

## Inspection

```text
python -m glio_noncode cohort-architecture-report
python -m glio_noncode cohort-architecture-scenarios
python -m glio_noncode cohort-architecture-sources
python -m glio_noncode cohort-architecture-query --operation D12-C13
python -m glio_noncode cohort-architecture-compliance
python -m glio_noncode cohort-architecture-validation
python -m glio_noncode cohort-architecture-bundle --output /tmp/glio-cohort-d12-bundle
```

The report exposes family contexts, state distributions, control counts, review counts, lineage, stages, depth, and artifacts. Queries can filter by operation, family, or scenario.

## Release gate

The D12 release is acceptable only when the data audit, typed schema, dependency plan, 64 receipts, 392 checks, 48 control routes, deterministic replay, six review-safe artifacts, quality gate, and 100% depth report all close. The release state must be `published`.

## Troubleshooting

If a source join fails, inspect the prefixed D12 source identifier and its delegate source identifier. If a case fails, compare the family record’s expected state with the evaluator’s observed state before changing the aggregate contract. If context handling fails, inspect `family_contexts` and `delegate_context_key` separately; D12 does not collapse heterogeneous cohort contexts. If a content address changes, inspect serialization order and the smallest changed delegate or aggregate object.

Any new family source or operation requires a contract entry, four scenario rows, evaluator coverage, source audit expectations, a capability registry link, tests, and a new release address.
