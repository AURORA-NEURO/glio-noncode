# D10 Runbook

The D10 commands operate offline on the checked-in public aggregate.

## Build and audit

```powershell
python -m glio_noncode link-graph-architecture-fixture --output data/link-graph-architecture-public-aggregate.json
python -m glio_noncode link-graph-architecture-data-audit --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-data.json
python -m glio_noncode link-graph-architecture-plan --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-plan.json
```

The audit must be accepted with 19 sources, 16 operations, 64 cases, and closed source and operation joins.

## Execute and verify

```powershell
python -m glio_noncode evaluate-link-graph-architecture --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-evaluation.json
python -m glio_noncode link-graph-architecture-runtime --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-runtime.json
python -m glio_noncode link-graph-architecture-quality --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-quality.json
python -m glio_noncode link-graph-architecture-depth --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-depth.json
python -m glio_noncode replay-link-graph-architecture --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-graph-replay.json
```

Expected results are 64 receipts, 392 checks, 22 accepted stages, six safe artifacts, a published release, and a 100 percent depth report. Replay must produce identical evaluation addresses.

## Query and bundle

```powershell
python -m glio_noncode link-graph-architecture-query --input data/link-graph-architecture-public-aggregate.json --operation D10-C13 --output .runtime/link-c13.json
python -m glio_noncode link-graph-architecture-report --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-report.json
python -m glio_noncode link-graph-architecture-bundle --input data/link-graph-architecture-public-aggregate.json --output .runtime/link-bundle
```

The operation query returns four rows. The bundle contains `fixture.json`, `runtime.json`, and `release.json`.

## Focused verification

```powershell
python -m unittest tests.test_link_graph_architecture tests.test_link_graph_architecture_exports tests.test_link_graph_architecture_cli tests.test_link_graph_architecture_reporting
python -m ruff format --check src/glio_noncode/link_graph_architecture_*.py tests/test_link_graph_architecture*.py
python -m ruff check src/glio_noncode/link_graph_architecture_*.py tests/test_link_graph_architecture*.py
```

The repository workflow repeats the D10 fixture, audit, plan, evaluation, runtime, quality, depth, replay, report, bundle, and focused tests on every push and pull request.
