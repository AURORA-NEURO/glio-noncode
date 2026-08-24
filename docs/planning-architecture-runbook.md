# D13 Runbook

The D13 commands operate offline on the checked-in public aggregate.

```powershell
python -m glio_noncode planning-architecture-fixture --output data/planning-architecture-public-aggregate.json
python -m glio_noncode planning-architecture-data-audit --input data/planning-architecture-public-aggregate.json --output .runtime/d13-audit.json
python -m glio_noncode planning-architecture-plan --input data/planning-architecture-public-aggregate.json --output .runtime/d13-plan.json
python -m glio_noncode evaluate-planning-architecture --input data/planning-architecture-public-aggregate.json --output .runtime/d13-evaluation.json
python -m glio_noncode planning-architecture-runtime --input data/planning-architecture-public-aggregate.json --output .runtime/d13-runtime.json
python -m glio_noncode planning-architecture-quality --input data/planning-architecture-public-aggregate.json --output .runtime/d13-quality.json
python -m glio_noncode planning-architecture-depth --input data/planning-architecture-public-aggregate.json --output .runtime/d13-depth.json
python -m glio_noncode replay-planning-architecture --input data/planning-architecture-public-aggregate.json --output .runtime/d13-replay.json
python -m glio_noncode planning-architecture-report --input data/planning-architecture-public-aggregate.json --output .runtime/d13-report.json
python -m glio_noncode planning-architecture-bundle --input data/planning-architecture-public-aggregate.json --output .runtime/d13-bundle
```

The query surface returns sanitized cases by operation, family, or scenario:

```powershell
python -m glio_noncode planning-architecture-query --input data/planning-architecture-public-aggregate.json --operation D13-C14 --output .runtime/d13-c14.json
```

The focused suite covers fixture cardinalities, delegate states and issue
codes, source joins, plan dependencies, runtime stages, review routing,
lineage, ledger closure, metrics, compliance, replay, exports, CLI, and
capability-registry promotion. CI repeats the public fixture and runtime
matrix on every push and pull request.
