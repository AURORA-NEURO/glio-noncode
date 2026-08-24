# D08 Cell State, Disease Class & Territory

D08 is the public aggregate subsystem for contextualizing disease class, age routing, molecular state, malignant territory, developmental lineage, spatial niche, recurrence state, treatment-induced state, and cell-state evidence. It is a closed, typed build with independently addressable sources, operations, cases, receipts, review controls, artifacts, and a release boundary.

## Build shape

The aggregate contains 18 public source receipts, 16 operation specifications, 64 cases, 458 execution checks, six release artifacts, and a 24-stage runtime. Every operation has exactly four cases:

| Scenario | Cases per operation | Disposition |
| --- | ---: | --- |
| positive | 1 | delegate and accept |
| foreign_context | 1 | hold with `context_mismatch` |
| malformed_input | 1 | hold with `malformed_input` |
| identity_conflict | 1 | hold with `identity_conflict` |

The reference context is `GRCh38|glioma|adult|stem_like|tumor|unknown`. A pediatric context is retained as a deliberate foreign-context control. The boundary is `public_aggregate_cell_state_disease_territory`.

## Four family tranches

1. C01-C04 (`cell_context_frontier`) assembles disease ontology, adult-pediatric route, molecular class/state, and territory context.
2. C05-C08 (`cell_context_beta_frontier`) contributes developmental-lineage, glioblastoma malignant-state, IDH-mutant lineage-state, and H3K27-altered developmental-state priors.
3. C09-C12 (`cell_context_alpha_frontier`) contributes spatial niche, core-margin, recurrence, and treatment-induced state priors.
4. C13-C16 (`cell_state_frontier`) runs abundance intervals, single-cell reference mapping, cell-state OOD detection, and exact-context publication.

The first twelve operations delegate to the corresponding public family evaluators. The final four operations call the cell-state primitives directly. Every case also carries a delegated context key, so a positive receipt proves context retention and a foreign control proves an explicit mismatch. This keeps the aggregate contract broad while ensuring that its most sensitive state paths are executable and inspectable.

## Functional state paths

The abundance operation estimates a bounded proportion and interval from an aggregate cell count. The reference mapper exposes top score, second score, and margin. The OOD detector records distance, support score, and the declared support boundary. The publisher joins mapping, abundance, and OOD addresses into a published envelope under one exact context key.

Each positive path is paired with controls that stop before delegation. Controls are not converted into successful results and are not discarded from the release record. They become review-safe receipts and remain visible in the ledger, review queue, scenario matrix, and report.

## Release boundary

The runtime publishes only when typed validation, data audit, dependency planning, all 64 receipts, replay, artifacts, access checks, invariants, compliance, and the 12-check quality gate pass. The six artifacts are the fixture, audit, evaluation, review queue, ledger, and source registry. Each has a content address and public aggregate visibility.

This subsystem does not provide subject-level inference, treatment guidance, causal conclusions, or an implied clinical decision. It records aggregate evidence paths and their uncertainty or review state.

## Primary commands

```text
python -m glio_noncode cell-state-architecture-fixture --output fixture.json
python -m glio_noncode cell-state-architecture-data-audit --input fixture.json --output audit.json
python -m glio_noncode cell-state-architecture-plan --input fixture.json --output plan.json
python -m glio_noncode evaluate-cell-state-architecture --input fixture.json --output evaluation.json
python -m glio_noncode cell-state-architecture-runtime --input fixture.json --output runtime.json
python -m glio_noncode cell-state-architecture-quality --input fixture.json --output quality.json
python -m glio_noncode cell-state-architecture-depth --input fixture.json --output depth.json
python -m glio_noncode cell-state-architecture-report --input fixture.json --output report.json
python -m glio_noncode cell-state-architecture-bundle --input fixture.json --output bundle
```

The default fixture is generated from the checked-in public family receipts. A file input must preserve the D08 content address and all declared joins.
