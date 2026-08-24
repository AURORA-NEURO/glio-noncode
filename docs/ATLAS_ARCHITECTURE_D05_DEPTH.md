# D05 Atlas Architecture Depth

## Boundary

D05 composes four public aggregate evidence families into one deterministic glioma regulatory atlas boundary. The family fixtures remain responsible for their own positive records and family calculations. D05 owns source joins, operation order, context policy, control handling, receipt normalization, review, lineage, validation, compliance, depth accounting, and release state.

```text
fixture: atlas-architecture-public-aggregate-v1
boundary: public_aggregate_glioma_regulatory_atlas
context: GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown
```

## Closure matrix

| Surface | Target | Observed | Closure rule |
| --- | ---: | ---: | --- |
| Public sources | 20 | 20 | source scope and public marker are explicit |
| Operations | 16 | 16 | each operation has family, plane, dependencies, and source joins |
| Cases | 64 | 64 | four scenarios per operation |
| Family tranches | 4 | 4 | regulatory, molecular, alpha evidence, and frontier |
| Evaluation checks | 458 | 458 | seven checks per case plus ten global checks |
| Validation cells | 80 | 80 | five planes by sixteen operations |
| Held controls | 48 | 48 | foreign, malformed, and identity controls remain in review |
| Ledger events | 64 | 64 | one linked event per case |
| Runtime stages | 24 | 24 | ordered closure from fixture load to final runtime |
| Release artifacts | 6 | 6 | fixture, evaluation, review, lineage, metrics, validation |
| Quality checks | 12 | 12 | cardinality, evaluation, plan, review, lineage, artifacts, runtime, release, checks, states, context, compliance |
| Result states | 6 | 6 | supported, accepted, published, out_of_domain, invalid, contradictory |

The depth percentage averages source count, operation count, case count, family count, and evaluation-check count. A complete D05 run reports `100.0`.

## Family map

| IDs | Family | Plane | Responsibility |
| --- | --- | --- | --- |
| C01-C04 | regulatory atlas | regulatory | cCRE tracks and cell or disease profiles |
| C05-C08 | molecular atlas | molecular | molecular state and histone harmonization |
| C09-C12 | alpha evidence | evidence | chromatin, methylation, role, and enhancer receipts |
| C13-C16 | frontier atlas | frontier | boundary, hotspot, tier, and snapshot receipts |

Every operation has one positive case and three controls. The positive case may delegate to a family adapter. Controls stop before delegation and carry one explicit issue code.

## Stage topology

The runtime stages are:

1. `fixture-loaded`
2. `sources-audited`
3. `plan-compiled`
4. `policy-scored`
5. `ingestion-closed`
6. `regulatory-family-ready`
7. `molecular-family-ready`
8. `alpha-evidence-family-ready`
9. `frontier-family-ready`
10. `cases-executed`
11. `review-routed`
12. `lineage-linked`
13. `metrics-materialized`
14. `validation-matrix-closed`
15. `schema-closed`
16. `artifacts-materialized`
17. `access-closed`
18. `replay-closed`
19. `depth-accounted`
20. `compliance-closed`
21. `release-gated`
22. `quality-gated`
23. `observability-closed`
24. `runtime-finalized`

Each stage carries one predecessor address, one output address, one ordinal, a state, a detail string, and a content address. A published runtime also requires accepted depth and compliance; release state alone is not sufficient.

## Evaluation depth

Each case retains seven checks:

1. aggregate state;
2. family result state;
3. exact issue tuple;
4. bounded count map;
5. addressed execution;
6. sanitized summary;
7. delegated context and foreign mismatch.

The ten global checks close receipt count, receipt identity, positive count, control count, receipt pass state, family coverage, source joins, operation balance, foreign controls, and result-state coverage.

The aggregate has 16 positive receipts and 48 review receipts. Expected controls are not failures: a control is correct when its held state, result state, issue code, empty count map, and output address all match the contract.

## Compliance depth

The compliance report walks every nested case payload and returns the exact path for a forbidden field. It verifies public source scope, explicit public aggregate markers, bounded aggregate or foreign contexts, delegated context keys, foreign controls that differ from delegated context, review state for every control, and content addresses for source, operation, and case declarations.

Positive summaries are sanitized before they are addressed and exported. The summary retains family, operation, aggregate context, delegated context, family result, issue tuple, and bounded counts while excluding raw payload markers.

## Verification

```powershell
python -m unittest tests.test_atlas_architecture tests.test_atlas_architecture_cli tests.test_atlas_architecture_exports tests.test_atlas_architecture_reporting
python -m glio_noncode atlas-architecture-fixture --output .artifacts/atlas-fixture.json
python -m glio_noncode atlas-architecture-runtime --input .artifacts/atlas-fixture.json --output .artifacts/atlas-runtime.json
python -m glio_noncode atlas-architecture-depth --input .artifacts/atlas-fixture.json --output .artifacts/atlas-depth.json
python -m glio_noncode atlas-architecture-compliance --input .artifacts/atlas-fixture.json --output .artifacts/atlas-compliance.json
python -m glio_noncode atlas-architecture-bundle --input .artifacts/atlas-fixture.json --output .artifacts/atlas-bundle
```

The accepted bundle contains `fixture.json`, `runtime.json`, `release.json`, and `report.json`. The release projection carries artifacts, release state, quality, depth, and compliance.
