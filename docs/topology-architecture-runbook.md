# D09 Runbook

All commands are offline and operate on the checked-in public aggregate or a caller-provided fixture.

## Build and inspect a fixture

```powershell
python -m glio_noncode topology-architecture-fixture --output data/topology-architecture-public-aggregate.json
python -m glio_noncode topology-architecture-data-audit --input data/topology-architecture-public-aggregate.json --output .runtime/topology-data-audit.json
python -m glio_noncode topology-architecture-plan --input data/topology-architecture-public-aggregate.json --output .runtime/topology-plan.json
```

The data audit must report `accepted: true`, zero failed checks, and closed source, operation, and case joins.

## Execute and release

```powershell
python -m glio_noncode evaluate-topology-architecture --input data/topology-architecture-public-aggregate.json --output .runtime/topology-evaluation.json
python -m glio_noncode topology-architecture-runtime --input data/topology-architecture-public-aggregate.json --output .runtime/topology-runtime.json
python -m glio_noncode topology-architecture-quality --input data/topology-architecture-public-aggregate.json --output .runtime/topology-quality.json
python -m glio_noncode topology-architecture-depth --input data/topology-architecture-public-aggregate.json --output .runtime/topology-depth.json
python -m glio_noncode replay-topology-architecture --input data/topology-architecture-public-aggregate.json --output .runtime/topology-replay.json
```

The expected evaluation has 64 receipts and 458 checks. The runtime has 24 accepted stages, six artifacts, a published release, twelve quality checks, and a 100 percent depth report. Replay must be accepted and deterministic.

## Review and query

```powershell
python -m glio_noncode topology-architecture-scenarios --input data/topology-architecture-public-aggregate.json --output .runtime/topology-scenarios.json
python -m glio_noncode topology-architecture-sources --input data/topology-architecture-public-aggregate.json --output .runtime/topology-sources.json
python -m glio_noncode topology-architecture-query --input data/topology-architecture-public-aggregate.json --operation D09-C13 --output .runtime/topology-c13.json
python -m glio_noncode topology-architecture-report --input data/topology-architecture-public-aggregate.json --output .runtime/topology-report.json
python -m glio_noncode topology-architecture-bundle --input data/topology-architecture-public-aggregate.json --output .runtime/topology-bundle
```

The query returns four cases for one operation: one positive and three controls. The bundle contains `fixture.json`, `runtime.json`, `release.json`, and `report.json`. The release projection retains quality and depth receipts.

## Verification

```powershell
python -m unittest tests.test_topology_architecture tests.test_topology_architecture_exports tests.test_topology_architecture_cli tests.test_topology_architecture_reporting
python -m ruff format --check src/glio_noncode/topology_architecture_*.py tests/test_topology_architecture*.py
python -m ruff check src/glio_noncode/topology_architecture_*.py tests/test_topology_architecture*.py
```

Run the focused checks before committing. The repository workflow repeats the same fixture, audit, plan, runtime, quality, depth, replay, report, bundle, and test commands on every push and pull request.
