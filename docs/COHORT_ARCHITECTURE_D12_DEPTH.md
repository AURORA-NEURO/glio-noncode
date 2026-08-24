# D12 Cohort Discovery Architecture Depth Build

## Why this build exists

D12 is the cohort discovery and longitudinal aggregate surface. The original
implementation already joined four public cohort families, but its runtime had
22 stages and its evaluator exposed 392 checks. This build closes the same
depth contract used by the later evidence, workbench, and platform modules:
seven checks per case, ten global checks, explicit schema and compliance
stages, depth and quality records on the runtime, and a deterministic closure
projection.

The result remains descriptive public aggregate research infrastructure. It
does not identify a person, make a clinical decision, establish efficacy, or
replace external validation. Controls remain first-class records so absence,
context mismatch, parity gaps, privacy floors, and invalid discovery inputs are
visible rather than converted into positive results.

## Closed inventory

| Record | Count | Closure |
| --- | ---: | --- |
| Public source receipts | 22 | four family registries |
| Operation contracts | 16 | four per family |
| Positive cases | 16 | one per operation |
| Control cases | 48 | three per operation |
| Total cases | 64 | exact four-case matrix |
| Per-case checks | 448 | seven per case |
| Global checks | 10 | fixture and cross-plane invariants |
| Evaluation checks | 458 | accepted receipts and joins |
| Ledger events | 80 | append-only case lifecycle |
| Review-safe artifacts | 6 | public and review projections |
| Runtime stages | 24 | accepted in order |
| Quality checks | 12 | release, compliance, and control surface |

The arithmetic is explicit: `64 * 7 + 10 = 458`. The ledger remains at 80
events because it represents the 64 case receipts plus the surrounding
fixture, plan, review, metrics, replay, artifact, release, and close events.

## Four family boundaries

### Foundation family

The foundation family covers cohort query, background rate, sequence control,
and chromatin control. It retains the baseline context
`GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment` and preserves controls
for excluded records, empty selections, missing callable intervals, and context
mismatch.

### Beta family

The beta family covers regulatory recurrence, regional burden, functional
convergence, and pathway or regulon convergence. It retains the same baseline
context and keeps negative controls, incomplete controls, contradictory
controls, and context mismatch as typed outcomes.

### Alpha family

The alpha family covers clonality timing, primary recurrence, treatment
selection, and cross-cohort replication. It retains review states and explicit
controls for empty inputs, incomplete evidence, parity gaps, and context
mismatch.

### Frontier family

The frontier family covers subgroup fairness, transportability, federated
summary, and cohort discovery. Its context is
`GRCh38|glioma|adult|stem_like|core|unknown`, and it retains fairness, shift,
privacy, federated-input, and discovery-input controls.

## Seven checks per case

Every case receipt closes these checks:

1. State: the delegate state equals the aggregate expected state.
2. Issues: the full ordered issue tuple is retained.
3. Counts: source, payload, and row accounting is reproducible.
4. Operation: the case points to a declared operation contract.
5. Sources: every case source address resolves in the source registry.
6. Context: the delegate context equals its family context, or a declared
   `context_mismatch` issue makes the exception explicit.
7. Receipt: the output is addressed and the expected-versus-observed receipt
   passes.

The context check is important because a state such as `out_of_domain` is not
enough by itself to prove why a case was held. The receipt now retains the
delegate context and the family context used for comparison.

## Ten global checks

The evaluator adds ten checks after case-level checks:

- all 64 cases execute;
- all 16 positive cases remain represented;
- control scenarios remain balanced at 16 each;
- four family counts remain balanced at 16 each;
- every operation owns four cases;
- all case source references resolve;
- every execution has an explicit state;
- every execution has an output address;
- every case has a corresponding execution receipt;
- context exceptions are explicit and limited to `context_mismatch` controls.

This gives the release gate a complete view of both semantic results and
structural closure.

## Typed runtime additions

The D12 runtime now includes:

- `depth`: source, operation, case, family, check, address, state, and issue
  counts;
- `quality`: twelve release, lineage, compliance, state-vocabulary, and
  control-surface checks;
- schema validation before planning and evaluation;
- recursive payload compliance scanning;
- report, runtime seed, and runtime final addresses;
- a 24-stage ordered runtime record.

The runtime is accepted only when audit, plan, evaluation, review, replay,
quality, compliance, and publication all close. The release record remains
published only when all six artifacts are available and the evaluation is
accepted.

## 24-stage sequence

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

Each stage has an input address, output address, check identifier, detail, and
content address. The stage chain is therefore inspectable without reconstructing
the runtime from console output.

## Recursive public-boundary scan

The compliance surface walks mappings and sequences inside every case payload.
It rejects restricted identity, decision, attribution, and syntax metadata
keys at any depth. It reports both the unique forbidden keys and their exact
payload paths. Public source flags, source addresses, operation addresses, case
addresses, and retained delegate contexts are checked in the same report.

## Schema closure

Mapping validation now checks required fields, exact counts, boundary and
context values, family-context cardinality, contiguous operation ordinals, and
four cases per operation. Typed fixture validation repeats the cardinality,
join, source visibility, context, and balance checks before runtime execution.

This prevents a syntactically valid JSON file with missing family rows or
forward operation references from reaching the release gate.

## Checked-in closure projection

`data/cohort-architecture-d12-runtime-closure.json` is a deterministic runtime
projection generated from the pinned public aggregate fixture. It contains the
fixture, audit, plan, 64 executions, 64 receipts, all 458 checks, review queue,
ledger, six artifacts, published release, depth report, quality gate, and all
24 stages. Its content addresses can be regenerated and compared during review.

## Verification targets

The accepted D12 result is:

```text
sources=22 operations=16 cases=64 checks=458
ledger_events=80 artifacts=6 stages=24 quality_checks=12
compliance=True release=published runtime=True
```

Focused tests cover fixture cardinality, family states, control issue tuples,
plan, review, lineage, ledger, metrics, depth, quality, release, schema,
compliance, replay, reports, exports, CLI projections, and bundle contents.
