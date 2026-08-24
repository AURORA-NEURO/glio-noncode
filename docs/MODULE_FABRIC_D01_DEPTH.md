# D01 Cross-cutting module-fabric depth

Status: implemented, deterministic, and release-gated.

The module fabric is the repository-wide integration boundary. It verifies
that the product ledger's declared implementation and test surfaces resolve,
that all sixteen domains remain represented, and that positive and control
rows retain distinct states. It is a release integration receipt, not a
scientific result.

## Closed denominators

| Quantity | Value | Contract |
| --- | ---: | --- |
| capability catalog rows | 256 | 16 domain rows × 16 ordered capabilities |
| domains | 16 | D01 through D16 |
| fixture records | 32 | one positive and one control per domain |
| public source receipts | 5 | HTTPS aggregate sources |
| record checks | 384 | 12 independently addressed checks per record |
| global checks | 10 | fixture-level conservation and closure checks |
| evaluation checks | 394 | 384 record checks + 10 global checks |
| runtime stages | 24 | integration, assurance, and release stages |
| quality checks | 20 | independent quality gate assertions |
| depth checks | 30 | catalog, fixture, reference, metrics, and release checks |
| compliance checks | 12 | public projection and release-boundary checks |
| release artifacts | 8 | fixture, audit, evaluation, metrics, depth, lineage, replay, quality |

The exact closure is recorded in
`data/module-fabric-d01-runtime-closure.json`. The closure includes the
fixture, evaluation, runtime, compliance, depth, quality, lineage, replay,
schema, catalog, source registry, operation ledger, recovery report, and
stable projections.

## Boundary

The fixture context is:

```text
GRCh38|glioma|adult|stem_like|tumor_core|pre_treatment
```

The control context is a tumor-margin, post-treatment context. It is retained
to test domain and context boundaries. A control with valid imports is still a
control; importability is not permission to promote it.

The fixture contains public aggregate module references. It does not copy raw
domain payloads into the operation output. Execution receipts retain counts,
states, issue codes, declared module paths, and content addresses.

## Twelve checks per record

The evaluator retains the original eight checks and adds four conservation
checks:

1. state matches the declared role expectation;
2. expected issue codes remain visible;
3. role cannot promote a control;
4. domain identity is retained;
5. implementation references resolve;
6. test references resolve;
7. output contains no private keys;
8. execution receipt is addressed;
9. source joins resolve to the five-source registry;
10. reference counts equal receipt cardinalities;
11. public record and capability identity are retained;
12. every reference receipt is addressed.

The check ID includes the record ID and check name. This makes a failure
addressable without requiring a consumer to diff the entire evaluation.

## Ten global checks

The fixture-level checks use `__fixture__` as their record ID and confirm:

- fixture identity is non-empty;
- all 32 records execute;
- the 394-check denominator is closed;
- execution IDs are unique;
- all fixture domains execute;
- the positive/control role balance is 16/16;
- observed accepted/review states conserve that balance;
- every declared reference resolves;
- all execution outputs remain aggregate-only; and
- all execution receipts are addressed.

## Reference resolution

Each ledger declaration is resolved as either an implementation reference or
a test reference. Resolution retains the original declaration, reference kind,
module name, optional symbol name, state, bounded detail, and an address. A
resolved reference proves importability of the declared surface. It does not
prove scientific validity, calibration, causal validity, or clinical
suitability.

The D01 depth audit verifies:

- all 256 ledger rows declare implementation modules;
- all 256 ledger rows declare test modules;
- all declared references resolve;
- the fixture has 32 rows and 16 domains;
- role and state counts conserve the fixture;
- source and execution addresses are present; and
- the expanded evaluation denominator remains 394.

## Runtime stages

| # | Stage | Evidence |
| ---: | --- | --- |
| 1 | fixture loaded | fixture receipt is addressed |
| 2 | public boundary audited | source, scope, and record checks pass |
| 3 | catalog snapshotted | 256-row ledger projection is retained |
| 4 | domain denominator closed | all 16 domains are present |
| 5 | capability denominator closed | all 256 capabilities are present |
| 6 | positive controls indexed | 16/16 role balance is visible |
| 7 | references resolved | implementation and test receipts resolve |
| 8 | fixture evaluated | all 32 records execute |
| 9 | metrics conserved | roles, states, domains, and references conserve |
| 10 | depth audited | the 30-check depth report passes |
| 11 | lineage closed | fixture-to-reference graph has no orphans |
| 12 | replay verified | repeated evaluation is deterministic |
| 13 | quality gated | 20 quality checks pass |
| 14 | release materialized | eight release artifacts are present |
| 15 | manifest serialized | only release metadata is projected |
| 16 | source joins retained | record source joins remain visible |
| 17 | control boundaries retained | control rows remain review |
| 18 | public projection sanitized | bounded aggregate fields are emitted |
| 19 | runtime receipt addressed | stage inputs and outputs are addressed |
| 20 | release decision | quality and release gates agree |
| 21 | evaluation checks closed | all 394 evaluation checks pass |
| 22 | compliance closed | 12 compliance checks pass |
| 23 | observability closed | every stage has a traceable address |
| 24 | runtime finalized | final state is accepted |

## Compliance

The compliance function walks the exact runtime projection and records paths,
not values, when a private field or disallowed metadata key is found. The
public boundary also checks HTTPS sources, canonical context, role/state
partitioning, reference resolution, release blockers, and stage addresses.

A compliance failure moves the runtime to review. It is not swallowed by a
quality summary and it is not repaired by changing the reported state.

## Release artifacts

| Artifact | Content |
| --- | --- |
| `fixture` | public aggregate fixture address |
| `data-audit` | source, role, context, and address checks |
| `evaluation` | 32 executions and 394 checks |
| `metrics` | conserved domain, role, state, and reference counts |
| `depth` | full catalog and fixture coverage audit |
| `lineage` | fixture-to-record-to-reference graph |
| `replay` | deterministic replay comparison |
| `quality` | combined assurance gate |

All artifacts are addressed. The release manifest retains blockers as a tuple;
an accepted release must have no blockers.

## Operational projections

`module-fabric-review-csv` emits one row per fixture record for review. It does
not promote controls. `module-fabric-checks-csv` emits one row per evaluation
check and therefore has 395 lines including its header. The JSON runtime
projection includes the compliance report and the 24-stage ledger.

The runtime report includes stage count, evaluation-check count,
compliance-check count, reference failures, review queue count, schema issues,
and addresses for evaluation, depth, quality, release, trace, and dictionary
projections.

## Failure modes

| Failure | State | Required action |
| --- | --- | --- |
| unknown capability | review | repair the catalog join |
| domain mismatch | review | repair capability/domain identity |
| missing implementation declaration | review | add a declared implementation surface |
| missing test declaration | review | add a test surface before promotion |
| import failure | review | fix the declared reference or keep it held |
| context mismatch | review | compare against the exact mission context |
| control boundary missing | review | preserve the control instead of promoting it |
| private projection key | review | remove it at the public boundary |
| ledger discontinuity | review | rebuild from the last valid address |
| replay mismatch | review | inspect changed input or serialization |
| release blocker | review | resolve the named assurance failure |

Negative controls are intentionally not converted into accepted outcomes by
fallback logic. A successful import is not evidence that a control belongs in
the canonical domain or context.

## Verification commands

```powershell
python -m glio_noncode module-fabric-data-audit
python -m glio_noncode module-fabric-evaluate
python -m glio_noncode module-fabric-compliance
python -m glio_noncode module-fabric-depth
python -m glio_noncode module-fabric-quality
python -m glio_noncode module-fabric-runtime
python -m glio_noncode module-fabric-checks-csv
python -m glio_noncode module-fabric-report --format markdown
```

Expected canonical values are: accepted runtime, 32 executions, 394
evaluation checks, 24 stages, 12 compliance checks, 20 quality checks, 30
depth checks, and 395 CSV lines.

## Extension rules

Adding a domain capability requires a catalog row, implementation references,
test references, a public fixture record, positive/control behavior, source
joins, metrics, lineage, scenario cells, release evidence, and closure data.
Changing a denominator without changing every dependent receipt is an
incomplete integration change.

The module fabric must stay narrower than scientific inference. Its job is to
make integration claims inspectable, reproducible, and conservative. Domain
modules remain responsible for their own biological and experimental
contracts.
