# D10 Link-Graph Architecture Depth Build

## Purpose

D10 is the regulatory link-graph aggregate. It joins public graph evidence for
regulatory elements, genes, contacts, perturbations, quantitative trait links,
and release ranking into a typed, deterministic, review-gated surface. It
retains partial, contradictory, missing, foreign-context, and publication
control paths as evidence states rather than hiding them behind a positive-only
view.

This build raises D10 from six checks per case and eight global checks to the
full seven-plus-ten closure contract. It also adds depth and quality records to
the runtime, validates the schema before execution, recursively scans public
payloads, materializes report and compliance stages, and checks the complete
runtime in a deterministic closure projection.

## Inventory

| Record | Count | Contract |
| --- | ---: | --- |
| Public source receipts | 19 | four graph-family registries |
| Ordered operations | 16 | four per family |
| Positive cases | 16 | one per operation |
| Control cases | 48 | three per operation |
| Cases | 64 | exact four-scenario matrix |
| Per-case checks | 448 | seven per case |
| Global checks | 10 | cardinality, balance, receipt, context |
| Evaluation checks | 458 | `64 * 7 + 10` |
| Ledger events | 80 | case and release lifecycle |
| Artifacts | 6 | public and review-safe |
| Runtime stages | 24 | chained and addressed |
| Quality checks | 10 | release and control gates |

## Four graph families

### Foundation family

The foundation family joins overlap, nearest-gene, cCRE, and consensus link
operations. It retains source and context receipt identity for the base graph
and keeps insufficient evidence, missing overlap, and foreign-context paths in
review.

### Beta activity family

The beta family joins activity, coaccessibility, QTL, and allele-aware link
operations. It preserves partial graph states and missing-evidence controls
without treating a single link as a complete regulatory relationship.

### Alpha perturbation family

The alpha family joins perturbation, contact, tethering, and graph consistency
operations. It retains contradictory evidence and unsupported context states so
graph reconciliation can be reviewed before any release projection.

### Frontier release family

The frontier family joins correction, ranking, calibration, and publication
operations. It keeps publication-context mismatch and calibration controls
visible, and a release does not become accepted merely because a rank exists.

## Receipt checks

Each case receives seven checks:

1. aggregate state matches the positive or review scenario;
2. delegate result state is retained;
3. issue tuple is retained exactly;
4. delegate count summary is retained;
5. public source receipt is attached;
6. delegate context equals aggregate context or `context_mismatch` is explicit;
7. receipt and output address are closed.

The context check makes a foreign-context link path inspectable independently of
its review state. The result state remains distinct from the aggregate state so
partial graph evidence cannot be confused with an accepted aggregate path.

## Global closure

Ten global checks close source, operation, and case cardinality; positive and
control balance; receipt count and pass status; four-family coverage; four
cases per operation; and explicit context controls. All 64 case receipts stay
in the evaluation, including held and contradictory paths.

## Runtime stages

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

Every stage contains an input address, output address, detail, check identifier,
and content address. Runtime acceptance requires schema, evaluation, replay,
quality, compliance, artifact, review, and published release closure.

## Depth and quality

The depth report counts sources, operations, cases, positive and control cases,
families, evaluation checks, addresses, result states, and issue codes. Its
completion target is 19 sources, 16 operations, 64 cases, four families, and
458 checks.

The quality gate checks audit, plan, evaluation, replay, release, artifact
safety, public boundary, recursive compliance, result-state coverage, and issue
control coverage. State and issue metrics are calculated from executions so a
shrinking control vocabulary is detectable.

## Public compliance

The compliance walk recursively inspects maps and sequences within every case
payload. It returns restricted keys and exact paths, and separately checks
public source flags, source/operation/case addresses, and delegate context
retention. The D10 boundary remains `public_aggregate_non_patient`.

## Schema invariants

Mapping validation checks envelope fields, boundary and context, exact 19/16/64
cardinalities, contiguous operation ordinals, and four cases per operation.
Typed validation repeats cardinality, four-family coverage, source joins,
operation joins, public source visibility, and case-context consistency before
planning or evaluation.

## Checked-in closure data

`data/link-graph-architecture-d10-runtime-closure.json` contains the complete
deterministic runtime projection: fixture, audit, plan, executions, receipts,
458 checks, review queue, ledger, six artifacts, release, depth, quality, and
24 stages. It is generated from the pinned public aggregate fixture and can be
replayed during review.

## Acceptance target

```text
sources=19 operations=16 cases=64 checks=458
ledger_events=80 artifacts=6 stages=24 quality_checks=10
compliance=True release=published runtime=True
```
