# D09 topology architecture depth

## Purpose

This document records the deeper D09 release contract for three-dimensional
genome and regulatory topology. The surface is a public aggregate research
boundary. It retains typed observations, source receipts, context joins, and
review states without making clinical or treatment claims.

The depth target is explicit:

| Dimension | Required | Meaning |
| --- | ---: | --- |
| public source receipts | 17 | every source is addressable and marked public aggregate |
| ordered operations | 16 | C01-C16 are contiguous and dependency-addressed |
| aggregate cases | 64 | one positive and three controls per operation |
| family planes | 4 | context, beta, alpha, and frontier tranches |
| evaluation checks | 458 | seven checks per case plus ten global checks |
| runtime stages | 24 | every output boundary has an ordered receipt |
| release artifacts | 6 | fixture, audit, evaluation, review, ledger, and source registry |
| quality checks | 12 | audit, plan, evaluation, replay, artifacts, metrics, lineage, release, ledger, compliance, state, and control gates |

The checked-in runtime closure is
`data/topology-architecture-d09-runtime-closure.json`. It is generated from
`data/topology-architecture-public-aggregate.json` and must remain accepted,
published, and deterministic.

## Four family planes

### Context quality: C01-C04

The context tranche handles contact import, matrix quality, boundary ensemble
calls, and insulation deltas. Its output is descriptive topology evidence. The
aggregate keeps the declared assembly, disease, age, developmental state,
territory, and unresolved dimension in the context key.

### Beta contact inference: C05-C08

The beta tranche retains loop or stripe evidence, promoter capture,
enhancer-promoter contact, and activity-by-contact observations. It does not
convert a contact score into a causal claim. It preserves source versions,
contact identifiers, measurement summaries, and issue codes supplied by the
family receipt.

### Alpha structural reasoning: C09-C12

The alpha tranche covers boundary motifs, CTCF/cohesin support, IDH-conditioned
insulation, and declared structural-variant rewiring. Structural rewiring is a
bounded declared observation or simulation receipt. It is not a prediction of
an unseen rearrangement.

### Frontier release: C13-C16

The frontier tranche retains ecDNA contact, compartment switching, uncertainty
transport, and publication receipts. Each path remains tied to its source IDs,
family record ID, family context, aggregate context, and content addresses.

## Case accounting

Every operation owns four cases:

1. `positive` delegates one public family observation and expects `accepted`.
2. `foreign_context` changes the aggregate context and expects `review`,
   `out_of_domain`, and `context_mismatch`.
3. `malformed_input` carries an invalid input marker and expects `review`,
   `invalid`, and `malformed_input`.
4. `identity_conflict` carries an identity conflict marker and expects
   `review`, `contradictory`, and `identity_conflict`.

The case receipt compares:

- aggregate execution state;
- family result state;
- exact issue-code tuple;
- primary and secondary count summary;
- source receipt presence;
- retained delegated context;
- receipt address and output address.

The ten global checks additionally verify source, operation, case, positive,
control, receipt, address, family, operation balance, and context-control
closure. The evaluator therefore cannot pass by checking only the positive
rows.

## Context transport

The D09 aggregate context is the run boundary. Family records may use a more
specific context key, and that delegated key is retained in every case. A
positive path may transport the family context as part of a valid join. A
foreign aggregate context must be held before delegation and must expose
`context_mismatch`. Malformed and identity controls retain their delegated
context while being held for their own reason code.

This distinction prevents a valid context transport from being mistaken for a
foreign-context failure and prevents a foreign context from disappearing into
a generic review state.

## Schema and invariants

`validate_topology_architecture_mapping` checks the envelope boundary,
cardinality, contiguous ordinals, and four-case balance. The typed fixture
validator additionally checks:

- unique source, operation, and case IDs;
- source joins for operations and cases;
- operation joins for every case;
- all four family values;
- explicit public source visibility;
- non-empty delegated context keys;
- explicit foreign-context control issue codes.

All content addresses are derived from canonical JSON. A changed source,
operation, case, evaluation, or runtime stage therefore changes its address and
causes replay or release comparisons to fail visibly.

## Compliance boundary

Compliance walks nested payload maps and sequences rather than checking only
top-level keys. It rejects restricted identity and decision fields, requires
the public aggregate boundary, requires public source flags, requires source,
operation, and case addresses, and requires delegate-context retention. The
result contains both offending keys and their nested paths for remediation.

The runtime accepts only when compliance is accepted. A sanitized artifact is
not enough if the source or context boundary is not explicit.

## Metrics and quality

Metrics expose source, operation, case, positive, control, family, plane,
scenario, result-state, issue-code, and evaluation-check counts. The metric
invariant function requires 17 sources, 16 operations, 64 cases, 16 positive
cases, 48 controls, and 458 evaluator checks.

The twelve quality checks are:

1. data audit;
2. dependency plan;
3. evaluation acceptance;
4. deterministic replay;
5. artifact safety;
6. metric invariants;
7. lineage gaps;
8. published release;
9. ledger closure;
10. recursive compliance;
11. four-state result coverage;
12. three-code control-surface coverage.

Each check has an address, observed value, required value, kind, and detail.
The release state is published only after every quality check passes.

## Runtime stage receipt

The 24 stages are:

1. fixture-loaded
2. sources-audited
3. schema-validated
4. plan-compiled
5. context-family-ready
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

Each stage has an ordinal, state, input addresses, output address, stage check
ID, detail, and content address. The final runtime address covers the fixture,
evaluation, release, quality result, and all stage receipts.

## Verification target

The D09 focused suite covers the aggregate contracts, export surface, CLI,
reporting, mutation behavior, replay, compliance, and release projections.
The command matrix must produce accepted outputs for fixture, audit, plan,
evaluation, runtime, quality, depth, replay, scenarios, sources, compliance,
validation, query, report, and bundle commands.

The bundle must contain `fixture.json`, `runtime.json`, `release.json`, and
`report.json`. The runtime must report 458 checks, 24 stages, 458 depth checks,
12 quality checks, and a published release.
