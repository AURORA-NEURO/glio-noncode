# Workspace beta frontier API

This package covers Domain 15 C05-C08:

1. `TopologyViewer` and `TopologyViewport`
2. `CausalChainExplorer` and `CausalChainView`
3. `PosteriorDecompositionViewer` and `PosteriorDecompositionView`
4. `EvidenceTableAndFilters` and `EvidenceTableView`

The `workspace_beta_frontier_*` modules add a public aggregate fixture,
execution accounting, contracts, schemas, policy, lineage, reconciliation,
metrics, replay, quality gates, runtime rehearsal, observability, release
artifacts, review queues, scenario probes, threshold probes, invariants, and
exports around those four projection primitives.

## Core execution

```python
from glio_noncode.workspace_beta_frontier_fixture_eval import evaluate_beta_frontier_fixture
from glio_noncode.workspace_beta_frontier_public_data import default_beta_frontier_fixture

fixture = default_beta_frontier_fixture()
evaluation = evaluate_beta_frontier_fixture(fixture)
assert evaluation.accepted
```

Every execution has `record_id`, `operation`, `role`, `state`, `issue_codes`,
serialized `output`, and a `sha256:` content address. Positive rows must match
their expected state and issue set. Control rows must also match expected
behavior, but remain outside the promotion count.

## Runtime rehearsal

```python
from glio_noncode.workspace_beta_frontier_runtime import run_beta_frontier_runtime

runtime = run_beta_frontier_runtime(fixture, run_id="local-beta-frontier")
assert runtime.accepted
assert len(runtime.stages) == 8
```

The fixed stage order is fixture load; contract and schema load; projection
execution; metric measurement; lineage build; policy application;
reconciliation; and quality and bundle assembly.

## Projection payloads

Topology payloads accept loop observations, promoter-capture contacts, contact
scores, activity-by-contact results, focus coordinates, and output bounds.
Focus coordinates are inclusive and require a chromosome, start, and end as a
complete group.

Causal payloads accept typed mediator mappings. The explorer retains exact
context edges, alternative paths, missing mediator kinds, against-direction
IDs, source receipts, and contradiction state.

Posterior payloads accept a declared posterior proxy and component mappings.
The view exposes prior, support, proxy value, calibration status, exact-context
components, normalized absolute shares, and residual support.

Evidence-table payloads contain a `ResearchWorkspace` mapping and a typed table
filter. Facets are computed before pagination. Filtering never changes a row's
underlying state.

## CLI surface

```text
beta-frontier-data-audit
beta-frontier-contracts
beta-frontier-schema
beta-frontier-evaluate
beta-frontier-replay
beta-frontier-metrics
beta-frontier-lineage
beta-frontier-policy
beta-frontier-quality-gate
beta-frontier-runtime
beta-frontier-observability
beta-frontier-artifacts
beta-frontier-bundle
beta-frontier-release
beta-frontier-review-queue
beta-frontier-depth-audit
beta-frontier-adapters
beta-frontier-scenarios
beta-frontier-thresholds
beta-frontier-invariants
export-beta-frontier-review-csv
```

Commands use the default public aggregate fixture when no input path is given.
All JSON outputs use the repository serialization layer and all CSV outputs
contain stable column order.
