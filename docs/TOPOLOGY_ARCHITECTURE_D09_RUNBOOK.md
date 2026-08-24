# D09 topology architecture depth runbook

## Scope

This runbook executes the D09 public aggregate topology runtime from a clean
checkout. Commands are offline and use only the checked-in aggregate fixture.
No restricted study payload is required for the release rehearsal.

## Fixture generation

```powershell
python -m glio_noncode topology-architecture-fixture --output data/topology-architecture-public-aggregate.json
```

Confirm that the fixture contains 17 sources, 16 operations, 64 cases, four
families, explicit public source flags, and a delegated context key on every
case. The fixture content address must be reproducible when the command is run
again without a source or contract change.

## Source and schema audit

```powershell
python -m glio_noncode topology-architecture-data-audit --input data/topology-architecture-public-aggregate.json --output .runtime/topology-data-audit.json
python -m glio_noncode topology-architecture-plan --input data/topology-architecture-public-aggregate.json --output .runtime/topology-plan.json
python -m glio_noncode topology-architecture-validation --input data/topology-architecture-public-aggregate.json --output .runtime/topology-validation.json
python -m glio_noncode topology-architecture-compliance --input data/topology-architecture-public-aggregate.json --output .runtime/topology-compliance.json
```

The audit must be accepted with no failed checks. The plan must contain 16
ready nodes. Validation must preserve all 64 expected states. Compliance must
report an empty forbidden-key collection, public sources, valid addresses, and
retained delegated contexts.

## Evaluation and runtime

```powershell
python -m glio_noncode evaluate-topology-architecture --input data/topology-architecture-public-aggregate.json --output .runtime/topology-evaluation.json
python -m glio_noncode topology-architecture-runtime --input data/topology-architecture-public-aggregate.json --output .runtime/topology-runtime.json
python -m glio_noncode topology-architecture-quality --input data/topology-architecture-public-aggregate.json --output .runtime/topology-quality.json
python -m glio_noncode topology-architecture-depth --input data/topology-architecture-public-aggregate.json --output .runtime/topology-depth.json
python -m glio_noncode replay-topology-architecture --input data/topology-architecture-public-aggregate.json --output .runtime/topology-replay.json
```

Expected values:

| Output | Expected |
| --- | --- |
| evaluation receipts | 64 |
| evaluation checks | 458 |
| positive cases | 16 |
| held controls | 48 |
| runtime stages | 24 |
| quality checks | 12 |
| depth check count | 458 |
| depth completion | 100.0% |
| release state | published |
| accepted | true |

Replay must produce identical evaluation addresses. A changed output address
is a reproducibility failure even when the state vocabulary still looks valid.

## Review, query, and projections

```powershell
python -m glio_noncode topology-architecture-scenarios --input data/topology-architecture-public-aggregate.json --output .runtime/topology-scenarios.json
python -m glio_noncode topology-architecture-sources --input data/topology-architecture-public-aggregate.json --output .runtime/topology-sources.json
python -m glio_noncode topology-architecture-query --input data/topology-architecture-public-aggregate.json --operation D09-C13 --output .runtime/topology-c13.json
python -m glio_noncode topology-architecture-report --input data/topology-architecture-public-aggregate.json --output .runtime/topology-report.json
python -m glio_noncode topology-architecture-bundle --input data/topology-architecture-public-aggregate.json --output .runtime/topology-bundle
```

The operation query returns four rows: one positive and three controls. The
scenario projection retains context and result state. The report includes
metrics, depth, review, lineage, operations, release, and stage count. The
bundle contains `fixture.json`, `runtime.json`, `release.json`, and
`report.json`.

## Failure triage

If the source count fails, inspect source registry joins and public flags.
If a case count fails, inspect the operation-to-case balance and ordinal
sequence. If evaluation fails, inspect the first failed case receipt before
the global checks. If only context checks fail, compare aggregate and
delegated context keys and verify that a foreign context carries
`context_mismatch`. If compliance fails, use the reported nested paths to
remove restricted payload keys. If replay fails, identify the first changed
content address rather than accepting a state-only comparison.

## Focused verification

```powershell
python -m unittest tests.test_topology_architecture tests.test_topology_architecture_exports tests.test_topology_architecture_cli tests.test_topology_architecture_reporting
python -m ruff check src/glio_noncode/topology_architecture_*.py tests/test_topology_architecture*.py
```

The focused suite must pass before committing. The generated runtime closure
should be inspected with a JSON parser and must show accepted true, 458
evaluation checks, 24 stages, 458 depth checks, 12 quality checks, and a
published release.

## Commit boundary

Commit the D09 implementation, fixture, runtime closure, tests, and depth
documents together. Confirm `git diff --check`, run the metadata scan over all
new D09 lines, and push the commit to `main`. The next domain may begin only
after the remote branch and local worktree agree.
