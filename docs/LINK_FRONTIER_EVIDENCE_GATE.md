# Domain 10 link frontier evidence gate

This document describes the Domain 10 C13-C16 evidence gate. The gate is a
public aggregate research boundary for candidate relationships among variants,
regulatory elements, and genes. It is intentionally narrower than a causal,
clinical, pathogenicity, or actionability system.

## Boundary

The fixture boundary is `public_aggregate_non_patient`.

The pinned context is:

```text
GRCh38|glioma|adult|stem_like|core|unknown
```

The fixture does not contain patient-level records. It contains source
receipts, operation inputs, expected states, issue expectations, and content
addresses. A source receipt identifies a public archive and the declared scope
for which it is used. The receipt does not claim that the archive supports
every downstream interpretation.

The fixture includes:

- four positive records, one for each operation;
- twelve controls, three for each operation;
- five HTTPS source receipts;
- one exact context key;
- one content address for the fixture;
- one content address for every source and record.

The positive/control ratio is deliberate. A release can pass only when the
positive paths execute and the controls retain their expected review or
invalid state.

## Capability map

| Capability | Operation | Existing primitive | Frontier depth |
| --- | --- | --- | --- |
| C13 | `link_dependence_correction` | `LinkEvidenceDependenceCorrector` | group size, raw support, corrected support |
| C14 | `target_gene_ranking` | `TargetGeneRanker` | score components, rank order, alternatives |
| C15 | `link_calibration_abstention` | `LinkCalibrationAndAbstention` | uncertainty, error, thresholds, abstention |
| C16 | `link_evidence_publication` | `LinkEvidencePublisher` | source IDs, context, record and bundle addresses |

The existing primitives remain responsible for their operation semantics. The
frontier modules provide receipts, controls, replay, policy, lineage, schema,
quality, release, observability, and review surfaces around those semantics.

## Execution stages

The runtime exposes nine deterministic stages:

1. `load` reads the fixture and checks its boundary.
2. `evaluate` dispatches every record to its declared operation.
3. `reconcile` compares expected states and issue codes with observed output.
4. `lineage` closes source, record, and execution parents.
5. `policy` evaluates bounded-use rules.
6. `schema` checks operation fields and state vocabularies.
7. `metrics` computes record, state, issue, and acceptance rates.
8. `quality` runs the release-quality checks.
9. `complete` records the final accepted or blocked state.

The runtime does not silently skip a stage. A missing or malformed input is
represented by a structured issue and a non-accepted state.

## C13 dependence correction

Dependence correction groups evidence paths by a declared dependence group.
Each path retains:

- link ID;
- context key;
- raw support;
- dependence group;
- group size;
- corrected support;
- operation state;
- content address.

The correction used by the current primitive is a bounded descriptive
transform. If two paths share a group, their support is divided by the group
size. The transform is not a probability calibration and is not evidence of a
regulatory mechanism.

The positive record has two paths in one group and one path in a second group.
The controls cover:

- zero support;
- empty input;
- support outside the declared bound.

The depth audit checks that corrected support does not exceed raw support,
group size is positive, context is retained, and zero support is surfaced.

## C14 target-gene ranking

Target-gene ranking orders declared component scores. The output retains:

- link ID;
- variant ID;
- regulatory element ID;
- gene ID;
- component score map;
- total score;
- deterministic rank;
- top-gene map;
- review or accepted state;
- content address.

The positive record contains two genes for one variant and element. The lower
scoring gene is retained as an alternative. The operation does not remove a
gene because it is not ranked first.

The controls cover:

- empty component scores;
- missing gene identity;
- empty input.

The depth audit checks contiguous rank values, gene identity, component score
retention, alternative-gene presence, deterministic top mapping, and zero
support review state.

## C15 calibration and abstention

Calibration compares an optional observed score with a predicted score and
retains the absolute calibration error. An uncertainty threshold and a
calibration-error threshold are declared in the fixture input.

The accepted path has low uncertainty and low error. The controls cover:

- uncertainty above the abstention threshold;
- calibration error above the declared threshold;
- empty input.

An abstained row is not converted into a negative finding. It remains a review
state with its issue code, predicted score, observed score when present,
uncertainty, and calibration error.

The depth audit checks that decisions are present, accepted IDs are explicit,
uncertainty and error are retained, thresholds are fixture data, and both
adversarial controls are surfaced.

## C16 publication

Publication requires a non-empty bundle ID, link IDs, source IDs, and exact
context. The returned bundle contains:

- bundle ID;
- exact context;
- sorted link IDs;
- records address;
- bundle address;
- published state.

The controls cover context mismatch, missing source identity, and empty input.
The publisher rejects a cross-context row instead of transporting it to the
bundle context.

The depth audit checks the published state, bundle address, records address,
link ID order, exact context, context mismatch control, and source control.

## Reconciliation

Reconciliation is record-level. For each record it compares:

1. expected state and observed state;
2. expected issue codes and observed issue codes;
3. the resulting acceptance boolean;
4. the execution content address.

All sixteen records must reconcile. A positive record is accepted only when
its expected supported or published state is observed. A control is successful
when its expected partial or invalid state and issue vocabulary are observed.

## Lineage

The lineage graph has a fixture root, source nodes, record nodes, and execution
nodes. Source nodes point to the fixture. Records point to every referenced
source. Executions point to their record. The graph verifier checks:

- every parent ID resolves;
- node IDs are unique;
- a root exists;
- the graph is not empty;
- execution nodes are present for every record.

The graph is content-addressed but not a substitute for source licensing or
archive retention. It records what the release consumed.

## Policy

The policy report has twelve rules:

1. boundary;
2. context;
3. source closure;
4. positive and control separation;
5. missingness;
6. dependence grouping;
7. alternatives;
8. calibration thresholds;
9. publication path;
10. interpretation limits;
11. content addresses;
12. deterministic evaluation.

Blocking rules prevent release when boundary, source closure, publication, or
interpretation limits are missing. Review rules retain uncertainty and
missingness without erasing a record.

## Quality gate

The quality gate has twelve checks:

| Check | Required observation |
| --- | --- |
| data audit | accepted |
| evaluation | all fixture checks pass |
| reconciliation | all records reconcile |
| lineage | graph is valid |
| policy | all rules pass |
| schema | all schema checks pass |
| replay | repeated run is deterministic |
| positive acceptance | `1.0` |
| control rejection | `1.0` |
| record count | `16` |
| source count | `5` |
| operation count | `4` |

The separate depth audit adds fifty-one operation and contract invariants. It
does not replace the quality gate; it verifies the information density of the
four operation outputs.

## Replay

Replay executes the same fixture twice. It compares states, issue codes,
execution addresses, and evaluation addresses. A replay mismatch is visible
even if the state values happen to match.

Replay is deterministic because:

- fixture rows have stable order;
- group and rank operations use stable sorting;
- source and link IDs are sorted at publication;
- hashes use canonical serialization;
- thresholds are declared in the fixture payload.

## Release limitations

The release manifest is descriptive only. It does not assert:

- a causal regulatory link;
- a target-gene mechanism;
- clinical relevance;
- pathogenicity;
- prognosis;
- treatment response;
- actionability;
- patient-level validity;
- transportability to another context;
- calibration outside the declared fixture.

External validation, assay calibration, negative-control expansion, and
context-specific replication remain required for scientific interpretation.

## Commands

```powershell
glio-noncode audit-link-frontier-data --output link-data.json
glio-noncode evaluate-link-frontier-fixture --output link-evaluation.json
glio-noncode replay-link-frontier --output link-replay.json
glio-noncode link-frontier-quality-gate --output link-quality.json
glio-noncode link-frontier-depth-audit --output link-depth.json
glio-noncode link-frontier-contracts --output link-contracts.json
glio-noncode link-frontier-schema --output link-schema.json
glio-noncode link-frontier-policy --output link-policy.json
glio-noncode link-frontier-metrics --output link-metrics.json
glio-noncode build-link-frontier-bundle --output link-bundle.json
glio-noncode link-frontier-lineage --output link-lineage.json
glio-noncode link-frontier-reconciliation --output link-reconciliation.json
glio-noncode run-link-frontier-pipeline --run-id link-ci --output link-pipeline.json
glio-noncode build-link-frontier-release --run-id link-ci --release-id link-ci --output link-release.json
glio-noncode link-frontier-review-view --output link-view.json
glio-noncode link-frontier-trace --run-id link-ci --output link-trace.json
```

## Review procedure

1. Confirm the fixture boundary and context.
2. Confirm source IDs resolve to HTTPS receipts.
3. Run the data audit.
4. Run the fixture evaluation.
5. Inspect all twelve controls.
6. Run the depth audit.
7. Review issue counts and review queue priorities.
8. Run replay.
9. Run the quality gate.
10. Inspect the release limitations.
11. Publish only the sanitized release manifest and selected exports.

No review step may convert an abstained or contradictory row into support by
editing the state alone. A new fixture record or declared rule is required.
