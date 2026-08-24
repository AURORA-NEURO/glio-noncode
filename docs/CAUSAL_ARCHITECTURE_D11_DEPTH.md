# D11 Causal Architecture Depth Build

## Scope

D11 is the causal evidence research aggregate. It joins four public causal
families into a typed, deterministic, review-gated surface for hypotheses,
mediators, sensitivity analysis, and release dossiers. The module records
support, review, partial result, abstention, invalid input, context mismatch,
and publication states without promoting descriptive evidence into a clinical
claim.

This build raises D11 to the full closure standard used by the later product
domains. The original six case checks and eight global checks are expanded to
seven case checks and ten global checks. Schema validation, recursive public
boundary checks, depth fields, report materialization, and runtime quality are
now part of the accepted runtime rather than independent side reports.

## Inventory

| Record | Count | Rule |
| --- | ---: | --- |
| Public source receipts | 20 | four causal family registries |
| Operations | 16 | four operations per family |
| Positive cases | 16 | one per operation |
| Control cases | 48 | three per operation |
| Total cases | 64 | exact scenario matrix |
| Per-case checks | 448 | seven per case |
| Global checks | 10 | cardinality, balance, context, and receipt closure |
| Evaluation checks | 458 | `64 * 7 + 10` |
| Ledger events | 80 | deterministic lifecycle events |
| Artifacts | 6 | public and review-safe projections |
| Runtime stages | 24 | ordered and addressed |
| Quality checks | 10 | release and boundary controls |

## Causal family map

### Foundation family

The foundation family covers typed hypothesis objects, factor graph
construction, context-conditioned priors, and measurement likelihoods. It
retains the declared GRCh38 glioma stem-like core context and uses review
controls for insufficient independent sources, unsupported contexts, and
invalid hypothesis inputs.

### Beta mediator family

The beta family covers sequence-to-element, element-to-gene, gene-to-state, and
counterfactual allele mediators. It keeps mediator state separate from the
aggregate state and preserves controls for missing links, unsupported
transitions, and foreign context.

### Alpha sensitivity family

The alpha family covers mediation sensitivity, confounding checklists,
dependence correction, and negative evidence integration. Controls remain
visible when assumptions fail, independent sources are insufficient, or
negative evidence cannot be reconciled.

### Frontier release family

The frontier family covers posterior decomposition, regulatory driver
posterior, selective prediction abstention, and causal dossier publication. It
retains the release boundary and rejects invalid dossier inputs rather than
publishing an incomplete causal record.

## Seven case checks

Each case closes the following checks:

1. Aggregate state equals the expected positive or review state.
2. Delegate result state is retained exactly.
3. Issue codes are retained as an ordered tuple.
4. Count summary matches the declared case accounting.
5. At least one public source receipt is attached.
6. Delegate context equals the aggregate context, or the case explicitly
   contains `context_mismatch`.
7. Receipt and output address are closed.

The context check uses the case’s exact delegate context. This makes a foreign
context control independently inspectable instead of inferring its reason from
the review state alone.

## Ten global checks

The evaluator adds checks for source count, operation count, case count,
positive coverage, control coverage, receipt count, receipt pass rate, family
coverage, four-case operation balance, and explicit context controls. All
receipts remain in the evaluation even when the expected aggregate state is
review.

## Runtime closure

The runtime contains typed depth and quality records and executes these stages:

1. fixture-loaded
2. sources-audited
3. schema-validated
4. plan-compiled
5. foundation-family-ready
6. beta-family-ready
7. alpha-family-ready
8. frontier-family-ready
9. cases-executed
10. review-routed
11. lineage-linked
12. ledger-closed
13. metrics-materialized
14. replay-closed
15. artifacts-materialized
16. bundle-closed
17. release-built
18. quality-gated
19. depth-accounted
20. controls-closed
21. compliance-closed
22. report-materialized
23. runtime-seeded
24. runtime-finalized

The accepted boolean requires audit, plan, evaluation, review, replay, quality,
recursive compliance, and published release. Stage records carry chained input
and output addresses so a reviewer can locate the first broken boundary.

## Depth and quality

The D11 depth report counts sources, operations, cases, positive and control
cases, families, checks, addresses, result states, and issue codes. Completion
is 100 percent only at 20 sources, 16 operations, 64 cases, four families, and
458 checks.

The quality gate checks audit, plan, evaluation, replay, release, artifact
safety, boundary, recursive compliance, result-state coverage, and control
issue vocabulary. The result and issue counts are calculated from delegate
executions, not from a hard-coded report.

## Public boundary

Compliance recursively walks every mapping and sequence inside every case
payload. It reports restricted keys and exact paths, then checks public source
flags and all source, operation, and case addresses. Delegate context retention
is also required. This prevents nested payload fields from bypassing the same
boundary applied to top-level fields.

## Schema invariants

Mapping validation checks required envelope fields, public boundary, exact
context, 20/16/64 cardinalities, contiguous ordinals, and four cases per
operation. Typed fixture validation repeats cardinality, four-family coverage,
source joins, operation joins, public source visibility, and aggregate case
context consistency before planning or evaluation.

## Checked-in runtime data

`data/causal-architecture-d11-runtime-closure.json` is generated from the
pinned public aggregate fixture. It contains the complete fixture projection,
audit, dependency plan, 64 executions, 64 receipts, all 458 checks, review
queue, ledger, artifacts, release, depth, quality, and 24 stages. It is a
replayable operational record rather than a hand-written example.

## Acceptance target

```text
sources=20 operations=16 cases=64 checks=458
ledger_events=80 artifacts=6 stages=24 quality_checks=10
compliance=True release=published runtime=True
```

Focused tests cover family results, issue tuples, schema, plan, review,
lineage, ledger, metrics, depth, quality, recursive compliance, replay,
reports, exports, CLI projections, and bundle contents.
