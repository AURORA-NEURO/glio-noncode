# D07 Chromatin Architecture Depth Build

## Scope

D07 is the aggregate chromatin, accessibility, methylation, chromatin-state,
and cross-assay evidence module. It composes four public tranches while
preserving their family boundaries, source joins, context keys, uncertainty,
and control outcomes. The module is a complete executable surface: its fixture
can be generated locally, its cases can be evaluated, its outputs can be
replayed, and its release can be inspected without network access.

## Fixed depth targets

The depth report measures five independent dimensions:

| Dimension | Target | Closure meaning |
| --- | ---: | --- |
| public sources | 19 | all four source registries are represented and marked public aggregate |
| operations | 16 | C01-C16 have ordered contracts and source joins |
| cases | 64 | every operation has one positive and three controls |
| families | 4 | context, methylation, alpha chromatin, and cross-assay tranches are present |
| checks | 458 | seven checks per case plus ten global checks pass |

`chromatin_architecture_depth_percent` reports the minimum ratio across those
five dimensions. A complete D07 build reports 100.0 percent, 19 sources, 16
operations, 64 cases, four families, and 458 checks. The depth record also
reports addressed object count, plane distribution, six result states, and the
number of distinct issue codes observed by the execution surface.

## Four family tranches

### Context accessibility: C01-C04

This tranche covers track retrieval, accessibility delta, histone context, and
H3K27ac activity. The aggregate stores a family record identifier and a
sanitized family summary. Positive execution delegates to the matching family
receipt. Foreign, malformed, and identity controls stop before delegation.

### Methylation: C05-C08

This tranche covers methylation context retrieval, CpG creation/loss,
methylation-sensitive motif behavior, and IDH hypermethylation context. The
adapter receipt remains attached to its source tranche while the aggregate case
uses the exact D07 routing context.

### Chromatin state: C09-C12

This tranche covers state segmentation, allele-specific chromatin, epigenomic
purity, and batch/composition correction. The aggregate records the result state
and issue tuple without copying raw family input into review summaries.

### Cross-assay release: C13-C16

This tranche runs direct typed primitives:

- context imputation keeps observed values separate from prior-filled values and
  retains confidence;
- assay coverage requires a declared support set before interpretation;
- cross-assay concordance reports direction agreement and a bounded score;
- publication requires exact context, feature identifiers, and assay IDs.

C16 is the only positive path that emits `published`. C13-C15 emit accepted
descriptive receipts. None of these paths establishes a clinical, causal, or
treatment conclusion.

## Contract closure

Sources now carry both `scope=public_aggregate` and
`public_aggregate=true`. The boolean is independently checked so a source
cannot enter the fixture by matching only a free-form scope label.

Cases carry both `context_key` and `delegate_context_key`. The routing context
is the D07 boundary. The delegated key records the exact family context used by
the positive receipt or retained by a held control. This makes context handling
auditable when a family receipt is narrower than the aggregate boundary.

Typed validation closes:

1. exact source, operation, and case cardinality;
2. contiguous operation ordinals;
3. all four family values;
4. four cases per operation;
5. source joins from operations and cases;
6. operation joins from cases;
7. allowed routing contexts;
8. explicit public source markers;
9. non-empty delegated contexts;
10. explicit `context_mismatch` on foreign controls;
11. content addresses on every contract object.

## Seven checks per case

Each case is checked through seven independent views:

1. aggregate execution state;
2. family or release result state;
3. exact issue tuple;
4. bounded primary and secondary counts;
5. receipt address;
6. sanitized summary;
7. delegated context retention.

The case surface contributes 448 checks. Ten global checks close receipt count,
positive count, control count, pass count, operation coverage, family coverage,
aggregate context, control policy, operation balance, and context-control
behavior. The complete accounting is:

```text
64 cases * 7 checks = 448
10 global checks    = 10
total               = 458
```

## Quality gate

The quality gate contains 14 direct decisions over the composed surfaces:

| Surface | Required result |
| --- | --- |
| data audit | accepted |
| dependency plan | accepted |
| case evaluation | accepted |
| policy | 16 accepted and 48 review decisions |
| review queue | 48 held items |
| lineage | all source-to-receipt links close |
| schema | 33 declared fields and 12 schema checks pass |
| replay | evaluation and receipt addresses are stable |
| invariants | all cross-surface checks pass |
| metrics | 64 receipts, 458 checks, six result states, issue coverage |
| failure report | expected controls remain classified and non-blocking to the positive release |
| release | published |
| artifact floor | six artifacts |
| compliance | public boundary and payload rules pass |

The quality gate intentionally keeps policy, review, schema, failure, and
compliance as separate decisions. A passing receipt does not erase a review
control, and a published release does not imply that every case is a positive
finding.

## Runtime closure

The D07 runtime contains 24 addressed stages:

1. fixture loaded;
2. sources audited;
3. plan compiled;
4. accessibility family ready;
5. methylation family ready;
6. chromatin-state family ready;
7. cross-assay family ready;
8. cases executed;
9. controls routed;
10. lineage linked;
11. ledger closed;
12. metrics materialized;
13. schema closed;
14. invariants closed;
15. replay closed;
16. artifacts materialized;
17. depth accounted;
18. policy closed;
19. quality gated;
20. release built;
21. access closed;
22. compliance closed;
23. observability closed;
24. runtime finalized.

Every stage consumes the prior stage address and emits a new stage address.
Acceptance requires all stage states to be accepted, depth check count 458,
compliance acceptance, published release state, and the composed quality gate.

## Artifacts and projections

The six release artifacts remain:

1. `d07-fixture`;
2. `d07-evaluation`;
3. `d07-policy`;
4. `d07-review`;
5. `d07-lineage`;
6. `d07-metrics`.

The bundle command now writes four projections:

```text
bundle/fixture.json
bundle/runtime.json
bundle/release.json
bundle/report.json
```

The release projection contains artifact descriptors, release state, quality
checks, depth counters, and the compliance report. The report projection adds
receipt metrics, family distribution, result-state distribution, dictionary
size, completion percent, stage count, and compliance acceptance.

## Verification matrix

```text
python -m glio_noncode chromatin-architecture-fixture --output fixture.json
python -m glio_noncode chromatin-architecture-data-audit --input fixture.json --output audit.json
python -m glio_noncode chromatin-architecture-plan --input fixture.json --output plan.json
python -m glio_noncode evaluate-chromatin-architecture --input fixture.json --output evaluation.json
python -m glio_noncode chromatin-architecture-validation --input fixture.json --output validation.json
python -m glio_noncode chromatin-architecture-quality --input fixture.json --output quality.json
python -m glio_noncode chromatin-architecture-depth --input fixture.json --output depth.json
python -m glio_noncode chromatin-architecture-compliance --input fixture.json --output compliance.json
python -m glio_noncode chromatin-architecture-runtime --input fixture.json --output runtime.json
python -m glio_noncode chromatin-architecture-bundle --input fixture.json --output bundle
```

Expected values are 19 sources, 16 operations, 64 cases, 458 evaluation
checks, 14 quality checks, 24 stages, six artifacts, six result states, a
published release, four bundle files, and `accepted=true`.

## Regeneration rule

The fixture and runtime closure are generated products. Change the contract or
builder, regenerate both projections, run the focused tests and CLI matrix, and
commit the changed addresses together. A partial regeneration is not a valid
build because the content addresses would describe different serialized
surfaces.
