# D08 Depth Build

## Purpose

D08 closes the aggregate cell-state, disease-class, and territory surface as a deterministic execution product. The build is deliberately organized around inspectable joins rather than a single opaque evaluator. Every source, operation, case, execution, receipt, artifact, runtime stage, quality check, and release carries an address derived from its serialized content.

The depth target is a five-dimensional closure:

| Dimension | Target | Meaning |
| --- | ---: | --- |
| public sources | 18 | Four family registries are represented and each source is explicitly public aggregate data. |
| operations | 16 | C01-C16 are ordered and all capability contracts are present. |
| cases | 64 | Every operation has one positive path and three held controls. |
| families | 4 | Context, beta-context, alpha-context, and direct cell-state tranches are represented. |
| checks | 458 | Seven case checks plus ten global conservation checks close the evaluation. |

The minimum dimension ratio is reported by `depth_percent`. A healthy D08 fixture reaches 100.0 percent when all five targets are met. The report also exposes positive and control counts, family and plane distributions, addressed object counts, six result states, and three control issue codes.

## Contract expansion

The D08 source contract now records `public_aggregate`. The field is not inferred from the scope string: both values are checked. This prevents a source descriptor from appearing public only because a free-form scope happens to contain the expected token.

The D08 case contract now records `delegate_context_key`. This is separate from the case routing context. A family receipt can use a narrower context while the aggregate case still records the routing context that was tested. Foreign context controls retain the delegated key as a trace and carry `context_mismatch` as the explicit issue code.

Typed validation enforces:

1. exact source, operation, and case cardinalities;
2. contiguous operation ordinals;
3. all four family values;
4. four scenarios per operation;
5. source joins for operations and cases;
6. operation joins for cases;
7. allowed context keys only;
8. public source flags and public scope;
9. non-empty delegated contexts;
10. explicit mismatch issues on foreign controls;
11. deterministic content addresses.

## Seven checks per case

The case surface is intentionally redundant. A case passes only when all seven views agree:

1. `state` confirms accepted or review-held execution disposition;
2. `result` confirms the operation result state;
3. `issues` confirms the exact ordered issue tuple;
4. `counts` confirms primary and secondary conservation;
5. `address` confirms the output is content addressed;
6. `context` confirms delegated context retention and explicit foreign mismatch;
7. `receipt` reconciles the full expected/observed record.

This gives 448 case checks. The ten global checks then verify all receipts, the positive partition, the control partition, family context, operation coverage, case coverage, address coverage, positive state, per-operation balance, and context-control behavior. The full equation is `448 + 10 = 458`.

## Quality surface

The quality gate has twelve direct checks. It does not copy the data-audit checks into the quality record; instead, it records one quality decision for each major execution plane:

| Check | Closure |
| --- | --- |
| data-audit | public aggregate source and fixture audit accepted |
| plan | dependency plan accepted |
| evaluation | all case receipts and checks accepted |
| replay | repeated evaluation has the same address |
| artifacts | six artifacts are review safe |
| metrics | cardinality and partition invariants hold |
| lineage | source, operation, and case joins have no gaps |
| release | release state is published |
| ledger | 64 append-only events reconcile |
| compliance | aggregate boundary and payload rules pass |
| state-coverage | six result states are represented |
| control-surface | at least three issue codes are represented |

The runtime acceptance boolean requires the quality gate, compliance report, release, access policy, bundle, invariants, replay, plan, audit, review queue, and evaluation to all pass.

## Result-state coverage

The D08 result-state projection covers:

- `supported` for delegated family evidence;
- `accepted` for successful abundance, mapping, and OOD primitives;
- `published` for the final context publication operation;
- `out_of_domain` for foreign contexts;
- `invalid` for malformed payload controls;
- `contradictory` for identity-conflict controls.

Execution disposition remains separately represented as `accepted` or `review`. This distinction matters: a held control can have a meaningful result state while still being prohibited from positive delegation.

## Compliance boundary

Compliance walks object and array payloads recursively and reports both forbidden keys and their paths. It requires the public aggregate boundary, public source markers, source/operation/case addresses, and delegated contexts. Raw text projections are not expanded by the compliance walker; the public-data sanitizer removes restricted nested fields before the family summary enters the fixture.

The compliance result is included in the runtime closure and receives its own address. The `compliance-closed` stage must pass before `runtime-finalized` can be accepted.

## Artifact and bundle behavior

The six review-safe artifacts remain:

1. fixture;
2. audit;
3. evaluation;
4. review queue;
5. ledger;
6. source registry.

The bundle command writes four projections:

- `fixture.json` for the public aggregate contract;
- `runtime.json` for the complete typed runtime;
- `release.json` for artifacts, release, quality, and depth;
- `report.json` for the human-readable operational projection.

The runtime retains the bundle and access decisions internally. The release projection is not considered publishable unless the runtime acceptance boolean is true.

## Verification matrix

The minimum D08 verification sequence is:

```text
python -m glio_noncode cell-state-architecture-fixture --output fixture.json
python -m glio_noncode cell-state-architecture-data-audit --input fixture.json --output audit.json
python -m glio_noncode cell-state-architecture-plan --input fixture.json --output plan.json
python -m glio_noncode evaluate-cell-state-architecture --input fixture.json --output evaluation.json
python -m glio_noncode cell-state-architecture-quality --input fixture.json --output quality.json
python -m glio_noncode cell-state-architecture-depth --input fixture.json --output depth.json
python -m glio_noncode cell-state-architecture-runtime --input fixture.json --output runtime.json
python -m glio_noncode cell-state-architecture-compliance --input fixture.json --output compliance.json
python -m glio_noncode cell-state-architecture-validation --input fixture.json --output validation.json
python -m glio_noncode cell-state-architecture-bundle --input fixture.json --output bundle
```

Expected closure values are 18 sources, 16 operations, 64 cases, 458 evaluation checks, 12 quality checks, 24 runtime stages, six artifacts, six result states, three issue codes, published release state, and `accepted=true`.

## Change-control notes

Any change to a source, operation, case, context, payload sanitizer, check formula, quality threshold, or stage detail changes content addresses. Regenerate the checked-in fixture and runtime closure together. Run the focused tests and the D08 CLI matrix before committing. A partial regeneration is not a valid release because the fixture and runtime addresses would describe different builds.
