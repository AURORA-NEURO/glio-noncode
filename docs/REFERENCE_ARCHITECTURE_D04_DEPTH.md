# D04 reference architecture depth

This document defines the measurable completion contract for the public aggregate reference boundary. Depth is not a line-count claim. It is the set of independently inspectable joins that must remain closed from source receipt through release projection.

## Completion targets

| Dimension | Target | Default observed |
| --- | ---: | ---: |
| public source receipts | 20 | 20 |
| operation specifications | 16 | 16 |
| adapter families | 4 | 4 |
| case contracts | 64 | 64 |
| positive cases | 16 | 16 |
| held controls | 48 | 48 |
| case and global evaluation checks | 458 | 458 |
| distinct result states | 6 | 6 |
| validation cells | 80 | 80 |
| lineage events | 64 | 64 |
| release artifacts | 6 | 6 |
| runtime stages | 24 | 24 |
| quality checks | 12 | 12 |
| compliance checks | 8 | 8 |

The depth score averages capped ratios for sources, operations, cases, families, and evaluation checks. The closed default fixture therefore returns `100.0`. A larger fixture cannot inflate the score above the declared contract, while a partial build remains visible as a lower score.

## Four-family coverage

The operation set is intentionally balanced:

1. Coordinate operations establish assembly, chain, ambiguity, and pangenome relationships.
2. Annotation operations resolve transcript and ontology catalog relationships.
3. Governance operations close nomenclature, frequency, snapshot, and license boundaries.
4. Release operations close provenance, drift, bundle, and final publication checks.

The global family check derives family coverage from operation specifications rather than from a hard-coded receipt label. This catches an operation that is present in the case table but disconnected from its typed family.

## Evaluation depth

Each of the 64 cases produces seven checks:

- architecture state;
- delegated family result state;
- issue-code equality;
- bounded count equality;
- output content address;
- sanitized summary boundary;
- delegated context retention.

Ten global checks then close receipt count, receipt identity, positive count, control count, receipt acceptance, family coverage, source joins, four-case operation balance, foreign-context controls, and result-state coverage. This gives `64 × 7 + 10 = 458` checks.

The receipt retains expected and observed values, but the execution summary removes raw payload-shaped fields before it is exported. This keeps the report useful for review and replay without turning the receipt into a second payload store.

## Context depth

Every case has both `context_key` and `delegate_context_key`. Positive cases use the exact D04 context for both fields. Foreign-context controls retain their foreign case context while delegating against the D04 reference context. The distinction lets the evaluator demonstrate that the boundary held the case before family dispatch.

Malformed and identity controls remain in the exact reference context. Their issue codes prove that scope, shape, and contradictory identity policies are distinct decisions rather than one generic failure path.

## Release closure

The 24-stage runtime adds explicit depth, compliance, quality, observability, and finalization stages after replay. The runtime state is published only when all of the following are accepted:

- data audit, plan, policy, and evaluation;
- validation matrix and interchange schema;
- review queue and lineage ledger;
- six content-addressed artifacts and access policy;
- replay, invariants, runbook, failures, and observations;
- depth targets and public aggregate compliance;
- the twelve-check quality gate;
- the release manifest.

The `ReferenceArchitectureDepthReport` records source, operation, case, family, check, state, issue-code, artifact, stage, and addressed-object counts. The `ReferenceArchitectureMetrics` projection records the same important dimensions in a compact operational form.

## Report projections

The deterministic report contains four sections:

- public reference sources;
- operation specifications;
- held-control review items;
- release artifacts.

JSON preserves the complete section rows. Markdown is intended for human inspection. Receipt CSV is one row per case plus a header; review CSV is one row per held control plus a header. All three use stable ordering from the runtime.

## Verification commands

```powershell
python -m glio_noncode reference-architecture-depth --input examples/reference-architecture-public-aggregate.json --output .\out\depth.json
python -m glio_noncode reference-architecture-compliance --input examples/reference-architecture-public-aggregate.json --output .\out\compliance.json
python -m glio_noncode reference-architecture-report --input examples/reference-architecture-public-aggregate.json --output .\out\report.json
python -m glio_noncode reference-architecture-bundle --input examples/reference-architecture-public-aggregate.json --output .\out\bundle
```

The bundle contains `runtime.json`, `release.json`, `fixture.json`, `report.json`, `report.md`, `receipts.csv`, `review.csv`, `compliance.json`, and `depth.json`. These projections are derived from the same run and can be compared by content address.
