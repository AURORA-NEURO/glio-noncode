# Domain 11 causal frontier evidence gate

## Purpose

This document describes the release boundary for the causal frontier module.
The boundary is deliberately narrower than a scientific conclusion. It accepts
typed, bounded, content-addressed aggregate records for review and rejects the
idea that a single score is sufficient evidence of mechanism, diagnosis,
prognosis, or treatment value.

The gate is built around four operation paths:

| Code | Operation | Positive output |
| --- | --- | --- |
| C13 | posterior decomposition | supported components |
| C14 | regulatory driver posterior | ranked driver hypotheses |
| C15 | selective prediction | accepted or abstained prediction |
| C16 | causal dossier publication | published evidence manifest |

Each path has one positive record and three controls. The positive record shows
that the adapter can produce a useful bounded receipt. The controls show that
zero support, empty input, invalid numeric ranges, low support, weak score,
high uncertainty, invalid identity, and missing evidence addresses remain
observable.

## Boundary statement

The fixture is public aggregate and non-patient. Its context is pinned to:

```text
GRCh38|glioma|adult|stem_like|core|unknown
```

The source receipts are public aggregate indexes and portals. They supply
context and provenance references; they are not silently treated as a unified
cohort, and they are not a substitute for a study-specific analysis plan.

Allowed uses include:

- aggregate evidence review;
- method development;
- reproducibility testing;
- research triage;
- fixture and contract regression testing;
- source-to-output lineage inspection;
- threshold and abstention sensitivity review.

Excluded uses include:

- patient care;
- diagnostic determination;
- treatment selection;
- pathogenicity declaration;
- actionability declaration;
- individual risk prediction;
- clinical trial eligibility decisions;
- evidence of causal identification.

## Gate layers

The gate is intentionally layered. A release candidate must pass each layer
before it can be called ready.

### 1. Public data audit

The data audit checks the fixture identity, version, context, boundary, source
count, record count, positive/control counts, operation coverage, source
references, HTTPS receipts, and uniqueness of IDs.

The audit does not inspect only the positive rows. It checks the complete
manifest, including the controls. A fixture with valid positive records but
missing controls is not complete.

### 2. Operation contracts

Every operation has a contract with:

- required input fields;
- positive states;
- control states;
- declared issue vocabulary;
- prohibited claim vocabulary;
- public boundary;
- content address.

Contracts are addressable objects. Their addresses make a change to an issue
code, required field, or prohibited-use list visible in a release diff.

### 3. Schema manifest

The schema records field type, requiredness, nullability, semantic role, and
validation for every operation. Common fields include `input_records`,
`context_key`, `content_address`, and `state`. Operation parameters add
thresholds or dossier identity fields where required.

Schema coverage is separate from runtime validation. The schema says what the
boundary expects; the evaluator proves how the implementation behaves when
the expectation is met or violated.

### 4. Positive/control replay

The evaluator runs all 16 records through their declared adapter. It creates
seven checks per record:

1. expected state;
2. expected issue codes;
3. operation dispatch;
4. exact context retention;
5. source receipt resolution;
6. execution content address;
7. positive/control acceptance separation.

It then adds eight global checks for identity, version, context, boundary,
execution count, positive count, control count, and operation count. The result
is 120 checks. This count is part of the depth audit so a future reduction in
coverage is visible.

### 5. Deterministic replay

Replay runs the same fixture twice and compares fixture address, evaluation
address, execution addresses, check count, pass count, and acceptance. A
different replay ID does not change the content addresses. Drift is returned as
named fields rather than hidden behind a boolean.

### 6. Metrics

Metrics report overall check pass rate, positive acceptance rate, control
rejection rate, per-operation acceptance, per-operation issue-free rate, issue
free execution rate, and issue density. These are coverage and process metrics.
They are not estimates of disease risk or biological effect size.

### 7. Lineage

Every source receipt is connected to each execution that cites it. Every fixture
record also has a fixture-to-execution edge. The graph has 36 edges for the
current fixture: 20 source edges and 16 fixture edges. Terminal addresses are
the 16 execution receipts.

The lineage graph is checked for cycles. A cyclic graph is blocked because a
derived receipt must not become its own source.

### 8. Policy

Policy decisions are made from the positive operation path while controls remain
available for quality evidence. Supported aggregate outputs can enter review.
A published dossier can enter a research release only as a manifest. Invalid
or empty positive input is blocked. Issue-bearing positive output requires
review. Controls do not disappear because the positive row is healthy.

### 9. Reconciliation

Reconciliation compares the expected state and issue codes in the fixture with
the observed state and issue codes from replay. A mismatch is tied to a record
ID. This prevents a broad pass flag from hiding a changed control behavior.

### 10. Quality gate

The current quality gate has 12 checks:

| Check | Requirement |
| --- | --- |
| data-audit | public fixture audit passes |
| evaluation | 120 replay checks pass |
| contract-coverage | four operation contracts |
| schema-coverage | four operation schemas |
| lineage-acyclic | no lineage cycle |
| lineage-terminals | 16 terminal execution receipts |
| reconciliation | expected and observed records match |
| content-addresses | execution addresses are present |
| source-boundary | non-patient boundary is explicit |
| positive-controls | four positive records |
| negative-controls | twelve control records |
| issue-vocabulary | every issue is declared |

All twelve checks are blocking for a release candidate.

## Runtime sequence

The runtime assembles the evidence in ten ordered stages:

1. data audit;
2. contract loading;
3. schema loading;
4. fixture replay;
5. metrics;
6. policy;
7. lineage;
8. reconciliation;
9. quality gate;
10. release bundle.

Each stage retains a duration, state, output address, detail, and stage
address. This gives an operator a receipt for each boundary crossing and makes
partial execution easier to diagnose.

## Release manifest

The release manifest binds the bundle, quality gate, and replay receipt. It
stores allowed and excluded uses so the boundary travels with the artifact.
The ready state requires all release checks to pass. A review state is still a
valid diagnostic output, but it must not be presented as a ready release.

The release checks are:

- bundle is addressable;
- quality gate is accepted;
- replay is accepted;
- positive operation decisions are releasable.

## Review questions

Before accepting a release, a reviewer should ask:

1. Does the context key match the intended aggregate scope?
2. Are all source receipts HTTPS and resolvable?
3. Are positive and control rows both present?
4. Do issue codes explain every control result?
5. Are uncertainty and abstention retained in the output?
6. Does the dossier contain evidence addresses rather than unsupported prose?
7. Does the lineage graph end at execution receipts?
8. Are policy decisions consistent with the positive path?
9. Are the excluded-use boundaries included in the manifest?
10. Does a second replay produce the same content addresses?

## Command examples

```powershell
glio-noncode causal-frontier-data-audit
glio-noncode causal-frontier-contracts
glio-noncode causal-frontier-schema
glio-noncode causal-frontier-evaluate
glio-noncode causal-frontier-replay
glio-noncode causal-frontier-metrics
glio-noncode causal-frontier-lineage
glio-noncode causal-frontier-policy
glio-noncode causal-frontier-quality-gate
glio-noncode causal-frontier-runtime
glio-noncode causal-frontier-release
glio-noncode causal-frontier-depth-audit
glio-noncode export-causal-frontier-review-csv
```

Each command can write JSON or CSV to an output path. The default fixture is
used when no input path is supplied. A caller-supplied fixture must preserve
the same object shape and will be audited before it is trusted.

## Change control

Changes to source receipts, fixture counts, issue vocabulary, thresholds,
policy decisions, schema fields, and prohibited uses are release-significant.
They require updated tests, a depth-audit review, and a fresh content address.
An implementation change that leaves the public API intact can still alter a
receipt and must be reviewed as a behavior change.

The module is ready for the next frontier only when its control behavior is
stable, its release notes are clear, and its evidence boundary remains narrow.
