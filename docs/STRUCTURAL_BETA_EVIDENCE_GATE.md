# Domain 02 C05-C08 structural beta evidence gate

## Purpose

This document defines the executable evidence boundary for the four structural
beta capabilities in Domain 02:

| Capability | Operation | Primary question | Release posture |
| --- | --- | --- | --- |
| GNC-D02-C05 | focal amplification | Do caller-supported copy-number segments form a bounded focal candidate? | descriptive candidate |
| GNC-D02-C06 | chromothripsis | Does a bounded breakpoint cluster contain the supplied oscillation pattern? | descriptive pattern |
| GNC-D02-C07 | ecDNA | Do circular, junction, and copy-number observations support a circular candidate? | descriptive candidate |
| GNC-D02-C08 | enhancer hijacking | Do exact-context bridge and activity/contact observations support an enhancer-to-gene candidate? | descriptive link |

The gate turns the existing detector adapters into a release-shaped, public,
aggregate-only contract. It does not create a new detector implementation. A
positive fixture record is executed through the operation adapter, compared to
its declared result state and counts, and then represented by a sanitized
receipt. A control record is expected to remain reviewable, abstained, partial,
ambiguous, or out of domain according to the operation contract.

The checked-in fixture is a mechanics fixture. It proves deterministic branch
behavior, state semantics, source/context agreement, payload boundaries, and
cross-surface integrity. It is not a cohort, a patient callset, a clinical
truth set, or a claim that any individual structural event is biologically
present.

## Reproducible entry points

Run these commands from the repository root after installing the package in
editable mode:

```powershell
python -m glio_noncode audit-structural-beta-data examples/structural-beta-public-aggregate.json --output beta-data.json
python -m glio_noncode evaluate-structural-beta-fixture examples/structural-beta-public-aggregate.json --output beta-fixture.json
python -m glio_noncode replay-structural-beta-fixtures examples/structural-beta-public-aggregate.json --output beta-replay.json
python -m glio_noncode structural-beta-quality-gate examples/structural-beta-public-aggregate.json --output beta-quality.json
python -m glio_noncode evaluate-structural-beta-scenarios examples/structural-beta-public-aggregate.json --output beta-scenarios.json
python -m glio_noncode structural-beta-contracts --output beta-contracts.json
python -m glio_noncode build-structural-beta-bundle examples/structural-beta-public-aggregate.json --output beta-bundle.json
python -m glio_noncode structural-beta-lineage examples/structural-beta-public-aggregate.json --output beta-lineage.json
python -m glio_noncode run-structural-beta-pipeline examples/structural-beta-pipeline-accepted.json --output beta-pipeline.json
```

The command exit policy is strict for evidence commands. A passing evaluation,
audit, replay, scenario matrix, quality gate, or lineage audit exits zero. A
failed gate exits two. Contract emission is a manifest operation and exits zero
after the registry is constructed. Bundle creation refuses a review-state
fixture unless `--allow-review` is supplied. Pipeline execution exits zero only
when all four stages accept at least one input record without an issue.

## Fixture identity

The canonical fixture is:

```text
examples/structural-beta-public-aggregate.json
```

Its schema version is `structural-beta-evidence-v1`. The fixture identity is
content-addressed from its parsed JSON representation. The exact context key is
the six-field string below:

```text
GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment
```

The six fields are ordered and are not normalized by the gate. A record with a
different assembly, disease label, age band, lineage, territory, or treatment
phase is a different context and cannot silently join this fixture. Context
comparison is exact in the data audit, fixture evaluator, replay checker,
scenario matrix, quality gate, lineage graph, and runtime request envelope.

The fixture contains four public source receipts, four positive records, and
eight review controls. Record IDs are unique across both arrays. Each record
names one operation, one source receipt, one exact context, a detector payload,
an expected detector result state, and optional expected counts or issue codes.

## Public source boundary

The fixture uses public aggregate source receipts only. The receipts identify
the source, title, URL, version label, license note, data scope, retrieval
date, and aggregate flag. The current receipt set is:

| Receipt | Public endpoint | Use in this gate |
| --- | --- | --- |
| `ncbi-dbvar-nstd102` | <https://www.ncbi.nlm.nih.gov/dbvar/content/human_hub/> | structural variation study framing |
| `ncbi-dbvar-nstd186` | <https://www.ncbi.nlm.nih.gov/dbvar/content/common_summary/> | common structural variation summary framing |
| `gnomad-sv-v4` | <https://gnomad.broadinstitute.org/news/2023-11-v4-structural-variants/> | public structural-variant release framing |
| `ncbi-dbvar-study-browser` | <https://www.ncbi.nlm.nih.gov/dbvar/studies/> | public study-browser framing |

These URLs are source receipts, not a claim that the checked-in mechanics rows
were downloaded from the endpoint. The fixture deliberately stores compact
aggregate observations so local CI is deterministic and offline. The receipts
make the intended source scope inspectable; they do not substitute for a
future source-specific extraction manifest or truth-set comparison.

The data audit rejects a source that is marked patient-level or whose scope
does not explicitly contain `public` or `aggregate`. It also rejects duplicate
source IDs, missing URLs, unsupported URL schemes, and record source IDs that
do not resolve to a receipt.

## Record schema

The top-level fixture object contains these fields:

| Field | Type | Required meaning |
| --- | --- | --- |
| `fixture_id` | string | stable fixture identity label |
| `schema_version` | string | must equal `structural-beta-evidence-v1` |
| `context_key` | string | exact six-field context |
| `provenance` | string | human-readable aggregate provenance boundary |
| `patient_level` | boolean | must be false |
| `sources` | array | public aggregate source receipts |
| `positives` | array | accepted fixture records, one per operation minimum |
| `controls` | array | review fixture records, two per operation minimum |
| `notes` | array | scope and limitation notes |

Each positive or control record contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `record_id` | string | unique stable record identity |
| `operation` | enum | one of the four C05-C08 operation names |
| `expected_state` | enum | `accepted` for positives or `review` for controls |
| `expected_result_state` | string | detector state expected from the adapter |
| `context_key` | string | must equal the top-level context exactly |
| `source_id` | string | must resolve to one public source receipt |
| `payload` | object | detector parameters and aggregate records |
| `required_issue_codes` | array | issue codes that must remain visible |
| `expected_counts` | object | named integer counts checked by the evaluator |
| `description` | string | review-facing rationale for the record |

The evaluator does not publish the payload. It publishes the operation, result
state, counts, issue codes, detector output address, and a short detail string.
Candidate and issue objects are reduced to safe fields and raw operation
objects are removed from the release receipt.

## Operation contracts

### C05 focal amplification

The mapper receives segment records with chromosome, start, end, caller, and
copy-number values. The fixture parameters declare an amplification threshold,
minimum gain, and boundary tolerance. The positive has two caller-supported
high-copy segments with shared boundaries. The controls cover a low-copy
segment and an invalid negative copy number.

The accepted mechanics behavior is:

1. invalid coordinates or copy numbers remain visible as an issue;
2. segments below the amplification threshold do not become candidates;
3. high-copy segments are merged only when observed gap and boundary rules
   permit the merge;
4. candidate boundaries retain caller-specific support rather than a fabricated
   sequence-level boundary;
5. a positive result remains a focal candidate and not a gene-level claim.

### C06 chromothripsis pattern

The detector receives breakpoint rows with chromosome, position, orientation,
and optional copy-number state. The positive has six tightly spaced rows with
alternating orientation and high/low copy-number state. Controls remove copy
number or place rows beyond the permitted gap.

The accepted mechanics behavior is:

1. cluster span and maximum gap are bounded explicitly;
2. orientation switches are counted, not interpreted as a probability;
3. copy-number oscillation is reported only when supplied and required;
4. missing copy-number state produces a partial or review result;
5. far-apart breakpoints abstain rather than forming a long-range pattern.

The evidence index is descriptive. It does not establish a mutational process,
temporal sequence, or biological mechanism.

### C07 ecDNA candidate

The detector receives component rows with caller identity, circularity,
junction count, copy number, and optional contradictory linear evidence. The
positive has two circular caller observations with junction and amplification
support. Controls cover high copy without circular evidence and conflicting
linear evidence.

The accepted mechanics behavior is:

1. circular evidence is explicit and caller-bound;
2. junction support meets the declared minimum;
3. amplification support meets the declared minimum;
4. high copy alone abstains;
5. contradictory linear evidence remains ambiguous instead of being discarded.

The result is a candidate component summary. It is not molecule imaging,
long-read reconstruction, or a claim of autonomous replication.

### C08 enhancer hijacking

The detector receives bridge rows connecting an enhancer to target genes. Each
row carries an exact context, event ID, enhancer ID, target gene ID, and
declared breakpoint, activity, or contact channels. The positive uses a shared
event and enhancer with two target genes. Controls omit the structural bridge
or use a context with a different territory.

The accepted mechanics behavior is:

1. context is compared exactly, including territory and treatment phase;
2. an explicit structural bridge is required;
3. evidence channels are counted from declared fields;
4. alternative target genes remain visible;
5. nearest-gene distance is not used as a substitute for a bridge.

The result is a context-qualified candidate link. It is not a causal regulatory
claim or an expression effect estimate.

## Evaluation contract

`evaluate_structural_beta_fixture` executes all twelve records through the
existing adapters. Each record receives state, result-state, output-address,
count, and required-issue checks. The canonical fixture produces 63 checks:

| Group | Records | Checks |
| --- | ---: | ---: |
| four positives | 4 × 5 | 20 |
| five base controls | 5 × 5 | 25 |
| negative-copy control | 1 × 6 | 6 |
| missing-bridge control | 1 × 6 | 6 |
| context-mismatch control | 1 × 6 | 6 |
| total | 12 | 63 |

The five base checks are fixture state, detector result state, output address,
and the declared candidate and issue counts as applicable. Additional control
checks require the issue code to remain visible. A positive is accepted only
when its detector state is supported, partial, or ambiguous and it has no
issue code. A control is expected to remain review-level even when its detector
state is useful for diagnosis.

The evaluation report contains twelve sanitized operation receipts. Every
receipt includes a content address beginning with `sha256:`. Its aggregate
address is calculated from the report body, making repeated evaluation stable.

## Replay contract

`replay_structural_beta_fixtures` verifies the fixture identity across one or
more paths. The canonical expectation requires:

- the expected fixture ID;
- the exact six-field context;
- the sorted four-source receipt set;
- at least 40 evaluation checks;
- at least four positive records;
- at least eight control records;
- no duplicate fixture identity;
- no duplicate fixture content address;
- no cross-fixture context drift.

Replay does not merge two fixtures. A second fixture with a different intended
version must use a different identity and be evaluated under a separately
declared expectation. This prevents a path list from silently combining
incompatible context or source boundaries.

## Scenario matrix

`evaluate_structural_beta_scenarios` runs each positive and control in an
independent scenario result. The canonical matrix contains twelve scenarios,
four positive scenarios, and eight review scenarios. A scenario records the
expected fixture state, observed fixture state, detector state, issue codes,
and output address. The matrix also checks that expected result-state drift is
not hidden by an aggregate pass.

The scenario layer is intentionally separate from the fixture evaluator. The
evaluator emphasizes detailed record assertions; the scenario matrix
emphasizes independent state transitions and expected behavior categories.

## Quality gate

`evaluate_structural_beta_quality_gate` reconciles the data audit, evaluation,
replay, scenario matrix, contract registry, and lineage graph. The canonical
gate has 20 named checks:

| Check family | Checks |
| --- | --- |
| data and execution | data audit, fixture evaluation, check floor |
| replay and scenarios | replay, scenario matrix |
| coverage | positive floor, control floor, operation coverage |
| contracts and context | contract floor, context agreement, source agreement |
| identity and scope | determinism, positive IDs, control IDs, aggregate scope |
| publication shape | address floor, contract-state coverage, sanitized boundary |
| lineage | lineage audit, 29-node/36-edge lineage shape |

The gate enters review when any check is false. Its report includes the
content-addressed evaluation, replay, scenario, contract, and lineage
components, allowing a reviewer to identify which surface drifted.

## Lineage graph

`build_structural_beta_lineage` constructs a typed graph with:

- four source nodes;
- one fixture node;
- twelve record nodes;
- twelve result nodes;
- twelve `declares` edges from sources to records;
- twelve `contains` edges from the fixture to records;
- twelve `produces` edges from records to results.

The result is 29 nodes and 36 edges. Every node and edge is content-addressed.
The audit checks source coverage, fixture presence, record/result pairing,
exact context across nodes, source references, endpoint integrity, and graph
address. The graph contains no detector payload, subject identifier, or
patient-level field.

## Runtime pipeline

`run_structural_beta_pipeline` accepts a request envelope with request ID,
manifest ID, exact context, source IDs, and one payload per operation. The
stages run in fixed order:

```text
focal_amplification -> chromothripsis -> ecdna -> enhancer_hijacking
```

Each stage emits a receipt with capability ID, operation, input count, accepted
count, review count, result state, issue codes, output address, and detail. The
count invariant is `accepted_count + review_count = input_count` for every
stage. The published manifest contains only stage IDs and addresses plus the
request/context/source identity.

The aggregate runtime state is:

| State | Meaning |
| --- | --- |
| `accepted` | all four stages have non-empty accepted input and no issue |
| `review` | at least one stage executed, but one or more stages require review |
| `blocked` | no stage has executable input; no manifest is published |

The accepted request is checked in at
`examples/structural-beta-pipeline-accepted.json`. The review request at
`examples/structural-beta-pipeline-review.json` demonstrates invalid copy
number, missing copy-number state, conflicting linear evidence, and context
mismatch propagation.

## Bundle relationship

The bundle builder requires the quality gate. It contains twelve entries, one
for each positive or review record, and references the quality and lineage
addresses. JSON is the canonical machine projection; CSV is the row projection
for review tables; Markdown is the compact human-readable projection. The
complete root and entry rules are defined in
`docs/STRUCTURAL_BETA_BUNDLE_FORMAT.md`.

## Limitations and next validation layer

This gate does not provide:

- patient-level data or consent/custody records;
- a complete structural-variant truth set;
- sequence reconstruction or molecule-level circularity validation;
- gene-expression validation for enhancer links;
- calibrated probabilities for any pattern;
- clinical interpretation or treatment recommendation;
- external database download reproducibility beyond the declared receipts.

The next validation layer should add versioned source extraction manifests,
independent benchmark callsets, caller-specific concordance reports, and
external calibration. Those additions must preserve the exact context, source
receipt, review state, address, and aggregate-only boundaries defined here.

## Verification checklist

Before treating a beta build as a verified local release, confirm:

1. the fixture data audit is accepted;
2. all 63 canonical checks pass;
3. replay sees the expected identity, source set, and context;
4. all 12 scenarios pass;
5. all 20 quality checks pass;
6. all four contracts are present;
7. the lineage audit passes with 29 nodes and 36 edges;
8. the bundle contains four positive and eight review entries;
9. the runtime accepted example has four accepted stage receipts;
10. serialized outputs contain no raw operation payloads;
11. content addresses remain stable on repeated local runs;
12. the same commands pass in the repository Actions workflow.
