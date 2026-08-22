# Domain 09 topology frontier evidence gate

This document defines the public aggregate evidence gate for the Domain 09
C13-C16 topology-inference tranche. The gate wraps four existing bounded
adapters and gives them one consistent fixture, source boundary, state
vocabulary, replay path, schema report, policy report, lineage report,
reconciliation report, release manifest, view, and export surface.

## Scope

The gate covers:

- ecDNA regulatory contact summaries;
- signed A/B compartment switch summaries;
- uncertainty-aware topology path transport;
- three-dimensional evidence publication.

The gate is descriptive. A supported result means that the declared adapter
accepted the supplied aggregate row under the declared context and threshold.
It does not mean a causal regulatory link, a mechanistic diagnosis, a clinical
interpretation, or a treatment recommendation.

## Boundary

The fixture boundary is `public_aggregate_non_patient`. Every source receipt has
an HTTPS locator, a public scope, a release label, and a content address. Every
record names one or more source identifiers. No record depends on an individual
record to interpret the result.

The exact context is:

`GRCh38|glioma|adult|stem_like|tumor|unknown`

Context is compared as an exact string. A pediatric, normal-compartment, or
other-context row is retained as a control and cannot be reused as accepted
adult tumor evidence.

## Fixture composition

The default fixture contains sixteen records:

| Capability | Positive | Controls | Adapter |
| --- | --- | --- | --- |
| C13 | 1 | 3 | `EcDNARegulatoryContactModel` |
| C14 | 1 | 3 | `CompartmentSwitchEstimator` |
| C15 | 1 | 3 | `TopologyUncertaintyTransportModel` |
| C16 | 1 | 3 | `ThreeDEvidencePublisher` |

Controls include weak support, missing support, other-context data, malformed
rows, stable values, disconnected paths, missing assay receipts, and empty
publication input. Controls are part of the contract, not optional examples.

## Acceptance sequence

The quality gate evaluates twelve checks in this order:

1. data audit;
2. adapter evaluation;
3. deterministic replay;
4. scenario expectations;
5. interpretation policy;
6. serialized schema;
7. source-to-receipt lineage;
8. expected/observed reconciliation;
9. record closure;
10. source closure;
11. operation closure;
12. bundle acceptance.

The run is accepted only if every check passes. A failed run remains useful for
diagnosis, but release construction rejects it.

## Adapter contracts

### C13 ecDNA regulatory contact

The adapter reads an amplicon identifier, element identifier, gene identifier,
contact score, and source identifiers. The minimum score and minimum source
count are explicit payload parameters. A row below either threshold is a review
state. A row in another context is out of domain. A non-object row is invalid.

The normalized support value is a bounded descriptive transform. The source set,
context, issues, and record address remain attached to the receipt.

### C14 compartment switch

The adapter reads a region identifier and paired signed scores. The sign maps to
the declared A/B labels. A cross-sign delta that reaches the threshold is a
supported switch observation. A small same-compartment delta is partial. Context
and parse failures remain separate controls.

The result does not imply that a compartment change caused any downstream event.
The prior and current scores remain separate fields in the adapter output.

### C15 topology uncertainty transport

The adapter reads path identifiers, ordered node identifiers, edge uncertainty,
and a bounded signal. Uncertainty accumulates across the edge list and reduces
effective signal. A node/edge count mismatch is a disconnected-path issue.

The path is not a claim that a regulatory mechanism exists. It is an explicit
descriptive path over supplied topology observations.

### C16 three-dimensional evidence publication

The publisher requires path identifiers, exact context, a bundle identifier, and
one or more assay identifiers. The resulting bundle preserves record and bundle
addresses. Context mismatch, missing assay identifiers, and empty rows remain
non-success states.

Publication is a release packaging result. It does not add biological meaning
that was absent from the supplied rows.

## State vocabulary

The gate maps adapter outcomes into four stable states:

| Gate state | Meaning |
| --- | --- |
| `supported` | positive path passed the declared adapter boundary |
| `partial` | a review condition remains but the row is parseable |
| `out_of_domain` | context or declared boundary does not match |
| `invalid` | the row cannot be interpreted under the operation schema |

Positive records must be `supported`. Control records must not be `supported`.
The evaluator checks both requirements for every run.

## Evidence artifacts

The gate emits:

- a nine-check data audit;
- sixteen execution receipts;
- 120 evaluation checks;
- eight replay checks;
- sixteen scenario rows and 48 scenario checks;
- eight policy rules and 14 policy checks;
- four operation schemas and 20 schema checks;
- sixteen lineage edges;
- sixteen reconciliation items and three global closure checks;
- four operation metric rows;
- one twelve-check quality report;
- one runtime result and nine-stage trace;
- one release manifest;
- one twelve-row review queue;
- five source-matrix rows;
- receipt, review, metric, and Markdown exports.

Each artifact is content-addressed. Nested addresses allow a reviewer to move
from a release manifest to its bundle, from the bundle to evaluation, and from a
receipt to its source edge.

## Review rules

Reviewers should inspect the first failing check, not the final release state.
The first failing check identifies the owning invariant. For example:

- `data-audit` points to fixture or source boundary drift;
- `evaluation` points to an adapter or record-join problem;
- `replay` points to determinism drift;
- `scenarios` points to changed expected behavior;
- `policy` points to scope or disclosure drift;
- `schema` points to a field or vocabulary mismatch;
- `lineage` points to source-to-receipt closure;
- `reconciliation` points to expected versus observed state;
- `bundle` points to composition or address drift.

## Reproducibility

The default fixture is local and deterministic. The normal test path does not
fetch remote content. Source receipts describe public scope and provenance; they
do not silently refresh the fixture. A refreshed fixture must receive a new
version and a new content address.

Reproducibility requires stable tuple ordering, normalized text, explicit null
handling, deterministic issue ordering, and no wall-clock values in addressed
payloads.

## CLI

The complete command sequence is:

```powershell
glio-noncode audit-topology-frontier-data
glio-noncode evaluate-topology-frontier-fixture
glio-noncode replay-topology-frontier
glio-noncode topology-frontier-quality-gate
glio-noncode evaluate-topology-frontier-scenarios
glio-noncode topology-frontier-contracts
glio-noncode topology-frontier-schema
glio-noncode topology-frontier-policy
glio-noncode topology-frontier-metrics
glio-noncode build-topology-frontier-bundle
glio-noncode topology-frontier-lineage
glio-noncode topology-frontier-reconciliation
glio-noncode run-topology-frontier-pipeline --run-id topology-ci
glio-noncode build-topology-frontier-release --run-id topology-ci --release-id topology-ci
glio-noncode topology-frontier-review-view
glio-noncode topology-frontier-trace --run-id topology-ci
```

CSV and Markdown exports are derived from the same evaluation and view objects.
They are review projections, not alternate evaluation engines.

## Completion criteria

The tranche is complete when:

- all four adapters have positive and control records;
- all source identifiers close against five source receipts;
- every context mismatch remains out of domain;
- every malformed record remains invalid;
- replay is accepted;
- schema, policy, lineage, and reconciliation are accepted;
- the twelve-check quality gate is accepted;
- release construction succeeds only for the accepted report;
- the focused and full test suites pass;
- the staged build contains no prohibited repository metadata markers;
- the build is committed on the main integration line and verified by Actions.
