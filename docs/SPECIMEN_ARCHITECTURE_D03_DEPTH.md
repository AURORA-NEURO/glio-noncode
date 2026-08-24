# D03 specimen architecture depth

This document defines the measurable completion contract for the public
aggregate specimen boundary. Depth is the set of independently inspectable
joins from source receipt through adapter execution, review, lineage, and
publication.

## Completion targets

| Dimension | Target | Default observed |
| --- | ---: | ---: |
| public source receipts | 15 | 15 |
| operation specifications | 16 | 16 |
| adapter families | 4 | 4 |
| case contracts | 64 | 64 |
| positive cases | 16 | 16 |
| held controls | 48 | 48 |
| evaluation checks | 458 | 458 |
| distinct result states | 6 | 6 |
| validation cells | 112 | 112 |
| lineage events | 64 | 64 |
| release artifacts | 6 | 6 |
| runtime stages | 24 | 24 |
| quality checks | 12 | 12 |
| compliance checks | 8 | 8 |

The depth score averages capped ratios for sources, operations, cases, adapter
families, and evaluation checks. The closed default fixture returns `100.0`.
Additional rows cannot inflate the score above the declared contract, while a
partial build remains visible as a lower score.

## Four adapter families

1. Core specimen context operations resolve ontology, matched-normal, purity,
   ploidy, and sample-integrity receipts.
2. Beta frontier operations classify specimen origin, mosaicism, cancer-cell
   fraction, and subclone summaries.
3. Lineage operations connect regions, longitudinal observations, phase, and
   treatment context.
4. Preanalytic operations close quality, assay lineage, identity adjudication,
   and context-envelope receipts.

The family check derives coverage from operation specifications and receipt
joins. It catches an operation that exists in the case table but is detached
from its declared typed family.

## Evaluation depth

Every one of the 64 cases contributes seven checks:

- architecture state;
- typed adapter result state;
- issue-code equality;
- bounded count equality;
- output content address;
- sanitized summary boundary;
- delegated context retention.

Ten global checks then close receipt count, receipt identity, positive count,
control count, receipt acceptance, family coverage, source joins, four-case
operation balance, foreign-context controls, and result-state coverage. The
result is `64 x 7 + 10 = 458` checks.

The execution summary removes payload-shaped keys before it enters a receipt.
This preserves deterministic review and replay projections without making a
receipt a second payload store.

## Context depth

Positive cases use the exact D03 context for both `context_key` and
`delegate_context_key`. Foreign-context controls retain the GRCh37 case context
while delegating against the D03 reference context. This makes pre-dispatch
scope handling observable. Malformed and identity controls remain in the exact
D03 context so shape and contradictory-identity policy are distinct decisions.

## Release closure

The runtime adds explicit depth, compliance, quality, observability, and final
stages after replay. Publication requires accepted data audit, plan, policy,
evaluation, validation matrix, schema, review queue, lineage, six artifacts,
access, replay, invariants, runbook, observations, compliance, depth, quality,
and release checks.

`SpecimenArchitectureDepthReport` records source, operation, case, family,
check, state, issue-code, artifact, stage, and addressed-object counts.
`SpecimenArchitectureMetrics` records the same operational dimensions in a
compact projection for reports and release artifacts.

## Report projections

The deterministic report contains four sections: public sources, operation
specifications, held controls, and release artifacts. JSON preserves complete
section rows. Markdown is intended for inspection. Receipt CSV contains one
row per case plus a header; review CSV contains one row per held control plus a
header. All outputs use the runtime's stable ordering.

## Verification commands

```powershell
python -m glio_noncode specimen-architecture-depth --input examples/specimen-architecture-public-aggregate.json --output .\out\depth.json
python -m glio_noncode specimen-architecture-compliance --input examples/specimen-architecture-public-aggregate.json --output .\out\compliance.json
python -m glio_noncode specimen-architecture-report --input examples/specimen-architecture-public-aggregate.json --output .\out\report.json
python -m glio_noncode specimen-architecture-bundle --input examples/specimen-architecture-public-aggregate.json --output .\out\bundle
```

The bundle contains runtime, release, fixture, report JSON and Markdown,
receipt CSV, review CSV, compliance JSON, and depth JSON projections derived
from the same run.
