# D14 Evidence Architecture

D14 is the aggregate evidence lifecycle and release boundary. It binds three existing public aggregate delegate families into one typed, deterministic surface. The module preserves source receipts, operation contracts, positive paths, held paths, context controls, review projections, content addresses, and a release decision.

The module is intentionally bounded. It is an evidence-processing architecture and not a patient record, a clinical decision service, an efficacy claim, or an inference about a person. Payloads stay at public aggregate scope, and every held state remains visible for review.

## Completion surface

The checked-in fixture is `evidence-architecture-public-aggregate-001`.

| Measure | Count | Closure rule |
| --- | ---: | --- |
| Public source receipts | 19 | Every source is public aggregate and content addressed |
| D14 operations | 16 | One operation per C01-C16 capability |
| Cases | 64 | One positive and three controls per operation |
| Positive cases | 16 | One positive contract path per operation |
| Control cases | 48 | One each of control A, B, and C per operation |
| Evaluation checks | 458 | Seven checks per case plus ten global checks |
| Ledger events | 80 | Sixteen operation declarations plus sixty-four executions |
| Projection artifacts | 6 | Public fixture, source register, evaluation, review, lineage, metrics/ledger |
| Runtime stages | 24 | Load through final addressed runtime |
| Quality checks | 10 | Audit, plan, evaluation, replay, artifacts, metrics, lineage, release, ledger, state coverage |

The aggregate fixture is reproducible from the three delegate fixtures and does not clone or embed a repository. Only public aggregate source and record data is retained.

## Family boundaries

| Aggregate family | Capability range | Plane | Sources | Records | Context |
| --- | --- | --- | ---: | ---: | --- |
| `evidence_lifecycle_frontier` | C01-C04 | `lifecycle_foundation` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|core\|untreated` |
| `lifecycle_beta_frontier` | C05-C12 | `lifecycle_adjudication` | 9 | 32 | `GRCh38\|glioma\|adult\|stem_like\|core\|untreated` |
| `evidence_release_frontier` | C13-C16 | `evidence_release` | 5 | 16 | `GRCh38\|glioma\|adult\|stem_like\|tumor_core\|pre_treatment` |

The aggregate context is `multi_context_public_aggregate`. A case may retain a foreign context only when the delegate result also contains an explicit `context_mismatch` issue. This makes control behavior inspectable instead of silently normalizing a mismatch.

## Operation matrix

| Capability | Operation | Delegate operation | Input contract | Output contract |
| --- | --- | --- | --- | --- |
| C01 | `citation_resolution` | `citation_resolution` | source receipt | resolved citation state |
| C02 | `graph_construction` | `graph_construction` | source and edge fields | graph node/edge projection |
| C03 | `edge_validation` | `edge_validation` | typed edge | validated edge result |
| C04 | `disagreement_tracking` | `disagreement_tracking` | competing claims | contradiction ledger entry |
| C05 | `tier_adjudication` | `tier_adjudication` | tier evidence | adjudicated tier |
| C06 | `provenance_lineage` | `provenance_lineage` | lineage references | lineage projection |
| C07 | `uncertainty_ledger` | `uncertainty_ledger` | uncertainty fields | uncertainty entry |
| C08 | `review_routing` | `review_routing` | issue and role fields | review queue item |
| C09 | `blinded_adjudication` | `blinded_adjudication` | blinded claims | adjudication decision |
| C10 | `comment_change_log` | `comment_change_log` | comment revisions | change record |
| C11 | `release_decision` | `release_decision` | gate results | release decision |
| C12 | `evidence_delta` | `evidence_delta` | prior/current claims | delta record |
| C13 | `reclassification` | `reclassification` | current classification | reclassification record |
| C14 | `supersession` | `supersession` | release lineage | supersession record |
| C15 | `reproducibility_bundle` | `reproducibility_bundle` | artifacts and addresses | bundle manifest |
| C16 | `signed_dossier` | `signed_dossier` | dossier sections | signed dossier |

Operation nodes retain ordinal order and dependencies. The plan validator requires every dependency to resolve to an earlier operation and requires exactly four cases for each operation.

## Case and control design

Every case contains:

- a stable case and operation join key;
- aggregate and delegate contexts;
- family, plane, and scenario enums;
- delegate fixture, record, and class references;
- source receipt identifiers;
- bounded payload fields;
- an expected state and ordered issue-code tuple;
- source, payload, output, and issue counts;
- a deterministic content address.

Positive paths preserve real observed delegate states. Some positive paths are intentionally held because the underlying aggregate result is partial, contradictory, review-required, or ready for review. A positive label does not force a successful state.

Controls cover the failure surface of each operation. Examples include missing fields, graph context mismatch, invalid uncertainty, tier direction conflict, missing parent, split verdicts, duplicate log identifiers, blocking gates, explicit rejection, changed citations, supersession cycles, expired dossiers, and missing independent review.

The control matrix is available through `evidence_architecture_control_rows` and `evidence_architecture_contract_matrix`. The evaluation keeps the issue vocabulary exactly as returned by each delegate evaluator.

## Evaluation accounting

Each of the 64 cases receives seven checks:

1. observed state matches the case contract;
2. issue codes match exactly;
3. bounded counts match exactly;
4. operation join resolves;
5. source joins resolve;
6. the exact family context or explicit mismatch control is visible;
7. an addressed receipt closes the case.

Ten global checks then close the matrix:

1. all 64 cases execute;
2. all 16 positive paths exist;
3. each of the three control scenarios has 16 cases;
4. family counts are 16, 32, and 16;
5. every operation has four cases;
6. source coverage resolves;
7. every result has an explicit state;
8. every output has an address;
9. foreign contexts carry explicit mismatch evidence;
10. executions and receipts cover the complete fixture.

The accepted evaluation requires every check to pass. A failed evaluation produces `review` state and cannot produce a published release.

## Runtime stages

The runtime is deliberately inspectable. Each stage carries an ordinal, input addresses, output address, check identifier, detail string, and stage address.

| Range | Stages |
| --- | --- |
| 1-4 | fixture load, source audit, schema validation, plan compilation |
| 5-8 | foundation, beta foundation, beta adjudication, and release family readiness |
| 9-12 | case execution, review routing, lineage linking, ledger closure |
| 13-16 | metrics, replay, artifacts, and bundle closure |
| 17-20 | release, quality, depth, and public-boundary compliance |
| 21-24 | controls, report, runtime seed, and final address |

The runtime is accepted only when audit, plan, evaluation, replay, review, quality, compliance, and release closure all pass.

## Public-boundary rules

The compliance module traverses case payloads and rejects restricted identity or decision fields. Reserved keys are checked without placing them into the public fixture. Source receipts must declare `public_aggregate=True`, contexts must remain non-empty, and all case addresses must be present.

The release limitations are retained in the release object and report. They state that the data is aggregate, that lifecycle states are not efficacy or causal claims, that held paths remain visible, and that external review and institutional controls are outside the release.

## Python surface

The stable export surface is `glio_noncode.evidence_architecture_exports`. The package root re-exports the D14 symbols. Main entry points are:

```python
from glio_noncode.evidence_architecture_runtime import run_evidence_architecture

runtime = run_evidence_architecture()
assert runtime.accepted
assert len(runtime.evaluation.checks) == 458
```

Useful supporting entry points include:

- `default_evidence_architecture_fixture`
- `audit_evidence_architecture_data`
- `build_evidence_architecture_plan`
- `evaluate_evidence_architecture_fixture`
- `build_evidence_architecture_review_queue`
- `evidence_architecture_lineage_rows`
- `build_evidence_architecture_ledger`
- `evidence_architecture_metrics`
- `replay_evidence_architecture_fixture`
- `build_evidence_architecture_artifacts`
- `build_evidence_architecture_release`
- `assess_evidence_architecture_quality`
- `assess_evidence_architecture_compliance`
- `deep_audit_evidence_architecture`
- `build_evidence_architecture_report`

## Verification commands

```text
python -m glio_noncode evidence-architecture-fixture --output data/evidence-architecture-public-aggregate.json
python -m glio_noncode evidence-architecture-data-audit --input data/evidence-architecture-public-aggregate.json --output /tmp/evidence-data.json
python -m glio_noncode evaluate-evidence-architecture --input data/evidence-architecture-public-aggregate.json --output /tmp/evidence-evaluation.json
python -m glio_noncode evidence-architecture-runtime --input data/evidence-architecture-public-aggregate.json --output /tmp/evidence-runtime.json
python -m glio_noncode evidence-architecture-query --input data/evidence-architecture-public-aggregate.json --operation D14-C14 --output /tmp/evidence-query.json
python -m unittest tests.test_evidence_architecture tests.test_evidence_architecture_exports tests.test_evidence_architecture_reporting tests.test_evidence_architecture_cli
```

The checked-in CI workflow runs the same fixture, audit, plan, evaluation, runtime, quality, depth, replay, report, compliance, validation, scenario, source, bundle, and focused test commands.
