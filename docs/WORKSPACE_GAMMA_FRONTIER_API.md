# Workspace Gamma Frontier API

This document describes the public C09–C12 package for the research workspace
surfaces. The package is a deterministic review and release layer around four
bounded operations:

1. `experiment_board` groups declared validation cards by workflow column.
2. `launch_plan` produces bounded notebook and SDK descriptors.
3. `shareable_snapshot` publishes and verifies a research-use HMAC envelope.
4. `collaboration_access` evaluates an explicit role/action permission matrix.

The package consumes aggregate research values and public HTTPS receipts. It
does not execute user code, grant institutional access, make clinical claims,
or replace a scientific review process.

## Root imports

The stable root package exports the following families:

| Family | Primary entry points | Purpose |
| --- | --- | --- |
| Fixture | `default_gamma_frontier_fixture`, `load_gamma_frontier_fixture` | Build or load the public aggregate package |
| Execution | `evaluate_gamma_frontier_fixture`, `execute_gamma_frontier_record` | Run positive and control records |
| Contracts | `default_gamma_frontier_contracts`, `default_gamma_frontier_schema` | Describe inputs, outputs, states, and fields |
| Runtime | `run_gamma_frontier_runtime`, `run_gamma_frontier_pipeline` | Rehearse the quality-gated sequence |
| Evidence | `build_gamma_frontier_lineage`, `reconcile_gamma_frontier` | Connect and compare receipts |
| Routing | `default_gamma_frontier_policy`, `build_gamma_frontier_review_queue` | Route release, review, and hold outcomes |
| Packaging | `assemble_gamma_frontier_bundle`, `build_gamma_frontier_artifact_inventory` | Assemble address-only release evidence |
| Export | `export_gamma_frontier_json`, `export_gamma_frontier_review_csv` | Emit canonical API and review formats |

## Minimal Python call

```python
from glio_noncode import run_gamma_frontier_pipeline

report = run_gamma_frontier_pipeline()
assert report.accepted
print(report.release.state)
print(report.addresses())
```

The default fixture has sixteen records: four positive records and twelve
controls. The four positive records exercise one operation each. Controls cover
foreign context, malformed records, expired or invalid signatures, unbounded
resource requests, inactive members, and unknown members.

## Fixture objects

`GammaFrontierFixture` contains:

- `fixture_id`, `fixture_version`, and `content_address`;
- one exact six-part `context_key`;
- an explicit `evidence_boundary`;
- five `GammaFrontierSourceReceipt` objects;
- sixteen `GammaFrontierRecord` objects.

Every record contains an operation, role, context, source IDs, payload,
expected state, expected issue codes, and notes. This design keeps control
rows first-class. A control is not silently dropped because its expected state
is blocked, denied, expired, or outside the requested context.

## Operation contract

### Experiment board

The board builder receives `cards` and an exact `context_key`. It returns
ordered columns, sorted cards, dependency edges, blocked IDs, warnings, and
retained issues. Unknown dependencies are visible. A foreign card is excluded
with `context_mismatch`. A malformed card becomes an
`invalid_experiment_card` receipt.

The board is a coordination read model. It does not schedule, execute, or
approve an experiment.

### Launch plan

The launch planner receives `requests` with an artifact ID, runtime, mode,
parameters, resource profile, and network declaration. It returns a parameter
hash, bounded invocation tokens, resource profile, network policy, and state.

Offline requests use `network_disabled`. A request with external access uses
`declared_network_review_required`. Unsupported runtimes and resource profiles
are rejected. The descriptor never contains executable source text.

### Shareable snapshot

The snapshot operation hashes the payload and signs an envelope with the
supplied HMAC secret. Verification reports signature validity, payload hash
validity, expiry, algorithm, and research-use status. A wrong secret produces
`snapshot_signature_invalid`; an expired envelope produces `snapshot_expired`.

The serialized review output does not include signing material. HMAC possession
is not a public-key identity, and integrity is not scientific validation.

### Collaboration access

The access evaluator receives members and requests. Each request is evaluated
against the explicit role matrix. Unknown members, inactive members, foreign
contexts, and actions absent from the role matrix are denied or quarantined.
Every decision includes a reason and policy receipt.

## Runtime sequence

`run_gamma_frontier_runtime` produces eight ordered stages:

1. `data-audit`
2. `fixture-evaluation`
3. `metrics`
4. `policy`
5. `lineage`
6. `reconciliation`
7. `projection-audit`
8. `quality-gate`

`run_gamma_frontier_pipeline` then adds replay, release, bundle, artifact,
review, observability, accessibility, compliance, invariants, scenarios,
thresholds, validation, runbook, adapters, and a compact manifest.

## CLI commands

All commands accept an optional JSON fixture path. With no path they use the
checked-in public aggregate fixture.

```text
gamma-frontier-data-audit
gamma-frontier-contracts
gamma-frontier-schema
gamma-frontier-evaluate
gamma-frontier-replay
gamma-frontier-metrics
gamma-frontier-lineage
gamma-frontier-policy
gamma-frontier-quality-gate
gamma-frontier-runtime
gamma-frontier-observability
gamma-frontier-artifacts
gamma-frontier-bundle
gamma-frontier-release
gamma-frontier-review-queue
gamma-frontier-accessibility
gamma-frontier-compliance
gamma-frontier-invariants
gamma-frontier-adapters
gamma-frontier-scenarios
gamma-frontier-thresholds
gamma-frontier-validation
gamma-frontier-runbook
gamma-frontier-pipeline
export-gamma-frontier-review-csv
```

Example:

```powershell
glio-noncode gamma-frontier-pipeline --output gamma-report.json
glio-noncode export-gamma-frontier-review-csv --output gamma-review.csv
```

## Serialization rules

- JSON uses the repository canonical encoder.
- Sets and enum values are normalized before hashing.
- Every report has a content address.
- Lists that affect review order are explicitly sorted.
- Secrets and raw launch inputs remain outside compact review outputs.
- State and issue codes are retained together.

## Failure handling

The package returns structured failure evidence for expected controls. A
malformed record does not abort the whole fixture evaluation. A quality-gate
failure is retained with a check ID and observed value. A release state is
`blocked` when a blocking check fails, `review` when only advisory review is
needed, and `ready` when all required evidence is present.

## Extension rules

New operations must add:

1. a `GammaFrontierOperation` member;
2. a fixture positive row and at least three controls;
3. an input/output contract;
4. schema fields and output order;
5. execution and expected-state checks;
6. projection assertions;
7. lineage and reconciliation coverage;
8. policy and release behavior;
9. CLI routing;
10. unit and command tests.

Do not add a surface that cannot preserve exact context, source receipts,
negative evidence, content addresses, and an explicit research boundary.
