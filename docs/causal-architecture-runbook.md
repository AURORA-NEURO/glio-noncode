# D11 Build and Release Runbook

## Build

Run the focused quality path from the repository root:

```text
python -m glio_noncode causal-architecture-fixture --output data/causal-architecture-public-aggregate.json
python -m glio_noncode causal-architecture-data-audit
python -m glio_noncode causal-architecture-plan
python -m glio_noncode evaluate-causal-architecture
python -m glio_noncode causal-architecture-runtime
python -m glio_noncode causal-architecture-quality
python -m glio_noncode causal-architecture-depth
```

The fixture command writes the canonical public aggregate JSON. The other commands can write a caller-selected output path with `--output`; runtime bundle output requires a directory path.

## Inspection

Use the following commands to inspect the release surface:

```text
python -m glio_noncode causal-architecture-report
python -m glio_noncode causal-architecture-scenarios
python -m glio_noncode causal-architecture-sources
python -m glio_noncode causal-architecture-query --operation D11-C13
python -m glio_noncode causal-architecture-compliance
python -m glio_noncode causal-architecture-validation
```

The report exposes metrics, depth, review counts, lineage, stages, and artifact count. The query command filters by operation, family, and scenario. The compliance command checks boundary and address rules. The validation command joins typed validation with evaluation acceptance.

## Release gate

The release is acceptable only when:

- the data audit is accepted;
- all 16 operation dependencies are ready;
- all 64 receipts pass their expected state, result, issue, and count comparisons;
- all 48 controls are routed;
- replay is deterministic;
- all six artifacts are review-safe and addressed;
- the quality gate is accepted;
- depth reports 100 percent;
- the release state is `published`.

## Troubleshooting

If a source or case join fails, inspect the fixture source identifiers and operation source lists first. If a receipt fails, compare the delegate result state and issue codes before changing the aggregate contract. If a context control unexpectedly supports, check the delegated context key and the expected `context_mismatch` path. If a content address changes, inspect serialization order and the smallest changed typed object.

The fixture is deliberately bounded. A new public aggregate source or operation requires a contract update, a four-scenario row set, a focused test, a data audit expectation, a capability registry link, and a fresh release address.
